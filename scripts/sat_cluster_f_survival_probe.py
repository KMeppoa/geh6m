#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cluster F-survival probe for SAT.

L:
    choose a cluster candidate.

G:
    apply cluster assignment + unit propagation.

F:
    survival_score = (satisfied_clauses + unknown_clauses) / total_clauses
                   = 1 - unsat_clauses / total_clauses

Then:
    useful_IG = IG * survival_score
    D = H / useful_IG

This probe does not know the true solution.
"""

import argparse
import csv
import random
from pathlib import Path

import sat_lg_test_v5_fast_parallel_cpu as sat
from sat_compatible_cluster_reliability import (
    build_signed_compatible_clusters,
)


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def clause_status(clause, assignment):
    unknown = False
    for lit in clause:
        var = abs(lit)
        if var not in assignment:
            unknown = True
            continue
        value = assignment[var]
        if (lit > 0 and value) or (lit < 0 and not value):
            return "sat"
    return "unknown" if unknown else "unsat"


def survival_score(formula, assignment):
    sat_count = 0
    unknown_count = 0
    unsat_count = 0
    dangerous_count = 0
    for clause in formula:
        status = clause_status(clause, assignment)
        if status == "sat":
            sat_count += 1
        elif status == "unknown":
            unknown_count += 1
            unassigned = sum(1 for lit in clause if abs(lit) not in assignment)
            if unassigned == 1:
                dangerous_count += 1
        else:
            unsat_count += 1
    total = len(formula)
    live = sat_count + unknown_count
    stability = (
        1.0 - (dangerous_count / unknown_count)
        if unknown_count > 0 else 1.0
    )
    survival = live / total if total else 0.0
    return {
        "sat_clauses": sat_count,
        "unknown_clauses": unknown_count,
        "unsat_clauses": unsat_count,
        "dangerous_clauses": dangerous_count,
        "survival_score": survival,
        "stability_score": stability,
        "R_est": survival * stability,
    }


def evaluate_cluster(formula, n_vars, cluster):
    pre = survival_score(formula, cluster)
    pre_danger = pre["dangerous_clauses"]
    pre_stability = (
        1.0 - (pre_danger / len(formula))
        if formula else 0.0
    )
    conflict, propagated, forced = sat.unit_propagate(formula, cluster, n_vars)
    h_after = len(sat.unassigned_vars(n_vars, propagated))
    ig = n_vars - h_after
    f = survival_score(formula, propagated)
    f["stability_score"] = pre_stability
    f["pre_dangerous_clauses"] = pre_danger
    f["R_est"] = f["survival_score"] * pre_stability
    if conflict:
        # Unit propagation found at least one contradiction even if the final
        # assignment object does not expose all dead clauses.
        f["survival_score"] = min(f["survival_score"], 0.0)
        f["R_est"] = 0.0
    useful_ig = ig * f["R_est"]
    return {
        "IG": ig,
        "forced": forced,
        "conflict": conflict,
        "useful_IG": useful_ig,
        **f,
    }


def choose_best_cluster(formula, n_vars, clusters, sample_clusters, rng):
    candidates = clusters
    if sample_clusters and len(candidates) > sample_clusters:
        candidates = rng.sample(candidates, sample_clusters)

    ranked = []
    for cluster in candidates:
        metrics = evaluate_cluster(formula, n_vars, cluster)
        ranked.append((
            -metrics["useful_IG"],
            -metrics["IG"],
            metrics["conflict"],
            -len(cluster),
            sorted(cluster.items()),
            cluster,
            metrics,
        ))
    ranked.sort(key=lambda item: item[:5])
    return ranked[0][5], ranked[0][6], len(candidates)


def probe_formula(n_vars, n_clauses, args, seed):
    rng = random.Random(seed + 260526)
    formula = sat.generate_random_k_sat(n_vars, n_clauses, 3, seed)
    clusters = build_signed_compatible_clusters(
        formula,
        n_vars,
        args.min_cooccur,
        args.max_cluster_size,
        args.check_unit,
    )
    cluster, metrics, sampled = choose_best_cluster(
        formula, n_vars, clusters, args.sample_clusters, rng
    )
    useful = metrics["useful_IG"]
    return {
        "seed": seed,
        "n_vars": n_vars,
        "n_clauses": n_clauses,
        "ratio": n_clauses / n_vars,
        "cluster_count": len(clusters),
        "sampled_clusters": sampled,
        "chosen_cluster_size": len(cluster),
        "IG": metrics["IG"],
        "R_est_survival": metrics["survival_score"],
        "stability_score": metrics["stability_score"],
        "R_est": metrics["R_est"],
        "useful_IG": useful,
        "D_pred": n_vars / useful if useful > 0 else "",
        "forced": metrics["forced"],
        "sat_clauses": metrics["sat_clauses"],
        "unknown_clauses": metrics["unknown_clauses"],
        "unsat_clauses": metrics["unsat_clauses"],
        "dangerous_clauses": metrics["dangerous_clauses"],
        "pre_dangerous_clauses": metrics["pre_dangerous_clauses"],
        "conflict": metrics["conflict"],
    }


def summarize(rows):
    summary = []
    for n_vars in sorted({row["n_vars"] for row in rows}):
        items = [row for row in rows if row["n_vars"] == n_vars]
        out = {"n_vars": n_vars, "samples": len(items)}
        for key in [
            "cluster_count",
            "chosen_cluster_size",
            "IG",
            "R_est_survival",
            "stability_score",
            "R_est",
            "useful_IG",
            "forced",
            "sat_clauses",
            "unknown_clauses",
            "unsat_clauses",
            "dangerous_clauses",
            "pre_dangerous_clauses",
        ]:
            out[f"avg_{key}"] = sum(row[key] for row in items) / len(items)
        out["D_pred"] = n_vars / out["avg_useful_IG"] if out["avg_useful_IG"] > 0 else ""
        out["conflicts"] = sum(1 for row in items if row["conflict"])
        summary.append(out)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="*", default=[100, 200, 500])
    parser.add_argument("--formulas", type=int, default=5)
    parser.add_argument("--ratio", type=float, default=4.27)
    parser.add_argument("--min-cooccur", type=int, default=1)
    parser.add_argument("--max-cluster-size", type=int, default=8)
    parser.add_argument("--sample-clusters", type=int, default=500)
    parser.add_argument("--check-unit", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-prefix", default="sat_cluster_f_survival_step1")
    args = parser.parse_args()

    rows = []
    print("=== SAT CLUSTER F SURVIVAL PROBE ===")
    for key, value in vars(args).items():
        print(f"{key}={value}")
    print()

    for n_vars in args.sizes:
        n_clauses = round(args.ratio * n_vars)
        print(f"n={n_vars}, clauses={n_clauses}")
        for i in range(args.formulas):
            seed = args.seed + n_vars * 1000 + i
            rows.append(probe_formula(n_vars, n_clauses, args, seed))
        print("  done")

    summary = summarize(rows)
    write_csv(Path(args.out_prefix + "_details.csv"), rows)
    write_csv(Path(args.out_prefix + "_summary.csv"), summary)

    print("\n=== SUMMARY ===")
    for row in summary:
        print(
            f"n={row['n_vars']} "
            f"IG={row['avg_IG']:.2f} "
            f"survival={row['avg_R_est_survival']:.3f} "
            f"stability={row['avg_stability_score']:.3f} "
            f"R_est={row['avg_R_est']:.3f} "
            f"usefulIG={row['avg_useful_IG']:.2f} "
            f"D={row['D_pred'] if row['D_pred'] == '' else round(row['D_pred'], 2)} "
            f"pre_danger={row['avg_pre_dangerous_clauses']:.2f}"
        )
    print("Files written:")
    print(args.out_prefix + "_details.csv")
    print(args.out_prefix + "_summary.csv")


if __name__ == "__main__":
    main()
