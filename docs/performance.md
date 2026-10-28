# Performance

Baseline for v0.1: `cases/small4`, production settings (N = 5, dt = 1e-4, Navier–Stokes, default solvers), nekRS v26.0.1, one NVIDIA A100, one MPI rank.

- **0.021 s per step**, about 3.5 min per beat cycle (10,000 steps).
- Start-up: several minutes of JIT compilation on a cold cache, ~1 s warm.

## Where the time goes

2,000 steps with `profileCilia = 1` (the syncs it adds cost ~3%):

| Part | ms/step | share of solve |
|---|---|---|
| Velocity solve (~82 Jacobi-PCG iterations/step) | 16.7 | 70% |
| Pressure solve (2–3 pMG iterations/step) | 4.2 | 18% |
| Diagnostics (every step) | 1.2 | 5% |
| Cilia model (all udf parts below) | 0.58 | 2.4% |
| › point location `find()` | 0.24 | 1.0% |
| › force spreading kernel | 0.20 | 0.8% |
| › velocity interpolation `eval()` | 0.06 | 0.3% |
| › host ↔ device copies | 0.05 | 0.2% |
| › host kinematics and drag | 0.03 | 0.1% |
| Explicit terms, checkpoints, rest | ~1.1 | ~4% |

On this small case the solvers dominate: the velocity Helmholtz problem at μ = 1/Re = 1000 and dt = 1e-4 is diffusion dominated, and Jacobi preconditioning needs many iterations. The cilia model is cheap at 80 panels, but its cost grows with the number of panels (the spreading kernel loops over all of them), so it becomes the bottleneck at scale.

## Next

1. Velocity and pressure solver settings (preconditioner, tolerances, projection).
2. Stokes mode and a larger time step.
3. Cheaper diagnostics.
4. The cilia model on the GPU end to end: neighbour lists for spreading, no per-step host round trips, then multi-GPU scaling to many cilia.
