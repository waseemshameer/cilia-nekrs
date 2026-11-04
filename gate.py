#!/usr/bin/env python3
# Accuracy gate: compare a run against a small4 reference over cycle 2 (t in [1, 2]).
#   python3 gate.py <run .out> [--ref <ref .out>] [--window T0 T1] [--tol-l2 2e-4] [--tol-max 2e-3]
# Default reference: cases/small4/reference.out (production model, N_p 40, at dt 1e-4, couplingTol 1e-5, solver tol 1e-4),
# i.e. "did the change move the answer".
# Reads the udf 'vals' and 'wall' lines. Per metric, two tests over the window, both / max |ref|:
#   L2   = sqrt(cycle mean of (run - ref)^2) <= --tol-l2: did the answer move. Robust to coupling-stop jitter,
#          which made the old max-only test a coin toss (production-equivalent runs: L2 1.4-1.6e-4, L-inf 7.5e-4 to 1.03e-3;
#          couplingTol 1e-4: L2 2.3e-4, dt 2e-3: 6.2e-4).
#   Linf = max |run - ref| <= --tol-max: backstop for isolated bad steps, which L2 dilutes.
# Both series are compared on the coarser of the two time grids (np.interp onto those times).
# --per-area A divides the run's wall integrals by A (A = k^2 for a k x k tiled case vs small4; ubar, |V|max are intensive).
# |V|max jumps between nodes, so it is gated on its cycle integral; the pointwise max is printed as info.
# The run must also come from the nekRS commit in NEKRS_VERSION: the SHA in the log header has to match, and a log
# with no SHA fails, because its version can't be confirmed. References are trimmed logs without a header, so only
# the run is checked.
import argparse, os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
p = argparse.ArgumentParser()
p.add_argument('run')
p.add_argument('--ref', default=os.path.join(HERE, 'cases', 'small4', 'reference.out'))  # references for earlier model versions are not shipped
p.add_argument('--window', nargs=2, type=float, default=[1.0, 2.0])
p.add_argument('--tol-l2', type=float, default=2e-4, help='cycle-rms diff / peak')
p.add_argument('--tol-max', type=float, default=2e-3, help='max pointwise diff / peak (backstop)')
p.add_argument('--tol-int', type=float, default=1e-3, help='cycle-integral diff / peak, for |V|max')
p.add_argument('--per-area', type=float, default=1.0, help='divide the run wall integrals by this area ratio')
a = p.parse_args()
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
        if len(v) == 0: sys.exit('%s: no %s lines' % (os.path.basename(f), k))
        _, i = np.unique(v[:, 0], return_index=True)   # drop repeats after a restart
        out[k] = v[np.sort(i)]
    return out

def window(t):
    return (t >= T0 - 1e-9) & (t <= T1 + 1e-9)

def log_shas(f):
    return sorted(set(re.findall(r'\(sha:([0-9a-f]+)\)', open(f, errors='replace').read())))   # a restarted log can hold several

run, ref = read(a.run), read(a.ref)
run['wall'][:, 1:] /= a.per_area
print('gate: %s\n  ref: %s\n  window t in [%g, %g]; of peak: L2 <= %.2g, Linf <= %.2g (|V|max: cycle int <= %.2g)\n'
      % (os.path.basename(a.run), os.path.basename(a.ref), T0, T1, a.tol_l2, a.tol_max, a.tol_int))
want = open(os.path.join(HERE, 'NEKRS_VERSION')).read().split()[1]
shas = log_shas(a.run)
ok = shas == [want]
print('nekRS sha: log %s, NEKRS_VERSION %s  %s\n' % (', '.join(shas) or 'none', want, 'PASS' if ok else 'FAIL'))
print('%-22s %10s %10s %13s %8s' % ('metric', 'L2/peak', 'Linf/peak', 'rel cycle int', 'result'))
for name, tag, c, pointwise in METRICS:
    tr, yr = ref[tag][:, 0], ref[tag][:, c]
    tc, yc = run[tag][:, 0], run[tag][:, c]
    if tc[-1] < T1 - 1e-9 or tc[0] > T0 + 1e-9:
        print('%-22s %10s %10s %13s %8s' % (name, '-', '-', '-', 'FAIL (run ends at t = %g)' % tc[-1])); ok = False; continue
    tw = tr[window(tr)] if np.diff(tr).mean() >= np.diff(tc).mean() else tc[window(tc)]
    r, y = np.interp(tw, tr, yr), np.interp(tw, tc, yc)
    pk = np.abs(r).max()
    d = y - r
    md = np.abs(d).max() / pk
    l2 = np.sqrt(np.trapz(d**2, tw) / (tw[-1] - tw[0])) / pk               # cycle-rms diff / peak
    ri = np.trapz(d, tw) / (pk * (tw[-1] - tw[0]))                          # cycle-mean diff / peak
    if pointwise:
        res = 'PASS' if l2 <= a.tol_l2 and md <= a.tol_max else 'FAIL'
    else:
        res = 'PASS' if abs(ri) <= a.tol_int else 'FAIL'
    ok &= res == 'PASS'
    print('%-22s %10.2e %10.2e %13.2e %8s%s' % (name, l2, md, ri, res, '' if pointwise else '  (gated on cycle int)'))
print('\nGATE %s' % ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
