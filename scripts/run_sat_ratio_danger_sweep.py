#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys


def tag(value):
    return str(value).replace(".", "p")


def main():
    ratios = [3.0, 3.5, 4.0, 4.27, 4.5, 5.0]
    for ratio in ratios:
        out_prefix = f"sat_ratio_danger_r{tag(ratio)}_n1000_5000_f3"
        cmd = [
            sys.executable,
            "sat_fast_d_scaling_probe.py",
            "--sizes", "1000", "5000",
            "--formulas", "3",
            "--ratio", str(ratio),
            "--max-levels", "5",
            "--sample-units", "500",
            "--candidate-cap", "250",
            "--top-neighbors", "16",
            "--topdown-bias", "5",
            "--min-useful-growth", "1.05",
            "--out-prefix", out_prefix,
        ]
        print("RUN", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
