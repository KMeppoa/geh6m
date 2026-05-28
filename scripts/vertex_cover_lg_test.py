#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L/G experiment for Vertex Cover decision.

Task:
    Select at most k vertices so every edge is covered.

L:
    Local covered/uncovered edge counts.

G:
    Forced consequences:
    - If an uncovered edge has only one selectable endpoint left, select it.
    - If selected_count > k, conflict.
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
    graph_seed: int
    mode: str
    success: bool
    status: str
    selected: set
    forbidden: set
    metrics: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)


def generate_planted_vertex_cover(n_vertices, edge_prob, cover_size, seed):
    rng = random.Random(seed)
    cover = set(rng.sample(range(n_vertices), cover_size))
    non_cover = set(range(n_vertices)) - cover
    edges = set()

    for i in range(n_vertices):
        for j in range(i + 1, n_vertices):
            if i in non_cover and j in non_cover:
                continue
            if rng.random() < edge_prob:
                edges.add((i, j))

    return edges, cover


def verify_cover(edges, selected, cover_size):
    if len(selected) > cover_size:
        return False
    return all(a in selected or b in selected for a, b in edges)


def uncovered_edges(edges, selected):
    return [(a, b) for a, b in edges if a not in selected and b not in selected]


def state_copy(state):
    return {
        "selected": set(state["selected"]),
        "forbidden": set(state["forbidden"]),
    }


def apply_action(state, action):
    kind, vertex = action
    new_state = state_copy(state)
    if kind == "select":
        new_state["selected"].add(vertex)
        new_state["forbidden"].discard(vertex)
    else:
        if vertex not in new_state["selected"]:
            new_state["forbidden"].add(vertex)
    return new_state


def possible_actions(n_vertices, state):
    actions = []
    for v in range(n_vertices):
        if v in state["selected"] or v in state["forbidden"]:
            continue
        actions.append(("select", v))
        actions.append(("forbid", v))
    return actions


def propagate(edges, state, cover_size):
    state = state_copy(state)
    forced_count = 0

    while True:
        if len(state["selected"]) > cover_size:
            return True, state, forced_count

        changed = False
        for a, b in uncovered_edges(edges, state["selected"]):
            a_possible = a not in state["forbidden"]
            b_possible = b not in state["forbidden"]

            if not a_possible and not b_possible:
                return True, state, forced_count

            if a_possible and not b_possible:
                state["selected"].add(a)
                forced_count += 1
                changed = True
                break

            if b_possible and not a_possible:
                state["selected"].add(b)
                forced_count += 1
                changed = True
                break

        if not changed:
            return False, state, forced_count


def stats(edges, state, cover_size):
    uncov = len(uncovered_edges(edges, state["selected"]))
    return {
        "selected": len(state["selected"]),
        "forbidden": len(state["forbidden"]),
        "uncovered": uncov,
        "over_limit": len(state["selected"]) > cover_size,
    }


def score_state(edges, state, cover_size, use_g):
    working = state
    forced = 0
    if use_g:
        conflict, working, forced = propagate(edges, state, cover_size)
        if conflict:
            return 10_000_000
    st = stats(edges, working, cover_size)
    return (
        (1_000_000 if st["over_limit"] else 0)
        + st["uncovered"] * 100
        + st["selected"] * 10
        + st["forbidden"]
        - forced
    )


def evaluate_future(edges, state, n_vertices, cover_size, depth, use_g, branch_cap, score_counter):
    if verify_cover(edges, state["selected"], cover_size):
        return -1_000_000

    base = score_state(edges, state, cover_size, use_g)
    score_counter[0] += 1
    if base >= 10_000_000 or depth <= 0:
        return base

    actions = possible_actions(n_vertices, state)
    if not actions:
        return base

    ranked = []
    for action in actions:
        next_state = apply_action(state, action)
        local = score_state(edges, next_state, cover_size, use_g)
        score_counter[0] += 1
        ranked.append((local, action, next_state))
    ranked.sort(key=lambda x: (x[0], x[1][0], x[1][1]))
    ranked = ranked[:branch_cap]

    best = inf
    for _, _, next_state in ranked:
        future = evaluate_future(
            edges, next_state, n_vertices, cover_size,
            depth - 1, use_g, branch_cap, score_counter,
        )
        if future < best:
            best = future
    return best


