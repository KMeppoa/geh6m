#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reliability R for recursive SAT cluster levels.

We use planted SAT so the hidden correct assignment is known.

R at a level:
    cluster_choice_reliable = all variables assigned by the chosen unit match
                              the planted solution.
    propagated_reliable     = all variables assigned after unit propagation
                              still match the planted solution.

This measures whether scale-compression is useful or brittle.
"""

import argparse
import csv
import random
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat
from sat_recursive_cluster_levels import build_next_level, write_csv


def generate_planted_k_sat(n_vars, n_clauses, k, seed):
    rng = random.Random(seed)
    planted = {var: rng.choice([False, True]) for var in range(1, n_vars + 1)}
    formula = []
    while len(formula) < n_clauses:
        vars_ = rng.sample(range(1, n_vars + 1), k)
        clause = []
        satisfied = False
        for var in vars_:
            sign = rng.choice([False, True])
            lit = var if sign else -var
            clause.append(lit)
            if (lit > 0 and planted[var]) or (lit < 0 and not planted[var]):
                satisfied = True
        if satisfied:
            formula.append(clause)
    return formula, planted


def clause_vars(clause):
    return sorted(set(abs(lit) for lit in clause))


def polarity_assignment(formula):
    pos = {var: 0 for clause in formula for var in clause_vars(clause)}
    neg = dict(pos)
    for clause in formula:
        for lit in clause:
            if lit > 0:
                pos[lit] = pos.get(lit, 0) + 1
            else:
                neg[-lit] = neg.get(-lit, 0) + 1
    return {var: pos.get(var, 0) >= neg.get(var, 0) for var in pos.keys() | neg.keys()}


def assignment_reliability(assignment, planted):
    if not assignment:
        return 1.0, True
    matches = sum(1 for var, value in assignment.items() if planted[var] == value)
    all_match = matches == len(assignment)
    return matches / len(assignment), all_match


def choose_level_unit(formula, units, n_vars, sample_units, rng):
    polarity = polarity_assignment(formula)
    candidates = list(range(len(units)))
    if sample_units and len(candidates) > sample_units:
        candidates = rng.sample(candidates, sample_units)

    ranked = []
    for idx in candidates:
        assignment = {var: polarity.get(var, True) for var in units[idx]}
        conflict, propagated, forced = sat.unit_propagate(formula, assignment, n_vars)
        score = 10_000_000 if conflict else len(sat.unassigned_vars(n_vars, propagated))
        ranked.append((score, -len(units[idx]), idx, assignment, propagated, forced, conflict))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    _, _, idx, assignment, propagated, forced, conflict = ranked[0]
    return idx, assignment, propagated, forced, conflict


def probe_formula(n_vars, n_clauses, args, seed):
    rng = random.Random(seed + 919191)
    formula, planted = generate_planted_k_sat(n_vars, n_clauses, 3, seed)
    formula_var_sets = [clause_vars(clause) for clause in formula]

    units = [[v] for v in range(1, n_vars + 1)]
    var_to_unit = {v: v - 1 for v in range(1, n_vars + 1)}
    rows = []

    for level in range(1, args.max_levels + 1):
        max_weight = args.base_max_cluster_size * level
        units, var_to_unit, _ = build_next_level(
            formula_var_sets,
            units,
            var_to_unit,
            args.min_cooccur,
            max_weight,
        )
        idx, assignment, propagated, forced, conflict = choose_level_unit(
            formula, units, n_vars, args.sample_units, rng
        )
        choice_r, choice_all_match = assignment_reliability(assignment, planted)
        prop_r, prop_all_match = assignment_reliability(propagated, planted)
        ig_total = n_vars - len(sat.unassigned_vars(n_vars, propagated))

        rows.append({
            "seed": seed,
            "n_vars": n_vars,
            "n_clauses": n_clauses,
            "level": level,
            "unit_count": len(units),
            "chosen_unit_size": len(units[idx]),
            "IG_total": ig_total,
            "forced": forced,
            "choice_R_fraction": choice_r,
            "choice_R_all_match": choice_all_match,
            "propagated_R_fraction": prop_r,
            "propagated_R_all_match": prop_all_match,
            "conflict": conflict,
            "D_pred": n_vars / ig_total if ig_total > 0 else "",
        })
    return rows


def summarize(rows):
    summary = []
    for n_vars in sorted({row["n_vars"] for row in rows}):
        n_items = [row for row in rows if row["n_vars"] == n_vars]
        for level in sorted({row["level"] for row in n_items}):
            items = [row for row in n_items if row["level"] == level]
            summary.append({
                "n_vars": n_vars,
                "level": level,
                "samples": len(items),
                "avg_unit_count": sum(row["unit_count"] for row in items) / len(items),
                "avg_chosen_unit_size": sum(row["chosen_unit_size"] for row in items) / len(items),
                "avg_IG_total": sum(row["IG_total"] for row in items) / len(items),
                "avg_forced": sum(row["forced"] for row in items) / len(items),
                "R_choice_success_rate": sum(1 for row in items if row["choice_R_all_match"]) / len(items),
                "R_propagated_success_rate": sum(1 for row in items if row["propagated_R_all_match"]) / len(items),
                "avg_choice_R_fraction": sum(row["choice_R_fraction"] for row in items) / len(items),
                "avg_propagated_R_fraction": sum(row["propagated_R_fraction"] for row in items) / len(items),
                "conflicts": sum(1 for row in items if row["conflict"]),
                "avg_D_pred": sum(float(row["D_pred"]) for row in items if row["D_pred"] != "") / len(items),
            })
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[100, 200, 500, 1000])
    parser.add_argument("--formulas", type=int, default=3)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--min-cooccur", type=int, default=2)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--max-levels", type=int, default=5)
    parser.add_argument("--sample-units", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_recursive_cluster_reliability_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT RECURSIVE CLUSTER RELIABILITY ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows.extend(probe_formula(n_vars, n_clauses, args, seed))
        print("  done")

    summary = summarize(rows)
    write_csv(Path(args.out_prefix + "_details.csv"), rows)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary)

    print("\n=== SUMMARY ===")
    for row in summary:
        if row["level"] in (1, args.max_levels):
            print(
                f"n={row['n_vars']} level={row['level']} "
                f"IG={row['avg_IG_total']:.2f} "
                f"D={row['avg_D_pred']:.2f} "
                f"R_choice={row['R_choice_success_rate']:.2f} "
                f"R_prop={row['R_propagated_success_rate']:.2f}"
            )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
