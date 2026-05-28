#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L/G experiment for Partial Latin Square completion.

Task:
    Fill an n x n grid with symbols 0..n-1 so every row and column contains
    each symbol exactly once, while respecting given cells.

L:
    Local score: empty cells, conflicts, candidate counts.

G:
    Global propagation:
        - if a cell has no candidate, the branch is dead;
        - if a cell has one candidate, force it;
        - if a symbol has only one possible cell in a row/column, force it.
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
    status: str
    success: bool
    steps: int
    grid: list
    metrics: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)


def planted_square(n, seed):
    rng = random.Random(seed)
    symbols = list(range(n))
    rng.shuffle(symbols)
    row_shift = list(range(n))
    col_shift = list(range(n))
    rng.shuffle(row_shift)
    rng.shuffle(col_shift)
    grid = [[symbols[(row_shift[r] + col_shift[c]) % n] for c in range(n)] for r in range(n)]
    return grid


def make_partial(n, givens, seed):
    full = planted_square(n, seed)
    rng = random.Random(seed + 100000)
    cells = [(r, c) for r in range(n) for c in range(n)]
    rng.shuffle(cells)
    keep = set(cells[:givens])
    grid = [[full[r][c] if (r, c) in keep else None for c in range(n)] for r in range(n)]
    return grid


def clone_grid(grid):
    return [row[:] for row in grid]


def verify_grid(grid):
    n = len(grid)
    target = set(range(n))
    for r in range(n):
        if set(grid[r]) != target:
            return False
    for c in range(n):
        if {grid[r][c] for r in range(n)} != target:
            return False
    return True


def conflicts(grid):
    n = len(grid)
    bad = 0
    for r in range(n):
        values = [v for v in grid[r] if v is not None]
        bad += len(values) - len(set(values))
    for c in range(n):
        values = [grid[r][c] for r in range(n) if grid[r][c] is not None]
        bad += len(values) - len(set(values))
    return bad


def candidates(grid, r, c):
    if grid[r][c] is not None:
        return []
    n = len(grid)
    used = {grid[r][x] for x in range(n) if grid[r][x] is not None}
    used |= {grid[x][c] for x in range(n) if grid[x][c] is not None}
    return [v for v in range(n) if v not in used]


def stats(grid):
    n = len(grid)
    empty = 0
    no_candidate = 0
    forced_cells = 0
    pressure = 0
    for r in range(n):
        for c in range(n):
            if grid[r][c] is None:
                empty += 1
                cand = candidates(grid, r, c)
                if not cand:
                    no_candidate += 1
                elif len(cand) == 1:
                    forced_cells += 1
                pressure += n - len(cand)
    return {
        "empty": empty,
        "filled": n * n - empty,
        "conflicts": conflicts(grid),
        "no_candidate": no_candidate,
        "forced_cells": forced_cells,
        "pressure": pressure,
    }


def set_cell(grid, r, c, value):
    new_grid = clone_grid(grid)
    new_grid[r][c] = value
    return new_grid


def propagate(grid, max_forced=10000):
    grid = clone_grid(grid)
    forced_count = 0
    n = len(grid)

    while forced_count < max_forced:
        st = stats(grid)
        if st["conflicts"] or st["no_candidate"]:
            return True, grid, forced_count
        if st["empty"] == 0:
            return False, grid, forced_count

        forced = None
        for r in range(n):
            for c in range(n):
                cand = candidates(grid, r, c)
                if grid[r][c] is None and len(cand) == 1:
                    forced = (r, c, cand[0])
                    break
            if forced:
                break

        if forced is None:
            for r in range(n):
                missing = [v for v in range(n) if v not in grid[r]]
                for v in missing:
                    places = [(r, c, v) for c in range(n) if grid[r][c] is None and v in candidates(grid, r, c)]
                    if len(places) == 1:
                        forced = places[0]
                        break
                if forced:
                    break

        if forced is None:
            for c in range(n):
                col = [grid[r][c] for r in range(n)]
                missing = [v for v in range(n) if v not in col]
                for v in missing:
                    places = [(r, c, v) for r in range(n) if grid[r][c] is None and v in candidates(grid, r, c)]
                    if len(places) == 1:
                        forced = places[0]
                        break
                if forced:
                    break

        if forced is None:
            return False, grid, forced_count
        r, c, v = forced
        grid[r][c] = v
        forced_count += 1

    return False, grid, forced_count