def search(edges, n_vertices, cover_size, graph_seed, mode, use_g, depth, max_steps, branch_cap):
    state = {"selected": set(), "forbidden": set()}
    decision_steps = 0
    forced_steps = 0
    score_counter = [0]
    logs = [f"START {mode}: use_g={use_g}, depth={depth}"]

    for step in range(1, max_steps + 1):
        if verify_cover(edges, state["selected"], cover_size):
            return RunResult(
                graph_seed, mode, True, "SOLUTION_FOUND",
                set(state["selected"]), set(state["forbidden"]),
                {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_counter[0]},
                logs,
            )

        actions = possible_actions(n_vertices, state)
        if not actions:
            break

        ranked = []
        for action in actions:
            next_state = apply_action(state, action)
            score = evaluate_future(
                edges, next_state, n_vertices, cover_size,
                depth - 1, use_g, branch_cap, score_counter,
            )
            ranked.append((score, action, next_state))
        ranked.sort(key=lambda x: (x[0], x[1][0], x[1][1]))
        best_score, action, next_state = ranked[0]

        if use_g:
            conflict, next_state, forced = propagate(edges, next_state, cover_size)
            if conflict:
                forced = 0
        else:
            forced = 0

        state = next_state
        decision_steps += 1
        forced_steps += forced
        logs.append(f"step={step}: action={action}, score={best_score}, forced={forced}, stats={stats(edges, state, cover_size)}")

        st = stats(edges, state, cover_size)
        if st["over_limit"]:
            break

    success = verify_cover(edges, state["selected"], cover_size)
    return RunResult(
        graph_seed, mode, success, "SOLUTION_FOUND" if success else "FAILED_TO_FIND",
        set(state["selected"]), set(state["forbidden"]),
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
    parser.add_argument("--graphs", type=int, default=30)
    parser.add_argument("--vertices", type=int, default=18)
    parser.add_argument("--cover-size", type=int, default=6)
    parser.add_argument("--edge-prob", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--out-prefix", default="vertex_cover_lg")
    args = parser.parse_args()

    results = []
    case_rows = []

    for i in range(args.graphs):
        graph_seed = args.seed + i
        edges, planted = generate_planted_vertex_cover(
            args.vertices, args.edge_prob, args.cover_size, graph_seed
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
            result = search(
                edges, args.vertices, args.cover_size, graph_seed,
                mode, use_g, depth, args.max_steps, args.branch_cap,
            )
            results.append(result)
            case_rows.append({
                "graph_seed": graph_seed,
                "mode": mode,
                "status": result.status,
                "success": result.success,
                "direct_verified": verify_cover(edges, result.selected, args.cover_size),
                "selected_count": len(result.selected),
                "forbidden_count": len(result.forbidden),
                "decision_steps": result.metrics["decision_steps"],
                "forced_steps": result.metrics["forced_steps"],
                "score_calls": result.metrics["score_calls"],
                "edge_count": len(edges),
                "planted_cover": " ".join(str(x) for x in sorted(planted)),
            })

    summary = summarize(results)
    save_csv(Path(args.out_prefix + "_summary_by_mode.csv"), summary)
    save_csv(Path(args.out_prefix + "_summary_by_case.csv"), case_rows)
    with open(args.out_prefix + "_logs.jsonl", "w", encoding="utf-8") as f:
        for result in results[:20]:
            f.write(json.dumps({
                "graph_seed": result.graph_seed,
                "mode": result.mode,
                "status": result.status,
                "success": result.success,
                "selected": sorted(result.selected),
                "metrics": result.metrics,
                "logs": result.logs,
            }, ensure_ascii=False) + "\n")

    print("=== VERTEX COVER L/G SUMMARY ===")
    for row in summary:
        print(row)
    print("Files written:")
    print(args.out_prefix + "_summary_by_mode.csv")
    print(args.out_prefix + "_summary_by_case.csv")
    print(args.out_prefix + "_logs.jsonl")


if __name__ == "__main__":
    main()
