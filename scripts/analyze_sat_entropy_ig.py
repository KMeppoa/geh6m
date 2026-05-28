#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Prototype entropy / information-gain analysis for SAT guided-depth runs.

For SAT:
    H_start = n_vars = log2(2^n_vars)
    IG_total ~= forced_steps from LG/unit propagation

This is a first coarse check:
    D_real = first guided depth that solves all DPLL-SAT formulas
    D_pred = H_start / avg_IG_total

Important:
    This prototype uses run-level forced_steps as IG. A later version should
    log H_before/H_after at each step inside the solver.
"""

import argparse
import csv
import math
import re
from pathlib import Path


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_n_vars(path):
    match = re.search(r"n(\d+)", path.name)
    if match:
        return int(match.group(1))
    match = re.search(r"v(\d+)", path.name)
    if match:
        return int(match.group(1))
    return None


def analyze_file(path, depths):
    rows = read_rows(path)
    n_vars = parse_n_vars(path)
    if n_vars is None:
        # Fallback: assigned_count is full variable count for DPLL SAT rows.
        for row in rows:
            if row.get("mode") == "dpll_control" and row.get("status") == "SAT_FOUND":
                n_vars = int(float(row.get("assigned_count", 0)))
                break
    if n_vars is None:
        raise ValueError(f"Cannot infer n_vars from {path}")

    sat_seeds = {
        row["formula_seed"]
        for row in rows
        if row["mode"] == "dpll_control" and row["status"] == "SAT_FOUND"
    }
    unsat_count = sum(
        1 for row in rows
        if row["mode"] == "dpll_control" and row["status"] == "UNSAT_PROVED"
    )

    depth_rows = []
    first_depth = None
    for depth in depths:
        mode = f"lookahead_LG_{depth}"
        mode_rows = [
            row for row in rows
            if row["formula_seed"] in sat_seeds and row["mode"] == mode
        ]
        successes = [row for row in mode_rows if row["status"] == "SAT_FOUND"]
        success_count = len(successes)
        sat_total = len(sat_seeds)
        if sat_total and success_count == sat_total and first_depth is None:
            first_depth = depth

        avg_ig_all = (
            sum(float(row["forced_steps"]) for row in mode_rows) / len(mode_rows)
            if mode_rows else 0.0
        )
        avg_ig_success = (
            sum(float(row["forced_steps"]) for row in successes) / len(successes)
            if successes else 0.0
        )
        avg_decision_success = (
            sum(float(row["decision_steps"]) for row in successes) / len(successes)
            if successes else 0.0
        )
        h_after_success = max(0.0, n_vars - avg_ig_success)
        d_pred = n_vars / avg_ig_success if avg_ig_success > 0 else ""
        d_pred_ceil = math.ceil(d_pred) if d_pred != "" else ""

        depth_rows.append({
            "source_file": str(path),
            "n_vars": n_vars,
            "H_start": n_vars,
            "depth": depth,
            "dpll_sat": sat_total,
            "dpll_unsat": unsat_count,
            "success": success_count,
            "success_rate": success_count / sat_total if sat_total else 0.0,
            "avg_IG_all": avg_ig_all,
            "avg_IG_success": avg_ig_success,
            "H_after_success": h_after_success,
            "avg_decision_success": avg_decision_success,
            "D_pred_H_over_IG": d_pred,
            "D_pred_ceil": d_pred_ceil,
        })

    return depth_rows, {
        "source_file": str(path),
        "n_vars": n_vars,
        "H_start": n_vars,
        "dpll_sat": len(sat_seeds),
        "dpll_unsat": unsat_count,
        "D_real_first_depth_100": first_depth if first_depth is not None else "",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="*", default=[
        "experiments/guided_depth_growth_sat_phase_step1/sat_phase_n12_summary_by_formula.csv",
        "experiments/guided_depth_growth_sat_phase_step1/sat_phase_n14_summary_by_formula.csv",
        "experiments/guided_depth_growth_sat_phase_step1/sat_phase_n16_summary_by_formula.csv",
    ])
    parser.add_argument("--depths", type=int, nargs="*", default=[1, 2, 3])
    parser.add_argument("--out-prefix", default="sat_entropy_ig_step1")
    args = parser.parse_args()

    detail_rows = []
    first_rows = []
    for input_path in args.inputs:
        path = Path(input_path)
        rows, first = analyze_file(path, args.depths)
        detail_rows.extend(rows)
        first_rows.append(first)

    write_csv(Path(args.out_prefix + "_by_depth.csv"), detail_rows)
    write_csv(Path(args.out_prefix + "_first_depth.csv"), first_rows)

    print("=== SAT ENTROPY / IG ANALYSIS ===")
    for first in first_rows:
        print(
            f"n={first['n_vars']} H={first['H_start']} "
            f"D_real={first['D_real_first_depth_100']} "
            f"SAT={first['dpll_sat']} UNSAT={first['dpll_unsat']}"
        )
        rows = [row for row in detail_rows if row["n_vars"] == first["n_vars"]]
        for row in rows:
            print(
                f"  depth={row['depth']} success={row['success']}/{row['dpll_sat']} "
                f"avg_IG_success={row['avg_IG_success']:.2f} "
                f"D_pred={row['D_pred_H_over_IG'] if row['D_pred_H_over_IG'] == '' else round(row['D_pred_H_over_IG'], 2)} "
                f"D_pred_ceil={row['D_pred_ceil']}"
            )
    print("Files written:")
    print(args.out_prefix + "_by_depth.csv")
    print(args.out_prefix + "_first_depth.csv")


if __name__ == "__main__":
    main()
