#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Run SAT phase-transition guided-depth tests for several sizes.

For each variable count n:
    clauses = round(4.27 * n)
    run sat_lg_test_v5_fast_parallel_cpu.py
    compute first LG depth that solves all DPLL-SAT formulas.
"""

import argparse
import csv
import json
import subprocess
import sys
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


def analyze(prefix, depths):
    rows = read_rows(f"{prefix}_summary_by_formula.csv")
    sat_seeds = {
        row["formula_seed"]
        for row in rows
        if row["mode"] == "dpll_control" and row["status"] == "SAT_FOUND"
    }
    unsat_count = sum(
        1 for row in rows
        if row["mode"] == "dpll_control" and row["status"] == "UNSAT_PROVED"
    )

    by_depth = []
    first = None
    for depth in depths:
        mode = f"lookahead_LG_{depth}"
        mode_rows = [
            row for row in rows
            if row["formula_seed"] in sat_seeds and row["mode"] == mode
        ]
        success = sum(1 for row in mode_rows if row["status"] == "SAT_FOUND")
        total = len(sat_seeds)
        rate = success / total if total else 0
        avg_decision = (
            sum(float(row["decision_steps"]) for row in mode_rows) / len(mode_rows)
            if mode_rows else 0
        )
        avg_forced = (
            sum(float(row["forced_steps"]) for row in mode_rows) / len(mode_rows)
            if mode_rows else 0
        )
        avg_score = (
            sum(float(row["score_calls"]) for row in mode_rows) / len(mode_rows)
            if mode_rows else 0
        )
        if total and success == total and first is None:
            first = depth
        by_depth.append({
            "depth": depth,
            "success": success,
            "sat_total": total,
            "success_rate": rate,
            "avg_decision_steps": avg_decision,
            "avg_forced_steps": avg_forced,
            "avg_score_calls": avg_score,
        })
    return by_depth, first, len(sat_seeds), unsat_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[12, 14, 16])
    parser.add_argument("--formulas", type=int, default=10)
    parser.add_argument("--depths", type=int, nargs="*", default=[1, 2, 3])
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--max-steps-factor", type=int, default=5)
    parser.add_argument("--max-dpll-nodes", type=int, default=120000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="experiments/guided_depth_growth_sat_phase_step1")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")

    summary_rows = []
    first_rows = []

    print("=== GUIDED DEPTH GROWTH: SAT PHASE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    depths_arg = ",".join(str(d) for d in args.depths)
    script = Path(__file__).with_name("sat_lg_test_v5_fast_parallel_cpu.py")

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        prefix_path = out_dir / f"sat_phase_n{n_vars}"
        print(f"n_vars={n_vars}, clauses={n_clauses}")
        cmd = [
            sys.executable,
            str(script),
            "--formulas", str(args.formulas),
            "--vars", str(n_vars),
            "--clauses", str(n_clauses),
            "--k", "3",
            "--max-steps", str(n_vars * args.max_steps_factor),
            "--max-dpll-nodes", str(args.max_dpll_nodes),
            "--lookaheads", depths_arg,
            "--branch-cap", str(args.branch_cap),
            "--workers", "1",
            "--profile", "full",
            "--seed", str(args.seed),
            "--out-prefix", str(prefix_path),
        ]
        subprocess.run(cmd, check=True)

        by_depth, first, sat_total, unsat_count = analyze(str(prefix_path), args.depths)
        for row in by_depth:
            summary_rows.append({
                "n_vars": n_vars,
                "clauses": n_clauses,
                "ratio": n_clauses / n_vars,
                "formulas": args.formulas,
                "dpll_sat": sat_total,
                "dpll_unsat": unsat_count,
                **row,
            })
            print(
                f"  guided_{row['depth']}: "
                f"{row['success']}/{row['sat_total']} "
                f"avg_decision={row['avg_decision_steps']:.2f} "
                f"avg_forced={row['avg_forced_steps']:.2f}"
            )
        first_rows.append({
            "n_vars": n_vars,
            "clauses": n_clauses,
            "ratio": n_clauses / n_vars,
            "dpll_sat": sat_total,
            "dpll_unsat": unsat_count,
            "first_depth_100": first if first is not None else "",
        })
        print(f"  first_depth_100={first}")
        print()

    write_csv(out_dir / "summary_by_depth.csv", summary_rows)
    write_csv(out_dir / "summary_first_depth_100.csv", first_rows)
    print("=== FILES WRITTEN ===")
    print(out_dir / "config.json")
    print(out_dir / "summary_by_depth.csv")
    print(out_dir / "summary_first_depth_100.csv")


if __name__ == "__main__":
    main()
