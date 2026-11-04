# Offline check: does the panel length / tangent choice change the u = 0 RFT force of one cilium?
# FB beat (L = 1, period 1), RFT with C_par = 1, C_perp = 2 (only the ratio and l matter).
# Metrics over one cycle: net x force Fx (wall shear), net z force Fz, and Mx = sum Fx z (pumping proxy:
# with a no-slip floor and a slip top, a plane force at height z drives a far-field flow proportional to F z).
# Run: python3 panel_length_check.py
import numpy as np
import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):  # kinematics_checks prints its own checks on import
    from kinematics_checks import xi
Np = 20
t = np.linspace(0, 1, 2001)[:-1]
def vel(s):  # dxi/dt by central differences in t (periodic, smooth)
    h = 1e-6; a = xi(s, t[:, None] + h); b = xi(s, t[:, None] - h)
    return (a[0] - b[0]) / (2 * h), (a[1] - b[1]) / (2 * h)
def rft(tx, tz, vx, vz, l, z):
    n = np.hypot(tx, tz); tx = tx / n; tz = tz / n
    vt = vx * tx + vz * tz
    fx = l * (vt * tx + 2 * (vx - vt * tx)); fz = l * (vt * tz + 2 * (vz - vt * tz))
    return fx.sum(1), fz.sum(1), (fx * z).sum(1)
def analytic(s, l):
    S = np.broadcast_to(s, (len(t), s.shape[-1])) if s.ndim == 1 else s
    x, z = xi(S, t[:, None]); dx, dz = xi(S, t[:, None], True); vx, vz = vel(S)
    return rft(dx, dz, vx, vz, l, z)
# arclength map s(sigma) per time (sigma = true arclength fraction)
sf = np.linspace(0, 1, 4001)
d1, d2 = xi(sf[None, :], t[:, None], True); st = np.hypot(d1, d2)
arc = np.concatenate([np.zeros((len(t), 1)), np.cumsum(0.5 * (st[:, 1:] + st[:, :-1]) * np.diff(sf), 1)], 1)
Ltrue = arc[:, -1]
sp = (np.arange(Np) + 0.5) / Np
res = {}
# A: current udf: uniform s, l = 1/N, FD tangent on the panel centres (centred inside, one-sided at ends)
x, z = xi(sp[None, :], t[:, None]); vx, vz = vel(sp[None, :])
im = np.r_[0, np.arange(Np - 1)]; ip = np.r_[np.arange(1, Np), Np - 1]
res['A current (l=L/N, FD tangent)'] = rft(x[:, ip] - x[:, im], z[:, ip] - z[:, im], vx, vz, 1 / Np, z)
# B: analytic tangent only
res['B analytic tangent, l=L/N'] = analytic(sp, 1 / Np)
# C: true local length l_i = |xi_s(s_i)| / N (midpoint rule of the line integral), analytic tangent
d1, d2 = xi(sp[None, :], t[:, None], True)
res['C l=|dx/ds|/N, analytic tangent'] = analytic(sp, np.hypot(d1, d2) / Np)
# D: panels at equal true arclength, l = L(t)/N
sig = np.array([np.interp((np.arange(Np) + 0.5) / Np * Ltrue[k], arc[k], sf) for k in range(len(t))])
res['D equal true arclength, l=L(t)/N'] = analytic(sig, Ltrue[:, None] / Np)
# E: D rescaled to length L (treat the fit's stretch as error: same shape, force per unit length x L/L(t))
res['E = D x L/L(t) (inextensible norm.)'] = tuple(r / Ltrue for r in res['D equal true arclength, l=L(t)/N'])
# truth: fine quadrature of the line integral over the actual curve
sfine = (np.arange(2000) + 0.5) / 2000; d1, d2 = xi(sfine[None, :], t[:, None], True)
ref = analytic(sfine, np.hypot(d1, d2) / 2000)
print("FB length L(t)/L: min %.3f max %.3f mean %.3f" % (Ltrue.min(), Ltrue.max(), Ltrue.mean()))
print("%-38s %9s %9s %9s %9s %9s" % ("variant", "Fx mean", "Fx rms", "Fz rms", "Mx mean", "Mx rms"))
def row(name, r):
    fx, fz, mx = r
    print("%-38s %9.4f %9.4f %9.4f %9.4f %9.4f" % (name, fx.mean(), fx.std(), fz.std(), mx.mean(), mx.std()))
row('line integral (truth, N=2000)', ref)
for k, r in res.items(): row(k, r)
print("relative to truth (%):  Fx mean, Fx rms, Fz rms, Mx mean, Mx rms ; max |dFx(t)|/Fx rms")
for k, r in res.items():
    rel = [100 * (r[0].mean() / ref[0].mean() - 1), 100 * (r[0].std() / ref[0].std() - 1), 100 * (r[1].std() / ref[1].std() - 1),
           100 * (r[2].mean() / ref[2].mean() - 1), 100 * (r[2].std() / ref[2].std() - 1), 100 * abs(r[0] - ref[0]).max() / ref[0].std()]
    print("%-38s" % k + " ".join("%8.2f" % v for v in rel))
