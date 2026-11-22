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
    "default": (1.2, 0.20),
}
RHO = 1.25  # g/cm^3


def main():
    parts = json.load(open(os.path.join(HERE, "stl", "parts.json")))
    out = []
    for p in parts:
        if p["group"] != "rocket":
            continue
        wall, infill = SETTINGS.get(p["name"], SETTINGS["default"])
        vol = p["volume_mm3"] / 1000.0
        shell = min(vol, p["area_mm2"] / 100.0 * wall / 10.0 * 0.5 * 2)   # area x wall (cm^3)
        core = max(vol - shell, 0.0)
        mass = RHO * (shell + infill * core) * p["qty"]
        zc = p["centroid_assembly_mm"][2]
        out.append(dict(name=p["name"], mass_g=round(mass, 1), z=round(Z_TIP - zc, 1), length=0.0,
                        radius=round(p["r_gyr_mm"], 1), source="CAD"))
    json.dump(out, open(os.path.join(HERE, "mass_properties.json"), "w"), indent=1)
    tot = sum(o["mass_g"] for o in out)
    for o in out:
        print(f"{o['name']:22s} {o['mass_g']:6.1f} g  z={o['z']:6.0f} mm from nose tip")
    print(f"total printed rocket parts: {tot:.0f} g")


if __name__ == "__main__":
    main()
