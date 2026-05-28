#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Removal-memory recursive cluster probe for SAT.

Baseline:
    recursive clusters built from clause co-occurrence.

Memory:
    after choosing units at a level, run unit propagation with reason tracking.
    If a chosen unit causes variables to be forced, add memory edges:
        chosen vars <-> forced vars
        reason clause vars <-> forced vars
    Next levels build clusters from co-occurrence + memory edges.

This is a structural probe, not a full SAT solver.
"""

import argparse
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat


class DSU:
    def __init__(self, n):
        self.parent = list(range(n))
        self.weight = [1] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union_if_small(self, a, b, max_weight):
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return True
        if self.weight[ra] + self.weight[rb] > max_weight:
            return False
        if self.weight[ra] < self.weight[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.weight[ra] += self.weight[rb]
        return True


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def clause_vars(clause):
    return sorted(set(abs(lit) for lit in clause))


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


def unit_propagate_with_reasons(formula, assignment, n_vars, max_forced=10000):
    assignment = dict(assignment)
    reasons = []
    forced_count = 0
    while forced_count < max_forced:
        changed = False
        for clause_idx, clause in enumerate(formula):
            status, unassigned = clause_value(clause, assignment)
            if status == "conflict":
                return True, assignment, forced_count, reasons
            if status == "unit":
                lit = unassigned[0]
                var = abs(lit)
                value = lit > 0
                if var in assignment:
                    continue
                assignment[var] = value
                reasons.append({
                    "forced_var": var,
                    "forced_value": value,
                    "clause_idx": clause_idx,
                    "reason_vars": clause_vars(clause),
                })
                forced_count += 1
                changed = True
                break
        if not changed:
            return False, assignment, forced_count, reasons
    return False, assignment, forced_count, reasons


def base_pair_counts(formula):
    counts = Counter()
    for clause in formula:
        vars_ = clause_vars(clause)
        for i in range(len(vars_)):
            for j in range(i + 1, len(vars_)):
                counts[(vars_[i], vars_[j])] += 1
    return counts


def build_level_from_counts(n_vars, units, pair_counts, min_weight, max_unit_size):
    var_to_unit = {}
    for idx, unit in enumerate(units):
        for var in unit:
            var_to_unit[var] = idx

    unit_counts = Counter()
    for (a, b), count in pair_counts.items():
        ua = var_to_unit.get(a)
        ub = var_to_unit.get(b)
        if ua is None or ub is None or ua == ub:
            continue
        key = (ua, ub) if ua < ub else (ub, ua)
        unit_counts[key] += count

    dsu = DSU(len(units))
    # Override initial weights with current unit sizes.
    dsu.weight = [len(unit) for unit in units]
    for (a, b), count in sorted(unit_counts.items(), key=lambda item: (-item[1], item[0])):
        if count < min_weight:
            break
        dsu.union_if_small(a, b, max_unit_size)

    grouped = defaultdict(list)
    for idx, unit in enumerate(units):
        grouped[dsu.find(idx)].extend(unit)
    new_units = [sorted(set(values)) for values in grouped.values()]
    new_units.sort(key=lambda unit: (-len(unit), unit[0]))
    return new_units


def polarity_assignment(formula):
    pos = Counter()
    neg = Counter()
    for clause in formula:
        for lit in clause:
            if lit > 0:
                pos[lit] += 1
            else:
                neg[-lit] += 1
    return {var: pos[var] >= neg[var] for var in set(pos) | set(neg)}


def risk_metrics(formula, unit, assignment):
    unit_vars = set(unit)
    affected = 0
    danger = 0
    for clause in formula:
        if not any(abs(lit) in unit_vars for lit in clause):
            continue
        affected += 1
        status, unassigned = clause_value(clause, assignment)
        if status == "unit":
            danger += 1
    rate = danger / affected if affected else 0.0
    return affected, danger, rate


def evaluate_unit(formula, n_vars, unit, polarity):
    assignment = {var: polarity.get(var, True) for var in unit}
    affected, danger, rate = risk_metrics(formula, unit, assignment)
    conflict, propagated, forced, reasons = unit_propagate_with_reasons(
        formula, assignment, n_vars
    )
    ig = n_vars - len(sat.unassigned_vars(n_vars, propagated))
    stability = 1.0 - rate
    useful_ig = 0.0 if conflict else ig * stability
    return {
        "assignment": assignment,
        "propagated": propagated,
        "reasons": reasons,
        "conflict": conflict,
        "IG": ig,
        "forced": forced,
        "affected": affected,
        "danger": danger,
        "danger_rate": rate,
        "useful_IG": useful_ig,
    }


def add_memory_edges(memory_counts, chosen_unit, reasons, weight):
    chosen = set(chosen_unit)
    for reason in reasons:
        forced = reason["forced_var"]
        for var in chosen:
            if var == forced:
                continue
            key = (var, forced) if var < forced else (forced, var)
            memory_counts[key] += weight
        for var in reason["reason_vars"]:
            if var == forced:
                continue
            key = (var, forced) if var < forced else (forced, var)
            memory_counts[key] += weight


def probe_formula(n_vars, n_clauses, args, seed, use_memory):
    rng = random.Random(seed + (999 if use_memory else 111))
    formula = sat.generate_random_k_sat(n_vars, n_clauses, 3, seed)
    base_counts = base_pair_counts(formula)
    memory_counts = Counter()
    units = [[v] for v in range(1, n_vars + 1)]
    polarity = polarity_assignment(formula)
    rows = []

    for level in range(1, args.max_levels + 1):
        combined_counts = Counter(base_counts)
        if use_memory:
            for key, value in memory_counts.items():
                combined_counts[key] += value
        units = build_level_from_counts(
            n_vars,
            units,
            combined_counts,
            args.min_weight,
            args.base_max_cluster_size * level,
        )

        candidates = units
        if args.sample_units and len(candidates) > args.sample_units:
            candidates = rng.sample(candidates, args.sample_units)

        best = None
        for unit in candidates:
            metrics = evaluate_unit(formula, n_vars, unit, polarity)
            key = (-metrics["useful_IG"], -metrics["IG"], metrics["danger_rate"], -len(unit))
            if best is None or key < best[0]:
                best = (key, unit, metrics)
        _, chosen_unit, metrics = best

        if use_memory:
            add_memory_edges(memory_counts, chosen_unit, metrics["reasons"], args.memory_weight)

        rows.append({
            "seed": seed,
            "mode": "memory" if use_memory else "baseline",
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
            "useful_IG": metrics["useful_IG"],
            "D_pred": n_vars / metrics["useful_IG"] if metrics["useful_IG"] > 0 else "",
            "memory_edges": len(memory_counts),
            "conflict": metrics["conflict"],
        })
    return rows


def summarize(rows):
    summary = []
    for mode in sorted({row["mode"] for row in rows}):
        mode_items = [row for row in rows if row["mode"] == mode]
        for n_vars in sorted({row["n_vars"] for row in mode_items}):
            n_items = [row for row in mode_items if row["n_vars"] == n_vars]
            for level in sorted({row["level"] for row in n_items}):
                items = [row for row in n_items if row["level"] == level]
                out = {"mode": mode, "n_vars": n_vars, "level": level, "samples": len(items)}
                for key in [
                    "unit_count",
                    "chosen_unit_size",
                    "IG",
                    "forced",
                    "danger",
                    "affected",
                    "danger_rate",
                    "useful_IG",
                    "memory_edges",
                ]:
                    out[f"avg_{key}"] = sum(row[key] for row in items) / len(items)
                out["D_pred"] = n_vars / out["avg_useful_IG"] if out["avg_useful_IG"] > 0 else ""
                out["conflicts"] = sum(1 for row in items if row["conflict"])
                summary.append(out)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[1000, 2000])
    parser.add_argument("--formulas", type=int, default=3)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--max-levels", type=int, default=5)
    parser.add_argument("--min-weight", type=int, default=2)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--sample-units", type=int, default=500)
    parser.add_argument("--memory-weight", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_removal_memory_probe_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT REMOVAL MEMORY PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows.extend(probe_formula(n_vars, n_clauses, args, seed, False))
            rows.extend(probe_formula(n_vars, n_clauses, args, seed, True))
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
                f"mem={row['avg_memory_edges']:.1f}"
            )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
