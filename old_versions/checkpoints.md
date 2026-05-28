This is an old summary. The current main document is MASTER_PROJECT_REPORT.md.

# РљРѕРЅС‚СЂРѕР»СЊРЅС‹Рµ С‚РѕС‡РєРё L/G

## РљРѕРЅС‚СЂРѕР»СЊРЅР°СЏ С‚РѕС‡РєР° 1

Р”Р°С‚Р°: 2026-05-24

РџР°РїРєРё СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ:

```text
experiments/micro_first
experiments/micro_branchcap4
experiments/small_stage_12_16_cap4
experiments/stage_18_20_cap4
```

## Checkpoint: Set Cover step1

Date: 2026-05-25

Files:

```text
set_cover_lg_test.py
set_cover_step1_small_summary_by_mode.csv
set_cover_step1_small_summary_by_case.csv
set_cover_step1_small_logs.jsonl
set_cover_step1_trap_summary_by_mode.csv
set_cover_step1_trap_summary_by_case.csv
set_cover_step1_trap_logs.jsonl
```

Small random Set Cover:

```text
cases=30, universe=24, sets=36, k=6

greedy_L       30/30 = 100.0%
greedy_LG      30/30 = 100.0%
lookahead_L_2  29/30 = 96.7%
lookahead_LG_2 29/30 = 96.7%
lookahead_L_3  29/30 = 96.7%
lookahead_LG_3 29/30 = 96.7%
```

Meaning:

```text
This random profile is too easy. L already solves almost everything, so it cannot show much benefit from G.
```

Trap Set Cover:

```text
cases=30, universe=24, sets=36, k=6

greedy_L       24/30 = 80.0%
greedy_LG      25/30 = 83.3%
lookahead_L_2  27/30 = 90.0%
lookahead_LG_2 28/30 = 93.3%
lookahead_L_3  25/30 = 83.3%
lookahead_LG_3 26/30 = 86.7%
```

Paired check:

```text
greedy_L vs greedy_LG:
    both=24, LG_only=1, L_only=0, neither=5

lookahead_L_2 vs lookahead_LG_2:
    both=26, LG_only=2, L_only=1, neither=1

lookahead_L_3 vs lookahead_LG_3:
    both=25, LG_only=1, L_only=0, neither=4
```

Checks:

```text
false_success = 0
oracle_unsat_generated = 0
py_compile passed
```

Plain-language result:

```text
Set Cover gives a weak-to-moderate positive signal for G only when the instance has traps.
On easy random instances, G is mostly neutral because L is already enough.
```

M/T memory update:

```text
Set Cover:
    Q = 0.100
    M = 0.102
    best_L  = lookahead_L_2  = 90.0%
    best_LG = lookahead_LG_2 = 93.3%
    T = lookahead_LG_2 -> lookahead_L_2 -> lookahead_LG_3 -> greedy_LG
```

Plain-language meaning:

```text
For future Set Cover-like tasks, T recommends trying lookahead_LG_2 first.
But Set Cover is not a strong G win yet; it is a small positive signal.
```

## Checkpoint: Exact Cover step1

Date: 2026-05-25

Files:

```text
exact_cover_lg_test.py
exact_cover_step1_small_summary_by_mode.csv
exact_cover_step1_small_summary_by_case.csv
exact_cover_step1_small_logs.jsonl
```

Config:

```text
cases=30
universe=24
sets=42
solution_size=6
profile=trap
branch_cap=4
lookaheads=2,3
```

Result:

```text
greedy_L        2/30  = 6.7%
greedy_LG      30/30 = 100.0%

lookahead_L_2  22/30 = 73.3%
lookahead_LG_2 30/30 = 100.0%

lookahead_L_3  27/30 = 90.0%
lookahead_LG_3 30/30 = 100.0%
```

Paired check:

```text
greedy_L vs greedy_LG:
    both=2, LG_only=28, L_only=0, neither=0

lookahead_L_2 vs lookahead_LG_2:
    both=22, LG_only=8, L_only=0, neither=0

lookahead_L_3 vs lookahead_LG_3:
    both=27, LG_only=3, L_only=0, neither=0
```

Checks:

```text
false_success = 0
oracle_unsat_generated = 0
py_compile passed
```

Runtime note:

```text
Expected time was too low. The run took about 8 minutes.
Future Exact Cover tests must start smaller or skip the expensive oracle when the generator is planted-SAT.
```

Plain-language result:

```text
Exact Cover is a very strong positive case for G.
L often chooses locally attractive sets, but G detects forced compatible sets and avoids branches that duplicate elements.
```

M/T memory update:

```text
Exact Cover:
    Q = 0.100
    M = 0.452
    best_L  = lookahead_L_3 = 90.0%
    best_LG = greedy_LG     = 100.0%
    T = greedy_LG -> lookahead_LG_2 -> lookahead_LG_3 -> lookahead_L_3
```

## Checkpoint: Latin Square step1

Date: 2026-05-25

Files:

```text
latin_square_lg_test.py
latin_square_smoke_n5_summary_by_mode.csv
latin_square_smoke_n5_summary_by_case.csv
latin_square_smoke_n5_logs.jsonl
latin_square_step1_n6_summary_by_mode.csv
latin_square_step1_n6_summary_by_case.csv
latin_square_step1_n6_logs.jsonl
```

Important runtime note:

```text
The first n=7, depth=3 attempt was too heavy and was stopped.
The valid tests are n=5 smoke and n=6 step1.
```

n=5 smoke:

```text
cases=5, n=5, givens=10, branch_cap=2, lookahead=2

greedy_L        5/5 = 100.0%, avg_decision=15.0, avg_forced=0.0
greedy_LG       5/5 = 100.0%, avg_decision=0.6,  avg_forced=14.4
lookahead_L_2   5/5 = 100.0%, avg_decision=15.0, avg_forced=0.0
lookahead_LG_2  5/5 = 100.0%, avg_decision=1.0,  avg_forced=14.0
```

n=6 step1:

```text
cases=10, n=6, givens=12, branch_cap=2, lookahead=2

greedy_L        9/10  = 90.0%,  avg_decision=24.0, avg_forced=0.0
greedy_LG       10/10 = 100.0%, avg_decision=1.5,  avg_forced=22.5
lookahead_L_2   9/10  = 90.0%,  avg_decision=24.0, avg_forced=0.0
lookahead_LG_2  10/10 = 100.0%, avg_decision=3.5,  avg_forced=20.5
```

Paired check:

```text
greedy_L vs greedy_LG:
    both=9, LG_only=1, L_only=0, neither=0

lookahead_L_2 vs lookahead_LG_2:
    both=9, LG_only=1, L_only=0, neither=0
```

Checks:

```text
false_success = 0
py_compile passed
```

Plain-language result:

```text
Latin Square is a strong G-forced-steps case.
Even when success rate is close, G turns many free guesses into forced consequences.
```

M/T memory update:

```text
Latin Square:
    Q = 0.100
    M = 1.665
    best_L  = greedy_L  = 90.0%
    best_LG = greedy_LG = 100.0%
    T = greedy_LG -> lookahead_LG_2 -> greedy_L -> lookahead_L_2
```

## Checkpoint: E efficiency indicator v1

Date: 2026-05-25

Files:

```text
build_M_T_memory.py
M_T_memory_measurements.csv
M_T_memory_strategies.csv
```

New indicator:

```text
E = Benefit / Cost
```

Where:

```text
Benefit = 3 * success_gain
        + normalized_decision_gain
        + normalized_forced_steps

Cost = 1 + relative_extra_score_calls
```

Plain-language meaning:

```text
M says whether G helps.
E says whether G helps enough to be worth its cost.
```

Current E ranking:

```text
Latin Square     E=2.106
N-Queens         E=1.902
SAT              E=1.743
Exact Cover      E=1.731
Graph Coloring   E=1.632
Clique           E=1.014
Set Cover        E=0.380
Independent Set  E=0.272
Subset Sum       E=0.211
Vertex Cover     E=0.010
```

Interpretation:

```text
High E:
    G gives strong value for the cost.

Low E:
    G may still help, but not enough to be clearly worth it.

Near zero E:
    Use G carefully or only after simpler methods.
```

## Checkpoint: weighted L/G on weak tasks v1

Date: 2026-05-25

Files:

```text
weak_efficiency_weighted_test.py
weak_weighted_step1_summary_by_mode.csv
weak_weighted_step1_summary_by_case.csv
```

Formula tested:

```text
score(x,a) = (1 - w_g) * L(x,a) + w_g * G(x,a)
```

Tasks:

```text
Set Cover
Vertex Cover
```

Config:

```text
cases=30 per task
depth=2
branch_cap=3
weights tested: w_g = 0.1, 0.2, 0.4
```

Set Cover:

```text
L_depth2              27/30
LG_depth2             28/30
weighted_G_0.1_depth2 26/30
weighted_G_0.2_depth2 26/30
weighted_G_0.4_depth2 26/30
```

Vertex Cover:

```text
L_depth2              29/30
LG_depth2             30/30
weighted_G_0.1_depth2 29/30
weighted_G_0.2_depth2 29/30
weighted_G_0.4_depth2 29/30
```

Plain-language result:

```text
Simple weighting alone did not improve weak tasks.
The useful part of G is not just adding G to the score.
The useful part is often applying forced consequences through propagation.
```

Formula implication:

```text
BestMove should not only weight L and G.
It also needs an ApplyG/Propagate step when E says G is worth using.
```

## Checkpoint: Hamiltonian Path prediction test

Date: 2026-05-25

Prediction under test:

```text
User prediction: E > 1.5
Assistant cautious prediction before test: medium E
```

Files:

```text
hamiltonian_path_lg_test.py
hamiltonian_path_step1_small_summary_by_mode.csv
hamiltonian_path_step1_small_summary_by_case.csv
hamiltonian_path_step1_small_logs.jsonl
hamiltonian_path_step1_applyg_summary_by_mode.csv
hamiltonian_path_step1_applyg_summary_by_case.csv
hamiltonian_path_step1_applyg_logs.jsonl
hamiltonian_path_step2_sparse_summary_by_mode.csv
hamiltonian_path_step2_sparse_summary_by_case.csv
hamiltonian_path_step2_sparse_logs.jsonl
```

Important correction:

```text
First version counted forced consequences but did not apply them.
Then ApplyG was added: if the endpoint has exactly one possible next vertex, append it automatically.
```

Sparse profile result:

