#!/usr/bin/env python3
# Closest approach between cilium centre lines over the FB beat (all cilia in phase, as in cilia.udf), periodic box,
# all pairs incl. each cilium's own periodic images. Coordinates file as the udf reads it: x_root y_root beta [rad].
#   python3 cilia_distances.py <coordinates.txt> [box_x [box_y]]     (default box 1 x 1, as small4)
import io
import contextlib
import sys
import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
with contextlib.redirect_stdout(io.StringIO()):
    import kinematics_checks as k

C = np.atleast_2d(np.loadtxt(sys.argv[1]))[:, :3]
bx = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
by = float(sys.argv[3]) if len(sys.argv) > 3 else bx
t = np.linspace(0, 1, 201); s = np.linspace(0, 1, 101)
x1, x2 = k.xi(s[None, :], t[:, None])
P = np.stack([x1[None] * np.cos(C[:, 2])[:, None, None] + C[:, 0][:, None, None],
              x1[None] * np.sin(C[:, 2])[:, None, None] + C[:, 1][:, None, None],
              np.broadcast_to(x2, (len(C),) + x2.shape)], -1)    # (cilium, t, s, xyz)
rows = []
for a in range(len(C)):
    for b in range(a, len(C)):
        for ix in (-1, 0, 1):
            for iy in (-1, 0, 1):
                if a == b and ix == 0 and iy == 0: continue
                d = P[a][:, :, None, :] - (P[b][:, None, :, :] + np.array([ix * bx, iy * by, 0.0]))
                r = np.sqrt((d**2).sum(-1)).min(axis=(1, 2))
                rows.append((r.min(), a, b, ix, iy, t[r.argmin()], (r < 0.1).mean(), (r < 0.05).mean()))
rows.sort()
print('closest approaches (centre lines, units of L), beat sampled at %d phases:' % len(t))
for r in rows[:8]:
    print('  %.4f  cilia %d-%d image (%d,%d)  at t = %.3f   share of beat < 0.1: %.2f  < 0.05: %.2f' % r)
