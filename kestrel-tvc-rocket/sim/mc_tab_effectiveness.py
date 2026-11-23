#!/usr/bin/env python3
"""Run: cd sim && python3 mc_tab_effectiveness.py

200 E20 Monte Carlo flights with the tab effectiveness centred 20 % above the model (flap-theory estimate for the
longer final tab), everything else as in montecarlo.py."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from concurrent.futures import ProcessPoolExecutor
import montecarlo as MC

def run(i):
    from kestrel.dynamics import Simulation, SimConfig
    from kestrel.sil import SilFsw
    cfg = MC.sample(i, "TSP-E20")
    cfg["tab_eff_scale"] = float(np.clip(cfg["tab_eff_scale"] * 1.2, 0.6, 1.7))
    ev = Simulation(SimConfig(**cfg), SilFsw()).run()
    out = {k: ev.get(k) for k in ["apogee", "max_tilt_burn", "tilt_burnout", "max_gimbal", "rod_exit_speed", "deploy_minus_apogee_s",
                                  "deploy_speed", "landing_vz", "landing_dist", "max_accel_g", "max_opening_g", "max_tilt_coast",
                                  "tilt_apogee", "max_roll_rate_burn", "max_roll_rate_coast", "max_abs_roll_deg", "max_tab", "final_state"]}
    out["tab_eff"] = cfg["tab_eff_scale"]
    return out

if __name__ == "__main__":
    from kestrel.sil import build
    build()
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        rows = list(ex.map(run, range(200), chunksize=4))
    s = MC.summarise(rows)
    print(f"tab effectiveness x1.2 (range {min(r['tab_eff'] for r in rows):.2f}-{max(r['tab_eff'] for r in rows):.2f}): "
          f"n={s['n']} success={100*s['success_rate']:.1f}%")
    for k in ["apogee", "max_tilt_burn", "max_tilt_coast", "max_roll_rate_burn", "max_roll_rate_coast", "max_abs_roll_deg", "max_tab", "landing_vz"]:
        v = s[k]; print(f"   {k:22s} mean {v['mean']:7.2f}  p95 {v['p95']:7.2f}  max {v['max']:7.2f}")
    print(f"total {time.time()-t0:.0f} s")
