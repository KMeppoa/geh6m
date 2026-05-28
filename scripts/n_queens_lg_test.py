#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L/G experiment for N-Queens.

Task:
    Place N queens on an N x N board so no queens attack each other.

L:
    Current placed queens and available columns in the next row.

G:
    Propagation over future rows:
    - if a future row has no legal columns, conflict;
    - if a future row has exactly one legal column, force that queen.
"""

import argparse
import csv
import json
from dataclasses import dataclass, field
from math import inf
from pathlib import Path


@dataclass
class RunResult:
    n: int
    mode: str
    success: bool
    status: str
    queens: dict
    metrics: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)


def attacks(row1, col1, row2, col2):
    return col1 == col2 or abs(row1 - row2) == abs(col1 - col2)


def legal_cols(n, queens, row):
    cols = []
    for col in range(n):
        ok = True
        for r, c in queens.items():
            if attacks(r, c, row, col):
                ok = False
                break
        if ok:
            cols.append(col)
    return cols


def verify(n, queens):
    if len(queens) != n:
        return False
    for r1, c1 in queens.items():
        for r2, c2 in queens.items():
            if r1 < r2 and attacks(r1, c1, r2, c2):
                return False
    return True


def next_unfilled_row(n, queens):
    for row in range(n):
        if row not in queens:
            return row
    return None


def propagate(n, queens):
    queens = dict(queens)
    forced_count = 0

    while True:
        changed = False
        for row in range(n):
            if row in queens:
                continue
            cols = legal_cols(n, queens, row)
            if not cols:
                return True, queens, forced_count
            if len(cols) == 1:
                queens[row] = cols[0]
                forced_count += 1
                changed = True
                break
        if not changed:
            return False, queens, forced_count


def score_state(n, queens, use_g):
    working = queens
    forced = 0
    if use_g:
        conflict, working, forced = propagate(n, queens)
        if conflict:
            return 10_000_000

    open_rows = 0
    total_options = 0
    min_options = n
    for row in range(n):
        if row in working:
            continue
        cols = legal_cols(n, working, row)
        if not cols:
            return 10_000_000
        open_rows += 1
        total_options += len(cols)
        min_options = min(min_options, len(cols))

    return open_rows * 100 + total_options - len(working) * 10 - forced * 5 + min_options


def possible_actions(n, queens):
    row = next_unfilled_row(n, queens)
    if row is None:
        return []
    return [(row, col) for col in legal_cols(n, queens, row)]


def apply_action(queens, action):
    row, col = action
    new_queens = dict(queens)
    new_queens[row] = col
    return new_queens


def evaluate_future(n, queens, depth, use_g, branch_cap, score_counter):
    if verify(n, queens):
        return -1_000_000

    base = score_state(n, queens, use_g)
    score_counter[0] += 1
    if base >= 10_000_000 or depth <= 0:
        return base

    actions = possible_actions(n, queens)
    if not actions:
        return base

    ranked = []
    for action in actions:
        next_queens = apply_action(queens, action)
        local = score_state(n, next_queens, use_g)
        score_counter[0] += 1
        ranked.append((local, action, next_queens))
    ranked.sort(key=lambda x: (x[0], x[1][0], x[1][1]))
    ranked = ranked[:branch_cap]

    best = inf
    for _, _, next_queens in ranked:
        future = evaluate_future(n, next_queens, depth - 1, use_g, branch_cap, score_counter)
        if future < best:
            best = future
    return best


def search(n, mode, use_g, depth, max_steps, branch_cap):
    queens = {}
    decision_steps = 0
    forced_steps = 0
    score_counter = [0]
    logs = [f"START {mode}: n={n}, use_g={use_g}, depth={depth}"]

    for step in range(1, max_steps + 1):
        if verify(n, queens):
            return RunResult(
                n, mode, True, "SOLUTION_FOUND", queens,
                {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_counter[0]},
                logs,
            )

        actions = possible_actions(n, queens)
        if not actions:
            break

        ranked = []
        for action in actions:
            next_queens = apply_action(queens, action)
            score = evaluate_future(n, next_queens, depth - 1, use_g, branch_cap, score_counter)
            ranked.append((score, action, next_queens))
        ranked.sort(key=lambda x: (x[0], x[1][0], x[1][1]))
        best_score, action, next_queens = ranked[0]

        if use_g:
            conflict, next_queens, forced = propagate(n, next_queens)
            if conflict:
                forced = 0
        else:
            forced = 0

        queens = next_queens
        decision_steps += 1
        forced_steps += forced
        logs.append(f"step={step}: action={action}, score={best_score}, placed={len(queens)}, forced={forced}")

    success = verify(n, queens)
    return RunResult(
        n, mode, success, "SOLUTION_FOUND" if success else "FAILED_TO_FIND", queens,
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
    parser.add_argument("--min-n", type=int, default=8)
    parser.add_argument("--max-n", type=int, default=16)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--dynamic-lg", action="store_true")
    parser.add_argument("--max-lg-depth", type=int, default=8)
    parser.add_argument("--out-prefix", default="n_queens_lg")
    args = parser.parse_args()

    results = []
    case_rows = []
    for n in range(args.min_n, args.max_n + 1):
        if args.dynamic_lg:
            modes = [
                (f"lookahead_LG_{depth}", True, depth)
                for depth in range(1, args.max_lg_depth + 1)
            ]
        else:
            modes = [
                ("greedy_L", False, 1),
                ("greedy_LG", True, 1),
                ("lookahead_L_2", False, 2),
                ("lookahead_LG_2", True, 2),
                ("lookahead_L_3", False, 3),
                ("lookahead_LG_3", True, 3),
            ]
        for mode, use_g, depth in modes:
            result = search(n, mode, use_g, depth, args.max_steps, args.branch_cap)
            results.append(result)
            case_rows.append({
                "n": n,
                "mode": mode,
                "status": result.status,
                "success": result.success,
                "direct_verified": verify(n, result.queens),
                "placed": len(result.queens),
                "decision_steps": result.metrics["decision_steps"],
                "forced_steps": result.metrics["forced_steps"],
                "score_calls": result.metrics["score_calls"],
            })

    summary = summarize(results)
    save_csv(Path(args.out_prefix + "_summary_by_mode.csv"), summary)
    save_csv(Path(args.out_prefix + "_summary_by_case.csv"), case_rows)

    if args.dynamic_lg:
        by_depth = {}
        for row in case_rows:
            depth = int(row["mode"].rsplit("_", 1)[1])
            by_depth.setdefault(depth, []).append(row)

        curve_rows = []
        for depth in sorted(by_depth):
            items = by_depth[depth]
            total = len(items)
            success = sum(1 for row in items if str(row["success"]).lower() == "true")
            curve_rows.append({
                "depth": depth,
                "total": total,
                "success": success,
                "fail": total - success,
                "success_rate": success / total if total else 0,
            })
        save_csv(Path(args.out_prefix + "_lg_depth_curve.csv"), curve_rows)

        transition_rows = []
        for depth in range(1, args.max_lg_depth):
            current = {row["n"]: row for row in by_depth.get(depth, [])}
            nxt = {row["n"]: row for row in by_depth.get(depth + 1, [])}
            fixed = broken = stayed_success = stayed_fail = 0
            for n in range(args.min_n, args.max_n + 1):
                if n not in current or n not in nxt:
                    continue
                cur_success = str(current[n]["success"]).lower() == "true"
                next_success = str(nxt[n]["success"]).lower() == "true"
                if not cur_success and next_success:
                    fixed += 1
                elif cur_success and not next_success:
                    broken += 1
                elif cur_success and next_success:
                    stayed_success += 1
                else:
                    stayed_fail += 1
            transition_rows.append({
                "from_depth": depth,
                "to_depth": depth + 1,
                "fixed_by_next": fixed,
                "broken_by_next": broken,
                "stayed_success": stayed_success,
                "stayed_fail": stayed_fail,
                "net_gain": fixed - broken,
            })
        save_csv(Path(args.out_prefix + "_lg_depth_transitions.csv"), transition_rows)

        first_rows = []
        for n in range(args.min_n, args.max_n + 1):
            first_depth = ""
            for depth in sorted(by_depth):
                row = next((x for x in by_depth[depth] if x["n"] == n), None)
                if row and str(row["success"]).lower() == "true":
                    first_depth = depth
                    break
            first_rows.append({
                "n": n,
                "first_success_depth": first_depth,
                "solved_within_limit": first_depth != "",
            })
        save_csv(Path(args.out_prefix + "_lg_first_success_by_n.csv"), first_rows)

    with open(args.out_prefix + "_logs.jsonl", "w", encoding="utf-8") as f:
        for result in results[:20]:
            f.write(json.dumps({
                "n": result.n,
                "mode": result.mode,
                "status": result.status,
                "success": result.success,
                "queens": result.queens,
                "metrics": result.metrics,
                "logs": result.logs,
            }, ensure_ascii=False) + "\n")

    print("=== N-QUEENS L/G SUMMARY ===")
    for row in summary:
        print(row)
    print("Files written:")
    print(args.out_prefix + "_summary_by_mode.csv")
    print(args.out_prefix + "_summary_by_case.csv")
    print(args.out_prefix + "_logs.jsonl")


if __name__ == "__main__":
    main()
