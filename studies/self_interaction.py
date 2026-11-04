# Free-space estimate of the self-interaction in the actuator model. Run: python3 self_interaction.py
# Free-space self-interaction of a straight rod of Np Gaussian blobs (no wall): velocity at panel
# centres induced by the panels' own spread force, then the RFT force that solves F = mu C l (V - u(F)).
import numpy as np
from scipy.integrate import quad
from scipy.special import spherical_jn as jn
def T(r,eps):  # u = (F/mu)(a I + b rhat rhat)
    g=lambda k: np.exp(-k*k*eps*eps/4)
    if r==0: return 1/(3*np.pi**1.5*eps),0.0
    a=quad(lambda k: g(k)*(jn(0,k*r)-jn(1,k*r)/(k*r)),0,60/eps,limit=2000)[0]/(2*np.pi**2)
    b=quad(lambda k: g(k)*jn(2,k*r),0,60/eps,limit=2000)[0]/(2*np.pi**2)
    return a,b
if __name__ == "__main__":
  LR=20; Cpar=2*np.pi/np.log(LR); Cperp=2*Cpar
  for eps in (0.2,0.1,0.05,0.025):
    for Np in (20,):
      l=1/Np; z=(np.arange(Np)+0.5)*l
      M_perp=np.zeros((Np,Np)); M_par=np.zeros((Np,Np))
      for i in range(Np):
          for j in range(Np):
              a,b=T(abs(z[i]-z[j]),eps); M_perp[i,j]=a; M_par[i,j]=a+b
      # F = C l (V - M F)  (mu cancels)  ->  (I + C l M) F = C l V
      for name,C,M in (("perp",Cperp,M_perp),("par",Cpar,M_par)):
          F=np.linalg.solve(np.eye(Np)+C*l*M, C*l*np.ones(Np))
          print("eps %.3f Np %d %s: total drag / RFT = %.3f  (mid-panel u_self/V = %.2f)"%(eps,Np,name,F.sum()/C,(M@F)[Np//2]))
