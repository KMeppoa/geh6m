#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Top-down reserve rebuild probe for recursive SAT clusters.

Procedure:
    1. Build levels G1..G5 normally.
    2. If G5 useful IG drops below G4 useful IG, create an importance signal.
    3. Rebuild G4 from saved G3 using the importance signal.
    4. Rebuild G5 from rebuilt G4.

This tests reserve as a navigator for cluster construction, not as recovered
loss accounting.
"""

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat
from sat_recursive_cluster_levels import build_next_level
from sat_reserve_loss_probe import evaluate_unit, polarity_assignment
from sat_recursive_risk_probe import clause_vars


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def candidate_units(units, sample_units, rng, importance):
    if not sample_units or len(units) <= sample_units:
        return units
    scored = [
        (sum(importance.get(var, 0.0) for var in unit), len(unit), idx, unit)
        for idx, unit in enumerate(units)
    ]
    keep_count = max(1, sample_units // 2)
    if importance:
        top = sorted(scored, key=lambda item: (-item[0], -item[1], item[2]))[:keep_count]
    else:
        top = sorted(scored, key=lambda item: (-item[1], item[2]))[:keep_count]
    chosen_indexes = {idx for _, _, idx, _ in top}
    remaining = [unit for _, _, idx, unit in scored if idx not in chosen_indexes]
    random_count = sample_units - len(top)
    if len(remaining) > random_count:
        remaining = rng.sample(remaining, random_count)
    return [unit for _, _, _, unit in top] + remaining


def choose_best(formula, n_vars, units, sample_units, rng, polarity, importance, level):
    candidates = candidate_units(units, sample_units, rng, importance)
    best = None
    for unit in candidates:
        metrics = evaluate_unit(
            formula,
            n_vars,
            unit,
            polarity,
            importance,
            beta=0.5,
            level=level,
            use_reserve=False,
        )
        key = (
            -metrics["base_useful_IG"],
            -metrics["IG"],
            metrics["danger_rate"],
            -sum(importance.get(var, 0.0) for var in unit),
            -len(unit),
        )
        if best is None or key < best[0]:
            best = (key, unit, metrics)
    return best[1], best[2]


def unit_scores_from_importance(units, importance):
    return [sum(importance.get(var, 0.0) for var in unit) for unit in units]


def build_level(formula_var_sets, units, var_to_unit, args, level, importance=None):
    if importance:
        unit_scores = unit_scores_from_importance(units, importance)
        reserve_bias = args.topdown_bias
    else:
        unit_scores = None
        reserve_bias = 0.0
    return build_next_level(
        formula_var_sets,
        units,
        var_to_unit,
        args.min_cooccur,
        args.base_max_cluster_size * level,
        unit_scores=unit_scores,
        reserve_bias=reserve_bias,
    )[:2]


def make_importance(g4_unit, g5_metrics, args):
    importance = defaultdict(float)
    for var in g4_unit:
        importance[var] += args.good_g4_weight
    for var in g5_metrics["dangerous_vars"]:
        importance[var] += args.danger_weight
    return importance


def row_from_metrics(seed, n_vars, n_clauses, stage, level, units, unit, metrics, dropped):
    useful = metrics["base_useful_IG"]
    return {
        "seed": seed,
        "n_vars": n_vars,
        "n_clauses": n_clauses,
        "stage": stage,
        "level": level,
        "dropped_before_rebuild": dropped,
        "unit_count": len(units),
        "chosen_unit_size": len(unit),
        "IG": metrics["IG"],
        "forced": metrics["forced"],
        "danger": metrics["danger"],
        "affected": metrics["affected"],
        "danger_rate": metrics["danger_rate"],
        "base_useful_IG": useful,
        "D_pred": n_vars / useful if useful > 0 else "",
        "conflict": metrics["conflict"],
    }


def run_formula(n_vars, n_clauses, args, seed):
    rng = random.Random(seed + 919191)
    formula = sat.generate_random_k_sat(n_vars, n_clauses, 3, seed)
    formula_var_sets = [clause_vars(clause) for clause in formula]
    polarity = polarity_assignment(formula)

    units = [[v] for v in range(1, n_vars + 1)]
    var_to_unit = {v: v - 1 for v in range(1, n_vars + 1)}
    snapshots = {0: (units, var_to_unit)}
    chosen = {}
    metrics_by_level = {}

    for level in range(1, args.max_levels + 1):
        units, var_to_unit = build_level(formula_var_sets, units, var_to_unit, args, level)
        snapshots[level] = (units, var_to_unit)
        unit, metrics = choose_best(
            formula, n_vars, units, args.sample_units, rng, polarity, defaultdict(float), level
        )
        chosen[level] = unit
        metrics_by_level[level] = metrics

    g4_useful = metrics_by_level[4]["base_useful_IG"]
    g5_useful = metrics_by_level[5]["base_useful_IG"]
    dropped = g5_useful < g4_useful

    rows = [
        row_from_metrics(seed, n_vars, n_clauses, "before", 4, snapshots[4][0], chosen[4], metrics_by_level[4], dropped),
        row_from_metrics(seed, n_vars, n_clauses, "before", 5, snapshots[5][0], chosen[5], metrics_by_level[5], dropped),
    ]

    if not dropped and not args.rebuild_always:
        return rows

    importance = make_importance(chosen[4], metrics_by_level[5], args)
    g3_units, g3_var_to_unit = snapshots[3]
    rebuilt_g4_units, rebuilt_g4_var_to_unit = build_level(
        formula_var_sets, g3_units, g3_var_to_unit, args, 4, importance
    )
    rebuilt_g4_unit, rebuilt_g4_metrics = choose_best(
        formula, n_vars, rebuilt_g4_units, args.sample_units, rng, polarity, importance, 4
    )

    rebuilt_g5_units, _ = build_level(
        formula_var_sets, rebuilt_g4_units, rebuilt_g4_var_to_unit, args, 5, importance
    )
    rebuilt_g5_unit, rebuilt_g5_metrics = choose_best(
        formula, n_vars, rebuilt_g5_units, args.sample_units, rng, polarity, importance, 5
    )

    rows.extend([
        row_from_metrics(seed, n_vars, n_clauses, "after", 4, rebuilt_g4_units, rebuilt_g4_unit, rebuilt_g4_metrics, dropped),
        row_from_metrics(seed, n_vars, n_clauses, "after", 5, rebuilt_g5_units, rebuilt_g5_unit, rebuilt_g5_metrics, dropped),
    ])
    return rows


def summarize(rows):
    summary = []
    for n_vars in sorted({row["n_vars"] for row in rows}):
        n_rows = [row for row in rows if row["n_vars"] == n_vars]
        for stage in ("before", "after"):
            stage_rows = [row for row in n_rows if row["stage"] == stage]
            if not stage_rows:
                continue
            for level in sorted({row["level"] for row in stage_rows}):
                items = [row for row in stage_rows if row["level"] == level]
                out = {"n_vars": n_vars, "stage": stage, "level": level, "samples": len(items)}
                for key in ["unit_count", "chosen_unit_size", "IG", "forced", "danger_rate", "base_useful_IG"]:
                    out[f"avg_{key}"] = sum(row[key] for row in items) / len(items)
                out["D_pred"] = n_vars / out["avg_base_useful_IG"] if out["avg_base_useful_IG"] > 0 else ""
                out["drops"] = sum(1 for row in items if row["dropped_before_rebuild"])
                summary.append(out)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[2000, 5000])
    parser.add_argument("--formulas", type=int, default=1)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--max-levels", type=int, default=5)
    parser.add_argument("--min-cooccur", type=int, default=2)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--sample-units", type=int, default=500)
    parser.add_argument("--topdown-bias", type=float, default=5.0)
    parser.add_argument("--good-g4-weight", type=float, default=1.0)
    parser.add_argument("--danger-weight", type=float, default=2.0)
    parser.add_argument("--rebuild-always", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_topdown_reserve_rebuild_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT TOP-DOWN RESERVE REBUILD PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows.extend(run_formula(n_vars, n_clauses, args, seed))
        print("  done")

    summary = summarize(rows)
    write_csv(Path(args.out_prefix + "_details.csv"), rows)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary)

    print("\n=== SUMMARY ===")
    for row in summary:
        print(
            f"{row['stage']} n={row['n_vars']} level={row['level']} "
            f"IG={row['avg_IG']:.2f} base={row['avg_base_useful_IG']:.2f} "
            f"D={row['D_pred'] if row['D_pred'] == '' else round(row['D_pred'], 2)}"
        )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
