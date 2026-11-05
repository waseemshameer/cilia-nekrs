# Scaling: setup and evidence

What this project does about nekRS scaling on GPUs, and why. Every setting below was checked against the source of nekRS v26.0 `96b3cf9e` and our own timers. Source paths are relative to that commit. Abbreviated papers are listed at the end.

## Load per GPU

**Unit.** Load per GPU is E·N³, the developers' unit (Min25 Sec 1.1). It's close to the true unique count: `tiled8` has 9.76M unique points, E·N³ gives 9.60M, and E·(N+1)³ gives 16.6M.

**Rule.** The developers' 2–5M per GPU (Min25 Conclusions) is only a starting guess. Production is sized by our own measured n0.8, the load at which parallel efficiency falls to 80%. A value from 8 GPUs or fewer is labelled small-P and optimistic, because Min25 Sec 4 says n0.8 is smaller at small n and P, and that neighbour communication doesn't saturate until P > 26. No load at scale is quoted until a run has gone past that, or says how far it got.

**Measured so far.** One node, host-staged gather-scatter, N_p = 40, steps 11–99 of a run to t = 0.1. These were measured on code newer than v0.3, so they aren't release numbers. Efficiency is against the same case on 1 GPU.

| Case | GPUs | elements per GPU | E·N³ per GPU | s/corrector | efficiency |
|---|---|---|---|---|---|
| `tiled8` | 1 | 76,800 | 9.6M | 0.508 | 1 |
| `tiled8` | 2 | 38,400 | 4.8M | 0.315 | 0.81 |
| `tiled8` | 4 | 19,200 | 2.4M | 0.269 | 0.46 |
| `tiled4` | 1 | 19,200 | 2.4M | 0.127 | 1 |
| `tiled4` | 4 | 4,800 | 0.6M | 0.113 | 0.29 |

So n0.8 lies between 2.4M and 4.8M on up to 4 GPUs, and it isn't named yet. Load alone doesn't set efficiency: `tiled8` on 4 GPUs and `tiled4` on 1 GPU carry the same load per GPU, yet the first costs 2.1× more per corrector. The cilia code isn't the limit, at 1.77% of the solve for `tiled8` on 4 GPUs.

