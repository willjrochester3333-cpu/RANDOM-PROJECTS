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
            thrust_misalign_az_deg=40.0, fin_cant_deg=0.3)

# (name, description, config overrides, flight-core parameter overrides, pass criteria)
CASES = [
    ("nominal_calm", "E20, no wind", dict(wind_speed=0.0, gust_sigma=0.0), {}, "normal"),
    ("nominal_wind3", "E20, 3 m/s wind + gusts (baseline)", {}, {}, "normal"),
    ("wind6_gusty", "E20, 6 m/s wind, 1.5 m/s gusts", dict(wind_speed=6.0, gust_sigma=1.5), {}, "normal"),
    ("wind9_limit", "E20, 9 m/s wind (UKRA/NAR wind limit)", dict(wind_speed=9.0, gust_sigma=2.0), {}, "normal"),
    ("rod_tilt5", "rod tilted 5 deg downwind (rocket holds the rod direction)", dict(rod_tilt_deg=5.0, rod_tilt_az_deg=90.0), {}, "normal"),
    ("misalign_1p5", "1.5 deg thrust misalignment (badly seated motor)", dict(thrust_misalign_deg=1.5), {}, "normal"),
    ("fin_cant2", "2 deg fin cant: strong roll torque the tabs must cancel", dict(fin_cant_deg=2.0), {}, "normal"),
    ("fin_misalign", "fins glued crooked: +1.0 / -0.5 / +0.8 / -0.2 deg", dict(fin_misalign_deg=(1.0, -0.5, 0.8, -0.2)), {}, "normal"),
    ("cg_aft_20mm", "CG 20 mm further aft than predicted", dict(cg_shift=0.020), {}, "normal"),
    ("heavy_15pct", "airframe 15% heavier than predicted", dict(mass_scale=1.15), {}, "normal"),
    ("cd_plus20", "drag 20% higher than predicted", dict(cd_scale=1.2), {}, "normal"),
    ("payload_0g", "empty payload bay", dict(payload_g=0.0), {}, "normal"),
    ("payload_50g", "maximum payload 50 g", dict(payload_g=50.0), {}, "normal"),
    ("tvc_gains_x0.5", "TVC gains halved", {}, dict(kp=55, ki=12.5, kd=8), "normal"),
    ("tvc_gains_x2", "TVC gains doubled", {}, dict(kp=220, ki=50, kd=32), "normal"),
    ("tab_gains_x0.5", "tab (roll + coast) gains halved", {}, dict(roll_kp=45, roll_kd=7, coast_kp=22.5, coast_kd=4.5), "normal"),
    ("tab_gains_x2", "tab (roll + coast) gains doubled", {}, dict(roll_kp=180, roll_kd=28, coast_kp=90, coast_kd=18), "normal"),
    ("tab_eff_minus40", "tabs 40% less effective than predicted", dict(tab_eff_scale=0.6), {}, "normal"),
    ("tab_eff_plus40", "tabs 40% more effective than predicted", dict(tab_eff_scale=1.4), {}, "normal"),
    ("slow_servos", "all servos half speed, 25 ms lag, extra backlash", dict(servo_rate_dps=300, servo_tau=0.025, gimbal_backlash_deg=0.5,
                                                                            tab_rate_dps=300, tab_tau=0.025, tab_backlash_deg=0.8), {}, "normal"),
    ("imu_misalign2", "IMU mounted 2 deg crooked", dict(imu_misalign_deg=2.0), {}, "normal"),
    ("gyro_drift", "gyro bias drifting 10x faster than spec", dict(gyro_bias_drift_dps=0.1), {}, "normal"),
    ("roll_program", "camera panorama: 90 deg/s roll programme in the coast", {}, dict(roll_program_dps=90), "normal_noroll"),
    ("coast_rate_only", "tabs only damp pitch/yaw in the coast (no attitude hold)", {}, dict(coast_hold_attitude=0), "normal"),
    ("tabs_disabled", "tabs switched off in the settings (TVC only, like KESTREL-1)", {}, dict(fins_enabled=0), "normal_noroll"),
    ("motor_D20", "TSP D20-0 (first test hop)", dict(motor="TSP-D20"), {}, "normal"),
    ("unarmed_launch", "FAULT: launched before calibration finished (1 s on the pad)", dict(t_pad=1.0), {}, "fault_safe"),
    ("tvc_off_calm", "FAULT: TVC servos dead, calm", dict(servo_failure="dead", wind_speed=0.0, gust_sigma=0.0), {}, "fault_safe"),
    ("tvc_off_wind3", "FAULT: TVC servos dead, 3 m/s wind (tabs still steer)", dict(servo_failure="dead"), {}, "fault_safe"),
    ("servo_hardover", "FAULT: TVC pitch servo jams at full deflection at T+0.5 s", dict(servo_failure="hardover_y"), {}, "fault_contained"),
    ("tab_hardover", "FAULT: tab 1 jams at full deflection at T+1 s", dict(tab_failure="hardover1", tab_failure_t=1.0), {}, "fault_safe"),
    ("tab_stuck", "FAULT: tab 2 freezes at T+0.5 s", dict(tab_failure="stuck2", tab_failure_t=0.5), {}, "fault_safe"),
    ("tabs_dead", "FAULT: all four tab servos dead from launch", dict(tab_failure="dead", tab_failure_t=0.0), {}, "fault_safe"),
    ("baro_dead", "FAULT: barometer dies at T+1 s", dict(baro_fail_after=1.0), {}, "fault_safe"),
    ("no_chute", "FAULT: parachute fails to deploy (shows why ground tests matter)", dict(deploy_failure=True), {}, "fault_info"),
    ("motor_E12", "TSP E12-0: NOT for KESTREL-2 (too little thrust for its mass)", dict(motor="TSP-E12"), {}, "fault_info"),
]

