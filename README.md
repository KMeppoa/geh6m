# Empirical Framework for Chain-Forcing Search Depth in NP-Style Problems

Author: Sargis Garibyan

Status: master project report, not a final theory paper.

This document records the full research path from the first L/G idea to the current large scaling probes. It is intentionally conservative. It separates observed effects from hypotheses, records negative results, and treats the current theory as an empirical framework rather than a completed proof.

## 1. Project Overview

The project started from a simple distinction:

```text
L = local view of the current partial state
G = global consequence expansion caused by a local choice
```

The core intuition is that a local choice can look good inside `L` while hiding global forced consequences. In SAT this means that a variable assignment can create unit clauses and forced assignments. In Graph Coloring this means that assigning a color can remove colors from neighbors and eventually force some vertices. In other constraint problems the same pattern appears as propagation, shrinking candidate sets, or forced inclusion/exclusion.

The goal is not to prove `P = NP` or `P != NP`. The working goal is narrower and empirical:

```text
measure how much recursive clustering and consequence expansion reduce predicted search depth.
```

The project therefore measures `D`, a predicted depth proxy, instead of claiming full solver complexity. The research question is:

```text
Can we identify structural signals that predict when a recursive global rebuild reduces D?
```

## 2. Core Formulas

### IG

`IG` means information gain. Operationally, it is the number of variables or decision objects fixed after choosing a cluster and applying the task-specific propagation rule.

For SAT:

```text
IG = number of variables assigned by:
     chosen cluster assignment
     + unit propagation consequences
```

For graph problems:

```text
IG = number of vertices or decision objects fixed by:
     chosen cluster action
     + forced propagation consequences
```

`IG` is not a proof-theoretic information measure. It is an empirical structural measurement.

### danger_rate

```text
danger_rate = dangerous_constraints / affected_constraints
```

`affected_constraints` are constraints touched by the chosen cluster. `dangerous_constraints` are affected constraints that become critical after the assignment.

Examples:

```text
SAT:
    affected = clauses touching cluster variables
    dangerous = affected clauses that become unit

Graph Coloring:
    affected = edges touching cluster vertices
    dangerous = neighboring vertices with only one remaining color

Vertex Cover:
    affected = edges touching cluster vertices
    dangerous = edges where the only uncovered endpoint becomes forced
```

In the fast SAT probe, `danger_rate` is counted on affected clauses, but `IG` is still computed after indexed propagation through `var_to_clauses`. Propagation is not artificially limited to the initially affected clauses.

### useful_IG

```text
useful_IG = IG * (1 - danger_rate)
```

This discounts raw information gain by the local risk created by the assignment.

### D

```text
D = n / useful_IG
```

`D` is the central scaling proxy. It estimates how many useful recursive steps are needed to cover an instance of size `n`, assuming the measured cluster behavior remains representative.

This is a probe metric, not a SAT solver proof.

### pressure, forcing, freedom, alpha

Later cross-problem probes introduced geometry terms:

```text
predicted_danger = pressure * forcing / freedom
alpha = actual_danger / predicted_danger
```

with:

```text
alpha = 0 if predicted_danger = 0 or forcing = 0
```

Important interpretation correction:

```text
alpha is only a chain-forcing coefficient.
alpha is not a general "NP depth" measure.
```

The earlier labels `P-like`, `weak NP`, and `strong NP` are too strong if read as formal complexity classes. The safer project language is:

```text
alpha = 0              no-chain observed by current instrument
small alpha > 0        weak-chain observed
larger alpha           strong-chain observed
```

If `alpha = 0`, it means the current chain-forcing measurement did not detect forcing in that representation. It does not mean the task is easy, polynomial, or outside NP-hardness.

## 3. Early L vs G Experiments

The early experiments tested whether adding `G` improves search compared with using only `L`.

The common pattern:

```text
L-only:
    evaluates current local state
    tends to require more free decisions
    produces zero or few forced_steps

LG:
    evaluates local state after global consequences
    converts some choices into forced_steps
    reduces free guessing when G is informative
```

### Labyrinth

The labyrinth experiments were the first non-SAT sanity check. The result recorded in the expansion plan:

```text
Labyrinth:
    guided_1 = 10%
    guided_7 = 100%
```

Interpretation: deeper/global guidance had a large effect in this toy domain. This supported the basic L/G idea but did not yet say anything about NP structure.

### SAT L vs LG

