#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L/G experiments for two graph NP tasks:
    1. Independent Set
    2. Clique

Instances are generated with a planted solution so success is possible.
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
    task: str
    graph_seed: int
    mode: str
    success: bool
    status: str
    steps: int
    selected: set
    metrics: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)


def make_graph(n_vertices, edge_prob, seed, task, target_size):
    rng = random.Random(seed)
    planted = set(rng.sample(range(n_vertices), target_size))
    edges = set()
    adjacency = {v: set() for v in range(n_vertices)}

    for i in range(n_vertices):
        for j in range(i + 1, n_vertices):
            forced_edge = task == "clique" and i in planted and j in planted
            forbidden_edge = task == "independent_set" and i in planted and j in planted
            has_edge = forced_edge or ((not forbidden_edge) and rng.random() < edge_prob)
            if has_edge:
                edges.add((i, j))
                adjacency[i].add(j)
                adjacency[j].add(i)
    return edges, adjacency, planted


def has_edge(edges, a, b):
    x, y = sorted((a, b))
    return (x, y) in edges


def verify_solution(task, edges, selected, target_size):
    if len(selected) < target_size:
        return False
    chosen = list(selected)[:target_size]
    for i in range(len(chosen)):
        for j in range(i + 1, len(chosen)):
            edge = has_edge(edges, chosen[i], chosen[j])
            if task == "independent_set" and edge:
                return False
            if task == "clique" and not edge:
                return False
    return True


def compatible(task, edges, selected, vertex):
    if vertex in selected:
        return False
    for other in selected:
        edge = has_edge(edges, vertex, other)
        if task == "independent_set" and edge:
            return False
        if task == "clique" and not edge:
            return False
    return True


def initial_state(n_vertices):
    return {
        "selected": set(),
        "candidates": set(range(n_vertices)),
    }


def state_copy(state):
    return {
        "selected": set(state["selected"]),
        "candidates": set(state["candidates"]),
    }


def l_candidates(task, edges, state, n_vertices):
    return [
        v for v in range(n_vertices)
        if compatible(task, edges, state["selected"], v)
    ]


def apply_l_action(state, vertex):
    new_state = state_copy(state)
    new_state["selected"].add(vertex)
    return new_state


def prune_candidates(task, adjacency, state, vertex):
    selected = set(state["selected"])
    candidates = set(state["candidates"])
    selected.add(vertex)
    candidates.discard(vertex)

    if task == "independent_set":
        candidates -= adjacency[vertex]
    else:
        candidates &= adjacency[vertex]

    return {
        "selected": selected,
        "candidates": candidates,
    }


def can_take_all(task, edges, selected, candidates, target_size):
    needed = target_size - len(selected)
    if needed < 0 or len(candidates) < needed:
        return False, set()
    forced = set(candidates)
    combined = set(selected) | forced
    return verify_solution(task, edges, combined, target_size), forced


def propagate(task, edges, adjacency, state, target_size):
    state = state_copy(state)
    forced_count = 0

    if len(state["selected"]) >= target_size:
        return False, state, forced_count

    if len(state["selected"]) + len(state["candidates"]) < target_size:
        return True, state, forced_count

    needed = target_size - len(state["selected"])
    if needed == len(state["candidates"]):
        ok, forced = can_take_all(task, edges, state["selected"], state["candidates"], target_size)
        if not ok:
            return True, state, forced_count
        state["selected"] |= forced
        state["candidates"].clear()
        forced_count += len(forced)

    return False, state, forced_count


def score_state(task, edges, adjacency, state, n_vertices, target_size, use_g):
    working = state
    forced_count = 0
    if use_g:
        conflict, working, forced_count = propagate(task, edges, adjacency, state, target_size)
        if conflict:
            return 10_000_000

    selected = working["selected"]
    candidates = working["candidates"] if use_g else set(l_candidates(task, edges, working, n_vertices))
    needed = max(0, target_size - len(selected))
    impossible = len(candidates) < needed
    return (
        (1_000_000 if impossible else 0)
        + needed * 100
        + len(candidates) * 2
        - len(selected) * 10
        - forced_count
    )


def possible_actions(task, edges, state, n_vertices, use_g):
    if use_g:
        return sorted(state["candidates"])
    return sorted(l_candidates(task, edges, state, n_vertices))


def apply_action(task, adjacency, state, vertex, use_g):
    if use_g:
        return prune_candidates(task, adjacency, state, vertex)
    return apply_l_action(state, vertex)


