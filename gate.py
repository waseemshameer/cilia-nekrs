#!/usr/bin/env python3
# Accuracy gate: compare a run against a small4 reference over cycle 2 (t in [1, 2]).
#   python3 gate.py <run .out> [--truth | --ref <ref .out>] [--window T0 T1] [--tol 1e-3]
# Default reference: the production baseline (small4, N = 5, dt = 1e-4, NS), i.e. "did the change move the answer".
# --truth compares against N = 7, dt = 1e-5 instead (for changes to the discretisation; production itself is
# 0.18% off there on int p, mostly N, see docs/case.md).
# Reads the udf 'vals' and 'wall' lines. Per metric: max |run - ref| / max |ref| over the window.
# Both series are compared on the coarser of the two time grids (np.interp onto those times).
# |V|max jumps between nodes, so it is gated on its cycle integral; the pointwise max is printed as info.
import argparse, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
p = argparse.ArgumentParser()
p.add_argument('run')
p.add_argument('--ref', default=os.path.join(HERE, 'cases', 'small4', 'p02_reference.out'))
p.add_argument('--truth', action='store_true', help='use cases/small4/p02_truth.out as the reference')
p.add_argument('--window', nargs=2, type=float, default=[1.0, 2.0])
p.add_argument('--tol', type=float, default=1e-3)
a = p.parse_args()
if a.truth: a.ref = os.path.join(HERE, 'cases', 'small4', 'p02_truth.out')
T0, T1 = a.window

# name, line tag, column (after time), gated pointwise
METRICS = [('ubar', 'vals', 1, True), ('|V|max', 'vals', 2, False),
           ('int p (z=0.001)', 'wall', 3, True), ('int du/dz (z=0.001)', 'wall', 4, True),
           ('int u (z=0.001)', 'wall', 1, True), ('int dv/dz (z=0.001)', 'wall', 5, True),
           ('int p (z=0)', 'wall', 6, True), ('int du/dz (z=0)', 'wall', 7, True),
           ('int dv/dz (z=0)', 'wall', 8, True)]

def read(f):
    d = {'vals': [], 'wall': []}
    for l in open(f, errors='replace'):
        s = l.split()
        if s and s[-1] in d:
            try: d[s[-1]].append([float(x) for x in s[:-1]])
            except ValueError: pass
    out = {}
    for k, v in d.items():
        v = np.array(v)
        if len(v) == 0: sys.exit('%s: no %s lines' % (f, k))
        _, i = np.unique(v[:, 0], return_index=True)   # drop repeats after a restart
        out[k] = v[np.sort(i)]
    return out

def window(t):
    return (t >= T0 - 1e-9) & (t <= T1 + 1e-9)

run, ref = read(a.run), read(a.ref)
print('gate: %s\n  ref: %s\n  window t in [%g, %g], tol %.2g of peak\n' % (a.run, a.ref, T0, T1, a.tol))
print('%-22s %14s %14s %8s' % ('metric', 'max|diff|/peak', 'rel cycle int', 'result'))
ok = True
for name, tag, c, pointwise in METRICS:
    tr, yr = ref[tag][:, 0], ref[tag][:, c]
    tc, yc = run[tag][:, 0], run[tag][:, c]
    if tc[-1] < T1 - 1e-9 or tc[0] > T0 + 1e-9:
        print('%-22s %14s %14s %8s' % (name, '-', '-', 'FAIL (run ends at t = %g)' % tc[-1])); ok = False; continue
    tw = tr[window(tr)] if np.diff(tr).mean() >= np.diff(tc).mean() else tc[window(tc)]
    r, y = np.interp(tw, tr, yr), np.interp(tw, tc, yc)
    pk = np.abs(r).max()
    md = np.abs(y - r).max() / pk
    ri = (np.trapz(y, tw) - np.trapz(r, tw)) / (pk * (tw[-1] - tw[0]))   # cycle-mean diff / peak
    v = md if pointwise else abs(ri)
    res = 'PASS' if v <= a.tol else 'FAIL'
    ok &= res == 'PASS'
    print('%-22s %14.2e %14.2e %8s%s' % (name, md, ri, res, '' if pointwise else '  (gated on cycle int)'))
print('\nGATE %s' % ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
