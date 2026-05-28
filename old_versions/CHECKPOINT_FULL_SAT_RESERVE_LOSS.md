This is an old summary. The current main document is MASTER_PROJECT_REPORT.md.

# CHECKPOINT FULL: SAT Reserve-Loss Probe

Read this first if you are continuing the SAT recursive-scaling work.

## Current goal

We study recursive scaling for SAT cluster selection.

Main question:

```text
When IG drops at level 5, does reserve recover useful_IG?
```

## What already looks true

```text
G beats L on all tested tasks.
D = H / useful_IG is a useful predictor.
danger_rate is roughly constant at 3-4% across levels and n.
Recursive clusters reduce D.
```

## Current problem

```text
For larger n, level-5 clusters become too large.
IG drops at level 5:
n=2000 level5 IG=38 < level4 IG=42
```

## Reserve idea under test

Formulas:

```text
base_useful_IG = IG * (1 - danger_rate)
loss = IG * danger_rate
reserve[var] += part of loss for dangerous variables
recovered = (0.5 ^ level) * overlap * reserve_score
useful_IG_reserve = base_useful_IG + recovered
cap: recovered <= IG
reserve is NOT decreased after use
beta = 0.5
```

## Why the first version failed

```text
overlap was often 0 because reserve and cluster construction were independent.
```

So reserve stayed in memory, but clusters did not move toward the variables that had reserve mass.

## Fix we are implementing now

Make clustering reserve-aware:

```text
when deciding which variables / units to merge into a cluster,
prefer units with higher reserve_score
```

Implementation idea:

```text
cluster merge priority = co-occurrence signal + reserve_score bias
```

This should make clusters themselves contain dangerous variables more often, which should increase overlap and recovered.

## Files changed

```text
sat_recursive_cluster_levels.py
sat_reserve_loss_probe.py
```

### `sat_recursive_cluster_levels.py`

Added optional reserve-aware merge ranking:

```text
build_next_level(..., unit_scores=None, reserve_bias=0.0)
```

Merge ordering now prefers edges with higher adjusted priority:

```text
adjusted = cooccur_count + reserve_bias * (score_a + score_b)
```

Important detail:

```text
eligible edges are filtered by min_cooccur first,
then ranked by the adjusted reserve-aware priority
```

### `sat_reserve_loss_probe.py`

Reserve-aware mode now:

```text
computes unit_scores from current reserve
passes unit_scores into build_next_level
uses reserve_bias only in reserve mode
```

Also kept:

```text
baseline and reserve use the same sampled candidate set
paired summary is written for direct comparison
```

Added CLI option:

```text
--reserve-bias
default: 0.35
```

## Existing outputs

```text
sat_reserve_loss_probe_step1_details.csv
sat_reserve_loss_probe_step1_summary.csv
sat_reserve_loss_probe_step1_paired_summary.csv
```

The old run showed:

```text
reserve_total grows,
but recovered was often near zero,
especially at level 5 on n=2000
```

That is the exact symptom this reserve-aware clustering is meant to fix.

## How to continue

Run the same test:

```text
python sat_reserve_loss_probe.py --sizes 1000 2000 --formulas 3 --max-levels 5 --min-cooccur 2 --base-max-cluster-size 8 --sample-units 500 --beta 0.5 --reserve-bias 0.35 --out-prefix sat_reserve_loss_probe_step2
```

Then compare:

```text
baseline_D_pred vs reserve_D_pred
baseline_useful_IG vs reserve_useful_IG
delta_useful_IG in paired summary
```

## What to look for

Success signal:

```text
level 4-5 reserve_useful_IG > baseline_useful_IG
level 4-5 reserve_D_pred < baseline_D_pred
delta_useful_IG positive in paired summary
```

If it still fails:

```text
increase reserve_bias
or make reserve influence merge order more strongly
or let reserve affect not only merging but also candidate ranking
```

## Notes

```text
The last full run was interrupted by the user before finishing.
The code has been compiled successfully after the reserve-aware change.
```

