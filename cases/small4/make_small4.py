"""
make_small4.py: the small4 benchmark, 4 cilia in a periodic 1 x 1 x 1.5 box.

The roots are a 2 x 2 sub-patch of one basal-body patch of the production layout (hexagonal
cells of side 5 um, cilium length 6 um, a 3 x 3 patch covering 16% of the cell): spacing 0.2688
and diagonal 0.380 in units of the cilium length. The patch is centred
in the box and rotated by alpha ~ N(0, 25 deg); each cilium beats at beta ~ N(alpha, 25 deg).

    python3 make_small4.py --seed 1      -> coordinates_small4.txt, small4.box
"""
import argparse
import math
from pathlib import Path

import numpy as np

# Production layout constants
SIDE_UM = 5.0e-6          # hexagonal cell side
L_UM = 6.0e-6             # cilium length (length scale)
PATCH_FRACTION = 0.16     # basal-body patch area / cell area
GRID = 3                  # cilia per patch edge


def square_patch(edge, n):
    g = np.linspace(-edge / 2, edge / 2, n)
    X, Y = np.meshgrid(g, g, indexing="xy")
    return np.c_[X.ravel(), Y.ravel()]


def rotate(pts, theta):
    c, s = np.cos(theta), np.sin(theta)
    return pts @ np.array([[c, -s], [s, c]]).T

BOX = """-3                     spatial dimension (will create box.re2)
1                      number of fields
#
#    comments: small4 benchmark, 4 cilia, periodic 1 x 1 x 1.5 (make_small4.py)
#
#========================================================
#
Box
-10 -10 -12                               Nelx  Nely Nelz
-0.5 0.5 1.0                              x0 x1 ratio
-0.5 0.5 1.0                              y0 y1 ratio
0.0 1.5 1.0                               z0 z1 ratio
P  ,P  ,P  ,P  ,W  ,SYM                   Velocity BC's:  (cbx0, cbx1, cby0, cby1, cbz0, cbz1)
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--alpha-std", type=float, default=25.0)
    ap.add_argument("--beta-std", type=float, default=25.0)
    args = ap.parse_args()

    hs = SIDE_UM / L_UM
    patch_edge = math.sqrt(PATCH_FRACTION * 3 * math.sqrt(3) / 2) * hs
    spacing = patch_edge / (GRID - 1)

    rng = np.random.default_rng(args.seed)
    alpha = rng.normal(0.0, np.deg2rad(args.alpha_std))
    pts = rotate(square_patch(spacing, 2), alpha)
    beta = rng.normal(alpha, np.deg2rad(args.beta_std), len(pts))

    out = Path(__file__).parent
    np.savetxt(out / "coordinates_small4.txt", np.c_[pts, beta], fmt="%.16e %.16e %.16e")
    (out / "small4.box").write_text(BOX)

    d = pts[:, None] - pts[None]
    d -= np.round(d)  # periodic images, box side 1
    r = np.hypot(d[..., 0], d[..., 1])
    np.fill_diagonal(r, np.inf)
    print(f"seed {args.seed}: alpha = {np.degrees(alpha):.1f} deg, beta = {np.round(np.degrees(beta), 1)} deg")
    print(f"spacing {spacing:.4f}; neighbour distances incl. images {np.unique(np.round(r[np.isfinite(r)], 4))}")


if __name__ == "__main__":
    main()
