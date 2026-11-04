#!/usr/bin/env python3
# gate.py's metric (max |run - ref| / max |ref| over t in [1, 2], pointwise; |V|max on its cycle integral)
# for many pairs at once, one row per pair.
#   python3 gate_metric_compare.py <label>=<run .out>:<ref .out> ...
# Needs your own run logs: this repo ships none besides cases/small4/reference.out.
import sys
import numpy as np

trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz   # np.trapz is gone from NumPy 2.0

COLS = [('ubar', 'vals', 1, True), ('Vmax', 'vals', 2, False), ('p.001', 'wall', 3, True), ('dudz.001', 'wall', 4, True),
        ('u.001', 'wall', 1, True), ('dvdz.001', 'wall', 5, True), ('p0', 'wall', 6, True), ('dudz0', 'wall', 7, True),
        ('dvdz0', 'wall', 8, True)]


def read(f):
    d = {'vals': [], 'wall': []}
    for line in open(f, errors='replace'):
        s = line.split()
        if s and s[-1] in d:
            try: d[s[-1]].append([float(x) for x in s[:-1]])
            except ValueError: pass
    out = {}
    for k, v in d.items():
        v = np.array(v)
        _, i = np.unique(v[:, 0], return_index=True)
        out[k] = v[np.sort(i)]
    return out


def compare(run, ref, T0=1.0, T1=2.0):
    res = {}
    for name, tag, c, pointwise in COLS:
        tr, yr = ref[tag][:, 0], ref[tag][:, c]
        tc, yc = run[tag][:, 0], run[tag][:, c]
        if tc[-1] < T1 - 1e-9:
            res[name] = np.nan; continue
        tw = tr[(tr >= T0 - 1e-9) & (tr <= T1 + 1e-9)]
        r, y = yr[(tr >= T0 - 1e-9) & (tr <= T1 + 1e-9)], np.interp(tw, tc, yc)
        pk = np.abs(r).max()
        res[name] = np.abs(y - r).max() / pk if pointwise else abs(trapz(y - r, tw)) / (pk * (tw[-1] - tw[0]))
    return res


if __name__ == '__main__':
    cache = {}
    get = lambda f: cache.setdefault(f, read(f))
    print('%-16s' % 'pair' + ''.join('%10s' % n for n, *_ in COLS) + '%10s' % 'worst')
    for a in sys.argv[1:]:
        lab, files = a.split('=', 1)
        run, ref = files.split(':')
        r = compare(get(run), get(ref))
        print('%-16s' % lab + ''.join('%10.2e' % r[n] for n, *_ in COLS) + '%10.2e' % np.nanmax(list(r.values())))
