#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Filtered removal-memory probe for SAT.

Compares:
    baseline clusters from clause co-occurrence
    filtered_memory clusters from co-occurrence + high-quality forced chains

Memory rule:
    memory_edge_weight = useful_IG * (1 - danger_rate)

Memory chains are also recursively compressed by overlap:
    similar chains share variables, so their union adds stronger pair edges.
"""

import argparse
import csv
import random
from collections import Counter
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat
from sat_removal_memory_probe import (
    add_memory_edges,
    base_pair_counts,
    build_level_from_counts,
    evaluate_unit,
)


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def polarity_assignment(formula):
    pos = Counter()
    neg = Counter()
    for clause in formula:
        for lit in clause:
            if lit > 0:
                pos[lit] += 1
            else:
                neg[-lit] += 1
    return {var: pos[var] >= neg[var] for var in set(pos) | set(neg)}


def compress_memory_chains(chains, max_chain_size):
    compressed = list(chains)
    used = [False] * len(chains)
    for i, chain_a in enumerate(chains):
        if used[i]:
            continue
        vars_a, weight_a = chain_a
        merged_vars = set(vars_a)
        merged_weight = weight_a
        used[i] = True
        for j in range(i + 1, len(chains)):
            if used[j]:
                continue
            vars_b, weight_b = chains[j]
            if not (merged_vars & vars_b):
                continue
            if len(merged_vars | vars_b) > max_chain_size:
                continue
            merged_vars |= vars_b
            merged_weight += weight_b
            used[j] = True
        compressed.append((merged_vars, merged_weight))
    return compressed[-len(chains):] if len(compressed) > len(chains) * 2 else compressed


def add_chain_pair_edges(memory_counts, chains):
    for vars_, weight in chains:
        vars_sorted = sorted(vars_)
        int_weight = max(1, round(weight))
        for i in range(len(vars_sorted)):
            for j in range(i + 1, len(vars_sorted)):
                memory_counts[(vars_sorted[i], vars_sorted[j])] += int_weight


def chain_from_reasons(chosen_unit, reasons):
    chosen = set(chosen_unit)
    chains = []
    for reason in reasons:
        chain = set(chosen)
        chain.add(reason["forced_var"])
        chain.update(reason["reason_vars"])
        chains.append(chain)
    return chains


def run_formula(n_vars, n_clauses, args, seed, mode):
    rng = random.Random(seed + (303 if mode == "baseline" else 909))
    formula = sat.generate_random_k_sat(n_vars, n_clauses, 3, seed)
    base_counts = base_pair_counts(formula)
    memory_counts = Counter()
    memory_chains = []
    units = [[v] for v in range(1, n_vars + 1)]
    polarity = polarity_assignment(formula)
    rows = []

    for level in range(1, args.max_levels + 1):
        combined = Counter(base_counts)
        if mode == "filtered_memory":
            add_chain_pair_edges(memory_counts, memory_chains)
            for key, value in memory_counts.items():
                combined[key] += value

        units = build_level_from_counts(
            n_vars,
            units,
            combined,
            args.min_weight,
            args.base_max_cluster_size * level,
        )

        candidates = units
        if args.sample_units and len(candidates) > args.sample_units:
            candidates = rng.sample(candidates, args.sample_units)

        best = None
        for unit in candidates:
            metrics = evaluate_unit(formula, n_vars, unit, polarity)
            key = (-metrics["useful_IG"], -metrics["IG"], metrics["danger_rate"], -len(unit))
            if best is None or key < best[0]:
                best = (key, unit, metrics)
        _, chosen_unit, metrics = best

        if mode == "filtered_memory":
            quality = metrics["useful_IG"] * (1.0 - metrics["danger_rate"])
            if quality >= args.min_memory_quality and not metrics["conflict"]:
                new_chains = [
                    (chain, quality)
                    for chain in chain_from_reasons(chosen_unit, metrics["reasons"])
                    if len(chain) <= args.max_memory_chain_size
                ]
                memory_chains.extend(new_chains)
                memory_chains = compress_memory_chains(
                    memory_chains,
                    args.max_memory_chain_size * level,
                )
                add_memory_edges(
                    memory_counts,
                    chosen_unit,
                    metrics["reasons"],
                    max(1, round(quality)),
                )

        rows.append({
            "seed": seed,
            "mode": mode,
            "n_vars": n_vars,
            "n_clauses": n_clauses,
            "level": level,
            "unit_count": len(units),
            "chosen_unit_size": len(chosen_unit),
            "IG": metrics["IG"],
            "forced": metrics["forced"],
            "danger": metrics["danger"],
            "affected": metrics["affected"],
            "danger_rate": metrics["danger_rate"],
            "useful_IG": metrics["useful_IG"],
            "D_pred": n_vars / metrics["useful_IG"] if metrics["useful_IG"] > 0 else "",
            "memory_edges": len(memory_counts),
            "memory_chains": len(memory_chains),
            "conflict": metrics["conflict"],
        })
    return rows


def summarize(rows):
    summary = []
    for mode in sorted({row["mode"] for row in rows}):
        mode_rows = [row for row in rows if row["mode"] == mode]
        for n_vars in sorted({row["n_vars"] for row in mode_rows}):
            n_rows = [row for row in mode_rows if row["n_vars"] == n_vars]
            for level in sorted({row["level"] for row in n_rows}):
                items = [row for row in n_rows if row["level"] == level]
                out = {"mode": mode, "n_vars": n_vars, "level": level, "samples": len(items)}
                for key in [
                    "unit_count",
                    "chosen_unit_size",
                    "IG",
                    "forced",
                    "danger_rate",
                    "useful_IG",
                    "memory_edges",
                    "memory_chains",
                ]:
                    out[f"avg_{key}"] = sum(row[key] for row in items) / len(items)
                out["D_pred"] = n_vars / out["avg_useful_IG"] if out["avg_useful_IG"] > 0 else ""
                out["conflicts"] = sum(1 for row in items if row["conflict"])
                summary.append(out)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[1000, 2000])
    parser.add_argument("--formulas", type=int, default=3)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--max-levels", type=int, default=5)
    parser.add_argument("--min-weight", type=int, default=2)
    parser.add_argument("--base-max-cluster-size", type=int, default=8)
    parser.add_argument("--sample-units", type=int, default=500)
    parser.add_argument("--min-memory-quality", type=float, default=5.0)
    parser.add_argument("--max-memory-chain-size", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_filtered_memory_probe_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT FILTERED MEMORY PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows.extend(run_formula(n_vars, n_clauses, args, seed, "baseline"))
            rows.extend(run_formula(n_vars, n_clauses, args, seed, "filtered_memory"))
        print("  done")

    summary = summarize(rows)
    write_csv(Path(args.out_prefix + "_details.csv"), rows)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary)

    print("\n=== SUMMARY ===")
    for row in summary:
        if row["level"] in (4, 5):
            print(
                f"{row['mode']} n={row['n_vars']} level={row['level']} "
                f"IG={row['avg_IG']:.2f} usefulIG={row['avg_useful_IG']:.2f} "
                f"D={row['D_pred'] if row['D_pred'] == '' else round(row['D_pred'], 2)} "
                f"chains={row['avg_memory_chains']:.1f}"
            )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
