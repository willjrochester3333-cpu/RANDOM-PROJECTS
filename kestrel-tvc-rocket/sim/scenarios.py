#!/usr/bin/env python3
"""Deterministic scenario & fault-injection suite. Every case flies the real C++ flight core (SIL).

    python3 scenarios.py            # runs all cases in parallel, writes results/scenarios.md + .json + plots
"""
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

BASE = dict(motor="TSP-E20", wind_speed=3.0, gust_sigma=0.6, t_pad=5.0, seed=11, thrust_misalign_deg=0.3,
            thrust_misalign_az_deg=40.0, fin_cant_deg=0.2)

# (name, description, config overrides, flight-core parameter overrides, pass criteria)
CASES = [
    ("nominal_calm", "E20, no wind", dict(wind_speed=0.0, gust_sigma=0.0), {}, "normal"),
    ("nominal_wind3", "E20, 3 m/s wind + gusts (baseline)", {}, {}, "normal"),
    ("wind6_gusty", "E20, 6 m/s wind, 1.5 m/s gusts", dict(wind_speed=6.0, gust_sigma=1.5), {}, "normal"),
    ("wind9_limit", "E20, 9 m/s wind (UKRA/NAR wind limit)", dict(wind_speed=9.0, gust_sigma=2.0), {}, "normal"),
    ("rod_tilt5", "rod tilted 5 deg downwind (rocket holds the rod direction)", dict(rod_tilt_deg=5.0, rod_tilt_az_deg=90.0), {}, "normal"),
    ("misalign_1p5", "1.5 deg thrust misalignment (badly seated motor)", dict(thrust_misalign_deg=1.5), {}, "normal"),
    ("roll_spin", "2 deg fin cant -> fast roll (tests roll-lead compensation)", dict(fin_cant_deg=2.0), {}, "normal"),
    ("cg_aft_20mm", "CG 20 mm further aft than predicted", dict(cg_shift=0.020), {}, "normal"),
    ("heavy_15pct", "airframe 15% heavier than predicted", dict(mass_scale=1.15), {}, "normal"),
    ("cd_plus20", "drag 20% higher than predicted", dict(cd_scale=1.2), {}, "normal"),
    ("gains_x0.5", "controller gains halved", {}, dict(kp=55, ki=12.5, kd=8), "normal"),
    ("gains_x2", "controller gains doubled", {}, dict(kp=220, ki=50, kd=32), "normal"),
    ("slow_servos", "servos half as fast, 25 ms lag, 0.5 deg backlash", dict(servo_rate_dps=300, servo_tau=0.025, gimbal_backlash_deg=0.5), {}, "normal"),
    ("imu_misalign2", "IMU mounted 2 deg crooked", dict(imu_misalign_deg=2.0), {}, "normal"),
    ("gyro_drift", "gyro bias drifting 10x faster than spec", dict(gyro_bias_drift_dps=0.1), {}, "normal"),
    ("motor_E12", "TSP E12-0 (3.5 s long-burn TVC demo)", dict(motor="TSP-E12"), {}, "normal"),
    ("motor_D20", "TSP D20-0 (first test hop)", dict(motor="TSP-D20"), {}, "normal"),
    ("motor_EstesE12", "Estes E12-0 (if available abroad)", dict(motor="Estes-E12"), {}, "normal"),
    ("unarmed_launch", "FAULT: launched before calibration finished (1 s on the pad)", dict(t_pad=1.0), {}, "fault_safe"),
    ("tvc_off_calm", "FAULT: TVC servos dead, calm", dict(servo_failure="dead", wind_speed=0.0, gust_sigma=0.0), {}, "fault_safe"),
    ("tvc_off_wind3", "FAULT: TVC servos dead, 3 m/s wind", dict(servo_failure="dead"), {}, "fault_safe"),
    ("servo_hardover", "FAULT: pitch servo jams at full deflection at T+0.5 s", dict(servo_failure="hardover_y"), {}, "fault_contained"),
    ("baro_dead", "FAULT: barometer dies at T+1 s", dict(baro_fail_after=1.0), {}, "fault_safe"),
    ("no_chute", "FAULT: parachute fails to deploy (shows why ground tests matter)", dict(deploy_failure=True), {}, "fault_info"),
]