```text
cases=30
vertices=24
edge_prob=0.03

greedy_L        22/30 = 73.3%, avg_decision=24.0, avg_forced=0.0
greedy_LG       19/30 = 63.3%, avg_decision=7.53, avg_forced=16.47
lookahead_L_2    0/30 = 0.0%
lookahead_LG_2   1/30 = 3.3%
lookahead_L_3    0/30 = 0.0%
lookahead_LG_3   1/30 = 3.3%
```

Paired check:

```text
greedy_L vs greedy_LG:
    both=18, LG_only=1, L_only=4, neither=7
```

M/T/E update:

```text
Hamiltonian Path:
    Q = 0.267
    M = 0.965
    E = 0.950
    best_L  = greedy_L  = 73.3%
    best_LG = greedy_LG = 63.3%
    T = greedy_L -> greedy_LG -> lookahead_LG_2 -> lookahead_LG_3
```

Plain-language result:

```text
The prediction E > 1.5 was not confirmed on this implementation/profile.
Hamiltonian Path has many forced-looking consequences, but they can force the search into a bad path.
So G reduces guessing, but does not yet improve success enough.
```

Theory implication:

```text
High forced_steps alone is not enough.
A good E predictor must distinguish useful forced consequences from brittle forced consequences.
```

## Checkpoint: Hamiltonian Path adaptive L_count

Date: 2026-05-25

Idea tested:

```text
If L_count is large, run G.
If L_count is small, avoid G.
```

Where:

```text
L_count = number of locally possible next vertices from the current endpoint.
```

Files:

```text
hamiltonian_path_step3_adaptive_lcount_summary_by_mode.csv
hamiltonian_path_step3_adaptive_lcount_summary_by_case.csv
hamiltonian_path_step3_adaptive_lcount_logs.jsonl
```

Result:

```text
greedy_L          22/30 = 73.3%
greedy_LG         19/30 = 63.3%
adaptive_LG_1_2   19/30 = 63.3%
adaptive_LG_1_3   18/30 = 60.0%
adaptive_LG_1_4   19/30 = 63.3%
```

Checks:

```text
false_success = 0
py_compile passed
```

Plain-language result:

```text
The rule "large L_count -> run G" did not improve Hamiltonian Path.
When L_count is large, G has fewer forced consequences.
The useful forced consequences appear when L_count is small, especially near bottlenecks.
```

Theory update:

```text
L_count alone is not enough.
The predictor should use:
    L_count
    bottleneck risk
    whether G creates real forced moves
    whether forced moves are reversible/risky
```

## Checkpoint: guided depth growth on Exact Cover

Date: 2026-05-25

Goal:

```text
Check how fast guided_n must grow to reach 100% as NP task size grows.
```

Task:

```text
Planted Exact Cover, trap profile.
```

Files:

```text
guided_depth_growth_exact_cover.py
experiments/guided_depth_growth_exact_cover_step1/
experiments/guided_depth_growth_exact_cover_step2_safe/
```

Step 1:

```text
cases=10 per size
sizes=12,18,24,30
depths=1,2,3,4
branch_cap=4

size=12 first_depth_100=1
size=18 first_depth_100=1
size=24 first_depth_100=1
size=30 first_depth_100=1
```

Step 2 safe:

```text
cases=5 per size
sizes=32,36,40
depths=1,2
branch_cap=3

size=32 first_depth_100=1
size=36 first_depth_100=1
size=40 first_depth_100=1
```

Runtime note:

```text
The attempted jump to sizes 40,60,80,100 was too slow and was stopped.
That run is not counted as a valid result.
```

Plain-language result:

```text
On this planted Exact Cover family, guided_1 already reaches 100% up to size 40.
So guided_n did not grow here.
This is a strong positive example for G, but the family may be too easy to prove universal behavior.
```

## Checkpoint: guided depth growth on N-Queens

Date: 2026-05-25

Goal:

```text
Find a medium task where guided_1 is not always enough and guided_n growth can be observed.
```

Files:

```text
guided_depth_growth_n_queens.py
experiments/guided_depth_growth_n_queens_step1/
```

Config:

```text
sizes=N=8,9,10,11,12
depths=1,2,3,4
branch_cap=2
max_steps=3*N
```

Result:

```text
N=8  first_depth_100=2
N=9  first_depth_100=2
N=10 first_depth_100=1
N=11 first_depth_100=2
N=12 first_depth_100=3
```

Detailed curve:

```text
N=8:  guided_1=0, guided_2=1, guided_3=1, guided_4=1
N=9:  guided_1=0, guided_2=1, guided_3=1, guided_4=1
N=10: guided_1=1, guided_2=0, guided_3=1, guided_4=1
N=11: guided_1=0, guided_2=1, guided_3=0, guided_4=1
N=12: guided_1=0, guided_2=0, guided_3=1, guided_4=1
```

Plain-language result:

```text
N-Queens is a better growth test than planted Exact Cover.
The needed guided depth stays small on N=8..12, but it is not constant at 1.
This is a useful early signal, not yet a scaling law.
```

## Checkpoint: guided depth growth on Graph Coloring and SAT phase

Date: 2026-05-26

Goal:

```text
Find whether minimal guided_n grows with problem size.
```

Graph Coloring files:

```text
guided_depth_growth_graph_coloring.py
experiments/guided_depth_growth_graph_coloring_step1/
experiments/guided_depth_growth_graph_coloring_step2_medium/
```

Graph Coloring planted colorable result:

```text
edge_prob=0.55, cases=10, sizes=18,22,26,30:
    first_depth_100 = 1 for all tested sizes

edge_prob=0.25, cases=5, sizes=18,22,26,30:
    first_depth_100 = 1 for all tested sizes
```

Meaning:

```text
For these planted colorable graph families, guided_1 already reaches 100%.
This is positive for G, but not useful for measuring growth of guided_n.
```

SAT phase-transition files:

```text
sat_phase_depth_step1_summary_by_mode.csv
sat_phase_depth_step1_summary_by_formula.csv
sat_phase_depth_step1_logs.jsonl
sat_phase_depth_step2_v14_summary_by_mode.csv
sat_phase_depth_step2_v14_summary_by_formula.csv
sat_phase_depth_step2_v14_logs.jsonl
```

SAT phase-transition result:

```text
vars=12, clauses=51, formulas=20, DPLL-SAT=16:
    guided_1 = 13/16
    guided_2 = 16/16
    guided_3 = 16/16
    guided_4 = 16/16
    first_depth_100 = 2

vars=14, clauses=60, formulas=10, DPLL-SAT=9:
    guided_1 = 9/9
    guided_2 = 9/9
    guided_3 = 9/9
    first_depth_100 = 1
```

Plain-language result:

```text
SAT phase transition is more promising than planted Graph Coloring for depth-growth tests.
At vars=12, guided_1 was not enough and guided_2 reached 100% on SAT formulas.
At vars=14, this small sample was easier and guided_1 already reached 100%.
More samples are needed before claiming a growth law.
```

Runtime note:

```text
Graph Coloring depth=4 was expensive and reached the timeout after writing files.
Future runs should use fewer cases, depth up to 3, or smaller branch_cap.
```

## Checkpoint: SAT phase depth growth packaged run

Date: 2026-05-26

Goal:

```text
Measure minimal guided_n on SAT near the phase transition ratio 4.27.
```

Files:

```text
guided_depth_growth_sat_phase.py
experiments/guided_depth_growth_sat_phase_step1/
```

Config:

```text
sizes=12,14,16 variables
clauses=round(4.27*n)
formulas=10 per size
depths=1,2,3
branch_cap=4
workers=1
```

Result on DPLL-SAT formulas only:

```text
n=12, clauses=51, DPLL-SAT=8:
    guided_1 = 7/8
    guided_2 = 8/8
    guided_3 = 8/8
    first_depth_100 = 2

n=14, clauses=60, DPLL-SAT=9:
    guided_1 = 9/9
    guided_2 = 9/9
    guided_3 = 9/9
    first_depth_100 = 1

n=16, clauses=68, DPLL-SAT=6:
    guided_1 = 5/6
    guided_2 = 6/6
    guided_3 = 6/6
    first_depth_100 = 2
```

Plain-language result:

```text
On this small SAT phase-transition sample, minimal guided depth stayed very small: 1 or 2.
This supports the idea that G can keep depth low on some hard SAT-like cases.
But samples are small, so this is an early signal, not a scaling law.
```

Next safe scaling:

```text
Increase formulas per size before increasing variable count too much.
Recommended next run: n=12,14,16 with formulas=20, depths=1,2,3.
```

## Checkpoint: SAT entropy / information gain v1

Date: 2026-05-26

Goal:

```text
Add H and IG to the SAT phase-growth results and test:
    D_pred = H(start) / avg_IG(G)
against:
    D_real = first guided depth reaching 100% on DPLL-SAT formulas.
```

Files:

```text
analyze_sat_entropy_ig.py
sat_entropy_ig_step1_by_depth.csv
sat_entropy_ig_step1_first_depth.csv
```

Definitions for this first SAT prototype:

```text
H_start = n_vars = log2(2^n_vars)
IG ~= forced_steps from unit propagation
D_pred = ceil(H_start / avg_IG_success)
```

Result:

```text
n=12:
    H = 12
    D_real = 2
    depth1 avg_IG_success = 7.43
    D_pred = ceil(12 / 7.43) = 2

n=14:
    H = 14
    D_real = 1
    depth1 avg_IG_success = 10.78
    D_pred = ceil(14 / 10.78) = 2

n=16:
    H = 16
    D_real = 2
    depth1 avg_IG_success = 12.60
    D_pred = ceil(16 / 12.60) = 2
```

Plain-language result:

```text
The simple entropy predictor matched 2 out of 3 tested sizes.
It predicted n=12 and n=16 correctly.
It overestimated n=14 by one depth level.
```

Important limitation:

```text
This v1 uses total forced_steps as IG.
The next stronger version should log H_before and H_after at every solver step.
```

## Checkpoint: SAT phase bigger n and entropy prediction

Date: 2026-05-26

Goal:

```text
Check whether D stays small on bigger SAT phase-transition instances before adding per-step H logging.
```

Files:

```text
experiments/guided_depth_growth_sat_phase_step2_bigger/
sat_entropy_ig_step2_bigger_by_depth.csv
sat_entropy_ig_step2_bigger_first_depth.csv
```

Config:

```text
sizes=18,20,22 variables
clauses=round(4.27*n)
formulas=5 per size
depths=1,2,3
branch_cap=3
workers=1
```

Depth-growth result on DPLL-SAT formulas:

