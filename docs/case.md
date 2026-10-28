# The model and the benchmark case

## Cilia model

Units: the cilium length L and the beat period T = 1/f. The fluid is incompressible Navier–Stokes at Re = 10⁻³.

1. **Kinematics.** Each cilium is N_p straight panels. Their centres and velocities follow the Fulford & Blake (1986) beat: a Fourier series in time up to the 6th harmonic whose coefficients are cubic in arclength s, rotated about z by the cilium's beat direction β and placed at its root.
2. **Fluid velocity at the panels.** `pointInterpolation_t` locates the panel centres in the mesh and interpolates u. The box is periodic in x and y, so panels are wrapped into it first.
3. **Drag.** Resistive-force theory: with V = V_cilium − u split into parts along and across the local tangent, the panel force is f* = R(t) μ l (C_par V_par + C_perp V_perp), with l = L/N_p and a linear start-up ramp R(t).
4. **Relaxation.** f = (1 − γ) f_old + γ f*, γ = 2π f_c dt (≤ 1): a low-pass filter with a dt-independent cut-off that keeps the explicit coupling stable.
5. **Spreading.** Each grid point sums f · exp(−r²/ε²)/(π^{3/2} ε³) over all panels within r_cut (minimum-image distances in x and y), in the OCCA kernel `addCiliaForce`. The result is added to the momentum source.

## `cases/small4`

- Box 1 × 1 × 1.5 (x, y periodic; no-slip wall at z = 0; symmetry at z = 1.5), 10 × 10 × 12 elements, N = 5.
- 4 cilia: a 2 × 2 patch with spacing 0.269 (diagonal 0.380), centred and rotated by a random angle; each cilium's beat direction is drawn around it (`make_small4.py --seed 1`). Neighbouring kernels overlap, as in dense ciliated tissue.
- Settings: dt = 1e-4, bdf2, Navier–Stokes, residual tolerances 1e-4. The start-up transient is gone by t ≈ 0.5 and cycle 2 is periodic to 10⁻⁶.

Regenerate the layout and box with `python3 make_small4.py --seed 1`; the mesh is `small4.re2` (from `small4.box` with `genbox`).

## Reference runs

`cases/small4/p02_reference.out` and `p02_truth.out` hold the `vals` and `wall` lines over t ∈ [1, 2] for

| File | N | dt | Use |
|---|---|---|---|
| `p02_reference.out` | 5 | 1e-4 | production baseline, default gate reference |
| `p02_truth.out` | 7 | 1e-5 | converged reference (`--truth`) |

At N = 5 every quantity except ∫p is converged in N to ~10⁻⁵; ∫p carries a 0.16% N error. dt = 1e-4 costs ~0.08% on the wall quantities against dt = 1e-5. ∫p over a plane depends on the pressure gauge (periodic x, y with a symmetry top), so treat it as a regression check, not as physics.
