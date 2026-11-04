#!/usr/bin/env python3
# Cycle-2 (t in [1, 2]) mean, rms and peak of ubar, int p, int du/dz (z = 0) per run, from the udf 'vals'/'wall' lines.
#   python3 cycle_metrics.py label=<run .out> ...   (first run = the comparison baseline)
import sys
import numpy as np

def read(f):
    d = {'vals': [], 'wall': []}
    for l in open(f, errors='replace'):
        s = l.split()
        if s and s[-1] in d:
            try: d[s[-1]].append([float(x) for x in s[:-1]])
            except ValueError: pass
    return {k: np.array(v) for k, v in d.items()}

COLS = [('ubar', 'vals', 1), ('int p', 'wall', 6), ('int du/dz', 'wall', 7)]
rows = []
for arg in sys.argv[1:]:
    lab, f = arg.split('=', 1)
    d = read(f); r = {}
    for name, tag, c in COLS:
        a = d[tag]; m = (a[:, 0] >= 1.0) & (a[:, 0] <= 2.0); t, y = a[m, 0], a[m, c]
        mean = np.trapz(y, t) / (t[-1] - t[0])
        r[name] = (mean, np.sqrt(np.trapz((y - mean)**2, t) / (t[-1] - t[0])), np.abs(y).max())
    rows.append((lab, r))
base = rows[0][1]
print(f"{'run':10s}" + ''.join(f"{n+' mean':>16s}{'rms':>10s}{'peak':>10s}" for n, _, _ in COLS))
for lab, r in rows:
    print(f"{lab:10s}" + ''.join(f"{r[n][0]:16.4g}{r[n][1]:10.4g}{r[n][2]:10.4g}" for n, _, _ in COLS))
print('relative to', rows[0][0])
for lab, r in rows[1:]:
    print(f"{lab:10s}" + ''.join(f"{r[n][0]/base[n][0]-1:+16.1%}{r[n][1]/base[n][1]-1:+10.1%}{r[n][2]/base[n][2]-1:+10.1%}" for n, _, _ in COLS))