```text
n=18, DPLL-SAT=3:
    guided_1 = 2/3
    guided_2 = 3/3
    guided_3 = 3/3
    D_real = 2

n=20, DPLL-SAT=5:
    guided_1 = 3/5
    guided_2 = 5/5
    guided_3 = 5/5
    D_real = 2

n=22, DPLL-SAT=2:
    guided_1 = 1/2
    guided_2 = 2/2
    guided_3 = 2/2
    D_real = 2
```

Entropy prediction:

```text
n=18:
    H=18, depth2 avg_IG=10.00
    D_pred=ceil(18/10.00)=2
    D_real=2

n=20:
    H=20, depth2 avg_IG=12.60
    D_pred=ceil(20/12.60)=2
    D_real=2

n=22:
    H=22, depth2 avg_IG=17.00
    D_pred=ceil(22/17.00)=2
    D_real=2
```

Plain-language result:

```text
For n=18,20,22, guided_2 solved all DPLL-SAT formulas in this sample.
The entropy predictor D_pred=ceil(H/IG) matched D_real for all three sizes.
This is the strongest prediction-supporting signal so far, but sample size is still small.
```

## Checkpoint: lightweight SAT H/IG probe up to n=100

Date: 2026-05-26

Goal:

```text
Measure H and IG on large SAT phase-transition formulas without full solving.
```

Files:

```text
sat_hig_probe.py
sat_hig_probe_step1_details.csv
sat_hig_probe_step1_summary.csv
```

Config:

```text
sizes=22,50,100
formulas=5
steps=5 greedy-LG probe steps
ratio=4.27
No DPLL, no lookahead, no full solving.
```

Definitions:

```text
H_before = unassigned variables before greedy action
H_after  = unassigned variables after action + unit propagation
IG_total = H_before - H_after
IG_G_only = max(0, IG_total - 1)
D_pred_total = n / avg_IG_total
D_pred_G_only = n / avg_IG_G_only
```

Result:

```text
n=22:
    avg_IG_total = 3.59
    avg_IG_G_only = 2.59
    D_pred_total = 6.13
    D_pred_G_only = 8.49

n=50:
    avg_IG_total = 7.83
    avg_IG_G_only = 6.83
    D_pred_total = 6.39
    D_pred_G_only = 7.32

n=100:
    avg_IG_total = 7.56
    avg_IG_G_only = 6.56
    D_pred_total = 13.23
    D_pred_G_only = 15.24
```

Plain-language result:

```text
The lightweight probe is much more cautious than full small-n solving.
IG grows from n=22 to n=50, but does not keep growing at n=100 in this small sample.
This suggests D may grow for n=100 unless deeper search creates better IG than early greedy steps.
```

Theory implication:

```text
There are two different measurements:
1. Solving-based IG from successful runs: optimistic, tied to found paths.
2. Probe-based early IG: cheaper, but may underestimate what guided search can create.

The theory needs per-step H/IG inside the real guided solver to connect them.
```

## Checkpoint: lightweight SAT H/IG probe at very large n

Date: 2026-05-26

Goal:

```text
Run the same lightweight H/IG probe at much larger SAT phase-transition sizes.
```

Files:

```text
sat_hig_probe.py
sat_hig_probe_large_step1_details.csv
sat_hig_probe_large_step1_summary.csv
```

Config:

```text
sizes=1000,3000,10000
formulas=1 per size
steps=2 greedy-LG probe steps
sample_actions=200
ratio=4.27
No DPLL, no lookahead, no full solving.
```

Result:

```text
n=1000:
    avg_IG_total = 1.50
    avg_IG_G_only = 0.50
    D_pred_total = 666.67
    D_pred_G_only = 2000.0

n=3000:
    avg_IG_total = 1.00
    avg_IG_G_only = 0.00
    D_pred_total = 3000.0
    D_pred_G_only = undefined

n=10000:
    avg_IG_total = 1.00
    avg_IG_G_only = 0.00
    D_pred_total = 10000.0
    D_pred_G_only = undefined
```

Plain-language result:

```text
At very large n, this cheap sampled early-step probe shows almost no propagation gain.
The measured IG is mostly just the one chosen variable, not extra G consequences.
```

Important limitation:

```text
This does not mean full guided search fails at n=10000.
It means early random-sampled greedy actions do not trigger unit-propagation cascades.
The previous small-n successful-run IG and this large-n sampled probe are measuring different things.
```

Theory implication:

```text
The current G=unit propagation may not produce large IG from arbitrary early choices at huge n.
To keep D small at large n, the method would need either:
    better action selection,
    stronger G than unit propagation,
    or measured cascades later in the search, not just first sampled steps.
```

## Checkpoint: hierarchical G probe v1

Date: 2026-05-26

Idea:

```text
When G1 loses usefulness at large n, add G on top of G:
    G1 = unit propagation
    G2 = failed-literal probing using G1
    G3 = another G2 round
```

Files:

```text
sat_hierarchy_g_probe.py
sat_hierarchy_g_probe_step1_details.csv
sat_hierarchy_g_probe_step1_summary.csv
```

Config:

```text
sizes=22,50,100,200
formulas=3
sample_actions=200
probe_vars=200
ratio=4.27
No DPLL, no full solving.
```

Result:

```text
n=22:
    IG1=1.00, IG2=1.33, IG3=2.33
    D1=22.0, D2=16.5, D3=9.43

n=50:
    IG1=1.00, IG2=1.33, IG3=1.33
    D1=50.0, D2=37.5, D3=37.5

n=100:
    IG1=1.00, IG2=1.00, IG3=1.00
    D1=100.0, D2=100.0, D3=100.0

n=200:
    IG1=1.00, IG2=1.00, IG3=1.00
    D1=200.0, D2=200.0, D3=200.0
```

Plain-language result:

```text
This simple G-over-G version helps a little at n=22, weakly at n=50, and not at n=100/200.
So failed-literal probing over sampled variables is not enough to create logarithmic levels on large random SAT.
```

Theory implication:

```text
The hierarchy idea is still valid as a direction, but G2 must be stronger or more structured.
Random sampled failed-literal probing does not discover large-scale structure at high n.
```

## Checkpoint: cluster G2 probe v1

Date: 2026-05-26

Idea:

```text
G1 works on variables.
G2 should work on clusters of variables that often appear together in clauses.
```

Files:

```text
sat_cluster_g2_probe.py
sat_cluster_g2_probe_step1_details.csv
sat_cluster_g2_probe_step1_summary.csv
```

Cluster construction:

```text
Count pairs (x_i, x_j) that occur in the same clause.
Union variables into clusters if pair_count >= 2.
Limit max cluster size to 8.
```

Config:

```text
sizes=50,100,200
formulas=3
ratio=4.27
min_cooccur=2
max_cluster_size=8
sample_actions=200
sample_clusters=200
No DPLL, no full solving.
```

Result:

```text
n=50:
    G1 IG_var = 1.00
    G2 IG_var = 16.67
    G2 forced = 8.67
    D_pred_G1 = 50.0
    D_pred_G2 = 3.0

n=100:
    G1 IG_var = 1.00
    G2 IG_var = 11.67
    G2 forced = 3.67
    D_pred_G1 = 100.0
    D_pred_G2 = 8.57

n=200:
    G1 IG_var = 1.00
    G2 IG_var = 14.67
    G2 forced = 6.67
    D_pred_G1 = 200.0
    D_pred_G2 = 13.64
```

Plain-language result:

```text
Cluster-level G2 is much stronger than variable-level G1 in this probe.
Unlike failed-literal G2, it creates real extra IG at n=50,100,200.
```

Important caution:

```text
Part of G2 IG comes from assigning several variables in the chosen cluster at once.
The additional propagation-only gain is measured by forced_G2:
    n=50  forced_G2=8.67
    n=100 forced_G2=3.67
    n=200 forced_G2=6.67
So the result is promising, but not yet proof that cluster hierarchy alone gives log(n).
```

Theory implication:

```text
The "G over G" idea works better when the higher level changes scale:
    variables -> clusters
not when it repeats variable-level probing.
```

## Checkpoint: cluster G2 probe n=500 and n=1000

Date: 2026-05-26

Goal:

```text
Check whether cluster-level G2 still reduces predicted depth at larger n.
```

Files:

```text
sat_cluster_g2_probe_step2_500_1000_details.csv
sat_cluster_g2_probe_step2_500_1000_summary.csv
```

Config:

```text
sizes=500,1000
formulas=2
ratio=4.27
min_cooccur=2
max_cluster_size=8
sample_actions=200
sample_clusters=200
No DPLL, no full solving.
```

Result:

```text
n=500:
    G1 IG_var = 1.00
    G2 IG_var = 10.50
    G2 forced = 2.50
    avg_cluster_size = 1.47
    D_pred_G1 = 500.0
    D_pred_G2 = 47.62

n=1000:
    G1 IG_var = 1.00
    G2 IG_var = 9.00
    G2 forced = 3.50
    avg_cluster_size = 1.21
    D_pred_G1 = 1000.0
    D_pred_G2 = 111.11
```

Plain-language result:

```text
Cluster G2 still beats G1 strongly at n=500 and n=1000.
But its advantage weakens because clusters become mostly single variables as n grows.
```

Theory implication:

```text
Changing scale helps, but the current co-occurrence clustering loses structure at large n.
To keep D closer to log(n), G2 needs better clusters or G3 over clusters-of-clusters.
```

## Checkpoint: recursive cluster scaling v1

Date: 2026-05-26

Idea:

```text
If IG at one level is too low, recursively build the next level:
variables -> clusters -> clusters of clusters -> ...
```

Files:

```text
sat_recursive_cluster_levels.py
sat_recursive_cluster_levels_step1_details.csv
sat_recursive_cluster_levels_step1_summary.csv
sat_recursive_cluster_levels_step1_levels_needed.csv
```

Config:

```text
sizes=100,200,500,1000
formulas=2
ratio=4.27
min_cooccur=2
base_max_cluster_size=8
ig_threshold=2.0
max_levels=5
```

Result:

```text
n=100:
    level1 bestIG=8,  D_pred=12.50
    level5 bestIG=39.5, D_pred=2.53

n=200:
    level1 bestIG=8,  D_pred=25.00
    level5 bestIG=37, D_pred=5.42

n=500:
    level1 bestIG=8,  D_pred=62.50
    level5 bestIG=40, D_pred=12.50

n=1000:
    level1 bestIG=5,  D_pred=208.33
    level5 bestIG=40, D_pred=25.00
```

Plain-language result:

```text
Recursive scale changes strongly reduce predicted depth.
At n=1000, D_pred drops from about 208 at level 1 to 25 at level 5.
```

Important caution:

```text
This is a structural probe, not a SAT-solving proof.
The current bestIG is based on the largest sampled unit size, so it measures compression scale more than verified useful propagation.
The next version must combine recursive clusters with actual G application and reliability R.
```

Theory implication:

```text
Recursive scale helps, but current D still grows:
    n=100  -> Dв‰€2.5 at level5
    n=1000 -> Dв‰€25 at level5
This looks closer to n / level_size than log(n).
To approach log(n), higher-level unit size or useful IG must grow faster with n.
```

## Checkpoint: recursive cluster reliability R v1

Date: 2026-05-26

Goal:

```text
Measure R at each recursive cluster level:
does compression point toward the known correct solution or into a brittle/wrong assignment?
```

Method:

```text
Use planted SAT so the hidden satisfying assignment is known.
R_choice = chosen cluster assignment fully matches planted solution.
R_propagated = chosen cluster + unit propagation fully matches planted solution.
```

Files:

```text
sat_recursive_cluster_reliability.py
sat_recursive_cluster_reliability_step1_details.csv
sat_recursive_cluster_reliability_step1_summary.csv
```

Config:

```text
sizes=100,200,500,1000
formulas=3
ratio=4.27
levels=1..5
base_max_cluster_size=8
min_cooccur=2
```

Result:

```text
n=100:
    level1 IG=19.00, D=5.74, R_choice=0.33, R_prop=0.33
    level5 IG=40.00, D=2.50, R_choice=0.00, R_prop=0.00

n=200:
    level1 IG=18.00, D=11.26, R_choice=0.00, R_prop=0.00
    level5 IG=42.67, D=4.90, R_choice=0.00, R_prop=0.00

n=500:
    level1 IG=11.33, D=44.64, R_choice=0.00, R_prop=0.00
    level5 IG=66.33, D=7.62, R_choice=0.00, R_prop=0.00

n=1000:
    level1 IG=7.67, D=132.28, R_choice=0.00, R_prop=0.00
    level5 IG=61.33, D=16.37, R_choice=0.00, R_prop=0.00
```

Plain-language result:

```text
Recursive clusters strongly increase IG and reduce D_pred.
But reliability R is near zero in this first planted-SAT test.
So the compression is mostly brittle: it removes many possibilities, but not reliably toward the hidden solution.
```

Theory implication:

```text
The correct formula cannot use IG alone.
It must use useful information:
    useful_IG = IG * R

High IG with low R is not enough.
The next problem is not compression; it is reliable orientation of compression.
```

## Checkpoint: reliability-aware compatible clusters v1

Date: 2026-05-26

Idea:

```text
Change cluster construction:
not just variables that co-occur,
but signed assignments that co-occur and do not immediately conflict under unit propagation.
```

Files:

```text
sat_compatible_cluster_reliability.py
sat_compatible_cluster_reliability_step1_details.csv
sat_compatible_cluster_reliability_step1_summary.csv
```

Config:

```text
planted SAT
sizes=100,200,500,1000
formulas=3
ratio=4.27
min_cooccur=1
max_cluster_size=8
check_unit=True
```

Measured:

```text
IG = compression
R_choice_fraction = fraction of chosen cluster assignments matching planted solution
R_choice_success_rate = all variables in chosen cluster match planted solution
useful_IG = IG * R_choice_fraction
```

Result:

```text
n=100:
    IG=23.67
    R_all=0.00
    R_fraction=0.58
    useful_IG=13.92
    D_useful=7.19

n=200:
    IG=15.00
    R_all=0.00
    R_fraction=0.50
    useful_IG=7.67
    D_useful=26.09

n=500:
    IG=11.33
    R_all=0.00
    R_fraction=0.50
    useful_IG=5.71
    D_useful=87.59

n=1000:
    IG=10.67
    R_all=0.00
    R_fraction=0.58
    useful_IG=6.17
    D_useful=162.16
```

Plain-language result:

```text
Compatibility-aware signed clusters improve partial reliability.
About half of chosen cluster assignments match the planted solution.
But full-cluster reliability is still zero, so clusters still contain wrong assignments.
```

Theory implication:

```text
Adding R to cluster construction helps, but not enough.
The next step is smaller/cleaner clusters or a repair mechanism inside clusters.
```

## Checkpoint: F survival score v1

Date: 2026-05-26

Idea:

```text
F does not know the true solution.
F estimates reliability by survival:
    R_est = (sat_clauses + unknown_clauses) / total_clauses
    useful_IG = IG * R_est
```

Files:

```text
sat_cluster_f_survival_probe.py
sat_cluster_f_survival_step1_details.csv
sat_cluster_f_survival_step1_summary.csv
```

Config:

```text
sizes=100,200,500
formulas=5
ratio=4.27
min_cooccur=1
max_cluster_size=8
sample_clusters=500
check_unit=True
```

Result:

```text
n=100:
    IG=21.00
    R_est=1.000
    useful_IG=21.00
    D=4.76

n=200:
    IG=16.60
    R_est=1.000
    useful_IG=16.60
    D=12.05

n=500:
    IG=11.20
    R_est=1.000
    useful_IG=11.20
    D=44.64
```

Plain-language result:

```text
This F version is too weak.
Most chosen clusters do not immediately create unsat clauses, so R_est becomes 1.0.
It measures "not dead yet", but not "pointing toward the solution".
```

Theory implication:

```text
F must be stronger than immediate survival.
A better F should estimate future risk, for example:
    number of low-option variables,
    number of new unit clauses,
    contradiction risk under small probes,
    or entropy after several simulated steps.
```

## Checkpoint: F stability score v2

Date: 2026-05-26

Idea:

```text
R_est = survival_score * stability_score
stability_score = 1 - dangerous_clauses / total_unknown
dangerous clause = unknown clause with exactly one unassigned literal
```

Files:

```text
sat_cluster_f_survival_probe.py
sat_cluster_f_stability_step2_details.csv
sat_cluster_f_stability_step2_summary.csv
```

Result:

```text
n=100:
    IG=21.00, survival=1.000, stability=1.000, R_est=1.000, D=4.76, dangerous=0

n=200:
    IG=16.60, survival=1.000, stability=1.000, R_est=1.000, D=12.05, dangerous=0

n=500:
    IG=11.20, survival=1.000, stability=1.000, R_est=1.000, D=44.64, dangerous=0
```

Logic check:

```text
After unit propagation, one-literal dangerous clauses disappear because unit propagation already processes them.
So this stability definition is not informative when measured after G.
```

Theory update:

```text
Danger should be measured either:
    before unit propagation, as newly created unit clauses;
or after unit propagation, as clauses with two remaining literals / low slack.
```

## Checkpoint: F pre-danger score v3

Date: 2026-05-26

Idea:

```text
Measure danger before unit propagation:
    pre_danger = number of unit clauses created by the cluster before G
    stability = 1 - pre_danger / total_clauses
    R_est = survival * stability
```

Files:

```text
sat_cluster_f_predanger_step3_details.csv
sat_cluster_f_predanger_step3_summary.csv
```

Result:

```text
n=100:
    IG=21.00
    survival=1.000
    stability=0.992
    R_est=0.992
    useful_IG=20.82
    D=4.80
    pre_danger=3.40

n=200:
    IG=16.60
    survival=1.000
    stability=0.998
    R_est=0.998
    useful_IG=16.57
    D=12.07
    pre_danger=1.60

n=500:
    IG=11.20
    survival=1.000
    stability=0.999
    R_est=0.999
    useful_IG=11.19
    D=44.68
    pre_danger=1.60
```

Plain-language result:

```text
Pre-danger is now measured correctly, but it is tiny compared with total clauses.
So dividing by total_clauses makes the penalty too weak.
```

Theory update:

```text
A better stability score should normalize danger by affected/unknown clauses,
not by all clauses.
```

## Checkpoint: recursive risk normalization by affected clauses

Date: 2026-05-26

Idea:

```text
pre_danger is not just a penalty; it may be a scale-invariant risk signal.
Normalize danger by affected clauses:
    danger_rate = pre_danger / affected_clauses
    stability = 1 - danger_rate
    useful_IG = IG * stability
```

Files:

```text
sat_recursive_risk_probe.py
sat_recursive_risk_probe_step1_details.csv
sat_recursive_risk_probe_step1_summary.csv
```

Config:

```text
sizes=100,200,500
formulas=5
levels=1..3
ratio=4.27
min_cooccur=2
base_max_cluster_size=8
```

Result:

```text
n=100:
    level1 danger=3.80, affected=84.40,  rate=0.046, usefulIG=12.76, D=7.84
    level2 danger=4.60, affected=159.80, rate=0.029, usefulIG=22.87, D=4.37
    level3 danger=5.80, affected=168.80, rate=0.034, usefulIG=17.40, D=5.75

n=200:
    level1 danger=3.80, affected=106.60, rate=0.036, usefulIG=13.69, D=14.61
    level2 danger=8.20, affected=181.80, rate=0.045, usefulIG=28.44, D=7.03
    level3 danger=9.00, affected=233.00, rate=0.039, usefulIG=40.73, D=4.91

n=500:
    level1 danger=3.40, affected=106.00, rate=0.032, usefulIG=11.20, D=44.64
    level2 danger=7.80, affected=201.20, rate=0.039, usefulIG=24.80, D=20.16
    level3 danger=11.80, affected=287.20, rate=0.041, usefulIG=40.26, D=12.42
```

Plain-language result:

```text
pre_danger grows with level, but danger_rate stays roughly stable around 3-5%.
This is a strong sign of recursive risk structure: when scale grows, risk grows proportionally with affected area.
```

Theory implication:

```text
The useful formula becomes:
    useful_IG(level) = IG(level) * (1 - danger_rate(level))
    D(n, level) = H(n) / useful_IG(level)

This is better than using raw IG or raw danger.
```

## Checkpoint: recursive risk n=1000 and n=2000

Date: 2026-05-26

Goal:

```text
Check whether danger_rate stays stable at larger n.
```

Files:

```text
sat_recursive_risk_probe_step2_1000_2000_details.csv
sat_recursive_risk_probe_step2_1000_2000_summary.csv
```

Config:

```text
sizes=1000,2000
formulas=3
levels=1..3
ratio=4.27
min_cooccur=2
base_max_cluster_size=8
sample_units=500
```

Result:

```text
n=1000:
    level1 danger=3.00,  affected=78.67,  rate=0.040, usefulIG=8.65,  D=115.64
    level2 danger=6.33,  affected=216.00, rate=0.029, usefulIG=22.00, D=45.45
    level3 danger=11.33, affected=299.67, rate=0.038, usefulIG=37.52, D=26.65

n=2000:
    level1 danger=1.67, affected=65.00,  rate=0.027, usefulIG=5.82,  D=343.55
    level2 danger=3.67, affected=142.67, rate=0.026, usefulIG=13.31, D=150.26
    level3 danger=7.00, affected=313.00, rate=0.022, usefulIG=30.63, D=65.29
```

Plain-language result:

```text
danger_rate stays stable at larger n, around 2-4%.
This supports the recursive-risk idea: danger grows with affected area, not explosively with n.
```

Theory implication:

```text
The risk term appears bounded:
    R_level ~= 1 - constant_risk_rate

The remaining issue is growth of useful_IG with level.
At level3, D is reduced strongly but still grows with n:
    n=1000 -> Dв‰€26.65
    n=2000 -> Dв‰€65.29
```

## Checkpoint: recursive risk levels 4 and 5

Date: 2026-05-26

Goal:

```text
Check whether adding recursive levels 4 and 5 increases IG and reduces D for n=1000 and n=2000.
```

Files:

```text
sat_recursive_risk_probe_step3_levels5_details.csv
sat_recursive_risk_probe_step3_levels5_summary.csv
```

Config:

```text
sizes=1000,2000
formulas=3
levels=1..5
ratio=4.27
min_cooccur=2
base_max_cluster_size=8
sample_units=500
```

Result:

```text
n=1000:
    level1 IG=9.00,  rate=0.040, usefulIG=8.65,  D=115.64
    level2 IG=22.67, rate=0.029, usefulIG=22.00, D=45.45
    level3 IG=39.00, rate=0.038, usefulIG=37.52, D=26.65
    level4 IG=51.67, rate=0.035, usefulIG=49.81, D=20.08
    level5 IG=66.33, rate=0.040, usefulIG=63.62, D=15.72

n=2000:
    level1 IG=6.00,  rate=0.027, usefulIG=5.82,  D=343.55
    level2 IG=13.67, rate=0.026, usefulIG=13.31, D=150.26
    level3 IG=31.33, rate=0.022, usefulIG=30.63, D=65.29
    level4 IG=42.33, rate=0.021, usefulIG=41.43, D=48.27
    level5 IG=38.67, rate=0.018, usefulIG=37.62, D=53.17
```

Plain-language result:

```text
For n=1000, levels 4 and 5 continue improving D.
For n=2000, level 4 improves, but level 5 gets worse.
So recursion helps, but the current cluster construction starts to hit a limit/noise at larger n.
```

Theory implication:

```text
Recursive levels are useful, but not automatically logarithmic yet.
The best current level:
    n=1000 -> level5, Dв‰€15.72
    n=2000 -> level4, Dв‰€48.27

If D is to stay near log(n), cluster construction must improve at high levels.
```

## Checkpoint: removal memory probe v1

Date: 2026-05-26

Idea:

```text
When G removes/forces variables, remember the cause:
    chosen cluster vars -> forced vars
    reason clause vars -> forced vars

Use removal_memory as extra edges when building higher-level clusters.
```

Files:

```text
sat_removal_memory_probe.py
sat_removal_memory_probe_step1_details.csv
sat_removal_memory_probe_step1_summary.csv
```

Config:

```text
sizes=1000,2000
formulas=3
levels=1..5
ratio=4.27
memory_weight=5
sample_units=500
```

Result:

```text
baseline n=1000:
    level4 IG=43.00, usefulIG=41.92, D=23.85
    level5 IG=56.33, usefulIG=54.77, D=18.26

memory n=1000:
    level4 IG=42.67, usefulIG=41.61, D=24.03
    level5 IG=52.67, usefulIG=51.54, D=19.40

baseline n=2000:
    level4 IG=38.33, usefulIG=37.80, D=52.90
    level5 IG=47.33, usefulIG=46.67, D=42.85

memory n=2000:
    level4 IG=37.33, usefulIG=36.89, D=54.22
    level5 IG=47.67, usefulIG=47.08, D=42.48
```

Plain-language result:

```text
This first removal_memory version did not meaningfully improve clustering.
It slightly improved n=2000 level5, but worsened n=1000 and level4.
```

Theory implication:

```text
The idea of causal memory is still reasonable, but memory edges are too crude.
A better version must distinguish useful forced chains from noisy forced chains,
probably using danger_rate/R as a filter before adding memory.
```

## Checkpoint: filtered recursive removal memory v2

Date: 2026-05-26

Idea:

```text
Improve removal memory:
1. Add only high-quality chains:
       memory_edge_weight = useful_IG * (1 - danger_rate)
2. Recursively compress similar memory chains by variable overlap.
```

Files:

```text
sat_filtered_memory_probe.py
sat_filtered_memory_probe_step1_details.csv
sat_filtered_memory_probe_step1_summary.csv
```

Config:

```text
sizes=1000,2000
formulas=3
levels=1..5
ratio=4.27
min_memory_quality=5
max_memory_chain_size=24
sample_units=500
```

Result:

```text
baseline n=1000:
    level4 IG=43.00, usefulIG=41.92, D=23.85
    level5 IG=56.33, usefulIG=54.77, D=18.26

filtered_memory n=1000:
    level4 IG=43.33, usefulIG=42.25, D=23.67
    level5 IG=55.00, usefulIG=53.80, D=18.59

baseline n=2000:
    level4 IG=38.33, usefulIG=37.80, D=52.90
    level5 IG=48.33, usefulIG=47.53, D=42.08

filtered_memory n=2000:
    level4 IG=38.00, usefulIG=37.57, D=53.24
    level5 IG=48.00, usefulIG=47.32, D=42.27
```

Plain-language result:

```text
Filtered memory is cleaner but still does not meaningfully improve IG or D.
It slightly improves n=1000 level4, but worsens or matches the other cases.
```

Theory implication:

```text
The memory idea needs stronger influence or a different representation.
Current memory chains are too sparse compared with base co-occurrence edges.
```

## Checkpoint: adaptive R stabilization v1

Date: 2026-05-26

Idea:

```text
If current IG drops below target_IG from previous levels,
filter harder by reliability:
    choose only among lowest danger_rate clusters.
```

Files:

```text
sat_adaptive_r_stabilization_probe.py
sat_adaptive_r_stabilization_step1_details.csv
sat_adaptive_r_stabilization_step1_summary.csv
```

Config:

```text
sizes=1000,2000
formulas=3
levels=1..5
risk_quantile=0.2
sample_units=500
```

Result:

```text
n=1000:
    baseline level4 usefulIG=49.81, D=20.08
    adaptive level4 usefulIG=49.77, D=20.09

    baseline level5 usefulIG=64.23, D=15.57
    adaptive level5 usefulIG=64.23, D=15.57

n=2000:
    baseline level4 usefulIG=31.33, D=63.85
    adaptive level4 usefulIG=29.60, D=67.56

    baseline level5 usefulIG=55.88, D=35.79
    adaptive level5 usefulIG=34.49, D=57.99
```

Plain-language result:

```text
Adaptive R did not help in this form.
At n=1000 it matched baseline.
At n=2000 it made high levels worse by choosing safer but less informative clusters.
```

Theory implication:

```text
Reliability cannot be used as a hard filter alone.
The selection must balance IG and R, not minimize risk after IG has already dropped.
```

## Quality checks included in checkpoint 1

These checks are part of the checkpoint, not a separate verbal note:

```text
small_stage_12_16_cap4:
    DPLL matches brute force.
    No dpll_matches_brute=False rows were found.

stage_18_20_cap4:
    No false success=True rows were found.
    There are no rows with success=True and direct_verified=False.

dynamic_guided_lab12_depth8_transitions:
    guided_X -> guided_X+1 transitions are readable and consistent.
    guided_depth_curve.csv exists.
    guided_depth_transitions.csv exists.
    guided_first_success_by_map.csv exists.
```

Why this matters:

```text
These checks protect the interpretation from hidden test errors.
The checkpoint says not only "LG looks better", but also:
1. DPLL was validated against brute force on the small SAT level.
2. SAT successes were directly verified.
3. Dynamic guided_X analysis is based on actual transition files.
```

## Control point 2

Date: 2026-05-25

Source files:

```text
sat_lg_v5_fast_summary_by_mode.csv
sat_lg_v5_fast_summary_by_formula.csv
sat_lg_v5_fast_logs.jsonl
```

Run parameters:

```text
formulas=100
vars=30
clauses=120
k=3
max_steps=120
lookaheads=3
workers=2
profile=fast
skip_unsat_heuristics=True
```

Main result:

```text
dpll_control    88/100 = 88%
greedy_L        24/100 = 24%
greedy_LG       48/100 = 48%
lookahead_L_3   32/100 = 32%
lookahead_LG_3  88/100 = 88%
```

Conditional on formulas where DPLL found SAT:

```text
greedy_L        24/88 = 27.3%
greedy_LG       48/88 = 54.5%
lookahead_L_3   32/88 = 36.4%
lookahead_LG_3  88/88 = 100%
```

Paired comparison:

```text
lookahead_L_3 vs lookahead_LG_3:
    LG_only = 56
    L_only  = 0
    same    = 32
```

Careful interpretation:

```text
LG is much stronger than L in this run.
There are no cases where L_3 found SAT and LG_3 did not.
There are 56 cases where LG_3 found SAT and L_3 did not.
```

Methodological limits:

```text
1. random is not a fair baseline in profile=fast.
2. skip_unsat_heuristics=True adds skipped rows with steps=0.
3. avg_steps_all is therefore not a clean cost metric.
4. DPLL fail currently mixes UNSAT and timeout/unknown.
```

Connection to checkpoint 1:

```text
Checkpoint 2 is interpreted together with checkpoint 1:
1. Small SAT checked DPLL against brute force.
2. stage_18_20 checked false success=True.
3. dynamic guided_X checked transition consistency.

So the large v5 result is not isolated; it continues a tested chain.
```

## Clean v5 instrumentation

Date: 2026-05-25

Changed file:

```text
sat_lg_test_v5_fast_parallel_cpu.py
```

Added result statuses:

```text
SAT_FOUND
UNSAT_PROVED
TIMEOUT
FAILED_TO_FIND
SKIPPED
```

Added cost metrics:

```text
decision_steps
forced_steps
score_calls
dpll_nodes
avg_steps_non_skipped
```

