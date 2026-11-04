"""Figures for the nekRS cilia model document: beat, kernels, layout.

Reads the Fulford & Blake coefficients from cilia.udf and the small4 coordinates;
writes PDF + 600 dpi PNG into ./figures/ next to this script.
"""
import re
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from scipy.integrate import quad
from scipy.special import erfc

HERE = Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p / "cilia.udf").exists())   # repo root
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)

# Okabe-Ito
VERM, BLUE, SKY, ORANGE, GREEN, GREY = "#D55E00", "#0072B2", "#56B4E9", "#E69F00", "#009E73", "#6b6b6b"
MM = 1 / 25.4

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["CMU Serif", "Latin Modern Math"],
    "mathtext.fontset": "cm", "axes.unicode_minus": False,
    "font.size": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "lines.linewidth": 1.0,
    "pdf.fonttype": 42, "savefig.dpi": 600,
})


def panel_label(ax, txt, dx=0.0, dy=1.0):
    ax.text(dx, dy, txt, transform=ax.transAxes, fontsize=8, fontweight="bold",
            ha="left", va="bottom")


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=600)
    plt.close(fig)


# ---------------------------------------------------------------- beat data
udf = (REPO / "cilia.udf").read_text()


def arr(name):
    m = re.search(rf"dfloat\s+{name}\[\d+\]\s*=\s*\{{([^}}]*)\}}", udf)
    return np.array([float(v) for v in m.group(1).replace("\n", " ").split(",")])


A1, A2, B1, B2 = arr("A1"), arr("A2"), arr("B1"), arr("B2")
assert len(A1) == len(A2) == 21 and len(B1) == len(B2) == 18
NO = 6
W = 2 * np.pi


def coeff(C, col, s, d=0):
    """Column col (1-based) polynomial sum_m C[(col-1)*3+m-1] s^m, or its s-derivative (d=1)."""
    c = C[(col - 1) * 3:(col - 1) * 3 + 3]
    if d == 0:
        return c[0] * s + c[1] * s**2 + c[2] * s**3
    return c[0] + 2 * c[1] * s + 3 * c[2] * s**2


def xi(A, B, s, t, d=0):
    out = 0.5 * coeff(A, 1, s, d)
    for j in range(1, NO + 1):
        out = out + coeff(A, j + 1, s, d) * np.cos(j * W * t) + coeff(B, j, s, d) * np.sin(j * W * t)
    return out


def shape(t, s):
    return xi(A1, B1, s, t), xi(A2, B2, s, t)


def tip_vel(t, h=1e-6):
    return (xi(A1, B1, 1.0, t + h) - xi(A1, B1, 1.0, t - h)) / (2 * h)


s_fine = np.linspace(0, 1, 401)
t_fine = np.linspace(0, 1, 801)
ds = s_fine[1] - s_fine[0]


def arclength(t):
    sx, sz = xi(A1, B1, s_fine, t, 1), xi(A2, B2, s_fine, t, 1)
    v = np.hypot(sx, sz)
    return np.sum(0.5 * (v[1:] + v[:-1])) * ds


Lt = np.array([arclength(t) for t in t_fine])
S, T = np.meshgrid(s_fine, t_fine)
X1, X2 = xi(A1, B1, S, T), xi(A2, B2, S, T)
tip1, tip2 = X1[:, -1], X2[:, -1]
vtip = np.array([tip_vel(t) for t in t_fine])

# Effective stroke: the cilium is extended, tip high, and moves the fluid forward.
# Sign of the tip xi1-velocity while the tip is above its median height.
high = tip2 > np.median(tip2)
SGN = np.sign(vtip[high].mean())
mean_v_high, mean_v_low = vtip[high].mean(), vtip[~high].mean()
print(f"L(t): min {Lt.min():.3f} max {Lt.max():.3f} mean {Lt.mean():.3f}")
print(f"panel z (xi2 over s,t): min {X2.min():.3f} max {X2.max():.3f}; "
      f"panel-centre z (s=(i+.5)/N_p, i.e. s in [0.5/N,1-0.5/N]) same order")
