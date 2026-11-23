#!/usr/bin/env python3
"""Fly the baseline case (F35, 3 m/s wind) with the real flight code (SIL) and write the result in the exact CSV
format the flight computer's `dump` command produces -> firmware/tools/example_flight_sim.csv.
Lets you try firmware/tools/kestrel_link.py (summary / plot) before you have a real flight.
GPS positions are offsets from an arbitrary reference point (52.0 N, 1.0 W)."""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scenarios import BASE  # noqa: E402
from kestrel.dynamics import Simulation, SimConfig  # noqa: E402
from kestrel.sil import SilFsw  # noqa: E402

LAT0, LON0 = 52.0, -1.0


def fw_version():
    """the firmware version the Pico app writes into its log sessions (kFwVersion in main.cpp)"""
    import re
    src = open(os.path.join(HERE, "..", "firmware", "pico", "src", "main.cpp")).read()
    return int(re.search(r"kFwVersion\s*=\s*(\d+)", src).group(1))


def main():
    sim = Simulation(SimConfig(**BASE), SilFsw({}))
    ev = sim.run()
    L = sim.log
    out = os.path.join(HERE, "..", "firmware", "tools", "example_flight_sim.csv")
    t = L["t"]
    st = L["fsw_state"].astype(int)
    i_launch = int(np.argmax(st == 3))
    t_launch = t[i_launch]
    last_t = -1e9
    rows = 0
    with open(out, "w") as fh:
        fh.write("t_ms,state,flags,gx_dps,gy_dps,gz_dps,ax,ay,az,alt_m,vz_ms,baro_alt_m,tilt_deg,gimbal_y,gimbal_z,"
                 "vbat,lat,lon,gps_alt,sats,qx,qy,qz,tab1,tab2,tab3,tab4,roll_deg\n")
        fh.write(f"# session: fw {fw_version()} flight 1 motor {BASE['motor']} (SIMULATED - sim/make_example_log.py)\n")
        vz_prev, t_prev = 0.0, t[0]
        for k in range(len(t)):
            s = st[k]
            rate = {3: 100.0, 4: 100.0, 5: 25.0, 6: 2.0}.get(s, 2.0)     # decimated for a small example file
            if t[k] - last_t < 1.0 / rate - 1e-6:
                continue
            dt = max(t[k] - t_prev, 1e-3)
            az = (L["vz"][k] - vz_prev) / dt + 9.81 if s in (3, 4) else 9.81
            vz_prev, t_prev = L["vz"][k], t[k]
            last_t = t[k]
            flags = (1 if s == 3 else 0) | (2 if s >= 5 else 0) | 4 | 8 | (32 if s in (3, 4) else 0)
            lat = LAT0 + L["y"][k] / 111320.0
            lon = LON0 + L["x"][k] / (111320.0 * math.cos(math.radians(LAT0)))
            fh.write(f"{int(round((t[k] - t_launch + 60.0) * 1000))},{s},{flags},{L['p_dps'][k]:.2f},{L['q_dps'][k]:.2f},"
                     f"{L['r_dps'][k]:.2f},{az:.2f},0.00,0.00,{L['alt_est'][k]:.2f},{L['vz_est'][k]:.2f},{L['z'][k]:.2f},"
                     f"{L['tilt'][k]:.2f},{L['gimbal_y'][k]:.2f},{L['gimbal_z'][k]:.2f},7.900,{lat:.7f},{lon:.7f},"
                     f"{int(95 + L['z'][k])},9,{L['qx'][k]:.4f},{L['qy'][k]:.4f},{L['qz'][k]:.4f},"
                     f"{L['tab1'][k]:.2f},{L['tab2'][k]:.2f},{L['tab3'][k]:.2f},{L['tab4'][k]:.2f},{L['roll'][k]:.2f}\n")
            rows += 1
        fh.write(f"# end: {rows} records, 0 failed CRC\n")
    print(f"apogee {ev['apogee']:.1f} m, wrote {rows} rows -> {os.path.relpath(out)}")


if __name__ == "__main__":
    main()