In the SAT v5 experiments, `LG` consistently used fewer decision steps and more forced steps than `L`.

Representative result from `clean_stats_v5_16x40_stats_by_mode.csv`:

| mode | total | success_rate | avg_decision_steps | avg_forced_steps |
|---|---:|---:|---:|---:|
| dpll_control | 40 | 0.775 | 9.750 | 1.075 |
| greedy_L | 40 | 0.450 | 13.425 | 0.000 |
| greedy_LG | 40 | 0.550 | 5.475 | 8.925 |
| lookahead_L_3 | 40 | 0.550 | 14.100 | 0.000 |
| lookahead_LG_3 | 40 | 0.775 | 6.275 | 8.300 |

The strongest SAT comparison in that run:

```text
lookahead_L_3  vs lookahead_LG_3
p-value = 0.00390625
```

Observed: adding global consequences reduced free decisions and matched the DPLL control success rate in that benchmark.

### Graph Coloring L vs LG

Graph Coloring repeated the same direction outside SAT.

From `graph_coloring_step2_18x60_summary_by_mode.csv`:

| mode | total | success_rate | avg_decision_steps | avg_forced_steps |
|---|---:|---:|---:|---:|
| greedy_L | 60 | 0.6167 | 17.350 | 0.000 |
| greedy_LG | 60 | 0.8833 | 6.517 | 11.133 |
| lookahead_L_2 | 60 | 0.6000 | 17.100 | 0.000 |
| lookahead_LG_2 | 60 | 0.9000 | 7.117 | 10.517 |
| lookahead_L_3 | 60 | 0.7333 | 17.133 | 0.000 |
| lookahead_LG_3 | 60 | 0.9000 | 8.083 | 9.483 |

Recorded project note:

```text
Graph Coloring greedy_L vs greedy_LG p-value ~= 0.0000305
```

Observed: the G effect was not SAT-specific. It also appeared in Graph Coloring as fewer decisions and more forced steps.

### forced_steps vs decision_steps

The early project lesson:

```text
decision_steps = free guesses still needed
forced_steps   = consequences automatically forced by G
```

The key signal was not only success rate. The more structural signal was that `LG` replaced free choices with forced consequences.

## 4. SAT Results

The SAT experiments provided the first stable evidence that `L-only` is weaker than `LG`.

From `sat_lg_v5_fast_summary_by_mode.csv`:

| mode | total | success_rate | avg_steps_success_only | avg_steps_all |
|---|---:|---:|---:|---:|
| dpll_control | 100 | 0.88 | 16.94 | 19.63 |
| greedy_L | 100 | 0.24 | 23.58 | 24.49 |
| greedy_LG | 100 | 0.48 | 3.33 | 11.20 |
| lookahead_L_3 | 100 | 0.32 | 28.59 | 24.69 |
| lookahead_LG_3 | 100 | 0.88 | 8.33 | 7.33 |
| random | 12 | 0.00 | n/a | 0.00 |

Interpretation:

```text
L-only was weak.
LG was much stronger.
lookahead_LG_3 matched DPLL control success rate in this benchmark.
```

The limited-DPLL comparison also showed cases where the limited control timed out but LG found a satisfying assignment. This was not interpreted as LG beating SAT generally; it showed that global consequence scoring can choose useful paths under shallow search limits.

`forced_steps` in SAT means unit-propagation consequences. When `LG` has high forced_steps and low decision_steps, it means the algorithm is moving through implication structure instead of pure guessing.

## 5. Graph Coloring Results

Graph Coloring was used to test whether L/G is only a SAT artifact.

The result was directionally supported:

```text
greedy_L     = 37/60 success
greedy_LG    = 53/60 success
lookahead_L_3  = 44/60 success
lookahead_LG_3 = 54/60 success
```

The observed effect repeated:

```text
L-only:
    more decision steps
    no forced steps

LG:
    fewer decision steps
    many forced steps
```

Conclusion: the G effect was observed beyond SAT. This supported the broader hypothesis that local choices hide global forced consequences in multiple constraint systems.

## 6. Reserve History

The first reserve hypothesis treated reserve as a loss-recovery store.

Old formula:

```text
recovered = beta^level * overlap * reserve_score
```

The idea was:

```text
information lost at deeper recursive levels might be recovered from reserve
if the current cluster overlaps with reserve variables.
```

The test result was negative.

Observed:

