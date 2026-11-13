# cilia-nekrs

GPU simulation of cilia-driven flow in [nekRS](https://github.com/Nek5000/nekRS): actuator-filament model, benchmark case, regression gate.

[![CI](https://github.com/waseemshameer/cilia-nekrs/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/waseemshameer/cilia-nekrs/actions/workflows/ci.yml)

<p align="center"><img src="docs/model/figures/beat.png" width="720" alt="Fulford-Blake beat: centreline shapes over one cycle and the arclength of the cilium"></p>

Each cilium is an actuator filament: a chain of panels that follows a prescribed beat (Fulford & Blake 1986), samples the fluid velocity, and returns a resistive-force-theory drag to the fluid as a regularised body force. Forces and flow are coupled implicitly within every time step by interface quasi-Newton iterations, as written up in [docs/model.pdf](docs/model.pdf). The model lives in one udf (`cilia.udf`) with OCCA kernels, so it isn't tied to one GPU vendor, though only the NVIDIA A100 has been run so far.

## Status

**Status.** Pre-1.0, developed by one person. `main` can be ahead of the latest release, so use a tag for results. **Known limit:** the mean pumping ū is converged in the kernel width ε (within 0.25% at ε = 0.1 vs ε = 0.035), but the mean wall shear is not: on `small4` it's 26% lower, and it converges only at first order in ε. Local wall stresses keep growing as ε falls, so don't quote wall-shear values as converged.

## Quick start

You need nekRS v26.0 `96b3cf9e` built and on your `PATH` (`nrsmpi`; the commit is pinned in `NEKRS_VERSION`, and the gate fails on any other), and Python 3 with NumPy.

```bash
git clone https://github.com/waseemshameer/cilia-nekrs.git
cd cilia-nekrs/cases/small4
nrsmpi small4 1 | tee small4.log          # or: sbatch ../../job_template.sh small4 (log: small4.out)
```

The first run JIT-compiles the kernels (several minutes); later runs reuse the cache. `small4.par` stops at t = 0.1. To check a change against the reference, set `endTime = 2.0` (two beat cycles, about a minute on one A100) and run

```bash
python3 ../../gate.py small4.log          # PASS if every quantity is within limits over cycle 2
```

More in [docs/running.md](docs/running.md).

## Measured speed

v0.4, NVIDIA A100, N_p = 40, on the v0.4 mesh (10 × 10 × 12 elements per tile; 8 × 8 × 10 since v0.5, [why](docs/case.md#mesh-per-tile)):

- `small4` (4 cilia, 1,200 elements), one GPU: 30.6 s per beat cycle
- `tiled8` (256 cilia, 76,800 elements), one GPU: about 1,540 s per beat cycle
- `tiled8`, 4 GPUs on one node with GPU-aware MPI: about 504 s per beat cycle, 3.05× faster than one GPU (efficiency 0.76)

Details: [performance](docs/performance.md), [how the speed was reached](docs/computational.md), [scaling setup and evidence](docs/scaling.md). What's next: [open Issues](https://github.com/waseemshameer/cilia-nekrs/issues).

## How results are checked

`gate.py` compares the second beat cycle of a `small4` run with `cases/small4/reference.out`. Every quantity must stay within a cycle L2 of 2e-4 and a maximum of 2e-3 of its peak ([the rule and its evidence](docs/running.md#regression-gate)). The reference has only been run on an NVIDIA A100, so whether it passes on other hardware is unmeasured.

The CI badge only means the GPU-less checks passed. It says nothing about answers, which need the gate on a GPU.

## Contents

| Path | What |
|---|---|
| `cilia.udf` | The cilia model: beat kinematics, RFT drag, self-flow removal, spreading kernel, IQN coupling, diagnostics |
| `cases/small4/` | Benchmark: 4 cilia in a periodic 1 × 1 × 1.5 box, 640 elements, N = 5, with the gate's reference |
| `cases/tiled*/`, `cases/make_tiled.py` | `small4` tiled k × ky: the scaling ladder at 128 cilia per GPU ([cases](docs/case.md#tiled-cases)) |
| `gate.py`, `NEKRS_VERSION` | Regression gate against the `small4` reference; the nekRS commit it requires |
| `job_template.sh` | Example Slurm script; adapt it to your cluster. It has only run on one cluster |
| `studies/` | Finished one-off analyses behind model choices; most need your own run logs |
| `tests/` | The udf built without nekRS or a GPU (`udf_mock/`), and tests of the gate and repo checks |
| `tools/` | `log-triage/`, `scaling_timing.py`, repo and release checks |
| `docs/` | [Model (PDF)](docs/model.pdf), [running](docs/running.md), [the case](docs/case.md), [performance](docs/performance.md), [computational work](docs/computational.md), [scaling](docs/scaling.md), [releasing](docs/releasing.md), [decisions](docs/adr/), [log signals](docs/nekrs-log-signals.md) |

`docs/model.pdf` is built from `docs/model/model.tex`, and rebuilt only when a release changes it.

## How this code is written

**How this code is written.** This code is developed with Claude Code, Anthropic's AI coding tool. Claude writes most of the code and docs, and drafts the commit messages, Issues and pull requests. Commits it helped with carry a `Co-Authored-By` line. I make the design and physics decisions and approve each commit. A change that can affect results must pass the `small4` gate before it merges. I am responsible for all of it, including any errors.

## Contributing, citing, licence

- **Contributing:** see [CONTRIBUTING.md](CONTRIBUTING.md).
- **Citing:** see [CITATION.cff](CITATION.cff), and name the tag you used. All versions: DOI [10.5281/zenodo.24012443](https://doi.org/10.5281/zenodo.24012443). A specific result cites its version's DOI, listed on that page.
- **Licence:** MIT, see [LICENSE](LICENSE).
- **Acknowledgements:** the lab, colleagues and computing resources behind this work are in [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).
