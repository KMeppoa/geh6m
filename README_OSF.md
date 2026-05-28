# Chain-Forcing Search Depth OSF Package

Author: Sargis Garibyan

This package documents an empirical framework for studying chain-forcing search depth in NP-style constraint problems.

The central distinction is:

```text
L = local view of the current partial state
G = global consequence expansion caused by a local choice
```

The main formulas are:

```text
useful_IG = IG * (1 - danger_rate)
D = n / useful_IG
```

`D` is a predicted search-depth proxy. The main question is: when does adding `G` reduce `D` compared with local structure alone?

This is an empirical framework, not a proof of `P = NP` or `P != NP`. The work studies measurable behavior: forced consequences, danger rate, useful information gain, recursive clustering, top-down rebuild, and scaling probes.

Main document:

```text
MASTER_PROJECT_REPORT.md
```

Folder layout:

```text
scripts/       all Python scripts found in the project tree
data/          all CSV result, summary, and analysis files
logs/          all JSONL run logs
notes/         text notes and supporting notes
old_versions/ old markdown summaries and project documents with warning headers
```

Start with `MASTER_PROJECT_REPORT.md`; older summaries are preserved only for history.
