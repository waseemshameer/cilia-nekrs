# Building and running

## nekRS

Build nekRS v26 following its [README](https://github.com/Nek5000/nekRS). The case uses only the standard udf interface; no nekRS patches are needed. Tested with v26.0.1 on one NVIDIA A100 (CUDA backend).

## Running a case

Each case directory holds `<case>.par`, `<case>.re2` and a coordinates file; the udf is shared (`udf = ../../3d.udf` in the par).

```bash
cd cases/small4
nrsmpi small4 1                      # 1 MPI rank = 1 GPU
```

On a Slurm cluster, edit `job_template.sh` (partition, modules, `NEKRS_HOME`) and submit it from the case directory: `sbatch ../../job_template.sh small4`. It also sets up a shared JIT cache so new run directories do not recompile.

## Model parameters

Everything the cilia model needs is in the `[CASEDATA]` section of the par. Any key left out takes the default shown there.

| Key | Symbol | Default | Meaning |
|---|---|---|---|
| `coordinatesFile` | | `coordinates.txt` | one cilium per line: `x_root y_root beta` (beat direction, rad) |
| `numPanels` | N_p | 20 | panels per cilium |
| `slenderness` | L/r | 20 | sets C_par = 2π/ln(L/r), C_perp = 2 C_par |
| `gaussianWidth` | ε | 0.1 | width of the regularised force |
| `gaussianCutoff` | r_cut/ε | 3.4 | kernel truncation |
| `rampTime` | T_ramp | 0.01 | linear start-up ramp of the force |
| `relaxCutoffFrequency` | f_c | 1.5915494 | force relaxation, γ = 2π f_c dt |
| `beatFrequency` | f | 1.0 | beat frequency (units of the reference frequency) |
| `ciliumLength` | L_c | 1.0 | cilium length (units of the reference length) |
| `diagnosticInterval` | | 1 | steps between diagnostic lines (0 = off) |
| `profileCilia` | | 0 | 1 = time the udf parts (adds device syncs) |

nekRS lowercases par values, so keep file names lowercase. The fluid viscosity comes from `[FLUID VELOCITY] viscosity` (negative = Re); the RFT drag uses the same μ = 1/Re.

## Output

Every `diagnosticInterval` steps rank 0 prints two lines:

```
time ubar |V|max  vals
time ∫u ∫v ∫p ∫du/dz ∫dv/dz (plane z = 0.001)  ∫p ∫du/dz ∫dv/dz (wall z = 0)  wall
```

`ubar` is the volume-mean x velocity; the integrals are over the whole horizontal plane, in code units. `gate.py` reads these lines. Checkpoints (`*0.f*`) follow `checkpointInterval`, plus `cilia_force_history.bin` so a restart keeps the relaxed forces.

## Regression gate

```bash
python3 gate.py <run log>             # vs production settings (N = 5, dt = 1e-4)
python3 gate.py <run log> --truth     # vs N = 7, dt = 1e-5
```

Both compare cycle 2 (t ∈ [1, 2]) of `small4`, so the run must reach t = 2 with diagnostics at least every 1e-4. A metric passes if max |run − ref| over the cycle is ≤ 0.1% of the reference peak (|V|max is gated on its cycle mean). Exit code 0 means every metric passed. Use the default reference for changes that should not move the answer (solver settings, kernels); use `--truth` for changes to the discretisation (dt, N).
