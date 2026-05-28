This is an old summary. The current main document is MASTER_PROJECT_REPORT.md.

# Empirical Theory of NP Complexity via Chain Forcing and Recursive Clustering

Author: Sargis Garibyan

## Abstract

This package reports a set of empirical probes for NP-style combinatorial problems. The central claim is that recursive clustering exposes an operational geometry of complexity: a local assignment may trigger chain forcing, reduce remaining freedom, and create a measurable danger rate. The work does not claim a proof of P vs NP. It proposes measurable quantities that can be tested across tasks.

## Core Formulas

Predicted depth:

```text
D = n / useful_IG
```

Useful information gain:

```text
useful_IG = IG * (1 - danger_rate)
```

Danger rate:

```text
danger_rate = dangerous_constraints / affected_constraints
```

Geometry-based prediction:

```text
predicted_danger = pressure * forcing / freedom
```

Alpha:

```text
alpha = actual_danger / predicted_danger
```

where `alpha = 0` when `predicted_danger = 0` or forcing is zero.

Interpretation used in the probes:

```text
alpha = 0        P-like
0 < alpha < 0.1 weak NP
alpha >= 0.1    strong NP
```

## Definitions

`IG` is the number of variables or decision objects assigned after choosing a G-level cluster and applying the task-specific propagation rule.

`danger_rate` measures what fraction of touched constraints becomes critical after a cluster assignment. Examples: SAT clauses becoming unit clauses, graph-coloring neighbors having one remaining color, vertex-cover edges with only one possible endpoint left, and Hamiltonian vertices with only one possible continuation.

`pressure` is the task-specific constraint density. Examples: clauses per variable for SAT, edges per vertex for graph coloring and vertex cover, sets per element for cover problems, and target divided by total sum for subset sum.

`forcing` is measured as:

```text
avg_forced_per_assignment = forced_by_propagation / chosen_cluster_size
```

`freedom` is the average number of remaining admissible choices for affected neighboring variables or constraints after the cluster assignment.

## Alpha and Complexity Table

Source: `np_alpha_complexity_table.csv`

| task | pressure | actual_danger | predicted_danger | alpha | known_hardness | approximation | FPT | predicted_class |
|---|---:|---:|---:|---:|---:|---|---|---|
| 2SAT_r1 | 1.000 | 0.2778 | 174.3333 | 0.0016 | 1 | yes | yes | weak NP |
| 2SAT_r4p27 | 4.270 | 0.0476 | 4.2700 | 0.0112 | 1 | yes | yes | weak NP |
| 3SAT | 4.270 | 0.0379 | 1.4573 | 0.0260 | 3 | no | no | weak NP |
| GraphColoring | 4.000 | 0.0463 | 0.2010 | 0.2304 | 3 | limited | yes | strong NP |
| VertexCover | 4.000 | 0.2314 | 3.0608 | 0.0756 | 2 | yes | yes | weak NP |
| IndependentSet | 2.000 | 0.2238 | 1.8488 | 0.1211 | 3 | no | yes | strong NP |
| Clique | 0.080 | 0.2920 | 3.2125 | 0.0909 | 3 | no | yes | weak NP |
| HamiltonianPath | 2.000 | 0.7502 | 1.3068 | 0.5741 | 3 | no | no | strong NP |
| SubsetSum | 0.098 | 0.0000 | 0.0000 | 0.0000 | 1 | pseudo-poly | yes | P-like |
| SetCover | 1.500 | 0.0000 | 0.0000 | 0.0000 | 1 | log | yes | P-like |
| ExactCover | 1.500 | 0.0000 | 0.0000 | 0.0000 | 2 | no | yes | P-like |
| NQueens | 1.000 | 0.0000 | 0.0000 | 0.0000 | 1 | n/a | n/a | P-like |

Notes: SubsetSum and NQueens are retained with `alpha = 0` as open theoretical cases. Subset Sum is formally NP-complete but has a pseudopolynomial algorithm. N-Queens is not treated as a classical NP-complete decision problem in this package.

## Forcing/Freedom Table

Source: `np_forcing_freedom_final_n1000_f3.csv`

| task | pressure | danger_G4 | danger_G5 | IG_G4 | IG_G5 | forced_G4 | forced_G5 | freedom_G4 | freedom_G5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SAT | 4.270 | 0.0352 | 0.0406 | 51.67 | 67.00 | 0.615 | 0.675 | 1.898 | 1.882 |
| GraphColoring | 4.000 | 0.0398 | 0.0528 | 35.00 | 44.00 | 0.094 | 0.100 | 1.940 | 1.918 |
| VertexCover | 4.000 | 0.2129 | 0.2499 | 54.00 | 71.00 | 0.755 | 0.775 | 1.000 | 1.000 |
| IndependentSet | 2.000 | 0.2069 | 0.2407 | 27.00 | 35.67 | 0.688 | 0.746 | 0.793 | 0.759 |
| Clique | 0.080 | 0.3016 | 0.2825 | 967.67 | 967.67 | 29.688 | 27.126 | 0.698 | 0.717 |
| HamiltonianPath | 2.000 | 0.8290 | 0.6714 | 32.00 | 39.00 | 2.823 | 2.270 | 3.906 | 3.887 |
| SubsetSum | 0.098 | 0.0000 | 0.0000 | 32.00 | 39.00 | 0.000 | 0.000 | 2.000 | 2.000 |
| SetCover | 1.500 | 0.0000 | 0.0000 | 32.00 | 40.00 | 0.000 | 0.000 | 13.156 | 11.900 |
| ExactCover | 1.500 | 0.0000 | 0.0000 | 32.00 | 39.00 | 0.000 | 0.000 | 12.864 | 11.960 |
| NQueens | 1.000 | 0.0000 | 0.0000 | 32.00 | 40.00 | 0.000 | 0.000 | 936.661 | 921.246 |

