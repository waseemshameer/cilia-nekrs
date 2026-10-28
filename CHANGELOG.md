# Changelog

## v0.1.0 (2026-10-28)

First public release.

- Actuator-filament cilia model as a nekRS v26 udf (`3d.udf`): Fulford & Blake beat shape, resistive-force-theory drag, Gaussian-regularised body force computed in an OCCA kernel, periodic in x and y.
- `cases/small4/`: 4-cilium benchmark case (periodic 1 × 1 × 1.5 box, 1,200 elements) and the script that generates it.
- `gate.py`: regression gate against two reference runs of `small4` (production settings, and N = 7, dt = 1e-5).
- Baseline GPU performance and time profile on one NVIDIA A100 (`docs/performance.md`).
- Generic Slurm job script (`job_template.sh`).
