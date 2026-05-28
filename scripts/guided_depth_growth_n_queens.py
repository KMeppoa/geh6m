#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Measure how guided_n depth grows on N-Queens.

This is a medium task family: guided_1 usually is not enough, and deeper LG
can improve success.
"""

import argparse
import csv
import json
from pathlib import Path

import n_queens_lg_test as nq


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_one(n, depth, branch_cap, max_steps):
    mode = "greedy_LG" if depth == 1 else f"lookahead_LG_{depth}"
    result = nq.search(n, mode, True, depth, max_steps, branch_cap)
    verified = nq.verify(n, result.queens)
    return {
        "mode": mode,
        "success": result.success and verified,
        "status": result.status if verified or not result.success else "FALSE_SUCCESS",
        "decision_steps": result.metrics.get("decision_steps", 0),
        "forced_steps": result.metrics.get("forced_steps", 0),
        "score_calls": result.metrics.get("score_calls", 0),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[8, 9, 10, 11, 12])
    parser.add_argument("--depths", type=int, nargs="*", default=[1, 2, 3, 4])
    parser.add_argument("--branch-cap", type=int, default=2)
    parser.add_argument("--max-steps-factor", type=int, default=3)
    parser.add_argument("--out-dir", default="experiments/guided_depth_growth_n_queens_step1")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")

    detail_rows = []
    summary_rows = []
    first_rows = []

    print("=== GUIDED DEPTH GROWTH: N-QUEENS ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n in args.sizes:
        first_depth = None
        print(f"N={n}")
        for depth in args.depths:
            row = run_one(n, depth, args.branch_cap, n * args.max_steps_factor)
            detail = {"n": n, "depth": depth, **row}
            detail_rows.append(detail)
            summary_rows.append({
                "n": n,
                "depth": depth,
                "success_rate": 1.0 if row["success"] else 0.0,
                "success": 1 if row["success"] else 0,
                "total": 1,
                "status": row["status"],
                "decision_steps": row["decision_steps"],
                "forced_steps": row["forced_steps"],
                "score_calls": row["score_calls"],
            })
            if row["success"] and first_depth is None:
                first_depth = depth
            print(
                f"  guided_{depth}: {1 if row['success'] else 0}/1 "
                f"decision={row['decision_steps']} forced={row['forced_steps']}"
            )
        first_rows.append({"n": n, "first_depth_100": first_depth if first_depth is not None else ""})
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
