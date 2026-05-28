#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
from pathlib import Path


def f(value):
    if value is None or value == "":
        return 0.0
    return float(str(value).replace(",", "."))


def avg(values):
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


META = {
    "2SAT_r1": (1, "yes", "yes", "P; polynomial 2-SAT"),
    "2SAT_r4p27": (1, "yes", "yes", "P; polynomial 2-SAT, overconstrained ratio point"),
    "3SAT": (3, "no", "no", "NP-complete; sharp phase transition"),
    "GraphColoring": (3, "limited", "yes", "NP-complete; k fixed is hard for k>=3"),
    "VertexCover": (2, "yes", "yes", "NP-complete; good approximation and FPT"),
    "IndependentSet": (3, "no", "yes", "NP-complete; hard to approximate"),
    "Clique": (3, "no", "yes", "NP-complete; hard to approximate"),
    "HamiltonianPath": (3, "no", "no", "NP-complete; very hard"),
    "SubsetSum": (1, "pseudo-poly", "yes", "alpha=0 but formally NP-complete; pseudopolynomial"),
    "SetCover": (1, "log", "yes", "NP-complete; logarithmic approximation"),
    "ExactCover": (2, "no", "yes", "NP-complete"),
    "NQueens": (1, "n/a", "n/a", "alpha=0; not classical NP-complete decision task"),
}


def actual_pred_from_forcing_row(row):
    actual = (f(row["danger_G4"]) + f(row["danger_G5"])) / 2.0
    pred = (f(row["pred_G4"]) + f(row["pred_G5"])) / 2.0
    pressure = f(row["pressure"])
    return actual, pred, pressure


def sat_alpha(path, task, pressure):
    rows = list(csv.DictReader(Path(path).open(encoding="utf-8")))
    actual = avg(f(row["danger_rate"]) for row in rows if row["level"] in ("4", "5"))
    pred = avg(
        pressure * f(row["avg_forced_per_assignment"]) / f(row["avg_freedom"])
        for row in rows
        if row["level"] in ("4", "5") and f(row["avg_freedom"]) > 0
    )
    return {
        "task": task,
        "pressure": pressure,
        "actual_danger": actual,
        "predicted_danger": pred,
    }


def predicted_class(alpha):
    if alpha == 0:
        return "P-like"
    if alpha < 0.1:
        return "weak NP"
    return "strong NP"


def main():
    rows = []
    rows.append(sat_alpha("sat2_alpha_n1000_r1p0_f3_fast.csv", "2SAT_r1", 1.0))
    rows.append(sat_alpha("sat2_alpha_n1000_r4p27_f3_fast.csv", "2SAT_r4p27", 4.27))

    base = list(csv.DictReader(Path("np_forcing_freedom_final_n1000_f3.csv").open(encoding="utf-8")))
    rename = {"SAT": "3SAT"}
    for row in base:
        task = rename.get(row["task"], row["task"])
        actual, pred, pressure = actual_pred_from_forcing_row(row)
        rows.append({
            "task": task,
            "pressure": pressure,
            "actual_danger": actual,
            "predicted_danger": pred,
        })

    out = []
    for row in rows:
        pred = row["predicted_danger"]
        actual = row["actual_danger"]
        alpha = 0.0 if pred <= 0 else actual / pred
        hardness, approx, fpt, note = META.get(row["task"], ("", "", "", ""))
        out.append({
            "task": row["task"],
            "pressure": row["pressure"],
            "actual_danger": actual,
            "predicted_danger": pred,
            "alpha": alpha,
            "known_hardness": hardness,
            "has_approximation": approx,
            "has_fpt": fpt,
            "predicted_class": predicted_class(alpha),
            "note": note,
        })

    with Path("np_alpha_complexity_table.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)

    print("task, alpha, predicted_class, known_hardness")
    for row in out:
        print(f"{row['task']}, {row['alpha']:.4f}, {row['predicted_class']}, {row['known_hardness']}")
    print("File written: np_alpha_complexity_table.csv")


if __name__ == "__main__":
    main()