Changed default:

```text
skip_unsat_heuristics=False
```

This means the clean mode runs heuristics on all formulas unless skipping is explicitly requested.

Smoke test:

```text
python sat_lg_test_v5_fast_parallel_cpu.py --formulas 4 --vars 8 --clauses 32 --k 3 --max-steps 20 --lookaheads 3 --workers 1 --profile fast --branch-cap 4 --out-prefix smoke_v5_clean
```

Smoke result:

```text
CSV files were written.
New columns are present.
No SKIPPED rows in clean default mode.
py_compile passed for sat_lg_test_v5_fast_parallel_cpu.py and lg_micro_benchmark.py.
```

## Clean v5 step 1: small test

Date: 2026-05-25

Run:

```text
python sat_lg_test_v5_fast_parallel_cpu.py --formulas 10 --vars 12 --clauses 48 --k 3 --max-steps 30 --lookaheads 3 --workers 1 --profile fast --branch-cap 4 --out-prefix clean_step1_v5_small
```

Files:

```text
clean_step1_v5_small_summary_by_mode.csv
clean_step1_v5_small_summary_by_formula.csv
clean_step1_v5_small_logs.jsonl
```

Result:

```text
dpll_control    10/10 = 100%
greedy_L         7/10 = 70%
greedy_LG       10/10 = 100%
lookahead_L_3    8/10 = 80%
lookahead_LG_3  10/10 = 100%
```

Cost comparison:

```text
greedy_L:
    avg_decision_steps = 8.8
    avg_forced_steps   = 0.0

greedy_LG:
    avg_decision_steps = 2.5
    avg_forced_steps   = 7.4

lookahead_L_3:
    avg_decision_steps = 8.6
    avg_forced_steps   = 0.0

lookahead_LG_3:
    avg_decision_steps = 4.4
    avg_forced_steps   = 7.3
```

Before:

```text
Old v5 tables mainly showed success=True/False and steps.
Some rows could be skipped and still look like normal failures.
```

After:

```text
Clean v5 shows status, skipped count, decision_steps, forced_steps and score_calls.
In this run there are no SKIPPED rows.
```

Plain-language interpretation:

```text
LG found more solutions than L.
LG also needed fewer free guesses.
The missing work was replaced by forced consequences from G.
```

Check:

```text
No SKIPPED rows found.
Statuses are readable.
py_compile passed.
```

## Clean v5 step 2: medium test

Date: 2026-05-25

Run:

```text
python sat_lg_test_v5_fast_parallel_cpu.py --formulas 20 --vars 20 --clauses 80 --k 3 --max-steps 60 --lookaheads 3 --workers 2 --profile fast --branch-cap 4 --out-prefix clean_step2_v5_medium
```

Note:

```text
The first sandbox run failed with a Windows multiprocessing permission error.
The same command was rerun with approval outside the sandbox.
```

Files:

```text
clean_step2_v5_medium_summary_by_mode.csv
clean_step2_v5_medium_summary_by_formula.csv
clean_step2_v5_medium_logs.jsonl
```

Result:

```text
dpll_control    16/20 = 80%
greedy_L         5/20 = 25%
greedy_LG       10/20 = 50%
lookahead_L_3    6/20 = 30%
lookahead_LG_3  16/20 = 80%
```

Statuses:

```text
SKIPPED = 0
dpll_control SAT_FOUND    = 16
dpll_control UNSAT_PROVED = 4
```

Conditional on formulas where DPLL found SAT:

```text
greedy_L        5/16  = 31.2%
greedy_LG       10/16 = 62.5%
lookahead_L_3   6/16  = 37.5%
lookahead_LG_3  16/16 = 100%
```

Cost comparison on DPLL-SAT formulas:

```text
greedy_L:
    avg_decision_steps = 18.25
    avg_forced_steps   = 0.00

greedy_LG:
    avg_decision_steps = 5.19
    avg_forced_steps   = 12.62

lookahead_L_3:
    avg_decision_steps = 18.81
    avg_forced_steps   = 0.00

lookahead_LG_3:
    avg_decision_steps = 5.81
    avg_forced_steps   = 13.31
```

Before:

```text
Step 1 used very small formulas: vars=12.
It showed that clean metrics work and LG is better than L.
```

After:

```text
Step 2 uses larger formulas: vars=20.
The same pattern remains:
LG finds more solutions and needs fewer free guesses.
```

Plain-language interpretation:

```text
When the problem grows, L has to keep guessing many times.
LG makes fewer guesses, because G forces many consequences automatically.
```

Check:

```text
No SKIPPED rows found.
Statuses are readable.
DPLL separated SAT_FOUND and UNSAT_PROVED.
L/LG comparison was calculated only on formulas where DPLL found SAT.
```

## Statistical confirmation 1

Date: 2026-05-25

Goal:

```text
Reduce the chance that the L/G effect is random.
Use clean v5 tables with statuses and cost metrics.
```

Attempted but stopped:

```text
vars=16
formulas=100
```

Reason:

```text
The run did not finish within 5 minutes.
It was stopped and not used as valid evidence.
```

Completed run:

```text
python sat_lg_test_v5_fast_parallel_cpu.py --formulas 40 --vars 16 --clauses 64 --k 3 --max-steps 50 --lookaheads 3 --workers 2 --profile fast --branch-cap 4 --out-prefix clean_stats_v5_16x40
```

Files:

```text
clean_stats_v5_16x40_summary_by_mode.csv
clean_stats_v5_16x40_summary_by_formula.csv
clean_stats_v5_16x40_logs.jsonl
clean_stats_v5_16x40_stats_by_mode.csv
clean_stats_v5_16x40_stats_paired.csv
```

Main result:

```text
dpll_control    31/40 = 77.5%
greedy_L        18/40 = 45.0%
greedy_LG       22/40 = 55.0%
lookahead_L_3   22/40 = 55.0%
lookahead_LG_3  31/40 = 77.5%
```

Status check:

```text
SKIPPED = 0
dpll_control SAT_FOUND    = 31
dpll_control UNSAT_PROVED = 9
```

Statistical result:

```text
lookahead_L_3 vs lookahead_LG_3 on DPLL-SAT formulas:
    compared = 31
    LG_only  = 9
    L_only   = 0
    net_gain = 9
    p_value  = 0.00390625
```

Plain-language meaning:

```text
On the formulas where DPLL found a solution,
there were 9 cases where LG solved the formula and L did not.
There were 0 cases where L solved it and LG did not.

The p-value is about 0.004.
That means this result is unlikely to be random noise.
```

Cost comparison:

```text
lookahead_L_3:
    avg_decision_steps = 14.10
    avg_forced_steps   = 0.00

lookahead_LG_3:
    avg_decision_steps = 6.28
    avg_forced_steps   = 8.30
```

Interpretation:

```text
LG does not only solve more formulas.
LG uses fewer free guesses and replaces many choices with forced consequences.
```

Limit:

```text
This is strong experimental/statistical support.
It is still not a mathematical proof of P = NP.
```

Return point:

```text
This checkpoint is the return point before separate experiments on the 9 UNSAT formulas.
If the separate experiment becomes confusing, return to:
clean_stats_v5_16x40_summary_by_formula.csv
clean_stats_v5_16x40_stats_paired.csv
```

Second return point:

```text
Before experiments with limited DPLL vs LG, return to the same clean statistical base:
clean_stats_v5_16x40_summary_by_formula.csv
clean_stats_v5_16x40_stats_paired.csv

The limited-DPLL experiment is separate and must not replace this checkpoint.
```

## Limited DPLL vs LG probe

Date: 2026-05-25

Purpose:

```text
Check whether LG can find a verified SAT solution when DPLL is artificially limited
to a very small number of nodes.
```

Important limit:

```text
This does not mean LG beats full DPLL.
It only tests LG against a deliberately resource-limited DPLL.
```

Run:

```text
python find_lg_beats_limited_dpll.py --formulas 30 --vars 20 --clauses 80 --seed 1000 --limited-dpll-nodes 5 --lg-depth 3 --branch-cap 4 --max-steps 60 --out lg_beats_limited_dpll_small.csv
```

Time note:

```text
Expected time was estimated too low.
Actual run took about 6 minutes.
The CSV was written fully, but future similar tests need a higher time estimate.
```

Result:

```text
TIMEOUT limited-DPLL + LG SAT_FOUND verified = 23
TIMEOUT limited-DPLL + LG FAILED_TO_FIND     = 4
limited-DPLL SAT_FOUND + LG SAT_FOUND        = 3
```

Plain-language meaning:

```text
With DPLL limited to only 5 nodes, many formulas timed out for DPLL.
LG still found verified solutions for 23 of those timeout cases.
Full DPLL later confirmed those candidate formulas as SAT_FOUND.
```

Interpretation:

```text
LG can be useful as a fast solution finder under limited resources.
This is different from proving it is stronger than full DPLL.
```

## Cross-task test 1: Graph Coloring

Date: 2026-05-25

Purpose:

```text
Check whether the same L/G idea works outside SAT.
Task: graph coloring with 3 colors.
```

Run:

```text
python graph_coloring_lg_test.py --graphs 20 --vertices 14 --colors 3 --edge-prob 0.18 --max-steps 30 --branch-cap 4 --out-prefix graph_coloring_step1_small
```

Files:

```text
graph_coloring_step1_small_summary_by_mode.csv
graph_coloring_step1_small_summary_by_graph.csv
graph_coloring_step1_small_logs.jsonl
```

Result:

```text
greedy_L        17/20 = 85%
greedy_LG       20/20 = 100%
lookahead_L_2   16/20 = 80%
lookahead_LG_2  20/20 = 100%
lookahead_L_3   17/20 = 85%
lookahead_LG_3  20/20 = 100%
```

Cost comparison:

```text
greedy_L:
    avg_decision_steps = 13.85
    avg_forced_steps   = 0.00

greedy_LG:
    avg_decision_steps = 6.60
    avg_forced_steps   = 7.40
```

Plain-language meaning:

```text
The same pattern appears in another NP-style constraint problem:
L makes many free choices.
LG makes fewer free choices because G forces consequences.
```

Check:

```text
No false success=True rows found.
graph_coloring_lg_test.py passed py_compile.
```

## Expansion save point

Date: 2026-05-25

Purpose:

```text
Save the current project state before expanding L/G tests to many NP tasks.
```

Base results:

```text
SAT:
    clean_stats_v5_16x40

Graph Coloring:
    graph_coloring_step2_18x60

Labyrinth:
    dynamic_guided_lab12_depth8_transitions
```

