#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Danger-rate analogues for Vertex Cover and Subset Sum.

This is a structural probe, not a solver.
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


def generate_sparse_planted_vertex_cover(n_vertices, cover_fraction, avg_degree, seed):
    rng = random.Random(seed)
    cover_size = max(1, int(n_vertices * cover_fraction))
    cover = set(rng.sample(range(1, n_vertices + 1), cover_size))
    target_edges = int(n_vertices * avg_degree / 2)
    edges = set()
    attempts = 0
    while len(edges) < target_edges and attempts < target_edges * 40:
        attempts += 1
        a = rng.randint(1, n_vertices)
        b = rng.randint(1, n_vertices)
        if a == b:
            continue
        if a not in cover and b not in cover:
            continue
        edge = (a, b) if a < b else (b, a)
        edges.add(edge)
    return list(edges), cover, cover_size


def build_vertex_to_edges(edges, n_vertices):
    idx = [[] for _ in range(n_vertices + 1)]
    for edge_idx, (a, b) in enumerate(edges):
        idx[a].append(edge_idx)
        idx[b].append(edge_idx)
    return idx


def vc_evaluate(unit, edges, vertex_to_edges, planted_cover, cover_size, n_vertices):
    selected = {v for v in unit if v in planted_cover}
    forbidden = {v for v in unit if v not in planted_cover}
    affected = set()
    for v in unit:
        affected.update(vertex_to_edges[v])

    dangerous = 0
    freedoms = []
    for edge_idx in affected:
        a, b = edges[edge_idx]
        if a in selected or b in selected:
            continue
        a_possible = a not in forbidden
        b_possible = b not in forbidden
        freedoms.append((1 if a_possible else 0) + (1 if b_possible else 0))
        if a_possible ^ b_possible:
            dangerous += 1

    forced = 0
    queue = deque(affected)
    seen = set(affected)
    while queue:
        edge_idx = queue.popleft()
        a, b = edges[edge_idx]
        if a in selected or b in selected:
            continue
        a_possible = a not in forbidden
        b_possible = b not in forbidden
        if not a_possible and not b_possible:
            break
        forced_vertex = None
        if a_possible and not b_possible:
            forced_vertex = a
        elif b_possible and not a_possible:
            forced_vertex = b
        if forced_vertex is not None and forced_vertex not in selected:
            selected.add(forced_vertex)
            forced += 1
            for next_edge in vertex_to_edges[forced_vertex]:
                if next_edge not in seen:
                    seen.add(next_edge)
                    queue.append(next_edge)

    ig = len(selected) + len(forbidden)
    danger_rate = dangerous / len(affected) if affected else 0.0
    useful = ig * (1.0 - danger_rate)
    return {
        "affected": len(affected),
        "dangerous": dangerous,
        "danger_rate": danger_rate,
        "avg_freedom": (sum(freedoms) / len(freedoms)) if freedoms else 0.0,
        "IG": ig,
        "forced": forced,
        "useful_IG": useful,
        "D": n_vertices / useful if useful > 0 else "",
    }


def generate_subset_sum(n_items, max_value, subset_fraction, seed):
    rng = random.Random(seed)
    numbers = [rng.randint(1, max_value) for _ in range(n_items)]
    subset_size = max(1, int(n_items * subset_fraction))
    planted = set(rng.sample(range(1, n_items + 1), subset_size))
    target = sum(numbers[i - 1] for i in planted)
    return numbers, target, planted


def subset_pairs_by_sorted_neighbors(numbers, top_neighbors):
    order = sorted(range(1, len(numbers) + 1), key=lambda idx: (numbers[idx - 1], idx))
    pairs = []
    for pos, item in enumerate(order):
        for offset in range(1, top_neighbors + 1):
            if pos + offset >= len(order):
                break
            pairs.append([item, order[pos + offset]])
    return pairs


def subset_evaluate(unit, numbers, target, planted, n_items):
    included = {i for i in unit if i in planted}
    excluded = {i for i in unit if i not in planted}
    cur = sum(numbers[i - 1] for i in included)
    remaining = [i for i in range(1, n_items + 1) if i not in included and i not in excluded]
    rest_sum = sum(numbers[i - 1] for i in remaining)
    residual = target - cur

    affected = len(unit)
    dangerous = 0
    freedoms = []
    for i in remaining:
        value = numbers[i - 1]
        must_include = cur + (rest_sum - value) < target
        must_exclude = cur + value > target
        exact_single = value == residual
        freedoms.append(1 if (must_include or must_exclude or exact_single) else 2)
        if must_include or must_exclude or exact_single:
            dangerous += 1

    forced = 0
    if cur == target:
        forced = len(remaining)
    elif cur + rest_sum == target:
        forced = len(remaining)
    ig = len(included) + len(excluded) + forced
    affected_states = affected + len(remaining)
    danger_rate = dangerous / affected_states if affected_states else 0.0
    useful = ig * (1.0 - danger_rate)
    return {
        "affected": affected_states,
        "dangerous": dangerous,
        "danger_rate": danger_rate,
        "avg_freedom": (sum(freedoms) / len(freedoms)) if freedoms else 0.0,
        "IG": ig,
        "forced": forced,
        "useful_IG": useful,
        "D": n_items / useful if useful > 0 else "",
    }