def score_l(grid):
    st = stats(grid)
    return st["conflicts"] * 1_000_000 + st["no_candidate"] * 500_000 + st["empty"] * 100 + st["pressure"] - st["filled"]


def score_lg(grid):
    conflict, propagated, forced_count = propagate(grid)
    if conflict:
        return 10_000_000
    st = stats(propagated)
    return st["empty"] * 100 + st["pressure"] - st["filled"] * 2 - forced_count * 20


def possible_actions(grid):
    n = len(grid)
    actions = []
    for r in range(n):
        for c in range(n):
            if grid[r][c] is None:
                for v in candidates(grid, r, c):
                    actions.append((r, c, v))
    return actions


def evaluate_future(grid, depth, score_kind, branch_cap, score_counter):
    if verify_grid(grid):
        return -1_000_000
    base_score = score_lg(grid) if score_kind == "LG" else score_l(grid)
    score_counter[0] += 1
    if base_score >= 10_000_000 or depth <= 0:
        return base_score

    ranked = []
    for action in possible_actions(grid):
        r, c, v = action
        new_grid = set_cell(grid, r, c, v)
        local_score = score_lg(new_grid) if score_kind == "LG" else score_l(new_grid)
        score_counter[0] += 1
        ranked.append((local_score, action, new_grid))
    ranked.sort(key=lambda x: (x[0], x[1]))

    best = inf
    for _, _, new_grid in ranked[:branch_cap]:
        best = min(best, evaluate_future(new_grid, depth - 1, score_kind, branch_cap, score_counter))
    return best


def run_solver(grid, mode, max_steps, branch_cap):
    grid = clone_grid(grid)
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
            conflict, propagated, forced = propagate(grid)
            forced_steps += forced
            grid = propagated
            if conflict:
                return RunResult(0, mode, "FAILED_TO_FIND", False, step, grid, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)

        if verify_grid(grid):
            return RunResult(0, mode, "SAT_FOUND", True, step, grid, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)

        actions = possible_actions(grid)
        if not actions:
            break

        ranked = []
        for action in actions:
            r, c, v = action
            new_grid = set_cell(grid, r, c, v)
            counter = [0]
            future = evaluate_future(new_grid, depth - 1, score_kind, branch_cap, counter)
            score_calls += counter[0]
            ranked.append((future, action))
        ranked.sort(key=lambda x: (x[0], x[1]))
        _, action = ranked[0]
        r, c, v = action
        grid[r][c] = v
        decision_steps += 1
        logs.append({"step": step, "action": action, "score": ranked[0][0]})

    return RunResult(0, mode, "FAILED_TO_FIND", False, max_steps, grid, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)


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
    parser.add_argument("--n", type=int, default=7)
    parser.add_argument("--givens", type=int, default=18)
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--lookaheads", type=int, nargs="*", default=[2, 3])
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="latin_square_step1_small")
    args = parser.parse_args()

    modes = ["greedy_L", "greedy_LG"]
    for depth in args.lookaheads:
        modes.extend([f"lookahead_L_{depth}", f"lookahead_LG_{depth}"])

    print("=== CONFIG LATIN SQUARE LG ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    results = []
    case_rows = []
    false_success = 0

    for case_idx in range(args.cases):
        case_seed = args.seed + case_idx + 1
        grid = make_partial(args.n, args.givens, case_seed)
        row = {"case": case_idx, "seed": case_seed}
        for mode in modes:
            result = run_solver(grid, mode, args.max_steps, args.branch_cap)
            result.case_seed = case_seed
            verified = verify_grid(result.grid)
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
            f.write(json.dumps(result.__dict__, ensure_ascii=False) + "\n")

    print("\n=== SUMMARY BY MODE ===")
    for row in summary_rows:
        print()
        for key, value in row.items():
            print(f"{key}: {value}")
    print("\n=== CHECKS ===")
    print(f"false_success: {false_success}")
    print("\n=== FILES WRITTEN ===")
    print(summary_path)
    print(case_path)
    print(logs_path)


if __name__ == "__main__":
    main()