**GPU-aware MPI.** `NEKRS_GPU_MPI=0` on every machine until a run there shows a gain and matches the 1-GPU answer. Off is the v26.0 default (`RELEASE.md:29`) and the developers' advice when the stack can't move device pointers (Discussions [#622](https://github.com/Nek5000/nekRS/discussions/622), [#578](https://github.com/Nek5000/nekRS/discussions/578), [#568](https://github.com/Nek5000/nekRS/discussions/568)). It's worth testing, since Polaris A100 n0.8 goes from 4.5M to 2.5M with it (Min25 Sec 5.3), but it can't be assumed: at 72,000 ranks on Frontier, routing through the host was the better option (Min25 Sec 5.5).

**New advice.** Any new solver advice is checked against the v26.0 parser and our timers before use.

## Settings we keep

| Setting | Evidence |
|---|---|
| FP32 preconditioner, FP64 Krylov | `pfloat = float` is hard-coded (`src/platform/nekrsSys.hpp.in:21-31`), so it can't be turned off |
| Chebyshev+ASM, pressure | The default smoother; degree 2 gave 1.04× on `small4` ([computational.md](computational.md)) |
| Chebyshev+Jacobi, velocity | Degree 2 gave 1.11×; `src/core/elliptic/elliptic.cpp:469-475` requires a Jacobi smoother for velocity multigrid |
| BoomerAMG on the host | The v26.0 default (`doc/parHelp.txt:139-141`); the coarse grid is 3.5 s of about 148 s on 4 GPUs |
| Default pMG schedule | Phi21 Sec 6: order and schedule move time only 10–20% |
| `pcg` non-block velocity | Required with multigrid (`src/core/elliptic/elliptic.cpp:463-467`); 14.2 to 11.4 s/cycle on `small4`. Retest below |
| Projection initial guess | 1.43× at the default 5 vectors, 23.6 to 14.1 s/cycle at 160; settled at 40 once velocity multigrid was in. Vector count retest below |
| gs autotune (`OOGS_MODE` unset), comm overlap on | Min25 Sec 1.4; `src/platform/ogs/oogs.cpp:559`; `src/lib/nekrs.cpp:78` |
| `residualTol` 3e-3 | Passes the gate, 1.25× for velocity and 1.13× for pressure. It's scaled by √volume (`src/core/elliptic/elliptic.cpp:408`), so it means the same on any tile size |

## Under test

In this order, because each one changes the balance between compute and communication.

1. **GPU-aware MPI**, as above ([#3](https://github.com/waseemshameer/cilia-nekrs/issues/3)).
2. **Velocity solver on 4 GPUs:** `pcg` + Jacobi, and 20 projection vectors. Any winner must also pass the gate on `small4` ([#5](https://github.com/waseemshameer/cilia-nekrs/issues/5)).

## Advice we checked and didn't adopt

| Claim | Why not |
|---|---|
| A `.par` using `[PRESSURE]`, `[VELOCITY]`, `precPrecision`, `projectionType`, `projectionVectors`, `advection` or solver `fgmres` | Invalid for v26.0: the sections and keys don't exist in `src/platform/par/par.cpp`, and nekRS aborts on them |
| "15–25k elements per GPU" | In no developer source. We measured 0.46 at 19,200 and 0.81 at 38,400 |
| "Under 5,000 elements stalls in BoomerAMG" | Our 0.29 at 4,800 fits "low efficiency", but Min25 Sec 2 puts the one-GPU limit on kernel-launch latency, and no source gives the BoomerAMG mechanism |
| "3–5× from projection" | The number has no support. Ours: 1.43× at the default, 1.67× at 160 vectors |
| "Coarse-grid allreduce dominates" | The coarse grid is 2.4% of our 4-GPU solve. This rejects the coarse-grid claim only: allreduce in PCG and projection is unmeasured |
| BoomerAMG on the device | The same 2.4%. Reopens only if the coarse grid passes 10% of the solve at scale, because below that even an instant coarse solve saves under 10% |
| Tolerances 1e-6 (pressure) and 1e-8 (velocity) | The gate passes at 3e-3, and they're tighter than the developers' own 1e-4 and 1e-6 (Min25 Sec 2) |
| Whole-solver FP32, the `nekrs-fp32` binary (`CMakeLists.txt:155`, Discussion [#626](https://github.com/Nek5000/nekRS/discussions/626)) | It passes the gate on `small4`, but gains little: 7% with `solver = gmres+flexible+nvector=15` in `[FLUID PRESSURE]`, one run each, because the preconditioner is already float. Its default pressure solver, with iterative refinement, is 9% slower. Float kinematics error grows with t unless t is wrapped into one period. It uses 47% less device memory, but FP64 needs only about 26 GB per GPU at 38,400 elements, on an 80 GB A100. Reopens if the 80% load nears GPU memory ([#4](https://github.com/waseemshameer/cilia-nekrs/issues/4)) |
| Explicit `pMGSchedule`, `[SCALAR01]`, ALE vs immersed boundary | The default schedule is fine, there's no scalar, and the case is already Eulerian |

## Sources

- **Min25:** Min, Lan, Fischer, Rathnayake, Holmen, "Nek5000/RS performance on advanced GPU architectures", *Front. High Perform. Comput.* 2 (2024), [doi:10.3389/fhpcp.2024.1303358](https://doi.org/10.3389/fhpcp.2024.1303358).
- **Phi21:** Phillips, Kerkemeier, Fischer, "Tuning spectral element preconditioners for parallel scalability on GPUs", [arXiv:2110.07663](https://arxiv.org/abs/2110.07663).
