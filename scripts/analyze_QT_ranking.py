#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Q/T ranking for completed L/G experiments.

Q = task difficulty for local L:
    Q = 1 - success_rate(L)

T = benefit of G:
    T_simple = success_rate(LG) - success_rate(L)
    T_full = T_simple + 0.05 * decision_gain + 0.02 * forced_steps
"""

import argparse
import csv
from pathlib import Path


DATASETS = [
    ("SAT", "clean_stats_v5_16x40_summary_by_formula.csv"),
    ("Graph Coloring", "graph_coloring_step2_18x60_summary_by_graph.csv"),
    ("Clique+Independent Set", "graph_is_clique_step2_20x60_summary_by_case.csv"),
    ("Vertex Cover", "vertex_cover_step1_small_summary_by_case.csv"),
    ("Subset Sum", "subset_sum_step1_small_summary_by_case.csv"),
    ("N-Queens", "n_queens_step1_small_summary_by_case.csv"),
]


PAIRS = [
    ("greedy_L", "greedy_LG", "greedy"),
    ("lookahead_L_2", "lookahead_LG_2", "depth2"),
    ("lookahead_L_3", "lookahead_LG_3", "depth3"),
]


def parse_bool(value):
    return str(value).strip().lower() == "true"


def number(row, key):
    value = row.get(key, "")
    return float(value) if value not in ("", None) else 0.0


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def groups_for_dataset(label, rows):
    if label == "Clique+Independent Set":
        groups = {}
        for task in sorted({row["task"] for row in rows}):
            pretty = "Clique" if task == "clique" else "Independent Set"
            groups[pretty] = [row for row in rows if row["task"] == task]
        return groups
    return {label: rows}


def summarize_mode(rows, mode):
    items = [row for row in rows if row["mode"] == mode]
    total = len(items)
    if total == 0:
        return None
    success = sum(1 for row in items if parse_bool(row["success"]))
    return {
        "total": total,
        "success_rate": success / total,
        "avg_decision": sum(number(row, "decision_steps") for row in items) / total,
        "avg_forced": sum(number(row, "forced_steps") for row in items) / total,
    }


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="QT_ranking.csv")
    args = parser.parse_args()

    output = []
    for label, path in DATASETS:
        if not Path(path).exists():
            print(f"SKIP missing: {path}")
            continue
        rows = load_rows(path)
        for task_name, task_rows in groups_for_dataset(label, rows).items():
            for l_mode, lg_mode, pair_name in PAIRS:
                l_sum = summarize_mode(task_rows, l_mode)
                lg_sum = summarize_mode(task_rows, lg_mode)
                if not l_sum or not lg_sum:
                    continue

                q = 1 - l_sum["success_rate"]
                success_gain = lg_sum["success_rate"] - l_sum["success_rate"]
                decision_gain = l_sum["avg_decision"] - lg_sum["avg_decision"]
                forced = lg_sum["avg_forced"]
                t_full = success_gain + 0.05 * decision_gain + 0.02 * forced
                tq_product = q * t_full

                output.append({
                    "task": task_name,
                    "pair": pair_name,
                    "L_success": l_sum["success_rate"],
                    "LG_success": lg_sum["success_rate"],
                    "Q_difficulty": q,
                    "T_simple_success_gain": success_gain,
                    "T_full": t_full,
                    "QT_product": tq_product,
                    "decision_gain": decision_gain,
                    "LG_forced_steps": forced,
                })

    output.sort(key=lambda row: row["QT_product"], reverse=True)
    write_csv(args.out, output)

    print("=== Q/T RANKING ===")
    for row in output:
        print(
            f"{row['task']} {row['pair']}: "
            f"Q={row['Q_difficulty']:.3f}, "
            f"T={row['T_full']:.3f}, "
            f"Q*T={row['QT_product']:.3f}, "
            f"L={row['L_success']:.3f}, LG={row['LG_success']:.3f}"
        )
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
