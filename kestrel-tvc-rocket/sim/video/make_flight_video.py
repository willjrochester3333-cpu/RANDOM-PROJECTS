#!/usr/bin/env python3
"""KESTREL-2 launch video from a simulated flight (the real flight code in the loop).

    python3 sim/video/make_flight_video.py --seed 7            # every seed is a different flight
    python3 sim/video/make_flight_video.py --seed 7 --draft    # quick low-quality preview

1. flies one randomised flight in the 6-DOF simulator (same dispersions as the Monte Carlo: wind, gusts,
   motor, mass, drag, payload 0-50 g, sensor errors ...) with the C++ flight core (SIL);
2. renders it in Blender from two cameras: a tracking camera on the ground and the rocket's own downward
   camera (in the camera pod, exactly where the CAD puts it);
3. adds the live telemetry (bottom left) and live graphs (bottom right) and encodes an MP4 with ffmpeg.
Output: sim/results/video/kestrel2_flight_seed<N>.mp4 (+ a poster frame PNG).
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(HERE)
ROOT = os.path.dirname(SIM)
sys.path.insert(0, SIM)

from kestrel.dynamics import Simulation, SimConfig, q_mul, q_to_R, q_from_axis_angle  # noqa: E402
from kestrel.sil import SilFsw, build  # noqa: E402
import montecarlo  # noqa: E402

STATE_NAMES = ["BOOT", "CALIBRATING", "READY", "BOOST", "COAST", "DESCENT", "LANDED", "ERROR"]


def fly(seed):
    cfg = montecarlo.sample(seed, "TSP-F35")
    cfg["t_pad"] = 6.0
    cfg["log_every"] = 2
    sim = Simulation(SimConfig(**cfg), SilFsw({}))
    ev = sim.run()
    return sim, ev, cfg


def hanging_q(t_since, seed):
    """attitude under the parachute: rocket hangs from its top, tilted ~12 deg, swinging and turning slowly"""
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 2 * math.pi)
    tilt = math.radians(12.0 + 5.0 * math.sin(2 * math.pi * t_since / 2.3 + ph))
    az = math.radians(25.0 * t_since + math.degrees(ph))
    axis = np.array([math.cos(az + math.pi / 2), math.sin(az + math.pi / 2), 0.0])
    up = q_from_axis_angle([0, 1, 0], -math.pi / 2)             # body x (+axis) -> world +z
    return q_mul(q_from_axis_angle(axis, tilt), up)


def slerp(q0, q1, f):
    q0 = np.asarray(q0, float); q1 = np.asarray(q1, float)
    d = float(np.dot(q0, q1))
    if d < 0:
        q1, d = -q1, -d
    if d > 0.9995:
        q = q0 + f * (q1 - q0)
        return q / np.linalg.norm(q)
    th = math.acos(d)
    return (math.sin((1 - f) * th) * q0 + math.sin(f * th) * q1) / math.sin(th)


def frames_from_sim(sim, ev, cfg, fps, seed):
    L = sim.log
    t = L["t"]
    t0 = -3.0
    t_land = ev.get("landing_t") or t[-1]
    t_end = t_land + 3.0
    times = np.arange(t0, t_end, 1.0 / fps)
    rk = sim.rocket
    z_cg_above_tail = rk.z_tail - rk.mass_props(rk.motor.burn_time + 1).z_cg
    t_sep = None
    if ev.get("deploy_cmd_t") is not None:
        t_sep = ev["deploy_cmd_t"] + sim.cfg.deploy_latch_delay
    fill = sim.cfg.chute_fill_time
    sep_time = sim.cfg.deploy_sep_time
    out = []
    v_land = np.array([L["vx"][-1], L["vy"][-1], L["vz"][-1]])
    p_land = np.array([L["x"][-1], L["y"][-1], L["z"][-1]])
    q_sep = None
    for tf in times:
        i = int(np.clip(np.searchsorted(t, tf), 0, len(t) - 1))
        if tf <= t[-1]:
            pos = np.array([np.interp(tf, t, L[k]) for k in ("x", "y", "z")])
            vel = np.array([np.interp(tf, t, L[k]) for k in ("vx", "vy", "vz")])
        else:                                                      # after the simulator's landing: finish the drop
            dtl = tf - t[-1]
            drop = min(dtl * abs(v_land[2]), 0.7)
            pos = p_land + np.array([0.0, 0.0, -drop])
            vel = np.zeros(3) if drop >= 0.7 else v_land
        q = np.array([L["qw"][i], L["qx"][i], L["qy"][i], L["qz"][i]])
        state = int(L["fsw_state"][i]) if tf <= t[-1] else 6
        sep = t_sep is not None and tf >= t_sep
        chute = 0.0
        if sep:
            if q_sep is None:
                q_sep = q.copy()
            ts = tf - t_sep
            chute = float(np.clip((ts - sep_time) / fill, 0.0, 1.0))
            q = slerp(q_sep, hanging_q(ts, seed), float(np.clip(ts / 1.6, 0, 1)))
            if tf > t_land:                                       # lying down on the grass after landing
                f = float(np.clip((tf - t_land - 0.2) / 0.8, 0, 1))
                q = slerp(q, q_mul(q_from_axis_angle([1, 0, 0], math.radians(84)), q_from_axis_angle([0, 1, 0], -math.pi / 2)), f)
        out.append(dict(
            t=round(float(tf), 4), x=float(pos[0]), y=float(pos[1]), z=float(pos[2]),
            q=[float(v) for v in q], speed=float(np.linalg.norm(vel)), vz=float(vel[2]),
            tilt=float(np.interp(tf, t, L["tilt"])), roll=float(np.interp(tf, t, L["roll"])),
            p=float(np.interp(tf, t, L["p_dps"])), qrate=float(np.interp(tf, t, L["q_dps"])), r=float(np.interp(tf, t, L["r_dps"])),
            gy=float(np.interp(tf, t, L["gimbal_y"])), gz=float(np.interp(tf, t, L["gimbal_z"])),
            tabs=[float(np.interp(tf, t, L[f"tab{k}"])) for k in range(1, 5)],
            thrust=float(rk.motor.thrust(tf)) if tf >= 0 else 0.0, mass=float(np.interp(tf, t, L["mass"])),
            qdyn=float(np.interp(tf, t, L["qdyn"])), alt_est=float(np.interp(tf, t, L["alt_est"])),
            vz_est=float(np.interp(tf, t, L["vz_est"])), state=state, sep=bool(sep), chute=chute,
        ))
    # acceleration from the velocity history (g)
    sp = np.array([[f["x"], f["y"], f["z"]] for f in out])
    vv = np.gradient(sp, 1.0 / fps, axis=0)
    aa = np.gradient(vv, 1.0 / fps, axis=0)
    for f, a in zip(out, aa):
        f["accel_g"] = float(np.linalg.norm(a + np.array([0, 0, 9.81])) / 9.81)
    meta = dict(seed=seed, fps=fps, motor=cfg["motor"], wind=cfg["wind_speed"], wind_to=cfg["wind_toward_deg"],
                gust=cfg["gust_sigma"], payload_g=cfg["payload_g"], z_cg_above_tail_mm=1000 * z_cg_above_tail,
                events={k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in ev.items()
                        if isinstance(v, (int, float, np.floating)) or v is None},
                burn_time=rk.motor.burn_time, t_sep=t_sep)
    return dict(meta=meta, frames=out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--draft", action="store_true", help="fast preview: 640x360 views, 4 samples, 15 fps")
    ap.add_argument("--skip-render", action="store_true", help="reuse rendered views (re-compose only)")
    a = ap.parse_args()
    fps = 15 if a.draft else a.fps
    out_dir = os.path.join(SIM, "results", "video", f"seed{a.seed}")
    os.makedirs(out_dir, exist_ok=True)
    build()
    t0 = time.time()
    sim, ev, cfg = fly(a.seed)
    traj = frames_from_sim(sim, ev, cfg, fps, a.seed)
    tp = os.path.join(out_dir, "traj.json")
    json.dump(traj, open(tp, "w"))
    print(f"flight seed {a.seed}: apogee {ev['apogee']:.1f} m, wind {cfg['wind_speed']:.1f} m/s, payload {cfg['payload_g']:.0f} g, "
          f"{len(traj['frames'])} frames ({time.time() - t0:.0f} s)")
    if not a.skip_render:
        procs = []
        for cam in ("ground", "onboard"):
            cmd = [os.environ.get("BLENDER", "blender"),            # BLENDER=/path/to/blender if not on PATH
                   "-b", "-P", os.path.join(HERE, "blender_scene.py"), "--", "--traj", tp, "--camera", cam,
                   "--out", os.path.join(out_dir, cam)]
            if a.draft:
                cmd.append("--draft")
            log = open(os.path.join(out_dir, f"blender_{cam}.log"), "w")
            procs.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT))
        for p in procs:
            p.wait()
            if p.returncode:
                raise SystemExit(f"blender failed, see {out_dir}/blender_*.log")
        print(f"views rendered ({time.time() - t0:.0f} s)")
    from compose import compose_video
    mp4 = compose_video(traj, out_dir, os.path.join(SIM, "results", "video", f"kestrel2_flight_seed{a.seed}.mp4"), draft=a.draft)
    print(f"wrote {mp4} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