def evaluate_future(task, edges, adjacency, state, n_vertices, target_size, depth, use_g, branch_cap, score_counter):
    if verify_solution(task, edges, state["selected"], target_size):
        return -1_000_000

    base = score_state(task, edges, adjacency, state, n_vertices, target_size, use_g)
    score_counter[0] += 1
    if base >= 10_000_000 or depth <= 0:
        return base

    actions = possible_actions(task, edges, state, n_vertices, use_g)
    if not actions:
        return base

    ranked = []
    for vertex in actions:
        next_state = apply_action(task, adjacency, state, vertex, use_g)
        local = score_state(task, edges, adjacency, next_state, n_vertices, target_size, use_g)
        score_counter[0] += 1
        ranked.append((local, vertex, next_state))
    ranked.sort(key=lambda x: (x[0], x[1]))
    ranked = ranked[:branch_cap]

    best = inf
    for _, _, next_state in ranked:
        future = evaluate_future(
            task, edges, adjacency, next_state, n_vertices, target_size,
            depth - 1, use_g, branch_cap, score_counter,
        )
        if future < best:
            best = future
    return best


def search(task, edges, adjacency, n_vertices, target_size, graph_seed, mode, use_g, depth, max_steps, branch_cap):
    state = initial_state(n_vertices)
    decision_steps = 0
    forced_steps = 0
    score_counter = [0]
    logs = [f"START {mode}: task={task}, depth={depth}, use_g={use_g}"]

    for step in range(1, max_steps + 1):
        if verify_solution(task, edges, state["selected"], target_size):
            return RunResult(
                task, graph_seed, mode, True, "SOLUTION_FOUND", step - 1,
                set(state["selected"]),
                {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_counter[0]},
                logs,
            )

        actions = possible_actions(task, edges, state, n_vertices, use_g)
        if not actions:
            break

        ranked = []
        for vertex in actions:
            next_state = apply_action(task, adjacency, state, vertex, use_g)
            score = evaluate_future(
                task, edges, adjacency, next_state, n_vertices, target_size,
                depth - 1, use_g, branch_cap, score_counter,
            )
            ranked.append((score, vertex, next_state))
        ranked.sort(key=lambda x: (x[0], x[1]))
        best_score, vertex, next_state = ranked[0]

        if use_g:
            conflict, next_state, forced_count = propagate(task, edges, adjacency, next_state, target_size)
            if conflict:
                forced_count = 0
        else:
            forced_count = 0

        state = next_state
        decision_steps += 1
        forced_steps += forced_count
        logs.append(
            f"step={step}: choose={vertex}, score={round(best_score,2)}, "
            f"selected={len(state['selected'])}, candidates={len(state['candidates'])}, forced={forced_count}"
        )

    success = verify_solution(task, edges, state["selected"], target_size)
    return RunResult(
        task, graph_seed, mode, success, "SOLUTION_FOUND" if success else "FAILED_TO_FIND",
        len(state["selected"]), set(state["selected"]),
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
    for key in sorted({(r.task, r.mode) for r in results}):
        task, mode = key
        items = [r for r in results if r.task == task and r.mode == mode]
        total = len(items)
        success = sum(1 for r in items if r.success)
        rows.append({
            "task": task,
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
    parser.add_argument("--target-size", type=int, default=5)
    parser.add_argument("--edge-prob", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--tasks", default="independent_set,clique")
    parser.add_argument("--out-prefix", default="graph_is_clique_lg")
    args = parser.parse_args()

    tasks = [x.strip() for x in args.tasks.split(",") if x.strip()]
    all_results = []
    case_rows = []

    for task in tasks:
        for i in range(args.graphs):
            graph_seed = args.seed + i
            edges, adjacency, planted = make_graph(
                args.vertices, args.edge_prob, graph_seed, task, args.target_size
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
                    task, edges, adjacency, args.vertices, args.target_size,
                    graph_seed, mode, use_g, depth, args.max_steps, args.branch_cap
                )
                all_results.append(result)
                case_rows.append({
                    "task": task,
                    "graph_seed": graph_seed,
                    "mode": mode,
                    "status": result.status,
                    "success": result.success,
                    "direct_verified": verify_solution(task, edges, result.selected, args.target_size),
                    "selected_count": len(result.selected),
                    "decision_steps": result.metrics["decision_steps"],
                    "forced_steps": result.metrics["forced_steps"],
                    "score_calls": result.metrics["score_calls"],
                    "edge_count": len(edges),
                    "planted": " ".join(str(x) for x in sorted(planted)),
                })

    summary = summarize(all_results)
    save_csv(Path(args.out_prefix + "_summary_by_mode.csv"), summary)
    save_csv(Path(args.out_prefix + "_summary_by_case.csv"), case_rows)

    with open(args.out_prefix + "_logs.jsonl", "w", encoding="utf-8") as f:
        for result in all_results[:20]:
            item = {
                "task": result.task,
                "graph_seed": result.graph_seed,
                "mode": result.mode,
                "status": result.status,
                "success": result.success,
                "selected": sorted(result.selected),
                "metrics": result.metrics,
                "logs": result.logs,
            }
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print("=== INDEPENDENT SET / CLIQUE L/G SUMMARY ===")
    for row in summary:
        print(row)
    print("Files written:")
    print(args.out_prefix + "_summary_by_mode.csv")
    print(args.out_prefix + "_summary_by_case.csv")
    print(args.out_prefix + "_logs.jsonl")


if __name__ == "__main__":
    main()