## Geometry Map Table

Source: `np_geometry_map_final_n1000_f3.csv`

| task | constraint_pressure | danger_G4 | danger_G5 | IG_G4 | IG_G5 |
|---|---:|---:|---:|---:|---:|
| SAT | 4.270 | 0.0352 | 0.0406 | 51.67 | 67.00 |
| GraphColoring | 4.000 | 0.0500 | 0.0565 | 35.00 | 44.50 |
| VertexCover | 4.000 | 0.2129 | 0.2499 | 54.00 | 71.00 |
| IndependentSet | 2.000 | 0.2069 | 0.2407 | 27.00 | 35.67 |
| Clique | 0.080 | 0.3016 | 0.2825 | 967.67 | 967.67 |
| HamiltonianPath | 2.000 | 0.8290 | 0.6714 | 32.00 | 39.00 |
| SubsetSum | target/sum | 0.0000 | 0.0000 | 32.00 | 39.00 |
| SetCover | 1.500 | 0.0000 | 0.0000 | 32.00 | 40.00 |
| ExactCover | 1.500 | 0.0000 | 0.0000 | 32.00 | 39.00 |
| NQueens | 1.000 | 0.0000 | 0.0000 | 32.00 | 40.00 |

## Test Summary

### SAT recursive scaling

The SAT probes measure recursive cluster levels G1 through G5. For each chosen cluster, unit propagation is applied, then `IG`, `danger_rate`, `useful_IG`, and `D` are computed. The fast probe was validated against the exact path on `n = 1000, 2000, 5000` and matched level-5 IG and D in the validation runs.

### Reserve and top-down rebuild

The first reserve interpretation treated reserve as a loss-recovery store:

```text
recovered = beta^level * overlap * reserve_score
```

The empirical result was that recovered information was usually close to zero. The stronger interpretation is that reserve is a navigational signal: it helps decide where clusters should be rebuilt. Top-down rebuild sometimes strongly reduced D, but the effect was not stable across all seeds and sizes.

### SAT danger across clause ratios

SAT danger stayed in a low range, often around a few percent, but did not peak cleanly at ratio 4.27 in the small probe. The result suggests that danger rate is stable but not explained by clause ratio alone.

### Graph coloring density sweep

For 3-coloring with average degree near 4, danger rate was close to 5 percent, similar to SAT. With 4 colors, danger rate was close to zero for sparse graphs because local freedom remained high.

### Geometry map across NP tasks

The same constraint pressure can yield different danger rates. Graph Coloring and Vertex Cover both used pressure near 4, but Graph Coloring danger was around 5 percent while Vertex Cover was around 20-25 percent. This motivated the additional variables forcing and freedom.

### Alpha complexity test

Alpha is defined as the ratio between actual danger and geometry-predicted danger. The test partially supports alpha as a measure of chain-forcing depth: 2-SAT has alpha close to zero, and Hamiltonian Path, Graph Coloring, and Independent Set have larger alpha. However, 3-SAT appears as weak NP in this operational metric, and Exact Cover appears P-like under the current danger definition.

## Main Conclusions

1. `D = n / useful_IG` is a practical empirical predictor for recursive cluster probes.
2. `danger_rate` is stable inside some task geometries but is not universal as a raw percentage.
3. Constraint pressure alone does not explain danger rate.
4. Adding forcing and freedom explains important differences such as Graph Coloring vs Vertex Cover.
5. Alpha may measure chain-forcing depth, but current task-specific danger analogues are not yet mature enough to classify all NP-complete tasks correctly.

## Open Questions

1. Can alpha be normalized so that 3-SAT at the phase transition is classified as strong NP?
2. Are the current analogues for Exact Cover, Set Cover, Subset Sum, and N-Queens too weak?
3. Should `freedom` be measured over constraints, variables, or reachable local states?
4. Can top-down rebuild be made stable by normalizing feedback by average co-occurrence weight?
5. Does danger rate converge with larger seeds and larger n?
6. Is alpha a property of a problem class, an instance distribution, or a chosen representation?
7. Can this framework predict the phase transition point of a new NP problem from pressure, forcing, and freedom alone?

## Reproducibility Notes

All scripts and final CSV files used for the tables are included in this OSF package. The probes are empirical and intentionally do not solve the full instances. They measure structural quantities produced by recursive clustering and task-specific propagation rules.