def run_case(case):
    from kestrel.dynamics import Simulation, SimConfig
    from kestrel.sil import SilFsw
    from kestrel.plots import flight_overview
    name, desc, over, fsw_over, crit = case
    cfg = dict(BASE)
    cfg.update(over)
    sim = Simulation(SimConfig(**cfg), SilFsw(fsw_over))
    t0 = time.time()
    ev = sim.run()
    ev["wall_s"] = time.time() - t0
    if name in ("nominal_wind3", "wind9_limit", "tvc_off_wind3", "servo_hardover", "baro_dead", "motor_E12", "unarmed_launch"):
        flight_overview(sim, os.path.join(RES, f"scenario_{name}.png"), f"{name}: {desc}")
    keep = {k: (float(v) if isinstance(v, (int, float)) and v is not None else v) for k, v in ev.items()
            if not isinstance(v, tuple)}
    keep["landing_pos"] = ev.get("landing_pos")
    return name, desc, crit, keep


def verdict(crit, ev):
    """Pass criteria (see docs/SIMULATION_REPORT.md)."""
    notes = []
    ok = True
    dep = ev.get("deploy_cmd_t") is not None
    if crit == "normal":
        if ev.get("max_tilt_burn", 99) > 10:
            ok = False; notes.append("tilt>10deg in boost")
        if not dep:
            ok = False; notes.append("no deploy")
        else:
            if abs(ev.get("deploy_minus_apogee_s", 9)) > 1.5:
                ok = False; notes.append("deploy not at apogee")
            if ev.get("deploy_speed", 99) > 15:
                ok = False; notes.append("fast deploy")
        if (ev.get("landing_vz") or 99) > 7.0:
            ok = False; notes.append("hard landing")
        if ev.get("final_state") != 6:
            ok = False; notes.append("not LANDED")
    elif crit == "fault_safe":
        if not dep:
            ok = False; notes.append("no deploy")
        if dep and ev.get("deploy_speed", 99) > 30:
            ok = False; notes.append("deploy too fast")
        if (ev.get("landing_vz") or 99) > 7.0:
            ok = False; notes.append("hard landing")
    elif crit == "fault_contained":
        # nothing can switch a solid motor off: success = abort detected, chute out, rocket kept near the pad
        if not dep:
            ok = False; notes.append("no deploy")
        if (ev.get("landing_dist") or 999) > 100 or ev.get("apogee", 999) > 60:
            ok = False; notes.append("not contained")
        notes.append("contained near pad")
    else:
        notes.append("informational")
    return ("PASS" if ok else "FAIL") if crit != "fault_info" else "INFO", ", ".join(notes)


def main():
    os.makedirs(RES, exist_ok=True)
    from kestrel.sil import build
    build()   # compile once before forking
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        results = list(ex.map(run_case, CASES))
    rows = []
    js = {}
    npass = 0
    for name, desc, crit, ev in results:
        v, notes = verdict(crit, ev)
        npass += v == "PASS"
        js[name] = dict(description=desc, verdict=v, notes=notes, events=ev)
        f = lambda k, fmt="{:.1f}": (fmt.format(ev[k]) if ev.get(k) is not None else "-")
        rows.append(f"| {name} | {desc} | {f('apogee', '{:.0f}')} | {f('max_tilt_burn')} | {f('max_gimbal')} | "
                    f"{f('deploy_minus_apogee_s', '{:+.2f}')} | {f('deploy_speed')} | {f('landing_vz')} | "
                    f"{f('landing_dist', '{:.0f}')} | **{v}** {notes} |")
    hdr = ("| case | description | apogee m | max tilt in boost ° | max gimbal ° | deploy − apogee s | "
           "speed at deploy m/s | descent rate at landing m/s | drift m | verdict |\n|---|---|---|---|---|---|---|---|---|---|\n")
    md = "# Scenario & fault-injection results (real flight code in the loop)\n\n" + hdr + "\n".join(rows) + "\n"
    with open(os.path.join(RES, "scenarios.md"), "w") as fh:
        fh.write(md)
    with open(os.path.join(RES, "scenarios.json"), "w") as fh:
        json.dump(js, fh, indent=1, default=str)
    print(md)
    print(f"{npass} PASS of {sum(1 for c in CASES if c[4] != 'fault_info')} graded cases, {time.time()-t0:.0f} s")


if __name__ == "__main__":
    main()