def candidate_units(units, sample_units, rng):
    if not sample_units or len(units) <= sample_units:
        return units
    keep = max(1, sample_units // 2)
    top = sorted(units, key=lambda unit: (-len(unit), unit[0]))[:keep]
    top_keys = {tuple(unit) for unit in top}
    rest = [unit for unit in units if tuple(unit) not in top_keys]
    need = sample_units - len(top)
    if len(rest) > need:
        rest = rng.sample(rest, need)
    return top + rest


def choose_best(units, sample_units, rng, eval_fn):
    best = None
    for unit in candidate_units(units, sample_units, rng):
        metrics = eval_fn(unit)
        key = (-metrics["useful_IG"], -metrics["IG"], metrics["danger_rate"], -len(unit), unit[0])
        if best is None or key < best[0]:
            best = (key, unit, metrics)
    return best[1], best[2]


def run_vertex_cover(n, args, seed):
    edges, planted, cover_size = generate_sparse_planted_vertex_cover(
        n, args.cover_fraction, args.avg_degree, seed
    )
    vertex_to_edges = build_vertex_to_edges(edges, n)
    units = [[v] for v in range(1, n + 1)]
    var_to_unit = {v: v - 1 for v in range(1, n + 1)}
    rows = []
    for level in range(1, args.max_levels + 1):
        units, var_to_unit, _edge_count, _eligible = build_next_level_sparse(
            [[a, b] for a, b in edges],
            units,
            var_to_unit,
            1,
            args.base_max_cluster_size * level,
            args.top_neighbors,
        )
        if level in (4, 5):
            unit, metrics = choose_best(
                units, args.sample_units, random.Random(seed + level),
                lambda u: vc_evaluate(u, edges, vertex_to_edges, planted, cover_size, n),
            )
            rows.append(("VertexCover", level, len(edges), len(unit), metrics))
    return rows


def run_subset_sum(n, args, seed):
    numbers, target, planted = generate_subset_sum(n, args.max_value, args.subset_fraction, seed)
    pseudo_edges = subset_pairs_by_sorted_neighbors(numbers, args.top_neighbors)
    units = [[v] for v in range(1, n + 1)]
    var_to_unit = {v: v - 1 for v in range(1, n + 1)}
    rows = []
    for level in range(1, args.max_levels + 1):
        units, var_to_unit, _edge_count, _eligible = build_next_level_sparse(
            pseudo_edges,
            units,
            var_to_unit,
            1,
            args.base_max_cluster_size * level,
            args.top_neighbors,
        )
        if level in (4, 5):
            unit, metrics = choose_best(
                units, args.sample_units, random.Random(seed + level),
                lambda u: subset_evaluate(u, numbers, target, planted, n),
            )
            rows.append(("SubsetSum", level, len(pseudo_edges), len(unit), metrics))
    return rows


def summarize(rows):
    out = []
    for task in sorted({row["task"] for row in rows}):
        for n in sorted({row["n"] for row in rows if row["task"] == task}):
            for level in (4, 5):
                items = [row for row in rows if row["task"] == task and row["n"] == n and row["level"] == level]
                if not items:
                    continue
                out.append({
                    "task": task,
                    "n": n,
                    "level": level,
                    "samples": len(items),
                    "avg_danger_rate": sum(row["danger_rate"] for row in items) / len(items),
                    "avg_freedom": sum(row["avg_freedom"] for row in items) / len(items),
                    "avg_forced_per_assignment": sum(row["avg_forced_per_assignment"] for row in items) / len(items),
                    "avg_IG": sum(row["IG"] for row in items) / len(items),
                    "avg_useful_IG": sum(row["useful_IG"] for row in items) / len(items),
                    "avg_D": sum(float(row["D"]) for row in items if row["D"] != "") / len(items),
                })
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[1000, 5000])
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--tasks", nargs="*", default=["VertexCover", "SubsetSum"])
    parser.add_argument("--avg-degree", type=float, default=4.0)
    parser.add_argument("--cover-fraction", type=float, default=0.30)
    parser.add_argument("--subset-fraction", type=float, default=0.10)
    parser.add_argument("--max-value", type=int, default=100)
    parser.add_argument("--max-levels", type=int, default=5)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--sample-units", type=int, default=500)
    parser.add_argument("--top-neighbors", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="np_danger_probe_step1")
    args = parser.parse_args()

    started = time.perf_counter()
    rows = []
    print("=== NP DANGER PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()
    for n in args.sizes:
        for i in range(args.seeds):
            seed = args.seed + n * 1000 + i
            task_rows = []
            if "VertexCover" in args.tasks:
                task_rows.extend(run_vertex_cover(n, args, seed))
            if "SubsetSum" in args.tasks:
                task_rows.extend(run_subset_sum(n, args, seed))
            for task, level, edge_count, unit_size, metrics in task_rows:
                rows.append({
                    "task": task,
                    "n": n,
                    "seed": seed,
                    "level": level,
                    "edge_or_state_count": edge_count,
                    "chosen_unit_size": unit_size,
                    "affected": metrics["affected"],
                    "dangerous": metrics["dangerous"],
                    "danger_rate": metrics["danger_rate"],
                    "avg_freedom": metrics["avg_freedom"],
                    "IG": metrics["IG"],
                    "forced": metrics["forced"],
                    "avg_forced_per_assignment": metrics["forced"] / unit_size if unit_size else 0.0,
                    "useful_IG": metrics["useful_IG"],
                    "D": metrics["D"],
                    "runtime_seconds": time.perf_counter() - started,
                })
        print(f"n={n} done")
    summary = summarize(rows)
    write_csv(args.out_prefix + "_details.csv", rows)
    write_csv(args.out_prefix + "_summary.csv", summary)
    for row in summary:
        print(
            f"{row['task']} n={row['n']} level={row['level']} "
            f"danger={row['avg_danger_rate']:.4f} IG={row['avg_IG']:.2f} D={row['avg_D']:.2f}"
        )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
