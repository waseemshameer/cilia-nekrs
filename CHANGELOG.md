# Changelog

## Unreleased

**Answers:** changed in how ∫p is logged; the flow is not. New reference: against the old one every other metric moves ≤ 2e-5 of peak, ∫p 1.7e-3 (L2). `small4` against it, worst metric ∫dv/dz: L2 1.57e-4, L∞ 9.54e-4 of peak. Velocity `residualTol` 2e-3 was within the gate against the old reference (∫dv/dz: L2 1.54e-4, L∞ 8.95e-4).
**Speed:** `tiled8` on 4 GPUs 0.936× s/step (same node); `small4` unchanged.

- The `wall` line logs plane pressure against its volume mean, ∫(p − p̄), instead of ∫p. Raw ∫p carried nekRS's node-mean pressure constant, which moves with the mesh by about 1e-3 of ∫p, so meshes couldn't be compared on it. New reference ([why](docs/case.md#reference-run), [#17](https://github.com/waseemshameer/cilia-nekrs/issues/17)).
- Velocity `residualTol` 3e-3 → 2e-3 in all case `.par` files; pressure stays at 3e-3. At 3e-3 the inexact velocity solve added coupling correctors in the hard phases of the beat on the tiled cases. `tiled8` correctors per step 4.41 → 3.68 ([why](docs/scaling.md#settings-we-keep), [#18](https://github.com/waseemshameer/cilia-nekrs/issues/18)).

## v0.4.0 (2026-11-06)

**Answers:** changed. N_p 20 → 40; worst metric ∫dv/dz moves 3.2e-3 of peak. New reference; production against it: L2 1.53e-4, L∞ 9.32e-4.
**Speed:** 30.6 s/cycle, `small4`, one A100.
**nekRS:** v26.0 `96b3cf9e`.

Development before this point was private. From here on it happens in this repository, so this entry covers everything since v0.3.0 in one step.

Model and answers:
- Production uses N_p = 40 (was 20), measured against N_p = 80 ([docs/running.md](docs/running.md#why-n_p--40)).
- The one reference is now `cases/small4/reference.out`, at N_p = 40.
- New gate rule: cycle L2 ≤ 2e-4 and maximum ≤ 2e-3 of peak, replacing the single 0.1% maximum ([ADR 0002](docs/adr/0002-definition-of-the-gate.md)). `--tol` is replaced by `--tol-l2`, `--tol-max` and `--tol-int`.
- `gate.py` fails if the nekRS commit in the log differs from the new `NEKRS_VERSION`, and it prints file names only.

Code:
- Multiple GPUs: each rank holds its own cilia plus a halo, with kinematics and binning on the device. `tiled8` on 4 GPUs against 1 on one node runs 3.05× faster, an efficiency of 0.76 ([numbers](docs/performance.md)).
- GPU-aware MPI: 38% less s/step on `tiled8` on 4 GPUs, same node, and 4 against 1 GPU passes the gate on cycle 2. It stays off on a machine until a run there shows the same ([rule](docs/scaling.md#load-per-gpu)).
- `3d.udf` is now `cilia.udf`. Analysis scripts moved to `studies/`, and tests to `tests/`.
- `job_template.sh` runs several cases on one node and reads an optional `cluster.env` and per-case `run.env`.
- `cilia.udf` compiles and passes setup in `nekrs-fp32`, and CI keeps it building. Production stays FP64 ([why](docs/scaling.md#advice-we-checked-and-didnt-adopt)).

Project:
- GPU-less CI, a release check, and new docs: [scaling](docs/scaling.md), [releasing](docs/releasing.md), [decisions](docs/adr/), [CONTRIBUTING](CONTRIBUTING.md).

## v0.3.0 (2026-11-02)

The cilia model on the GPU at scale. Same model and same answer as v0.2 (`small4` passes the gate against the v0.2 reference); on the 256-cilium `tiled8` case the cilia model drops from about half of every step to 2.8%, and its cost is now linear in the number of cilia.

- **Binned force spreading** (`addCiliaForceBinned`, on by default; `ciliaBinning = 0` keeps the old all-pairs kernel). Panels are sorted into bins of about half the kernel cut-off each step, and each element visits only nearby bins. 38× faster spreading on `tiled8`, equal to the all-pairs result to round-off.
- **IQN corrector on the GPU:** self-flow subtraction and resistive-force theory in one panel kernel; the IQN iterate and all secant pairs in a device pool; the least-squares update through a small Gram matrix instead of a host QR. IQN update 122× faster on `tiled8`; same result as the host path to round-off.
- **IQN restart rule** `couplingRestart = 10` (set in all case pars): a step that needs 10 correctors drops the older steps' secant pairs. Fixes a coupling breakdown on large cases (every step at the 50-corrector cap) and is the fastest setting tried.
- **Fix:** untyped panel coordinate buffers made nekRS's point search take 8× too many points (crash on large cases).
- New checks `binningCheck = K` and `iqnCheck = K` ([CASEDATA]): run the old path alongside the first K calls and print the difference.
- New cases `cases/tiled2`, `tiled4`, `tiled8` (16, 64, 256 cilia; 4,800, 19,200, 76,800 elements) and their generator `cases/make_tiled.py`. `gate.py --per-area k²` gates a tiled run against `small4`.
- New document [docs/computational.md](docs/computational.md): how a step is computed, every speed-up from v0.1 to v0.3 with its measured gain, and a figure.

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

- Actuator-filament cilia model as a nekRS v26 udf (`3d.udf`, now `cilia.udf`): Fulford & Blake beat shape, resistive-force-theory drag, Gaussian-regularised body force computed in an OCCA kernel, periodic in x and y.
- `cases/small4/`: 4-cilium benchmark case (periodic 1 × 1 × 1.5 box, 1,200 elements) and the script that generates it.
- `gate.py`: regression gate against two reference runs of `small4` (production settings, and N = 7, dt = 1e-5).
- Baseline GPU performance and time profile on one NVIDIA A100 (`docs/performance.md`).
- Generic Slurm job script (`job_template.sh`).
