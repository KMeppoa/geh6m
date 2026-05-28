#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Statistical analysis for L/G SAT experiment CSV files.

Input: *_summary_by_formula.csv from sat_lg_test_v5_fast_parallel_cpu.py
Output: compact CSV + readable console report.
"""

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


def parse_bool(value):
    return str(value).strip().lower() == "true"


def wilson_interval(success, total, z=1.96):
    if total == 0:
        return 0.0, 0.0
    p = success / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return max(0.0, center - half), min(1.0, center + half)


def exact_two_sided_binomial_p(k, n, p=0.5):
    if n == 0:
        return 1.0
    observed = math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))
    total = 0.0
    for i in range(n + 1):
        prob = math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
        if prob <= observed + 1e-15:
            total += prob
    return min(1.0, total)


def load_rows(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["success_bool"] = parse_bool(row["success"])
            row["decision_steps_num"] = float(row.get("decision_steps") or 0)
            row["forced_steps_num"] = float(row.get("forced_steps") or 0)
            row["score_calls_num"] = float(row.get("score_calls") or 0)
            rows.append(row)
    return rows


def mode_summary(rows, seeds):
    by_mode = defaultdict(list)
    for row in rows:
        by_mode[row["mode"]].append(row)

    result = []
    for mode in sorted(by_mode):
        items = by_mode[mode]
        total = len(items)
        success = sum(1 for r in items if r["success_bool"])
        lo, hi = wilson_interval(success, total)
        non_skipped = [r for r in items if r.get("status") != "SKIPPED"]
        denom = len(non_skipped) or 1
        result.append({
            "mode": mode,
            "total": total,
            "success": success,
            "success_rate": success / total if total else 0,
            "ci95_low": lo,
            "ci95_high": hi,
            "skipped": sum(1 for r in items if r.get("status") == "SKIPPED"),
            "avg_decision_steps": sum(r["decision_steps_num"] for r in non_skipped) / denom,
            "avg_forced_steps": sum(r["forced_steps_num"] for r in non_skipped) / denom,
            "avg_score_calls": sum(r["score_calls_num"] for r in non_skipped) / denom,
        })
    return result


def paired_summary(rows, mode_a, mode_b, dpll_mode="dpll_control"):
    idx = {(r["formula_seed"], r["mode"]): r for r in rows}
    seeds = sorted({r["formula_seed"] for r in rows})
    dpll_sat = [
        seed for seed in seeds
        if (seed, dpll_mode) in idx and idx[(seed, dpll_mode)].get("status") == "SAT_FOUND"
    ]

    a_only = 0
    b_only = 0
    both = 0
    neither = 0
    compared = 0

    for seed in dpll_sat:
        if (seed, mode_a) not in idx or (seed, mode_b) not in idx:
            continue
        a = idx[(seed, mode_a)]["success_bool"]
        b = idx[(seed, mode_b)]["success_bool"]
        compared += 1
        if a and b:
            both += 1
        elif a and not b:
            a_only += 1
        elif b and not a:
            b_only += 1
        else:
            neither += 1

    discordant = a_only + b_only
    p_value = exact_two_sided_binomial_p(min(a_only, b_only), discordant) if discordant else 1.0

    return {
        "mode_a": mode_a,
        "mode_b": mode_b,
        "dpll_sat_total": len(dpll_sat),
        "compared": compared,
        "a_only": a_only,
        "b_only": b_only,
        "both": both,
        "neither": neither,
        "net_gain_b_over_a": b_only - a_only,
        "exact_p_value": p_value,
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
    parser.add_argument("summary_by_formula")
    parser.add_argument("--out-prefix", default="")
    args = parser.parse_args()

    path = Path(args.summary_by_formula)
    rows = load_rows(path)
    seeds = sorted({r["formula_seed"] for r in rows})
    prefix = args.out_prefix or path.with_suffix("").as_posix() + "_stats"

    summaries = mode_summary(rows, seeds)
    pairs = [
        paired_summary(rows, "greedy_L", "greedy_LG"),
        paired_summary(rows, "lookahead_L_3", "lookahead_LG_3"),
    ]

    write_csv(Path(prefix + "_by_mode.csv"), summaries)
    write_csv(Path(prefix + "_paired.csv"), pairs)

    print("=== MODE SUMMARY ===")
    for row in summaries:
        print(
            f"{row['mode']}: {row['success']}/{row['total']} = "
            f"{row['success_rate']:.3f}, CI95=[{row['ci95_low']:.3f}, {row['ci95_high']:.3f}], "
            f"avg_decision={row['avg_decision_steps']:.2f}, "
            f"avg_forced={row['avg_forced_steps']:.2f}, skipped={row['skipped']}"
        )

    print()
    print("=== PAIRED L VS LG ON DPLL-SAT FORMULAS ===")
    for row in pairs:
        print(
            f"{row['mode_a']} vs {row['mode_b']}: compared={row['compared']}, "
            f"LG_only={row['b_only']}, L_only={row['a_only']}, "
            f"net={row['net_gain_b_over_a']}, p={row['exact_p_value']:.6g}"
        )

    print()
    print("Files written:")
    print(prefix + "_by_mode.csv")
    print(prefix + "_paired.csv")


if __name__ == "__main__":
    main()
