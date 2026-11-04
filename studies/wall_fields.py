#!/usr/bin/env python3
# Local wall statistics from nekRS checkpoints (Nek5000 fld format), which the plane-integral 'wall' line can't see
# (in Stokes with periodic sides those integrals are set by the total panel forces alone).
#   python3 wall_fields.py extract <run dir> <out.npz> [tmin tmax]   (python 3.6 / numpy 1.19 ok)
#   python3 wall_fields.py compare label=<npz> ...                    (first = the comparison baseline)
# Needs checkpoints from your own runs: this repo ships none.
# Per frame on the wall z = 0: tau_x = du/dz, tau_y = dv/dz (spectral derivative in the bottom element layer) and p:
# plane mean, spatial rms of the deviation from it, max |deviation|, |tau| max, and Fourier modes |kx|, |ky| <= K
# (box 1 x 1, units of 2 pi). Also the spatial rms of the time-mean field over the frames.
import glob
import os
import sys
import numpy as np

K = 4


def read_fld(fn):
    with open(fn, 'rb') as f:
        hdr = f.read(132).decode('ascii', 'replace')
        tok = hdr.split()
        wd, nx, ny, nz, nelt = int(tok[1]), int(tok[2]), int(tok[3]), int(tok[4]), int(tok[5])
        time = float(tok[7])
        var = ''.join(tok[11:])
        tag = np.frombuffer(f.read(4), '<f4')[0]
        end = '<' if abs(tag - 6.54321) < 1e-4 else '>'
        ids = np.frombuffer(f.read(4 * nelt), end + 'i4')
        dt = np.dtype(end + ('f4' if wd == 4 else 'f8'))
        npts = nx * ny * nz
        out = {'time': time, 'ids': ids, 'n': (nx, ny, nz)}

        def rd(ncomp):
            a = np.frombuffer(f.read(dt.itemsize * nelt * ncomp * npts), dt).astype(np.float64)
            return a.reshape(nelt, ncomp, nz, ny, nx)
        if 'X' in var: out['X'] = rd(3)
        if 'U' in var: out['U'] = rd(3)
        if 'P' in var: out['P'] = rd(1)[:, 0]
    return out


def gll(N):
    from numpy.polynomial import legendre as L
    c = np.zeros(N + 1); c[N] = 1
    x = np.concatenate(([-1.0], np.sort(np.real(L.legroots(L.legder(c)))), [1.0]))
    PN = L.legval(x, c)
    w = 2.0 / (N * (N + 1) * PN**2)
    D = np.zeros((N + 1, N + 1))
    for i in range(N + 1):
        for j in range(N + 1):
            if i != j: D[i, j] = PN[i] / (PN[j] * (x[i] - x[j]))
    D[0, 0] = -N * (N + 1) / 4.0; D[N, N] = N * (N + 1) / 4.0
    return x, w, D


def extract(rundir, out, tmin=1.0, tmax=2.0):
    files = sorted(f for f in glob.glob(os.path.join(rundir, '*0.f[0-9]*')) if not f.endswith('.nek5000'))
    X = None
    for fn in files:
        d = read_fld(fn)
        if 'X' in d: X, ids = d['X'], d['ids']; break
    nx, ny, nz = d['n']
    x, w, D = gll(nx - 1)
    zmin = X[:, 2].min(axis=(1, 2, 3))
    bot = np.where(np.abs(zmin) < 1e-9)[0]
    Xb = X[bot]
    hx = Xb[:, 0, 0, 0, -1] - Xb[:, 0, 0, 0, 0]
    hy = Xb[:, 1, 0, -1, 0] - Xb[:, 1, 0, 0, 0]
    hz = Xb[:, 2, -1, 0, 0] - Xb[:, 2, 0, 0, 0]
    W = np.einsum('e,j,i->eji', hx * hy / 4.0, w, w)
    A = W.sum()
    xw, yw = Xb[:, 0, 0], Xb[:, 1, 0]
    ks = [(kx, ky) for kx in range(-K, K + 1) for ky in range(-K, K + 1) if (kx, ky) != (0, 0)]
    E = np.array([np.exp(-2j * np.pi * (kx * xw + ky * yw)) for kx, ky in ks])
    times, stats, modes = [], [], []
    acc, nacc = 0.0, 0
    for fn in files:
        d = read_fld(fn)
        t = d['time']
        if not (tmin + 1e-6 < t < tmax + 1e-6) or 'U' not in d: continue
        assert np.array_equal(d['ids'], ids)
        U = d['U'][bot]
        tx = np.einsum('k,ekji->eji', D[0], U[:, 0]) * (2.0 / hz)[:, None, None]
        ty = np.einsum('k,ekji->eji', D[0], U[:, 1]) * (2.0 / hz)[:, None, None]
        p = d['P'][bot][:, 0]
        row, mrow = [], []
        for q in (tx, ty, p):
            m = (W * q).sum() / A
            dq = q - m
            row += [m, np.sqrt((W * dq**2).sum() / A), np.abs(dq).max()]
            mrow.append(np.einsum('keji,eji->k', E, W * q) / A)
        row.append(np.sqrt(tx**2 + ty**2).max())
        times.append(t); stats.append(row); modes.append(mrow)
        acc = acc + np.stack([tx, ty, p]); nacc += 1
    tm = acc / nacc
    tmrms = [np.sqrt((W * (q - (W * q).sum() / A)**2).sum() / A) for q in tm]
    np.savez(out, times=np.array(times), stats=np.array(stats), modes=np.array(modes), ks=np.array(ks),
             tmean_rms=np.array(tmrms), area=A, nbot=len(bot))
    print('%s: %d frames t %.3f..%.3f, %d wall elements, area %.6f' % (out, len(times), times[0], times[-1], len(bot), A))


NAMES = ['tx mean', 'tx rms', 'tx max', 'ty mean', 'ty rms', 'ty max', 'p mean', 'p rms', 'p max', '|tau| max']


def compare(args):
    runs = []
    for a in args:
        lab, f = a.split('=', 1)
        runs.append((lab, np.load(f)))
    base = runs[0][1]
    hdr = '%-12s' % 'run' + ''.join('%11s' % n for n in ['tx rms', 'ty rms', 'p rms', 'tx max', 'p max', '|tau|max', 'tm tx rms', 'tm p rms', 'tx k<=2', 'p k<=2'])
    print('cycle space-time rms of the deviation from the plane mean, max over frames; tm = time-mean field; k<=2: rel. L2 diff of the modes |k|<=2 vs the first run')
    print(hdr)
    for lab, r in runs:
        s = r['stats']
        assert np.allclose(r['times'], base['times']), lab
        rms = lambda c: np.sqrt(np.mean(s[:, c]**2))
        ks = r['ks']; sel = np.max(np.abs(ks), axis=1) <= 2
        md = []
        for c in (0, 2):
            mb, mr = base['modes'][:, c][:, sel], r['modes'][:, c][:, sel]
            md.append(np.sqrt(np.sum(np.abs(mr - mb)**2) / np.sum(np.abs(mb)**2)))
        vals = [rms(1), rms(4), rms(7), s[:, 2].max(), s[:, 8].max(), s[:, 9].max(), r['tmean_rms'][0], r['tmean_rms'][2], md[0], md[1]]
        print('%-12s' % lab + ''.join('%11.4g' % v for v in vals))


if __name__ == '__main__':
    if sys.argv[1] == 'extract':
        extract(sys.argv[2], sys.argv[3], *[float(v) for v in sys.argv[4:6]])
    else:
        compare(sys.argv[2:])
