#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fast D-scaling probe for recursive SAT clusters.

This is a probe, not a SAT solver. It measures predicted depth:

    D = n / useful_IG
    useful_IG = IG * (1 - danger_rate)
    danger_rate = dangerous_clauses / affected_clauses

IG is measured after unit propagation. The fast path uses a var_to_clauses
index, but propagation is allowed to continue beyond the initially affected
clauses.
"""

import argparse
import csv
import random
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat
from sat_recursive_cluster_levels import DSU, build_next_level
from sat_reserve_loss_probe import evaluate_unit


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def clause_vars(clause):
    return sorted(set(abs(lit) for lit in clause))


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


def build_var_to_clauses(formula, n_vars):
    index = [[] for _ in range(n_vars + 1)]
    for clause_idx, clause in enumerate(formula):
        for lit in clause:
            index[abs(lit)].append(clause_idx)
    return index


def clause_eval(clause, assignment):
    unassigned = []
    for lit in clause:
        var = abs(lit)
        if var not in assignment:
            unassigned.append(lit)
            continue
        value = assignment[var]
        if (lit > 0 and value) or (lit < 0 and not value):
            return "sat", unassigned
    if not unassigned:
        return "conflict", unassigned
    if len(unassigned) == 1:
        return "unit", unassigned
    return "open", unassigned


def affected_clause_ids(unit, var_to_clauses):
    affected = set()
    for var in unit:
        affected.update(var_to_clauses[var])
    return affected


def indexed_unit_propagate(formula, var_to_clauses, initial_assignment, max_forced):
    assignment = dict(initial_assignment)
    queue = deque(initial_assignment.keys())
    queued_clauses = set()
    forced = 0

    while queue:
        var = queue.popleft()
        for clause_idx in var_to_clauses[var]:
            if clause_idx in queued_clauses:
                continue
            queued_clauses.add(clause_idx)

        while queued_clauses:
            clause_idx = queued_clauses.pop()
            status, unassigned = clause_eval(formula[clause_idx], assignment)
            if status == "conflict":
                return True, assignment, forced
            if status != "unit":
                continue
            lit = unassigned[0]
            unit_var = abs(lit)
            unit_value = lit > 0
            if unit_var in assignment:
                if assignment[unit_var] != unit_value:
                    return True, assignment, forced
                continue
            assignment[unit_var] = unit_value
            forced += 1
            if forced >= max_forced:
                return False, assignment, forced
            queue.append(unit_var)

    return False, assignment, forced


def evaluate_unit_fast(formula, n_vars, var_to_clauses, unit, polarity, cache, cache_key_prefix, max_forced):
    assignment = {var: polarity.get(var, True) for var in unit}
    assignment_key = tuple(sorted(assignment.items()))
    cache_key = cache_key_prefix + (tuple(sorted(unit)), assignment_key)
    if cache_key in cache:
        return cache[cache_key]

    affected_ids = affected_clause_ids(unit, var_to_clauses)
    dangerous = 0
    dangerous_vars = set()
    freedoms = []
    for clause_idx in affected_ids:
        status, _ = clause_eval(formula[clause_idx], assignment)
        if status == "unit":
            dangerous += 1
            dangerous_vars.update(abs(lit) for lit in formula[clause_idx])
        if status == "conflict":
            freedoms.append(0)
        elif status != "sat":
            freedoms.append(len([lit for lit in formula[clause_idx] if abs(lit) not in assignment]))

    affected = len(affected_ids)
    danger_rate = dangerous / affected if affected else 0.0
    conflict, propagated, forced = indexed_unit_propagate(
        formula, var_to_clauses, assignment, max_forced
    )
    ig = len(propagated)
    useful_ig = 0.0 if conflict else ig * (1.0 - danger_rate)
    metrics = {
        "IG": ig,
        "forced": forced,
        "affected_clauses": affected,
        "dangerous_clauses": dangerous,
        "danger_rate": danger_rate,
        "avg_freedom": (sum(freedoms) / len(freedoms)) if freedoms else 0.0,
        "useful_IG": useful_ig,
        "D": n_vars / useful_ig if useful_ig > 0 else "",
        "dangerous_vars": dangerous_vars,
        "conflict": conflict,
    }
    cache[cache_key] = metrics
    return metrics


def edge_priority(item, unit_scores, reserve_bias):
    (a, b), count = item
    score_sum = unit_scores[a] + unit_scores[b]
    adjusted = count + reserve_bias * score_sum
    return (-adjusted, -count, -score_sum, a, b)


def build_next_level_sparse(
    formula_var_sets,
    units,
    var_to_unit,
    min_cooccur,
    max_unit_weight,
    top_neighbors,
    unit_scores=None,
    reserve_bias=0.0,
):
    edge_counts = Counter()
    for vars_ in formula_var_sets:
        touched = sorted(set(var_to_unit[v] for v in vars_))
        for i in range(len(touched)):
            for j in range(i + 1, len(touched)):
                edge_counts[(touched[i], touched[j])] += 1

    if unit_scores is None:
        unit_scores = [0.0] * len(units)

    eligible = []
    for item in edge_counts.items():
        (a, b), count = item
        score_sum = unit_scores[a] + unit_scores[b]
        adjusted = count + reserve_bias * score_sum
        if count >= min_cooccur or (reserve_bias > 0 and score_sum > 0 and adjusted >= min_cooccur):
            eligible.append(item)

    if top_neighbors and top_neighbors > 0:
        by_unit = defaultdict(list)
        for item in eligible:
            (a, b), _count = item
            by_unit[a].append(item)
            by_unit[b].append(item)
        keep = set()
        for unit_idx, items in by_unit.items():
            ranked = sorted(items, key=lambda item: edge_priority(item, unit_scores, reserve_bias))
            for item in ranked[:top_neighbors]:
                keep.add(item[0])
        eligible = [(edge, edge_counts[edge]) for edge in keep]

    dsu = DSU(len(units))
    weights = [len(unit) for unit in units]
    for (a, b), _count in sorted(eligible, key=lambda item: edge_priority(item, unit_scores, reserve_bias)):
        dsu.union_if_small(a, b, max_unit_weight, weights)

    grouped = defaultdict(list)
    for idx, unit in enumerate(units):
        grouped[dsu.find(idx)].extend(unit)
    new_units = [sorted(values) for values in grouped.values()]
    new_units.sort(key=lambda unit: (-len(unit), unit[0]))
    new_var_to_unit = {}
    for idx, unit in enumerate(new_units):
        for var in unit:
            new_var_to_unit[var] = idx
    return new_units, new_var_to_unit, len(edge_counts), len(eligible)


def build_level(formula_var_sets, units, var_to_unit, args, level, importance=None, exact=False):
    unit_scores = None
    reserve_bias = 0.0
    if importance:
        unit_scores = [sum(importance.get(var, 0.0) for var in unit) for unit in units]
        reserve_bias = args.topdown_bias
    if exact:
        new_units, new_var_to_unit, edge_counts = build_next_level(
            formula_var_sets,
            units,
            var_to_unit,
            args.min_cooccur,
            args.base_max_cluster_size * level,
            unit_scores=unit_scores,
            reserve_bias=reserve_bias,
        )
        return new_units, new_var_to_unit, len(edge_counts), ""
    return build_next_level_sparse(
        formula_var_sets,
        units,
        var_to_unit,
        args.min_cooccur,
        args.base_max_cluster_size * level,
        args.top_neighbors,
        unit_scores=unit_scores,
        reserve_bias=reserve_bias,
    )


def candidate_units(units, args, rng, importance):
    if not args.sample_units or len(units) <= args.sample_units:
        pool = list(units)
    else:
        scored = [
            (sum(importance.get(var, 0.0) for var in unit), len(unit), idx, unit)
            for idx, unit in enumerate(units)
        ]
        keep_count = max(1, args.sample_units // 2)
        if importance:
            top = sorted(scored, key=lambda item: (-item[0], -item[1], item[2]))[:keep_count]
        else:
            top = sorted(scored, key=lambda item: (-item[1], item[2]))[:keep_count]
        chosen = {idx for _, _, idx, _ in top}
        remaining = [unit for _, _, idx, unit in scored if idx not in chosen]
        random_count = args.sample_units - len(top)
        if len(remaining) > random_count:
            remaining = rng.sample(remaining, random_count)
        pool = [unit for _, _, _, unit in top] + remaining

    if args.candidate_cap and len(pool) > args.candidate_cap:
        ranked = sorted(
            pool,
            key=lambda unit: (
                -sum(importance.get(var, 0.0) for var in unit),
                -len(unit),
                unit[0],
            ),
        )
        return ranked[:args.candidate_cap]
    return pool


def choose_best_fast(formula, n_vars, var_to_clauses, units, args, rng, polarity, importance, cache, seed, level):
    best = None
    candidates = candidate_units(units, args, rng, importance)
    cache_key_prefix = (
        seed,
        level,
        args.topdown_bias,
        args.good_g4_weight,
        args.danger_weight,
        args.top_neighbors,
    )
    for unit in candidates:
        metrics = evaluate_unit_fast(
            formula,
            n_vars,
            var_to_clauses,
            unit,
            polarity,
            cache,
            cache_key_prefix,
            args.max_forced,
        )
        key = (
            -metrics["useful_IG"],
            -metrics["IG"],
            metrics["danger_rate"],
            -sum(importance.get(var, 0.0) for var in unit),
            -len(unit),
            unit[0],
        )
        if best is None or key < best[0]:
            best = (key, unit, metrics)
    return best[1], best[2]


def choose_best_exact(formula, n_vars, units, args, rng, polarity, importance, level):
    best = None
    for unit in candidate_units(units, args, rng, importance):
        metrics = evaluate_unit(formula, n_vars, unit, polarity, defaultdict(float), 0.5, level, False)
        normalized = {
            "IG": metrics["IG"],
            "forced": metrics["forced"],
            "affected_clauses": metrics["affected"],
            "dangerous_clauses": metrics["danger"],
            "danger_rate": metrics["danger_rate"],
            "avg_freedom": "",
            "useful_IG": metrics["base_useful_IG"],
            "D": n_vars / metrics["base_useful_IG"] if metrics["base_useful_IG"] > 0 else "",
            "dangerous_vars": metrics["dangerous_vars"],
            "conflict": metrics["conflict"],
        }
        key = (
            -normalized["useful_IG"],
            -normalized["IG"],
            normalized["danger_rate"],
            -sum(importance.get(var, 0.0) for var in unit),
            -len(unit),
            unit[0],
        )
        if best is None or key < best[0]:
            best = (key, unit, normalized)
    return best[1], best[2]


def make_importance(good_unit, weak_metrics, args):
    importance = defaultdict(float)
    for var in good_unit:
        importance[var] += args.good_g4_weight
    for var in weak_metrics["dangerous_vars"]:
        importance[var] += args.danger_weight
    return importance


def blank_after():
    return {
        "IG_after_rebuild": "",
        "danger_rate_after_rebuild": "",
        "useful_IG_after_rebuild": "",
        "D_after_rebuild": "",
    }


def output_row(
    n_vars,
    seed,
    level,
    metrics,
    unit,
    args,
    runtime,
    rebuild_triggered,
    trigger_reason,
    trigger_level,
    ratio_54,
    ratio_43,
    useful_ig_g3,
    useful_ig_g4,
    useful_ig_g5,
    after_metrics=None,
):
    baseline_d = metrics["D"]
    after_d = after_metrics["D"] if after_metrics else ""
    improvement_ratio = (
        baseline_d / after_d
        if baseline_d != "" and after_d != "" and after_d > 0
        else ""
    )
    row = {
        "n": n_vars,
        "seed": seed,
        "level": level,
        "IG": metrics["IG"],
        "danger_rate": metrics["danger_rate"],
        "avg_freedom": metrics.get("avg_freedom", ""),
        "useful_IG": metrics["useful_IG"],
        "D": metrics["D"],
        **blank_after(),
        "sample_units": args.sample_units,
        "candidate_cap": args.candidate_cap,
        "top_neighbors": args.top_neighbors,
        "min_useful_growth": args.min_useful_growth,
        "topdown_bias": args.topdown_bias,
        "affected_clauses": metrics["affected_clauses"],
        "dangerous_clauses": metrics["dangerous_clauses"],
        "forced": metrics["forced"],
        "avg_forced_per_assignment": (
            metrics["forced"] / len(unit) if unit else 0.0
        ),
        "chosen_unit_size": len(unit),
        "rebuilt": after_metrics is not None,
        "rebuild_triggered": rebuild_triggered,
        "trigger_level": trigger_level if rebuild_triggered else "",
        "trigger_reason": trigger_reason,
        "ratio_54": ratio_54,
        "ratio_43": ratio_43,
        "useful_IG_G3": useful_ig_g3,
        "useful_IG_G4": useful_ig_g4,
        "useful_IG_G5": useful_ig_g5,
        "baseline_D": baseline_d,
        "after_D": after_d,
        "improvement_ratio": improvement_ratio,
        "runtime_seconds": runtime,
    }
    if after_metrics:
        row.update({
            "IG_after_rebuild": after_metrics["IG"],
            "danger_rate_after_rebuild": after_metrics["danger_rate"],
            "useful_IG_after_rebuild": after_metrics["useful_IG"],
            "D_after_rebuild": after_metrics["D"],
        })
    return row


def run_probe(n_vars, n_clauses, args, seed, exact=False):
    started = time.perf_counter()
    rng = random.Random(seed + 616161)
    formula = sat.generate_random_k_sat(n_vars, n_clauses, args.k, seed)
    formula_var_sets = [clause_vars(clause) for clause in formula]
    var_to_clauses = build_var_to_clauses(formula, n_vars)
    polarity = polarity_assignment(formula)
    cache = {}

    units = [[v] for v in range(1, n_vars + 1)]
    var_to_unit = {v: v - 1 for v in range(1, n_vars + 1)}
    snapshots = {0: (units, var_to_unit)}
    chosen = {}
    metrics_by_level = {}

    for level in range(1, args.max_levels + 1):
        units, var_to_unit, _edge_count, _eligible = build_level(
            formula_var_sets, units, var_to_unit, args, level, exact=exact
        )
        snapshots[level] = (units, var_to_unit)
        if exact:
            unit, metrics = choose_best_exact(
                formula, n_vars, units, args, rng, polarity, defaultdict(float), level
            )
        else:
            unit, metrics = choose_best_fast(
                formula, n_vars, var_to_clauses, units, args, rng, polarity,
                defaultdict(float), cache, seed, level
            )
        chosen[level] = unit
        metrics_by_level[level] = metrics

    after_by_level = {}
    rebuild_triggered = False
    trigger_reason = ""
    trigger_level = None
    for level in range(args.max_levels - 1, 0, -1):
        current_useful = metrics_by_level[level]["useful_IG"]
        next_useful = metrics_by_level[level + 1]["useful_IG"]
        if next_useful < current_useful:
            trigger_level = level
            trigger_reason = "drop"
            break
        if current_useful > 0 and next_useful < current_useful * args.min_useful_growth:
            trigger_level = level
            trigger_reason = "weak_growth"
            break

    if trigger_level is not None or args.rebuild_always:
        rebuild_triggered = trigger_level is not None
        if trigger_reason == "" and args.rebuild_always:
            trigger_reason = "forced"
        level = trigger_level if trigger_level is not None else args.max_levels - 1
        importance = make_importance(chosen[level], metrics_by_level[level + 1], args)
        base_units, base_var_to_unit = snapshots[level - 1]
        rebuilt_units, rebuilt_var_to_unit, _edge_count, _eligible = build_level(
            formula_var_sets, base_units, base_var_to_unit, args, level, importance, exact=exact
        )
        if exact:
            rebuilt_unit, rebuilt_metrics = choose_best_exact(
                formula, n_vars, rebuilt_units, args, rng, polarity, importance, level
            )
        else:
            rebuilt_unit, rebuilt_metrics = choose_best_fast(
                formula, n_vars, var_to_clauses, rebuilt_units, args, rng, polarity,
                importance, cache, seed, level
            )
        after_by_level[level] = (rebuilt_unit, rebuilt_metrics)

        rebuilt_next_units, _rebuilt_next_var_to_unit, _edge_count, _eligible = build_level(
            formula_var_sets, rebuilt_units, rebuilt_var_to_unit, args, level + 1, importance, exact=exact
        )
        if exact:
            rebuilt_next_unit, rebuilt_next_metrics = choose_best_exact(
                formula, n_vars, rebuilt_next_units, args, rng, polarity, importance, level + 1
            )
        else:
            rebuilt_next_unit, rebuilt_next_metrics = choose_best_fast(
                formula, n_vars, var_to_clauses, rebuilt_next_units, args, rng, polarity,
                importance, cache, seed, level + 1
            )
        after_by_level[level + 1] = (rebuilt_next_unit, rebuilt_next_metrics)

    runtime = time.perf_counter() - started
    rows = []
    useful_3 = metrics_by_level[3]["useful_IG"] if 3 in metrics_by_level else 0.0
    useful_4 = metrics_by_level[4]["useful_IG"] if 4 in metrics_by_level else 0.0
    useful_5 = metrics_by_level[5]["useful_IG"] if 5 in metrics_by_level else 0.0
    ratio_43 = useful_4 / useful_3 if useful_3 > 0 else ""
    ratio_54 = useful_5 / useful_4 if useful_4 > 0 else ""
    for level in range(1, args.max_levels + 1):
        after = after_by_level.get(level)
        rows.append(output_row(
            n_vars,
            seed,
            level,
            metrics_by_level[level],
            chosen[level],
            args,
            runtime,
            rebuild_triggered and after is not None,
            trigger_reason if after is not None else "",
            trigger_level,
            ratio_54,
            ratio_43,
            useful_3,
            useful_4,
            useful_5,
            after[1] if after else None,
        ))
    return rows


def validation_rows(fast_rows, exact_rows):
    exact_by_key = {(row["n"], row["seed"], row["level"]): row for row in exact_rows}
    rows = []
    for fast in fast_rows:
        key = (fast["n"], fast["seed"], fast["level"])
        exact = exact_by_key.get(key)
        if not exact:
            continue
        rows.append({
            "n": fast["n"],
            "seed": fast["seed"],
            "level": fast["level"],
            "fast_IG": fast["IG"],
            "exact_IG": exact["IG"],
            "delta_IG": fast["IG"] - exact["IG"],
            "fast_danger_rate": fast["danger_rate"],
            "exact_danger_rate": exact["danger_rate"],
            "delta_danger_rate": fast["danger_rate"] - exact["danger_rate"],
            "fast_useful_IG": fast["useful_IG"],
            "exact_useful_IG": exact["useful_IG"],
            "delta_useful_IG": fast["useful_IG"] - exact["useful_IG"],
            "fast_D": fast["D"],
            "exact_D": exact["D"],
            "D_ratio_fast_over_exact": (
                fast["D"] / exact["D"]
                if fast["D"] != "" and exact["D"] != "" and exact["D"] != 0
                else ""
            ),
            "fast_rebuilt": fast["rebuilt"],
            "exact_rebuilt": exact["rebuilt"],
            "trend_match_useful": (
                (fast["useful_IG_after_rebuild"] == "" and exact["useful_IG_after_rebuild"] == "")
                or (fast["useful_IG_after_rebuild"] != "" and exact["useful_IG_after_rebuild"] != "")
            ),
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[1000, 2000, 5000])
    parser.add_argument("--formulas", type=int, default=1)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--max-levels", type=int, default=5)
    parser.add_argument("--min-cooccur", type=int, default=2)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--sample-units", type=int, default=500)
    parser.add_argument("--candidate-cap", type=int, default=250)
    parser.add_argument("--top-neighbors", type=int, default=16)
    parser.add_argument("--topdown-bias", type=float, default=5.0)
    parser.add_argument("--good-g4-weight", type=float, default=1.0)
    parser.add_argument("--danger-weight", type=float, default=2.0)
    parser.add_argument("--min-useful-growth", type=float, default=1.05)
    parser.add_argument("--max-forced", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--rebuild-always", action="store_true")
    parser.add_argument("--out-prefix", default="sat_fast_d_scaling_step1")
    args = parser.parse_args()

    fast_rows = []
    exact_rows = []
    print("=== SAT FAST D-SCALING PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            fast_rows.extend(run_probe(n_vars, n_clauses, args, seed, exact=False))
            if args.validate:
                exact_rows.extend(run_probe(n_vars, n_clauses, args, seed, exact=True))
        print("  done")

    write_csv(Path(args.out_prefix + "_fast.csv"), fast_rows)
    if args.validate:
        write_csv(Path(args.out_prefix + "_exact.csv"), exact_rows)
        write_csv(Path(args.out_prefix + "_validation.csv"), validation_rows(fast_rows, exact_rows))

    print("\n=== LEVEL 5 SUMMARY ===")
    for row in fast_rows:
        if row["level"] == 5:
            print(
                f"fast n={row['n']} seed={row['seed']} "
                f"IG={row['IG']} useful={row['useful_IG']:.2f} "
                f"D={row['D'] if row['D'] == '' else round(row['D'], 2)} "
                f"afterD={row['D_after_rebuild'] if row['D_after_rebuild'] == '' else round(row['D_after_rebuild'], 2)}"
            )
    print("Files written:")
    print(args.out_prefix + "_fast.csv")
    if args.validate:
        print(args.out_prefix + "_exact.csv")
        print(args.out_prefix + "_validation.csv")


if __name__ == "__main__":
    main()
