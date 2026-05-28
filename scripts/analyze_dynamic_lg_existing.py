#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analyze existing CSV files for dynamic LG behavior.

LG_dynamic means:
    A case is solved if any available lookahead_LG_n mode solved it.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


DEFAULT_FILES = [
    ("graph_coloring", "graph_coloring_step2_18x60_summary_by_graph.csv", "graph_seed"),
    ("is_clique", "graph_is_clique_step2_20x60_summary_by_case.csv", "task:graph_seed"),
    ("vertex_cover", "vertex_cover_step1_small_summary_by_case.csv", "graph_seed"),
    ("subset_sum", "subset_sum_step1_small_summary_by_case.csv", "case_seed"),
    ("n_queens", "n_queens_step1_small_summary_by_case.csv", "n"),
    ("n_queens_dynamic", "n_queens_dynamic_lg_safe_summary_by_case.csv", "n"),
]


def parse_bool(value):
    return str(value).strip().lower() == "true"


def case_id(row, id_spec):
    if ":" in id_spec:
        return "|".join(row[p] for p in id_spec.split(":"))
    return row[id_spec]


def lg_depth(mode):
    if not mode.startswith("lookahead_LG_"):
        return None
    try:
        return int(mode.rsplit("_", 1)[1])
    except ValueError:
        return None


def analyze_file(label, path, id_spec):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            depth = lg_depth(row["mode"])
            if depth is None:
                continue
            row["depth"] = depth
            row["success_bool"] = parse_bool(row["success"])
            rows.append(row)

    by_case = defaultdict(list)
    by_depth = defaultdict(list)
    for row in rows:
        cid = case_id(row, id_spec)
        by_case[cid].append(row)
        by_depth[row["depth"]].append(row)

    depth_rows = []
    for depth in sorted(by_depth):
        items = by_depth[depth]
        success = sum(1 for row in items if row["success_bool"])
        total = len(items)
        depth_rows.append({
            "label": label,
            "depth": depth,
            "total": total,
            "success": success,
            "success_rate": success / total if total else 0,
        })

    dynamic_success = 0
    first_depth_counts = defaultdict(int)
    total_cases = len(by_case)

    for cid, items in by_case.items():
        solved_depths = sorted(row["depth"] for row in items if row["success_bool"])
        if solved_depths:
            dynamic_success += 1
            first_depth_counts[solved_depths[0]] += 1

    best_single = max((row["success"] for row in depth_rows), default=0)
    dynamic_row = {
        "label": label,
        "cases": total_cases,
        "best_single_success": best_single,
        "best_single_rate": best_single / total_cases if total_cases else 0,
        "dynamic_success": dynamic_success,
        "dynamic_rate": dynamic_success / total_cases if total_cases else 0,
        "dynamic_gain_over_best_single": dynamic_success - best_single,
        "first_depth_counts": " ".join(
            f"{depth}:{first_depth_counts[depth]}"
            for depth in sorted(first_depth_counts)
        ),
    }
    return depth_rows, dynamic_row


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-prefix", default="dynamic_lg_existing")
    args = parser.parse_args()

    all_depth_rows = []
    dynamic_rows = []

    for label, path, id_spec in DEFAULT_FILES:
        if not Path(path).exists():
            print(f"SKIP missing: {path}")
            continue
        depth_rows, dynamic_row = analyze_file(label, path, id_spec)
        all_depth_rows.extend(depth_rows)
        dynamic_rows.append(dynamic_row)

    write_csv(args.out_prefix + "_by_depth.csv", all_depth_rows)
    write_csv(args.out_prefix + "_summary.csv", dynamic_rows)

    print("=== LG DYNAMIC SUMMARY ===")
    for row in dynamic_rows:
        print(row)
    print("Files written:")
    print(args.out_prefix + "_by_depth.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
