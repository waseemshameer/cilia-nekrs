# Building and running

## nekRS

Build nekRS v26.0 `96b3cf9e` following its [README](https://github.com/Nek5000/nekRS). That commit is pinned in `NEKRS_VERSION`; its build files call it 26.0.1, which is the same commit. The case uses only the standard udf interface; no nekRS patches are needed. It has been tested only with this commit on NVIDIA A100 (CUDA backend), so the reference is unmeasured on any other GPU or backend.

The udf works around one nekRS issue, [#722](https://github.com/Nek5000/nekRS/issues/722): the pressure boundary term reads averaged face normals on aligned slip faces (`zeroDirichletX/Y/Z`), which nekRS fills only for unaligned ones. `fixAlignedAvgNormals()` copies the face normals in at setup (static meshes only). Without it, a `slipZ` top diverges within the first beat cycle. The fix hasn't reached a nekRS release yet, so the workaround stays.

## Running a case

Each case directory holds `<case>.par`, `<case>.re2`, `<case>.usr` (boundary IDs) and a coordinates file; the udf is shared (`udf = ../../cilia.udf` in the par).

```bash
cd cases/small4
nrsmpi small4 1                      # 1 MPI rank = 1 GPU
```

On a Slurm cluster, adapt the `#SBATCH` lines of `job_template.sh`, put modules and `NEKRS_HOME` in a `cluster.env` in the submit directory (optional), and submit from the case directory: `sbatch ../../job_template.sh small4`. The log is `small4.out`. The script's header shows how to run several cases on one node and how to set the ranks per run. It also sets up a shared JIT cache so new run directories do not recompile. The script has only run on one cluster, so expect to adapt it.

## Model parameters

Everything the cilia model needs is in the `[CASEDATA]` section of the par. A key left out takes the udf default, which for several keys is the v0.1 model; `small4.par` sets every key of the current model. The model is described in [model.pdf](model.pdf).

| Key | Symbol | udf default | `small4` | Meaning |
|---|---|---|---|---|
| `coordinatesFile` | | `coordinates.txt` | `coordinates_small4.txt` | one cilium per line: `x_root y_root beta` (beat direction, rad) |
| `numPanels` | N_p | 20 | 40 | panels per cilium |
| `slenderness` | L/r | 20 | 20 | sets C_par = 2π/ln(L/r), C_perp = 2 C_par |
| `gaussianKernel` | | `gauss` | `gauss2` | spreading kernel: Gaussian, or zero-second-moment Gaussian |
| `gaussianWidth` | ε | 0.1 | 0.1 | kernel width |
| `gaussianCutoff` | r_cut/ε | 3.4 | 3.8 | kernel truncation |
| `panelLength` | | `uniform` | `arclength` | panel lengths L/N_p, or the true arclength with the analytic tangent |
| `subtractSelfFlow` | | 0 | 1 | 1 = remove each cilium's own regularised-Stokeslet flow from the sampled velocity; 2 = the same, solved per cilium (explicit coupling only) |
| `couplingScheme` | | `explicit` | `iqn` | `explicit`: one solve per step (needs relaxation); `iqn`: implicit f = f\* by outer correctors + IQN-ILS |
| `couplingTol` | τ | 1e-4 | 3e-5 | iqn stop: ‖f\* − F‖ ≤ τ ‖f\*‖ |
| `couplingMaxIter` | | 50 | 50 | correctors per step at most |
| `couplingReuse` | q | 8 | 8 | IQN-ILS: secant pairs kept from the last q steps |
| `couplingOmega` | | 0.2 | 0.2 | under-relaxation of the first update when there are no secant pairs |
| `couplingRestart` | | 0 | 10 | a step that reaches this many correctors drops the earlier steps' secant pairs; 0 = off |
| `couplingFilter` | | 1e-3 | 1e-3 | QR filter for nearly dependent secant columns |
| `relaxScheme` | | `cn` | `none` | force relaxation for the explicit scheme (`cn`, `euler`); `none` = f = f\* |
| `relaxCutoffFrequency` | f_c | 1.5915494 | (unused) | relaxation cut-off, used by `cn` and `euler` only |
| `rampTime` | T_ramp | 0.01 | 0.01 | linear start-up ramp of the force |
| `beatFrequency` | f | 1.0 | 1.0 | beat frequency (units of the reference frequency) |
| `ciliumLength` | L_c | 1.0 | 1.0 | cilium length (units of the reference length) |
| `diagnosticInterval` | | 1 | 1 | steps between diagnostic lines (0 = off) |
| `wallPlaneZ` | | 0.001 | 0.001 | height of the plane for the first set of `wall` integrals |
| `profileCilia` | | 0 | 0 | 1 = time the udf parts (adds device syncs) |
| `iqnVerbose` | | 0 | 0 | 1 = print the residual of every corrector (`iqnres` lines) |
| `ciliaBinning` | | 1 | 1 | 1 = binned force spreading; 0 = the all-pairs loop (same result to round-off) |
| `binWidth` | | 0.5 | 0.5 | target bin width / r_cut |
| `kinematics` | | `fb` | `fb` | `fb`: the Fulford-Blake beat; `rod`: a straight rigid rod, for the drag test in `studies/make_rod_test.py` |
| `rodAxis`, `rodVelocity` | | `z`, `x` | (unused) | rod direction and its virtual velocity direction: x, y or z |
| `rodCentreZ` | | 0.5 | (unused) | height of the rod centre |
| `binningCheck`, `iqnCheck`, `kinematicsCheck` | | 0 | 0 | K > 0: run the old host path alongside the first K calls and print the difference |
| `dumpPanelSteps` | | 0 | 0 | K > 0: print one `panel` line per panel for the first K force calls |
| `tilePeriod` | | 0 | 0 | > 0: print `tileasym` lines, how far the panel forces are from tile-periodic |

nekRS lowercases par values, so keep file names lowercase. The fluid viscosity comes from `[FLUID VELOCITY] viscosity` (negative = Re); the RFT drag uses the same μ = 1/Re. The `iqn` scheme needs `relaxScheme = none`.

## Output

Every `diagnosticInterval` steps rank 0 prints

```
time ubar |V|max  vals
time ∫u ∫v ∫p ∫du/dz ∫dv/dz (plane z = wallPlaneZ)  ∫p ∫du/dz ∫dv/dz (wall z = 0)  wall
```

and with `couplingScheme = iqn` one line per step

```
time correctors relative-residual steps-that-hit-couplingMaxIter  iqn
```

`ubar` is the volume-mean x velocity; the integrals are over the whole horizontal plane, in code units. `gate.py` reads the `vals` and `wall` lines. Checkpoints (`*0.f*`) follow `checkpointInterval`, plus `cilia_force_history.bin` so a restart keeps the panel forces.

## Why N_p = 40

Measured on `small4` (base mesh 10 × 10 × 12, N = 5, dt 1e-3, tightened solver tolerances) against N_p = 80:

| N_p | worst metric (∫dv/dz), relative to peak | mean ū | mean wall shear |
|---|---|---|---|
| 10 | 1.9e-2 | +2.54% | +7.4% |
| 15 | 7.6e-3 | +1.12% | +3.4% |
| 20 | 4.0e-3 | +0.62% | +1.9% |
| 40 | 1.00e-3 | +0.12% | +0.38% |

Convergence is about second order. A Richardson estimate puts N_p = 40's own error at about 0.16% in ū and 0.5% in mean wall shear. Time per step did not change between N_p 10 and 80 on this case, so the finer setting costs nothing here. N_p = 20 to 40 moved the answer by the same amount on the base mesh (3.22e-3) and on the finest mesh tested (3.16e-3), so the mesh and N_p errors are independent.

## What N_p, ε and the cutoff cost

Measured on `small4` on one A100 and one node, with one change per run from the production settings (`studies/make_cost_sweep.py`). Time per step is cycle 2; the control is 0.0307 s/step. Mean wall shear is relative to the reference.

| Change | Time per step | Gate | Mean wall shear |
|---|---|---|---|
| r_cut 3.4 ε | +1.2% | pass | −0.01% |
| r_cut 3.0 ε | +4.9% | fail | −0.19% |
| N_p 20 | −1.6% | fail | +1.5% |
| N_p 30 | −0.8% | fail | +0.42% |
| N_p 80 | +5.0% | pass | −0.37% |
| ε 0.13 | −5.1% | fail | −17% |
| ε 0.0707 | +10.1% | fail | +15% |
| ε 0.05 | +32.6% | fail | +26% |

So all three stay: N_p = 40, ε = 0.1, r_cut = 3.8 ε. The cilia model is about 6% of the step here and 2.8% on `tiled8`, so N_p and the cutoff have little time to give. A shorter cutoff also backfires: spreading gets cheaper, but the sharper truncation adds about 5% more velocity iterations at 3.0 ε. Only ε changes the fluid solve much, and it does so by changing the answer.

## Regression gate

```bash
python3 gate.py <run log>             # vs cases/small4/reference.out
python3 gate.py <run log> --ref <other reference .out>
```

The run must use the nekRS commit in `NEKRS_VERSION`: the gate fails if the SHA in the log header differs or is missing.

It compares cycle 2 (t ∈ [1, 2]) of `small4`, so the run must reach t = 2. A metric passes two tests, each relative to that metric's own reference peak: the cycle L2 of run − ref (the square root of the cycle mean of the squared difference) is ≤ 2e-4 (`--tol-l2`), and max |run − ref| over the cycle is ≤ 2e-3 (`--tol-max`). The second catches isolated bad steps, which L2 dilutes. |V|max is instead gated on its cycle integral, within 1e-3 (`--tol-int`). Exit code 0 means every metric passed.

The limits were set on 18 existing `small4` runs. Production-equivalent runs have a worst L2 of about 1.6e-4 (on ∫dv/dz) and a worst max of 1.03e-3. Each of these fails: dt 2e-3, `couplingTol` 1e-4, `couplingMaxIter` 2, and N_p 20 against an N_p 40 reference. The gate compares runs of the same model, so it says nothing about model error such as the ε error in wall shear. Use it for changes that should not move the answer (solver settings, kernels, code speed-ups). `--window T0 T1` changes the compared interval, and `--per-area A` divides the run's wall integrals by A, for a k × k tiled case against `small4` (A = k²). Why the gate is built this way: [ADR 0002](adr/0002-definition-of-the-gate.md).

A change that can affect results must pass before it merges. A release adds a multi-GPU run, because `small4` can't test multi-rank cilia code ([releasing.md](releasing.md)).

## What stays stable

A version number promises these three things:

- **The `[CASEDATA]` table** above.
- **All `gate.py` options:** `--ref`, `--window`, `--tol-l2`, `--tol-max`, `--tol-int`, `--per-area`.
- **Answers:** the `small4` metrics the gate reads, compared against `cases/small4/reference.out`.

A change to any of these means a new minor version, and a patch never changes answers.
