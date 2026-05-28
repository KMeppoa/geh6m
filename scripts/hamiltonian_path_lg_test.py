#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L/G experiment for Hamiltonian Path.

Task:
    Find a path that visits every vertex exactly once.

L:
    Local score: path length, endpoint options, repeated vertices.

G:
    Global propagation/pruning:
        - a vertex cannot be used twice;
        - the current endpoint must still have a way forward;
        - unused vertices must stay reachable from the endpoint;
        - isolated unused vertices make the branch dead.
"""

import argparse
import csv
import json
import random
from collections import deque
from dataclasses import dataclass, field
from math import inf
from pathlib import Path


@dataclass
class RunResult:
    graph_seed: int
    mode: str
    status: str
    success: bool
    path: list
    metrics: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)


def generate_planted_hamiltonian(n_vertices, edge_prob, seed):
    rng = random.Random(seed)
    vertices = list(range(n_vertices))
    rng.shuffle(vertices)
    edges = set()
    adjacency = {v: set() for v in range(n_vertices)}

    for a, b in zip(vertices, vertices[1:]):
        edge = tuple(sorted((a, b)))
        edges.add(edge)
        adjacency[a].add(b)
        adjacency[b].add(a)

    for i in range(n_vertices):
        for j in range(i + 1, n_vertices):
            if (i, j) in edges:
                continue
            if rng.random() < edge_prob:
                edges.add((i, j))
                adjacency[i].add(j)
                adjacency[j].add(i)

    return edges, adjacency, vertices


def verify_path(path, adjacency, n_vertices):
    if len(path) != n_vertices:
        return False
    if len(set(path)) != n_vertices:
        return False
    for a, b in zip(path, path[1:]):
        if b not in adjacency[a]:
            return False
    return True


def path_conflicts(path):
    return len(path) - len(set(path))


def endpoint(path):
    return path[-1] if path else None


def possible_actions(path, adjacency, n_vertices):
    used = set(path)
    if not path:
        return list(range(n_vertices))
    end = endpoint(path)
    return sorted(v for v in adjacency[end] if v not in used)


def reachable_unused_from_endpoint(path, adjacency, n_vertices):
    used = set(path)
    unused = set(range(n_vertices)) - used
    if not unused:
        return True
    if not path:
        return True
    start = endpoint(path)
    seen = {start}
    queue = deque([start])
    allowed = unused | {start}
    while queue:
        node = queue.popleft()
        for nbr in adjacency[node]:
            if nbr in allowed and nbr not in seen:
                seen.add(nbr)
                queue.append(nbr)
    return unused <= seen


def unused_isolated_count(path, adjacency, n_vertices):
    used = set(path)
    unused = set(range(n_vertices)) - used
    count = 0
    for v in unused:
        if not any(nbr not in used or nbr == endpoint(path) for nbr in adjacency[v]):
            count += 1
    return count


def stats(path, adjacency, n_vertices):
    used = set(path)
    unused = n_vertices - len(used)
    actions = possible_actions(path, adjacency, n_vertices)
    return {
        "length": len(path),
        "unused": unused,
        "conflicts": path_conflicts(path),
        "endpoint_options": len(actions),
        "isolated_unused": unused_isolated_count(path, adjacency, n_vertices),
        "reachable": reachable_unused_from_endpoint(path, adjacency, n_vertices),
    }


def score_l(path, adjacency, n_vertices):
    st = stats(path, adjacency, n_vertices)
    return (
        st["conflicts"] * 1_000_000
        + (100_000 if path and st["endpoint_options"] == 0 and st["unused"] else 0)
        + st["unused"] * 100
        - st["length"] * 8
        + st["endpoint_options"] * 2
    )


def propagate_check(path, adjacency, n_vertices):
    st = stats(path, adjacency, n_vertices)
    if st["conflicts"]:
        return True, 0
    if st["isolated_unused"]:
        return True, 0
    if not st["reachable"]:
        return True, 0
    if path and st["endpoint_options"] == 0 and st["unused"]:
        return True, 0
    forced = 1 if path and st["endpoint_options"] == 1 and st["unused"] else 0
    return False, forced


def apply_g(path, adjacency, n_vertices, max_forced=10000):
    path = list(path)
    forced_count = 0
    while forced_count < max_forced:
        conflict, forced = propagate_check(path, adjacency, n_vertices)
        if conflict:
            return True, path, forced_count
        if forced <= 0:
            return False, path, forced_count
        actions = possible_actions(path, adjacency, n_vertices)
        if len(actions) != 1:
            return False, path, forced_count
        path.append(actions[0])
        forced_count += 1
        if verify_path(path, adjacency, n_vertices):
            return False, path, forced_count
    return False, path, forced_count


def score_lg(path, adjacency, n_vertices):
    conflict, propagated, forced = apply_g(path, adjacency, n_vertices)
    if conflict:
        return 10_000_000
    st = stats(propagated, adjacency, n_vertices)
    return (
        st["unused"] * 100
        - st["length"] * 12
        + st["endpoint_options"]
        - forced * 30
    )


def evaluate_future(path, adjacency, n_vertices, depth, score_kind, branch_cap, score_counter):
    if verify_path(path, adjacency, n_vertices):
        return -1_000_000

    base = score_lg(path, adjacency, n_vertices) if score_kind == "LG" else score_l(path, adjacency, n_vertices)
    score_counter[0] += 1
    if base >= 10_000_000 or depth <= 0:
        return base

    ranked = []
    for action in possible_actions(path, adjacency, n_vertices):
        new_path = path + [action]
        local = score_lg(new_path, adjacency, n_vertices) if score_kind == "LG" else score_l(new_path, adjacency, n_vertices)
        score_counter[0] += 1
        ranked.append((local, action, new_path))
    ranked.sort(key=lambda item: (item[0], item[1]))

    best = inf
    for _, _, new_path in ranked[:branch_cap]:
        best = min(
            best,
            evaluate_future(new_path, adjacency, n_vertices, depth - 1, score_kind, branch_cap, score_counter),
        )
    return best


def run_solver(adjacency, n_vertices, mode, max_steps, branch_cap):
    path = []
    logs = []
    decision_steps = 0
    forced_steps = 0
    score_calls = 0

    if mode == "greedy_L":
        score_kind, depth = "L", 1
    elif mode == "greedy_LG":
        score_kind, depth = "LG", 1
    elif mode.startswith("adaptive_LG_"):
        parts = mode.split("_")
        score_kind, depth = "ADAPTIVE", int(parts[2])
        adaptive_threshold = int(parts[3])
    elif mode.startswith("lookahead_LG_"):
        score_kind, depth = "LG", int(mode.rsplit("_", 1)[1])
    elif mode.startswith("lookahead_L_"):
        score_kind, depth = "L", int(mode.rsplit("_", 1)[1])
    else:
        raise ValueError(f"Unknown mode: {mode}")

    for step in range(max_steps):
        use_g_now = score_kind == "LG"
        if score_kind == "ADAPTIVE":
            l_count = len(possible_actions(path, adjacency, n_vertices))
            use_g_now = l_count >= adaptive_threshold

        if use_g_now:
            conflict, propagated, forced = apply_g(path, adjacency, n_vertices)
            path = propagated
            forced_steps += forced
            if conflict:
                return RunResult(0, mode, "FAILED_TO_FIND", False, path, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)

        if verify_path(path, adjacency, n_vertices):
            return RunResult(0, mode, "SAT_FOUND", True, path, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)

        actions = possible_actions(path, adjacency, n_vertices)
        if not actions:
            break

        ranked = []
        for action in actions:
            new_path = path + [action]
            counter = [0]
            future_kind = "LG" if use_g_now else "L"
            future = evaluate_future(new_path, adjacency, n_vertices, depth - 1, future_kind, branch_cap, counter)
            score_calls += counter[0]
            ranked.append((future, action))
        ranked.sort(key=lambda item: (item[0], item[1]))
        path.append(ranked[0][1])
        decision_steps += 1
        logs.append({"step": step, "chosen": ranked[0][1], "score": ranked[0][0], "stats": stats(path, adjacency, n_vertices)})

    success = verify_path(path, adjacency, n_vertices)
    return RunResult(0, mode, "SAT_FOUND" if success else "FAILED_TO_FIND", success, path, {"decision_steps": decision_steps, "forced_steps": forced_steps, "score_calls": score_calls}, logs)


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
            "avg_decision_steps": sum(r.metrics["decision_steps"] for r in successes) / len(successes) if successes else "",
            "avg_forced_steps": sum(r.metrics["forced_steps"] for r in successes) / len(successes) if successes else "",
            "avg_score_calls": sum(r.metrics["score_calls"] for r in subset) / len(subset) if subset else "",
        })
    return rows


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=30)
    parser.add_argument("--vertices", type=int, default=16)
    parser.add_argument("--edge-prob", type=float, default=0.18)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--lookaheads", type=int, nargs="*", default=[2, 3])
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--adaptive-thresholds", type=int, nargs="*", default=[2, 3, 4])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="hamiltonian_path_step1_small")
    args = parser.parse_args()

    modes = ["greedy_L", "greedy_LG"]
    for depth in args.lookaheads:
        modes.extend([f"lookahead_L_{depth}", f"lookahead_LG_{depth}"])
    for threshold in args.adaptive_thresholds:
        modes.append(f"adaptive_LG_1_{threshold}")

    print("=== CONFIG HAMILTONIAN PATH LG ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    results = []
    case_rows = []
    false_success = 0

    for case_idx in range(args.cases):
        graph_seed = args.seed + case_idx + 1
        _, adjacency, planted = generate_planted_hamiltonian(args.vertices, args.edge_prob, graph_seed)
        row = {"case": case_idx, "seed": graph_seed, "planted_path": " ".join(map(str, planted))}
        for mode in modes:
            result = run_solver(adjacency, args.vertices, mode, args.max_steps, args.branch_cap)
            result.graph_seed = graph_seed
            verified = verify_path(result.path, adjacency, args.vertices)
            if result.success and not verified:
                false_success += 1
                result.status = "FALSE_SUCCESS"
                result.success = False
            results.append(result)
            row[f"{mode}_status"] = result.status
            row[f"{mode}_success"] = result.success
            row[f"{mode}_decision_steps"] = result.metrics["decision_steps"]
            row[f"{mode}_forced_steps"] = result.metrics["forced_steps"]
            row[f"{mode}_score_calls"] = result.metrics["score_calls"]
        case_rows.append(row)
        if (case_idx + 1) == 1 or (case_idx + 1) % 10 == 0 or (case_idx + 1) == args.cases:
            print(f"done {case_idx + 1}/{args.cases}, seed={graph_seed}")

    summary = summarize(results)
    write_csv(Path(args.out_prefix + "_summary_by_mode.csv"), summary)
    write_csv(Path(args.out_prefix + "_summary_by_case.csv"), case_rows)
    with open(args.out_prefix + "_logs.jsonl", "w", encoding="utf-8") as f:
        for result in results[:40]:
            f.write(json.dumps({
                "graph_seed": result.graph_seed,
                "mode": result.mode,
                "status": result.status,
                "success": result.success,
                "path": result.path,
                "metrics": result.metrics,
                "logs": result.logs,
            }, ensure_ascii=False) + "\n")

    print("\n=== SUMMARY BY MODE ===")
    for row in summary:
        print()
        for key, value in row.items():
            print(f"{key}: {value}")
    print("\n=== CHECKS ===")
    print(f"false_success: {false_success}")
    print("\n=== FILES WRITTEN ===")
    print(args.out_prefix + "_summary_by_mode.csv")
    print(args.out_prefix + "_summary_by_case.csv")
    print(args.out_prefix + "_logs.jsonl")


if __name__ == "__main__":
    main()
