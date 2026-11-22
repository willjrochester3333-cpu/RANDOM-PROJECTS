#!/usr/bin/env python3
"""Small-multiples summary of sim/results/montecarlo.json -> sim/results/montecarlo_summary.png
(one panel per metric, one outline histogram per motor, shared colours: E20 blue, E12 orange, D20 aqua)."""
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
COLORS = {"TSP-E20": "#2a78d6", "TSP-E12": "#eb6834", "TSP-D20": "#1baf7a"}
METRICS = [
    ("apogee", "Apogee (m)", None),
    ("max_tilt_burn", "Max tilt during boost (deg)", None),
    ("max_gimbal", "Max gimbal deflection (deg)", 6.0),
    ("deploy_minus_apogee_s", "Deploy time minus true apogee (s)", None),
    ("deploy_speed", "Airspeed at deploy (m/s)", None),
    ("landing_dist", "Landing distance from pad (m)", None),
]


def main():
    d = json.load(open(os.path.join(RES, "montecarlo.json")))
    runs, summ = d["runs"], d["summary"]
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "text.color": INK})
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.6), facecolor=SURFACE)
    for ax, (key, title, limit) in zip(axes.flat, METRICS):
        ax.set_facecolor(SURFACE)
        allv = np.concatenate([[r[key] for r in runs[m] if r.get(key) is not None] for m in COLORS])
        bins = np.linspace(np.percentile(allv, 0.2), np.percentile(allv, 99.8), 36)
        for m, c in COLORS.items():
            v = np.array([r[key] for r in runs[m] if r.get(key) is not None])
            ax.hist(v, bins=bins, histtype="step", lw=2, color=c, label=f"{m} (n={len(v)})")
            ax.axvline(np.median(v), color=c, lw=1, ls=(0, (2, 2)))
        if limit is not None:
            ax.axvline(limit, color=INK2, lw=1)
            ax.text(limit, ax.get_ylim()[1] * 0.97, "command limit \n(+ servo backlash;\nCAD clearance\nchecked to 7°) ",
                    color=INK2, va="top", ha="right", fontsize=8.5)
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
             "time (1 sd 4 %), mass (4 %), CG (8 mm), drag (8 %), fin lift (7 %), thrust misalignment, fin cant, rod tilt, servo trim/speed/"
             "backlash, gyro/accel bias, IMU misalignment, baro noise, chute Cd and fill time, latch delay, site altitude.", 190),
             color=INK2, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    out = os.path.join(RES, "montecarlo_summary.png")
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    print("saved", out)


if __name__ == "__main__":
    main()