```text
overlap ~= 0
recovered ~= 0
reserve did not work as a loss-recovery bank
```

From reserve paired summaries, many `baseline_recovered` values were exactly `0.0`, and `reserve_recovered` was usually near zero. The theory version "reserve as a bank of lost IG" should be considered dead in its tested form.

Important failure mode:

```text
clusters were built independently of reserve.
if cluster construction ignores reserve variables,
overlap stays near zero,
and recovery cannot activate.
```

## 7. Reserve as Navigator

The next interpretation was stronger and more useful:

```text
reserve/feedback does not recover lost IG after the fact.
reserve/feedback should guide where clusters are built.
```

Old reserve was passive:

```text
build cluster by co-occurrence
then check whether reserve overlaps
```

Navigator reserve is active:

```text
build cluster using reserve/feedback signal
```

The cluster edge scoring idea:

```text
edge_weight = cooccur + lambda * feedback
```

or, more generally:

```text
edge_weight = cooccur_score + reserve_bias * reserve_score
```

Why this is stronger:

```text
passive reserve can only help if overlap already exists.
active reserve changes cluster construction so overlap becomes likely.
```

This moved the research from "recover loss" to "navigate cluster construction."

## 8. Top-Down Rebuild

The top-down rebuild idea:

```text
1. Build G1..G5 baseline.
2. Measure useful_IG at each level.
3. If a higher level is weak, send feedback down.
4. Rebuild G4 using feedback from G5.
5. Rebuild G5 from the corrected G4.
6. Compare D before and after rebuild.
```

Trigger condition used in the fast probe:

```text
if useful_IG_next < useful_IG_current:
    rebuild

or:

if useful_IG_next grows too weakly relative to useful_IG_current:
    rebuild
```

The clean small top-down result:

From `sat_topdown_reserve_rebuild_step3_always_summary.csv`:

| n | stage | level | avg_IG | avg_danger_rate | avg_base_useful_IG | D_pred |
|---:|---|---:|---:|---:|---:|---:|
| 2000 | before | 4 | 47.0 | 0.0307 | 45.56 | 43.90 |
| 2000 | after | 4 | 45.0 | 0.0282 | 43.73 | 45.73 |
| 2000 | before | 5 | 57.0 | 0.0312 | 55.22 | 36.22 |
| 2000 | after | 5 | 57.0 | 0.0296 | 55.31 | 36.16 |
| 5000 | before | 4 | 18.0 | 0.0109 | 17.80 | 280.85 |
| 5000 | after | 4 | 37.0 | 0.0110 | 36.59 | 136.64 |
| 5000 | before | 5 | 24.0 | 0.0107 | 23.74 | 210.58 |
| 5000 | after | 5 | 51.0 | 0.0181 | 50.08 | 99.84 |

Observed:

```text
n = 5000:
    D fell from about 210.58 to 99.84 at level 5.
    This is a strong positive result.

n = 2000:
    effect was neutral or slightly worse.
```

Conclusion:

```text
top-down rebuild can help strongly,
but it does not help reliably in every instance or scale.
```

## 9. Fast D-Scaling Probe

The exact cluster/propagation experiments became too slow for large `n`. A fast probe was created to measure D-scaling without solving SAT.

Important:

```text
This is a probe, not a solver.
It does not search for a complete SAT solution.
It measures IG, danger_rate, useful_IG, and D.
```

Acceleration methods:

```text
var_to_clauses index
affected_clauses only for danger_rate
sparse co-occurrence top-K
sample_units cap
candidate_cap
propagation cache
no full SAT solve
```

Validation:

From `sat_fast_d_scaling_validation_step1_validation.csv`:

| n | level | exact_IG | fast_IG | exact_D | fast_D |
|---:|---:|---:|---:|---:|---:|
| 1000 | 5 | 66 | 66 | 15.7699 | 15.7699 |
| 2000 | 5 | 57 | 57 | 36.2173 | 36.2173 |
| 5000 | 5 | 24 | 24 | 210.5815 | 210.5815 |

Observed:

```text
fast matched exact on IG and D for n = 1000, 2000, 5000 in validation.
```

This justified using the fast probe for larger scaling tests, while still treating large results as approximate because they depend on:

```text
sample_units
candidate_cap
top_neighbors
```

## 10. Scaling to 1,000,000

The large scaling runs tested:

```text
n = 10k, 50k, 100k, 200k, 500k, 1M
seeds = 3
levels = G1..G5
topdown_bias = 5
min_useful_growth = 1.05
sample_units = 500
candidate_cap = 250
top_neighbors = 16
```

The main fact:

```text
D did not grow in a clean, stable log(n) pattern.
top-down rebuild sometimes produced x11/x12 improvements.
top-down rebuild sometimes made D worse.
```

Selected level-5 results from `sat_fast_d_scaling_trigger_topdown_step2_10k_1m_f3_fast.csv`:

| n | seed | baseline_D | after_D | improvement_ratio |
|---:|---:|---:|---:|---:|
| 10000 | 10000042 | 1693.12 | 2032.79 | 0.833 |
| 10000 | 10000043 | 1733.33 | 229.03 | 7.568 |
| 10000 | 10000044 | 2032.79 | 2500.00 | 0.813 |
| 50000 | 50000042 | 12847.22 | 1146.14 | 11.209 |
| 50000 | 50000043 | 10487.80 | 1058.04 | 9.912 |
| 50000 | 50000044 | 12837.84 | 1122.38 | 11.438 |
| 100000 | 100000042 | 25000.00 | 25555.56 | 0.978 |
| 100000 | 100000043 | 27000.00 | 27083.33 | 0.997 |
| 100000 | 100000044 | 25000.00 | 2116.27 | 11.813 |
| 200000 | 200000042 | 68468.47 | 4577.81 | 14.957 |
| 200000 | 200000043 | 50000.00 | 54347.83 | 0.920 |
| 200000 | 200000044 | 54545.45 | 4487.51 | 12.155 |
| 500000 | 500000042 | 132352.94 | 136363.64 | 0.971 |
| 500000 | 500000043 | 131578.95 | 131756.76 | 0.999 |
| 500000 | 500000044 | 135869.57 | 170634.92 | 0.796 |
| 1000000 | 1000000042 | 267857.14 | 23402.69 | 11.446 |
| 1000000 | 1000000043 | 257142.86 | 263513.51 | 0.976 |
| 1000000 | 1000000044 | 265625.00 | 23399.96 | 11.352 |

Interpretation:

```text
improvement_ratio = baseline_D / after_D

> 1 means improved
< 1 means worsened
```

Observed:

```text
Some seeds show large improvement.
Some seeds show neutral or harmful rebuild.
The central unresolved problem is predicting which case we are in before rebuilding.
```

This is the current strongest and most unstable result.

## 11. Sweep Negative Result

Two sweeps were run to search for a simple empirical trigger constant.

### min_useful_growth sweep

```text
min_useful_growth = 1.01, 1.05, 1.10, 1.20, 1.50, 2.00
topdown_bias = 5
```

### topdown_bias sweep

```text
topdown_bias = 0.5, 1, 2, 5, 10, 20
min_useful_growth = 1.05
```

Result:

```text
The sweep values did not materially change the outcomes.
For each n, the rows were effectively identical across the sweep settings.
```

Examples from the sweep summaries:

```text
n = 10000:
    median_improvement_ratio = 0.8329
    win_rate = 0.3333
    harm_rate = 0.6667

n = 50000:
    median_improvement_ratio = 11.2091
    win_rate = 1.0000
    harm_rate = 0.0000

n = 500000:
    median_improvement_ratio = 0.9706
    win_rate = 0.0000
    harm_rate = 1.0000
```

Negative conclusion:

```text
min_useful_growth is not the missing constant.
raw topdown_bias is not the missing constant.
ratio_54 and ratio_43 were weak predictors of rebuild success.
```

The likely issue is that feedback strength is not normalized against the scale of co-occurrence weights. Another issue is that the current rebuild may only reorder existing candidate structures rather than adding genuinely new feedback edges.

## 12. Danger-Rate Hypothesis

The danger-rate hypothesis asked whether the local criticality rate is:

```text
a structural background constant,
or
a predictor of whether rebuild wins or harms.
```

SAT and Graph Coloring showed danger rates around a few percent in important regimes:

```text
SAT:
    often around 3-5% in phase-style probes

Graph Coloring:
    around 5% near 3-coloring avg_degree ~= 4
```

But later cross-problem tests showed that raw danger rate is not universal:

```text
Vertex Cover:
    around 20-25%

Hamiltonian Path:
    much higher

Subset Sum / Set Cover / Exact Cover / NQueens:
    zero under current analogues
```

