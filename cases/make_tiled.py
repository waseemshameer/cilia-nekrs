"""
make_tiled.py: the small4 tile repeated k x k times, for profiling at scale.

Box k x k x 1.5 (x, y in [-k/2, k/2]), 10k x 10k x 12 elements, P,P,P,P,W,SYM. Each tile is the
small4 patch (same seed, same draws and options as make_small4.py) shifted to the tile centre.
--rerandomize keeps tile (0, 0) as small4 and gives every other tile its own cell direction
alpha ~ N(0, 25 deg) (patch and beat turned together); check those for crossings between
tiles with studies/cilia_distances.py. k = 1 reproduces small4 (same box lines and coordinates).

    python3 make_tiled.py --k 4 --seed 1  -> tiled4/{coordinates_tiled4.txt, tiled4.box, tiled4.par, tiled4.usr}

The .re2 comes from Nek5000 genbox: genbox < tiled4.box, then mv box.re2 tiled4.re2.
"""
import argparse
import math
import re
from pathlib import Path

import numpy as np

# Production layout constants (as make_small4.py)
SIDE_UM = 5.0e-6          # hexagonal cell side
L_UM = 6.0e-6             # cilium length (length scale)
PATCH_FRACTION = 0.16     # basal-body patch area / cell area
GRID = 3                  # cilia per patch edge

HERE = Path(__file__).parent
SMALL4 = HERE / "small4"

BOX = """-3                     spatial dimension (will create box.re2)
1                      number of fields
#
#    comments: {name}, {n} cilia, small4 tiled {k} x {k}, periodic {k} x {k} x 1.5 (make_tiled.py)
#
#========================================================
#
Box
-{nx} -{nx} -12                               Nelx  Nely Nelz
{x0:g} {x1:g} 1.0                              x0 x1 ratio
{x0:g} {x1:g} 1.0                              y0 y1 ratio
0.0 1.5 1.0                               z0 z1 ratio
P  ,P  ,P  ,P  ,W  ,SYM                   Velocity BC's:  (cbx0, cbx1, cby0, cby1, cbz0, cbz1)
"""


def square_patch(edge, n):
    g = np.linspace(-edge / 2, edge / 2, n)
    X, Y = np.meshgrid(g, g, indexing="xy")
    return np.c_[X.ravel(), Y.ravel()]


def rotate(pts, theta):
    c, s = np.cos(theta), np.sin(theta)
    return pts @ np.array([[c, -s], [s, c]]).T


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, required=True, help="tiles per side")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--alpha-std", type=float, default=25.0)
    ap.add_argument("--beta-std", type=float, default=0.0)
    ap.add_argument("--lattice-angle", type=float, default=28.0)
    ap.add_argument("--rerandomize", action="store_true", help="draw a cell direction per tile (tile 0 stays small4)")
    args = ap.parse_args()
    k = args.k

    # Same draws, in the same order, as make_small4.py
    hs = SIDE_UM / L_UM
    patch_edge = math.sqrt(PATCH_FRACTION * 3 * math.sqrt(3) / 2) * hs
    spacing = patch_edge / (GRID - 1)
    rng = np.random.default_rng(args.seed)
    alpha = rng.normal(0.0, np.deg2rad(args.alpha_std))
    lat = np.deg2rad(args.lattice_angle)
    pts = rotate(square_patch(spacing, 2), alpha + lat)
    beta = rng.normal(alpha, np.deg2rad(args.beta_std), len(pts))

    rows = []
    for j in range(k):
        for i in range(k):
            shift = np.array([i - (k - 1) / 2, j - (k - 1) / 2])
            p, b = pts, beta
            if args.rerandomize and (i, j) != (0, 0):
                a = rng.normal(0.0, np.deg2rad(args.alpha_std))
                p = rotate(square_patch(spacing, 2), a + lat)
                b = rng.normal(a, np.deg2rad(args.beta_std), len(pts))
            rows.append(np.c_[p + shift, b])
    coords = np.vstack(rows)

    name = f"tiled{k}" + ("r" if args.rerandomize else "")
    out = HERE / name
    out.mkdir(exist_ok=True)
    np.savetxt(out / f"coordinates_{name}.txt", coords, fmt="%.16e %.16e %.16e")
    (out / f"{name}.box").write_text(BOX.format(name=name, n=len(coords), k=k, nx=10 * k, x0=-k / 2, x1=k / 2))

    par = (SMALL4 / "small4.par").read_text()
    par, n = re.subn(r"coordinates_small4\.txt", f"coordinates_{name}.txt", par)
    assert n == 1
    (out / f"{name}.par").write_text(par)
    (out / f"{name}.usr").write_text((SMALL4 / "small4.usr").read_text())

    d = coords[:, None, :2] - coords[None, :, :2]
    d -= k * np.round(d / k)  # periodic images, box side k
    r = np.hypot(d[..., 0], d[..., 1])
    np.fill_diagonal(r, np.inf)
    print(f"{name}: {len(coords)} cilia, {100 * k * k * 12} elements, box {k} x {k} x 1.5")
    print(f"nearest-neighbour distance incl. images: min {r.min(axis=1).min():.4f}, max {r.min(axis=1).max():.4f}")


if __name__ == "__main__":
    main()
