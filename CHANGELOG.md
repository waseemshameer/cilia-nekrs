# Changelog

## v0.2.0 (2026-11-01)

Solver tuning and a corrected cilia model. `small4` now runs a beat cycle in about 29 s on one A100, against 210 s in v0.1, and the model it runs is a different (corrected) one, so results are not comparable with v0.1.

Model ([docs/model.pdf](docs/model.pdf)):
- Each cilium's own flow is subtracted from the velocity it samples (`subtractSelfFlow = 1`). Resistive-force theory already contains that flow; counting it twice delivered about half of the intended drag.
- Forces and flow are coupled implicitly, f = f\* within each step, by outer correctors with interface quasi-Newton (IQN-ILS) updates (`couplingScheme = iqn`). The v0.1 relaxation filter (f_c = 1.59) is no longer used; it lowered the mean pumping by about 35%.
- Panel lengths and tangents follow the true arclength of the beat shape (`panelLength = arclength`).
- Zero-second-moment spreading kernel (`gaussianKernel = gauss2`), which removes the first-order error in ε; ε = 0.1, N_p = 20, r_cut = 3.8 ε.
- `small4` rebuilt so its cilia never touch: one beat direction per cell, root lattice turned 28° from the beat.

Solvers and time stepping (`cases/small4/small4.par`):
- Stokes mode, BDF2 at dt = 1e-3 (was Navier–Stokes at 1e-4).
- Velocity: pCG with p-multigrid (Chebyshev–Jacobi, degree 2), projection with 40 vectors, tolerance 3e-3. Pressure: Chebyshev–ASM degree 2, tolerance 3e-3.
- Slip top boundary as `zeroDirichletZ`, with a udf workaround for nekRS v26 averaged normals on aligned faces (`fixAlignedAvgNormals`).
- Diagnostics in one fused device reduction; checkpoints every 0.1.

Other:
- `gate.py` defaults to the new reference `cases/small4/m8_reference_gauss2.out`; the v0.1 references and `--truth` are removed.
- New model document `docs/model.pdf` (LaTeX source and figure script in `docs/model/`).

## v0.1.0 (2026-10-28)

First public release.

- Actuator-filament cilia model as a nekRS v26 udf (`3d.udf`): Fulford & Blake beat shape, resistive-force-theory drag, Gaussian-regularised body force computed in an OCCA kernel, periodic in x and y.
- `cases/small4/`: 4-cilium benchmark case (periodic 1 × 1 × 1.5 box, 1,200 elements) and the script that generates it.
- `gate.py`: regression gate against two reference runs of `small4` (production settings, and N = 7, dt = 1e-5).
- Baseline GPU performance and time profile on one NVIDIA A100 (`docs/performance.md`).
- Generic Slurm job script (`job_template.sh`).
