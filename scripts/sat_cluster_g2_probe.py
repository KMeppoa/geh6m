#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cluster-level G2 probe for SAT.

G1:
    choose one variable assignment, then unit propagation.

G2:
    build variable clusters from co-occurrence in clauses.
    choose one cluster assignment, then unit propagation.

Cluster entropy:
    H_cluster = number of clusters that still contain at least one unassigned variable.

This is a lightweight structural probe, not a full SAT solver.
"""

import argparse
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat


class DSU:
    def __init__(self, items):
        self.parent = {x: x for x in items}
        self.size = {x: 1 for x in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union_if_small(self, a, b, max_size):
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return True
        if self.size[ra] + self.size[rb] > max_size:
            return False
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        return True


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def clause_vars(clause):
    return [abs(lit) for lit in clause]


def build_clusters(formula, n_vars, min_cooccur, max_cluster_size):
    counts = Counter()
    for clause in formula:
        vars_ = sorted(set(clause_vars(clause)))
        for i in range(len(vars_)):
            for j in range(i + 1, len(vars_)):
                counts[(vars_[i], vars_[j])] += 1

    dsu = DSU(range(1, n_vars + 1))
    for (a, b), count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        if count < min_cooccur:
            break
        dsu.union_if_small(a, b, max_cluster_size)

    groups = defaultdict(list)
    for var in range(1, n_vars + 1):
        groups[dsu.find(var)].append(var)

    clusters = list(groups.values())
    clusters.sort(key=lambda c: (-len(c), c[0]))
    var_to_cluster = {}
    for idx, cluster in enumerate(clusters):
        for var in cluster:
            var_to_cluster[var] = idx
    return clusters, var_to_cluster, counts


def polarity_assignment(formula):
    pos = Counter()
    neg = Counter()
    for clause in formula:
        for lit in clause:
            if lit > 0:
                pos[lit] += 1
            else:
                neg[-lit] += 1
    return {var: pos[var] >= neg[var] for var in set(pos) | set(neg)}


def cluster_h(clusters, assignment):
    unassigned_clusters = 0
    for cluster in clusters:
        if any(var not in assignment for var in cluster):
            unassigned_clusters += 1
    return unassigned_clusters


def choose_g1_action(formula, assignment, n_vars, rng, sample_actions):
    actions = sat.possible_actions(n_vars, assignment)
    if sample_actions and len(actions) > sample_actions:
        actions = rng.sample(actions, sample_actions)
    ranked = []
    for var, value in actions:
        trial = dict(assignment)
        trial[var] = value
        score = sat.score_LG(formula, trial, n_vars)
        ranked.append((score, var, value))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    _, var, value = ranked[0]
    return var, value


def apply_g1(formula, n_vars, rng, sample_actions):
    assignment = {}
    var, value = choose_g1_action(formula, assignment, n_vars, rng, sample_actions)
    after_action = {var: value}
    conflict, propagated, forced = sat.unit_propagate(formula, after_action, n_vars)
    return conflict, after_action, propagated, forced


def choose_g2_cluster(formula, n_vars, clusters, rng, sample_clusters):
    polarity = polarity_assignment(formula)
    candidates = [idx for idx, cluster in enumerate(clusters) if len(cluster) > 1]
    if not candidates:
        candidates = list(range(len(clusters)))
    if sample_clusters and len(candidates) > sample_clusters:
        candidates = rng.sample(candidates, sample_clusters)

    ranked = []
    for idx in candidates:
        assignment = {var: polarity.get(var, True) for var in clusters[idx]}
        conflict, propagated, forced = sat.unit_propagate(formula, assignment, n_vars)
        h_after = len(sat.unassigned_vars(n_vars, propagated))
        score = 10_000_000 if conflict else h_after
        ranked.append((score, -len(clusters[idx]), idx, assignment, propagated, forced, conflict))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    _, _, idx, assignment, propagated, forced, conflict = ranked[0]
    return idx, assignment, propagated, forced, conflict


def probe_formula(n_vars, n_clauses, k, seed, args):
    rng = random.Random(seed + 20260526)
    formula = sat.generate_random_k_sat(n_vars, n_clauses, k, seed)
    clusters, var_to_cluster, counts = build_clusters(
        formula, n_vars, args.min_cooccur, args.max_cluster_size
    )

    h_var_start = n_vars
    h_cluster_start = len(clusters)

    conflict1, g1_action_assignment, g1_propagated, forced1 = apply_g1(
        formula, n_vars, rng, args.sample_actions
    )
    h_var_g1 = len(sat.unassigned_vars(n_vars, g1_propagated))
    h_cluster_g1 = cluster_h(clusters, g1_propagated)

    cluster_idx, g2_assignment, g2_propagated, forced2, conflict2 = choose_g2_cluster(
        formula, n_vars, clusters, rng, args.sample_clusters
    )
    h_var_g2 = len(sat.unassigned_vars(n_vars, g2_propagated))
    h_cluster_g2 = cluster_h(clusters, g2_propagated)

    non_singleton = [c for c in clusters if len(c) > 1]
    return {
        "seed": seed,
        "n_vars": n_vars,
        "n_clauses": n_clauses,
        "ratio": n_clauses / n_vars,
        "cluster_count": len(clusters),
        "non_singleton_clusters": len(non_singleton),
        "max_cluster_size_seen": max(len(c) for c in clusters),
        "avg_cluster_size": sum(len(c) for c in clusters) / len(clusters),
        "H_var_start": h_var_start,
        "H_cluster_start": h_cluster_start,
        "H_var_after_G1": h_var_g1,
        "H_cluster_after_G1": h_cluster_g1,
        "H_var_after_G2": h_var_g2,
        "H_cluster_after_G2": h_cluster_g2,
        "IG_var_G1": h_var_start - h_var_g1,
        "IG_cluster_G1": h_cluster_start - h_cluster_g1,
        "IG_var_G2": h_var_start - h_var_g2,
        "IG_cluster_G2": h_cluster_start - h_cluster_g2,
        "forced_G1": forced1,
        "forced_G2": forced2,
        "chosen_cluster_size": len(clusters[cluster_idx]),
        "conflict_G1": conflict1,
        "conflict_G2": conflict2,
    }


def summarize(rows):
    summary = []
    for n_vars in sorted({row["n_vars"] for row in rows}):
        items = [row for row in rows if row["n_vars"] == n_vars]
        out = {"n_vars": n_vars, "samples": len(items)}
        keys = [
            "cluster_count",
            "non_singleton_clusters",
            "max_cluster_size_seen",
            "avg_cluster_size",
            "IG_var_G1",
            "IG_cluster_G1",
            "IG_var_G2",
            "IG_cluster_G2",
            "forced_G1",
            "forced_G2",
            "chosen_cluster_size",
        ]
        for key in keys:
            out[f"avg_{key}"] = sum(row[key] for row in items) / len(items)
        out["D_pred_var_G1"] = n_vars / out["avg_IG_var_G1"] if out["avg_IG_var_G1"] > 0 else ""
        out["D_pred_var_G2"] = n_vars / out["avg_IG_var_G2"] if out["avg_IG_var_G2"] > 0 else ""
        out["conflicts_G1"] = sum(1 for row in items if row["conflict_G1"])
        out["conflicts_G2"] = sum(1 for row in items if row["conflict_G2"])
        summary.append(out)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[50, 100, 200])
    parser.add_argument("--formulas", type=int, default=3)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--min-cooccur", type=int, default=2)
    parser.add_argument("--max-cluster-size", type=int, default=8)
    parser.add_argument("--sample-actions", type=int, default=200)
    parser.add_argument("--sample-clusters", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_cluster_g2_probe_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT CLUSTER G2 PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows.append(probe_formula(n_vars, n_clauses, args.k, seed, args))
        print("  done")

    summary = summarize(rows)
    write_csv(Path(args.out_prefix + "_details.csv"), rows)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary)

    print("\n=== SUMMARY ===")
    for row in summary:
        print(
            f"n={row['n_vars']} "
            f"clusters={row['avg_cluster_count']:.1f} "
            f"avg_cluster={row['avg_avg_cluster_size']:.2f} "
            f"IG1={row['avg_IG_var_G1']:.2f} "
            f"IG2={row['avg_IG_var_G2']:.2f} "
            f"D1={row['D_pred_var_G1'] if row['D_pred_var_G1'] == '' else round(row['D_pred_var_G1'], 2)} "
            f"D2={row['D_pred_var_G2'] if row['D_pred_var_G2'] == '' else round(row['D_pred_var_G2'], 2)}"
        )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