print(f"tip height range {tip2.min():.3f}..{tip2.max():.3f}; mean tip xi1-velocity "
      f"while tip high {mean_v_high:+.2f}, while low {mean_v_low:+.2f} -> effective stroke is "
      f"d xi1_tip/dt {'>' if SGN > 0 else '<'} 0")
print(f"xi1 range over s,t: {X1.min():.3f} .. {X1.max():.3f}")


def is_eff(t):
    return SGN * tip_vel(t) > 0


def col(t):
    return VERM if is_eff(t) else BLUE


# ---------------------------------------------------------------- fig 1
def fig_beat():
    fig = plt.figure(figsize=(150 * MM, 58 * MM))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.6, 1], left=0.07, right=0.985, bottom=0.17, top=0.92, wspace=0.3)
    ax = fig.add_subplot(gs[0])
    ph = np.arange(16) / 16
    for k, t in enumerate(ph):
        x, z = shape(t, s_fine)
        ax.plot(x, z, color=col(t), lw=0.7, alpha=0.45 + 0.55 * k / 15, solid_capstyle="round")
    ax.plot(tip1, tip2, color=GREY, ls=(0, (3, 2)), lw=0.7)
    # arrowhead on tip path, mid-way along an interval
    # on the upper (effective-stroke) leg, where the tip moves along +xi1 direction of travel
    cand = np.where((SGN * vtip > 0) & (np.abs(tip1 - 0.25) < 0.05) & (tip2 > 0.8))[0]
    i0 = cand[0]
    ax.annotate("", xy=(tip1[i0 + 8], tip2[i0 + 8]), xytext=(tip1[i0], tip2[i0]),
                arrowprops=dict(arrowstyle="-|>", color=GREY, lw=0.7, mutation_scale=8, shrinkA=0, shrinkB=0))
    xl = ax.get_xlim()
    ax.axhline(0, color="#222222", lw=1.8, solid_capstyle="butt", zorder=3)
    ax.add_patch(Rectangle((-1e3, -0.07), 2e3, 0.07, facecolor="none", edgecolor="#9a9a9a", hatch="////", lw=0, zorder=1))
    ax.set_aspect("equal")
    ax.set_xlim(X1.min() - 0.12, X1.max() + 0.12)
    ax.set_ylim(-0.07, X2.max() + 0.1)
    ax.set_xlabel(r"$\xi_1/L$"); ax.set_ylabel(r"$\xi_2/L$")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(handles=[Line2D([], [], color=VERM, lw=0.9), Line2D([], [], color=BLUE, lw=0.9),
                       Line2D([], [], color=GREY, lw=0.7, ls=(0, (3, 2)))],
              labels=["effective stroke", "recovery stroke", "tip path"],
              loc="upper left", frameon=False, handlelength=1.8, borderaxespad=0.2, labelspacing=0.3)
    panel_label(ax, "(a)", dx=-0.02)

    ax2 = fig.add_subplot(gs[1])
    ax2.plot(t_fine, Lt, color=VERM, lw=1.0)
    ax2.axhline(1, color=GREY, ls=":", lw=0.7)
    ax2.axhline(Lt.mean(), color=BLUE, ls="--", lw=0.7)
    ax2.annotate(f"mean {Lt.mean():.2f}", (0.45, Lt.mean()), xytext=(0.40, 0.985), color="#222222",
                 ha="left", va="center", arrowprops=dict(arrowstyle="-", color="#222222", lw=0.5, shrinkB=0))
    ax2.text(0.98, 1.0 + 0.003, r"$L$", color=GREY, ha="right", va="bottom", transform=ax2.get_yaxis_transform())
    ax2.set_xlim(0, 1)
    ax2.set_xlabel(r"$t/T$"); ax2.set_ylabel(r"arclength $/\,L$")
    for sp in ("top", "right"):
        ax2.spines[sp].set_visible(False)
    panel_label(ax2, "(b)", dx=-0.22)
    save(fig, "beat")


# ---------------------------------------------------------------- fig 2
def delta_g(r):
    return np.exp(-r**2) / np.pi**1.5


def delta_g2(r):
    return (2.5 - r**2) * np.exp(-r**2) / np.pi**1.5


def out_g(r):
    return erfc(r) + 2 * r * np.exp(-r**2) / np.sqrt(np.pi)


