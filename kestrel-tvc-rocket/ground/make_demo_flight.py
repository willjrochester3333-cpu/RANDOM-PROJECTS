#!/usr/bin/env python3
"""Make ground/demo_flight.csv: a simulated F35 flight for Mission Control's built-in demo.

Flies Monte Carlo seed 7 (the flight in the launch video: 4.9 m/s wind, 20 g payload) with the real flight code in
the loop and writes it in the exact CSV format the flight computer's `dump` command produces, at the logger's
rates thinned for a small file: 10 Hz on the pad, 50 Hz in BOOST/COAST, 10 Hz under the parachute, 5 Hz on the
ground. The flight software keeps running for 10 s after touchdown (as the simulator does), and its own state
(DESCENT, then LANDED once the rocket has been still for 5 s) is recorded, not made up. The last column (`rssi`, the
radio signal at the rocket, added in firmware 3.00) is 0 = "no radio report": the simulator does not model the
radio. Mission Control's simulated-live mode models the radio link itself, on top of this file.

    python3 ground/make_demo_flight.py
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))
import montecarlo  # noqa: E402
from kestrel.dynamics import Simulation, SimConfig  # noqa: E402
from kestrel.sil import SilFsw  # noqa: E402

LAT0, LON0 = 52.0, -1.0          # arbitrary reference point for the GPS columns (a field in England)
SEED = 7
T_PAD = 12.0                     # seconds on the pad (READY) before ignition
RATES = {2: 10.0, 3: 50.0, 4: 50.0, 5: 10.0, 6: 5.0}


class RecordingFsw(SilFsw):
    """the real flight code, plus a record of every state it reports (the simulator logs only until touchdown)"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.trace = []

    def step(self, t, *a, **k):
        out = super().step(t, *a, **k)
        self.trace.append((t, int(out.state), bool(out.deploy)))
        return out


def fw_version():
    import re
    src = open(os.path.join(ROOT, "firmware", "pico", "src", "main.cpp")).read()
    return int(re.search(r"kFwVersion\s*=\s*(\d+)", src).group(1))


def main():
    cfg = montecarlo.sample(SEED, "TSP-F35")
    cfg["t_pad"] = T_PAD
    fsw = RecordingFsw({})
    sim = Simulation(SimConfig(**cfg), fsw)
    ev = sim.run()
    L = sim.log
    t = L["t"]
    st = L["fsw_state"].astype(int)
    tr = np.array([x[0] for x in fsw.trace])
    trs = np.array([x[1] for x in fsw.trace])
    dep_t = ev.get("deploy_cmd_t")
    rows = []
    last = -1e9
    vz_prev, t_prev = 0.0, t[0]

    def emit(tt, s, x, y, z, vz, alt, vz_est, tilt, gy, gz, q, tabs, roll, p, qd, r, az):
        lat = LAT0 + y / 111320.0
        lon = LON0 + x / (111320.0 * math.cos(math.radians(LAT0)))
        deployed = dep_t is not None and tt >= dep_t
        flags = (1 if s == 3 else 0) | (2 if deployed else 0) | 4 | 8 | (32 if s in (3, 4) else 0)
        qw, qx, qy, qz = q
        if qw < 0:
            qx, qy, qz = -qx, -qy, -qz
        rows.append(f"{int(round((tt + 600.0) * 1000))},{s},{flags},{p:.2f},{qd:.2f},{r:.2f},{az:.2f},0.00,0.00,"
                    f"{alt:.2f},{vz_est:.2f},{z:.2f},{tilt:.2f},{gy:.2f},{gz:.2f},7.900,{lat:.7f},{lon:.7f},"
                    f"{int(round(95 + z))},9,{qx:.4f},{qy:.4f},{qz:.4f},"
                    f"{tabs[0]:.2f},{tabs[1]:.2f},{tabs[2]:.2f},{tabs[3]:.2f},{roll:.2f},0")

    for k in range(len(t)):
        s = int(st[k])
        if t[k] - last < 1.0 / RATES.get(s, 10.0) - 1e-6:
            continue
        dt = max(t[k] - t_prev, 1e-3)
        az = (L["vz"][k] - vz_prev) / dt + 9.81 if s in (3, 4) else 9.81
        vz_prev, t_prev, last = L["vz"][k], t[k], t[k]
        emit(t[k], s, L["x"][k], L["y"][k], L["z"][k], L["vz"][k], L["alt_est"][k], L["vz_est"][k], L["tilt"][k],
             L["gimbal_y"][k], L["gimbal_z"][k], (L["qw"][k], L["qx"][k], L["qy"][k], L["qz"][k]),
             [L[f"tab{j}"][k] for j in range(1, 5)], L["roll"][k], L["p_dps"][k], L["q_dps"][k], L["r_dps"][k], az)
    # after touchdown: the rocket lies on its side at the landing point; the states are the flight code's own
    x0, y0 = L["x"][-1], L["y"][-1]
    q_side = (math.cos(math.radians(45)), 0.0, 0.0, math.sin(math.radians(45)))   # body x horizontal
    t_land = t[-1]
    tt = t_land + 0.2
    while tt <= tr[-1]:
        i = int(np.searchsorted(tr, tt))
        s = int(trs[min(i, len(trs) - 1)])
        emit(tt, s, x0, y0, 0.0, 0.0, 0.0, 0.0, 90.0, 0.0, 0.0, q_side, [0, 0, 0, 0], L["roll"][-1], 0, 0, 0, 9.81)
        tt += 1.0 / RATES.get(s, 5.0)
    out = os.path.join(HERE, "demo_flight.csv")
    with open(out, "w") as fh:
        fh.write("t_ms,state,flags,gx_dps,gy_dps,gz_dps,ax,ay,az,alt_m,vz_ms,baro_alt_m,tilt_deg,gimbal_y,gimbal_z,"
                 "vbat,lat,lon,gps_alt,sats,qx,qy,qz,tab1,tab2,tab3,tab4,roll_deg,rssi\n")
        fh.write(f"# session: fw {fw_version()} flight 1 motor {cfg['motor']} (SIMULATED - ground/make_demo_flight.py, "
                 f"seed {SEED}, wind {cfg['wind_speed']:.1f} m/s, payload {cfg['payload_g']:.0f} g)\n")
        fh.write("\n".join(rows) + "\n")
        fh.write(f"# end: {len(rows)} records, 0 failed CRC\n")
    print(f"apogee {ev['apogee']:.1f} m, landed {ev.get('landing_dist', float('nan')):.0f} m from the pad, "
          f"final state {ev.get('landed_detect_state')}, {len(rows)} rows -> {out} ({os.path.getsize(out) / 1000:.0f} kB)")


if __name__ == "__main__":
    main()
