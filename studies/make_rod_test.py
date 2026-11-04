"""
make_rod_test.py: the straight-rod drag test behind the rod table in docs/model (section Verification).

One straight rigid rod (kinematics = rod in cilia.udf), far from the walls. This script records the
settings of those 10 runs and is frozen: it carries them itself, so later changes to small4.par don't
reach it. The runs were not repeated on later udf versions, so whether today's udf still reproduces the
table is unverified. The rod path is still in the udf, and its defaults (gauss kernel, uniform panels,
explicit coupling) still match these settings.

Box B x B x B (x, y in [-B/2, B/2], z in [0, B]), P,P,P,P,W,SYM, rod centred at (0, 0, B/2).
Elements are 0.1 (as small4) where the Gaussian force sits, x, z in [-0.9, 0.9] and y in [-0.4, 0.4]
around the centre, growing by 1.4 per element to at most 0.5 outside. The rod has velocity 1 along z
in every run, so the net force drives no mean flow (it would in x or y: a Couette flow set by the box).

    python3 make_rod_test.py   -> rod_test/<run>/{<run>.box, <run>.par, <run>.usr, coordinates_rod.txt}

The .re2 comes from genbox: genbox < <run>.box, then mv box.re2 <run>.re2.
"""
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
OUT = HERE / "rod_test"
SMALL4 = HERE.parent / "cases" / "small4"  # only for the .usr, which sets the boundary IDs

# run name: box size B, rod axis (velocity is z), epsilon, polynomial order; each also as <name>_sf
# with subtractSelfFlow = 1 (removes the rod's own regularised-Stokeslet flow)
RUNS = {
    "rod_perp_b4": (4, "x", 0.1, 5),
    "rod_par_b4": (4, "z", 0.1, 5),
    "rod_perp_b8": (8, "x", 0.1, 5),
    "rod_par_b8": (8, "z", 0.1, 5),
    "rod_perp_b4_eps05": (4, "x", 0.05, 7),
}
RUNS.update({k + "_sf": v + (1,) for k, v in RUNS.items()})

PAR = """userSections = CASEDATA

[GENERAL]
stopAt = endTime
endTime = 1.0                   # steady drag (relaxation time 0.1)
dt = 2.0e-3                     # largest passing dt with cn (6.8e-4 of peak vs the cn dt 1e-4 reference), 23.6 s/cycle
timeStepper = bdf2              # bdf3 is more accurate at 2e-3 but 30% slower per cycle
udf = ../../../cilia.udf   # the shared udf at the repo root
polynomialOrder = {N}

checkpointControl = simulationtime
checkpointInterval = 1.0

[PROBLEMTYPE]
equation = stokes                # passes the gate, same s/step as NS

[FLUID PRESSURE]
smootherType = fourthoptcheby+asm+degree=2   # pressure 71.9 -> 65.4 s per 2 cycles, 1.035x
residualTol = 3.0e-3             # 1e-4 -> 3e-3 cuts pressure 25% (same node), 8.12 -> 7.21 s/cycle ex. checkpointing

[FLUID VELOCITY]
boundaryTypeMap = wall, slipZ   # IDs from small4.usr; slipZ needs fixAlignedAvgNormals in cilia.udf (nekRS v26 bug)
solver = pcg                    # pMG (needs the non-block solver) 14.2 -> 11.4 s/cycle
preconditioner = multigrid
initialGuess = projectionAconj+nVector=40    # projection 1.43x; 160 vectors (default 5) 23.6 -> 14.1 s/cycle; 40 with degree 2, 8.25 -> 7.50
residualTol = 3.0e-3             # 1e-4 -> 3e-3 gives 11.4 -> 9.2 s/cycle, gate metrics unchanged
smootherType = fourthoptcheby+jac+degree=2   # pMG Chebyshev degree 1 (default) -> 2 gives 9.17 -> 8.25 s/cycle
density = 1.0
viscosity = -1.0e-3      # negative = Re; the cilia drag uses this mu = 1/Re too

# Cilia model (read by cilia.udf; units of L and T = 1/f).
# Any key left out falls back to the value shown (the udf default).
# nekRS lowercases values, so keep the coordinates filename lowercase.
[CASEDATA]
coordinatesFile      = coordinates_rod.txt # one rod at (0, 0)
numPanels            = 20                # N_p
slenderness          = 20                # L/r -> C_par = 2pi/ln(L/r), C_perp = 2 C_par
gaussianWidth        = {eps:g}
gaussianCutoff       = 3.4               # r_cut / epsilon
rampTime             = 0.01              # T_ramp
relaxCutoffFrequency = 1.5915494         # f_c (= 1.59); gamma = 2 pi f_c dt = 2e-2 at dt = 2e-3
relaxScheme          = cn                # Crank-Nicolson, removes the O(dt) error of euler
beatFrequency        = 1.0               # f / f_ref
ciliumLength         = 1.0               # L_c / L
diagnosticInterval   = 50
kinematics           = rod               # straight rigid rod, no beat
rodAxis              = {axis}
rodVelocity          = z
rodCentreZ           = {zc:g}
subtractSelfFlow     = {sf}
"""


def graded(lo, hi, flo, fhi, h=0.1, growth=1.4, hmax=0.5):
    """Element edges on [lo, hi]: size h on [flo, fhi], growing outward to the ends."""
    def side(dist):  # widths from the fine region out to a boundary at distance dist
        w, out = h, []
        while sum(out) < dist - 1e-9:
            w = min(w * growth, hmax)
            out.append(w)
        return np.array(out) * dist / sum(out)  # stretch to land on the boundary
    nf = round((fhi - flo) / h)
    fine = flo + h * np.arange(nf + 1)
    left = flo - np.cumsum(side(flo - lo))[::-1]
    right = fhi + np.cumsum(side(hi - fhi))
    return np.r_[left, fine, right]


def coords_line(e):  # genbox reads 132-character lines and continues a list on the next line
    return "\n".join(" ".join("%.6f" % v for v in e[i:i + 8]) for i in range(0, len(e), 8))


def main():
    usr = (SMALL4 / "small4.usr").read_text()
    for name, (B, axis, eps, N, *sf) in RUNS.items():
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        zc = B / 2
        ex = graded(-B / 2, B / 2, -0.9, 0.9)
        ey = graded(-B / 2, B / 2, -0.4, 0.4)
        ez = graded(0, B, zc - 0.9, zc + 0.9)
        box = (f"-3                     spatial dimension (will create box.re2)\n"
               f"1                      number of fields\n#\n"
               f"#    comments: {name}, rod test, box {B}, rod axis {axis}, velocity z (make_rod_test.py)\n"
               f"#\n#========================================================\n#\nBox\n"
               f"{len(ex)-1} {len(ey)-1} {len(ez)-1}                               Nelx  Nely Nelz\n"
               f"{coords_line(ex)}\n{coords_line(ey)}\n{coords_line(ez)}\n"
               f"P  ,P  ,P  ,P  ,W  ,SYM                   Velocity BC's:  (cbx0, cbx1, cby0, cby1, cbz0, cbz1)\n")
        (d / f"{name}.box").write_text(box)
        (d / f"{name}.usr").write_text(usr.replace("c small4:", f"c {name} (copied from small4):", 1))
        (d / "coordinates_rod.txt").write_text("0.0 0.0 0.0\n")
        (d / f"{name}.par").write_text(PAR.format(N=N, eps=eps, axis=axis, zc=zc, sf=sf[0] if sf else 0))
        print(name, "elements", (len(ex) - 1) * (len(ey) - 1) * (len(ez) - 1))


if __name__ == "__main__":
    main()
