#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Recursive cluster scaling probe for SAT.

Level 0:
    variables.

Level 1:
    clusters of variables built by clause co-occurrence.

Level 2+:
    clusters of clusters. Two units are connected if variables from both units
    co-occur in clauses often enough.

This is a structural scaling probe. It does not solve SAT. It estimates whether
changing scale can keep information gain above a threshold.
"""

import argparse
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat


class DSU:
    def __init__(self, n):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union_if_small(self, a, b, max_weight, weights):
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return True
        if weights[ra] + weights[rb] > max_weight:
            return False
        if weights[ra] < weights[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        weights[ra] += weights[rb]
        return True


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def clause_vars(clause):
    return sorted(set(abs(lit) for lit in clause))


def build_next_level(
    formula_var_sets,
    units,
    var_to_unit,
    min_cooccur,
    max_unit_weight,
    unit_scores=None,
    reserve_bias=0.0,
):
    edge_counts = Counter()
    for vars_ in formula_var_sets:
        touched = sorted(set(var_to_unit[v] for v in vars_))
        for i in range(len(touched)):
            for j in range(i + 1, len(touched)):
                edge_counts[(touched[i], touched[j])] += 1

    if unit_scores is None:
        unit_scores = [0.0] * len(units)

    dsu = DSU(len(units))
    weights = [len(unit) for unit in units]
    def edge_priority(item):
        (a, b), count = item
        score_sum = unit_scores[a] + unit_scores[b]
        adjusted = count + reserve_bias * score_sum
        return (-adjusted, -count, -score_sum, a, b)

    eligible_edges = []
    for item in edge_counts.items():
        (a, b), count = item
        score_sum = unit_scores[a] + unit_scores[b]
        adjusted = count + reserve_bias * score_sum
        if count >= min_cooccur or (reserve_bias > 0 and score_sum > 0 and adjusted >= min_cooccur):
            eligible_edges.append(item)
    for (a, b), count in sorted(eligible_edges, key=edge_priority):
        dsu.union_if_small(a, b, max_unit_weight, weights)

    grouped = defaultdict(list)
    for idx, unit in enumerate(units):
        grouped[dsu.find(idx)].extend(unit)

    new_units = [sorted(values) for values in grouped.values()]
    new_units.sort(key=lambda unit: (-len(unit), unit[0]))
    new_var_to_unit = {}
    for idx, unit in enumerate(new_units):
        for var in unit:
            new_var_to_unit[var] = idx
    return new_units, new_var_to_unit, edge_counts


def estimate_level_ig(units, sample_units, rng):
    candidates = [unit for unit in units if unit]
    if sample_units and len(candidates) > sample_units:
        candidates = rng.sample(candidates, sample_units)
    if not candidates:
        return 0.0, 0, 0, 0.0
    sizes = [len(unit) for unit in candidates]
    avg_size = sum(sizes) / len(sizes)
    max_size = max(sizes)
    non_singleton = sum(1 for size in sizes if size > 1)
    # Best sampled unit approximates what a guided choice would prefer.
    best_ig = max_size
    return best_ig, max_size, non_singleton, avg_size


def probe_formula(n_vars, n_clauses, args, seed):
    rng = random.Random(seed + 7727)
    formula = sat.generate_random_k_sat(n_vars, n_clauses, 3, seed)
    formula_var_sets = [clause_vars(clause) for clause in formula]

    units = [[v] for v in range(1, n_vars + 1)]
    var_to_unit = {v: v - 1 for v in range(1, n_vars + 1)}

    rows = []
    levels_needed = ""
    previous_count = len(units)

    for level in range(1, args.max_levels + 1):
        max_weight = args.base_max_cluster_size * level
        units, var_to_unit, edge_counts = build_next_level(
            formula_var_sets,
            units,
            var_to_unit,
            args.min_cooccur,
            max_weight,
        )
        best_ig, max_size, non_singleton_sample, avg_sample_size = estimate_level_ig(
            units, args.sample_units, rng
        )
        avg_unit_size = sum(len(unit) for unit in units) / len(units)
        non_singleton_total = sum(1 for unit in units if len(unit) > 1)
        rows.append({
            "seed": seed,
            "n_vars": n_vars,
            "n_clauses": n_clauses,
            "level": level,
            "unit_count": len(units),
            "previous_unit_count": previous_count,
            "avg_unit_size": avg_unit_size,
            "max_unit_size": max(len(unit) for unit in units),
            "non_singleton_units": non_singleton_total,
            "sample_best_IG": best_ig,
            "sample_max_size": max_size,
            "sample_avg_size": avg_sample_size,
            "sample_non_singleton": non_singleton_sample,
            "D_pred_by_best_IG": n_vars / best_ig if best_ig > 0 else "",
            "above_threshold": best_ig >= args.ig_threshold,
            "edge_count_between_units": len(edge_counts),
        })
        if best_ig >= args.ig_threshold and levels_needed == "":
            levels_needed = level
        previous_count = len(units)

    return rows, levels_needed


def summarize(detail_rows, level_rows):
    summary = []
    for n_vars in sorted({row["n_vars"] for row in detail_rows}):
        items = [row for row in detail_rows if row["n_vars"] == n_vars]
        for level in sorted({row["level"] for row in items}):
            level_items = [row for row in items if row["level"] == level]
            summary.append({
                "n_vars": n_vars,
                "level": level,
                "samples": len(level_items),
                "avg_unit_count": sum(row["unit_count"] for row in level_items) / len(level_items),
                "avg_unit_size": sum(row["avg_unit_size"] for row in level_items) / len(level_items),
                "avg_max_unit_size": sum(row["max_unit_size"] for row in level_items) / len(level_items),
                "avg_sample_best_IG": sum(row["sample_best_IG"] for row in level_items) / len(level_items),
                "avg_D_pred": sum(float(row["D_pred_by_best_IG"]) for row in level_items if row["D_pred_by_best_IG"] != "") / len(level_items),
                "above_threshold_count": sum(1 for row in level_items if row["above_threshold"]),
            })
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[100, 200, 500, 1000])
    parser.add_argument("--formulas", type=int, default=2)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--min-cooccur", type=int, default=2)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--ig-threshold", type=float, default=2.0)
    parser.add_argument("--max-levels", type=int, default=5)
    parser.add_argument("--sample-units", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_recursive_cluster_levels_step1")
    args = parser.parse_args()

    details = []
    level_needed_rows = []

    print("=== SAT RECURSIVE CLUSTER LEVELS ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows, levels_needed = probe_formula(n_vars, n_clauses, args, seed)
            details.extend(rows)
            level_needed_rows.append({
                "n_vars": n_vars,
                "seed": seed,
                "levels_needed_for_threshold": levels_needed,
            })
        print("  done")

    summary = summarize(details, level_needed_rows)
    write_csv(Path(args.out_prefix + "_details.csv"), details)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary)
    write_csv(Path(args.out_prefix + "_levels_needed.csv"), level_needed_rows)

    print("\n=== SUMMARY ===")
    for row in summary:
        if row["level"] in (1, args.max_levels):
            print(
                f"n={row['n_vars']} level={row['level']} "
                f"bestIG={row['avg_sample_best_IG']:.2f} "
                f"D={row['avg_D_pred']:.2f} "
                f"unit_count={row['avg_unit_count']:.1f}"
            )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")
    print(args.out_prefix + "_levels_needed.csv")


if __name__ == "__main__":
    main()
