# Performance

nekRS v26.0.1, one NVIDIA A100, one MPI rank, N = 5. s/cycle is wall time per beat period T. How each number was reached, change by change, is in [computational.md](computational.md).

## v0.3

| Case | cilia | elements | s/step | s/cycle | correctors/step | cilia model share |
|---|---|---|---|---|---|---|
| `small4` | 4 | 1,200 | 0.030 | ~30 | 2.4 | a few % |
| `tiled8` | 256 | 76,800 | 1.64 | ~1,640 | 4.6 | 2.8% |

- Start-up: several minutes of JIT compilation on a cold cache, ~1 s warm. `tiled8` also needs ~8 min of setup and ~26 GB of host memory.
- The cilia model now scales linearly with the number of cilia: force spreading costs ~35 µs per cilium per corrector.
- Almost all of the step is the fluid solve, done 2–5 times per step by the implicit force–flow coupling (outer correctors). Each corrector is a full pressure + velocity solve at 2–3 iterations per field.

## History

| Version | `small4` s/cycle | `tiled8` cilia share | Main change |
|---|---|---|---|
| v0.1 | 210 | | baseline |
| v0.2, v0.1 model | 7.21 | | solver settings (29×) |
| v0.2 | 29.0 | ~50% (est.) | corrected model, implicit coupling |
| v0.3 | ~30 | 2.8% | binned spreading, IQN on the GPU, IQN restart rule |

## Next

1. Multi-GPU: each rank keeps only the cilia whose kernels reach its elements, then strong and weak scaling on tiled cases.
2. Panel kinematics and binning on the device (the last per-step host work).
3. Fewer correctors per step.
