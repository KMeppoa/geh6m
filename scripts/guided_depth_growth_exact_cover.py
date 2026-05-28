#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Measure how guided_n depth grows on a simple planted Exact Cover family.

This test asks:
    as the task size grows, what is the first LG depth that reaches 100%?

It writes all outputs into one experiment folder so results do not mix with
other checkpoints.
"""

import argparse
import csv
import json
from pathlib import Path

import exact_cover_lg_test as ec


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_case(universe_size, n_sets, solution_size, seed, depth, max_steps, branch_cap, profile):
    universe, sets = ec.generate_exact_cover(
        universe_size, n_sets, solution_size, seed, profile
    )
    mode = "greedy_LG" if depth == 1 else f"lookahead_LG_{depth}"
    result = ec.run_solver(universe, sets, mode, max_steps, branch_cap)
    verified = ec.verify_exact_cover(universe, sets, result.chosen)
    success = result.success and verified
    return {
        "success": success,
        "status": result.status if verified or not result.success else "FALSE_SUCCESS",
        "decision_steps": result.metrics.get("decision_steps", 0),
        "forced_steps": result.metrics.get("forced_steps", 0),
        "score_calls": result.metrics.get("score_calls", 0),
        "chosen_count": len(result.chosen),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=10)
    parser.add_argument("--sizes", type=int, nargs="*", default=[12, 18, 24, 30])
    parser.add_argument("--depths", type=int, nargs="*", default=[1, 2, 3, 4])
    parser.add_argument("--sets-factor", type=float, default=1.75)
    parser.add_argument("--solution-factor", type=float, default=0.25)
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--branch-cap", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", choices=["random", "trap"], default="trap")
    parser.add_argument("--out-dir", default="experiments/guided_depth_growth_exact_cover")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    config_path = out_dir / "config.json"
    config_path.write_text(json.dumps(vars(args), indent=2), encoding="utf-8")

    detail_rows = []
    summary_rows = []

    print("=== GUIDED DEPTH GROWTH: EXACT COVER ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for size in args.sizes:
        n_sets = max(size + 1, int(round(size * args.sets_factor)))
        solution_size = max(2, int(round(size * args.solution_factor)))
        print(f"size={size}, sets={n_sets}, solution_size={solution_size}")

        first_100_depth = None
        for depth in args.depths:
            successes = 0
            false_success = 0
            decisions = 0
            forced = 0
            score_calls = 0

            for case_idx in range(args.cases):
                seed = args.seed + size * 1000 + depth * 100 + case_idx
                row = run_case(
                    size, n_sets, solution_size, seed, depth,
                    args.max_steps, args.branch_cap, args.profile,
                )
                successes += 1 if row["success"] else 0
                false_success += 1 if row["status"] == "FALSE_SUCCESS" else 0
                decisions += row["decision_steps"]
                forced += row["forced_steps"]
                score_calls += row["score_calls"]
                detail_rows.append({
                    "size": size,
                    "sets": n_sets,
                    "solution_size": solution_size,
                    "depth": depth,
                    "case": case_idx,
                    "seed": seed,
                    **row,
                })

            success_rate = successes / args.cases
            if success_rate == 1.0 and first_100_depth is None:
                first_100_depth = depth
            summary_rows.append({
                "size": size,
                "sets": n_sets,
                "solution_size": solution_size,
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

        print(f"  first_depth_100={first_100_depth}")
        print()

    first_rows = []
    for size in args.sizes:
        rows = [row for row in summary_rows if row["size"] == size and row["success_rate"] == 1.0]
        first = min((row["depth"] for row in rows), default="")
        first_rows.append({"size": size, "first_depth_100": first})

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
