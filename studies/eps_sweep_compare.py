#!/usr/bin/env python3
# Cycle-2 metrics (t in [1, 2]) of eps-sweep runs from their 'vals'/'wall' lines, relative to a baseline run.
#   python3 eps_sweep_compare.py base=<run .out> label=<run .out> ...
# ubar mean, int p rms (z = 0), int du/dz mean (z = 0: the mean net x force in Stokes), int du/dz rms.
# Means use the samples' trapezoid in time (runs at equal dt only).
import sys
import numpy as np

def load(f):
    v, w = [], []
    for line in open(f):
        s = line.split()
        if len(s) == 4 and s[-1] == 'vals': v.append([float(x) for x in s[:3]])
        elif len(s) == 10 and s[-1] == 'wall': w.append([float(x) for x in s[:9]])
    v, w = np.array(v), np.array(w)
    v = v[(v[:, 0] >= 1 - 1e-9) & (v[:, 0] <= 2 + 1e-9)]; w = w[(w[:, 0] >= 1 - 1e-9) & (w[:, 0] <= 2 + 1e-9)]
    mean = lambda t, y: np.trapz(y, t) / (t[-1] - t[0])
    rms = lambda t, y: np.sqrt(mean(t, (y - mean(t, y))**2))
    return dict(ubar=mean(v[:, 0], v[:, 1]), prms=rms(w[:, 0], w[:, 6]), tx=mean(w[:, 0], w[:, 7]), txrms=rms(w[:, 0], w[:, 7]),
                tend=v[-1, 0])

if __name__ == '__main__':
    runs = [(a.split('=', 1)[0], load(a.split('=', 1)[1])) for a in sys.argv[1:]]
    b = runs[0][1]
    keys = ['ubar', 'prms', 'tx', 'txrms']
    print('%-14s' % 'run' + ''.join('%12s' % k for k in keys) + '   t_end')
    for lab, r in runs:
        if r is b: print('%-14s' % lab + ''.join('%12.5g' % r[k] for k in keys) + '   %.3f' % r['tend'])
        else: print('%-14s' % lab + ''.join('%+11.2f%%' % (100 * (r[k] / b[k] - 1)) for k in keys) + '   %.3f' % r['tend'])