def out_g2(r):
    return quad(lambda q: 4 * np.pi * q**2 * delta_g2(q), r, np.inf, epsabs=1e-18, epsrel=1e-8, limit=200)[0]


def sci(v):
    e = int(np.floor(np.log10(v)))
    return rf"${v / 10**e:.1f}\times10^{{{e}}}$"


def fig_kernels():
    r1, r2 = 3.4, 3.8
    print(f"gauss outside 3.4: {out_g(r1):.3e}; 3.8: {out_g(r2):.3e}")
    print(f"gauss2 outside 3.4: {out_g2(r1):.3e}; 3.8: {out_g2(r2):.3e}  (signed; plotted as absolute value)")
    print(f"gauss2 total mass: {out_g2(0.0):.6f}; gauss: {out_g(0.0):.6f}")
    fig = plt.figure(figsize=(150 * MM, 52 * MM))
    gs = fig.add_gridspec(1, 2, left=0.075, right=0.985, bottom=0.2, top=0.93, wspace=0.28)
    ax = fig.add_subplot(gs[0])
    r = np.linspace(0, 4.2, 600)
    ax.axhline(0, color="#999999", lw=0.5)
    ax.plot(r, delta_g(r), color=BLUE, label="Gaussian")
    ax.plot(r, delta_g2(r), color=VERM, label="zero-second-moment (gauss2)")
    ax.axvline(r1, color=BLUE, ls="--", lw=0.7)
    ax.axvline(r2, color=VERM, ls="--", lw=0.7)
    ax.text(r1 - 0.06, 0.30, "old cutoff", color="#222222", rotation=90, ha="right", va="center", fontsize=7)
    ax.text(r2 + 0.06, 0.30, r"$r_\mathrm{cut}$", color="#222222", rotation=90, ha="left", va="center", fontsize=7)
    ax.set_xlim(0, 4.2)
    ax.set_xlabel(r"$r/\varepsilon$"); ax.set_ylabel(r"$\varepsilon^3\,\delta$")
    ax.legend(loc="upper right", frameon=False, handlelength=1.6, borderaxespad=0.2, bbox_to_anchor=(0.78, 1.0))
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    panel_label(ax, "(a)", dx=-0.13)

    ax2 = fig.add_subplot(gs[1])
    r = np.linspace(0, 4.5, 451)
    mg = out_g(r)
    mg2 = np.abs(np.array([out_g2(x) for x in r]))
    ax2.semilogy(r, np.maximum(mg, 1e-30), color=BLUE)
    ax2.semilogy(r, np.maximum(mg2, 1e-30), color=VERM)
    ax2.plot([r1], [out_g(r1)], "o", color=BLUE, ms=3.5, zorder=4)
    ax2.plot([r2], [abs(out_g2(r2))], "o", color=VERM, ms=3.5, zorder=4)
    ax2.annotate(sci(out_g(r1)), (r1, out_g(r1)), xytext=(-6, -6), textcoords="offset points",
                 ha="right", va="top", color="#222222", fontsize=7)
    ax2.annotate(sci(abs(out_g2(r2))), (r2, abs(out_g2(r2))), xytext=(4.0, 3e-3), textcoords="data",
                 ha="center", va="center", color="#222222", fontsize=7,
                 arrowprops=dict(arrowstyle="-", color="#222222", lw=0.5, shrinkA=1, shrinkB=2))
    ax2.set_ylim(1e-8, 1); ax2.set_xlim(0, 4.5)
    ax2.set_yticks([10.0**k for k in range(-8, 1, 2)])
    ax2.set_xlabel(r"$r/\varepsilon$"); ax2.set_ylabel(r"$|$mass outside $r|$")
    for sp in ("top", "right"):
        ax2.spines[sp].set_visible(False)
    panel_label(ax2, "(b)", dx=-0.17)
    save(fig, "kernels")


