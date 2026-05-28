#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NP geometry map probe.

Lightweight structural probe for danger_rate vs constraint_pressure.
This is not a solver.
"""

import argparse
import csv
import random
import subprocess
import sys
import time
from pathlib import Path

from sat_fast_d_scaling_probe import build_next_level_sparse


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def median(values):
    vals = sorted(values)
    if not vals:
        return ""
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


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


def build_levels(n, constraints, args):
    units = [[v] for v in range(1, n + 1)]
    var_to_unit = {v: v - 1 for v in range(1, n + 1)}
    by_level = {}
    for level in range(1, 6):
        units, var_to_unit, _edge_count, _eligible = build_next_level_sparse(
            constraints,
            units,
            var_to_unit,
            1,
            args.base_max_cluster_size * level,
            args.top_neighbors,
        )
        if level in (4, 5):
            by_level[level] = units
    return by_level


def choose_best(units, sample_units, rng, eval_fn):
    best = None
    for unit in candidate_units(units, sample_units, rng):
        metrics = eval_fn(unit)
        key = (-metrics["useful_IG"], -metrics["IG"], metrics["danger_rate"], -len(unit), unit[0])
        if best is None or key < best[0]:
            best = (key, unit, metrics)
    best[2]["cluster_size"] = len(best[1])
    return best[1], best[2]


def sparse_graph(n, avg_degree, seed, planted_mode=None, target_size=None, density=None):
    rng = random.Random(seed)
    edges = set()
    adjacency = {v: set() for v in range(1, n + 1)}
    planted = set(rng.sample(range(1, n + 1), target_size or max(1, n // 10)))
    if density is not None:
        target_edges = int(density * n * (n - 1) / 2)
    else:
        target_edges = int(n * avg_degree / 2)
    attempts = 0
    while len(edges) < target_edges and attempts < target_edges * 50:
        attempts += 1
        a = rng.randint(1, n)
        b = rng.randint(1, n)
        if a == b:
            continue
        if planted_mode == "independent" and a in planted and b in planted:
            continue
        edge = (a, b) if a < b else (b, a)
        edges.add(edge)
    if planted_mode == "clique":
        p = sorted(planted)
        for i in range(len(p)):
            for j in range(i + 1, len(p)):
                edges.add((p[i], p[j]))
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    return list(edges), adjacency, planted


def graph_edge_index(edges, n):
    idx = [[] for _ in range(n + 1)]
    edge_set = set()
    for i, (a, b) in enumerate(edges):
        idx[a].append(i)
        idx[b].append(i)
        edge_set.add((a, b) if a < b else (b, a))
    return idx, edge_set


def graph_affected(unit, idx):
    out = set()
    for v in unit:
        out.update(idx[v])
    return out


def independent_set_task(n, args, seed):
    edges, adjacency, planted = sparse_graph(n, args.avg_degree, seed, "independent", max(2, n // 10))
    idx, _edge_set = graph_edge_index(edges, n)
    levels = build_levels(n, [[a, b] for a, b in edges], args)
    rows = []
    for level, units in levels.items():
        def ev(unit):
            selected = set(unit) & planted
            affected = graph_affected(unit, idx)
            excluded = set()
            for v in selected:
                excluded.update(adjacency[v])
            dangerous_vertices = excluded - selected
            danger = len(dangerous_vertices)
            denom = max(1, len(affected))
            ig = len(selected) + len(excluded)
            rate = danger / denom
            return {"danger_rate": rate, "IG": ig, "forced": len(excluded), "avg_freedom": 1.0 - rate, "useful_IG": ig * (1 - rate)}
        _unit, m = choose_best(units, args.sample_units, random.Random(seed + level), ev)
        rows.append(row("IndependentSet", n, seed, level, len(edges) / n, len(edges) / n, m))
    return rows


def clique_task(n, args, seed):
    density = args.clique_density
    edges, adjacency, planted = sparse_graph(n, args.avg_degree, seed, "clique", max(2, n // 20), density=density)
    idx, edge_set = graph_edge_index(edges, n)
    levels = build_levels(n, [[a, b] for a, b in edges], args)
    rows = []
    all_vertices = set(range(1, n + 1))
    for level, units in levels.items():
        def ev(unit):
            selected = set(unit) & planted
            candidates = set(all_vertices)
            for v in selected:
                candidates &= adjacency[v]
            forced_out = all_vertices - candidates - selected
            affected = graph_affected(unit, idx)
            danger = len(forced_out)
            denom = max(1, len(affected))
            ig = len(selected) + len(forced_out)
            rate = min(1.0, danger / denom)
            return {"danger_rate": rate, "IG": ig, "forced": len(forced_out), "avg_freedom": 1.0 - rate, "useful_IG": ig * (1 - rate)}
        _unit, m = choose_best(units, args.sample_units, random.Random(seed + level), ev)
        rows.append(row("Clique", n, seed, level, density, len(edges) / n, m))
    return rows


def hamiltonian_task(n, args, seed):
    edges, adjacency, planted = sparse_graph(n, args.avg_degree, seed, None)
    idx, _edge_set = graph_edge_index(edges, n)
    levels = build_levels(n, [[a, b] for a, b in edges], args)
    rows = []
    for level, units in levels.items():
        def ev(unit):
            used = set(unit)
            affected = graph_affected(unit, idx)
            dangerous = 0
            for v in range(1, n + 1):
                if v in used:
                    continue
                options = [nbr for nbr in adjacency[v] if nbr not in used]
                if len(options) == 1:
                    dangerous += 1
            ig = len(used)
            rate = dangerous / max(1, len(affected))
            freedoms = [
                len([nbr for nbr in adjacency[v] if nbr not in used])
                for v in range(1, n + 1) if v not in used
            ]
            return {"danger_rate": rate, "IG": ig, "forced": dangerous, "avg_freedom": (sum(freedoms) / len(freedoms)) if freedoms else 0.0, "useful_IG": ig * (1 - rate)}
        _unit, m = choose_best(units, args.sample_units, random.Random(seed + level), ev)
        rows.append(row("HamiltonianPath", n, seed, level, len(edges) / n, len(edges) / n, m))
    return rows


def set_system(n, set_ratio, set_size, seed, exact=False):
    rng = random.Random(seed)
    n_sets = max(1, int(n * set_ratio))
    sets = []
    for _ in range(n_sets):
        size = max(1, int(set_size))
        sets.append(set(rng.sample(range(1, n + 1), min(n, size))))
    return sets


def set_cover_like_task(name, n, args, seed, exact=False):
    sets = set_system(n, args.set_ratio, args.set_size, seed)
    element_to_sets = [[] for _ in range(n + 1)]
    constraints = []
    for idx, s in enumerate(sets, start=1):
        constraints.append(sorted(s))
        for e in s:
            element_to_sets[e].append(idx)
    levels = build_levels(n, constraints, args)
    rows = []
    for level, units in levels.items():
        def ev(unit):
            chosen_elements = set(unit)
            affected_sets = set()
            for e in chosen_elements:
                affected_sets.update(element_to_sets[e])
            dangerous = 0
            for e in range(1, n + 1):
                carriers = [s for s in element_to_sets[e] if s not in affected_sets]
                if len(carriers) == 1:
                    dangerous += 1
            freedoms = [len([s for s in element_to_sets[e] if s not in affected_sets]) for e in range(1, n + 1)]
            ig = len(chosen_elements)
            rate = dangerous / max(1, len(affected_sets))
            return {"danger_rate": rate, "IG": ig, "forced": dangerous, "avg_freedom": (sum(freedoms) / len(freedoms)) if freedoms else 0.0, "useful_IG": ig * (1 - rate)}
        _unit, m = choose_best(units, args.sample_units, random.Random(seed + level), ev)
        rows.append(row(name, n, seed, level, len(sets) / n, len(sets) / n, m))
    return rows


def nqueens_task(n, args, seed):
    constraints = [[i, i + 1] for i in range(1, n)]
    levels = build_levels(n, constraints, args)
    rows = []
    for level, units in levels.items():
        def ev(unit):
            queens = {r: (r * 2 + seed) % n for r in unit}
            used_cols = set(queens.values())
            used_d1 = {r - c for r, c in queens.items()}
            used_d2 = {r + c for r, c in queens.items()}
            affected = 0
            dangerous = 0
            freedoms = []
            for r in range(1, n + 1):
                if r in queens:
                    continue
                legal = 0
                for c in range(n):
                    if c in used_cols or (r - c) in used_d1 or (r + c) in used_d2:
                        affected += 1
                        continue
                    legal += 1
                if legal == 1:
                    dangerous += 1
                freedoms.append(legal)
            ig = len(unit)
            rate = dangerous / max(1, affected)
            return {"danger_rate": rate, "IG": ig, "forced": dangerous, "avg_freedom": (sum(freedoms) / len(freedoms)) if freedoms else 0.0, "useful_IG": ig * (1 - rate)}
        _unit, m = choose_best(levels[level], args.sample_units, random.Random(seed + level), ev)
        rows.append(row("NQueens", n, seed, level, 1.0, 1.0, m))
    return rows


def row(task, n, seed, level, pressure, density, metrics):
    return {
        "task": task,
        "n": n,
        "seed": seed,
        "level": level,
        "constraint_pressure": pressure,
        "avg_degree_or_density": density,
        "danger_rate": metrics["danger_rate"],
        "IG": metrics["IG"],
        "forced": metrics.get("forced", 0),
        "avg_forced_per_assignment": (
            metrics.get("forced", 0) / metrics.get("cluster_size", 1)
            if metrics.get("cluster_size", 0) else 0.0
        ),
        "avg_freedom": metrics.get("avg_freedom", 0.0),
        "useful_IG": metrics["useful_IG"],
    }


def summarize(rows):
    out = []
    for task in sorted({r["task"] for r in rows}):
        for level in (4, 5):
            items = [r for r in rows if r["task"] == task and r["level"] == level]
            if not items:
                continue
            out.append({
                "task": task,
                "constraint_pressure": sum(r["constraint_pressure"] for r in items) / len(items),
                "avg_degree_or_density": sum(r["avg_degree_or_density"] for r in items) / len(items),
                "level": level,
                "danger_rate": sum(r["danger_rate"] for r in items) / len(items),
                "IG": sum(r["IG"] for r in items) / len(items),
                "avg_forced_per_assignment": sum(r["avg_forced_per_assignment"] for r in items) / len(items),
                "avg_freedom": sum(r["avg_freedom"] for r in items) / len(items),
            })
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--tasks", nargs="*", default=[
        "IndependentSet", "Clique", "HamiltonianPath", "SetCover", "ExactCover", "NQueens"
    ])
    parser.add_argument("--avg-degree", type=float, default=4.0)
    parser.add_argument("--clique-density", type=float, default=0.08)
    parser.add_argument("--set-ratio", type=float, default=1.5)
    parser.add_argument("--set-size", type=float, default=12)
    parser.add_argument("--sample-units", type=int, default=500)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--top-neighbors", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="np_geometry_map_new_tasks")
    args = parser.parse_args()

    started = time.perf_counter()
    rows = []
    for i in range(args.seeds):
        seed = args.seed + args.n * 1000 + i
        if "IndependentSet" in args.tasks:
            rows.extend(independent_set_task(args.n, args, seed))
        if "Clique" in args.tasks:
            rows.extend(clique_task(args.n, args, seed))
        if "HamiltonianPath" in args.tasks:
            rows.extend(hamiltonian_task(args.n, args, seed))
        if "SetCover" in args.tasks:
            rows.extend(set_cover_like_task("SetCover", args.n, args, seed))
        if "ExactCover" in args.tasks:
            rows.extend(set_cover_like_task("ExactCover", args.n, args, seed + 77, exact=True))
        if "NQueens" in args.tasks:
            rows.extend(nqueens_task(args.n, args, seed))
    summary = summarize(rows)
    write_csv(args.out_prefix + "_details.csv", rows)
    write_csv(args.out_prefix + "_summary.csv", summary)
    print(f"runtime_seconds={time.perf_counter() - started:.2f}")
    for r in summary:
        print(
            f"{r['task']} level={r['level']} pressure={r['constraint_pressure']:.4f} "
            f"danger={r['danger_rate']:.4f} IG={r['IG']:.2f}"
        )


if __name__ == "__main__":
    main()
