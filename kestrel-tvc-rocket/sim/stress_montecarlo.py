#!/usr/bin/env python3
"""Stress Monte Carlo: the same real-flight-code simulation as montecarlo.py, but with every error source widened
well beyond what we expect (about twice the normal spread), to find where the design's margins end.

    python3 stress_montecarlo.py [N]        (default 1000 flights, TSP-F35)

The launch procedure is the documented one: the 1.5 m rod above 3 m/s of wind, never above 9 m/s.
Writes results/stress_montecarlo.json and prints success rates by wind band and every failure.
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import montecarlo as MC  # noqa: E402

RES = MC.RES


def sample_stress(i, motor="TSP-F35"):
    rng = np.random.default_rng(500_000 + i)
    wind = float(rng.uniform(0.0, 9.0))
    return dict(
        motor=motor, seed=int(500_000 + i), t_pad=5.0,
        wind_speed=wind, wind_toward_deg=float(rng.uniform(0, 360)), gust_sigma=float(rng.uniform(0.3, 2.5)),
        rod_length=1.5 if wind > 3.0 else 1.0,
        thrust_misalign_deg=float(abs(rng.normal(0, 1.0))), thrust_misalign_az_deg=float(rng.uniform(0, 360)),
        fin_cant_deg=float(rng.normal(0, 0.6)),
        mass_scale=float(rng.normal(1.0, 0.08)), cg_shift=float(rng.normal(0, 0.015)),
        cd_scale=float(rng.normal(1.0, 0.15)), cna_scale=float(rng.normal(1.0, 0.12)),
        impulse_scale=float(np.clip(rng.normal(1.0, 0.08), 0.85, 1.2)),
        burn_time_scale=float(rng.normal(1.0, 0.06)),
        rod_tilt_deg=float(abs(rng.normal(0, 3.0))), rod_tilt_az_deg=float(rng.uniform(0, 360)),
        servo_trim_err_deg=(float(rng.normal(0, 0.8)), float(rng.normal(0, 0.8))),
        servo_rate_dps=float(rng.uniform(300, 650)), servo_tau=float(rng.uniform(0.008, 0.03)),
        gimbal_backlash_deg=float(rng.uniform(0.1, 0.6)),
        gyro_bias_dps=tuple(float(x) for x in rng.normal(0, 1.0, 3)),
        accel_bias_mg=tuple(float(x) for x in rng.normal(0, 30, 3)),
        imu_misalign_deg=float(abs(rng.normal(0, 1.0))),
        baro_noise_pa=float(rng.uniform(0.3, 1.5)), baro_port_cp=float(rng.normal(-0.02, 0.06)),
        chute_cd=float(rng.normal(0.8, 0.12)), deploy_latch_delay=float(rng.uniform(0.1, 0.4)),
        chute_fill_time=float(rng.uniform(0.4, 1.2)), initial_roll_deg=float(rng.uniform(0, 360)),
        site_alt_asl=float(rng.uniform(0, 400)),
        payload_g=float(rng.uniform(0.0, 50.0)),
        fin_misalign_deg=tuple(float(x) for x in rng.normal(0, 0.6, 4)),
        tab_trim_err_deg=tuple(float(x) for x in rng.normal(0, 1.0, 4)),
        tab_eff_scale=float(np.clip(rng.normal(1.0, 0.3), 0.4, 1.6)),
        tab_rate_dps=float(rng.uniform(300, 650)), tab_tau=float(rng.uniform(0.008, 0.03)),
        tab_backlash_deg=float(rng.uniform(0.15, 1.0)),
    )


def run_one(i):
    from kestrel.dynamics import Simulation, SimConfig
    from kestrel.sil import SilFsw
    cfg = sample_stress(i)
    sim = Simulation(SimConfig(**cfg), SilFsw())
    ev = sim.run()
    keys = ["apogee", "max_tilt_burn", "max_tilt_coast", "max_gimbal", "rod_exit_speed", "deploy_minus_apogee_s", "deploy_speed",
            "landing_vz", "landing_dist", "final_state", "max_roll_rate_burn", "max_tab", "max_opening_g"]
    out = {k: ev.get(k) for k in keys}
    out.update(i=i, wind=cfg["wind_speed"], payload_g=cfg["payload_g"], tab_eff=cfg["tab_eff_scale"],
               misalign=cfg["thrust_misalign_deg"], mass_scale=cfg["mass_scale"], rod=cfg["rod_length"])
    return out


def ok(r):
    reasons = []
    if r["max_tilt_burn"] >= 10:
        reasons.append(f"tilt in boost {r['max_tilt_burn']:.1f} deg")
    if r["max_roll_rate_burn"] >= 60:
        reasons.append(f"roll {r['max_roll_rate_burn']:.0f} deg/s in boost")
    if r["deploy_minus_apogee_s"] is None or abs(r["deploy_minus_apogee_s"]) >= 1.5:
        reasons.append("parachute not at apogee")
    if (r["deploy_speed"] or 99) >= 15:
        reasons.append(f"deploy at {r['deploy_speed'] or 0:.1f} m/s")
    if (r["landing_vz"] or 99) >= 7:
        reasons.append(f"landing {r['landing_vz'] or 0:.1f} m/s")
    if r["final_state"] != 6:
        reasons.append("not LANDED")
    return reasons


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    from kestrel.sil import build
    build()
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        rows = list(ex.map(run_one, range(n), chunksize=4))
    fails = [(r, ok(r)) for r in rows if ok(r)]
    safe = [r for r in rows if r["deploy_minus_apogee_s"] is not None and (r["landing_vz"] or 99) < 7]
    bands = [(0, 3), (3, 6), (6, 9)]
    by_band = {}
    for lo, hi in bands:
        b = [r for r in rows if lo <= r["wind"] < hi]
        by_band[f"{lo}-{hi} m/s"] = dict(n=len(b), success=sum(1 for r in b if not ok(r)) / max(len(b), 1))
    a = np.array([r["apogee"] for r in rows])
    summary = dict(n=n, success=1 - len(fails) / n, safe_recovery=len(safe) / n, by_wind=by_band,
                   apogee=dict(mean=float(a.mean()), p5=float(np.percentile(a, 5)), p95=float(np.percentile(a, 95))),
                   max_tilt_burn_p95=float(np.percentile([r["max_tilt_burn"] for r in rows], 95)),
                   landing_dist_p95=float(np.percentile([r["landing_dist"] for r in rows], 95)),
                   failures=[dict(i=r["i"], wind=round(r["wind"], 1), tab_eff=round(r["tab_eff"], 2), misalign=round(r["misalign"], 2),
                                  why=w) for r, w in fails])
    json.dump(dict(summary=summary, runs=rows), open(os.path.join(RES, "stress_montecarlo.json"), "w"), indent=1, default=str)
    print(f"stress Monte Carlo, TSP-F35, n={n}: success {100 * summary['success']:.1f} %, "
          f"parachute out and landing < 7 m/s in {100 * summary['safe_recovery']:.1f} %")
    for k, v in by_band.items():
        print(f"   wind {k}: n={v['n']} success {100 * v['success']:.1f} %")
    print(f"   apogee mean {summary['apogee']['mean']:.1f} m (5-95 % {summary['apogee']['p5']:.0f}-{summary['apogee']['p95']:.0f}), "
          f"tilt in boost p95 {summary['max_tilt_burn_p95']:.1f} deg, landing distance p95 {summary['landing_dist_p95']:.0f} m")
    for f in summary["failures"]:
        print("   FAIL", f)
    print(f"total {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
