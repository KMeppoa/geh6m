#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L/G experiment for Set Cover.

Task:
    Choose at most k sets so every universe element is covered.

L:
    Local score: how many elements are still uncovered and how many sets were used.

G:
    Global propagation:
        - if an uncovered element can be covered by only one remaining set, force it;
        - if no remaining set can cover an uncovered element, the branch is dead;
        - if even the best remaining sets cannot fit into k, the branch is dead.
"""

import argparse
import csv
import json
import random
from dataclasses import dataclass, field
from itertools import combinations
from math import ceil, inf
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


def generate_set_cover(universe_size, n_sets, k, seed, profile):
    rng = random.Random(seed)
    universe = set(range(universe_size))
    sets = []

    if profile == "trap":
        rare = list(range(k))
        common = list(range(k, universe_size))
        rng.shuffle(common)
        chunks = [[] for _ in range(k)]
        for idx, element in enumerate(common):
            chunks[idx % k].append(element)

        # The planted solution needs exactly k sets. Each set covers one rare
        # element plus a chunk of common elements.
        for i in range(k):
            sets.append({rare[i]} | set(chunks[i]))

        # Bait sets cover many common elements but no rare elements. A local
        # greedy method likes them, but they do not help finish within k.
        while len(sets) < max(k + 1, n_sets // 2):
            size = rng.randint(max(1, len(common) // 2), max(1, len(common) - 1))
            sets.append(set(rng.sample(common, size)))

        # Noise sets cover small mixed fragments. They make the instance less
        # deterministic without destroying the planted structure.
        while len(sets) < n_sets:
            size = rng.randint(1, max(2, universe_size // 5))
            pool = rare + common
            sets.append(set(rng.sample(pool, size)))

        rng.shuffle(sets)
        return universe, sets

    shuffled = list(universe)
    rng.shuffle(shuffled)
    chunks = [[] for _ in range(k)]
    for idx, element in enumerate(shuffled):
        chunks[idx % k].append(element)

    for chunk in chunks:
        extra = rng.sample(list(universe), rng.randint(0, max(1, universe_size // 5)))
        sets.append(set(chunk) | set(extra))

    while len(sets) < n_sets:
        size = rng.randint(1, max(2, universe_size // 3))
        sets.append(set(rng.sample(list(universe), size)))

    rng.shuffle(sets)
    return universe, sets


def verify_cover(universe, sets, chosen, k):
    if len(chosen) > k:
        return False
    covered = set()
    for idx in chosen:
        if idx < 0 or idx >= len(sets):
            return False
        covered |= sets[idx]
    return universe <= covered


def exact_cover_exists(universe, sets, k):
    indices = range(len(sets))
    for r in range(k + 1):
        for combo in combinations(indices, r):
            if verify_cover(universe, sets, combo, k):
                return True
    return False


def covered_by(sets, chosen):
    covered = set()
    for idx in chosen:
        covered |= sets[idx]
    return covered


def remaining_indices(sets, chosen):
    chosen_set = set(chosen)
    return [i for i in range(len(sets)) if i not in chosen_set]


def stats(universe, sets, chosen, k):
    covered = covered_by(sets, chosen)
    uncovered = universe - covered
    remaining = remaining_indices(sets, chosen)
    max_gain = 0
    dead_elements = 0
    forced_elements = 0
    pressure = 0

    for element in uncovered:
        carriers = [i for i in remaining if element in sets[i]]
        if not carriers:
            dead_elements += 1
        elif len(carriers) == 1:
            forced_elements += 1
        pressure += max(0, 5 - len(carriers))

    for idx in remaining:
        max_gain = max(max_gain, len(sets[idx] & uncovered))

    lower_bound = ceil(len(uncovered) / max_gain) if uncovered and max_gain else 0
    return {
        "covered": len(covered),
        "uncovered": len(uncovered),
        "chosen": len(chosen),
        "remaining": len(remaining),
        "dead_elements": dead_elements,
        "forced_elements": forced_elements,
        "pressure": pressure,
        "lower_bound": lower_bound,
        "over_k": max(0, len(chosen) - k),
    }


def propagate(universe, sets, chosen, k, max_forced=10000):
    chosen = list(chosen)
    forced_count = 0

    while forced_count < max_forced:
        st = stats(universe, sets, chosen, k)
        if st["over_k"] or st["dead_elements"]:
            return True, chosen, forced_count
        if st["uncovered"] == 0:
            return False, chosen, forced_count
        if len(chosen) + st["lower_bound"] > k:
            return True, chosen, forced_count

        covered = covered_by(sets, chosen)
        uncovered = universe - covered
        remaining = remaining_indices(sets, chosen)
        forced = None
        for element in sorted(uncovered):
            carriers = [i for i in remaining if element in sets[i]]
            if len(carriers) == 1:
                forced = carriers[0]
                break

        if forced is None:
            return False, chosen, forced_count
        chosen.append(forced)
        forced_count += 1

    return False, chosen, forced_count


def score_l(universe, sets, chosen, k):
    st = stats(universe, sets, chosen, k)
    return (
        st["over_k"] * 10_000_000
        + st["dead_elements"] * 1_000_000
        + st["uncovered"] * 100
        + st["chosen"] * 15
        + st["pressure"]
        - st["covered"]
    )


def score_lg(universe, sets, chosen, k):
    conflict, propagated, forced_count = propagate(universe, sets, chosen, k)
    if conflict:
        return 10_000_000
    st = stats(universe, sets, propagated, k)
    return (
        st["uncovered"] * 100
        + st["chosen"] * 15
        + st["pressure"]
        - st["covered"] * 2
        - forced_count * 25
    )


def possible_actions(universe, sets, chosen, k):
    if len(chosen) >= k:
        return []
    covered = covered_by(sets, chosen)
    uncovered = universe - covered
    actions = []
    chosen_set = set(chosen)
    for idx, s in enumerate(sets):
        if idx in chosen_set:
            continue
        gain = len(s & uncovered)
        if gain > 0:
            actions.append(idx)
    return actions


def evaluate_future(universe, sets, chosen, k, depth, score_kind, branch_cap, score_counter):
    if verify_cover(universe, sets, chosen, k):
        return -1_000_000

    base_score = score_lg(universe, sets, chosen, k) if score_kind == "LG" else score_l(universe, sets, chosen, k)
    score_counter[0] += 1
    if base_score >= 10_000_000 or depth <= 0:
        return base_score

    ranked = []
    for action in possible_actions(universe, sets, chosen, k):
        new_chosen = chosen + [action]
        local_score = score_lg(universe, sets, new_chosen, k) if score_kind == "LG" else score_l(universe, sets, new_chosen, k)
        score_counter[0] += 1
        ranked.append((local_score, action, new_chosen))

    ranked.sort(key=lambda x: (x[0], x[1]))
    best = inf
    for _, _, new_chosen in ranked[:branch_cap]:
        best = min(
            best,
            evaluate_future(
                universe, sets, new_chosen, k, depth - 1, score_kind, branch_cap, score_counter
            ),
        )
    return best


def run_solver(universe, sets, k, mode, max_steps, branch_cap):
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
            conflict, propagated, forced = propagate(universe, sets, chosen, k)
            forced_steps += forced
            chosen = propagated
            if conflict:
                return RunResult(0, mode, "FAILED_TO_FIND", False, step, chosen, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)

        if verify_cover(universe, sets, chosen, k):
            return RunResult(0, mode, "SAT_FOUND", True, step, chosen, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)

        actions = possible_actions(universe, sets, chosen, k)
        if not actions:
            break

        ranked = []
        for action in actions:
            new_chosen = chosen + [action]
            counter = [0]
            future = evaluate_future(universe, sets, new_chosen, k, depth - 1, score_kind, branch_cap, counter)
            score_calls += counter[0]
            ranked.append((future, action))

        ranked.sort(key=lambda x: (x[0], x[1]))
        chosen.append(ranked[0][1])
        decision_steps += 1
        logs.append({"step": step, "chosen_set": ranked[0][1], "score": ranked[0][0]})

    return RunResult(0, mode, "FAILED_TO_FIND", False, max_steps, chosen, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)


def summarize(results):
    modes = sorted({r.mode for r in results})
    rows = []
    for mode in modes:
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
    parser.add_argument("--sets", type=int, default=36)
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--lookaheads", type=int, nargs="*", default=[2, 3])
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="set_cover_step1_small")
    parser.add_argument("--profile", choices=["random", "trap"], default="random")
    parser.add_argument("--skip-oracle", action="store_true")
    args = parser.parse_args()

    modes = ["greedy_L", "greedy_LG"]
    for depth in args.lookaheads:
        modes.extend([f"lookahead_L_{depth}", f"lookahead_LG_{depth}"])

    print("=== CONFIG SET COVER LG ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    results = []
    case_rows = []
    false_success = 0
    oracle_errors = 0

    for case_idx in range(args.cases):
        case_seed = args.seed + case_idx + 1
        universe, sets = generate_set_cover(args.universe, args.sets, args.k, case_seed, args.profile)
        oracle_sat = True if args.skip_oracle else exact_cover_exists(universe, sets, args.k)
        if not oracle_sat:
            oracle_errors += 1

        row = {"case": case_idx, "seed": case_seed, "oracle_sat": oracle_sat}
        for mode in modes:
            result = run_solver(universe, sets, args.k, mode, args.max_steps, args.branch_cap)
            result.case_seed = case_seed
            verified = verify_cover(universe, sets, result.chosen, args.k)
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
    print(f"oracle_unsat_generated: {oracle_errors}")
    print("\n=== FILES WRITTEN ===")
    print(summary_path)
    print(case_path)
    print(logs_path)


if __name__ == "__main__":
    main()
