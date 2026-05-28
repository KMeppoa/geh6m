#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Graph Coloring danger-rate probe.

Analogue of SAT danger_rate:
    affected_edges = edges touching vertices in chosen cluster
    dangerous_edges = affected edges where, after assigning cluster colors,
                      an uncolored endpoint has only one available color
    danger_rate = dangerous_edges / affected_edges

This is a probe, not a graph-coloring solver.
"""

import argparse
import csv
import random
import time
from collections import deque
from pathlib import Path

from sat_fast_d_scaling_probe import build_next_level_sparse


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def generate_sparse_planted_graph(n_vertices, n_colors, avg_degree, seed):
    rng = random.Random(seed)
    vertices = list(range(1, n_vertices + 1))
    colors = {v: (v - 1) % n_colors for v in vertices}
    shuffled = [colors[v] for v in vertices]
    rng.shuffle(shuffled)
    colors = {v: shuffled[v - 1] for v in vertices}

    target_edges = int(n_vertices * avg_degree / 2)
    edges = set()
    adjacency = {v: set() for v in vertices}
    attempts = 0
    max_attempts = target_edges * 30
    while len(edges) < target_edges and attempts < max_attempts:
        attempts += 1
        a = rng.randint(1, n_vertices)
        b = rng.randint(1, n_vertices)
        if a == b or colors[a] == colors[b]:
            continue
        edge = (a, b) if a < b else (b, a)
        if edge in edges:
            continue
        edges.add(edge)
        adjacency[a].add(b)
        adjacency[b].add(a)
    return edges, adjacency, colors


def build_edge_index(edges, n_vertices):
    edge_list = list(edges)
    vertex_to_edges = [[] for _ in range(n_vertices + 1)]
    for idx, (a, b) in enumerate(edge_list):
        vertex_to_edges[a].append(idx)
        vertex_to_edges[b].append(idx)
    return edge_list, vertex_to_edges


def available_colors(vertex, coloring, adjacency, n_colors):
    used = {coloring[nbr] for nbr in adjacency[vertex] if nbr in coloring}
    return [color for color in range(n_colors) if color not in used]


def affected_edge_ids(unit, vertex_to_edges):
    affected = set()
    for vertex in unit:
        affected.update(vertex_to_edges[vertex])
    return affected


def propagate_coloring(coloring, adjacency, n_vertices, n_colors, queue_vertices, max_forced):
    coloring = dict(coloring)
    queue = deque(queue_vertices)
    forced = 0

    while queue:
        vertex = queue.popleft()
        for nbr in adjacency[vertex]:
            if nbr in coloring:
                continue
            avail = available_colors(nbr, coloring, adjacency, n_colors)
            if not avail:
                return True, coloring, forced
            if len(avail) == 1:
                coloring[nbr] = avail[0]
                forced += 1
                if forced >= max_forced:
                    return False, coloring, forced
                for nn in adjacency[nbr]:
                    queue.append(nn)
    return False, coloring, forced


def evaluate_unit(unit, edge_list, vertex_to_edges, adjacency, n_vertices, n_colors, planted, max_forced):
    coloring = {vertex: planted[vertex] for vertex in unit}
    affected = affected_edge_ids(unit, vertex_to_edges)
    dangerous = 0
    freedoms = []
    for edge_idx in affected:
        a, b = edge_list[edge_idx]
        is_dangerous = False
        if a not in coloring:
            avail_a = len(available_colors(a, coloring, adjacency, n_colors))
            freedoms.append(avail_a)
            if avail_a == 1:
                is_dangerous = True
        if b not in coloring:
            avail_b = len(available_colors(b, coloring, adjacency, n_colors))
            freedoms.append(avail_b)
            if avail_b == 1:
                is_dangerous = True
        if is_dangerous:
            dangerous += 1

    conflict, propagated, forced = propagate_coloring(
        coloring, adjacency, n_vertices, n_colors, list(unit), max_forced
    )
    ig = len(propagated)
    danger_rate = dangerous / len(affected) if affected else 0.0
    useful_ig = 0.0 if conflict else ig * (1.0 - danger_rate)
    return {
        "IG": ig,
        "forced": forced,
        "affected_edges": len(affected),
        "dangerous_edges": dangerous,
        "danger_rate": danger_rate,
        "avg_freedom": (sum(freedoms) / len(freedoms)) if freedoms else 0.0,
        "useful_IG": useful_ig,
        "D": n_vertices / useful_ig if useful_ig > 0 else "",
        "conflict": conflict,
    }


def candidate_units(units, sample_units, rng):
    if not sample_units or len(units) <= sample_units:
        return units
    keep_count = max(1, sample_units // 2)
    top = sorted(units, key=lambda unit: (-len(unit), unit[0]))[:keep_count]
    top_keys = {tuple(unit) for unit in top}
    remaining = [unit for unit in units if tuple(unit) not in top_keys]
    random_count = sample_units - len(top)
    if len(remaining) > random_count:
        remaining = rng.sample(remaining, random_count)
    return top + remaining


def choose_best(units, sample_units, rng, edge_list, vertex_to_edges, adjacency, n_vertices, n_colors, planted, max_forced):
    best = None
    for unit in candidate_units(units, sample_units, rng):
        metrics = evaluate_unit(
            unit, edge_list, vertex_to_edges, adjacency, n_vertices, n_colors, planted, max_forced
        )
        key = (
            -metrics["useful_IG"],
            -metrics["IG"],
            metrics["danger_rate"],
            -len(unit),
            unit[0],
        )
        if best is None or key < best[0]:
            best = (key, unit, metrics)
    return best[1], best[2]


def run_one(n_vertices, n_colors, args, seed):
    started = time.perf_counter()
    rng = random.Random(seed + 31337)
    edges, adjacency, planted = generate_sparse_planted_graph(
        n_vertices, n_colors, args.avg_degree, seed
    )
    edge_list, vertex_to_edges = build_edge_index(edges, n_vertices)
    edge_var_sets = [[a, b] for a, b in edge_list]

    units = [[v] for v in range(1, n_vertices + 1)]
    var_to_unit = {v: v - 1 for v in range(1, n_vertices + 1)}
    rows = []
    for level in range(1, args.max_levels + 1):
        units, var_to_unit, _edge_count, _eligible = build_next_level_sparse(
            edge_var_sets,
            units,
            var_to_unit,
            args.min_cooccur,
            args.base_max_cluster_size * level,
            args.top_neighbors,
        )
        if level not in (4, 5):
            continue
        chosen, metrics = choose_best(
            units,
            args.sample_units,
            rng,
            edge_list,
            vertex_to_edges,
            adjacency,
            n_vertices,
            n_colors,
            planted,
            args.max_forced,
        )
        rows.append({
            "n": n_vertices,
            "seed": seed,
            "colors": n_colors,
            "level": level,
            "edge_count": len(edge_list),
            "avg_degree": (2 * len(edge_list) / n_vertices) if n_vertices else 0.0,
            "unit_count": len(units),
            "chosen_unit_size": len(chosen),
            "IG": metrics["IG"],
            "forced": metrics["forced"],
            "affected_edges": metrics["affected_edges"],
            "dangerous_edges": metrics["dangerous_edges"],
            "danger_rate": metrics["danger_rate"],
            "avg_freedom": metrics["avg_freedom"],
            "useful_IG": metrics["useful_IG"],
            "D": metrics["D"],
            "avg_forced_per_assignment": metrics["forced"] / len(chosen) if chosen else 0.0,
            "sample_units": args.sample_units,
            "top_neighbors": args.top_neighbors,
            "runtime_seconds": time.perf_counter() - started,
        })
    return rows


def summarize(rows):
    out = []
    for n in sorted({row["n"] for row in rows}):
        for level in (4, 5):
            items = [row for row in rows if row["n"] == n and row["level"] == level]
            if not items:
                continue
            out.append({
                "n": n,
                "level": level,
                "samples": len(items),
                "avg_danger_rate": sum(row["danger_rate"] for row in items) / len(items),
                "avg_freedom": sum(row["avg_freedom"] for row in items) / len(items),
                "avg_forced_per_assignment": sum(row["avg_forced_per_assignment"] for row in items) / len(items),
                "avg_IG": sum(row["IG"] for row in items) / len(items),
                "avg_useful_IG": sum(row["useful_IG"] for row in items) / len(items),
                "avg_D": sum(float(row["D"]) for row in items if row["D"] != "") / len(items),
                "avg_affected_edges": sum(row["affected_edges"] for row in items) / len(items),
                "avg_dangerous_edges": sum(row["dangerous_edges"] for row in items) / len(items),
            })
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[1000, 5000, 10000])
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--colors", type=int, default=3)
    parser.add_argument("--avg-degree", type=float, default=8.0)
    parser.add_argument("--max-levels", type=int, default=5)
    parser.add_argument("--min-cooccur", type=int, default=1)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--sample-units", type=int, default=500)
    parser.add_argument("--top-neighbors", type=int, default=16)
    parser.add_argument("--max-forced", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="graph_coloring_danger_probe_step1")
    args = parser.parse_args()

    rows = []
    print("=== GRAPH COLORING DANGER PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()
    for n in args.sizes:
        print(f"n={n}")
        for i in range(args.seeds):
            rows.extend(run_one(n, args.colors, args, args.seed + n * 1000 + i))
        print("  done")
    summary = summarize(rows)
    write_csv(args.out_prefix + "_details.csv", rows)
    write_csv(args.out_prefix + "_summary.csv", summary)
    for row in summary:
        print(
            f"n={row['n']} level={row['level']} "
            f"danger={row['avg_danger_rate']:.4f} IG={row['avg_IG']:.2f} D={row['avg_D']:.2f}"
        )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
