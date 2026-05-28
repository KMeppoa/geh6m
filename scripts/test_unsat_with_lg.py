#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Run LG modes on formulas that DPLL marked as UNSAT_PROVED.

Purpose:
    Check whether LG ever reports a solution on formulas where DPLL proved UNSAT.
    Expected result: LG should not find a verified SAT assignment.
"""

import argparse
import csv
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_sat_module():
    path = ROOT / "sat_lg_test_v5_fast_parallel_cpu.py"
    spec = importlib.util.spec_from_file_location("sat_lg_v5", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_unsat_seeds(summary_by_formula):
    seeds = []
    with open(summary_by_formula, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["mode"] == "dpll_control" and row.get("status") == "UNSAT_PROVED":
                seeds.append(int(row["formula_seed"]))
    return sorted(seeds)


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="clean_stats_v5_16x40_summary_by_formula.csv")
    parser.add_argument("--vars", type=int, default=16)
    parser.add_argument("--clauses", type=int, default=64)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--depths", default="1,2,3,4")
    parser.add_argument("--branch-caps", default="4,6,8")
    parser.add_argument("--out", default="unsat_lg_probe_results.csv")
    args = parser.parse_args()

    sat = load_sat_module()
    seeds = load_unsat_seeds(args.source)
    depths = [int(x.strip()) for x in args.depths.split(",") if x.strip()]
    branch_caps = [int(x.strip()) for x in args.branch_caps.split(",") if x.strip()]

    rows = []
    print(f"UNSAT seeds: {seeds}")
    print(f"Total UNSAT formulas: {len(seeds)}")

    for seed in seeds:
        formula = sat.generate_random_k_sat(args.vars, args.clauses, args.k, seed)
        dpll = sat.dpll_control(formula, args.vars, seed, max_nodes=200000)

        for branch_cap in branch_caps:
            for depth in depths:
                result = sat.search_sat(
                    formula,
                    args.vars,
                    seed,
                    mode=f"probe_LG_{depth}_cap_{branch_cap}",
                    score_kind="LG",
                    lookahead_depth=depth,
                    max_steps=args.max_steps,
                    branch_cap=branch_cap,
                )
                verified = sat.is_formula_satisfied(formula, result.assignment, args.vars)
                rows.append({
                    "formula_seed": seed,
                    "dpll_status": dpll.status,
                    "depth": depth,
                    "branch_cap": branch_cap,
                    "lg_status": result.status,
                    "lg_success": result.success,
                    "direct_verified": verified,
                    "decision_steps": result.metrics.get("decision_steps", ""),
                    "forced_steps": result.metrics.get("forced_steps", ""),
                    "score_calls": result.metrics.get("score_calls", ""),
                })

    write_csv(ROOT / args.out, rows)

    false_hits = [
        row for row in rows
        if row["lg_success"] or row["direct_verified"]
    ]
    print(f"Rows written: {len(rows)}")
    print(f"LG found/verified solutions on DPLL-UNSAT formulas: {len(false_hits)}")
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
