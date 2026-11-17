"""Scaling figure: parallel efficiency T_1 / (P T_P) against load per GPU, one line per GPU count.

Numbers from docs/scaling.md, 'Measured' table. Writes scaling.pdf + 600 dpi scaling.png next to this script.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FixedFormatter, NullLocator

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

# ------------------------------------------------------------------- data
# Source: docs/scaling.md, 'Measured' table.
# Per P: (load E N^3 in millions, efficiency lo, efficiency hi); lo = hi is a single value.
SERIES = [
    ("2 GPUs, 1 node", SKY, "o",
     [(2.56, 0.862, 0.862), (5.12, 0.909, 0.909)]),
    ("4 GPUs, 1 node", BLUE, "s",
     [(1.28, 0.664, 0.664), (2.56, 0.771, 0.771), (3.84, 0.788, 0.788), (5.12, 0.807, 0.827)]),
    ("8 GPUs, 2 nodes", VERM, "^",
     [(1.28, 0.581, 0.581), (2.56, 0.679, 0.683), (5.12, 0.782, 0.798), (7.68, 0.798, 0.821)]),
    ("16 GPUs, 4 nodes", GREEN, "D",
     [(3.84, 0.665, 0.715), (5.12, 0.656, 0.729), (10.24, 0.640, 0.826)]),
]
# n_0.8 ranges (millions per GPU) for P = 4 and P = 8
N08 = {"4 GPUs, 1 node": (4.2, 4.6), "8 GPUs, 2 nodes": (5.2, 7.7)}
TICKS = [1.28, 2.56, 3.84, 5.12, 7.68, 10.24]
LADDER = 5.12

# -------------------------------------------------------------------- figure
fig, ax = plt.subplots(figsize=(89 * MM, 62 * MM))
fig.subplots_adjust(left=0.115, right=0.975, top=0.97, bottom=0.17)

ax.set_xscale("log", base=2)
ax.set_xlim(1.1, 12.5)
ax.set_ylim(0.5, 1.0)
ax.xaxis.set_major_locator(FixedLocator(TICKS))
ax.xaxis.set_major_formatter(FixedFormatter([f"{t:g}" for t in TICKS]))
ax.xaxis.set_minor_locator(NullLocator())
ax.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])

ax.axhline(0.8, color=GREY, ls="--", lw=0.5, zorder=1)
ax.text(1.12, 0.805, "80%", color=GREY, fontsize=6.5, ha="left", va="bottom")
ax.plot([LADDER, LADDER], [0.5, 0.855], color=GREY, ls=":", lw=0.6, zorder=1)  # stops under the legend
ax.text(LADDER * 1.02, 0.508, "ladder", color=GREY, fontsize=6.5, ha="left", va="bottom")

for lab, col, mk, pts in SERIES:
    if lab in N08:
        lo, hi = N08[lab]
        ax.plot([lo, hi], [0.8, 0.8], color=col, lw=2.5, alpha=0.35, solid_capstyle="butt", zorder=2)
    xs = [p[0] for p in pts]
    mid = [(p[1] + p[2]) / 2 for p in pts]
    ax.plot(xs, mid, color=col, lw=1.0, zorder=3)
    for x, lo, hi in pts:
        m = (lo + hi) / 2
        if hi > lo:
            ax.errorbar(x, m, yerr=(hi - lo) / 2, color=col, lw=0.6, capsize=1.5, capthick=0.6, zorder=3)
        ax.plot(x, m, mk, color=col, ms=3.5, mew=0, zorder=4)
    ax.plot([], [], mk + "-", color=col, ms=3.5, mew=0, lw=1.0, label=lab)

ax.text(6.3, 0.765, "$n_{0.8}$", color=GREY, fontsize=7, ha="center", va="center")

ax.set_xlabel("Load per GPU, $E N^3$ (millions)")
ax.set_ylabel("Parallel efficiency, $T_1 / (P\\,T_P)$")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(loc="upper right", frameon=False, handlelength=1.8, labelspacing=0.35)

fig.savefig(OUT / "scaling.pdf")
fig.savefig(OUT / "scaling.png", dpi=600)
plt.close(fig)
