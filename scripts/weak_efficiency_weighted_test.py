#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weighted L/G tests for weak-efficiency tasks.

Formula:
    score(x,a) = (1 - w_g) * L(x,a) + w_g * G(x,a)

Purpose:
    Check whether a cautious G weight improves tasks where full LG had low E.
"""

import argparse
import csv
from math import inf
from pathlib import Path

import set_cover_lg_test as sc
import vertex_cover_lg_test as vc


def save_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows):
    out = []
    for mode in sorted({row["mode"] for row in rows}):
        items = [row for row in rows if row["mode"] == mode]
        successes = [row for row in items if row["success"]]
        out.append({
            "mode": mode,
            "total": len(items),
            "success": len(successes),
            "fail": len(items) - len(successes),
            "success_rate": len(successes) / len(items) if items else 0,
            "avg_decision_steps": sum(row["decision_steps"] for row in successes) / len(successes) if successes else "",
            "avg_forced_steps": sum(row["forced_steps"] for row in successes) / len(successes) if successes else "",
            "avg_score_calls": sum(row["score_calls"] for row in items) / len(items) if items else "",
        })
    return out


def set_cover_weighted_score(universe, sets, chosen, k, w_g):
    l_score = sc.score_l(universe, sets, chosen, k)
    g_score = sc.score_lg(universe, sets, chosen, k)
    return (1.0 - w_g) * l_score + w_g * g_score


def set_cover_eval(universe, sets, chosen, k, depth, branch_cap, w_g, score_counter):
    if sc.verify_cover(universe, sets, chosen, k):
        return -1_000_000
    base = set_cover_weighted_score(universe, sets, chosen, k, w_g)
    score_counter[0] += 2
    if base >= 10_000_000 or depth <= 0:
        return base

    ranked = []
    for action in sc.possible_actions(universe, sets, chosen, k):
        new_chosen = chosen + [action]
        score = set_cover_weighted_score(universe, sets, new_chosen, k, w_g)
        score_counter[0] += 2
        ranked.append((score, action, new_chosen))
    ranked.sort(key=lambda item: (item[0], item[1]))

    best = inf
    for _, _, new_chosen in ranked[:branch_cap]:
        best = min(best, set_cover_eval(universe, sets, new_chosen, k, depth - 1, branch_cap, w_g, score_counter))
    return best


def run_set_cover_weighted(universe, sets, k, mode, w_g, depth, max_steps, branch_cap):
    chosen = []
    decision_steps = 0
    forced_steps = 0
    score_counter = [0]

    for _ in range(max_steps):
        if sc.verify_cover(universe, sets, chosen, k):
            return True, chosen, decision_steps, forced_steps, score_counter[0]
        actions = sc.possible_actions(universe, sets, chosen, k)
        if not actions:
            break

        ranked = []
        for action in actions:
            new_chosen = chosen + [action]
            score = set_cover_eval(universe, sets, new_chosen, k, depth - 1, branch_cap, w_g, score_counter)
            ranked.append((score, action))
        ranked.sort(key=lambda item: (item[0], item[1]))
        chosen.append(ranked[0][1])
        decision_steps += 1

    return sc.verify_cover(universe, sets, chosen, k), chosen, decision_steps, forced_steps, score_counter[0]


def run_set_cover(args):
    rows = []
    modes = [
        ("L_depth2", 0.0, 2),
        ("weighted_G_0.1_depth2", 0.1, 2),
        ("weighted_G_0.2_depth2", 0.2, 2),
        ("weighted_G_0.4_depth2", 0.4, 2),
        ("LG_depth2", 1.0, 2),
    ]
    for case_idx in range(args.cases):
        seed = args.seed + case_idx + 1
        universe, sets = sc.generate_set_cover(args.universe, args.sets, args.k, seed, "trap")
        for mode, w_g, depth in modes:
            success, chosen, decisions, forced, score_calls = run_set_cover_weighted(
                universe, sets, args.k, mode, w_g, depth, args.max_steps, args.branch_cap
            )
            rows.append({
                "task": "Set Cover",
                "case": case_idx,
                "seed": seed,
                "mode": mode,
                "w_g": w_g,
                "success": success,
                "verified": sc.verify_cover(universe, sets, chosen, args.k),
                "decision_steps": decisions,
                "forced_steps": forced,
                "score_calls": score_calls,
            })
    return rows


def vertex_weighted_score(edges, state, cover_size, w_g):
    l_score = vc.score_state(edges, state, cover_size, False)
    g_score = vc.score_state(edges, state, cover_size, True)
    return (1.0 - w_g) * l_score + w_g * g_score


def vertex_eval(edges, state, n_vertices, cover_size, depth, branch_cap, w_g, score_counter):
    if vc.verify_cover(edges, state["selected"], cover_size):
        return -1_000_000
    base = vertex_weighted_score(edges, state, cover_size, w_g)
    score_counter[0] += 2
    if base >= 10_000_000 or depth <= 0:
        return base

    ranked = []
    for action in vc.possible_actions(n_vertices, state):
        next_state = vc.apply_action(state, action)
        score = vertex_weighted_score(edges, next_state, cover_size, w_g)
        score_counter[0] += 2
        ranked.append((score, action, next_state))
    ranked.sort(key=lambda item: (item[0], item[1][0], item[1][1]))

    best = inf
    for _, _, next_state in ranked[:branch_cap]:
        best = min(best, vertex_eval(edges, next_state, n_vertices, cover_size, depth - 1, branch_cap, w_g, score_counter))
    return best


def run_vertex_weighted(edges, n_vertices, cover_size, w_g, depth, max_steps, branch_cap):
    state = {"selected": set(), "forbidden": set()}
    decision_steps = 0
    forced_steps = 0
    score_counter = [0]

    for _ in range(max_steps):
        if vc.verify_cover(edges, state["selected"], cover_size):
            return True, state, decision_steps, forced_steps, score_counter[0]
        actions = vc.possible_actions(n_vertices, state)
        if not actions:
            break

        ranked = []
        for action in actions:
            next_state = vc.apply_action(state, action)
            score = vertex_eval(edges, next_state, n_vertices, cover_size, depth - 1, branch_cap, w_g, score_counter)
            ranked.append((score, action, next_state))
        ranked.sort(key=lambda item: (item[0], item[1][0], item[1][1]))
        state = ranked[0][2]
        decision_steps += 1
        if vc.stats(edges, state, cover_size)["over_limit"]:
            break

    return vc.verify_cover(edges, state["selected"], cover_size), state, decision_steps, forced_steps, score_counter[0]


def run_vertex_cover(args):
    rows = []
    modes = [
        ("L_depth2", 0.0, 2),
        ("weighted_G_0.1_depth2", 0.1, 2),
        ("weighted_G_0.2_depth2", 0.2, 2),
        ("weighted_G_0.4_depth2", 0.4, 2),
        ("LG_depth2", 1.0, 2),
    ]
    for case_idx in range(args.cases):
        seed = args.seed + case_idx + 1
        edges, _ = vc.generate_planted_vertex_cover(args.vertices, args.edge_prob, args.cover_size, seed)
        for mode, w_g, depth in modes:
            success, state, decisions, forced, score_calls = run_vertex_weighted(
                edges, args.vertices, args.cover_size, w_g, depth, args.max_steps, args.branch_cap
            )
            rows.append({
                "task": "Vertex Cover",
                "case": case_idx,
                "seed": seed,
                "mode": mode,
                "w_g": w_g,
                "success": success,
                "verified": vc.verify_cover(edges, state["selected"], args.cover_size),
                "decision_steps": decisions,
                "forced_steps": forced,
                "score_calls": score_calls,
            })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["set_cover", "vertex_cover", "both"], default="both")
    parser.add_argument("--cases", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--branch-cap", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--out-prefix", default="weak_weighted_step1")
    parser.add_argument("--universe", type=int, default=24)
    parser.add_argument("--sets", type=int, default=36)
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--vertices", type=int, default=18)
    parser.add_argument("--cover-size", type=int, default=6)
    parser.add_argument("--edge-prob", type=float, default=0.25)
    args = parser.parse_args()

    rows = []
    if args.task in ("set_cover", "both"):
        rows.extend(run_set_cover(args))
    if args.task in ("vertex_cover", "both"):
        rows.extend(run_vertex_cover(args))

    summary = summarize(rows)
    save_csv(Path(args.out_prefix + "_summary_by_mode.csv"), summary)
    save_csv(Path(args.out_prefix + "_summary_by_case.csv"), rows)

    print("=== WEAK WEIGHTED SUMMARY ===")
    for row in summary:
        print(row)
    print("Files written:")
    print(args.out_prefix + "_summary_by_mode.csv")
    print(args.out_prefix + "_summary_by_case.csv")


if __name__ == "__main__":
    main()
