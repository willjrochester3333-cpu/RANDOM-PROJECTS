#!/usr/bin/env python3
"""First-flight study: the TSP E20 as KESTREL-2's first motor (TEST_PLAN flights 1-2), real flight code in the loop.

Flight 1 flies with the fin tabs OFF (TVC only, `tabs 0`), flight 2 with them on; both without payload and only in
winds up to 3 m/s (the test plan's limit for the first flights). A third batch flies flight 2's set-up in 3-6 m/s wind
to show what happens beyond that limit. Every other dispersion is the main Monte Carlo's (sim/montecarlo.py).

What the first motor has to do is give the parachute room: for every flight this records how high the rocket is when
the latch opens, how high it still is when the canopy is fully open, and how long it then hangs under it.

    python3 sim/first_flight_mc.py [N_FLIGHT1] [N_FLIGHT2] [N_WINDY]        (default 300 300 100)
Writes sim/results/first_flight_mc.json and first_flight_mc.md.
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RES = os.path.join(HERE, "results")
MOTOR = "TSP-E20"
BATCHES = {
    "flight1_tvc_only": dict(tabs=False, wind=(0.0, 3.0), seed0=300_000,
                             title="Flight 1: E20, TVC only (tabs 0), no payload, wind 0-3 m/s"),
    "flight2_tabs_on": dict(tabs=True, wind=(0.0, 3.0), seed0=310_000,
                            title="Flight 2: E20, TVC + fin tabs, no payload, wind 0-3 m/s"),
    "beyond_limit_3_6": dict(tabs=True, wind=(3.0, 6.0), seed0=320_000,
                             title="Beyond the first-flight wind limit: E20, tabs on, wind 3-6 m/s"),
}


def run_one(args):
    import montecarlo
    from kestrel.dynamics import Simulation, SimConfig
    from kestrel.sil import SilFsw
    batch, i = args
    b = BATCHES[batch]
    cfg = montecarlo.sample(b["seed0"] + i, MOTOR)
    rng = np.random.default_rng(b["seed0"] + 7 * i + 1)
    cfg["wind_speed"] = float(rng.uniform(*b["wind"]))
    cfg["payload_g"] = 0.0
    cfg["tabs_enabled"] = b["tabs"]
    sim = Simulation(SimConfig(**cfg), SilFsw())
    ev = sim.run()
    L = sim.log
    t, z = np.asarray(L["t"]), np.asarray(L["z"])

    def z_at(tt):
        return float(np.interp(tt, t, z)) if tt is not None else None
    full_t = ev.get("chute_full_t")
    out = dict(i=i, wind=cfg["wind_speed"], apogee=ev.get("apogee"), deploy_alt=ev.get("deploy_alt"),
               full_open_alt=z_at(full_t), full_open_t=full_t, landing_t=ev.get("landing_t"),
               deploy_minus_apogee_s=ev.get("deploy_minus_apogee_s"), deploy_speed=ev.get("deploy_speed"),
               landing_vz=ev.get("landing_vz"), landing_dist=ev.get("landing_dist"), max_tilt_burn=ev.get("max_tilt_burn"),
               max_tilt_coast=ev.get("max_tilt_coast"), tilt_apogee=ev.get("tilt_apogee"), rod_exit_speed=ev.get("rod_exit_speed"),
               max_roll_rate_burn=ev.get("max_roll_rate_burn"), final_state=ev.get("final_state"))
    out["under_canopy_s"] = (out["landing_t"] - full_t) if (full_t is not None and out["landing_t"] is not None) else None
    out["ok"] = bool(out["max_tilt_burn"] is not None and out["max_tilt_burn"] < 10 and out["deploy_minus_apogee_s"] is not None
                     and abs(out["deploy_minus_apogee_s"]) < 1.5 and (out["deploy_speed"] or 99) < 15
                     and (out["landing_vz"] or 99) < 7 and out["final_state"] == 6)
    return batch, out


def stats(rows, key):
    a = np.array([r[key] for r in rows if r.get(key) is not None], dtype=float)
    if not len(a):
        return None
    return dict(mean=float(a.mean()), p5=float(np.percentile(a, 5)), p50=float(np.percentile(a, 50)),
                p95=float(np.percentile(a, 95)), min=float(a.min()), max=float(a.max()))


def main():
    n = [int(sys.argv[k]) if len(sys.argv) > k else d for k, d in ((1, 300), (2, 300), (3, 100))]
    jobs = [(b, i) for b, nb in zip(BATCHES, n) for i in range(nb)]
    t0 = time.time()
    rows = {b: [] for b in BATCHES}
    with ProcessPoolExecutor() as ex:
        for k, (b, r) in enumerate(ex.map(run_one, jobs, chunksize=4)):
            rows[b].append(r)
            if (k + 1) % 100 == 0:
                print(f"{k + 1}/{len(jobs)} flights ({time.time() - t0:.0f} s)", flush=True)
    keys = ["apogee", "deploy_alt", "full_open_alt", "under_canopy_s", "deploy_speed", "landing_vz", "landing_dist",
            "max_tilt_burn", "max_tilt_coast", "rod_exit_speed", "max_roll_rate_burn"]
    summ = {}
    for b, rs in rows.items():
        s = {k: stats(rs, k) for k in keys}
        s["n"] = len(rs)
        s["success_rate"] = sum(r["ok"] for r in rs) / max(1, len(rs))
        s["title"] = BATCHES[b]["title"]
        lowest = min(rs, key=lambda r: r["full_open_alt"] if r["full_open_alt"] is not None else -1e9)
        s["lowest_full_open"] = {k: lowest[k] for k in ("i", "wind", "apogee", "full_open_alt", "under_canopy_s", "landing_vz")}
        summ[b] = s
    json.dump(dict(motor=MOTOR, summary=summ, rows=rows, seconds=time.time() - t0), open(os.path.join(RES, "first_flight_mc.json"), "w"))
    md = ["# First-flight study: TSP E20 (`sim/first_flight_mc.py`)", "",
          "Real flight code in the loop; the main Monte Carlo's dispersions (motor impulse, mass, drag, CG, sensors, servos, rod",
          "tilt, gusts...), no payload. *Full open* = the canopy has reached its full size (latch delay + fill time).", ""]
    md += ["| | " + " | ".join(BATCHES[b]["title"].split(":")[0] for b in BATCHES) + " |", "|---|" + "---|" * len(BATCHES)]

    def row(label, key, fmt, which="p50"):
        vals = []
        for b in BATCHES:
            s = summ[b][key]
            vals.append("–" if s is None else fmt.format(s[which]))
        md.append(f"| {label} | " + " | ".join(vals) + " |")
    md.append("| flights | " + " | ".join(str(summ[b]["n"]) for b in BATCHES) + " |")
    md.append("| success (criteria as the main Monte Carlo) | " + " | ".join(f"{100 * summ[b]['success_rate']:.1f} %" for b in BATCHES) + " |")
    row("apogee, median m", "apogee", "{:.1f}")
    row("apogee, 5th percentile m", "apogee", "{:.1f}", "p5")
    row("latch opens at, median m", "deploy_alt", "{:.1f}")
    row("canopy fully open at, median m", "full_open_alt", "{:.1f}")
    row("canopy fully open at, 5th percentile m", "full_open_alt", "{:.1f}", "p5")
    row("canopy fully open at, lowest m", "full_open_alt", "{:.1f}", "min")
    row("time under the open canopy, median s", "under_canopy_s", "{:.1f}")
    row("time under the open canopy, shortest s", "under_canopy_s", "{:.1f}", "min")
    row("speed when the latch opens, 95th pct m/s", "deploy_speed", "{:.1f}", "p95")
    row("landing speed, 95th percentile m/s", "landing_vz", "{:.1f}", "p95")
    row("landing distance, 95th percentile m", "landing_dist", "{:.0f}", "p95")
    row("max tilt in boost, 95th percentile deg", "max_tilt_burn", "{:.1f}", "p95")
    row("rod exit speed, median m/s", "rod_exit_speed", "{:.1f}")
    row("roll rate in boost, 95th percentile deg/s", "max_roll_rate_burn", "{:.0f}", "p95")
    md += ["", f"{sum(len(v) for v in rows.values())} flights in {time.time() - t0:.0f} s."]
    open(os.path.join(RES, "first_flight_mc.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
