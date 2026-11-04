# Closed form of the Gaussian-regularised Stokeslet used by cilia.udf (subtractSelfFlow), checked
# against the Fourier integral T() of self_interaction.py. Run: python3 stokeslet_closed_form.py
# Blob phi = exp(-r^2/eps^2)/(pi^1.5 eps^3). u = (1/mu)[a F + b (F.rhat) rhat] with G = erf(r/eps)/(4 pi r),
# B'(r) = [(r^2/2 - eps^2/4) erf(r/eps) + eps r e^(-r^2/eps^2)/(2 sqrt(pi))]/(4 pi r^2), a = G - B'/r, b = 3B'/r - G.
import numpy as np
from math import erf, exp, pi, sqrt
from self_interaction import T

def closed(r, eps):
    if r < 1e-3 * eps: return 1/(3*pi**1.5*eps), 0.0
    G = erf(r/eps)/(4*pi*r)
    Bp = ((r*r/2 - eps*eps/4)*erf(r/eps) + eps*r*exp(-r*r/eps**2)/(2*sqrt(pi)))/(4*pi*r*r)
    return G - Bp/r, 3*Bp/r - G

worst = 0
for eps in (0.1, 0.05):
    for r in (0, 1e-4, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0):
        a, b = closed(r, eps); a2, b2 = T(r, eps)
        worst = max(worst, abs(a-a2)/abs(a2), abs(b-b2)/max(abs(a2), 1e-30))
        print("eps %.2f r %.4f  a %.6f (quad %.6f)  b %.6f (quad %.6f)" % (eps, r, a, a2, b, b2))
print("worst relative difference %.1e" % worst)
