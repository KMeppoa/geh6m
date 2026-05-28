#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Recursive risk probe for SAT clusters.

Measures whether pre-danger has a stable pattern across recursive scales.

For a chosen unit/cluster:
    affected_clauses = clauses touching any variable in the unit
    pre_danger       = affected clauses that become unit clauses before G
    danger_rate      = pre_danger / affected_clauses
    stability        = 1 - danger_rate

This tests whether risk is roughly constant across levels:
    variables -> clusters -> clusters of clusters -> ...
"""

import argparse
import csv
import random
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat
from sat_recursive_cluster_levels import build_next_level


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def clause_vars(clause):
    return sorted(set(abs(lit) for lit in clause))


def clause_status(clause, assignment):
    unknown = False
    for lit in clause:
        var = abs(lit)
        if var not in assignment:
            unknown = True
            continue
        value = assignment[var]
        if (lit > 0 and value) or (lit < 0 and not value):
            return "sat"
    return "unknown" if unknown else "unsat"


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


def risk_metrics(formula, unit, assignment):
    unit_vars = set(unit)
    affected = 0
    pre_danger = 0
    pre_unsat = 0
    pre_unknown = 0
    pre_sat = 0
    for clause in formula:
        if not any(abs(lit) in unit_vars for lit in clause):
            continue
        affected += 1
        status = clause_status(clause, assignment)
        if status == "sat":
            pre_sat += 1
            continue
        if status == "unsat":
            pre_unsat += 1
            continue
        pre_unknown += 1
        unassigned = sum(1 for lit in clause if abs(lit) not in assignment)
        if unassigned == 1:
            pre_danger += 1

    danger_rate = pre_danger / affected if affected else 0.0
    stability = 1.0 - danger_rate
    return {
        "affected_clauses": affected,
        "pre_danger": pre_danger,
        "pre_unsat": pre_unsat,
        "pre_unknown": pre_unknown,
        "pre_sat": pre_sat,
        "danger_rate": danger_rate,
        "stability": stability,
    }


def choose_unit(formula, n_vars, units, sample_units, rng):
    polarity = polarity_assignment(formula)
    candidates = units
    if sample_units and len(candidates) > sample_units:
        candidates = rng.sample(candidates, sample_units)

    ranked = []
    for unit in candidates:
        assignment = {var: polarity.get(var, True) for var in unit}
        risk = risk_metrics(formula, unit, assignment)
        conflict, propagated, forced = sat.unit_propagate(formula, assignment, n_vars)
        ig = n_vars - len(sat.unassigned_vars(n_vars, propagated))
        useful_ig = ig * risk["stability"] * (0 if conflict else 1)
        ranked.append((
            -useful_ig,
            -ig,
            risk["danger_rate"],
            -len(unit),
            unit,
            assignment,
            propagated,
            forced,
            conflict,
            risk,
            useful_ig,
            ig,
        ))
    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4][0]))
    return ranked[0]


def probe_formula(n_vars, n_clauses, args, seed):
    rng = random.Random(seed + 882211)
    formula = sat.generate_random_k_sat(n_vars, n_clauses, 3, seed)
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
        (
            _neg_useful,
            _neg_ig,
            _danger_rate,
            _neg_size,
            unit,
            assignment,
            propagated,
            forced,
            conflict,
            risk,
            useful_ig,
            ig,
        ) = choose_unit(formula, n_vars, units, args.sample_units, rng)

        rows.append({
            "seed": seed,
            "n_vars": n_vars,
            "n_clauses": n_clauses,
            "level": level,
            "unit_count": len(units),
            "chosen_unit_size": len(unit),
            "IG": ig,
            "forced": forced,
            "useful_IG": useful_ig,
            "D_pred": n_vars / useful_ig if useful_ig > 0 else "",
            "conflict": conflict,
            **risk,
        })
    return rows


def summarize(rows):
    summary = []
    for n_vars in sorted({row["n_vars"] for row in rows}):
        n_items = [row for row in rows if row["n_vars"] == n_vars]
        for level in sorted({row["level"] for row in n_items}):
            items = [row for row in n_items if row["level"] == level]
            out = {"n_vars": n_vars, "level": level, "samples": len(items)}
            for key in [
                "unit_count",
                "chosen_unit_size",
                "affected_clauses",
                "pre_danger",
                "danger_rate",
                "stability",
                "IG",
                "useful_IG",
                "forced",
            ]:
                out[f"avg_{key}"] = sum(row[key] for row in items) / len(items)
            out["D_pred"] = n_vars / out["avg_useful_IG"] if out["avg_useful_IG"] > 0 else ""
            out["conflicts"] = sum(1 for row in items if row["conflict"])
            summary.append(out)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[100, 200, 500])
    parser.add_argument("--formulas", type=int, default=5)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--min-cooccur", type=int, default=2)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--max-levels", type=int, default=3)
    parser.add_argument("--sample-units", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_recursive_risk_probe_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT RECURSIVE RISK PROBE ===")
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
        print(
            f"n={row['n_vars']} level={row['level']} "
            f"danger={row['avg_pre_danger']:.2f} "
            f"affected={row['avg_affected_clauses']:.2f} "
            f"rate={row['avg_danger_rate']:.3f} "
            f"IG={row['avg_IG']:.2f} "
            f"usefulIG={row['avg_useful_IG']:.2f} "
            f"D={row['D_pred'] if row['D_pred'] == '' else round(row['D_pred'], 2)}"
        )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
