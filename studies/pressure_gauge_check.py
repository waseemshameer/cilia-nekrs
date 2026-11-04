#!/usr/bin/env python3
# Is the mesh dependence of int p (z = 0) the pressure gauge?
# Stokes, periodic x and y, wall z = 0, slip z = H: the area-mean pressure obeys P(z) = P(0) + G(z), G = int_0^z fbar_z (exact).
# nekRS removes the unweighted mean over unique GLL nodes (removeMean, elliptic.cpp), so P(0) = -<G>_nodes depends on the
# node layout in z. Model: force spread uniformly over z < zt. Compare the predicted int p ratio between meshes with the
# observed one (fit d = k p_ref over cycle 2), then print what is left of int p once k is removed.
#   python3 pressure_gauge_check.py <dir holding m10_<tag>.out>
import sys, os
import numpy as np
from numpy.polynomial import legendre as L
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate_metric_compare import read

B = sys.argv[1]
RUNS = {'h10': (12, 5), 'h15': (18, 5), 'h20': (24, 5), 'h10_n7': (12, 7)}   # elements in z, N


def nodes(nz, N, H=1.5):
    x = np.r_[-1, np.sort(np.real(L.Legendre.basis(N).deriv().roots())), 1]
    e = np.linspace(0, H, nz + 1)
    return np.unique(np.round((e[:-1, None] + (x[None] + 1) / 2 * np.diff(e)[:, None]).ravel(), 12))


ref = read(f'{B}/m10_h20.out')['wall']
m = (ref[:, 0] >= 1) & (ref[:, 0] <= 2)
t, pb = ref[m, 0], ref[m, 6]
for zt in [0.6, 0.8, 1.0]:
    g = {r: -np.mean(np.minimum(nodes(*v) / zt, 1)) for r, v in RUNS.items()}
    print(f'zt {zt}: ' + '  '.join(f'{r}/h20 pred {g[r] / g["h20"] - 1:+.2e}' for r in ['h10', 'h15', 'h10_n7']))
for r in ['h10', 'h15', 'h10_n7']:
    a = read(f'{B}/m10_{r}.out')['wall']
    d = np.interp(t, a[:, 0], a[:, 6]) - pb
    k = (d @ pb) / (pb @ pb)
    pk = np.abs(pb).max()
    print(f'{r:7s} observed k {k:+.2e}  raw {np.abs(d).max() / pk:.2e}  residual after k {np.abs(d - k * pb).max() / pk:.2e}')
