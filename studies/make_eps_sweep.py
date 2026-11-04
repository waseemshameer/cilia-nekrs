#!/usr/bin/env python3
"""
make_eps_sweep.py: epsilon sweep on small4 (same cilia, beat and par as cases/small4, only epsilon, the mesh and N_p change).

The sweep keeps eps / (element size) and eps / (panel spacing L/N_p) fixed at the small4 values (eps 0.1, h 0.1 x 0.1 x 0.125,
N_p 20), plus three controls at one change each.

    python3 make_eps_sweep.py        -> m2_<tag>/{m2_<tag>.box, .par, .usr, coordinates_small4.txt}

The .re2 comes from genbox: echo <name>.box | genbox > genbox.log && mv box.re2 <name>.re2
This only writes the case folders. The runs and their logs aren't in this repo, so run them yourself.
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
SMALL4 = HERE.parent / "cases" / "small4"

# tag: (epsilon, elements in x and y, elements in z, N_p)
RUNS = {
    "e100":      (0.100, 10, 12, 20),   # = small4.par
    "e100_h2":   (0.100, 20, 24, 20),   # control: mesh refined 2x at fixed eps
    "e100_np40": (0.100, 10, 12, 40),   # control: N_p doubled at fixed eps
    "e050_h1":   (0.050, 10, 12, 40),   # control: eps halved on the small4 mesh (eps / GLL gap 1.4-1.7)
    "e071":      (0.0707, 14, 17, 28),
    "e050":      (0.050, 20, 24, 40),
    "e035":      (0.0354, 28, 34, 57),
}
# Family "" is whatever cases/small4 holds: the first sweep ran the earlier small4 (crossing cilia), a later one the contact-free one.
# Families (finding: the earlier small4's cilia 0 and 2 cross, min distance 0.005): same box and beat, other root/beta sets.
#   s: one cilium at the box centre, beta 0 (own periodic image >= 0.36 away);
#   p: small4's roots, all beta = -20 deg (min distance between cilia 0.12).
FAMILIES = {"": None, "s": "coordinates_single.txt", "p": "coordinates_par20.txt"}
FAMILY_RUNS = ["e100", "e071", "e050", "e035"]
# Suffix t: velocity and pressure residualTol 1e-5 (was 3e-3). At eps 0.035 the 3e-3 solves leave a coupling noise floor
# of ~6e-3 > couplingTol (m2p_e035 stuck at couplingMaxIter from t = 0.63; m2s_e035 on 57 steps).
TIGHT = {"": ["e035"], "s": ["e035"], "p": ["e035"]}
COORDS = {"coordinates_single.txt": "0.0 0.0 0.0\n"}

BOX = """-3                     spatial dimension (will create box.re2)
1                      number of fields
#
#    comments: eps sweep {tag}: small4 with eps = {eps}, {nx} x {nx} x {nz} elements, N_p = {np} (make_eps_sweep.py)
#
#========================================================
#
Box
-{nx} -{nx} -{nz}                               Nelx  Nely Nelz
-0.5 0.5 1.0                              x0 x1 ratio
-0.5 0.5 1.0                              y0 y1 ratio
0.0 1.5 1.0                               z0 z1 ratio
P  ,P  ,P  ,P  ,W  ,SYM                   Velocity BC's:  (cbx0, cbx1, cby0, cby1, cbz0, cbz1)
"""


def sub1(pattern, repl, text):
    text, n = re.subn(pattern, repl, text, flags=re.M)
    assert n == 1, pattern
    return text


def main():
    par0 = (SMALL4 / "small4.par").read_text()
    c4 = (SMALL4 / "coordinates_small4.txt").read_text().split("\n")
    COORDS["coordinates_par20.txt"] = "".join(" ".join(l.split()[:2]) + " -0.3490658503988659\n" for l in c4 if l.strip())
    jobs = [(fam, cfile, tag) for fam, cfile in FAMILIES.items() for tag in (RUNS if cfile is None else FAMILY_RUNS)]
    jobs += [(fam, FAMILIES[fam], tag + "t") for fam, tags in TIGHT.items() for tag in tags]
    for fam, cfile, tag in jobs:
        eps, nx, nz, np_ = RUNS[tag.rstrip("t")]
        name = f"m2{fam}_{tag}"
        out = HERE / name
        out.mkdir(exist_ok=True)
        (out / f"{name}.box").write_text(BOX.format(tag=tag, eps=eps, nx=nx, nz=nz, np=np_))
        par = sub1(r"^endTime *=.*$", "endTime = 2.0", par0)
        par = sub1(r"^checkpointInterval *=.*$", "checkpointInterval = 0.05         # 20 wall frames per cycle", par)
        par = sub1(r"^(numPanels *= *)\d+", rf"\g<1>{np_}", par)
        par = sub1(r"^(gaussianWidth *= *)[0-9.e-]+", rf"\g<1>{eps:g}", par)
        if tag.endswith("t"):
            par = re.sub(r"^residualTol *=.*$", "residualTol = 1.0e-5             # tight solves (coupling noise floor at eps 0.035)", par, flags=re.M)
        if cfile is None:
            (out / "coordinates_small4.txt").write_text((SMALL4 / "coordinates_small4.txt").read_text())
        else:
            par = sub1(r"coordinates_small4\.txt", cfile, par)
            (out / cfile).write_text(COORDS[cfile])
        (out / f"{name}.par").write_text(par)
        (out / f"{name}.usr").write_text((SMALL4 / "small4.usr").read_text())
        print(f"{name}: eps {eps:g}, {nx}x{nx}x{nz} = {nx * nx * nz} elements, N_p {np_}, eps/(L/N_p) {eps * np_:.2f}")


if __name__ == "__main__":
    main()
