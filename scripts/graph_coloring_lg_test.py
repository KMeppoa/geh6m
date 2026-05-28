#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L/G experiment for graph coloring.

Task:
    Color graph vertices with k colors so adjacent vertices have different colors.

L:
    Local state: conflicts, uncolored vertices, available colors.

G:
    Constraint propagation: if a vertex has only one possible color, force it.
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
    status: str
    success: bool
    steps: int
    coloring: dict
    metrics: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)


def generate_random_graph(n_vertices, edge_prob, seed):
    rng = random.Random(seed)
    edges = set()
    adjacency = {v: set() for v in range(n_vertices)}
    for i in range(n_vertices):
        for j in range(i + 1, n_vertices):
            if rng.random() < edge_prob:
                edges.add((i, j))
                adjacency[i].add(j)
                adjacency[j].add(i)
    return edges, adjacency


def verify_coloring(edges, coloring, n_vertices):
    if len(coloring) < n_vertices:
        return False
    for a, b in edges:
        if coloring.get(a) == coloring.get(b):
            return False
    return True


def available_colors(vertex, coloring, adjacency, n_colors):
    used = {
        coloring[nbr]
        for nbr in adjacency[vertex]
        if nbr in coloring
    }
    return [c for c in range(n_colors) if c not in used]


def uncolored_vertices(n_vertices, coloring):
    return [v for v in range(n_vertices) if v not in coloring]


def coloring_stats(edges, adjacency, coloring, n_vertices, n_colors):
    conflicts = 0
    for a, b in edges:
        if a in coloring and b in coloring and coloring[a] == coloring[b]:
            conflicts += 1

    uncolored = uncolored_vertices(n_vertices, coloring)
    no_color = 0
    forced = 0
    pressure = 0

    for v in uncolored:
        avail = available_colors(v, coloring, adjacency, n_colors)
        pressure += n_colors - len(avail)
        if not avail:
            no_color += 1
        elif len(avail) == 1:
            forced += 1

    return {
        "conflicts": conflicts,
        "colored": len(coloring),
        "uncolored": len(uncolored),
        "no_color": no_color,
        "forced": forced,
        "pressure": pressure,
    }


def score_l(edges, adjacency, coloring, n_vertices, n_colors):
    st = coloring_stats(edges, adjacency, coloring, n_vertices, n_colors)
    return (
        st["conflicts"] * 1_000_000
        + st["no_color"] * 100_000
        + st["uncolored"] * 10
        + st["pressure"] * 2
        - st["colored"]
    )


def propagate(coloring, adjacency, n_vertices, n_colors, max_forced=10000):
    coloring = dict(coloring)
    forced_count = 0

    while forced_count < max_forced:
        changed = False
        for v in range(n_vertices):
            if v in coloring:
                continue
            avail = available_colors(v, coloring, adjacency, n_colors)
            if not avail:
                return True, coloring, forced_count
            if len(avail) == 1:
                coloring[v] = avail[0]
                forced_count += 1
                changed = True
                break
        if not changed:
            return False, coloring, forced_count

    return False, coloring, forced_count


def score_lg(edges, adjacency, coloring, n_vertices, n_colors):
    conflict, propagated, forced_count = propagate(
        coloring, adjacency, n_vertices, n_colors
    )
    if conflict:
        return 10_000_000
    st = coloring_stats(edges, adjacency, propagated, n_vertices, n_colors)
    return (
        st["conflicts"] * 1_000_000
        + st["no_color"] * 100_000
        + st["uncolored"] * 10
        + st["pressure"] * 2
        - st["colored"] * 2
        - forced_count
    )


def possible_actions(n_vertices, n_colors, coloring, adjacency):
    actions = []
    for v in uncolored_vertices(n_vertices, coloring):
        for c in available_colors(v, coloring, adjacency, n_colors):
            actions.append((v, c))
    return actions


def apply_action(coloring, action):
    v, c = action
    new_coloring = dict(coloring)
    new_coloring[v] = c
    return new_coloring


def evaluate_future(
    edges,
    adjacency,
    coloring,
    n_vertices,
    n_colors,
    depth,
    score_kind,
    branch_cap,
    score_counter,
):
    if verify_coloring(edges, coloring, n_vertices):
        return -1_000_000

    if score_kind == "LG":
        base_score = score_lg(edges, adjacency, coloring, n_vertices, n_colors)
    else:
        base_score = score_l(edges, adjacency, coloring, n_vertices, n_colors)
    score_counter[0] += 1

    if base_score >= 10_000_000 or depth <= 0:
        return base_score

    actions = possible_actions(n_vertices, n_colors, coloring, adjacency)
    if not actions:
        return base_score

    ranked = []
    for action in actions:
        new_coloring = apply_action(coloring, action)
        if score_kind == "LG":
            local_score = score_lg(edges, adjacency, new_coloring, n_vertices, n_colors)
        else:
            local_score = score_l(edges, adjacency, new_coloring, n_vertices, n_colors)
        score_counter[0] += 1
        ranked.append((local_score, action, new_coloring))

    ranked.sort(key=lambda x: (x[0], x[1][0], x[1][1]))
    ranked = ranked[:branch_cap]

    best = inf
    for _, _, new_coloring in ranked:
        future = evaluate_future(
            edges,
            adjacency,
            new_coloring,
            n_vertices,
            n_colors,
            depth - 1,
            score_kind,
            branch_cap,
            score_counter,
        )
        if future < best:
            best = future
    return best


