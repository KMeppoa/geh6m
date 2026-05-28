#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lightweight SAT H/IG probe without full solving.

Goal:
    Estimate whether unit propagation information gain grows with n.

This does not prove SAT/UNSAT and does not try to fully solve the formula.
It only measures:
    H_start = n_vars
    IG_step = forced assignments created by G after a greedy action
    D_pred = H_start / avg_IG
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


def choose_greedy_lg_action(formula, assignment, n_vars, rng, sample_actions):
    actions = sat.possible_actions(n_vars, assignment)
    if not actions:
        return None, None
    if sample_actions and len(actions) > sample_actions:
        actions = rng.sample(actions, sample_actions)
    ranked = []
    for action in actions:
        new_assignment = dict(assignment)
        var, value = action
        new_assignment[var] = value
        score = sat.score_LG(formula, new_assignment, n_vars)
        ranked.append((score, action))
    ranked.sort(key=lambda item: (item[0], item[1][0], item[1][1]))
    return ranked[0]


def probe_formula(n_vars, n_clauses, k, seed, steps, sample_actions):
    rng = random.Random(seed + 99991)
    formula = sat.generate_random_k_sat(n_vars, n_clauses, k, seed)
    assignment = {}
    rows = []
    conflict = False

    for step in range(1, steps + 1):
        h_before = len(sat.unassigned_vars(n_vars, assignment))
        if h_before <= 0:
            break

        score_action = choose_greedy_lg_action(
            formula, assignment, n_vars, rng, sample_actions
        )
        if score_action[1] is None:
            break

        _, action = score_action
        var, value = action
        after_action = dict(assignment)
        after_action[var] = value

        conflict, propagated, forced_count = sat.unit_propagate(
            formula, after_action, n_vars
        )
        h_after = len(sat.unassigned_vars(n_vars, propagated))
        ig_total = h_before - h_after
        ig_g_only = max(0, ig_total - 1)

        rows.append({
            "seed": seed,
            "step": step,
            "n_vars": n_vars,
            "n_clauses": n_clauses,
            "ratio": n_clauses / n_vars,
            "H_before": h_before,
            "H_after": h_after,
            "IG_total": ig_total,
            "IG_G_only": ig_g_only,
            "forced_count": forced_count,
            "conflict": conflict,
            "assigned_after": len(propagated),
            "sample_actions": sample_actions,
        })

        if conflict:
            break
        assignment = propagated

    return rows


def summarize(detail_rows):
    groups = {}
    for row in detail_rows:
        groups.setdefault(row["n_vars"], []).append(row)
    summary = []
    for n_vars, rows in sorted(groups.items()):
        non_conflict = [row for row in rows if not row["conflict"]]
        use_rows = non_conflict or rows
        avg_ig_total = sum(row["IG_total"] for row in use_rows) / len(use_rows)
        avg_ig_g = sum(row["IG_G_only"] for row in use_rows) / len(use_rows)
        avg_h_before = sum(row["H_before"] for row in use_rows) / len(use_rows)
        d_pred_total = n_vars / avg_ig_total if avg_ig_total > 0 else ""
        d_pred_g = n_vars / avg_ig_g if avg_ig_g > 0 else ""
        summary.append({
            "n_vars": n_vars,
            "samples": len(rows),
            "non_conflict_samples": len(non_conflict),
            "H_start": n_vars,
            "avg_H_before": avg_h_before,
            "avg_IG_total": avg_ig_total,
            "avg_IG_G_only": avg_ig_g,
            "D_pred_total": d_pred_total,
            "D_pred_G_only": d_pred_g,
            "conflicts": sum(1 for row in rows if row["conflict"]),
        })
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[22, 50, 100])
    parser.add_argument("--formulas", type=int, default=5)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--sample-actions", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_hig_probe_step1")
    args = parser.parse_args()

    detail_rows = []
    print("=== SAT H/IG PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows = probe_formula(
                n_vars, n_clauses, args.k, seed, args.steps, args.sample_actions
            )
            detail_rows.extend(rows)
        print("  done")

    summary_rows = summarize(detail_rows)
    write_csv(Path(args.out_prefix + "_details.csv"), detail_rows)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary_rows)

    print("\n=== SUMMARY ===")
    for row in summary_rows:
        print(
            f"n={row['n_vars']} avg_IG_total={row['avg_IG_total']:.2f} "
            f"avg_IG_G_only={row['avg_IG_G_only']:.2f} "
            f"D_pred_total={row['D_pred_total'] if row['D_pred_total'] == '' else round(row['D_pred_total'], 2)} "
            f"D_pred_G_only={row['D_pred_G_only'] if row['D_pred_G_only'] == '' else round(row['D_pred_G_only'], 2)} "
            f"conflicts={row['conflicts']}"
        )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
