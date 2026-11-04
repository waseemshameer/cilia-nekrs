# Offline checks of the cilia model (no nekRS): Fulford-Blake length, panel heights, Gaussian
# truncation and wall loss, relaxation filter. Run: python3 kinematics_checks.py
import numpy as np
from scipy.special import erf, erfc
A1=np.array([-0.449,-0.072,0.658, 0.130,-1.502,0.793, -0.169,0.260,-0.251, 0.063,-0.123,0.049, -0.050,0.011,0.009, -0.040,-0.009,0.023, -0.068,0.196,-0.111]).reshape(7,3)
A2=np.array([2.076,-1.074,0.381, -0.003,-0.230,0.331, 0.054,-0.305,0.193, 0.007,-0.180,0.082, 0.026,-0.069,0.029, 0.022,0.001,0.002, 0.010,-0.080,0.048]).reshape(7,3)
B1=np.array([-0.030,1.285,-1.034, -0.093,-0.036,0.050, 0.037,-0.244,0.143, 0.062,-0.093,0.043, 0.016,-0.137,0.098, -0.065,0.095,-0.054]).reshape(6,3)
B2=np.array([0.080,-0.298,0.210, -0.044,0.513,-0.367, -0.017,0.004,0.009, 0.052,-0.222,0.120, 0.007,0.035,-0.024, 0.051,-0.128,0.102]).reshape(6,3)
def poly(C,s): return C[...,0]*s+C[...,1]*s**2+C[...,2]*s**3
def dpoly(C,s): return C[...,0]+2*C[...,1]*s+3*C[...,2]*s**2
def xi(s,t,d=False):
    P=dpoly if d else poly
    w=2*np.pi
    x1=0.5*P(A1[0],s); x2=0.5*P(A2[0],s)
    for n in range(1,7):
        c,sn=np.cos(n*w*t),np.sin(n*w*t)
        x1=x1+P(A1[n],s)*c+P(B1[n-1],s)*sn
        x2=x2+P(A2[n],s)*c+P(B2[n-1],s)*sn
    return x1,x2
t=np.linspace(0,1,2001)[:,None]; s=np.linspace(0,1,401)[None,:]
d1,d2=xi(s,t,True); stretch=np.hypot(d1,d2)
Lt=np.trapz(stretch,s[0],axis=1)
print("1) FB length over cycle: min %.3f max %.3f mean %.3f ; local |dx/ds| min %.3f max %.3f"%(Lt.min(),Lt.max(),Lt.mean(),stretch.min(),stretch.max()))
Np=20; sp=(np.arange(Np)+0.5)/Np
x1,x2=xi(sp[None,:],t)
print("2) panel z: min %.4f max %.4f ; tip x range %.3f..%.3f"%(x2.min(),x2.max(),x1[:,-1].min(),x1[:,-1].max()))
for k in (3.4,):
    out=erfc(k)+2/np.sqrt(np.pi)*k*np.exp(-k*k)
    print("3) Gaussian mass beyond r_cut=%.1f eps: %.2e (= %.4f %%)"%(k,out,100*out))
eps=0.1
# fraction of each panel's Gaussian inside z>0 (cutoff ignored)
frac=0.5*(1+erf(x2/eps))
# force magnitude with u=0 (RFT) to weight
x1d=np.gradient(x1,t[:,0],axis=0); x2d=np.gradient(x2,t[:,0],axis=0)
tx=np.gradient(x1,sp,axis=1); tz=np.gradient(x2,sp,axis=1); n=np.hypot(tx,tz); tx/=n; tz/=n
Vt=x1d*tx+x2d*tz; Fx=(Vt*tx)*1+ (x1d-Vt*tx)*2; Fz=(Vt*tz)+(x2d-Vt*tz)*2
print("4) Gaussian mass inside fluid: panel 1 (s=0.025) time-mean %.3f, min over all %.3f"%(frac[:,0].mean(),frac.min()))
print("   cycle-mean x force (u=0, RFT shape): full %.4f, with wall loss %.4f  (ratio %.3f)"%(Fx.sum(1).mean(),(Fx*frac).sum(1).mean(),(Fx*frac).sum(1).mean()/Fx.sum(1).mean()))
print("   rms x force: full %.4f, wall loss %.4f"%(np.sqrt((Fx.sum(1)**2).mean()),np.sqrt(((Fx*frac).sum(1)**2).mean())))
# relaxation filter H = 1/(1+i f/fc)
fc=1.5915494
for h in range(1,7):
    H=1/(1+1j*h/fc); print("5) harmonic %d: |H| %.2f, lag %.0f deg"%(h,abs(H),-np.angle(H,deg=True)))
F=np.fft.rfft(Fx.sum(1)[:-1]); fr=np.arange(len(F)); Ff=F/(1+1j*fr/fc)
fx=np.fft.irfft(Ff,n=2000)
print("   filtered x force: mean %.4f (raw %.4f), rms %.4f (raw %.4f), peak %.3f (raw %.3f)"%(fx.mean(),Fx.sum(1)[:-1].mean(),fx.std(),Fx.sum(1)[:-1].std(),fx.max(),Fx.sum(1).max()))
i=np.unravel_index(stretch.argmax(),stretch.shape); j=np.unravel_index(stretch.argmin(),stretch.shape)
print("6) max stretch at t=%.3f s=%.3f ; min at t=%.3f s=%.3f"%(t[i[0],0],s[0,i[1]],t[j[0],0],s[0,j[1]]))
pl=np.hypot(np.diff(xi(np.linspace(0,1,21)[None,:],t)[0],axis=1),np.diff(xi(np.linspace(0,1,21)[None,:],t)[1],axis=1))*20
print("   panel length / (L/N_p): min %.2f max %.2f; fraction of (t,panel) off by >10%%: %.2f"%(pl.min(),pl.max(),(abs(pl-1)>0.1).mean()))