def search_coloring(
    edges,
    adjacency,
    n_vertices,
    n_colors,
    graph_seed,
    mode,
    score_kind,
    lookahead_depth,
    max_steps,
    branch_cap,
):
    coloring = {}
    decision_steps = 0
    forced_steps = 0
    score_calls = [0]
    logs = [f"START {mode}: score_kind={score_kind}, lookahead={lookahead_depth}"]

    for step in range(1, min(max_steps, n_vertices) + 1):
        if verify_coloring(edges, coloring, n_vertices):
            return RunResult(
                graph_seed,
                mode,
                "SOLUTION_FOUND",
                True,
                step - 1,
                coloring,
                {
                    "decision_steps": decision_steps,
                    "forced_steps": forced_steps,
                    "score_calls": score_calls[0],
                },
                logs,
            )

        actions = possible_actions(n_vertices, n_colors, coloring, adjacency)
        if not actions:
            break

        scored = []
        for action in actions:
            new_coloring = apply_action(coloring, action)
            score = evaluate_future(
                edges,
                adjacency,
                new_coloring,
                n_vertices,
                n_colors,
                lookahead_depth - 1,
                score_kind,
                branch_cap,
                score_calls,
            )
            scored.append((score, action, new_coloring))

        scored.sort(key=lambda x: (x[0], x[1][0], x[1][1]))
        best_score, best_action, best_coloring = scored[0]

        if score_kind == "LG":
            conflict, propagated, forced_count = propagate(
                best_coloring, adjacency, n_vertices, n_colors
            )
            if conflict:
                forced_count = 0
            else:
                best_coloring = propagated
        else:
            forced_count = 0

        coloring = best_coloring
        decision_steps += 1
        forced_steps += forced_count

        logs.append(
            f"step={step}: chosen=v{best_action[0]} c{best_action[1]}, "
            f"score={round(best_score, 2)}, forced={forced_count}, "
            f"stats={coloring_stats(edges, adjacency, coloring, n_vertices, n_colors)}"
        )

        st = coloring_stats(edges, adjacency, coloring, n_vertices, n_colors)
        if st["conflicts"] > 0 or st["no_color"] > 0:
            break

    success = verify_coloring(edges, coloring, n_vertices)
    return RunResult(
        graph_seed,
        mode,
        "SOLUTION_FOUND" if success else "FAILED_TO_FIND",
        success,
        len(coloring),
        coloring,
        {
            "decision_steps": decision_steps,
            "forced_steps": forced_steps,
            "score_calls": score_calls[0],
        },
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
    modes = sorted({r.mode for r in results})
    rows = []
    for mode in modes:
        items = [r for r in results if r.mode == mode]
        total = len(items)
        success = sum(1 for r in items if r.success)
        rows.append({
            "mode": mode,
            "total": total,
            "success": success,
            "fail": total - success,
            "success_rate": success / total if total else 0,
            "avg_decision_steps": sum(r.metrics.get("decision_steps", 0) for r in items) / total if total else "",
            "avg_forced_steps": sum(r.metrics.get("forced_steps", 0) for r in items) / total if total else "",
            "avg_score_calls": sum(r.metrics.get("score_calls", 0) for r in items) / total if total else "",
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graphs", type=int, default=30)
    parser.add_argument("--vertices", type=int, default=16)
    parser.add_argument("--colors", type=int, default=3)
    parser.add_argument("--edge-prob", type=float, default=0.18)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--out-prefix", default="graph_coloring_lg")
    args = parser.parse_args()

    all_results = []
    case_rows = []

    for i in range(args.graphs):
        graph_seed = args.seed + i
        edges, adjacency = generate_random_graph(args.vertices, args.edge_prob, graph_seed)

        modes = [
            ("greedy_L", "L", 1),
            ("greedy_LG", "LG", 1),
            ("lookahead_L_2", "L", 2),
            ("lookahead_LG_2", "LG", 2),
            ("lookahead_L_3", "L", 3),
            ("lookahead_LG_3", "LG", 3),
        ]

        for mode, score_kind, depth in modes:
            result = search_coloring(
                edges,
                adjacency,
                args.vertices,
                args.colors,
                graph_seed,
                mode,
                score_kind,
                depth,
                args.max_steps,
                args.branch_cap,
            )
            all_results.append(result)
            case_rows.append({
                "graph_seed": graph_seed,
                "mode": mode,
                "status": result.status,
                "success": result.success,
                "steps": result.steps,
                "colored_count": len(result.coloring),
                "direct_verified": verify_coloring(edges, result.coloring, args.vertices),
                "decision_steps": result.metrics.get("decision_steps", ""),
                "forced_steps": result.metrics.get("forced_steps", ""),
                "score_calls": result.metrics.get("score_calls", ""),
                "edge_count": len(edges),
            })

    summary_rows = summarize(all_results)
    save_csv(Path(args.out_prefix + "_summary_by_mode.csv"), summary_rows)
    save_csv(Path(args.out_prefix + "_summary_by_graph.csv"), case_rows)

    with open(args.out_prefix + "_logs.jsonl", "w", encoding="utf-8") as f:
        for result in all_results[:20]:
            f.write(json.dumps(result.__dict__, ensure_ascii=False) + "\n")

    print("=== GRAPH COLORING L/G SUMMARY ===")
    for row in summary_rows:
        print(row)
    print("Files written:")
    print(args.out_prefix + "_summary_by_mode.csv")
    print(args.out_prefix + "_summary_by_graph.csv")
    print(args.out_prefix + "_logs.jsonl")


if __name__ == "__main__":
    main()
