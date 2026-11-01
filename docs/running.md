# Building and running

## nekRS

Build nekRS v26 following its [README](https://github.com/Nek5000/nekRS). The case uses only the standard udf interface; no nekRS patches are needed. Tested with v26.0.1 on one NVIDIA A100 (CUDA backend).

The udf works around one nekRS v26 issue: the pressure boundary term reads averaged face normals on aligned slip faces (`zeroDirichletX/Y/Z`), which nekRS fills only for unaligned ones. `fixAlignedAvgNormals()` copies the face normals in at setup (static meshes only). Without it, a `slipZ` top diverges within the first beat cycle.

## Running a case

Each case directory holds `<case>.par`, `<case>.re2`, `<case>.usr` (boundary IDs) and a coordinates file; the udf is shared (`udf = ../../3d.udf` in the par).

```bash
cd cases/small4
nrsmpi small4 1                      # 1 MPI rank = 1 GPU
```

On a Slurm cluster, edit `job_template.sh` (partition, modules, `NEKRS_HOME`) and submit it from the case directory: `sbatch ../../job_template.sh small4`. It also sets up a shared JIT cache so new run directories do not recompile.

## Model parameters

Everything the cilia model needs is in the `[CASEDATA]` section of the par. A key left out takes the udf default, which for several keys is the v0.1 model; `small4.par` sets every key of the current model. The model is described in [model.pdf](model.pdf).

| Key | Symbol | udf default | `small4` | Meaning |
|---|---|---|---|---|
| `coordinatesFile` | | `coordinates.txt` | `coordinates_small4.txt` | one cilium per line: `x_root y_root beta` (beat direction, rad) |
| `numPanels` | N_p | 20 | 20 | panels per cilium |
| `slenderness` | L/r | 20 | 20 | sets C_par = 2π/ln(L/r), C_perp = 2 C_par |
| `gaussianKernel` | | `gauss` | `gauss2` | spreading kernel: Gaussian, or zero-second-moment Gaussian |
| `gaussianWidth` | ε | 0.1 | 0.1 | kernel width |
| `gaussianCutoff` | r_cut/ε | 3.4 | 3.8 | kernel truncation |
| `panelLength` | | `uniform` | `arclength` | panel lengths L/N_p, or the true arclength with the analytic tangent |
| `subtractSelfFlow` | | 0 | 1 | 1 = remove each cilium's own regularised-Stokeslet flow from the sampled velocity |
| `couplingScheme` | | `explicit` | `iqn` | `explicit`: one solve per step (needs relaxation); `iqn`: implicit f = f\* by outer correctors + IQN-ILS |
| `couplingTol` | τ | 1e-4 | 3e-5 | iqn stop: ‖f\* − F‖ ≤ τ ‖f\*‖ |
| `couplingMaxIter` | | 50 | 50 | correctors per step at most |
| `couplingReuse` | q | 8 | 8 | IQN-ILS: secant pairs kept from the last q steps |
| `couplingOmega` | | 0.2 | 0.2 | under-relaxation of the first update when there are no secant pairs |
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

## Regression gate

```bash
python3 gate.py <run log>             # vs cases/small4/m8_reference_gauss2.out
python3 gate.py <run log> --ref <other reference .out>
```

It compares cycle 2 (t ∈ [1, 2]) of `small4`, so the run must reach t = 2. A metric passes if max |run − ref| over the cycle is ≤ 0.1% of the reference peak (|V|max is gated on its cycle mean). Exit code 0 means every metric passed. Use it for changes that should not move the answer (solver settings, kernels, code speed-ups).
