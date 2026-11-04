#!/usr/bin/env python3
"""
make_resolution_study.py: resolution study of the production model (gauss2, eps 0.1, iqn, dt 1e-3) on small4.

Only the mesh (elements, N) and N_p change; eps stays 0.1 (a model choice). Every run uses tight
tolerances (velocity and pressure residualTol 1e-5, couplingTol 1e-5) so that differences between levels
are discretisation, not the 3e-3 solver / 3e-5 coupling stop jitter (~1e-3 of peak on int dv/dz);
tag tt is the noise check (solver 1e-6, coupling 3e-6) on the base mesh.

    python3 make_resolution_study.py [tag ...]   -> m10_<tag>/{.box, .par, .usr, coordinates_small4.txt}

The .re2 comes from genbox: echo m10_<tag>.box | genbox && mv box.re2 m10_<tag>.re2
"""
import sys
from pathlib import Path
from make_eps_sweep import BOX, SMALL4, sub1
import re

HERE = Path(__file__).parent

# tag: (elements in x and y, elements in z, N, N_p, solver residualTol, couplingTol[, dt])
RUNS = {
    "h10":      (10, 12, 5, 20, 1e-5, 1e-5),   # = small4.par mesh and N_p, tight tolerances
    "h10_tt":   (10, 12, 5, 20, 1e-6, 3e-6),   # tolerance noise check
    "h15":      (15, 18, 5, 20, 1e-5, 1e-5),
    "h20":      (20, 24, 5, 20, 1e-5, 1e-5),
    "h10_n7":   (10, 12, 7, 20, 1e-5, 1e-5),   # splits h from N
    "h15_n7":   (15, 18, 7, 20, 1e-5, 1e-5),   # next level for N 7 (same grid points as h20)
    "p10":      (10, 12, 5, 10, 1e-5, 1e-5),
    "p15":      (10, 12, 5, 15, 1e-5, 1e-5),
    "p40":      (10, 12, 5, 40, 1e-5, 1e-5),
    "p80":      (10, 12, 5, 80, 1e-5, 1e-5),
    "h20_p40":  (20, 24, 5, 40, 1e-5, 1e-5),   # the chosen N_p on the finest mesh
    "ref_p40":  (10, 12, 5, 40, 1e-4, 1e-5, 1e-4),   # gate reference candidate: same settings as the earlier gauss2 reference (dt 1e-4), N_p 40
    "prod_p40": (10, 12, 5, 40, 3e-3, 3e-5),   # production tolerances, N_p 40 (gated against ref_p40)
}


def main():
    par0 = (SMALL4 / "small4.par").read_text()
    for tag in sys.argv[1:] or RUNS:
        nx, nz, n, np_, stol, ctol, *dt = RUNS[tag]
        name = f"m10_{tag}"
        out = HERE / name
        out.mkdir(exist_ok=True)
        box = BOX.format(tag=tag, eps=0.1, nx=nx, nz=nz, np=np_).replace("eps sweep", f"resolution study, N = {n},")
        (out / f"{name}.box").write_text(box)
        par = sub1(r"^endTime *=.*$", "endTime = 2.0", par0)
        par = sub1(r"^checkpointInterval *=.*$", "checkpointInterval = 1.0          # the gate reads the udf lines; no field frames needed", par)
        par = sub1(r"^polynomialOrder *=.*$", f"polynomialOrder = {n}", par)
        par = sub1(r"^(numPanels *= *)\d+", rf"\g<1>{np_}", par)
        par, k = re.subn(r"^residualTol *=.*$", f"residualTol = {stol:.1e}             # tight solves: discretisation, not stop jitter", par, flags=re.M)
        assert k == 2
        par = sub1(r"^(couplingTol *= *)[0-9.e-]+", rf"\g<1>{ctol:g}", par)
        if dt:
            par = sub1(r"^dt *= *[0-9.e-]+", f"dt = {dt[0]:.1e}", par)
        (out / "coordinates_small4.txt").write_text((SMALL4 / "coordinates_small4.txt").read_text())
        (out / f"{name}.par").write_text(par)
        (out / f"{name}.usr").write_text((SMALL4 / "small4.usr").read_text())
        print(f"{name}: {nx}x{nx}x{nz} = {nx * nx * nz} elements, N {n}, N_p {np_}, eps/(L/N_p) {0.1 * np_:.1f}, tol {stol:g}/{ctol:g}")


if __name__ == "__main__":
    main()
