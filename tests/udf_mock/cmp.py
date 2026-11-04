import numpy as np, sys
n = int(sys.argv[3]) if len(sys.argv) > 3 else 540   # unknowns per step: 3 N_part
a=np.fromfile(sys.argv[1]).reshape(-1,n); b=np.fromfile(sys.argv[2]).reshape(-1,n)
d=np.abs(a-b).max(1)/np.abs(a).max(1).clip(1e-300)
print("max rel F diff over steps %.2e (step %d), last step %.2e, |F| last %.3e" % (d.max(), d.argmax()+1, d[-1], np.abs(a[-1]).max()))
