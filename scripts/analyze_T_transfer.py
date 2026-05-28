#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
T-analysis for L/G experiments.

T is a task measurement:
    How much does G help compared to L?

For each task and each depth pair L vs LG, compute:
    success_gain = LG_success_rate - L_success_rate
    decision_gain = L_avg_decision_steps - LG_avg_decision_steps
    forced = LG_avg_forced_steps
    T = success_gain + 0.05 * decision_gain + 0.02 * forced

This is not a proof. It is a practical transfer signal:
    if T is high on one task, LG-style solving is likely useful.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


DATASETS = [
    ("sat16x40", "clean_stats_v5_16x40_summary_by_formula.csv", "formula_seed"),
    ("graph_coloring", "graph_coloring_step2_18x60_summary_by_graph.csv", "graph_seed"),
    ("is_clique", "graph_is_clique_step2_20x60_summary_by_case.csv", "task:graph_seed"),
    ("vertex_cover", "vertex_cover_step1_small_summary_by_case.csv", "graph_seed"),
    ("subset_sum", "subset_sum_step1_small_summary_by_case.csv", "case_seed"),
    ("n_queens", "n_queens_step1_small_summary_by_case.csv", "n"),
]


PAIRS = [
    ("greedy_L", "greedy_LG", "greedy"),
    ("lookahead_L_2", "lookahead_LG_2", "depth2"),
    ("lookahead_L_3", "lookahead_LG_3", "depth3"),
]


def parse_bool(value):
    return str(value).strip().lower() == "true"


def case_id(row, id_spec):
    if ":" in id_spec:
        return "|".join(row[p] for p in id_spec.split(":"))
    return row[id_spec]


def number(row, key):
    value = row.get(key, "")
    return float(value) if value not in ("", None) else 0.0


def load_dataset(path, id_spec):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["_case_id"] = case_id(row, id_spec)
            row["_success"] = parse_bool(row["success"])
            row["_decision"] = number(row, "decision_steps")
            row["_forced"] = number(row, "forced_steps")
            rows.append(row)
    return rows


def summarize_mode(rows, mode):
    items = [row for row in rows if row["mode"] == mode]
    total = len(items)
    if total == 0:
        return None
    return {
        "total": total,
        "success": sum(1 for row in items if row["_success"]),
        "success_rate": sum(1 for row in items if row["_success"]) / total,
        "avg_decision": sum(row["_decision"] for row in items) / total,
        "avg_forced": sum(row["_forced"] for row in items) / total,
    }


def paired_counts(rows, mode_l, mode_lg):
    idx = {(row["_case_id"], row["mode"]): row for row in rows}
    case_ids = sorted({row["_case_id"] for row in rows})
    lg_only = l_only = both = neither = compared = 0
    for cid in case_ids:
        if (cid, mode_l) not in idx or (cid, mode_lg) not in idx:
            continue
        compared += 1
        l_success = idx[(cid, mode_l)]["_success"]
        lg_success = idx[(cid, mode_lg)]["_success"]
        if l_success and lg_success:
            both += 1
        elif l_success and not lg_success:
            l_only += 1
        elif lg_success and not l_success:
            lg_only += 1
        else:
            neither += 1
    return compared, lg_only, l_only, both, neither


def analyze_dataset(label, rows):
    output = []
    for mode_l, mode_lg, pair_name in PAIRS:
        l_sum = summarize_mode(rows, mode_l)
        lg_sum = summarize_mode(rows, mode_lg)
        if l_sum is None or lg_sum is None:
            continue

        success_gain = lg_sum["success_rate"] - l_sum["success_rate"]
        decision_gain = l_sum["avg_decision"] - lg_sum["avg_decision"]
        forced = lg_sum["avg_forced"]
        t_score = success_gain + 0.05 * decision_gain + 0.02 * forced
        compared, lg_only, l_only, both, neither = paired_counts(rows, mode_l, mode_lg)

        output.append({
            "dataset": label,
            "pair": pair_name,
            "mode_l": mode_l,
            "mode_lg": mode_lg,
            "l_success_rate": l_sum["success_rate"],
            "lg_success_rate": lg_sum["success_rate"],
            "success_gain": success_gain,
            "l_avg_decision": l_sum["avg_decision"],
            "lg_avg_decision": lg_sum["avg_decision"],
            "decision_gain": decision_gain,
            "lg_avg_forced": forced,
            "T_score": t_score,
            "paired_compared": compared,
            "paired_lg_only": lg_only,
            "paired_l_only": l_only,
            "paired_both": both,
            "paired_neither": neither,
        })
    return output


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="T_transfer_analysis.csv")
    args = parser.parse_args()

    all_rows = []
    for label, path, id_spec in DATASETS:
        if not Path(path).exists():
            print(f"SKIP missing: {path}")
            continue
        rows = load_dataset(path, id_spec)
        all_rows.extend(analyze_dataset(label, rows))

    write_csv(args.out, all_rows)

    print("=== T TRANSFER ANALYSIS ===")
    for row in sorted(all_rows, key=lambda r: (r["dataset"], r["pair"])):
        print(
            f"{row['dataset']} {row['pair']}: "
            f"T={row['T_score']:.3f}, "
            f"success_gain={row['success_gain']:.3f}, "
            f"decision_gain={row['decision_gain']:.2f}, "
            f"forced={row['lg_avg_forced']:.2f}, "
            f"LG_only={row['paired_lg_only']}, L_only={row['paired_l_only']}"
        )

    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
