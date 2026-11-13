# The benchmark case

The cilia model itself is written up in [model.pdf](model.pdf).

## `cases/small4`

- Box 1 × 1 × 1.5 in units of the cilium length (x, y periodic; no-slip wall at z = 0; symmetry plane at z = 1.5), 8 × 8 × 10 elements (640), N = 5. Before v0.5 it was 10 × 10 × 12 ([why it changed](#mesh-per-tile)).
- 4 cilia: a 2 × 2 patch with spacing 0.269 (diagonal 0.380), taken from one basal-body patch of a ciliated cell. All four beat in the cell direction α (`make_small4.py --seed 1` draws α from N(0, 25°)), in phase, and the square lattice is turned 28° from the beat so neighbours stay at least 0.126 L apart (more than one cilium diameter). Neighbouring kernels overlap, as in dense ciliated tissue.
- Settings: Stokes, BDF2, dt = 1e-3 (1,000 steps per beat), N_p = 40, residual tolerances 2e-3 (velocity) and 3e-3 (pressure), implicit IQN coupling with tolerance 3e-5. The start-up transient is gone by t ≈ 0.5 and cycle 2 is periodic.
- Boundary IDs for the solvers come from `small4.usr` (wall = 1, top = 2); the top is `slipZ`.

Regenerate the layout and box with `python3 make_small4.py --seed 1`; the mesh is `small4.re2` (from `small4.box` with `genbox`).

## Tiled cases

The `small4` cell repeated k × ky times: box k × ky × 1.5, 8k × 8ky × 10 elements, 4·k·ky cilia, same settings as `small4`. `python3 make_tiled.py --k K [--ky KY] --seed 1` writes the case (k = 1 reproduces `small4`); the mesh comes from the `.box` with `genbox`. A tiled run is the same flow as `small4` per unit area, so it can be gated against the `small4` reference with `gate.py <log> --per-area <tiles>`.

The tiled cases form one ladder for weak and strong scaling, at 32 tiles (128 cilia, 20,480 elements, 2.56M E·N³) per GPU:

| Case | cilia | elements | GPUs at 32 tiles each |
|---|---|---|---|
| `tiled8x4` | 128 | 20,480 | 1 |
| `tiled8` | 256 | 40,960 | 2 |
| `tiled16x8` | 512 | 81,920 | 4 |
| `tiled16` | 1,024 | 163,840 | 8 |
| `tiled32x16` | 2,048 | 327,680 | 16 |
| `tiled32` | 4,096 | 655,360 | 32 |
| `tiled64x32` | 8,192 | 1,310,720 | 64 |

`tiled4` (64 cilia) stays for the GPU-less mock tests.

## Mesh per tile

8 × 8 × 10 elements per tile since v0.5, down from 10 × 10 × 12. Against the 10 × 10 × 12 reference, `small4` on the coarser mesh passes the gate with a worst metric of ∫∂v/∂z at a cycle L2 of 1.61e-4 and a maximum of 1.08e-3 of peak (1.57e-4 and 9.54e-4 on 10 × 10 × 12), and `tiled8` per area passes with L2 1.57e-4 and maximum 9.96e-4, ∫p included. The gated quantities move ≤ 3e-4 of peak between the two meshes. Local wall shear moves by 0.5% (L2) and 0.9% (maximum), about the size of the error from N_p = 40 and far below the model's own error from the kernel width ε. That local shear isn't gated, so a study that needs it better than ~1% should check it on the finer mesh. `tiled8` steps in 0.557× the time on 4 A100s ([#17](https://github.com/waseemshameer/cilia-nekrs/issues/17)).

## Why Stokes

Stokes is the default. `equation = navierstokes` runs, but isn't part of the gate and hasn't been re-checked with the current model.

The Reynolds number is 1e-3, so advection is negligible. On the v0.1 model, Stokes matched Navier–Stokes to 4.8e-5 of peak on the worst gate quantity at the same cost per step. What it buys is no CFL limit on dt, which is how dt could rise from 1e-4 ([computational.md](computational.md)).

## Meshes

The `small4`, `tiled4`, `tiled8x4`, `tiled8` and `tiled16x8` `.re2` files are in git, the largest at 17.7 MB. A mesh over 20 MB raw is never committed: `tiled16` and up aren't in git, `make_tiled.py` writes their `.box` and coordinates, and you generate the mesh with `genbox`, which comes with Nek5000, not nekRS. `tiled16` is about 35 MB. The stock `genbox` stops at 150,000 elements, so `tiled16x8` is the largest it builds; for bigger boxes, rebuild it with a larger `MAXNEL`.

## Reference run

`cases/small4/reference.out` holds the `cilia`, `vals` and `wall` lines over t ∈ [1, 2] of `small4` at tighter settings than production: dt = 1e-4, coupling tolerance 1e-5, solver tolerances 1e-4. Everything else is the production model, on the finer 10 × 10 × 12 mesh: N = 5, N_p = 40, `gauss2`, ε = 0.1, nekRS on one NVIDIA A100. It has only been run on an A100. Production settings on the production mesh pass the gate against it with a cycle L2 of 1.61e-4 and a maximum of 1.08e-3 of peak on the worst quantity (∫∂v/∂z), so the L2 margin is small: changes that are meant to keep the answer should be judged with it, and changes to dt or tolerances will show up.

The file's name never changes. It is replaced in place only on an answer change, the changelog says when, and each tag holds the reference its statements were measured against.

Pressure in this box (periodic x, y, symmetry top) is fixed only up to a constant. nekRS sets the constant through an unweighted mean over the mesh nodes, which moves when the mesh changes, so the `wall` line logs ∫(p − p̄) with p̄ the volume mean. That is the same on any mesh that resolves the flow, so one reference serves them all.
