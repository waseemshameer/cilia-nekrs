# cilia-nekrs

GPU simulation of flow driven by beating cilia, in [nekRS](https://github.com/Nek5000/nekRS) (v26).

Each cilium is an actuator filament: a chain of panels that follows a prescribed beat (Fulford & Blake 1986). Every time step the panels feel the local fluid velocity, resistive-force theory turns the slip into a force, and that force goes back into the fluid as a Gaussian-regularised body force. The model lives entirely in one udf (`3d.udf`); the spreading of panel forces onto the grid is an OCCA kernel, so the same code runs on NVIDIA, AMD and Intel GPUs.

The current focus is GPU performance and scaling toward very large numbers of cilia. v0.1 is the starting point: a small benchmark case, a regression gate, and a baseline profile.

## Quick start

You need a working nekRS v26 install (`nrsmpi` on your `PATH`), Python 3 with NumPy.

```bash
git clone https://github.com/waseemshameer/cilia-nekrs.git
cd cilia-nekrs/cases/small4
nrsmpi small4 1 | tee small4.log          # or: sbatch ../../job_template.sh small4
```

The first run JIT-compiles the kernels (several minutes); later runs reuse the cache. `small4.par` stops at t = 0.1. To check a change against the reference, set `endTime = 2.0` (two beat cycles, ~7 min on one A100) and run

```bash
python3 ../../gate.py small4.log          # PASS if every quantity is within 0.1% of peak over cycle 2
```

## Contents

| Path | What |
|---|---|
| `3d.udf` | The cilia model: beat kinematics, RFT drag, force relaxation, Gaussian spreading kernel, diagnostics |
| `cases/small4/` | Benchmark: 4 cilia in a periodic 1 × 1 × 1.5 box, 1,200 elements, N = 5 |
| `gate.py` | Regression gate against the `small4` reference runs |
| `job_template.sh` | Generic Slurm script; adapt it to your cluster |
| `docs/` | [Running](docs/running.md), [the case](docs/case.md), [performance](docs/performance.md) |

## Citing and acknowledgements

See `CITATION.cff`. Released under the MIT license. The lab, colleagues and computing resources behind this work are acknowledged in [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).
