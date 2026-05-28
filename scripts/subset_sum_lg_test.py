#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L/G experiment for Subset Sum.

Task:
    Choose a subset of positive numbers whose sum equals target.

L:
    Current sum and distance to target.

G:
    Bound propagation:
    - if current_sum > target, conflict;
    - if current_sum + sum(remaining) < target, conflict;
    - if current_sum == target, force all remaining numbers to be excluded;
    - if current_sum + sum(remaining) == target, force all remaining numbers to be included.
"""

import argparse
import csv
import json
import random
from dataclasses import dataclass, field
from math import inf
from pathlib import Path


@dataclass
class RunResult:
    case_seed: int
    mode: str
    success: bool
    status: str
    included: set
    excluded: set
    metrics: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)


def generate_instance(n_items, max_value, subset_size, seed):
    rng = random.Random(seed)
    numbers = [rng.randint(1, max_value) for _ in range(n_items)]
    planted = set(rng.sample(range(n_items), subset_size))
    target = sum(numbers[i] for i in planted)
    return numbers, target, planted


def verify(numbers, target, included):
    return sum(numbers[i] for i in included) == target


def state_copy(state):
    return {
        "included": set(state["included"]),
        "excluded": set(state["excluded"]),
    }


def current_sum(numbers, state):
    return sum(numbers[i] for i in state["included"])


def undecided_indices(numbers, state):
    return [
        i for i in range(len(numbers))
        if i not in state["included"] and i not in state["excluded"]
    ]


def apply_action(state, action):
    kind, idx = action
    new_state = state_copy(state)
    if kind == "include":
        new_state["included"].add(idx)
        new_state["excluded"].discard(idx)
    else:
        if idx not in new_state["included"]:
            new_state["excluded"].add(idx)
    return new_state


def possible_actions(numbers, state):
    actions = []
    for i in undecided_indices(numbers, state):
        actions.append(("include", i))
        actions.append(("exclude", i))
    return actions


def propagate(numbers, target, state):
    state = state_copy(state)
    forced_count = 0

    cur = current_sum(numbers, state)
    undecided = undecided_indices(numbers, state)
    rest_sum = sum(numbers[i] for i in undecided)

    if cur > target:
        return True, state, forced_count
    if cur + rest_sum < target:
        return True, state, forced_count

    if cur == target:
        for i in undecided:
            state["excluded"].add(i)
            forced_count += 1
        return False, state, forced_count

    if cur + rest_sum == target:
        for i in undecided:
            state["included"].add(i)
            forced_count += 1
        return False, state, forced_count

    return False, state, forced_count


def score_state(numbers, target, state, use_g):
    working = state
    forced = 0
    if use_g:
        conflict, working, forced = propagate(numbers, target, state)
        if conflict:
            return 10_000_000

    cur = current_sum(numbers, working)
    undecided = undecided_indices(numbers, working)
    rest_sum = sum(numbers[i] for i in undecided)
    impossible = cur > target or cur + rest_sum < target
    return (
        (1_000_000 if impossible else 0)
        + abs(target - cur) * 10
        + len(undecided)
        - len(working["included"])
        - forced
    )


def evaluate_future(numbers, target, state, depth, use_g, branch_cap, score_counter):
    if verify(numbers, target, state["included"]):
        return -1_000_000

    base = score_state(numbers, target, state, use_g)
    score_counter[0] += 1
    if base >= 10_000_000 or depth <= 0:
        return base

    actions = possible_actions(numbers, state)
    if not actions:
        return base

    ranked = []
    for action in actions:
        next_state = apply_action(state, action)
        local = score_state(numbers, target, next_state, use_g)
        score_counter[0] += 1
        ranked.append((local, action, next_state))
    ranked.sort(key=lambda x: (x[0], x[1][0], x[1][1]))
    ranked = ranked[:branch_cap]

    best = inf
    for _, _, next_state in ranked:
        future = evaluate_future(
            numbers, target, next_state, depth - 1, use_g, branch_cap, score_counter
        )
        if future < best:
            best = future
    return best


def search(numbers, target, case_seed, mode, use_g, depth, max_steps, branch_cap):
    state = {"included": set(), "excluded": set()}
    decision_steps = 0
    forced_steps = 0
    score_counter = [0]
    logs = [f"START {mode}: use_g={use_g}, depth={depth}, target={target}"]

    for step in range(1, max_steps + 1):
        if verify(numbers, target, state["included"]):
            return RunResult(
                case_seed, mode, True, "SOLUTION_FOUND",
                set(state["included"]), set(state["excluded"]),
                {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_counter[0]},
                logs,
            )

        actions = possible_actions(numbers, state)
        if not actions:
            break

        ranked = []
        for action in actions:
            next_state = apply_action(state, action)
            score = evaluate_future(numbers, target, next_state, depth - 1, use_g, branch_cap, score_counter)
            ranked.append((score, action, next_state))
        ranked.sort(key=lambda x: (x[0], x[1][0], x[1][1]))
        best_score, action, next_state = ranked[0]

        if use_g:
            conflict, next_state, forced = propagate(numbers, target, next_state)
            if conflict:
                forced = 0
        else:
            forced = 0

        state = next_state
        decision_steps += 1
        forced_steps += forced
        logs.append(
            f"step={step}: action={action}, score={best_score}, "
            f"sum={current_sum(numbers, state)}, forced={forced}, undecided={len(undecided_indices(numbers, state))}"
        )

        if current_sum(numbers, state) > target:
            break

    success = verify(numbers, target, state["included"])
    return RunResult(
        case_seed, mode, success, "SOLUTION_FOUND" if success else "FAILED_TO_FIND",
        set(state["included"]), set(state["excluded"]),
        {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_counter[0]},
        logs,
    )


def save_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def summarize(results):
    rows = []
    for mode in sorted({r.mode for r in results}):
        items = [r for r in results if r.mode == mode]
        total = len(items)
        success = sum(1 for r in items if r.success)
        rows.append({
            "mode": mode,
            "total": total,
            "success": success,
            "fail": total - success,
            "success_rate": success / total if total else 0,
            "avg_decision_steps": sum(r.metrics["decision_steps"] for r in items) / total if total else "",
            "avg_forced_steps": sum(r.metrics["forced_steps"] for r in items) / total if total else "",
            "avg_score_calls": sum(r.metrics["score_calls"] for r in items) / total if total else "",
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=40)
    parser.add_argument("--items", type=int, default=18)
    parser.add_argument("--max-value", type=int, default=50)
    parser.add_argument("--subset-size", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--out-prefix", default="subset_sum_lg")
    args = parser.parse_args()

    results = []
    case_rows = []

    for i in range(args.cases):
        case_seed = args.seed + i
        numbers, target, planted = generate_instance(
            args.items, args.max_value, args.subset_size, case_seed
        )
        modes = [
            ("greedy_L", False, 1),
            ("greedy_LG", True, 1),
            ("lookahead_L_2", False, 2),
            ("lookahead_LG_2", True, 2),
            ("lookahead_L_3", False, 3),
            ("lookahead_LG_3", True, 3),
        ]
        for mode, use_g, depth in modes:
            result = search(numbers, target, case_seed, mode, use_g, depth, args.max_steps, args.branch_cap)
            results.append(result)
            case_rows.append({
                "case_seed": case_seed,
                "mode": mode,
                "status": result.status,
                "success": result.success,
                "direct_verified": verify(numbers, target, result.included),
                "included_count": len(result.included),
                "included_sum": sum(numbers[i] for i in result.included),
                "target": target,
                "decision_steps": result.metrics["decision_steps"],
                "forced_steps": result.metrics["forced_steps"],
                "score_calls": result.metrics["score_calls"],
                "planted": " ".join(str(x) for x in sorted(planted)),
            })

    summary = summarize(results)
    save_csv(Path(args.out_prefix + "_summary_by_mode.csv"), summary)
    save_csv(Path(args.out_prefix + "_summary_by_case.csv"), case_rows)

    with open(args.out_prefix + "_logs.jsonl", "w", encoding="utf-8") as f:
        for result in results[:20]:
            f.write(json.dumps({
                "case_seed": result.case_seed,
                "mode": result.mode,
                "status": result.status,
                "success": result.success,
                "included": sorted(result.included),
                "metrics": result.metrics,
                "logs": result.logs,
            }, ensure_ascii=False) + "\n")

    print("=== SUBSET SUM L/G SUMMARY ===")
    for row in summary:
        print(row)
    print("Files written:")
    print(args.out_prefix + "_summary_by_mode.csv")
    print(args.out_prefix + "_summary_by_case.csv")
    print(args.out_prefix + "_logs.jsonl")


if __name__ == "__main__":
    main()