Expansion plan:

```text
NP_LG_EXPANSION_PLAN.md
```

Next package:

```text
Independent Set
Clique
Vertex Cover
Subset Sum
N-Queens
```

Rule:

```text
Each new task starts small, then scales only after checks pass.
```

## Package 1 small test: Independent Set and Clique

Date: 2026-05-25

Expected time:

```text
10-30 seconds
```

Actual time:

```text
about 1.4 seconds
```

Run:

```text
python graph_is_clique_lg_test.py --graphs 20 --vertices 16 --target-size 5 --edge-prob 0.25 --max-steps 25 --branch-cap 4 --out-prefix graph_is_clique_step1_small
```

Files:

```text
graph_is_clique_step1_small_summary_by_mode.csv
graph_is_clique_step1_small_summary_by_case.csv
graph_is_clique_step1_small_logs.jsonl
```

Clique result:

```text
greedy_L        1/20  = 5%
greedy_LG       9/20  = 45%
lookahead_L_2   15/20 = 75%
lookahead_LG_2  20/20 = 100%
lookahead_L_3   18/20 = 90%
lookahead_LG_3  20/20 = 100%
```

Independent Set result:

```text
greedy_L        17/20 = 85%
greedy_LG       17/20 = 85%
lookahead_L_2   19/20 = 95%
lookahead_LG_2  20/20 = 100%
lookahead_L_3   20/20 = 100%
lookahead_LG_3  20/20 = 100%
```

Plain-language meaning:

```text
Clique shows a strong LG advantage.
Independent Set is easier in this small setup; L already does well,
but LG still reduces free choices and adds some forced consequences.
```

Check:

```text
No false success=True rows found.
graph_is_clique_lg_test.py passed py_compile.
```

Checklist update:

```text
Independent Set = [~]
Clique          = [~]
```

## Package 1 scaled test: Independent Set and Clique

Date: 2026-05-25

Expected time:

```text
20-60 seconds
```

Actual time:

```text
about 12 seconds
```

Run:

```text
python graph_is_clique_lg_test.py --graphs 60 --vertices 20 --target-size 6 --edge-prob 0.25 --max-steps 35 --branch-cap 4 --out-prefix graph_is_clique_step2_20x60
```

Clique result:

```text
greedy_L        3/60  = 5.0%
greedy_LG       15/60 = 25.0%
lookahead_L_2   48/60 = 80.0%
lookahead_LG_2  60/60 = 100.0%
lookahead_L_3   58/60 = 96.7%
lookahead_LG_3  60/60 = 100.0%
```

Clique paired statistics:

```text
greedy_L vs greedy_LG:
    LG_only = 12
    L_only  = 0
    p       = 0.000488

lookahead_L_2 vs lookahead_LG_2:
    LG_only = 12
    L_only  = 0
    p       = 0.000488
```

Independent Set result:

```text
greedy_L        39/60 = 65.0%
greedy_LG       48/60 = 80.0%
lookahead_L_2   57/60 = 95.0%
lookahead_LG_2  60/60 = 100.0%
lookahead_L_3   59/60 = 98.3%
lookahead_LG_3  59/60 = 98.3%
```

Independent Set paired statistics:

```text
greedy_L vs greedy_LG:
    LG_only = 9
    L_only  = 0
    p       = 0.003906

lookahead_L_3 vs lookahead_LG_3:
    LG_only = 0
    L_only  = 0
    p       = 1
```

Plain-language meaning:

```text
Clique confirms L/G strongly.
Independent Set confirms L/G for greedy mode, but deep L already catches up.
This means Independent Set is easier for local lookahead in this setup.
```

Check:

```text
No false success=True rows found.
graph_is_clique_lg_test.py passed py_compile.
```

Checklist update:

```text
Clique          = [x]
Independent Set = [~]
```

## Package 1 small test: Vertex Cover

Date: 2026-05-25

Expected time:

```text
10-40 seconds
```

Actual time:

```text
about 14 seconds
```

Run:

```text
python vertex_cover_lg_test.py --graphs 30 --vertices 18 --cover-size 6 --edge-prob 0.25 --max-steps 40 --branch-cap 4 --out-prefix vertex_cover_step1_small
```

Result:

```text
greedy_L        29/30 = 96.7%
greedy_LG       18/30 = 60.0%
lookahead_L_2   29/30 = 96.7%
lookahead_LG_2  30/30 = 100.0%
lookahead_L_3   29/30 = 96.7%
lookahead_LG_3  30/30 = 100.0%
```

Important observation:

```text
Vertex Cover is not a simple "LG always better" case.
greedy_LG is worse than greedy_L.
But lookahead_LG_2 and lookahead_LG_3 improve over L.
```

Plain-language meaning:

```text
Forced consequences can help, but if used too greedily they can also push the search
into a bad early commitment.
This is useful because it shows a boundary of the L/G idea.
```

Check:

```text
No false success=True rows found.
vertex_cover_lg_test.py passed py_compile.
```

Checklist update:

```text
Vertex Cover = [~]
```

## Package 1 small test: Subset Sum

Date: 2026-05-25

Expected time:

```text
5-20 seconds
```

Actual time:

```text
about 28 seconds
```

Run:

```text
python subset_sum_lg_test.py --cases 40 --items 18 --max-value 50 --subset-size 6 --max-steps 40 --branch-cap 4 --out-prefix subset_sum_step1_small
```

Result:

```text
greedy_L        21/40 = 52.5%
greedy_LG       21/40 = 52.5%
lookahead_L_2   38/40 = 95.0%
lookahead_LG_2  39/40 = 97.5%
lookahead_L_3   40/40 = 100.0%
lookahead_LG_3  40/40 = 100.0%
```

Important observation:

```text
Subset Sum does not show a strong LG advantage in this setup.
Lookahead itself is already very strong.
G adds forced_steps, but success_rate is almost the same as L.
```

Plain-language meaning:

```text
This is a useful neutral result.
It suggests that L/G advantage depends on the structure of the problem.
For this planted Subset Sum setup, looking ahead is enough to solve almost everything.
```

Check:

```text
No false success=True rows found.
subset_sum_lg_test.py passed py_compile.
```

Checklist update:

```text
Subset Sum = [~]
```

## Package 1 small test: N-Queens

Date: 2026-05-25

Expected time:

```text
5-20 seconds
```

Actual time:

```text
about 6 seconds
```

Run:

```text
python n_queens_lg_test.py --min-n 8 --max-n 16 --max-steps 40 --branch-cap 4 --out-prefix n_queens_step1_small
```

Result:

```text
greedy_L        0/9 = 0.0%
greedy_LG       1/9 = 11.1%
lookahead_L_2   0/9 = 0.0%
lookahead_LG_2  5/9 = 55.6%
lookahead_L_3   2/9 = 22.2%
lookahead_LG_3  6/9 = 66.7%
```

Plain-language meaning:

```text
N-Queens shows a clear L/G advantage.
L alone gets stuck often.
LG uses forced consequences from future rows and solves more cases.
```

Check:

```text
No false success=True rows found.
n_queens_lg_test.py passed py_compile.
```

Checklist update:

```text
N-Queens = [~]
```

## N-Queens dynamic LG safe test

Date: 2026-05-25

Failed heavy attempt:

```text
N=8..16, LG depth 1..8, branch_cap=4
```

Reason:

```text
Too heavy for current PC. Run was interrupted and is not valid evidence.
```

Safe run:

```text
python n_queens_lg_test.py --min-n 8 --max-n 12 --max-steps 30 --branch-cap 2 --dynamic-lg --max-lg-depth 4 --out-prefix n_queens_dynamic_lg_safe
```

Result:

```text
LG_1  1/5 = 20%
LG_2  3/5 = 60%
LG_3  4/5 = 80%
LG_4  5/5 = 100%
```

Transitions:

```text
1 -> 2:
    fixed = 3
    broken = 1

2 -> 3:
    fixed = 2
    broken = 1

3 -> 4:
    fixed = 1
    broken = 0
```

First success depth:

```text
N=8   depth 2
N=9   depth 2
N=10  depth 1
N=11  depth 2
N=12  depth 3
```

Plain-language meaning:

```text
Deeper LG generally helps, but it can still break a previous success at some transitions.
The safe test reaches 100% at LG_4.
```

Check:

```text
No false success=True rows found.
```

## Dynamic LG on existing task results

Date: 2026-05-25

Purpose:

```text
Check whether LG_dynamic improves existing task results.
LG_dynamic = solved if any available lookahead_LG_n solved the case.
```

Run:

```text
python analyze_dynamic_lg_existing.py --out-prefix dynamic_lg_existing
```

Files:

```text
dynamic_lg_existing_by_depth.csv
dynamic_lg_existing_summary.csv
```

Result:

```text
Graph Coloring:
    best single LG = 54/60
    dynamic LG     = 54/60
    gain           = 0

Clique / Independent Set combined file:
    best single LG = 120/120
    dynamic LG     = 120/120
    gain           = 0

Vertex Cover:
    best single LG = 30/30
    dynamic LG     = 30/30
    gain           = 0

Subset Sum:
    best single LG = 40/40
    dynamic LG     = 40/40
    gain           = 0

N-Queens old small:
    best single LG = 6/9
    dynamic LG     = 7/9
    gain           = +1

N-Queens safe dynamic:
    best single LG = 5/5
    dynamic LG     = 5/5
    gain           = 0
```

Plain-language meaning:

```text
Dynamic LG does not automatically improve every task.
Most existing task files already had one LG depth that solved all cases LG_dynamic could solve.
The only clear gain in saved results was N-Queens old small: 6/9 -> 7/9.
```

Important interpretation:

```text
LG_dynamic is useful as a safety strategy:
try several depths and keep any successful result.
But it is not guaranteed to improve over the best single depth if that best depth already covers the cases.
```

## T measurement v1

Date: 2026-05-25

Purpose:

```text
Create a measurement T that describes how useful G is for a task.
Try using this as a transfer signal between NP tasks.
```

Run:

```text
python analyze_T_transfer.py --out T_transfer_analysis.csv
```

Formula:

```text
T = success_gain + 0.05 * decision_gain + 0.02 * forced_steps
```

Plain-language meaning:

```text
T is high when LG solves more, guesses less, and gets more forced consequences.
T is low when G does not add much.
T is negative when G hurts in that mode.
```

Key results:

