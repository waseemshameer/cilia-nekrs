# The gate is cycle L2 plus a backstop, against one fixed reference

A change keeps the answers only if `small4` at production settings stays within a cycle L2 of 2e-4 and a maximum of 2e-3 of each metric's own peak over t ∈ [1, 2] (|V|max: its cycle integral within 1e-3), against one reference at tighter settings, and the change doesn't deliberately alter the model or its resolution. Every release is compared with the same reference, so small passing moves can't add up.

## Considered options

- **Maximum pointwise difference alone, at 1e-3 of peak** (the earlier gate). Rejected: it's an extreme-value statistic, so runs differing only in where the coupling iteration stopped scored 7.5e-4 to 1.03e-3, a coin toss at the limit. The time-step error alone uses about two thirds of that budget on ∫dv/dz.
- **Filtering the coupling-stop jitter out of the signal.** Rejected: the jitter is correlated over 5–20 steps, and no filter window separates it cleanly from the smooth error.
- **A higher-order "truth" reference** (N = 7, dt = 1e-5). Dropped: the question is whether a change moved the answer, not how far the answer is from the exact solution.

## Evidence

On existing runs, all 15 production-equivalent comparisons pass (L2 1.43–1.63e-4) and all 5 must-fail comparisons fail (L2 2.30e-4 to 1.07e-3), with no overlap. The L2 limit sits 1.23× above the passing band, and `couplingTol` 1e-4 fails by 1.15×. The maximum exists because L2 dilutes an isolated bad step: a lone 3e-3 step adds only about 1e-4 to L2 over 1,000 steps. Passing maxima reach 1.03e-3 and must-fail ones start at 1.58e-3.

## Consequences

- The gate compares runs of the same model, so it says nothing about model error such as the ε error in wall shear. That is why a deliberate model or resolution change counts as an answer change even when it passes: N_p 40 → 80 scores L2 1.61e-4 and moves ū by 0.12%.
- The margin is narrow, and the reference has only been run on an A100. Whether it passes on other hardware is unmeasured.
- `small4` can't test multi-rank cilia code, since on 2 ranks one rank owns all 4 cilia, so releases add a multi-GPU run ([releasing.md](../releasing.md)).
