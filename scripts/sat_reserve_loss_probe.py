#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reserve-loss probe for recursive SAT clusters.

Reserve idea:
    loss = IG * danger_rate
    reserve[var] accumulates loss from dangerous clauses.

Recovery:
    recovered = beta^level * overlap * reserve_score
    cap: recovered <= IG

Reserve is memory, not fuel:
    it is not decreased after recovery.
"""

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat
from sat_recursive_cluster_levels import build_next_level
from sat_recursive_risk_probe import clause_vars


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def polarity_assignment(formula):
    pos = defaultdict(int)
    neg = defaultdict(int)
    for clause in formula:
        for lit in clause:
            if lit > 0:
                pos[lit] += 1
            else:
                neg[-lit] += 1
    return {var: pos[var] >= neg[var] for var in set(pos) | set(neg)}


def clause_value(clause, assignment):
    unassigned = []
    for lit in clause:
        var = abs(lit)
        if var not in assignment:
            unassigned.append(lit)
            continue
        value = assignment[var]
        if (lit > 0 and value) or (lit < 0 and not value):
            return "sat", []
    if not unassigned:
        return "conflict", []
    return "unit" if len(unassigned) == 1 else "open", unassigned


def risk_and_danger_vars(formula, unit, assignment):
    unit_vars = set(unit)
    affected = 0
    pre_danger = 0
    dangerous_vars = set()
    for clause in formula:
        vars_ = clause_vars(clause)
        if not any(var in unit_vars for var in vars_):
            continue
        affected += 1
        status, _ = clause_value(clause, assignment)
        if status == "unit":
            pre_danger += 1
            dangerous_vars.update(vars_)
    danger_rate = pre_danger / affected if affected else 0.0
    stability = 1.0 - danger_rate
    return affected, pre_danger, danger_rate, stability, dangerous_vars


def evaluate_unit(formula, n_vars, unit, polarity, reserve, beta, level, use_reserve):
    assignment = {var: polarity.get(var, True) for var in unit}
    affected, danger, danger_rate, stability, dangerous_vars = risk_and_danger_vars(
        formula, unit, assignment
    )
    conflict, propagated, forced = sat.unit_propagate(formula, assignment, n_vars)
    ig = n_vars - len(sat.unassigned_vars(n_vars, propagated))
    base_useful = 0.0 if conflict else ig * stability
    loss = ig * danger_rate

    reserve_score = sum(reserve.get(var, 0.0) for var in unit)
    reserved_vars_in_unit = sum(1 for var in unit if reserve.get(var, 0.0) > 0)
    overlap = reserved_vars_in_unit / len(unit) if unit else 0.0
    recovered_raw = (beta ** level) * overlap * reserve_score if use_reserve else 0.0
    recovered = min(ig, recovered_raw)
    useful_with_reserve = base_useful + recovered

    return {
        "IG": ig,
        "forced": forced,
        "affected": affected,
        "danger": danger,
        "danger_rate": danger_rate,
        "stability": stability,
        "base_useful_IG": base_useful,
        "loss": loss,
        "reserve_score": reserve_score,
        "overlap": overlap,
        "recovered": recovered,
        "useful_IG": useful_with_reserve,
        "dangerous_vars": dangerous_vars,
        "conflict": conflict,
    }


def add_loss_to_reserve(reserve, dangerous_vars, loss):
    if not dangerous_vars or loss <= 0:
        return
    share = loss / len(dangerous_vars)
    for var in dangerous_vars:
        reserve[var] += share


def sample_candidates(units, sample_units, rng, reserve, use_reserve):
    if not sample_units or len(units) <= sample_units:
        return units
    if not use_reserve:
        return rng.sample(units, sample_units)

    scored = [
        (sum(reserve.get(var, 0.0) for var in unit), idx, unit)
        for idx, unit in enumerate(units)
    ]
    keep_count = max(1, sample_units // 2)
    top = sorted(scored, key=lambda item: (-item[0], item[1]))[:keep_count]
    chosen_indexes = {idx for _, idx, _ in top}
    remaining = [
        unit for _, idx, unit in scored
        if idx not in chosen_indexes
    ]
    random_count = sample_units - len(top)
    if len(remaining) > random_count:
        remaining = rng.sample(remaining, random_count)
    return [unit for _, _, unit in top] + remaining


def run_formula(n_vars, n_clauses, args, seed, mode):
    # Keep the sampled candidate set identical across modes so baseline vs reserve
    # differences come from reserve logic, not random sampling noise.
    rng = random.Random(seed + 7727)
    formula = sat.generate_random_k_sat(n_vars, n_clauses, 3, seed)
    formula_var_sets = [clause_vars(clause) for clause in formula]
    units = [[v] for v in range(1, n_vars + 1)]
    var_to_unit = {v: v - 1 for v in range(1, n_vars + 1)}
    polarity = polarity_assignment(formula)
    reserve = defaultdict(float)
    rows = []
    use_reserve = mode == "reserve"

    for level in range(1, args.max_levels + 1):
        unit_scores = [sum(reserve.get(var, 0.0) for var in unit) for unit in units]
        units, var_to_unit, _ = build_next_level(
            formula_var_sets,
            units,
            var_to_unit,
            args.min_cooccur,
            args.base_max_cluster_size * level,
            unit_scores=unit_scores if use_reserve else None,
            reserve_bias=args.reserve_bias if use_reserve else 0.0,
        )
        candidates = sample_candidates(units, args.sample_units, rng, reserve, use_reserve)

        best = None
        for unit in candidates:
            metrics = evaluate_unit(
                formula, n_vars, unit, polarity, reserve,
                args.beta, level, use_reserve,
            )
            key = (
                -metrics["useful_IG"],
                -metrics["base_useful_IG"],
                -metrics["IG"],
                metrics["danger_rate"],
                -len(unit),
            )
            if best is None or key < best[0]:
                best = (key, unit, metrics)

        _, chosen_unit, metrics = best
        if use_reserve:
            add_loss_to_reserve(reserve, metrics["dangerous_vars"], metrics["loss"])

        rows.append({
            "seed": seed,
            "mode": mode,
            "n_vars": n_vars,
            "n_clauses": n_clauses,
            "level": level,
            "unit_count": len(units),
            "chosen_unit_size": len(chosen_unit),
            "IG": metrics["IG"],
            "forced": metrics["forced"],
            "danger": metrics["danger"],
            "affected": metrics["affected"],
            "danger_rate": metrics["danger_rate"],
            "base_useful_IG": metrics["base_useful_IG"],
            "loss": metrics["loss"],
            "reserve_size": len(reserve),
            "reserve_total": sum(reserve.values()),
            "reserve_score": metrics["reserve_score"],
            "overlap": metrics["overlap"],
            "recovered": metrics["recovered"],
            "useful_IG": metrics["useful_IG"],
            "D_pred": n_vars / metrics["useful_IG"] if metrics["useful_IG"] > 0 else "",
            "conflict": metrics["conflict"],
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
                    "IG",
                    "danger_rate",
                    "base_useful_IG",
                    "loss",
                    "reserve_total",
                    "reserve_score",
                    "overlap",
                    "recovered",
                    "useful_IG",
                    "chosen_unit_size",
                ]:
                    out[f"avg_{key}"] = sum(row[key] for row in items) / len(items)
                out["D_pred"] = n_vars / out["avg_useful_IG"] if out["avg_useful_IG"] > 0 else ""
                out["conflicts"] = sum(1 for row in items if row["conflict"])
                summary.append(out)
    return summary


def summarize_paired(rows):
    paired = {}
    for row in rows:
        key = (row["seed"], row["n_vars"], row["n_clauses"], row["level"])
        paired.setdefault(key, {})[row["mode"]] = row

    summary = []
    for (seed, n_vars, n_clauses, level), item in sorted(paired.items()):
        if "baseline" not in item or "reserve" not in item:
            continue
        base = item["baseline"]
        res = item["reserve"]
        summary.append({
            "seed": seed,
            "n_vars": n_vars,
            "n_clauses": n_clauses,
            "level": level,
            "baseline_useful_IG": base["useful_IG"],
            "reserve_useful_IG": res["useful_IG"],
            "delta_useful_IG": res["useful_IG"] - base["useful_IG"],
            "baseline_D_pred": base["D_pred"],
            "reserve_D_pred": res["D_pred"],
            "delta_D_pred": (
                res["D_pred"] - base["D_pred"]
                if base["D_pred"] != "" and res["D_pred"] != ""
                else ""
            ),
            "baseline_recovered": base["recovered"],
            "reserve_recovered": res["recovered"],
            "delta_recovered": res["recovered"] - base["recovered"],
            "baseline_reserve_total": base["reserve_total"],
            "reserve_reserve_total": res["reserve_total"],
            "delta_reserve_total": res["reserve_total"] - base["reserve_total"],
        })
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
    parser.add_argument("--beta", type=float, default=0.5)
    parser.add_argument("--reserve-bias", type=float, default=0.35)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_reserve_loss_probe_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT RESERVE LOSS PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows.extend(run_formula(n_vars, n_clauses, args, seed, "baseline"))
            rows.extend(run_formula(n_vars, n_clauses, args, seed, "reserve"))
        print("  done")

    summary = summarize(rows)
    paired_summary = summarize_paired(rows)
    write_csv(Path(args.out_prefix + "_details.csv"), rows)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary)
    write_csv(Path(args.out_prefix + "_paired_summary.csv"), paired_summary)

    print("\n=== SUMMARY ===")
    for row in summary:
        if row["level"] in (4, 5):
            print(
                f"{row['mode']} n={row['n_vars']} level={row['level']} "
                f"base={row['avg_base_useful_IG']:.2f} "
                f"rec={row['avg_recovered']:.2f} "
                f"useful={row['avg_useful_IG']:.2f} "
                f"D={row['D_pred'] if row['D_pred'] == '' else round(row['D_pred'], 2)}"
            )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")
    print(args.out_prefix + "_paired_summary.csv")


if __name__ == "__main__":
    main()
