#!/usr/bin/env python3
"""
make_gauss2_eps_sweep.py: eps sweep with the zero-second-moment blob (gaussianKernel = gauss2, gaussianCutoff 3.8), run 2026-10-29 from the earlier small4.par (gauss, eps 0.05, N_p 40); same meshes,
N_p and par as the make_eps_sweep.py sweep, so the gauss runs of that sweep (small4 and family s) are the comparison.

    python3 make_gauss2_eps_sweep.py        -> m8{fam}_<tag>/{.box, .par, .usr, coordinates}

Families: "" = cases/small4 (contact-free), s = one cilium at the box centre, beta 0.
The .re2 comes from genbox: echo <name>.box | genbox > genbox.log && mv box.re2 <name>.re2
This only writes the case folders. The runs and their logs aren't in this repo, so run them yourself.
"""
from pathlib import Path
from make_eps_sweep import BOX, RUNS, SMALL4, sub1
import re

HERE = Path(__file__).parent
TAGS = ["e100", "e100_h2", "e071", "e050_h1", "e050", "e035t"]
FAMILIES = {"": None, "s": "coordinates_single.txt"}
COORDS = {"coordinates_single.txt": "0.0 0.0 0.0\n"}


def main():
    par0 = (SMALL4 / "small4.par").read_text()
    for fam, cfile in FAMILIES.items():
        for tag in TAGS:
            eps, nx, nz, np_ = RUNS[tag.rstrip("t")]
            name = f"m8{fam}_{tag}"
            out = HERE / name
            out.mkdir(exist_ok=True)
            (out / f"{name}.box").write_text(BOX.format(tag=tag, eps=eps, nx=nx, nz=nz, np=np_).replace("eps sweep", "gauss2 eps sweep"))
            par = sub1(r"^endTime *=.*$", "endTime = 2.0", par0)
            par = sub1(r"^checkpointInterval *=.*$", "checkpointInterval = 0.05         # 20 wall frames per cycle", par)
            par = sub1(r"^(numPanels *= *)\d+", rf"\g<1>{np_}", par)
            par = sub1(r"^(gaussianWidth *= *)[0-9.e-]+", rf"\g<1>{eps:g}", par)
            par = sub1(r"^(gaussianCutoff *= *)[0-9.e-]+.*$", r"\g<1>3.8               # gauss2 loses 3.8e-4 of its mass beyond 3.4 eps, 3.1e-5 beyond 3.8", par)
            if "gaussianKernel" not in par:   # an earlier small4.par
                par = sub1(r"^(rampTime *=.*)$", "gaussianKernel       = gauss2            # zero second moment\n\\1", par)
            if tag.endswith("t"):
                par = re.sub(r"^residualTol *=.*$", "residualTol = 1.0e-5             # tight solves (coupling noise floor at eps 0.035)", par, flags=re.M)
            if cfile is None:
                (out / "coordinates_small4.txt").write_text((SMALL4 / "coordinates_small4.txt").read_text())
            else:
                par = sub1(r"coordinates_small4\.txt", cfile, par)
                (out / cfile).write_text(COORDS[cfile])
            (out / f"{name}.par").write_text(par)
            (out / f"{name}.usr").write_text((SMALL4 / "small4.usr").read_text())
            print(f"{name}: eps {eps:g}, {nx}x{nx}x{nz} = {nx * nx * nz} elements, N_p {np_}")


if __name__ == "__main__":
    main()
