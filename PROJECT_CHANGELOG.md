# Project Changelog

- Early L/G idea: split local state information `L` from global consequence expansion `G`.
- Labyrinth: early toy-domain experiments showed that deeper/global guidance could strongly improve success.
- SAT: L vs LG tests showed that LG reduced free decision steps and increased forced steps.
- Graph Coloring: the L/G effect repeated outside SAT; LG improved success and reduced decision steps.
- Reserve recovery failed: reserve as recovered IG did not work because overlap and recovered values were near zero.
- Reserve navigator: reserve was reinterpreted as feedback for cluster construction rather than a loss-recovery bank.
- Top-down rebuild: weak upper levels send feedback downward, then G4/G5 are rebuilt.
- Fast probe: fast D-scaling was validated against exact measurements on n = 1000, 2000, and 5000.
- Scaling to 1M: large probes showed unstable D; rebuild sometimes gave large wins and sometimes harmed.
- Sweeps failed to find a simple trigger: `min_useful_growth` and raw `topdown_bias` did not explain win/harm.
- Current question: find the structural signal that predicts when top-down rebuild reduces D.
