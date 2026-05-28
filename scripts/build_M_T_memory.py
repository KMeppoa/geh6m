#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build M/T memory from completed L/G experiments.

M = measurement/passport of a solved task family:
    difficulty for L, usefulness of G, forced consequences, cost.

T = task-space strategy sequence:
    an ordered list of modes to try on future similar tasks.

This is a first practical prototype of transfer:
    use solved task measurements to recommend a solving sequence for future tasks.
"""

import argparse
import csv
from pathlib import Path


DATASETS = [
    ("SAT", "clean_stats_v5_16x40_summary_by_formula.csv"),
    ("Graph Coloring", "graph_coloring_step2_18x60_summary_by_graph.csv"),
    ("Clique+Independent Set", "graph_is_clique_step2_20x60_summary_by_case.csv"),
    ("Vertex Cover", "vertex_cover_step1_small_summary_by_case.csv"),
    ("Subset Sum", "subset_sum_step1_small_summary_by_case.csv"),
    ("N-Queens", "n_queens_step1_small_summary_by_case.csv"),
    ("Set Cover", "set_cover_step1_trap_summary_by_case.csv"),
    ("Exact Cover", "exact_cover_step1_small_summary_by_case.csv"),
    ("Latin Square", "latin_square_step1_n6_summary_by_case.csv"),
    ("Hamiltonian Path", "hamiltonian_path_step2_sparse_summary_by_case.csv"),
]


def parse_bool(value):
    return str(value).strip().lower() == "true"


def number(row, key):
    value = row.get(key, "")
    return float(value) if value not in ("", None) else 0.0


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def normalize_rows(rows):
    if not rows or "mode" in rows[0]:
        return rows

    normalized = []
    success_keys = [key for key in rows[0] if key.endswith("_success")]
    for row in rows:
        for success_key in success_keys:
            mode = success_key[:-len("_success")]
            normalized.append({
                "mode": mode,
                "success": row.get(f"{mode}_success", ""),
                "decision_steps": row.get(f"{mode}_decision_steps", row.get(f"{mode}_steps", 0)),
                "forced_steps": row.get(f"{mode}_forced_steps", 0),
                "score_calls": row.get(f"{mode}_score_calls", 0),
            })
    return normalized


def split_dataset(label, rows):
    if label == "Clique+Independent Set":
        groups = {}
        for task in sorted({row["task"] for row in rows}):
            pretty = "Clique" if task == "clique" else "Independent Set"
            groups[pretty] = [row for row in rows if row["task"] == task]
        return groups
    return {label: rows}


def summarize_mode(rows, mode):
    items = [row for row in rows if row["mode"] == mode]
    total = len(items)
    if total == 0:
        return None
    success = sum(1 for row in items if parse_bool(row["success"]))
    return {
        "mode": mode,
        "total": total,
        "success": success,
        "success_rate": success / total,
        "avg_decision": sum(number(row, "decision_steps") for row in items) / total,
        "avg_forced": sum(number(row, "forced_steps") for row in items) / total,
        "avg_score_calls": sum(number(row, "score_calls") for row in items) / total,
    }


def make_measurement(task_name, rows):
    modes = sorted({
        row["mode"] for row in rows
        if row["mode"] == "greedy_L"
        or row["mode"].startswith("lookahead_L_")
        or row["mode"] == "greedy_LG"
        or row["mode"].startswith("lookahead_LG_")
    })
    summaries = [summarize_mode(rows, mode) for mode in modes]
    summaries = [s for s in summaries if s is not None]

    l_modes = [s for s in summaries if "_LG" not in s["mode"]]
    lg_modes = [s for s in summaries if "_LG" in s["mode"]]

    best_l = max(l_modes, key=lambda s: (s["success_rate"], -s["avg_decision"])) if l_modes else None
    best_lg = max(lg_modes, key=lambda s: (s["success_rate"], -s["avg_decision"])) if lg_modes else None

    if best_l is None or best_lg is None:
        return None, []

    q = 1 - best_l["success_rate"]
    success_gain = best_lg["success_rate"] - best_l["success_rate"]
    decision_gain = best_l["avg_decision"] - best_lg["avg_decision"]
    forced = best_lg["avg_forced"]
    m_score = success_gain + 0.05 * decision_gain + 0.02 * forced
    relative_cost = max(
        0.0,
        (best_lg["avg_score_calls"] - best_l["avg_score_calls"])
        / (1.0 + best_l["avg_score_calls"]),
    )
    normalized_decision_gain = decision_gain / (1.0 + best_l["avg_decision"])
    normalized_forced = forced / (1.0 + best_l["avg_decision"])
    benefit = 3.0 * success_gain + normalized_decision_gain + normalized_forced
    e_efficiency = benefit / (1.0 + relative_cost)

    # Strategy value: success first, then fewer decisions, then fewer score calls.
    strategy_items = []
    for s in summaries:
        cost_penalty = 0.002 * s["avg_decision"] + 0.00001 * s["avg_score_calls"]
        value = s["success_rate"] - cost_penalty
        if "_LG" in s["mode"]:
            value += 0.03
        strategy_items.append({
            "task": task_name,
            "mode": s["mode"],
            "success_rate": s["success_rate"],
            "avg_decision": s["avg_decision"],
            "avg_forced": s["avg_fored"] if "avg_fored" in s else s["avg_forced"],
            "avg_score_calls": s["avg_score_calls"],
            "strategy_value": value,
        })
    strategy_items.sort(key=lambda item: item["strategy_value"], reverse=True)

    t_sequence = " -> ".join(item["mode"] for item in strategy_items[:4])
    measurement = {
        "task": task_name,
        "cases": best_l["total"],
        "best_L_mode": best_l["mode"],
        "best_L_success": best_l["success_rate"],
        "best_L_decision": best_l["avg_decision"],
        "best_L_score_calls": best_l["avg_score_calls"],
        "best_LG_mode": best_lg["mode"],
        "best_LG_success": best_lg["success_rate"],
        "best_LG_decision": best_lg["avg_decision"],
        "best_LG_forced": best_lg["avg_forced"],
        "best_LG_score_calls": best_lg["avg_score_calls"],
        "Q_difficulty": q,
        "M_usefulness_of_G": m_score,
        "E_efficiency": e_efficiency,
        "benefit_B": benefit,
        "relative_cost_C": relative_cost,
        "success_gain": success_gain,
        "decision_gain": decision_gain,
        "T_strategy_sequence": t_sequence,
    }
    return measurement, strategy_items


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-prefix", default="M_T_memory")
    args = parser.parse_args()

    measurements = []
    strategies = []

    for label, path in DATASETS:
        if not Path(path).exists():
            print(f"SKIP missing: {path}")
            continue
        rows = normalize_rows(load_rows(path))
        for task_name, task_rows in split_dataset(label, rows).items():
            measurement, strategy_items = make_measurement(task_name, task_rows)
            if measurement:
                measurements.append(measurement)
                strategies.extend(strategy_items)

    measurements.sort(key=lambda row: (row["E_efficiency"], row["M_usefulness_of_G"], row["Q_difficulty"]), reverse=True)
    write_csv(args.out_prefix + "_measurements.csv", measurements)
    write_csv(args.out_prefix + "_strategies.csv", strategies)

    print("=== M/T MEMORY ===")
    for row in measurements:
        print(
            f"{row['task']}: Q={row['Q_difficulty']:.3f}, "
            f"M={row['M_usefulness_of_G']:.3f}, "
            f"E={row['E_efficiency']:.3f}, "
            f"best_L={row['best_L_mode']}({row['best_L_success']:.3f}), "
            f"best_LG={row['best_LG_mode']}({row['best_LG_success']:.3f}), "
            f"T={row['T_strategy_sequence']}"
        )

    print("Files written:")
    print(args.out_prefix + "_measurements.csv")
    print(args.out_prefix + "_strategies.csv")


if __name__ == "__main__":
    main()
