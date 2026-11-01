# Performance

`cases/small4`, nekRS v26.0.1, one NVIDIA A100, one MPI rank. s/cycle is wall time per beat period T, measured over the two-cycle gate runs. Runs were on different A100 nodes, which differ by a few percent.

## v0.2: 29 s per cycle

Production settings (`small4.par`): Stokes, BDF2, dt = 1e-3, implicit IQN coupling, ~29 ms per step, **29 s per cycle**. Start-up: several minutes of JIT compilation on a cold cache, ~1 s warm.

Each step runs on average 2.3 fluid solves (the outer correctors of the IQN coupling). At 2–3 solver iterations per field, a corrector costs a fixed ~10 ms (right-hand side, projection, smoother setup, force spreading), so the number of correctors is now the main lever.

## How v0.1 got to v0.2

The solver work (P1) was done on the v0.1 model, then the model was corrected (M), which costs about 4× back, mostly because the implicit coupling needs ~2 solves per step and a smaller dt than the old filtered force.

| Change | s/cycle |
|---|---|
| v0.1 baseline: Navier–Stokes, dt = 1e-4, block CG + Jacobi | 210 |
| velocity initial guess by projection | 136 |
| pressure Chebyshev degree 2 | 131 |
| Stokes mode (same cost per step, no CFL limit) | 131 |
| dt = 2e-3 with a second-order force relaxation | 23.6 |
| velocity projection with 160 vectors | 14.1 |
| `slipZ` top (udf workaround) and velocity p-multigrid | 11.4 |
| velocity tolerance 3e-3 | 9.2 |
| velocity p-multigrid Chebyshev degree 2 | 8.25 |
| velocity projection with 40 vectors | 7.50 |
| pressure tolerance 3e-3 | **7.21** (29× over v0.1) |
| model: self-flow removal | 7.63 |
| model: implicit coupling f = f\* (IQN), dt = 1e-3 | 27.2 |
| model: arclength panels | 28.3 |
| model: zero-second-moment kernel, ε = 0.1, N_p = 20 | **29.0** |

Every row passed the regression gate against the reference of its model at the time.

## Next

1. The cilia model on the GPU end to end: neighbour lists for spreading, no per-step host round trips, the self-flow sum on the device. On `small4` the model is a few percent of a step, but the spreading kernel loops over every panel, so it dominates at scale; it is profiled on larger tiled cases.
2. Fewer or cheaper correctors per step.
3. Multi-GPU scaling to many cilia.
