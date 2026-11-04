# Offline model of the eps error: one FB cilium above a no-slip wall (half space, Blake 1971), RFT panel forces
# f = mu C l (V - u_bg), u_bg = the wall part of the cilium's own flow at the panel (the free-space self-flow is
# subtracted, as subtractSelfFlow = 1), quasi-steady Stokes per snapshot (f = f*, as iqn).
# Regularised: each panel force is spread with the blob phi (only the part in z > 0 acts, as on the mesh) and u is
# sampled at the panel point; the eps -> 0 limit is the point-force Blake image.
# Blobs: gauss  phi = exp(-r^2/eps^2)/(pi^1.5 eps^3) (cilia.udf), u = (1 + eps^2/4 lap) S F + exp. small: an O(eps^2/r^3)
#        potential-dipole error in every far interaction (wall image, neighbours);
#        gauss2 phi = (5/2 - r^2/eps^2) exp(-r^2/eps^2)/(pi^1.5 eps^3) = (1 - eps^2/4 lap) gauss: zero second moment,
#        far-field error exponentially small.
# Metrics over one cycle (H = 1.5 slip top for the pressure weight): Fx mean (wall shear), Fx rms,
# P rms (sum Fz (1 - z/H), the int p proxy), Mx mean (sum Fx z, pumping proxy).
# Run: python3 halfspace_eps_model.py
import contextlib, io, sys
import numpy as np
with contextlib.redirect_stdout(io.StringIO()):
    from kinematics_checks import xi

LR = 20; Cpar = 2 * np.pi / np.log(LR); Cperp = 2 * Cpar; H = 1.5
NT = 40
tt = (np.arange(NT) + 0.5) / NT

def panels(Np, t):
    s = (np.arange(Np) + 0.5) / Np
    x, z = xi(s, t); dx, dz = xi(s, t, True)
    h = 1e-6; a = xi(s, t + h); b = xi(s, t - h)
    vx, vz = (a[0] - b[0]) / (2 * h), (a[1] - b[1]) / (2 * h)
    l = np.hypot(dx, dz) / Np
    P = np.stack([x, 0 * x, z], 1); V = np.stack([vx, 0 * vx, vz], 1); T = np.stack([dx, 0 * dx, dz], 1) / (l * Np)[:, None]
    return P, V, T, l

def stokeslet(R):  # (..., 3) -> (..., 3, 3), 8 pi mu u = S F
    r = np.linalg.norm(R, axis=-1)[..., None, None]
    return np.eye(3) / r + R[..., :, None] * R[..., None, :] / r**3

def blake_image(x, y):  # wall part of the Blake tensor, source y (y3 > 0), field x: 8 pi mu u = I F
    X = x - y * np.array([1, 1, -1]); h = y[..., 2][..., None, None]
    R = np.linalg.norm(X, axis=-1)[..., None, None]
    Xi = X[..., :, None]; Xk = X[..., None, :]; X3 = X[..., 2][..., None, None]
    d = np.eye(3); e3i = d[:, 2][:, None]; e3k = d[2][None, :]
    D = h * (d / R**3 - 3 * Xi * Xk / R**5) + e3i * Xk / R**3 - (d * X3 + Xi * e3k) / R**3 + 3 * Xi * X3 * Xk / R**5
    M = np.array([1.0, 1.0, -1.0])
    return -(d / R + Xi * Xk / R**3) + 2 * h * D * M[None, :]

# quadrature over the blob: Gauss-Hermite in x, y; Gauss-Legendre over z in [max(0, zj - 5 eps), zj + 5 eps] (fluid)
# plus the part below the wall (lost force: its free-space flow is subtracted from the full-blob self-flow)
gh_t, gh_w = np.polynomial.hermite.hermgauss(10); gh_w = gh_w / np.sqrt(np.pi)
gl_t, gl_w = np.polynomial.legendre.leggauss(24)

