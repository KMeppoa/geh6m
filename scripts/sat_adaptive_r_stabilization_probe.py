#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Adaptive-R stabilization probe for recursive SAT clusters.

Baseline:
    choose cluster by useful_IG = IG * (1 - danger_rate).

Adaptive-R:
    target_IG = average IG from previous levels.
    if current best IG < target_IG:
        choose only among the safest clusters by danger_rate.

Question:
    does stricter reliability filtering stabilize useful_IG at high levels?
"""

import argparse
import csv
import random
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat
from sat_recursive_cluster_levels import build_next_level
from sat_recursive_risk_probe import clause_vars, risk_metrics


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def polarity_assignment(formula):
    pos = {}
    neg = {}
    for clause in formula:
        for lit in clause:
            var = abs(lit)
            pos.setdefault(var, 0)
            neg.setdefault(var, 0)
            if lit > 0:
                pos[var] += 1
            else:
                neg[var] += 1
    return {var: pos.get(var, 0) >= neg.get(var, 0) for var in pos.keys() | neg.keys()}


def evaluate_unit(formula, n_vars, unit, polarity):
    assignment = {var: polarity.get(var, True) for var in unit}
    risk = risk_metrics(formula, unit, assignment)
    conflict, propagated, forced = sat.unit_propagate(formula, assignment, n_vars)
    ig = n_vars - len(sat.unassigned_vars(n_vars, propagated))
    useful_ig = 0.0 if conflict else ig * risk["stability"]
    return {
        "IG": ig,
        "forced": forced,
        "useful_IG": useful_ig,
        "conflict": conflict,
        **risk,
    }


def choose_candidate(evaluated, mode, previous_igs, risk_quantile):
    # Baseline: direct useful_IG.
    baseline = max(
        evaluated,
        key=lambda item: (item["useful_IG"], item["IG"], -item["danger_rate"], item["unit_size"]),
    )
    if mode == "baseline" or not previous_igs:
        return baseline, False, sum(previous_igs) / len(previous_igs) if previous_igs else 0.0

    target_ig = sum(previous_igs) / len(previous_igs)
    if baseline["IG"] >= target_ig:
        return baseline, False, target_ig

    sorted_by_risk = sorted(evaluated, key=lambda item: (item["danger_rate"], -item["useful_IG"]))
    keep = max(1, int(round(len(sorted_by_risk) * risk_quantile)))
    safe_pool = sorted_by_risk[:keep]
    chosen = max(
        safe_pool,
        key=lambda item: (item["useful_IG"], item["IG"], -item["danger_rate"], item["unit_size"]),
    )
    return chosen, True, target_ig


def run_formula(n_vars, n_clauses, args, seed, mode):
    rng = random.Random(seed + (4444 if mode == "adaptive" else 2222))
    formula = sat.generate_random_k_sat(n_vars, n_clauses, 3, seed)
    formula_var_sets = [clause_vars(clause) for clause in formula]
    units = [[v] for v in range(1, n_vars + 1)]
    var_to_unit = {v: v - 1 for v in range(1, n_vars + 1)}
    polarity = polarity_assignment(formula)
    rows = []
    previous_igs = []

    for level in range(1, args.max_levels + 1):
        units, var_to_unit, _ = build_next_level(
            formula_var_sets,
            units,
            var_to_unit,
            args.min_cooccur,
            args.base_max_cluster_size * level,
        )
        candidates = units
        if args.sample_units and len(candidates) > args.sample_units:
            candidates = rng.sample(candidates, args.sample_units)

        evaluated = []
        for unit in candidates:
            metrics = evaluate_unit(formula, n_vars, unit, polarity)
            evaluated.append({
                "unit_size": len(unit),
                **metrics,
            })

        chosen, adaptive_triggered, target_ig = choose_candidate(
            evaluated, mode, previous_igs, args.risk_quantile
        )
        previous_igs.append(chosen["IG"])

        rows.append({
            "seed": seed,
            "mode": mode,
            "n_vars": n_vars,
            "n_clauses": n_clauses,
            "level": level,
            "unit_count": len(units),
            "sampled_units": len(candidates),
            "target_IG": target_ig,
            "adaptive_triggered": adaptive_triggered,
            "chosen_unit_size": chosen["unit_size"],
            "IG": chosen["IG"],
            "forced": chosen["forced"],
            "danger": chosen["pre_danger"],
            "affected": chosen["affected_clauses"],
            "danger_rate": chosen["danger_rate"],
            "stability": chosen["stability"],
            "useful_IG": chosen["useful_IG"],
            "D_pred": n_vars / chosen["useful_IG"] if chosen["useful_IG"] > 0 else "",
            "conflict": chosen["conflict"],
        })
    return rows


def summarize(rows):
    summary = []
    for mode in sorted({row["mode"] for row in rows}):
        mode_rows = [row for row in rows if row["mode"] == mode]
        for n_vars in sorted({row["n_vars"] for row in mode_rows}):
            n_rows = [row for row in mode_rows if row["n_vars"] == n_vars]
            for level in sorted({row["level"] for row in n_rows}):
                items = [row for row in n_rows if row["level"] == level]
                out = {"mode": mode, "n_vars": n_vars, "level": level, "samples": len(items)}
                for key in [
                    "target_IG",
                    "chosen_unit_size",
                    "IG",
                    "forced",
                    "danger_rate",
                    "stability",
                    "useful_IG",
                ]:
                    out[f"avg_{key}"] = sum(row[key] for row in items) / len(items)
                out["D_pred"] = n_vars / out["avg_useful_IG"] if out["avg_useful_IG"] > 0 else ""
                out["adaptive_triggered_count"] = sum(1 for row in items if row["adaptive_triggered"])
                out["conflicts"] = sum(1 for row in items if row["conflict"])
                summary.append(out)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[1000, 2000])
    parser.add_argument("--formulas", type=int, default=3)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--max-levels", type=int, default=5)
    parser.add_argument("--min-cooccur", type=int, default=2)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--sample-units", type=int, default=500)
    parser.add_argument("--risk-quantile", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_adaptive_r_stabilization_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT ADAPTIVE R STABILIZATION PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows.extend(run_formula(n_vars, n_clauses, args, seed, "baseline"))
            rows.extend(run_formula(n_vars, n_clauses, args, seed, "adaptive"))
        print("  done")

    summary = summarize(rows)
    write_csv(Path(args.out_prefix + "_details.csv"), rows)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary)

    print("\n=== SUMMARY ===")
    for row in summary:
        if row["level"] in (4, 5):
            print(
                f"{row['mode']} n={row['n_vars']} level={row['level']} "
                f"IG={row['avg_IG']:.2f} usefulIG={row['avg_useful_IG']:.2f} "
                f"D={row['D_pred'] if row['D_pred'] == '' else round(row['D_pred'], 2)} "
                f"triggered={row['adaptive_triggered_count']}"
            )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
