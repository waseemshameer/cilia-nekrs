#!/usr/bin/env python3
"""Shape of the growing mode of f = f* from the 'panel' lines (dumpPanelSteps > 0 in [CASEDATA]).

Usage: panel_mode_shape.py <run .out> [more .out]
Needs your own run logs: this repo ships none besides cases/small4/reference.out.

Per call of userForcing it prints
  growth  rms(fa)_n / rms(fa)_{n-1} (fa = applied force sum_h c_h f_h, the force of the next solve)
  unif    |panel mean of fa|^2 / mean |fa|^2: 1 = every panel of every cilium pushes the same way (box-scale mode)
  zig     sum (fa_i - fa_{i+1})^2 / (2 sum fa_i^2) along each cilium: ~0 smooth, 1 uncorrelated, 2 panel-to-panel zigzag
  u_raw, u_self  panel means of x velocity (raw sampled u and the subtracted self-flow)
  gain    -<u_raw - u_raw_prev> / <fa_prev - fa_prevprev> * C mu l, the loop gain of the mean mode (x)
"""
import sys
import numpy as np


def load(path):
    rows, cext = {}, {}
    mu = None
    C_par = C_perp = l = None
    for line in open(path):
        w = line.split()
        if not w:
            continue
        if w[0] == 'panel':
            rows.setdefault(int(w[1]), []).append([float(v) for v in w[2:]])
        elif w[0] == 'panel_cext':
            cext[int(w[1])] = [float(v) for v in w[2:]]
        elif line.startswith('cilia: N_p'):
            t =line.replace('=', ' ').split()
            l = float(t[t.index('l') + 1]); C_par = float(t[t.index('C_par') + 1])
            C_perp = float(t[t.index('C_perp') + 1]); mu = float(t[t.index('mu') + 1])
    calls = sorted(rows)
    A = np.array([rows[c] for c in calls])   # call, panel, column
    return calls, A, cext, (mu, C_par, C_perp, l)


def report(path):
    calls, A, cext, (mu, C_par, C_perp, l) = load(path)
    t, k, i = A[:, :, 0], A[:, :, 1].astype(int), A[:, :, 2].astype(int)
    fs, fa, ur, us, V = A[:, :, 3:6], A[:, :, 6:9], A[:, :, 9:12], A[:, :, 12:15], A[:, :, 15:18]
    Np = i.max() + 1
    Nc = k.max() + 1
    print(f'== {path}: {len(calls)} calls, {Nc} cilia x {Np} panels, mu {mu}, C_perp mu l {C_perp*mu*l:.4g}')
    print(' call     time   cext          rms(fa)  growth  unif   zig   <fa_x>      <u_raw_x>   <u_self_x>  gain_x')
    prev = None
    for n, c in enumerate(calls):
        f = fa[n]
        rms = np.sqrt((f**2).sum(1).mean())
        unif = (f.mean(0)**2).sum() / max((f**2).sum(1).mean(), 1e-300)
        fc = f.reshape(Nc, Np, 3)
        zig = ((fc[:, 1:] - fc[:, :-1])**2).sum() / max(2 * (fc**2).sum(), 1e-300)
        g = ''
        if n >= 2:
            dfa = fa[n - 1, :, 0].mean() - fa[n - 2, :, 0].mean()
            dur = ur[n, :, 0].mean() - ur[n - 1, :, 0].mean()
            if abs(dfa) > 0:
                g = f'{-dur / dfa * C_perp * mu * l:8.3f}'
        gr = f'{rms / prev:7.3f}' if prev else '      -'
        ce = ' '.join(f'{v:g}' for v in cext.get(c, []))
        print(f'{c:5d} {t[n,0]:.5f}  {ce:12s} {rms:10.3e} {gr} {unif:6.3f} {zig:5.3f} {f[:,0].mean():11.3e} '
              f'{ur[n,:,0].mean():11.3e} {us[n,:,0].mean():11.3e} {g}')
        prev = rms if rms > 0 else None
    # shape of the last call's mode along each cilium (x, normalised by the overall rms)
    n = len(calls) - 1
    f = fa[n].reshape(Nc, Np, 3)
    s = np.sqrt((f**2).sum(2).mean())
    print(f' last call: fa_x / rms along each cilium (rows = cilia, columns = panels 0..{Np-1})')
    for kk in range(Nc):
        print('  ' + ' '.join(f'{v:5.2f}' for v in f[kk, :, 0] / s))
    print(' last call: fa_z / rms')
    for kk in range(Nc):
        print('  ' + ' '.join(f'{v:5.2f}' for v in f[kk, :, 2] / s))


if __name__ == '__main__':
    for p in sys.argv[1:]:
        report(p)