def K_reg(P, eps, blob):
    """8 pi mu K[i, j]: velocity at panel i (wall part + lost-blob correction) per unit force of panel j."""
    Np = len(P); K = np.zeros((Np, Np, 3, 3))
    for j in range(Np):
        zj = P[j, 2]
        parts = []
        lo, hi = max(0.0, zj - 5 * eps), zj + 5 * eps
        zq = 0.5 * (hi - lo) * gl_t + 0.5 * (hi + lo); wz = 0.5 * (hi - lo) * gl_w * np.exp(-((zq - zj) / eps)**2) / (np.sqrt(np.pi) * eps)
        parts.append((zq, wz, +1))
        if zj - 5 * eps < 0:   # blob part below the wall: lost on the mesh
            lo2, hi2 = zj - 5 * eps, 0.0
            zq2 = 0.5 * (hi2 - lo2) * gl_t + 0.5 * (hi2 + lo2); wz2 = 0.5 * (hi2 - lo2) * gl_w * np.exp(-((zq2 - zj) / eps)**2) / (np.sqrt(np.pi) * eps)
            parts.append((zq2, wz2, -1))
        for zq, wz, sgn in parts:
            ax, ay, az = np.meshgrid(gh_t, gh_t, zq, indexing='ij')
            W = (gh_w[:, None, None] * gh_w[None, :, None] * wz[None, None, :])
            Y = np.stack([P[j, 0] + eps * ax, P[j, 1] + eps * ay, az], -1).reshape(-1, 3)
            W = W.reshape(-1)
            if blob == 'gauss2':
                rr = (eps * ax)**2 + (eps * ay)**2 + (az - zj)**2
                W = W * (2.5 - rr.reshape(-1) / eps**2)
            if sgn > 0:
                G = blake_image(P[:, None, :], Y[None, :, :])
            else:
                G = -stokeslet(P[:, None, :] - Y[None, :, :])
            K[:, j] += np.einsum('q,iqab->iab', W, G)
    return K

def K_sing(P):
    return blake_image(P[:, None, :], P[None, :, :])

def solve(P, V, T, l, K):
    Np = len(P)
    C = l[:, None, None] * (Cperp * np.eye(3) + (Cpar - Cperp) * T[:, :, None] * T[:, None, :])
    A = np.eye(3 * Np).reshape(Np, 3, Np, 3).copy()
    A += np.einsum('iab,ijbc->iajc', C, K / (8 * np.pi))
    f = np.linalg.solve(A.reshape(3 * Np, 3 * Np), np.einsum('iab,ib->ia', C, V).reshape(-1)).reshape(Np, 3)
    return f

def cycle(Np, eps, blob):
    out = []
    for t in tt:
        P, V, T, l = panels(Np, t)
        K = K_sing(P) if blob == 'sing' else K_reg(P, eps, blob)
        f = solve(P, V, T, l, K)
        out.append((f[:, 0].sum(), (f[:, 2] * (1 - P[:, 2] / H)).sum(), (f[:, 0] * P[:, 2]).sum(), f, P))
    Fx = np.array([o[0] for o in out]); Pz = np.array([o[1] for o in out]); Mx = np.array([o[2] for o in out])
    return dict(Fx=Fx.mean(), Fxr=Fx.std(), Pr=Pz.std(), Mx=Mx.mean(), raw=out)

if __name__ == "__main__":
    ref = cycle(320, 0, 'sing')
    ref2 = cycle(160, 0, 'sing')
    keys = ('Fx', 'Fxr', 'Pr', 'Mx')
    print("eps -> 0 (point Blake image), Np 320: " + "  ".join("%s %.5f" % (k, ref[k]) for k in keys))
    print("                              Np 160: " + "  ".join("%s %+.3f%%" % (k, 100 * (ref2[k] / ref[k] - 1)) for k in keys))
    print("%-7s %6s %4s " % ("blob", "eps", "Np") + " ".join("%9s" % k for k in keys) + "   (% vs the eps -> 0 limit)")
    for blob in ('gauss', 'gauss2'):
        for eps in (0.1, 0.0707, 0.05, 0.0354):
            Np = int(round(2 / eps))
            r = cycle(Np, eps, blob)
            print("%-7s %6.4f %4d " % (blob, eps, Np) + " ".join("%+8.2f%%" % (100 * (r[k] / ref[k] - 1)) for k in keys))
            sys.stdout.flush()
