"""Speed-up figure: small4 wall time per beat cycle (a), tiled8 cilia-model time per corrector (b).

All numbers are hard-coded from the project's own tables:
ROADMAP compute budget / ROADMAP_done P2.1, P2.2.
Writes speedups.pdf + 600 dpi speedups.png next to this script.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.transforms import blended_transform_factory

OUT = Path(__file__).resolve().parent

# Okabe-Ito
VERM, BLUE, SKY, ORANGE, GREEN, GREY = "#D55E00", "#0072B2", "#56B4E9", "#E69F00", "#009E73", "#6b6b6b"
MM = 1 / 25.4

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["CMU Serif", "Latin Modern Math"],
    "mathtext.fontset": "cm", "axes.unicode_minus": False,
    "font.size": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "lines.linewidth": 1.0,
    "pdf.fonttype": 42, "savefig.dpi": 600, "hatch.linewidth": 0.4,
})


def panel_label(ax, txt, dx=0.0, dy=1.0):
    ax.text(dx, dy, txt, transform=ax.transAxes, fontsize=8, fontweight="bold",
            ha="left", va="bottom")


# ------------------------------------------------------------------- data
# Source: ROADMAP compute budget / ROADMAP_done P2.1, P2.2.
# (a) small4, one A100: s per beat cycle. Rows 1-11 solver tuning, rows 12-15 model corrections.
ROWS_A = [
    ("v0.1 baseline: Navier–Stokes, $\\Delta t = 10^{-4}$, Jacobi PCG", 210, 0),
    ("velocity initial guess by projection", 136, 0),
    ("pressure Chebyshev degree 2", 131, 0),
    ("Stokes mode", 131, 0),
    ("$\\Delta t = 2\\times10^{-3}$, second-order force relaxation", 23.6, 0),
    ("velocity projection, 160 vectors", 14.1, 0),
    ("slip top + velocity $p$-multigrid", 11.4, 0),
    ("velocity tolerance $3\\times10^{-3}$", 9.2, 0),
    ("$p$-multigrid Chebyshev degree 2", 8.25, 0),
    ("velocity projection, 40 vectors", 7.50, 0),
    ("pressure tolerance $3\\times10^{-3}$", 7.21, 0),
    ("self-flow removal", 7.63, 1),
    ("implicit coupling $f = f^{*}$ (IQN), $\\Delta t = 10^{-3}$", 27.2, 1),
    ("arclength panels", 28.3, 1),
    ("zero-second-moment kernel, $\\varepsilon = 0.1$, $N_p = 20$", 29.0, 1),
]
VAL_FMT = {7.50: "7.50", 29.0: "29.0"}   # keep the trailing zero as tabulated
GROUP_COL = [BLUE, VERM]
GROUP_LAB = ["solver tuning (v0.1 model)", "model corrections (v0.2)"]

# (b) tiled8, one A100: ms per corrector.
# components: force spreading, IQN update, self-flow + RFT, other
COMP_LAB = ["force spreading", "IQN update", "self-flow + RFT", "other"]
COMP_COL = [BLUE, ORANGE, GREEN, GREY]
ROWS_B = [
    ("v0.2: spreading over all panels\n(estimated)", [359, 13.9, 5.6, 1.3], 380, True),
    ("binned spreading", [9.54, 13.9, 5.6, 1.3], 30.3, False),
    ("+ IQN corrector on the GPU", [8.66, 0.11, 0.09, 0.98], 9.8, False),
]
FLUID_MS = 337          # fluid solve per corrector, 337-360 ms

def head(a, lab, txt):
    """Panel label and heading on one line, flush with the figure's left edge."""
    tr = blended_transform_factory(fig.transFigure, a.transAxes)
    a.text(0.012, 1.04, lab, transform=tr, fontsize=8, fontweight="bold", ha="left", va="bottom")
    a.text(0.045, 1.04, txt, transform=tr, fontsize=7.5, ha="left", va="bottom")


# -------------------------------------------------------------------- figure
fig = plt.figure(figsize=(180 * MM, 125 * MM))
gs = fig.add_gridspec(2, 1, height_ratios=[15, 5.6], left=0.405, right=0.975,
                      top=0.945, bottom=0.095, hspace=0.34)

# ---- (a)
ax = fig.add_subplot(gs[0])
n = len(ROWS_A)
for i, (lab, v, g) in enumerate(ROWS_A):
    ax.barh(i, v - 1, left=1, height=0.68, color=GROUP_COL[g], lw=0)
    ax.text(v * 1.07, i, VAL_FMT.get(v, f"{v:g}"), va="center", ha="left", fontsize=7)
ax.text(7.21 * 1.07 * 1.55, 10, "29× over v0.1", va="center", ha="left", fontsize=7,
        style="italic")
ax.set_xscale("log")
ax.set_xlim(1, 600)
ax.set_ylim(n - 0.4, -0.6)
ax.set_yticks(range(n))
ax.set_yticklabels([r[0] for r in ROWS_A])
ax.tick_params(axis="y", length=0)
ax.set_xlabel("s per beat cycle")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(handles=[Patch(color=c, label=l) for c, l in zip(GROUP_COL, GROUP_LAB)],
          loc="lower right", frameon=False, handlelength=1.0, handleheight=0.8)
head(ax, "(a)", "small4 (4 cilia, 1,200 elements), one A100: wall time per beat cycle")

# ---- (b)
bx = fig.add_subplot(gs[1])
for i, (lab, comps, tot, est) in enumerate(ROWS_B):
    assert abs(sum(comps) - tot) < 0.06 * max(1, tot / 100), (lab, sum(comps), tot)
    left = 0.0
    for c, col in zip(comps, COMP_COL):
        bx.barh(i, c, left=left, height=0.62, color=col,
                edgecolor="white" if est else "none", hatch="////" if est else None,
                linewidth=0)
        left += c
    bx.text(left + 5, i, f"{tot:g} ms", va="center", ha="left", fontsize=7)
bx.axvline(FLUID_MS, color=GREY, ls="--", lw=0.8, zorder=0)
bx.text(FLUID_MS - 6, -0.62, "fluid solve per corrector (337–360 ms)", color=GREY,
        ha="right", va="center", fontsize=7)
bx.set_xlim(0, 480)
bx.set_ylim(2.5, -0.95)
bx.set_yticks(range(3))
bx.set_yticklabels([r[0] for r in ROWS_B])
bx.tick_params(axis="y", length=0)
bx.set_xlabel("ms per corrector")
for s in ("top", "right"):
    bx.spines[s].set_visible(False)
handles = [Patch(color=c, label=l) for c, l in zip(COMP_COL, COMP_LAB)]
bx.legend(handles=handles, loc="lower right", frameon=False,
          handlelength=1.0, handleheight=0.8, labelspacing=0.35)
head(bx, "(b)", "tiled8 (256 cilia, 76,800 elements), one A100: cilia-model time per fluid solve (corrector)")

fig.savefig(OUT / "speedups.pdf")
fig.savefig(OUT / "speedups.png", dpi=600)
plt.close(fig)
