#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analyze fast D-scaling sweep CSV files.

Inputs are *_fast.csv files produced by sat_fast_d_scaling_probe.py.
The analyzer focuses on level 5 and computes numeric medians plus simple
threshold checks for ratio_54 and ratio_43.
"""

import argparse
import csv
import math
from pathlib import Path


def read_rows(paths):
    rows = []
    for path in paths:
        with Path(path).open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
    return rows


def as_float(value):
    if value == "" or value is None:
        return None
    return float(value)


def median(values):
    vals = sorted(value for value in values if value is not None)
    if not vals:
        return ""
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def summarize_level5(rows):
    level5 = [row for row in rows if row["level"] == "5"]
    groups = {}
    for row in level5:
        key = (
            row["n"],
            row.get("min_useful_growth", ""),
            row.get("topdown_bias", ""),
            row.get("sample_units", ""),
            row.get("candidate_cap", ""),
            row.get("top_neighbors", ""),
        )
        groups.setdefault(key, []).append(row)

    summary = []
    for key, items in sorted(groups.items(), key=lambda item: int(item[0][0])):
        ratios = [as_float(row["improvement_ratio"]) for row in items]
        baseline_d = [as_float(row["baseline_D"]) for row in items]
        after_d = [as_float(row["after_D"]) for row in items]
        useful = [as_float(row["useful_IG"]) for row in items]
        useful_after = [as_float(row["useful_IG_after_rebuild"]) for row in items]
        improved = [ratio for ratio in ratios if ratio is not None and ratio > 1.0]
        worsened = [ratio for ratio in ratios if ratio is not None and ratio < 1.0]
        valid_ratios = [ratio for ratio in ratios if ratio is not None and ratio > 0]
        log_ratios = [math.log(ratio) for ratio in valid_ratios]
        n, growth, bias, sample_units, candidate_cap, top_neighbors = key
        summary.append({
            "n": n,
            "min_useful_growth": growth,
            "topdown_bias": bias,
            "sample_units": sample_units,
            "candidate_cap": candidate_cap,
            "top_neighbors": top_neighbors,
            "seeds": len(items),
            "triggered": sum(1 for row in items if row["rebuild_triggered"] == "True"),
            "median_baseline_D": median(baseline_d),
            "median_after_D": median(after_d),
            "median_improvement_ratio": median(ratios),
            "median_log_improvement": median(log_ratios),
            "win_rate": (len(improved) / len(valid_ratios)) if valid_ratios else "",
            "harm_rate": (len(worsened) / len(valid_ratios)) if valid_ratios else "",
            "improved_count": len(improved),
            "worsened_count": len(worsened),
            "median_useful_IG": median(useful),
            "median_useful_IG_after": median(useful_after),
        })
    return summary


def threshold_rows(rows, ratio_field, thresholds):
    level5 = [row for row in rows if row["level"] == "5"]
    output = []
    for threshold in thresholds:
        items = [
            row for row in level5
            if as_float(row.get(ratio_field, "")) is not None
            and as_float(row.get(ratio_field, "")) < threshold
            and as_float(row.get("improvement_ratio", "")) is not None
        ]
        ratios = [as_float(row["improvement_ratio"]) for row in items]
        valid_ratios = [ratio for ratio in ratios if ratio is not None and ratio > 0]
        improved = [ratio for ratio in valid_ratios if ratio > 1.0]
        worsened = [ratio for ratio in valid_ratios if ratio < 1.0]
        log_ratios = [math.log(ratio) for ratio in valid_ratios]
        output.append({
            "ratio_field": ratio_field,
            "C": threshold,
            "cases": len(items),
            "improved_count": len(improved),
            "worsened_count": len(worsened),
            "improved_rate": (len(improved) / len(items)) if items else "",
            "harm_rate": (len(worsened) / len(items)) if items else "",
            "median_improvement_ratio": median(ratios),
            "median_log_improvement": median(log_ratios),
        })
    return output


def best_threshold_rows(rows, ratio_field, thresholds):
    candidates = threshold_rows(rows, ratio_field, thresholds)
    scored = [
        row for row in candidates
        if row["cases"] != 0 and row["improved_rate"] != "" and row["median_log_improvement"] != ""
    ]
    scored.sort(
        key=lambda row: (
            -float(row["improved_rate"]),
            -float(row["median_log_improvement"]),
            float(row["harm_rate"]),
            -int(row["cases"]),
        )
    )
    return scored[:5]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--out-prefix", default="fast_d_scaling_sweep_analysis")
    parser.add_argument("--thresholds", type=float, nargs="*", default=[0.8, 0.9, 1.0, 1.05, 1.1, 1.2, 1.5, 2.0])
    args = parser.parse_args()

    rows = read_rows(args.files)
    summary = summarize_level5(rows)
    thresholds = []
    thresholds.extend(threshold_rows(rows, "ratio_54", args.thresholds))
    thresholds.extend(threshold_rows(rows, "ratio_43", args.thresholds))
    best = []
    best.extend(best_threshold_rows(rows, "ratio_54", args.thresholds))
    best.extend(best_threshold_rows(rows, "ratio_43", args.thresholds))

    write_csv(args.out_prefix + "_summary.csv", summary)
    write_csv(args.out_prefix + "_thresholds.csv", thresholds)
    write_csv(args.out_prefix + "_best_thresholds.csv", best)
    print("Files written:")
    print(args.out_prefix + "_summary.csv")
    print(args.out_prefix + "_thresholds.csv")
    print(args.out_prefix + "_best_thresholds.csv")


if __name__ == "__main__":
    main()
