"""Report plots (matplotlib). Palette/marks follow a validated categorical palette:
fixed slot order, 2 px lines, recessive grid, one y-axis per panel, legends + direct labels."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
PHASE = {"BOOST": "#fbe3d7", "COAST": "#e3edf9", "DESCENT": "#dff3ea"}


def style(ax, ylabel, title=None):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9.5)
    if title:
        ax.set_title(title, color=INK, fontsize=10.5, loc="left", fontweight="bold")


def new_fig(rows, cols=1, h=2.3, w=8.6):
    fig, axs = plt.subplots(rows, cols, figsize=(w, h * rows), sharex=(cols == 1), facecolor=SURFACE)
    return fig, np.atleast_1d(axs)


def shade_phases(ax, log):
    st = log["fsw_state"]
    t = log["t"]
    for code, name in ((3, "BOOST"), (4, "COAST"), (5, "DESCENT")):
        m = st == code
        if m.any():
            ax.axvspan(t[m][0], t[m][-1], color=PHASE[name], zorder=0, linewidth=0)


def label_end(ax, x, y, text, color):
    ax.annotate(text, (x[-1], y[-1]), xytext=(4, 0), textcoords="offset points", color=INK2, fontsize=8.5,
                va="center")
    ax.plot([x[-1]], [y[-1]], "o", ms=3.5, color=color)


def flight_overview(sim, path, title):
    L = sim.log
    ev = sim.events
    t = L["t"]
    m = t >= -0.2
    tend = min(t[-1], (ev.get("apogee_t") or 8) + 6)
    m &= t <= tend
    fig, axs = new_fig(4)
    ax = axs[0]
    shade_phases(ax, {k: v[m] for k, v in L.items()})
    ax.plot(t[m], L["z"][m], color=S1, lw=2, label="true altitude")
    ax.plot(t[m], L["alt_est"][m], color=S2, lw=1.6, ls="--", label="flight computer estimate")
    style(ax, "altitude (m)", title)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    if ev.get("apogee_t"):
        ax.annotate(f"apogee {ev['apogee']:.0f} m", (ev["apogee_t"], ev["apogee"]), xytext=(-60, -18),
                    textcoords="offset points", fontsize=8.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    if ev.get("deploy_cmd_t"):
        ax.axvline(ev["deploy_cmd_t"], color=INK2, lw=0.8, ls=":")
        ax.annotate("parachute released", (ev["deploy_cmd_t"], ev["deploy_alt"] * 0.55), xytext=(4, 0),
                    textcoords="offset points", fontsize=8, color=INK2)
    ax = axs[1]
    shade_phases(ax, {k: v[m] for k, v in L.items()})
    ax.plot(t[m], L["vz"][m], color=S1, lw=2, label="true")
    ax.plot(t[m], L["vz_est"][m], color=S2, lw=1.6, ls="--", label="estimate")
    style(ax, "vertical speed (m/s)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    ax = axs[2]
    shade_phases(ax, {k: v[m] for k, v in L.items()})
    ax.plot(t[m], L["tilt"][m], color=S1, lw=2)
    style(ax, "tilt from vertical (deg)")
    ax.set_ylim(0, max(5, float(np.nanmax(L["tilt"][m & (L["fsw_state"] <= 3)])) * 1.4))
    ax = axs[3]
    shade_phases(ax, {k: v[m] for k, v in L.items()})
    ax.plot(t[m], L["gimbal_y"][m], color=S1, lw=1.6, label="gimbal pitch")
    ax.plot(t[m], L["gimbal_z"][m], color=S2, lw=1.6, label="gimbal yaw")
    style(ax, "gimbal angle (deg)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper right", ncol=2)
    ax.set_xlabel("time since ignition (s)   shading: boost / coast / descent", color=INK2, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