Current interpretation:

```text
danger_rate is useful,
but raw danger_rate alone is not a universal NP constant.
```

For rebuild prediction:

```text
If danger_rate is similar in win and harm cases:
    danger is background, not a trigger.

If danger_rate separates win and harm cases:
    danger is a candidate hidden criterion.
```

The project has not yet settled this. The win/harm separation question remains active.

## 13. Cross-Problem Geometry

The geometry map tested ten tasks:

```text
SAT
GraphColoring
VertexCover
IndependentSet
Clique
HamiltonianPath
SubsetSum
SetCover
ExactCover
NQueens
```

The goal was to check whether each task has a characteristic danger geometry.

From `np_geometry_map_final_n1000_f3.csv`:

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

Key observation:

```text
GraphColoring and VertexCover can have the same pressure ~= 4,
but very different danger_rate.
```

Therefore pressure alone is insufficient.

This motivated:

```text
forcing = forced_by_propagation / chosen_cluster_size
freedom = average remaining admissible choices after assignment
```

From `np_forcing_freedom_final_n1000_f3.csv`:

| task | pressure | danger_G4 | danger_G5 | forced_G4 | forced_G5 | freedom_G4 | freedom_G5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| SAT | 4.270 | 0.0352 | 0.0406 | 0.615 | 0.675 | 1.898 | 1.882 |
| GraphColoring | 4.000 | 0.0398 | 0.0528 | 0.094 | 0.100 | 1.940 | 1.918 |
| VertexCover | 4.000 | 0.2129 | 0.2499 | 0.755 | 0.775 | 1.000 | 1.000 |
| IndependentSet | 2.000 | 0.2069 | 0.2407 | 0.688 | 0.746 | 0.793 | 0.759 |
| Clique | 0.080 | 0.3016 | 0.2825 | 29.688 | 27.126 | 0.698 | 0.717 |
| HamiltonianPath | 2.000 | 0.8290 | 0.6714 | 2.823 | 2.270 | 3.906 | 3.887 |
| SubsetSum | 0.098 | 0.0000 | 0.0000 | 0.000 | 0.000 | 2.000 | 2.000 |
| SetCover | 1.500 | 0.0000 | 0.0000 | 0.000 | 0.000 | 13.156 | 11.900 |
| ExactCover | 1.500 | 0.0000 | 0.0000 | 0.000 | 0.000 | 12.864 | 11.960 |
| NQueens | 1.000 | 0.0000 | 0.0000 | 0.000 | 0.000 | 936.661 | 921.246 |

Safe chain-language interpretation:

| task | alpha | safer interpretation |
|---|---:|---|
| 2SAT_r1 | 0.0016 | weak-chain / almost no-chain |
| 2SAT_r4p27 | 0.0112 | weak-chain |
| 3SAT | 0.0260 | weak-chain under current metric |
| GraphColoring | 0.2304 | strong-chain observed |
| VertexCover | 0.0756 | weak-chain to medium-chain |
| IndependentSet | 0.1211 | strong-chain observed |
| Clique | 0.0909 | medium-chain |
| HamiltonianPath | 0.5741 | strong-chain observed |
| SubsetSum | 0.0000 | no-chain observed by current instrument |
| SetCover | 0.0000 | no-chain observed by current instrument |
| ExactCover | 0.0000 | no-chain observed by current instrument |
| NQueens | 0.0000 | no-chain observed by current instrument |

Important correction:

```text
Do not read "no-chain observed" as "formally easy."
It means the current danger/forcing analogue did not detect chain forcing.
```

SubsetSum and ExactCover are especially important open cases because formal NP-completeness and current alpha behavior do not align cleanly.

## 14. Current State

What works:

```text
1. The L/G distinction is useful.
2. LG reduced free decision steps in SAT and Graph Coloring.
3. forced_steps is a meaningful operational signal.
4. useful_IG and D provide a practical scaling probe.
5. Fast D-scaling matched exact on n = 1000, 2000, 5000.
6. Top-down rebuild can massively reduce D on some large SAT seeds.
7. Cross-problem geometry shows pressure alone is insufficient.
8. forcing/freedom helps explain differences like GraphColoring vs VertexCover.
```

What does not work, or is not stable:

```text
1. Reserve as a loss-recovery store did not work.
2. recovered = beta^level * overlap * reserve_score produced recovered ~= 0.
3. Raw reserve_bias sweeps did not stabilize rebuild.
4. min_useful_growth sweeps did not find a reliable trigger.
5. ratio_54 and ratio_43 did not reliably predict rebuild success.
6. D did not show a clean log(n) law in current large probes.
7. alpha should not be presented as formal NP-depth.
8. Several task-specific danger analogues may be too weak or representation-dependent.
```

The current main question:

```text
What internal structural signal predicts when top-down rebuild reduces D?
```

Current candidate signals:

```text
normalized_feedback =
    topdown_bias * feedback_score / average_cooccur_weight

danger_rate win/harm separation

cooccur scale and distribution

new feedback edges rather than only reordering existing clusters

cluster construction that explicitly prefers high-feedback variables
```

The most likely next improvement is to normalize feedback against local co-occurrence scale:

```text
edge_weight = normalized_cooccur + normalized_feedback
```

instead of using a raw additive bias that may be too small or too large depending on instance scale.

## 15. Required Tone and Research Position

This project should be described using conservative research language:

```text
observed
supported in these probes
directionally supported
unstable
negative result
open question
```

Avoid:

```text
confirmed
proved
universal NP law
P-like as a formal class
alpha as solved NP-depth
```

The strongest honest summary is:

```text
Recursive global consequence expansion clearly reduces free guessing in several probes.
The D-scaling framework is useful and fast enough to test large instances.
Top-down rebuild sometimes gives very large improvements.
The project has not yet found the structural trigger that separates improvement cases from harm cases.
```

## 16. Current Hypotheses

### H1: L/G captures real forced-consequence structure

Status: supported in SAT, Graph Coloring, and toy labyrinth probes.

Reason:

```text
LG increases forced_steps and reduces decision_steps.
```

### H2: Reserve is a bank of recoverable information

Status: rejected in tested form.

Reason:

```text
overlap ~= 0
recovered ~= 0
```

### H3: Reserve/feedback is a cluster navigator

Status: directionally supported.

Reason:

```text
Changing cluster construction through feedback can increase useful_IG.
Top-down rebuild at n = 5000 reduced D from about 210.58 to 99.84.
```

Open issue:

```text
The effect is unstable across n and seeds.
```

### H4: D grows roughly log(n)

Status: not supported by current large scaling data.

Reason:

```text
D values fluctuate strongly.
Rebuild can improve by x11 or harm slightly depending on seed.
No clean log(n) trend is visible yet.
```

### H5: danger_rate is a universal NP constant

Status: not supported as a raw percentage.

Reason:

```text
SAT / Graph Coloring: few percent
VertexCover: about 20-25%
HamiltonianPath: much higher
several tasks: zero under current instrument
```

Better hypothesis:

```text
danger_rate is a task/representation-specific chain criticality signal.
```

### H6: pressure * forcing / freedom predicts danger

Status: partially supported.

Reason:

```text
pressure alone failed.
forcing and freedom explain important differences.
alpha still varies substantially and depends on task representation.
```

## 17. Open Questions

1. What signal predicts whether top-down rebuild improves or harms D?
2. Should feedback create new cluster edges instead of only reweighting existing co-occurrence?
3. How should feedback be normalized against average co-occurrence weight?
4. Is danger_rate different between win and harm rebuild cases?
5. Are current danger analogues for SubsetSum, SetCover, ExactCover, and NQueens too weak?
6. Should `freedom` be measured over variables, constraints, reachable local states, or propagation frontier?
7. Is alpha a property of a task, an instance distribution, or a representation?
8. Can larger seed counts make the scaling picture less unstable?
9. Can top-down rebuild be made monotone, so it only applies when expected improvement is positive?
10. Is there a better `D` formula that preserves the meaning of IG and danger_rate but accounts for variance?

## 18. Practical Next Steps

The next experiments should focus on prediction, not bigger raw scaling.

Recommended next probe:

```text
For each rebuild candidate:
    compute average_cooccur_weight
    compute feedback_score distribution
    compute normalized_feedback
    compute danger_rate_G4/G5
    compute ratio_54 and ratio_43
    compute number of new feedback edges
    record win/harm after rebuild
```

Then train or fit a simple empirical rule:

```text
rebuild if normalized_feedback exceeds threshold
and expected danger/harm signal is acceptable
```

The target is not a black-box model. The target is a small interpretable structural rule that predicts:

```text
when top-down rebuild lowers D.
```