# ---------------------------------------------------------------- fig 3
def fig_layout():
    cs = np.loadtxt(REPO / "cases/small4/coordinates_small4.txt")
    fig = plt.figure(figsize=(150 * MM, 62 * MM))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.0], left=0.065, right=0.985, bottom=0.15, top=0.93, wspace=0.22)
    ax = fig.add_subplot(gs[0])
    lo, hi = X1.min(), X1.max()
    shifts = [(i, j) for i in (-1, 0, 1) for j in (-1, 0, 1)]
    for gx in np.arange(-0.5, 0.5001, 0.1):
        ax.plot([gx, gx], [-0.5, 0.5], color="#dddddd", lw=0.4, zorder=0)
        ax.plot([-0.5, 0.5], [gx, gx], color="#dddddd", lw=0.4, zorder=0)
    for (i, j) in shifts:
        main = (i, j) == (0, 0)
        a = 1.0 if main else 0.25
        for x0, y0, b in cs:
            c, s_ = np.cos(b), np.sin(b)
            xr, yr = x0 + i, y0 + j
            ax.plot([xr + lo * c, xr + hi * c], [yr + lo * s_, yr + hi * s_], color=SKY, lw=3.0, alpha=0.55 * (1 if main else 0.45),
                    solid_capstyle="round", zorder=2)
            ax.plot(xr, yr, "o", color="k", ms=2.5, alpha=a, zorder=4)
            ax.annotate("", xy=(xr + SGN * 0.15 * c, yr + SGN * 0.15 * s_), xytext=(xr, yr),
                        arrowprops=dict(arrowstyle="-|>", color=VERM, lw=0.9, mutation_scale=6, alpha=a, shrinkA=0, shrinkB=0), zorder=5)
    ax.add_patch(Rectangle((-0.5, -0.5), 1, 1, fill=False, edgecolor="k", lw=0.8, zorder=6))
    ax.set_aspect("equal"); ax.set_xlim(-0.8, 0.8); ax.set_ylim(-0.8, 0.8)
    ax.set_xticks([-0.5, 0, 0.5]); ax.set_yticks([-0.5, 0, 0.5])
    ax.set_xlabel(r"$x/L$"); ax.set_ylabel(r"$y/L$")
    panel_label(ax, "(a)", dx=-0.1)

    ax2 = fig.add_subplot(gs[1])
    for gx in np.arange(-0.5, 0.5001, 0.1):
        ax2.plot([gx, gx], [0, 1.5], color="#e0e0e0", lw=0.4, zorder=0)
    for gz in np.arange(0, 1.5001, 0.125):
        ax2.plot([-0.5, 0.5], [gz, gz], color="#e0e0e0", lw=0.4, zorder=0)
    x0, y0, b = cs[0]
    for k in range(6):
        t = k / 6
        x, z = shape(t, s_fine)
        ax2.plot(x0 + x * np.cos(b), z, color=col(t), lw=0.8, zorder=3)
    ax2.plot(x0, 0, "o", color="k", ms=2.5, zorder=4)
    ax2.plot([-0.5, 0.5], [0, 0], color="#222222", lw=1.8, solid_capstyle="butt", zorder=5)
    ax2.plot([-0.5, 0.5], [1.5, 1.5], color=GREY, lw=1.0, ls=(0, (4, 2)), zorder=5)
    ax2.plot([-0.5, -0.5], [0, 1.5], color=GREY, lw=1.0, ls=":", zorder=5)
    ax2.plot([0.5, 0.5], [0, 1.5], color=GREY, lw=1.0, ls=":", zorder=5)
    ax2.text(0, -0.06, "no-slip wall", ha="center", va="top", fontsize=7)
    ax2.text(0, 1.56, "symmetry (slip)", ha="center", va="bottom", fontsize=7)
    ax2.text(-0.53, 1.0, "periodic", ha="right", va="center", rotation=90, fontsize=7)
    ax2.text(0.53, 1.0, "periodic", ha="left", va="center", rotation=90, fontsize=7)
    ax2.set_aspect("equal"); ax2.set_xlim(-0.8, 0.8); ax2.set_ylim(-0.2, 1.7)
    ax2.set_xticks([-0.5, 0, 0.5]); ax2.set_yticks([0, 0.5, 1.0, 1.5])
    ax2.set_xlabel(r"$x/L$"); ax2.set_ylabel(r"$z/L$")
    for sp in ("top", "right", "bottom", "left"):
        ax2.spines[sp].set_visible(False)
    panel_label(ax2, "(b)", dx=-0.1)
    save(fig, "layout")


if __name__ == "__main__":
    fig_beat()
    fig_kernels()
    fig_layout()