PLOTS = ("nominal_wind3", "wind9_limit", "fin_cant2", "tabs_disabled", "roll_program", "tvc_off_wind3", "servo_hardover",
         "tab_hardover", "baro_dead", "payload_50g", "unarmed_launch")


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
    if name in PLOTS:
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
    if crit in ("normal", "normal_noroll"):
        if crit == "normal" and ev.get("max_roll_rate_burn", 999) > 60:
            ok = False; notes.append("roll not held in boost")
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
        rows.append(f"| {name} | {desc} | {f('apogee', '{:.0f}')} | {f('max_tilt_burn')} | {f('max_tilt_coast')} | {f('max_gimbal')} | "
                    f"{f('max_roll_rate_burn', '{:.0f}')} / {f('max_roll_rate_coast', '{:.0f}')} | {f('max_tab')} | "
                    f"{f('deploy_minus_apogee_s', '{:+.2f}')} | {f('deploy_speed')} | {f('landing_vz')} | "
                    f"{f('landing_dist', '{:.0f}')} | **{v}** {notes} |")
    hdr = ("| case | description | apogee m | max tilt boost ° | max tilt coast ° | max gimbal ° | roll rate boost / coast °/s | "
           "max tab ° | deploy − apogee s | speed at deploy m/s | landing m/s | drift m | verdict |\n"
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    md = "# Scenario & fault-injection results (real flight code in the loop)\n\n" + hdr + "\n".join(rows) + "\n"
    with open(os.path.join(RES, "scenarios.md"), "w") as fh:
        fh.write(md)
    with open(os.path.join(RES, "scenarios.json"), "w") as fh:
        json.dump(js, fh, indent=1, default=str)
    print(md)
    print(f"{npass} PASS of {sum(1 for c in CASES if c[4] != 'fault_info')} graded cases, {time.time()-t0:.0f} s")


if __name__ == "__main__":
    main()