```text
Graph Coloring:
    T around 0.8-1.0
    LG strongly useful.

SAT:
    T around 0.68-0.78
    LG strongly useful.

N-Queens:
    T around 0.6-0.69 for lookahead.
    LG useful.

Subset Sum:
    T around 0.1-0.14
    G mostly neutral in this setup.

Vertex Cover greedy:
    T = -0.183
    Greedy G can hurt.
```

Interpretation:

```text
T can classify tasks/modes:
    high T      -> use LG
    low T       -> L/lookahead may already be enough
    negative T  -> G must be used carefully, usually with lookahead
```

Limit:

```text
This is an empirical measurement, not a theorem.
The coefficients in T are first-version heuristic weights.
```

## Q/T ranking v1

Date: 2026-05-25

Purpose:

```text
Sort completed NP-task experiments by:
Q = difficulty for L
T = usefulness of G
Q*T = best candidates where G matters most
```

Run:

```text
python analyze_QT_ranking.py --out QT_ranking.csv
```

Top results:

```text
N-Queens depth2:
    Q=1.000
    T=0.690
    Q*T=0.690

N-Queens depth3:
    Q=0.778
    T=0.606
    Q*T=0.471

Graph Coloring depth2:
    Q=0.400
    T=1.010
    Q*T=0.404

Graph Coloring greedy:
    Q=0.383
    T=1.031
    Q*T=0.395

SAT greedy:
    Q=0.550
    T=0.676
    Q*T=0.372

SAT depth3:
    Q=0.450
    T=0.782
    Q*T=0.352
```

Plain-language meaning:

```text
The best places to continue are where:
1. L struggles.
2. G gives a big improvement.

Right now those are:
    N-Queens
    Graph Coloring
    SAT
    Clique in simpler modes
```

Negative example:

```text
Vertex Cover greedy:
    Q*T = -0.006

Meaning:
    G used greedily can hurt there.
```

## M/T memory v1

Date: 2026-05-25

Purpose:

```text
Build first task memory:
M = measurement/passport of a solved task family.
T = recommended strategy sequence for a future similar task.
```

Run:

```text
python build_M_T_memory.py --out-prefix M_T_memory
```

Files:

```text
M_T_memory_measurements.csv
M_T_memory_strategies.csv
```

Important correction:

```text
First run incorrectly allowed dpll_control as an L-mode for SAT.
This was fixed.
M/T now compares only L modes with LG modes.
```

Result:

```text
Graph Coloring:
    Q=0.267
    M=0.878
    T=greedy_LG -> lookahead_LG_2 -> greedy_L -> lookahead_LG_3

SAT:
    Q=0.450
    M=0.782
    T=lookahead_LG_3 -> greedy_LG -> greedy_L -> lookahead_L_3

N-Queens:
    Q=0.778
    M=0.606
    T=lookahead_LG_3 -> lookahead_LG_2 -> lookahead_L_3 -> greedy_LG

Clique:
    Q=0.033
    M=0.255
    T=lookahead_LG_2 -> lookahead_LG_3 -> lookahead_L_3 -> lookahead_L_2

Subset Sum:
    Q=0.000
    M=0.140
    T=lookahead_LG_2 -> lookahead_L_2 -> lookahead_LG_3 -> lookahead_L_3

Independent Set:
    Q=0.017
    M=0.071
    T=lookahead_LG_2 -> lookahead_LG_3 -> lookahead_L_3 -> lookahead_L_2

Vertex Cover:
    Q=0.033
    M=-0.054
    T=lookahead_LG_2 -> greedy_L -> lookahead_L_2 -> lookahead_LG_3
```

Plain-language meaning:

```text
M is the task passport.
It says how hard the task is for L and how useful G was.

T is the remembered solving sequence.
It says what modes should be tried first on a future similar task.
```

First transfer idea:

```text
If a future task looks like high-M tasks, try LG modes first.
If it looks like low-M tasks, simple lookahead may be enough.
If M is negative, avoid greedy G and use G only with lookahead.
```

## Cross-task test 2: Graph Coloring scaled

Date: 2026-05-25

Expected time:

```text
1-3 minutes
```

Actual time:

```text
about 2.4 minutes
```

Run:

```text
python graph_coloring_lg_test.py --graphs 60 --vertices 18 --colors 3 --edge-prob 0.18 --max-steps 40 --branch-cap 4 --out-prefix graph_coloring_step2_18x60
```

Files:

```text
graph_coloring_step2_18x60_summary_by_mode.csv
graph_coloring_step2_18x60_summary_by_graph.csv
graph_coloring_step2_18x60_logs.jsonl
```

Result:

```text
greedy_L        37/60 = 61.7%
greedy_LG       53/60 = 88.3%
lookahead_L_2   36/60 = 60.0%
lookahead_LG_2  54/60 = 90.0%
lookahead_L_3   44/60 = 73.3%
lookahead_LG_3  54/60 = 90.0%
```

Statistical paired comparison:

```text
greedy_L vs greedy_LG:
    LG_only = 16
    L_only  = 0
    p       = 0.0000305

lookahead_L_2 vs lookahead_LG_2:
    LG_only = 18
    L_only  = 0
    p       = 0.00000763

lookahead_L_3 vs lookahead_LG_3:
    LG_only = 10
    L_only  = 0
    p       = 0.001953
```

Cost comparison:

```text
greedy_L:
    avg_decision_steps = 17.35
    avg_forced_steps   = 0.00

greedy_LG:
    avg_decision_steps = 6.52
    avg_forced_steps   = 11.13

lookahead_L_3:
    avg_decision_steps = 17.13
    avg_forced_steps   = 0.00

lookahead_LG_3:
    avg_decision_steps = 8.08
    avg_forced_steps   = 9.48
```

Plain-language meaning:

```text
The L/G pattern also holds on graph coloring:
LG solves more graphs than L.
LG needs fewer free guesses.
LG gets many forced consequences from G.
The paired p-values are small, so this is unlikely to be random noise.
```

Check:

```text
No false success=True rows found.
graph_coloring_lg_test.py passed py_compile.
```

Р“Р»Р°РІРЅР°СЏ РїСЂРѕРІРµСЂРµРЅРЅР°СЏ РёРґРµСЏ:

```text
L = Р»РѕРєР°Р»СЊРЅР°СЏ РѕС†РµРЅРєР° СЃРѕСЃС‚РѕСЏРЅРёСЏ.
G = РіР»РѕР±Р°Р»СЊРЅС‹Рµ РїРѕСЃР»РµРґСЃС‚РІРёСЏ РІС‹Р±РѕСЂР° С‡РµСЂРµР· propagation.
```

Р§С‚Рѕ РїРѕРґС‚РІРµСЂР¶РґРµРЅРѕ РЅР° С‚РµРєСѓС‰РµРј СѓСЂРѕРІРЅРµ:

```text
1. РќР° РјР°Р»РµРЅСЊРєРёС… SAT DPLL СЃРѕРІРїР°Р» СЃ brute force.
2. Р›РѕР¶РЅС‹С… success=True РЅРµ РЅР°Р№РґРµРЅРѕ.
3. РџСЂРё СЂРѕСЃС‚Рµ SAT РґРѕ 18/20 РїРµСЂРµРјРµРЅРЅС‹С… LG РґРµСЂР¶РёС‚СЃСЏ Р»СѓС‡С€Рµ, С‡РµРј L.
4. lookahead_LG_2 РЅР° SAT 18/20 РґРѕСЃС‚РёРі 80%, РєР°Рє Рё dpll_control.
5. lookahead_L_2 РЅР° С‚РµС… Р¶Рµ С„РѕСЂРјСѓР»Р°С… РґР°Р» С‚РѕР»СЊРєРѕ 30%.
```

РљР»СЋС‡РµРІС‹Рµ РґР°РЅРЅС‹Рµ SAT 18/20:

```text
dpll_control    8/10 = 80%
greedy_L        3/10 = 30%
greedy_LG       3/10 = 30%
lookahead_L_2   3/10 = 30%
lookahead_LG_2  8/10 = 80%
random          0/10 = 0%
```

РљР»СЋС‡РµРІР°СЏ РјРµС‚СЂРёРєР° СЃС‚РѕРёРјРѕСЃС‚Рё:

```text
lookahead_L_2:
success_rate        30%
avg_decision_steps  17.8
avg_forced_steps     0.0
avg_score_calls   11011.0

lookahead_LG_2:
success_rate        80%
avg_decision_steps   5.8
avg_forced_steps    11.5
avg_score_calls   5068.2
```

РРЅС‚РµСЂРїСЂРµС‚Р°С†РёСЏ:

```text
G РЅРµ РїСЂРѕСЃС‚Рѕ СѓР»СѓС‡С€Р°РµС‚ РїСЂРѕС†РµРЅС‚ СѓСЃРїРµС…Р°.
G СѓРјРµРЅСЊС€Р°РµС‚ РєРѕР»РёС‡РµСЃС‚РІРѕ СЃРІРѕР±РѕРґРЅС‹С… СЂРµС€РµРЅРёР№, РїРѕС‚РѕРјСѓ С‡С‚Рѕ С‡Р°СЃС‚СЊ РїРѕРёСЃРєР° РїСЂРµРІСЂР°С‰Р°РµС‚СЃСЏ
РІ РІС‹РЅСѓР¶РґРµРЅРЅС‹Рµ РїРѕСЃР»РµРґСЃС‚РІРёСЏ.
```

РћСЃС‚РѕСЂРѕР¶РЅС‹Р№ РІС‹РІРѕРґ:

```text
РќР° С‚РµРєСѓС‰РёС… РјР°Р»С‹С… Рё СЃСЂРµРґРЅРёС… С‚РµСЃС‚Р°С… РёРґРµСЏ L/G СЂР°Р±РѕС‚Р°РµС‚.
Р­С‚Рѕ РЅРµ РґРѕРєР°Р·Р°С‚РµР»СЊСЃС‚РІРѕ P = NP, РЅРѕ СЌС‚Рѕ СѓСЃС‚РѕР№С‡РёРІС‹Р№ СЌРєСЃРїРµСЂРёРјРµРЅС‚Р°Р»СЊРЅС‹Р№ СЃРёРіРЅР°Р»:
Р»РѕРєР°Р»СЊРЅР°СЏ РѕС†РµРЅРєР° L СЃР»Р°Р±РµРµС‚, Р° РіР»РѕР±Р°Р»СЊРЅРѕРµ СЂР°СЃРїСЂРѕСЃС‚СЂР°РЅРµРЅРёРµ G СѓРґРµСЂР¶РёРІР°РµС‚ РєР°С‡РµСЃС‚РІРѕ.
```

