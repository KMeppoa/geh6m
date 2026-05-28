#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reliability-aware SAT cluster probe.

Old clusters:
    variables that often co-occur.

New clusters:
    signed compatible assignments that co-occur and do not immediately conflict.

Example:
    clause (x1 OR !x2 OR x7) contributes signed links:
        x1=True with x2=False
        x1=True with x7=True
        x2=False with x7=True

The cluster stores assignments {var: value}. Merging is allowed only if:
    - no variable gets two different values;
    - unit propagation on the merged assignment does not conflict.

R is measured against planted SAT hidden assignment.
"""

import argparse
import csv
import random
from collections import Counter
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat
from sat_recursive_cluster_reliability import generate_planted_k_sat


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def lit_assignment(lit):
    return abs(lit), lit > 0


def merge_assignments(a, b):
    merged = dict(a)
    for var, value in b.items():
        if var in merged and merged[var] != value:
            return None
        merged[var] = value
    return merged


def build_signed_compatible_clusters(formula, n_vars, min_cooccur, max_cluster_size, check_unit):
    literal_pair_counts = Counter()
    for clause in formula:
        lits = sorted(set(clause), key=lambda lit: (abs(lit), lit < 0))
        for i in range(len(lits)):
            for j in range(i + 1, len(lits)):
                a = lit_assignment(lits[i])
                b = lit_assignment(lits[j])
                if a[0] == b[0]:
                    continue
                literal_pair_counts[(a, b)] += 1

    clusters = [{var: value} for var in range(1, n_vars + 1) for value in (False, True)]

    def find_cluster_index(var, value):
        for idx, cluster in enumerate(clusters):
            if len(cluster) == 1 and cluster.get(var) == value:
                return idx
        return None

    # Direct lookup for singleton starts. Later we scan because cluster count is small enough for probe scale.
    singleton_index = {
        (var, value): idx
        for idx, cluster in enumerate(clusters)
        for var, value in cluster.items()
    }

    for (a, b), count in sorted(literal_pair_counts.items(), key=lambda item: (-item[1], item[0])):
        if count < min_cooccur:
            break
        idx_a = None
        idx_b = None
        for idx, cluster in enumerate(clusters):
            if a[0] in cluster and cluster[a[0]] == a[1]:
                idx_a = idx
            if b[0] in cluster and cluster[b[0]] == b[1]:
                idx_b = idx
            if idx_a is not None and idx_b is not None:
                break
        if idx_a is None:
            idx_a = singleton_index.get(a)
        if idx_b is None:
            idx_b = singleton_index.get(b)
        if idx_a is None or idx_b is None or idx_a == idx_b:
            continue

        merged = merge_assignments(clusters[idx_a], clusters[idx_b])
        if merged is None or len(merged) > max_cluster_size:
            continue
        if check_unit:
            conflict, _, _ = sat.unit_propagate(formula, merged, n_vars)
            if conflict:
                continue

        keep = min(idx_a, idx_b)
        drop = max(idx_a, idx_b)
        clusters[keep] = merged
        clusters.pop(drop)

    # Remove duplicate assignment clusters.
    unique = {}
    for cluster in clusters:
        key = tuple(sorted(cluster.items()))
        unique[key] = cluster
    clusters = list(unique.values())
    clusters.sort(key=lambda c: (-len(c), sorted(c.items())))
    return clusters


def assignment_reliability(assignment, planted):
    if not assignment:
        return 1.0, True
    matches = sum(1 for var, value in assignment.items() if planted[var] == value)
    return matches / len(assignment), matches == len(assignment)


def choose_best_cluster(formula, n_vars, clusters, sample_clusters, rng):
    candidates = clusters
    if sample_clusters and len(candidates) > sample_clusters:
        candidates = rng.sample(candidates, sample_clusters)
    ranked = []
    for cluster in candidates:
        conflict, propagated, forced = sat.unit_propagate(formula, cluster, n_vars)
        score = 10_000_000 if conflict else len(sat.unassigned_vars(n_vars, propagated))
        ranked.append((score, -len(cluster), cluster, propagated, forced, conflict))
    ranked.sort(key=lambda item: (item[0], item[1], sorted(item[2].items())))
    _, _, cluster, propagated, forced, conflict = ranked[0]
    return cluster, propagated, forced, conflict


def probe_formula(n_vars, n_clauses, args, seed):
    rng = random.Random(seed + 526526)
    formula, planted = generate_planted_k_sat(n_vars, n_clauses, 3, seed)
    clusters = build_signed_compatible_clusters(
        formula,
        n_vars,
        args.min_cooccur,
        args.max_cluster_size,
        args.check_unit,
    )
    cluster, propagated, forced, conflict = choose_best_cluster(
        formula, n_vars, clusters, args.sample_clusters, rng
    )
    choice_r, choice_all = assignment_reliability(cluster, planted)
    prop_r, prop_all = assignment_reliability(propagated, planted)
    ig = n_vars - len(sat.unassigned_vars(n_vars, propagated))
    useful_ig_choice = ig * choice_r
    useful_ig_prop = ig * prop_r
    return {
        "seed": seed,
        "n_vars": n_vars,
        "n_clauses": n_clauses,
        "cluster_count": len(clusters),
        "max_cluster_size_seen": max(len(c) for c in clusters),
        "avg_cluster_size": sum(len(c) for c in clusters) / len(clusters),
        "chosen_cluster_size": len(cluster),
        "IG": ig,
        "forced": forced,
        "R_choice_fraction": choice_r,
        "R_choice_all_match": choice_all,
        "R_propagated_fraction": prop_r,
        "R_propagated_all_match": prop_all,
        "useful_IG_choice": useful_ig_choice,
        "useful_IG_propagated": useful_ig_prop,
        "D_pred_IG": n_vars / ig if ig > 0 else "",
        "D_pred_useful_choice": n_vars / useful_ig_choice if useful_ig_choice > 0 else "",
        "D_pred_useful_propagated": n_vars / useful_ig_prop if useful_ig_prop > 0 else "",
        "conflict": conflict,
    }


def summarize(rows):
    summary = []
    for n_vars in sorted({row["n_vars"] for row in rows}):
        items = [row for row in rows if row["n_vars"] == n_vars]
        out = {"n_vars": n_vars, "samples": len(items)}
        for key in [
            "cluster_count",
            "max_cluster_size_seen",
            "avg_cluster_size",
            "chosen_cluster_size",
            "IG",
            "forced",
            "R_choice_fraction",
            "R_propagated_fraction",
            "useful_IG_choice",
            "useful_IG_propagated",
        ]:
            out[f"avg_{key}"] = sum(row[key] for row in items) / len(items)
        out["R_choice_success_rate"] = sum(1 for row in items if row["R_choice_all_match"]) / len(items)
        out["R_propagated_success_rate"] = sum(1 for row in items if row["R_propagated_all_match"]) / len(items)
        out["D_pred_IG"] = n_vars / out["avg_IG"] if out["avg_IG"] > 0 else ""
        out["D_pred_useful_choice"] = n_vars / out["avg_useful_IG_choice"] if out["avg_useful_IG_choice"] > 0 else ""
        out["D_pred_useful_propagated"] = n_vars / out["avg_useful_IG_propagated"] if out["avg_useful_IG_propagated"] > 0 else ""
        out["conflicts"] = sum(1 for row in items if row["conflict"])
        summary.append(out)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[100, 200, 500, 1000])
    parser.add_argument("--formulas", type=int, default=3)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--min-cooccur", type=int, default=1)
    parser.add_argument("--max-cluster-size", type=int, default=8)
    parser.add_argument("--sample-clusters", type=int, default=300)
    parser.add_argument("--check-unit", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_compatible_cluster_reliability_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT COMPATIBLE CLUSTER RELIABILITY ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows.append(probe_formula(n_vars, n_clauses, args, seed))
        print("  done")

    summary = summarize(rows)
    write_csv(Path(args.out_prefix + "_details.csv"), rows)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary)

    print("\n=== SUMMARY ===")
    for row in summary:
        print(
            f"n={row['n_vars']} "
            f"IG={row['avg_IG']:.2f} "
            f"R_choice={row['R_choice_success_rate']:.2f} "
            f"R_frac={row['avg_R_choice_fraction']:.2f} "
            f"usefulIG={row['avg_useful_IG_choice']:.2f} "
            f"D_useful={row['D_pred_useful_choice'] if row['D_pred_useful_choice'] == '' else round(row['D_pred_useful_choice'], 2)}"
        )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
