#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Search for formulas where limited DPLL times out but LG finds a verified SAT assignment.
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


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--formulas", type=int, default=30)
    parser.add_argument("--vars", type=int, default=20)
    parser.add_argument("--clauses", type=int, default=80)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--limited-dpll-nodes", type=int, default=5)
    parser.add_argument("--full-dpll-nodes", type=int, default=200000)
    parser.add_argument("--lg-depth", type=int, default=3)
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--out", default="lg_beats_limited_dpll.csv")
    args = parser.parse_args()

    sat = load_sat_module()
    rows = []

    for i in range(args.formulas):
        formula_seed = args.seed + i
        formula = sat.generate_random_k_sat(args.vars, args.clauses, args.k, formula_seed)

        limited = sat.dpll_control(
            formula,
            args.vars,
            formula_seed,
            max_nodes=args.limited_dpll_nodes,
        )
        lg = sat.search_sat(
            formula,
            args.vars,
            formula_seed,
            mode=f"lookahead_LG_{args.lg_depth}",
            score_kind="LG",
            lookahead_depth=args.lg_depth,
            max_steps=args.max_steps,
            branch_cap=args.branch_cap,
        )
        verified = sat.is_formula_satisfied(formula, lg.assignment, args.vars)

        full_status = ""
        full_success = ""
        if limited.status == "TIMEOUT" and lg.success and verified:
            full = sat.dpll_control(
                formula,
                args.vars,
                formula_seed,
                max_nodes=args.full_dpll_nodes,
            )
            full_status = full.status
            full_success = full.success

        rows.append({
            "formula_seed": formula_seed,
            "limited_dpll_status": limited.status,
            "limited_dpll_steps": limited.steps,
            "lg_status": lg.status,
            "lg_success": lg.success,
            "lg_direct_verified": verified,
            "lg_decision_steps": lg.metrics.get("decision_steps", ""),
            "lg_forced_steps": lg.metrics.get("forced_steps", ""),
            "lg_score_calls": lg.metrics.get("score_calls", ""),
            "full_dpll_status_if_candidate": full_status,
            "full_dpll_success_if_candidate": full_success,
        })

    write_csv(ROOT / args.out, rows)

    candidates = [
        r for r in rows
        if r["limited_dpll_status"] == "TIMEOUT"
        and r["lg_success"]
        and r["lg_direct_verified"]
    ]
    print(f"Rows written: {len(rows)}")
    print(f"Candidates limited-DPLL TIMEOUT + LG SAT_FOUND: {len(candidates)}")
    for row in candidates[:10]:
        print(row)
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
