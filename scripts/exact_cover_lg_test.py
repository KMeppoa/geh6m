#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L/G experiment for Exact Cover.

Task:
    Choose sets so every universe element is covered exactly once.

L:
    Local score: uncovered elements, duplicate-covered elements, chosen set count.

G:
    Global propagation:
        - if an element is already covered twice, the branch is dead;
        - if an uncovered element has only one compatible remaining set, force it;
        - if an uncovered element has no compatible remaining set, the branch is dead.
"""

import argparse
import csv
import json
import random
from dataclasses import dataclass, field
from itertools import combinations
from math import inf
from pathlib import Path


@dataclass
class RunResult:
    case_seed: int
    mode: str
    status: str
    success: bool
    steps: int
    chosen: list
    metrics: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)


def generate_exact_cover(universe_size, n_sets, solution_size, seed, profile):
    rng = random.Random(seed)
    universe = set(range(universe_size))
    sets = []

    shuffled = list(universe)
    rng.shuffle(shuffled)
    chunks = [[] for _ in range(solution_size)]
    for idx, element in enumerate(shuffled):
        chunks[idx % solution_size].append(element)

    planted = [set(chunk) for chunk in chunks]
    sets.extend(planted)

    if profile == "trap":
        # Bait sets cover many elements, but overlap with several planted sets.
        # They look good locally but make exact cover harder.
        while len(sets) < max(solution_size + 1, n_sets // 2):
            size = rng.randint(max(2, universe_size // 4), max(3, universe_size // 2))
            sets.append(set(rng.sample(list(universe), size)))

    while len(sets) < n_sets:
        size = rng.randint(1, max(2, universe_size // 4))
        sets.append(set(rng.sample(list(universe), size)))

    rng.shuffle(sets)
    return universe, sets


def coverage_counts(sets, chosen):
    counts = {}
    for idx in chosen:
        for element in sets[idx]:
            counts[element] = counts.get(element, 0) + 1
    return counts


def verify_exact_cover(universe, sets, chosen):
    counts = coverage_counts(sets, chosen)
    return all(counts.get(element, 0) == 1 for element in universe)


def exact_solution_exists(universe, sets, max_solution_size):
    indices = range(len(sets))
    for r in range(max_solution_size + 1):
        for combo in combinations(indices, r):
            if verify_exact_cover(universe, sets, combo):
                return True
    return False


def compatible_set(sets, chosen, idx):
    counts = coverage_counts(sets, chosen)
    return all(counts.get(element, 0) == 0 for element in sets[idx])


def remaining_indices(sets, chosen):
    chosen_set = set(chosen)
    return [idx for idx in range(len(sets)) if idx not in chosen_set]


def stats(universe, sets, chosen):
    counts = coverage_counts(sets, chosen)
    uncovered = [e for e in universe if counts.get(e, 0) == 0]
    duplicate = [e for e in universe if counts.get(e, 0) > 1]
    remaining = remaining_indices(sets, chosen)
    compatible = [idx for idx in remaining if compatible_set(sets, chosen, idx)]

    dead_elements = 0
    forced_elements = 0
    pressure = 0
    for element in uncovered:
        carriers = [idx for idx in compatible if element in sets[idx]]
        if not carriers:
            dead_elements += 1
        elif len(carriers) == 1:
            forced_elements += 1
        pressure += max(0, 5 - len(carriers))

    return {
        "covered_once": sum(1 for e in universe if counts.get(e, 0) == 1),
        "uncovered": len(uncovered),
        "duplicate": len(duplicate),
        "chosen": len(chosen),
        "compatible_remaining": len(compatible),
        "dead_elements": dead_elements,
        "forced_elements": forced_elements,
        "pressure": pressure,
    }


def propagate(universe, sets, chosen, max_forced=10000):
    chosen = list(chosen)
    forced_count = 0

    while forced_count < max_forced:
        st = stats(universe, sets, chosen)
        if st["duplicate"] or st["dead_elements"]:
            return True, chosen, forced_count
        if st["uncovered"] == 0:
            return False, chosen, forced_count

        counts = coverage_counts(sets, chosen)
        uncovered = [e for e in universe if counts.get(e, 0) == 0]
        compatible = [idx for idx in remaining_indices(sets, chosen) if compatible_set(sets, chosen, idx)]
        forced = None
        for element in sorted(uncovered):
            carriers = [idx for idx in compatible if element in sets[idx]]
            if len(carriers) == 1:
                forced = carriers[0]
                break

        if forced is None:
            return False, chosen, forced_count
        chosen.append(forced)
        forced_count += 1

    return False, chosen, forced_count


def score_l(universe, sets, chosen):
    st = stats(universe, sets, chosen)
    return (
        st["duplicate"] * 1_000_000
        + st["dead_elements"] * 500_000
        + st["uncovered"] * 100
        + st["chosen"] * 12
        + st["pressure"]
        - st["covered_once"]
    )


def score_lg(universe, sets, chosen):
    conflict, propagated, forced_count = propagate(universe, sets, chosen)
    if conflict:
        return 10_000_000
    st = stats(universe, sets, propagated)
    return (
        st["uncovered"] * 100
        + st["chosen"] * 12
        + st["pressure"]
        - st["covered_once"] * 2
        - forced_count * 30
    )


def possible_actions(universe, sets, chosen):
    counts = coverage_counts(sets, chosen)
    actions = []
    for idx in remaining_indices(sets, chosen):
        if all(counts.get(element, 0) == 0 for element in sets[idx]):
            if any(counts.get(element, 0) == 0 for element in sets[idx]):
                actions.append(idx)
    return actions


def evaluate_future(universe, sets, chosen, depth, score_kind, branch_cap, score_counter):
    if verify_exact_cover(universe, sets, chosen):
        return -1_000_000

    base_score = score_lg(universe, sets, chosen) if score_kind == "LG" else score_l(universe, sets, chosen)
    score_counter[0] += 1
    if base_score >= 10_000_000 or depth <= 0:
        return base_score

    ranked = []
    for action in possible_actions(universe, sets, chosen):
        new_chosen = chosen + [action]
        local_score = score_lg(universe, sets, new_chosen) if score_kind == "LG" else score_l(universe, sets, new_chosen)
        score_counter[0] += 1
        ranked.append((local_score, action, new_chosen))

    ranked.sort(key=lambda x: (x[0], x[1]))
    best = inf
    for _, _, new_chosen in ranked[:branch_cap]:
        best = min(
            best,
            evaluate_future(universe, sets, new_chosen, depth - 1, score_kind, branch_cap, score_counter),
        )
    return best


def run_solver(universe, sets, mode, max_steps, branch_cap):
    chosen = []
    logs = []
    forced_steps = 0
    score_calls = 0
    decision_steps = 0

    if mode == "greedy_L":
        score_kind, depth = "L", 1
    elif mode == "greedy_LG":
        score_kind, depth = "LG", 1
    elif mode.startswith("lookahead_LG_"):
        score_kind, depth = "LG", int(mode.rsplit("_", 1)[1])
    elif mode.startswith("lookahead_L_"):
        score_kind, depth = "L", int(mode.rsplit("_", 1)[1])
    else:
        raise ValueError(f"Unknown mode: {mode}")

    for step in range(max_steps):
        if score_kind == "LG":
            conflict, propagated, forced = propagate(universe, sets, chosen)
            forced_steps += forced
            chosen = propagated
            if conflict:
                return RunResult(0, mode, "FAILED_TO_FIND", False, step, chosen, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)

        if verify_exact_cover(universe, sets, chosen):
            return RunResult(0, mode, "SAT_FOUND", True, step, chosen, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)

        actions = possible_actions(universe, sets, chosen)
        if not actions:
            break

        ranked = []
        for action in actions:
            new_chosen = chosen + [action]
            counter = [0]
            future = evaluate_future(universe, sets, new_chosen, depth - 1, score_kind, branch_cap, counter)
            score_calls += counter[0]
            ranked.append((future, action))

        ranked.sort(key=lambda x: (x[0], x[1]))
        chosen.append(ranked[0][1])
        decision_steps += 1
        logs.append({"step": step, "chosen_set": ranked[0][1], "score": ranked[0][0]})

    return RunResult(0, mode, "FAILED_TO_FIND", False, max_steps, chosen, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)


def summarize(results):
    rows = []
    for mode in sorted({r.mode for r in results}):
        subset = [r for r in results if r.mode == mode]
        successes = [r for r in subset if r.success]
        rows.append({
            "mode": mode,
            "total": len(subset),
            "success": len(successes),
            "fail": len(subset) - len(successes),
            "success_rate": len(successes) / len(subset) if subset else 0,
            "avg_steps_success": sum(r.steps for r in successes) / len(successes) if successes else "",
            "avg_decision_steps": sum(r.metrics.get("decision_steps", 0) for r in successes) / len(successes) if successes else "",
            "avg_forced_steps": sum(r.metrics.get("forced_steps", 0) for r in successes) / len(successes) if successes else "",
            "avg_score_calls": sum(r.metrics.get("score_calls", 0) for r in subset) / len(subset) if subset else "",
        })
    return rows


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=30)
    parser.add_argument("--universe", type=int, default=24)
    parser.add_argument("--sets", type=int, default=42)
    parser.add_argument("--solution-size", type=int, default=6)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--lookaheads", type=int, nargs="*", default=[2, 3])
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", choices=["random", "trap"], default="trap")
    parser.add_argument("--out-prefix", default="exact_cover_step1_small")
    parser.add_argument("--skip-oracle", action="store_true")
    args = parser.parse_args()

    modes = ["greedy_L", "greedy_LG"]
    for depth in args.lookaheads:
        modes.extend([f"lookahead_L_{depth}", f"lookahead_LG_{depth}"])

    print("=== CONFIG EXACT COVER LG ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    results = []
    case_rows = []
    false_success = 0
    oracle_unsat_generated = 0

    for case_idx in range(args.cases):
        case_seed = args.seed + case_idx + 1
        universe, sets = generate_exact_cover(
            args.universe, args.sets, args.solution_size, case_seed, args.profile
        )
        oracle_sat = True if args.skip_oracle else exact_solution_exists(universe, sets, args.solution_size + 2)
        if not oracle_sat:
            oracle_unsat_generated += 1

        row = {"case": case_idx, "seed": case_seed, "oracle_sat": oracle_sat}
        for mode in modes:
            result = run_solver(universe, sets, mode, args.max_steps, args.branch_cap)
            result.case_seed = case_seed
            verified = verify_exact_cover(universe, sets, result.chosen)
            if result.success and not verified:
                false_success += 1
                result.status = "FALSE_SUCCESS"
                result.success = False
            results.append(result)
            row[f"{mode}_status"] = result.status
            row[f"{mode}_success"] = result.success
            row[f"{mode}_steps"] = result.steps
            row[f"{mode}_decision_steps"] = result.metrics.get("decision_steps", 0)
            row[f"{mode}_forced_steps"] = result.metrics.get("forced_steps", 0)
            row[f"{mode}_score_calls"] = result.metrics.get("score_calls", 0)
        case_rows.append(row)

        if (case_idx + 1) == 1 or (case_idx + 1) % 10 == 0 or (case_idx + 1) == args.cases:
            print(f"done {case_idx + 1}/{args.cases}, seed={case_seed}")

    summary_rows = summarize(results)
    summary_path = Path(f"{args.out_prefix}_summary_by_mode.csv")
    case_path = Path(f"{args.out_prefix}_summary_by_case.csv")
    logs_path = Path(f"{args.out_prefix}_logs.jsonl")

    write_csv(summary_path, summary_rows, list(summary_rows[0].keys()))
    write_csv(case_path, case_rows, list(case_rows[0].keys()))
    with logs_path.open("w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result.__dict__, ensure_ascii=False, default=list) + "\n")

    print("\n=== SUMMARY BY MODE ===")
    for row in summary_rows:
        print()
        for key, value in row.items():
            print(f"{key}: {value}")

    print("\n=== CHECKS ===")
    print(f"false_success: {false_success}")
    print(f"oracle_unsat_generated: {oracle_unsat_generated}")
    print("\n=== FILES WRITTEN ===")
    print(summary_path)
    print(case_path)
    print(logs_path)


if __name__ == "__main__":
    main()
