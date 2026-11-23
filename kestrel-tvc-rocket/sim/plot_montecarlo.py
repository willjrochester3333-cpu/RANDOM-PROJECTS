#!/usr/bin/env python3
"""Small-multiples summary of sim/results/montecarlo.json -> sim/results/montecarlo_summary.png
(one panel per metric, one outline histogram per motor, shared colours: E20 blue, D20 orange) and
sim/results/montecarlo_payload.png (apogee against payload mass, E20)."""
import json
import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COLORS = {"TSP-E20": "#2a78d6", "TSP-D20": "#eb6834"}
METRICS = [
    ("apogee", "Apogee (m)", None),
    ("max_tilt_burn", "Max tilt during boost (deg)", None),
    ("max_tilt_coast", "Max tilt during coast (deg)", None),
    ("max_roll_rate_burn", "Max roll rate during boost (deg/s)", None),
    ("max_abs_roll_deg", "Largest roll-angle error before apogee (deg)", None),
    ("max_tab", "Largest fin-tab deflection (deg)", 15.0),
    ("max_gimbal", "Largest gimbal deflection (deg)", 6.0),
    ("deploy_minus_apogee_s", "Parachute release minus true apogee (s)", None),
    ("landing_dist", "Landing distance from the pad (m)", None),
]


def main():
    d = json.load(open(os.path.join(RES, "montecarlo.json")))
    runs, summ = d["runs"], d["summary"]
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "text.color": INK})
    fig, axes = plt.subplots(3, 3, figsize=(14, 10.6), facecolor=SURFACE)
    for ax, (key, title, limit) in zip(axes.flat, METRICS):
        ax.set_facecolor(SURFACE)
        allv = np.concatenate([[r[key] for r in runs[m] if r.get(key) is not None] for m in COLORS])
        bins = np.linspace(np.percentile(allv, 0.2), np.percentile(allv, 99.5), 36)
        for m, c in COLORS.items():
            v = np.array([r[key] for r in runs[m] if r.get(key) is not None])
            ax.hist(v, bins=bins, histtype="step", lw=2, color=c, label=f"{m} (n={len(v)})")
            ax.axvline(np.median(v), color=c, lw=1, ls=(0, (2, 2)))
        if limit is not None:
            ax.axvline(limit, color=INK2, lw=1)
            ax.text(limit, ax.get_ylim()[1] * 0.97, "command limit ", color=INK2, va="top", ha="right", fontsize=8.5)
        ax.set_title(title, loc="left", color=INK, fontsize=11)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.set_ylabel("flights")
    axes.flat[0].legend(frameon=False, fontsize=9, loc="upper left")
    e20 = summ["TSP-E20"]
    fig.suptitle(
        f"Monte Carlo, real flight code in the loop: {sum(len(v) for v in runs.values())} flights, "
        f"success {min(s['success_rate'] for s in summ.values()) * 100:.0f}% on every motor  |  "
        f"E20 apogee {e20['apogee']['mean']:.0f} m (5-95%: {e20['apogee']['p5']:.0f}-{e20['apogee']['p95']:.0f} m)",
        x=0.01, ha="left", color=INK, fontsize=12)
    fig.text(0.01, 0.005, textwrap.fill("Dashed line = median per motor. Each flight draws: wind 0-6 m/s from any direction + gusts, impulse and burn "
             "time (1 sd 4 %), mass (4 %), CG (8 mm), drag (8 %), fin lift (7 %), payload 0-50 g, thrust misalignment, fin cant and per-fin "
             "misalignment, rod tilt, TVC and tab servo trim/speed/backlash, tab effectiveness (15 %), gyro/accel bias, IMU misalignment, "
             "baro noise, chute Cd and fill time, latch delay, site altitude.", 190), color=INK2, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    out = os.path.join(RES, "montecarlo_summary.png")
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    print("saved", out)
    # apogee against payload mass (E20): one series, so no legend box - the title names it
    r = [x for x in runs["TSP-E20"] if x.get("payload_g") is not None]
    pl = np.array([x["payload_g"] for x in r]); ap = np.array([x["apogee"] for x in r])
    fig, ax = plt.subplots(figsize=(8.6, 4.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.scatter(pl, ap, s=14, color=COLORS["TSP-E20"], alpha=0.55, linewidths=0)
    k, c = np.polyfit(pl, ap, 1)
    xx = np.array([0, 50])
    ax.plot(xx, k * xx + c, color=INK, lw=2)
    ax.annotate(f"trend: {c:.0f} m empty, {k * 10:+.1f} m per 10 g", (50, k * 50 + c), xytext=(-8, 14), textcoords="offset points",
                ha="right", color=INK, fontsize=9.5)
    ax.set_xlabel("payload in the bay (g)", color=INK2)
    ax.set_ylabel("apogee (m)", color=INK2)
    ax.set_title(f"TSP E20: apogee against payload ({len(r)} randomised flights, wind 0-6 m/s)", loc="left", color=INK, fontsize=11)
    ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    fig.tight_layout()
    out2 = os.path.join(RES, "montecarlo_payload.png")
    fig.savefig(out2, dpi=130, facecolor=SURFACE)
    print("saved", out2)


if __name__ == "__main__":
    main()
