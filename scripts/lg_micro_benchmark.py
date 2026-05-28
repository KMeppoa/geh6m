#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Small staged benchmark for the L/G idea.

This runner is intentionally light for weak PCs. It creates a separate output
folder for every test block, so results do not mix with older experiments.
"""

import argparse
import csv
import importlib.util
import json
from datetime import datetime
from itertools import product
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def brute_force_sat(sat, formula, n_vars):
    for bits in product([False, True], repeat=n_vars):
        assignment = {i + 1: bits[i] for i in range(n_vars)}
        if sat.is_formula_satisfied(formula, assignment, n_vars):
            return True, assignment
    return False, None


def summarize(results):
    by_mode = {}
    for item in results:
        by_mode.setdefault(item["mode"], []).append(item)

    rows = []
    for mode in sorted(by_mode):
        items = by_mode[mode]
        total = len(items)
        success = sum(1 for x in items if x["success"])
        steps = [x["steps"] for x in items]
        success_steps = [x["steps"] for x in items if x["success"]]
        decision_steps = [x.get("decision_steps", 0) for x in items]
        forced_steps = [x.get("forced_steps", 0) for x in items]
        score_calls = [x.get("score_calls", 0) for x in items]
        rows.append({
            "mode": mode,
            "total": total,
            "success": success,
            "fail": total - success,
            "success_rate": success / total if total else 0,
            "avg_steps_all": sum(steps) / total if total else "",
            "avg_steps_success_only": (
                sum(success_steps) / len(success_steps) if success_steps else ""
            ),
            "avg_decision_steps": sum(decision_steps) / total if total else "",
            "avg_forced_steps": sum(forced_steps) / total if total else "",
            "avg_score_calls": sum(score_calls) / total if total else "",
        })
    return rows


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_labyrinth_micro(
    out_dir,
    maps,
    trials_per_map,
    size,
    max_steps,
    seed,
    guided_depths,
    dynamic_guided,
    max_guided_depth,
):
    labmod = load_module(
        "dynamic_l_labyrinth_test_v2",
        ROOT / "dynamic_l_labyrinth_test_v2" / "dynamic_l_labyrinth_test_v2.py",
    )

    results = []
    logs = []
    bfs_rows = []

    for i in range(maps):
        map_seed = seed + i
        lab = labmod.DynamicLLabyrinth(size=size, seed=map_seed, wall_density=0.25)
        bfs_path = labmod.bfs_state_search(lab)
        bfs_rows.append({
            "map_seed": map_seed,
            "bfs_has_path": bfs_path is not None,
            "bfs_path_len": len(bfs_path) if bfs_path is not None else "",
        })

        for trial in range(trials_per_map):
            random_seed = seed * 1_000_000 + map_seed * 1000 + trial
            rnd = labmod.random_search(
                lab,
                map_seed=map_seed,
                max_steps=max_steps,
                seed=random_seed,
            )
            results.append({
                "case_id": f"map_{map_seed}_trial_{trial}",
                "map_seed": map_seed,
                "mode": rnd.mode,
                "success": rnd.success,
                "steps": rnd.steps,
                "path_len": len(rnd.path),
            })
            if len(logs) < 20:
                logs.append(rnd.__dict__)

        if not dynamic_guided:
            for depth in guided_depths:
                guided = labmod.guided_lookahead_search(
                    lab,
                    map_seed=map_seed,
                    lookahead_depth=depth,
                    max_steps=max_steps,
                )
                results.append({
                    "case_id": f"map_{map_seed}_guided_{depth}",
                    "map_seed": map_seed,
                    "mode": guided.mode,
                    "success": guided.success,
                    "steps": guided.steps,
                    "path_len": len(guided.path),
                })
                if len(logs) < 20:
                    logs.append(guided.__dict__)

    if dynamic_guided:
        stop_depth = None
        depth_rows = []
        guided_by_depth = {}
        for depth in range(1, max_guided_depth + 1):
            depth_results = []
            for item in bfs_rows:
                map_seed = item["map_seed"]
                lab = labmod.DynamicLLabyrinth(size=size, seed=map_seed, wall_density=0.25)
                guided = labmod.guided_lookahead_search(
                    lab,
                    map_seed=map_seed,
                    lookahead_depth=depth,
                    max_steps=max_steps,
                )
                row = {
                    "case_id": f"map_{map_seed}_guided_{depth}",
                    "map_seed": map_seed,
                    "mode": guided.mode,
                    "success": guided.success,
                    "steps": guided.steps,
                    "path_len": len(guided.path),
                }
                results.append(row)
                depth_results.append(row)
                if len(logs) < 20:
                    logs.append(guided.__dict__)

            guided_by_depth[depth] = depth_results
            items = depth_results
            total = len(items)
            success = sum(1 for x in items if x["success"])
            success_rate = success / total if total else 0
            depth_rows.append({
                "depth": depth,
                "total": total,
                "success": success,
                "fail": total - success,
                "success_rate": success_rate,
            })
            if success_rate >= 1.0:
                stop_depth = depth
                break

        transition_rows = []
        first_success_rows = []
        map_seeds = [item["map_seed"] for item in bfs_rows]

        for depth in range(1, max(guided_by_depth.keys())):
            current = {
                item["map_seed"]: item
                for item in guided_by_depth.get(depth, [])
            }
            nxt = {
                item["map_seed"]: item
                for item in guided_by_depth.get(depth + 1, [])
            }

            fixed = 0
            broken = 0
            stayed_success = 0
            stayed_fail = 0

            for map_seed in map_seeds:
                if map_seed not in current or map_seed not in nxt:
                    continue
                cur_success = current[map_seed]["success"]
                next_success = nxt[map_seed]["success"]

                if not cur_success and next_success:
                    fixed += 1
                elif cur_success and not next_success:
                    broken += 1
                elif cur_success and next_success:
                    stayed_success += 1
                else:
                    stayed_fail += 1

            total = fixed + broken + stayed_success + stayed_fail
            transition_rows.append({
                "from_depth": depth,
                "to_depth": depth + 1,
                "total": total,
                "fixed_by_next": fixed,
                "broken_by_next": broken,
                "stayed_success": stayed_success,
                "stayed_fail": stayed_fail,
                "net_gain": fixed - broken,
            })

        for map_seed in map_seeds:
            first_depth = None
            for depth in sorted(guided_by_depth):
                rows = [
                    item
                    for item in guided_by_depth[depth]
                    if item["map_seed"] == map_seed
                ]
                if rows and rows[0]["success"]:
                    first_depth = depth
                    break

            first_success_rows.append({
                "map_seed": map_seed,
                "first_success_depth": first_depth if first_depth is not None else "",
                "solved_within_limit": first_depth is not None,
            })

        write_csv(
            out_dir / "guided_depth_curve.csv",
            depth_rows,
            ["depth", "total", "success", "fail", "success_rate"],
        )
        write_csv(
            out_dir / "guided_depth_transitions.csv",
            transition_rows,
            [
                "from_depth",
                "to_depth",
                "total",
                "fixed_by_next",
                "broken_by_next",
                "stayed_success",
                "stayed_fail",
                "net_gain",
            ],
        )
        write_csv(
            out_dir / "guided_first_success_by_map.csv",
            first_success_rows,
            ["map_seed", "first_success_depth", "solved_within_limit"],
        )
        write_json(
            out_dir / "guided_dynamic_result.json",
            {
                "reached_100_percent": stop_depth is not None,
                "first_100_percent_depth": stop_depth,
                "max_guided_depth": max_guided_depth,
            },
        )

    summary_rows = summarize(results)
    write_csv(
        out_dir / "summary_by_mode.csv",
        summary_rows,
        [
            "mode",
            "total",
            "success",
            "fail",
            "success_rate",
            "avg_steps_all",
            "avg_steps_success_only",
            "avg_decision_steps",
            "avg_forced_steps",
            "avg_score_calls",
        ],
    )
    write_csv(
        out_dir / "summary_by_case.csv",
        results,
        ["case_id", "map_seed", "mode", "success", "steps", "path_len"],
    )
    write_csv(
        out_dir / "bfs_control.csv",
        bfs_rows,
        ["map_seed", "bfs_has_path", "bfs_path_len"],
    )
    write_json(out_dir / "logs_sample.json", logs)
    return summary_rows


def run_sat_micro(out_dir, formulas, sizes, seed, branch_cap, brute_force_max_vars):
    sat = load_module("sat_lg_v5", ROOT / "sat_lg_test_v5_fast_parallel_cpu.py")

    results = []
    logs = []
    validation_rows = []

    for n_vars in sizes:
        n_clauses = max(1, int(round(n_vars * 4.0)))
        k = min(3, n_vars)
        max_steps = n_vars

        for i in range(formulas):
            formula_seed = seed + n_vars * 10_000 + i
            formula = sat.generate_random_k_sat(n_vars, n_clauses, k, formula_seed)
            brute_checked = n_vars <= brute_force_max_vars
            brute_ok = None
            if brute_checked:
                brute_ok, _ = brute_force_sat(sat, formula, n_vars)
            dpll = sat.dpll_control(formula, n_vars, formula_seed, max_nodes=100_000)

            validation_rows.append({
                "formula_seed": formula_seed,
                "n_vars": n_vars,
                "n_clauses": n_clauses,
                "brute_checked": brute_checked,
                "brute_sat": brute_ok,
                "dpll_success": dpll.success,
                "dpll_matches_brute": (brute_ok == dpll.success) if brute_checked else "",
            })

            modes = [
                dpll,
                sat.random_search_sat(
                    formula,
                    n_vars,
                    formula_seed,
                    max_steps=max_steps,
                    seed=seed * 1_000_000 + formula_seed,
                ),
                sat.search_sat(
                    formula,
                    n_vars,
                    formula_seed,
                    mode="greedy_L",
                    score_kind="L",
                    lookahead_depth=1,
                    max_steps=max_steps,
                    branch_cap=branch_cap,
                ),
                sat.search_sat(
                    formula,
                    n_vars,
                    formula_seed,
                    mode="greedy_LG",
                    score_kind="LG",
                    lookahead_depth=1,
                    max_steps=max_steps,
                    branch_cap=branch_cap,
                ),
                sat.search_sat(
                    formula,
                    n_vars,
                    formula_seed,
                    mode="lookahead_L_2",
                    score_kind="L",
                    lookahead_depth=2,
                    max_steps=max_steps,
                    branch_cap=branch_cap,
                ),
                sat.search_sat(
                    formula,
                    n_vars,
                    formula_seed,
                    mode="lookahead_LG_2",
                    score_kind="LG",
                    lookahead_depth=2,
                    max_steps=max_steps,
                    branch_cap=branch_cap,
                ),
            ]

            for result in modes:
                verified = sat.is_formula_satisfied(formula, result.assignment, n_vars)
                results.append({
                    "case_id": f"sat_n{n_vars}_seed_{formula_seed}",
                    "formula_seed": formula_seed,
                    "n_vars": n_vars,
                    "n_clauses": n_clauses,
                    "mode": result.mode,
                    "success": result.success,
                    "direct_verified": verified,
                    "steps": result.steps,
                    "assigned_count": len(result.assignment),
                    "decision_steps": result.metrics.get("decision_steps", ""),
                    "forced_steps": result.metrics.get("forced_steps", ""),
                    "score_calls": result.metrics.get("score_calls", ""),
                    "dpll_nodes": result.metrics.get("dpll_nodes", ""),
                })
                if len(logs) < 20:
                    logs.append(result.__dict__)

    summary_rows = summarize(results)
    write_csv(
        out_dir / "summary_by_mode.csv",
        summary_rows,
        [
            "mode",
            "total",
            "success",
            "fail",
            "success_rate",
            "avg_steps_all",
            "avg_steps_success_only",
            "avg_decision_steps",
            "avg_forced_steps",
            "avg_score_calls",
        ],
    )
    write_csv(
        out_dir / "summary_by_case.csv",
        results,
        [
            "case_id",
            "formula_seed",
            "n_vars",
            "n_clauses",
            "mode",
            "success",
            "direct_verified",
            "steps",
            "assigned_count",
            "decision_steps",
            "forced_steps",
            "score_calls",
            "dpll_nodes",
        ],
    )
    write_csv(
        out_dir / "bruteforce_validation.csv",
        validation_rows,
        [
            "formula_seed",
            "n_vars",
            "n_clauses",
            "brute_checked",
            "brute_sat",
            "dpll_success",
            "dpll_matches_brute",
        ],
    )
    write_json(out_dir / "logs_sample.json", logs)
    return summary_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", default="")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lab-maps", type=int, default=8)
    parser.add_argument("--lab-trials", type=int, default=3)
    parser.add_argument("--lab-size", type=int, default=8)
    parser.add_argument("--lab-max-steps", type=int, default=120)
    parser.add_argument("--lab-guided-depths", default="1,2,3")
    parser.add_argument("--lab-dynamic-guided", action="store_true")
    parser.add_argument("--lab-max-guided-depth", type=int, default=8)
    parser.add_argument("--sat-formulas", type=int, default=12)
    parser.add_argument("--sat-sizes", default="6,8,10")
    parser.add_argument("--branch-cap", type=int, default=8)
    parser.add_argument("--brute-force-max-vars", type=int, default=16)
    args = parser.parse_args()

    run_id = args.run_name.strip() or datetime.now().strftime("micro_%Y%m%d_%H%M%S")
    run_dir = ensure_dir(ROOT / "experiments" / run_id)
    lab_dir = ensure_dir(run_dir / "01_labyrinth_micro")
    sat_dir = ensure_dir(run_dir / "02_sat_micro")

    config = {
        "seed": args.seed,
        "lab_maps": args.lab_maps,
        "lab_trials": args.lab_trials,
        "lab_size": args.lab_size,
        "lab_max_steps": args.lab_max_steps,
        "lab_guided_depths": args.lab_guided_depths,
        "lab_dynamic_guided": args.lab_dynamic_guided,
        "lab_max_guided_depth": args.lab_max_guided_depth,
        "sat_formulas": args.sat_formulas,
        "sat_sizes": args.sat_sizes,
        "branch_cap": args.branch_cap,
        "brute_force_max_vars": args.brute_force_max_vars,
    }
    write_json(run_dir / "config.json", config)

    print(f"Run folder: {run_dir}")
    print("Running 01_labyrinth_micro...")
    guided_depths = [
        int(x.strip())
        for x in args.lab_guided_depths.split(",")
        if x.strip()
    ]
    lab_summary = run_labyrinth_micro(
        lab_dir,
        maps=args.lab_maps,
        trials_per_map=args.lab_trials,
        size=args.lab_size,
        max_steps=args.lab_max_steps,
        seed=args.seed,
        guided_depths=guided_depths,
        dynamic_guided=args.lab_dynamic_guided,
        max_guided_depth=args.lab_max_guided_depth,
    )
    print("Labyrinth summary:")
    for row in lab_summary:
        print(row)

    print()
    print("Running 02_sat_micro...")
    sat_sizes = [int(x.strip()) for x in args.sat_sizes.split(",") if x.strip()]
    sat_summary = run_sat_micro(
        sat_dir,
        formulas=args.sat_formulas,
        sizes=sat_sizes,
        seed=args.seed,
        branch_cap=args.branch_cap,
        brute_force_max_vars=args.brute_force_max_vars,
    )
    print("SAT summary:")
    for row in sat_summary:
        print(row)

    print()
    print("Done.")
    print(f"Results saved in: {run_dir}")


if __name__ == "__main__":
    main()
