# The benchmark case

The cilia model itself is written up in [model.pdf](model.pdf).

## `cases/small4`

- Box 1 × 1 × 1.5 in units of the cilium length (x, y periodic; no-slip wall at z = 0; symmetry plane at z = 1.5), 10 × 10 × 12 elements, N = 5.
- 4 cilia: a 2 × 2 patch with spacing 0.269 (diagonal 0.380), taken from one basal-body patch of a ciliated cell. All four beat in the cell direction α (`make_small4.py --seed 1` draws α from N(0, 25°)), in phase, and the square lattice is turned 28° from the beat so neighbours stay at least 0.126 L apart (more than one cilium diameter). Neighbouring kernels overlap, as in dense ciliated tissue.
- Settings: Stokes, BDF2, dt = 1e-3 (1,000 steps per beat), residual tolerances 3e-3, implicit IQN coupling with tolerance 3e-5. The start-up transient is gone by t ≈ 0.5 and cycle 2 is periodic.
- Boundary IDs for the solvers come from `small4.usr` (wall = 1, top = 2); the top is `slipZ`.

Regenerate the layout and box with `python3 make_small4.py --seed 1`; the mesh is `small4.re2` (from `small4.box` with `genbox`).

## Reference run

`cases/small4/m8_reference_gauss2.out` holds the `cilia`, `vals` and `wall` lines over t ∈ [1, 2] of `small4` at tighter settings than production: dt = 1e-4, coupling tolerance 1e-5, solver tolerances 1e-4. Production settings pass the gate against it with 8.7e-4 of peak on the worst quantity (∫∂v/∂z), so the margin is small: changes that are meant to keep the answer should be judged with it, and changes to dt or tolerances will show up.

∫p over a plane depends on the pressure gauge (periodic x, y with a symmetry top), so treat it as a regression check, not as physics.
