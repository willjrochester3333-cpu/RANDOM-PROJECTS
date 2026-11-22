#!/usr/bin/env python3
"""Monte-Carlo dispersion analysis, real flight code in the loop.

    python3 montecarlo.py [N_E20] [N_E12] [N_D20]
"""
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def sample(i, motor):
    rng = np.random.default_rng(10_000 + i)
    return dict(
        motor=motor, seed=int(10_000 + i), t_pad=5.0,
        wind_speed=float(rng.uniform(0.0, 6.0)), wind_toward_deg=float(rng.uniform(0, 360)),
        gust_sigma=float(rng.uniform(0.2, 1.5)),
        thrust_misalign_deg=float(abs(rng.normal(0, 0.5))), thrust_misalign_az_deg=float(rng.uniform(0, 360)),
        fin_cant_deg=float(rng.normal(0, 0.3)),
        mass_scale=float(rng.normal(1.0, 0.04)), cg_shift=float(rng.normal(0, 0.008)),
        cd_scale=float(rng.normal(1.0, 0.08)), cna_scale=float(rng.normal(1.0, 0.07)),
        impulse_scale=float(rng.normal(1.0, 0.04)), burn_time_scale=float(rng.normal(1.0, 0.04)),
        rod_tilt_deg=float(abs(rng.normal(0, 1.5))), rod_tilt_az_deg=float(rng.uniform(0, 360)),
        servo_trim_err_deg=(float(rng.normal(0, 0.4)), float(rng.normal(0, 0.4))),
        servo_rate_dps=float(rng.uniform(450, 650)), servo_tau=float(rng.uniform(0.008, 0.02)),
        gimbal_backlash_deg=float(rng.uniform(0.1, 0.35)),
        gyro_bias_dps=tuple(float(x) for x in rng.normal(0, 0.5, 3)),
        accel_bias_mg=tuple(float(x) for x in rng.normal(0, 15, 3)),
        imu_misalign_deg=float(abs(rng.normal(0, 0.5))),
        baro_noise_pa=float(rng.uniform(0.3, 0.8)), baro_port_cp=float(rng.normal(-0.02, 0.03)),
        chute_cd=float(rng.normal(0.8, 0.08)), deploy_latch_delay=float(rng.uniform(0.1, 0.25)),
        chute_fill_time=float(rng.uniform(0.4, 0.9)), initial_roll_deg=float(rng.uniform(0, 360)),
        site_alt_asl=float(rng.uniform(0, 300)),
    )


def run_one(args):
    from kestrel.dynamics import Simulation, SimConfig
    from kestrel.sil import SilFsw
    i, motor = args
    cfg = sample(i, motor)
    sim = Simulation(SimConfig(**cfg), SilFsw())
    ev = sim.run()
    out = {k: ev.get(k) for k in ["apogee", "apogee_t", "max_tilt_burn", "tilt_burnout", "max_gimbal", "rod_exit_speed",
                                  "deploy_minus_apogee_s", "deploy_speed", "landing_vz", "landing_dist", "final_state",
                                  "max_accel_g", "max_speed", "max_opening_g", "max_aoa_deg"]}
    out["landing_pos"] = ev.get("landing_pos")
    out["wind"] = cfg["wind_speed"]
    out["i"] = i
    return motor, out


def summarise(rows):
    def stats(key):
        a = np.array([r[key] for r in rows if r.get(key) is not None], dtype=float)
        return dict(mean=float(a.mean()), std=float(a.std()), p5=float(np.percentile(a, 5)),
                    p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95)), min=float(a.min()), max=float(a.max()))
    keys = ["apogee", "max_tilt_burn", "tilt_burnout", "max_gimbal", "rod_exit_speed", "deploy_minus_apogee_s",
            "deploy_speed", "landing_vz", "landing_dist", "max_accel_g", "max_opening_g"]
    s = {k: stats(k) for k in keys}
    ok = [r for r in rows if r["max_tilt_burn"] < 10 and r["deploy_minus_apogee_s"] is not None and
          abs(r["deploy_minus_apogee_s"]) < 1.5 and r["deploy_speed"] < 15 and (r["landing_vz"] or 99) < 7 and r["final_state"] == 6]
    s["success_rate"] = len(ok) / len(rows)
    s["n"] = len(rows)
    return s


def main():
    n12 = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    n20 = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    nd = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    from kestrel.sil import build
    build()
    jobs = [(i, "TSP-E20") for i in range(n12)] + [(100_000 + i, "TSP-E12") for i in range(n20)] + \
           [(200_000 + i, "TSP-D20") for i in range(nd)]
    t0 = time.time()
    res = {}
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for motor, out in ex.map(run_one, jobs, chunksize=4):
            res.setdefault(motor, []).append(out)
    summary = {m: summarise(r) for m, r in res.items()}
    with open(os.path.join(RES, "montecarlo.json"), "w") as fh:
        json.dump(dict(summary=summary, runs=res), fh, indent=1, default=str)
    for m, s in summary.items():
        print(f"== {m}: n={s['n']} success={100*s['success_rate']:.1f}%")
        for k in ["apogee", "max_tilt_burn", "max_gimbal", "deploy_minus_apogee_s", "deploy_speed", "landing_vz", "landing_dist"]:
            v = s[k]
            print(f"   {k:24s} mean {v['mean']:7.2f}  sd {v['std']:6.2f}  p5 {v['p5']:7.2f}  p95 {v['p95']:7.2f}  max {v['max']:7.2f}")
    print(f"total {time.time()-t0:.0f} s")


if __name__ == "__main__":
    main()
