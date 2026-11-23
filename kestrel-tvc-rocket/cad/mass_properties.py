#!/usr/bin/env python3
"""Turn the CAD export (cad/stl/parts.json: volume, area, assembly centroid) into printed-part masses and
positions for the flight simulator. Writes cad/mass_properties.json.

Printed mass model: perimeters (wall_mm) at 100% + infill fraction of the remaining core, PETG/PLA ~1.25 g/cm^3.
Per-part print settings below match the print notes in the build guide."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
D = json.load(open(os.path.join(ROOT, "design.json")))
Z_TIP = json.load(open(os.path.join(HERE, "component_positions.json")))["_z_tip_above_tail_mm"]   # written by kestrel_cad.py

SETTINGS = {  # (wall mm, infill fraction) - match the print notes in the build guide
    "nose_cone": (1.2, 0.10), "avbay_coupler": (1.6, 0.25), "tvc_frame": (1.2, 0.25), "fin_can": (1.2, 0.20),
    "tvc_motor_holder": (1.6, 0.30), "tvc_gimbal_ring": (1.2, 0.40), "tvc_motor_retainer": (1.2, 0.40),
    "payload_wall": (1.2, 0.25), "top_latch_insert": (1.2, 0.25), "fin_control_tab": (1.2, 0.20),
    "tvc_motor_adapter_24mm": (1.2, 0.30), "tvc_motor_retainer_24mm": (1.2, 0.40), "tvc_motor_spacer_D": (1.2, 0.30),
    "default": (1.2, 0.20),
}
# parts flown only with some motors: the simulator adds them when the loaded motor matches
ONLY_WITH = {
    "tvc_motor_retainer": dict(motor_d=29.0),                         # the F35's retainer
    "tvc_motor_adapter_24mm": dict(motor_d=24.0),                     # 24 mm motors: sleeve + their own retainer
    "tvc_motor_retainer_24mm": dict(motor_d=24.0),
    "tvc_motor_spacer_D": dict(motor_d=24.0, motor_len=70.0),         # 70 mm D motors only
}
RHO = 1.25  # g/cm^3


def main():
    parts = json.load(open(os.path.join(HERE, "stl", "parts.json")))
    out = []
    for p in parts:
        if p["group"] not in ("rocket", "adapter"):
            continue
        wall, infill = SETTINGS.get(p["name"], SETTINGS["default"])
        vol = p["volume_mm3"] / 1000.0
        shell = min(vol, p["area_mm2"] / 100.0 * wall / 10.0 * 0.5 * 2)   # area x wall (cm^3)
        core = max(vol - shell, 0.0)
        mass = RHO * (shell + infill * core) * p["qty"]
        zc = p["centroid_assembly_mm"][2]
        q = dict(name=p["name"], mass_g=round(mass, 1), z=round(Z_TIP - zc, 1), length=0.0,
                 radius=round(p["r_gyr_mm"], 1), source="CAD")
        if p["name"] in ONLY_WITH:
            q["only_with"] = ONLY_WITH[p["name"]]
        out.append(q)
    json.dump(out, open(os.path.join(HERE, "mass_properties.json"), "w"), indent=1)
    for o in out:
        tag = f"  (only with {o['only_with']})" if "only_with" in o else ""
        print(f"{o['name']:24s} {o['mass_g']:6.1f} g  z={o['z']:6.0f} mm from nose tip{tag}")
    for d_mm in (29.0, 24.0):
        tot = sum(o["mass_g"] for o in out if "only_with" not in o or (o["only_with"]["motor_d"] == d_mm
                                                                       and "motor_len" not in o["only_with"]))
        print(f"total printed rocket parts flown with a {d_mm:.0f} mm motor: {tot:.0f} g")


if __name__ == "__main__":
    main()
