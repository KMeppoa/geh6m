#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Measure how guided_n depth grows on planted Graph Coloring.

The generator creates k-colorable graphs by planting a coloring and only adding
edges between different color classes. This keeps the test SAT while allowing
dense constraints.
"""

import argparse
import csv
import json
import random
from pathlib import Path

import graph_coloring_lg_test as gc


def generate_planted_colorable_graph(n_vertices, n_colors, edge_prob, seed):
    rng = random.Random(seed)
    planted = {v: v % n_colors for v in range(n_vertices)}
    vertices = list(range(n_vertices))
    rng.shuffle(vertices)
    shuffled_colors = [planted[v] for v in vertices]
    planted = {v: shuffled_colors[i] for i, v in enumerate(range(n_vertices))}

    edges = set()
    adjacency = {v: set() for v in range(n_vertices)}
    for i in range(n_vertices):
        for j in range(i + 1, n_vertices):
            if planted[i] == planted[j]:
                continue
            if rng.random() < edge_prob:
                edges.add((i, j))
                adjacency[i].add(j)
                adjacency[j].add(i)
    return edges, adjacency, planted


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_one(edges, adjacency, n_vertices, n_colors, seed, depth, branch_cap, max_steps):
    mode = "greedy_LG" if depth == 1 else f"lookahead_LG_{depth}"
    result = gc.search_coloring(
        edges,
        adjacency,
        n_vertices,
        n_colors,
        seed,
        mode,
        "LG",
        depth,
        max_steps,
        branch_cap,
    )
    verified = gc.verify_coloring(edges, result.coloring, n_vertices)
    return {
        "mode": mode,
        "success": result.success and verified,
        "status": result.status if verified or not result.success else "FALSE_SUCCESS",
        "decision_steps": result.metrics.get("decision_steps", 0),
        "forced_steps": result.metrics.get("forced_steps", 0),
        "score_calls": result.metrics.get("score_calls", 0),
        "colored": len(result.coloring),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=10)
    parser.add_argument("--sizes", type=int, nargs="*", default=[18, 22, 26, 30])
    parser.add_argument("--colors", type=int, default=3)
    parser.add_argument("--edge-prob", type=float, default=0.55)
    parser.add_argument("--depths", type=int, nargs="*", default=[1, 2, 3, 4])
    parser.add_argument("--branch-cap", type=int, default=3)
    parser.add_argument("--max-steps-factor", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="experiments/guided_depth_growth_graph_coloring_step1")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")

    detail_rows = []
    summary_rows = []
    first_rows = []

    print("=== GUIDED DEPTH GROWTH: GRAPH COLORING ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for size in args.sizes:
        print(f"size={size}")
        first_depth = None
        for depth in args.depths:
            successes = 0
            false_success = 0
            decisions = 0
            forced = 0
            score_calls = 0
            for case_idx in range(args.cases):
                seed = args.seed + size * 1000 + depth * 100 + case_idx
                edges, adjacency, _ = generate_planted_colorable_graph(
                    size, args.colors, args.edge_prob, seed
                )
                row = run_one(
                    edges,
                    adjacency,
                    size,
                    args.colors,
                    seed,
                    depth,
                    args.branch_cap,
                    size * args.max_steps_factor,
                )
                successes += 1 if row["success"] else 0
                false_success += 1 if row["status"] == "FALSE_SUCCESS" else 0
                decisions += row["decision_steps"]
                forced += row["forced_steps"]
                score_calls += row["score_calls"]
                detail_rows.append({
                    "size": size,
                    "depth": depth,
                    "case": case_idx,
                    "seed": seed,
                    "edge_count": len(edges),
                    **row,
                })

            success_rate = successes / args.cases
            if success_rate == 1.0 and first_depth is None:
                first_depth = depth
            summary_rows.append({
                "size": size,
                "depth": depth,
                "success": successes,
                "total": args.cases,
                "success_rate": success_rate,
                "false_success": false_success,
                "avg_decision_steps": decisions / args.cases,
                "avg_forced_steps": forced / args.cases,
                "avg_score_calls": score_calls / args.cases,
            })
            print(
                f"  guided_{depth}: {successes}/{args.cases} "
                f"avg_decision={decisions / args.cases:.2f} "
                f"avg_forced={forced / args.cases:.2f}"
            )
        first_rows.append({"size": size, "first_depth_100": first_depth if first_depth is not None else ""})
        print(f"  first_depth_100={first_depth}")
        print()

    write_csv(out_dir / "summary_by_depth.csv", summary_rows)
    write_csv(out_dir / "summary_first_depth_100.csv", first_rows)
    write_csv(out_dir / "details.csv", detail_rows)

    print("=== FILES WRITTEN ===")
    print(out_dir / "config.json")
    print(out_dir / "summary_by_depth.csv")
    print(out_dir / "summary_first_depth_100.csv")
    print(out_dir / "details.csv")


if __name__ == "__main__":
    main()
