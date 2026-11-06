# Performance

Speed is measured two ways: wall time per beat cycle (s/cycle) on `small4`, and cilia-cycles per GPU-hour at scale. How each number was reached, change by change, is in [computational.md](computational.md).

## v0.4

nekRS v26.0 `96b3cf9e`, NVIDIA A100, one MPI rank per GPU, N = 5, N_p = 40. Means over all 2,000 steps of a 2-cycle run. The two `tiled8` runs share a node, and the 4-GPU one uses GPU-aware MPI.

| Case | cilia | elements | GPUs | s/step | s/cycle | cilia-cycles per GPU-hour | correctors/step | capped steps |
|---|---|---|---|---|---|---|---|---|
| `small4` | 4 | 1,200 | 1 | 0.0306 | 30.6 | ~470 | 2.45 | 0 |
| `tiled8` | 256 | 76,800 | 1 | 1.54 | ~1,540 | ~600 | 4.74 | 2 |
| `tiled8` | 256 | 76,800 | 4 | 0.504 | ~504 | ~457 | 4.47 | 1 |

- `tiled8` on 4 GPUs is 3.05× faster than on 1, an efficiency of 0.76, and it passes `gate.py` with the 1-GPU run as the reference: worst metric ∫dv/dz, L2 3.2e-5, L∞ 1.80e-4. More in [scaling.md](scaling.md).
- Start-up in these runs: 80 s for `small4`, 327 s for `tiled8` on 1 GPU, 139 s on 4 GPUs. A cold JIT cache can add several minutes. At v0.3, with N_p = 20, `tiled8` needed ~26 GB of host memory.
- These runs have `profileCilia` off, so no cilia model share is quoted at this tag. At v0.3 it was 2.8% of the step on `tiled8`, with force spreading at ~35 µs per cilium per corrector. Timed separately on code between the two tags, `addCiliaForce` is 2.30% of the solve on 4 GPUs ([scaling.md](scaling.md#load-per-gpu)).
- Almost all of the step is the fluid solve, done 2–5 times per step by the implicit force–flow coupling (outer correctors). Each corrector is a full pressure + velocity solve at 2–3 iterations per field.

## History

| Version | `small4` s/cycle | `tiled8` cilia share | Main change |
|---|---|---|---|
| v0.1 | 210 | | baseline |
| v0.2, v0.1 model | 7.21 | | solver settings (29×) |
| v0.2 | 29.0 | ~50% (est.) | corrected model, implicit coupling |
| v0.3 | ~30 | 2.8% | binned spreading, IQN on the GPU, IQN restart rule |
| v0.4 | 30.6 | not timed | N_p = 40, multiple GPUs, GPU-aware MPI on one node |

These compare releases, not back-to-back runs on one node, so small differences aren't speed claims. Work in progress is in [scaling.md](scaling.md) and the [open Issues](https://github.com/waseemshameer/cilia-nekrs/issues).
