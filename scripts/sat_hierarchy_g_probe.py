#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hierarchical G probe for SAT.

G1:
    unit propagation.

G2:
    failed-literal probing using G1:
        try x=True + G1
        try x=False + G1
        if one side conflicts, force the other side and run G1.

G3:
    another round of the same G2 process after newly forced assignments.

This is a rigorous first version of "G on top of G" because higher levels use
G1 as a subroutine to reveal more forced consequences.
"""

import argparse
import csv
import random
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def g1(formula, assignment, n_vars):
    return sat.unit_propagate(formula, assignment, n_vars)


def g2_round(formula, assignment, n_vars, rng, probe_vars):
    assignment = dict(assignment)
    unassigned = sat.unassigned_vars(n_vars, assignment)
    if probe_vars and len(unassigned) > probe_vars:
        candidates = rng.sample(unassigned, probe_vars)
    else:
        candidates = unassigned

    forced_by_probe = 0
    probe_conflicts = 0

    for var in candidates:
        if var in assignment:
            continue

        asg_true = dict(assignment)
        asg_true[var] = True
        conflict_true, _, _ = g1(formula, asg_true, n_vars)

        asg_false = dict(assignment)
        asg_false[var] = False
        conflict_false, _, _ = g1(formula, asg_false, n_vars)

        if conflict_true and conflict_false:
            probe_conflicts += 2
            return True, assignment, forced_by_probe, probe_conflicts

        if conflict_true and not conflict_false:
            assignment[var] = False
            forced_by_probe += 1
            probe_conflicts += 1
            conflict, assignment, _ = g1(formula, assignment, n_vars)
            if conflict:
                return True, assignment, forced_by_probe, probe_conflicts

        elif conflict_false and not conflict_true:
            assignment[var] = True
            forced_by_probe += 1
            probe_conflicts += 1
            conflict, assignment, _ = g1(formula, assignment, n_vars)
            if conflict:
                return True, assignment, forced_by_probe, probe_conflicts

    return False, assignment, forced_by_probe, probe_conflicts


def choose_sampled_greedy_action(formula, assignment, n_vars, rng, sample_actions):
    actions = sat.possible_actions(n_vars, assignment)
    if sample_actions and len(actions) > sample_actions:
        actions = rng.sample(actions, sample_actions)
    ranked = []
    for var, value in actions:
        trial = dict(assignment)
        trial[var] = value
        score = sat.score_LG(formula, trial, n_vars)
        ranked.append((score, var, value))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    _, var, value = ranked[0]
    return var, value


def probe_formula(n_vars, n_clauses, k, seed, sample_actions, probe_vars):
    rng = random.Random(seed + 1234567)
    formula = sat.generate_random_k_sat(n_vars, n_clauses, k, seed)

    h_start = n_vars
    assignment = {}

    var, value = choose_sampled_greedy_action(
        formula, assignment, n_vars, rng, sample_actions
    )
    assignment[var] = value
    h_after_action = len(sat.unassigned_vars(n_vars, assignment))

    conflict1, after_g1, forced_g1 = g1(formula, assignment, n_vars)
    h_after_g1 = len(sat.unassigned_vars(n_vars, after_g1))

    if conflict1:
        return {
            "seed": seed,
            "n_vars": n_vars,
            "n_clauses": n_clauses,
            "H_start": h_start,
            "H_after_action": h_after_action,
            "H_after_G1": h_after_g1,
            "H_after_G2": h_after_g1,
            "H_after_G3": h_after_g1,
            "IG_action": h_start - h_after_action,
            "IG_G1_only": h_after_action - h_after_g1,
            "IG_G2_only": 0,
            "IG_G3_only": 0,
            "IG_total_G1": h_start - h_after_g1,
            "IG_total_G2": h_start - h_after_g1,
            "IG_total_G3": h_start - h_after_g1,
            "forced_g1": forced_g1,
            "forced_g2_probe": 0,
            "forced_g3_probe": 0,
            "probe_conflicts_g2": 0,
            "probe_conflicts_g3": 0,
            "conflict": True,
        }

    conflict2, after_g2, forced_g2, probe_conflicts_g2 = g2_round(
        formula, after_g1, n_vars, rng, probe_vars
    )
    h_after_g2 = len(sat.unassigned_vars(n_vars, after_g2))

    if conflict2:
        h_after_g3 = h_after_g2
        forced_g3 = 0
        probe_conflicts_g3 = 0
    else:
        conflict3, after_g3, forced_g3, probe_conflicts_g3 = g2_round(
            formula, after_g2, n_vars, rng, probe_vars
        )
        h_after_g3 = len(sat.unassigned_vars(n_vars, after_g3))

    return {
        "seed": seed,
        "n_vars": n_vars,
        "n_clauses": n_clauses,
        "H_start": h_start,
        "H_after_action": h_after_action,
        "H_after_G1": h_after_g1,
        "H_after_G2": h_after_g2,
        "H_after_G3": h_after_g3,
        "IG_action": h_start - h_after_action,
        "IG_G1_only": h_after_action - h_after_g1,
        "IG_G2_only": h_after_g1 - h_after_g2,
        "IG_G3_only": h_after_g2 - h_after_g3,
        "IG_total_G1": h_start - h_after_g1,
        "IG_total_G2": h_start - h_after_g2,
        "IG_total_G3": h_start - h_after_g3,
        "forced_g1": forced_g1,
        "forced_g2_probe": forced_g2,
        "forced_g3_probe": forced_g3,
        "probe_conflicts_g2": probe_conflicts_g2,
        "probe_conflicts_g3": probe_conflicts_g3,
        "conflict": conflict2,
    }


def summarize(rows):
    summary = []
    for n_vars in sorted({row["n_vars"] for row in rows}):
        items = [row for row in rows if row["n_vars"] == n_vars]
        out = {
            "n_vars": n_vars,
            "samples": len(items),
            "H_start": n_vars,
            "conflicts": sum(1 for row in items if row["conflict"]),
        }
        for key in [
            "IG_G1_only",
            "IG_G2_only",
            "IG_G3_only",
            "IG_total_G1",
            "IG_total_G2",
            "IG_total_G3",
            "forced_g2_probe",
            "forced_g3_probe",
            "probe_conflicts_g2",
            "probe_conflicts_g3",
        ]:
            out[f"avg_{key}"] = sum(row[key] for row in items) / len(items)
        for level in [1, 2, 3]:
            ig = out[f"avg_IG_total_G{level}"]
            out[f"D_pred_G{level}"] = n_vars / ig if ig > 0 else ""
        summary.append(out)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[22, 50, 100, 200])
    parser.add_argument("--formulas", type=int, default=3)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--sample-actions", type=int, default=200)
    parser.add_argument("--probe-vars", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_hierarchy_g_probe_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT HIERARCHICAL G PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows.append(
                probe_formula(
                    n_vars,
                    n_clauses,
                    args.k,
                    seed,
                    args.sample_actions,
                    args.probe_vars,
                )
            )
        print("  done")

    summary = summarize(rows)
    write_csv(Path(args.out_prefix + "_details.csv"), rows)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary)

    print("\n=== SUMMARY ===")
    for row in summary:
        print(
            f"n={row['n_vars']} "
            f"IG1={row['avg_IG_total_G1']:.2f} "
            f"IG2={row['avg_IG_total_G2']:.2f} "
            f"IG3={row['avg_IG_total_G3']:.2f} "
            f"D1={row['D_pred_G1'] if row['D_pred_G1'] == '' else round(row['D_pred_G1'], 2)} "
            f"D2={row['D_pred_G2'] if row['D_pred_G2'] == '' else round(row['D_pred_G2'], 2)} "
            f"D3={row['D_pred_G3'] if row['D_pred_G3'] == '' else round(row['D_pred_G3'], 2)}"
        )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
