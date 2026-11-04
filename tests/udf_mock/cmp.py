#!/usr/bin/env python3
# Compares two F.bin files from driver_dist.cpp; exits 1 if the largest relative difference is above the threshold.
#   python3 cmp.py a.bin b.bin [3N_part = 540] [threshold = 1e-12]
# NaN fails, and so do files of different lengths.
import numpy as np, sys
n = int(sys.argv[3]) if len(sys.argv) > 3 else 540   # unknowns per step: 3 N_part
tol = float(sys.argv[4]) if len(sys.argv) > 4 else 1e-12
a=np.fromfile(sys.argv[1]).reshape(-1,n); b=np.fromfile(sys.argv[2]).reshape(-1,n)
if a.shape != b.shape: sys.exit("different lengths: %d and %d steps" % (len(a), len(b)))
d=np.abs(a-b).max(1)/np.abs(a).max(1).clip(1e-300)
print("max rel F diff over steps %.2e (step %d), last step %.2e, |F| last %.3e" % (d.max(), d.argmax()+1, d[-1], np.abs(a[-1]).max()))
if not d.max() <= tol: sys.exit("above the threshold %.0e" % tol)   # written this way round so NaN fails
