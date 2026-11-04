# The benchmark case

The cilia model itself is written up in [model.pdf](model.pdf).

## `cases/small4`

- Box 1 × 1 × 1.5 in units of the cilium length (x, y periodic; no-slip wall at z = 0; symmetry plane at z = 1.5), 10 × 10 × 12 elements, N = 5.
- 4 cilia: a 2 × 2 patch with spacing 0.269 (diagonal 0.380), taken from one basal-body patch of a ciliated cell. All four beat in the cell direction α (`make_small4.py --seed 1` draws α from N(0, 25°)), in phase, and the square lattice is turned 28° from the beat so neighbours stay at least 0.126 L apart (more than one cilium diameter). Neighbouring kernels overlap, as in dense ciliated tissue.
- Settings: Stokes, BDF2, dt = 1e-3 (1,000 steps per beat), N_p = 40, residual tolerances 3e-3, implicit IQN coupling with tolerance 3e-5. The start-up transient is gone by t ≈ 0.5 and cycle 2 is periodic.
- Boundary IDs for the solvers come from `small4.usr` (wall = 1, top = 2); the top is `slipZ`.

Regenerate the layout and box with `python3 make_small4.py --seed 1`; the mesh is `small4.re2` (from `small4.box` with `genbox`).

## `cases/tiled2`, `tiled4`, `tiled8`

The `small4` cell repeated k × k times (k = 2, 4, 8): box k × k × 1.5, 10k × 10k × 12 elements, 4k² cilia (16, 64, 256), same settings as `small4`. `python3 make_tiled.py --k K --seed 1` writes the case (k = 1 reproduces `small4`); the mesh comes from the `.box` with `genbox`. A tiled run is the same flow as `small4` per unit area, so it can be gated against the `small4` reference with `gate.py <log> --per-area K²` (`tiled2` passes). `tiled8` needs ~26 GB of host memory.

## Why Stokes

Stokes is the default. `equation = navierstokes` runs, but isn't part of the gate and hasn't been re-checked with the current model.

The Reynolds number is 1e-3, so advection is negligible. On the v0.1 model, Stokes matched Navier–Stokes to 4.8e-5 of peak on the worst gate quantity at the same cost per step. What it buys is no CFL limit on dt, which is how dt could rise from 1e-4 ([computational.md](computational.md)).

## Meshes

The `small4`, `tiled2`, `tiled4` and `tiled8` `.re2` files are in git, the largest at 16.4 MB. A mesh over 20 MB raw is never committed: it ships as its `.box` and coordinates, and you generate it with `genbox`, which comes with Nek5000, not nekRS. `tiled16`, for example, would be about 65 MB (scaled from `tiled8`, not built).

## Reference run

`cases/small4/reference.out` holds the `cilia`, `vals` and `wall` lines over t ∈ [1, 2] of `small4` at tighter settings than production: dt = 1e-4, coupling tolerance 1e-5, solver tolerances 1e-4. Everything else is the production model: mesh 10 × 10 × 12, N = 5, N_p = 40, `gauss2`, ε = 0.1, nekRS on one NVIDIA A100. It has only been run on an A100. Production settings pass the gate against it with a cycle L2 of 1.56e-4 and a maximum of 1.01e-3 of peak on the worst quantity (∫∂v/∂z), so the L2 margin is small: changes that are meant to keep the answer should be judged with it, and changes to dt or tolerances will show up.

The file's name never changes. It is replaced in place only on an answer change, the changelog says when, and each tag holds the reference its statements were measured against.

∫p over a plane depends on the pressure gauge (periodic x, y with a symmetry top), so treat it as a regression check, not as physics.
