#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys


def tag(value):
    return str(value).replace(".", "p")


def main():
    avg_degrees = [3, 4, 5, 6, 8]
    colors_list = [3, 4]
    for colors in colors_list:
        for avg_degree in avg_degrees:
            out_prefix = f"graph_coloring_danger_n1000_c{colors}_deg{tag(avg_degree)}"
            cmd = [
                sys.executable,
                "graph_coloring_danger_probe.py",
                "--sizes", "1000",
                "--seeds", "2",
                "--colors", str(colors),
                "--avg-degree", str(avg_degree),
                "--sample-units", "500",
                "--top-neighbors", "16",
                "--out-prefix", out_prefix,
            ]
            print("RUN", " ".join(cmd), flush=True)
            subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
