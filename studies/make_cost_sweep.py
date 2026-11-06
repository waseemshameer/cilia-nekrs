#!/usr/bin/env python3
"""
make_cost_sweep.py: what N_p, the kernel width, the kernel cutoff and the mesh each cost on small4.

One change per run from the production small4.par: same tolerances, dt and model, 2 cycles so gate.py can read
cycle 2, and profileCilia on so the cilia parts are timed. On another mesh, int p also moves through the nodal
pressure gauge (pressure_gauge_check.py shows why), so a gate miss on int p alone doesn't mean the flow moved.

    python3 make_cost_sweep.py [tag ...]   -> ../cases/cost_<tag>/{.box, .par, .usr, coordinates_small4.txt}

The .re2 comes from genbox: echo cost_<tag>.box | genbox && mv box.re2 cost_<tag>.re2
This only writes the case folders. The runs and their logs aren't in this repo, so run them yourself.
"""
import sys
from pathlib import Path
from make_eps_sweep import BOX, SMALL4, sub1

CASES = Path(__file__).parent.parent / "cases"

# tag: (epsilon, r_cut / epsilon, elements in x and y, elements in z, N_p)
RUNS = {
    "base": (0.100, 3.8, 10, 12, 40),   # = small4.par, the control
    "rc34": (0.100, 3.4, 10, 12, 40),   # gauss2 mass lost beyond r_cut: 3.8e-4
    "rc30": (0.100, 3.0, 10, 12, 40),   # 3.3e-3
    "np20": (0.100, 3.8, 10, 12, 20),
    "np30": (0.100, 3.8, 10, 12, 30),
    "np80": (0.100, 3.8, 10, 12, 80),
    "e130": (0.130, 3.8, 10, 12, 40),   # r_cut 0.494, the widest kernel the 1 x 1 box allows at this cutoff
    "e071": (0.0707, 3.8, 10, 12, 40),
    "e050": (0.050, 3.8, 10, 12, 40),
    "h8":   (0.100, 3.8, 8, 10, 40),
    "h6":   (0.100, 3.8, 6, 7, 40),
    "h5":   (0.100, 3.8, 5, 6, 40),
}


def main():
    par0 = (SMALL4 / "small4.par").read_text()
    for tag in sys.argv[1:] or RUNS:
        eps, rcut, nx, nz, np_ = RUNS[tag]
        name = f"cost_{tag}"
        out = CASES / name
        out.mkdir(exist_ok=True)
        box = BOX.format(tag=tag, eps=eps, nx=nx, nz=nz, np=np_).replace("eps sweep", "cost sweep")
        (out / f"{name}.box").write_text(box)
        par = sub1(r"^endTime *=.*$", "endTime = 2.0", par0)
        par = sub1(r"^checkpointInterval *=.*$", "checkpointInterval = 1.0          # the gate reads the udf lines", par)
        par = sub1(r"^(numPanels *= *)\d+", rf"\g<1>{np_}", par)
        par = sub1(r"^(gaussianWidth *= *)[0-9.e-]+", rf"\g<1>{eps:g}", par)
        par = sub1(r"^(gaussianCutoff *= *)[0-9.e-]+", rf"\g<1>{rcut:g}", par)
        par = par.rstrip("\n") + "\nprofileCilia         = 1\n"
        (out / f"{name}.par").write_text(par)
        (out / f"{name}.usr").write_text((SMALL4 / "small4.usr").read_text())
        (out / "coordinates_small4.txt").write_text((SMALL4 / "coordinates_small4.txt").read_text())
        print(f"{name}: eps {eps:g}, r_cut {rcut:g} eps, {nx}x{nx}x{nz} = {nx * nx * nz} elements, N_p {np_}")


if __name__ == "__main__":
    main()
