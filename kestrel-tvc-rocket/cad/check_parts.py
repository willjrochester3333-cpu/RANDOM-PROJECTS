#!/usr/bin/env python3
"""Printability / sanity checks for every exported STL.

* watertight & consistently wound (a valid solid for the slicer)
* positive volume, single body
* fits a 220 x 220 x 250 mm bed (Ender-3 / Prusa MK-class)
* estimated printed mass (PLA/PETG ~1.24-1.27 g/cm^3 with walls + infill)
* thinnest-wall probe via ray casting
* overhangs in the exported print orientation: downward faces steeper than 45 deg that are not on the bed. Parts
  that need support material must say so in SUPPORTS; every other part may only have small overhangs and bridges
  (largest single overhang region below MAX_UNSUPPORTED_MM2)
Writes cad/stl/check_report.md and returns non-zero if any check fails.
"""
import json
import os
import sys

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
STL = os.path.join(HERE, "stl")
BED = (220.0, 220.0, 250.0)
# parts printed WITH support material, and where it goes (must match the build guide)
SUPPORTS = {
    "tvc_frame": "under the four servo bars",
    "tvc_motor_holder": "under the pushrod tab",
    "pad_hub": "tree supports in the leg sockets",
}
# parts whose larger flat overhangs are bridges (supported on both sides), reviewed by hand
BRIDGES = {
    "fin_can": "printed upside down: lead-channel floors bridge 9 mm and servo-pocket floors 12.6 mm between the fin skins",
    "camera_pod": "camera-pocket roof bridges 23.6 mm between its side walls",
    "fin_leg": "printed sleeve-rim down: the pocket roof bridges 12.6 mm between the sleeve's side walls",
}
MAX_UNSUPPORTED_MM2 = 120.0   # flat downward region allowed without supports (bridges such as window tops are longer but narrow)


def overhang(m, z_tol=0.25):
    """area of downward faces steeper than 45 deg (not on the bed) and the largest connected flat (> 60 deg) region"""
    z0 = m.bounds[0][2]
    n, a, c = m.face_normals, m.area_faces, m.triangles_center
    on_bed = (c[:, 2] - z0 < z_tol) & (n[:, 2] < -0.999)
    ov45 = (n[:, 2] < -np.cos(np.radians(45.0))) & ~on_bed
    flat = (n[:, 2] < -np.cos(np.radians(30.0))) & ~on_bed
    largest = 0.0
    if flat.any():
        idx = np.nonzero(flat)[0]
        sub = m.submesh([idx], append=True)
        for piece in sub.split(only_watertight=False):
            largest = max(largest, float(piece.area))
    return float(a[ov45].sum()), largest


def wall_probe(m, n=4000, seed=0):
    """Sample surface points, cast a ray inward along -normal, report the 2nd-percentile thickness."""
    rng = np.random.default_rng(seed)
    pts, fi = trimesh.sample.sample_surface(m, n, seed=int(rng.integers(1 << 30)))
    nrm = m.face_normals[fi]
    origins = pts - nrm * 1e-3
    locs, idx_ray, _ = m.ray.intersects_location(origins, -nrm, multiple_hits=False)
    if len(locs) == 0:
        return float("nan")
    d = np.linalg.norm(locs - origins[idx_ray], axis=1)
    d = d[d > 1e-3]
    return float(np.percentile(d, 2)) if len(d) else float("nan")


def effective_density(volume_cm3, area_cm2, wall_mm=1.2, infill=0.2, rho=1.25):
    shell = min(volume_cm3, area_cm2 * wall_mm / 10.0)
    core = max(volume_cm3 - shell, 0.0)
    return rho * (shell + infill * core)


def main():
    parts = json.load(open(os.path.join(STL, "parts.json")))
    rows, fails = [], 0
    total_rocket = 0.0
    for p in parts:
        f = os.path.join(STL, p["name"] + ".stl")
        m = trimesh.load(f, force="mesh")
        ext = m.bounding_box.extents
        bodies = m.split(only_watertight=False)
        ok_w = bool(m.is_watertight)
        ok_v = bool(m.is_volume) and m.volume > 0
        fits = all(sorted(ext)[i] <= sorted(BED)[i] for i in range(3))
        wall = wall_probe(m) if ok_w else float("nan")
        mass = effective_density(m.volume / 1000.0, m.area / 100.0) * p["qty"] if ok_v else float("nan")
        if p.get("group", "rocket") == "rocket":            # pad, build tools and the 24 mm adapter set left out
            total_rocket += 0 if np.isnan(mass) else mass
        ov_area, ov_largest = overhang(m) if ok_w else (float("nan"), float("nan"))
        sup = SUPPORTS.get(p["name"], "")
        ok_ov = bool(sup) or p["name"] in BRIDGES or ov_largest <= MAX_UNSUPPORTED_MM2
        if not sup and p["name"] in BRIDGES:
            sup = "none (" + BRIDGES[p["name"]] + ")"
        ok = ok_w and ok_v and fits and len(bodies) == 1 and ok_ov
        fails += not ok
        rows.append(f"| {p['name']} | {p['qty']} | {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} | {m.volume/1000:.1f} | "
                    f"{mass:.1f} | {wall:.2f} | {'yes' if ok_w else 'NO'} | {len(bodies)} | {'yes' if fits else 'NO'} | "
                    f"{ov_area:.0f} / {ov_largest:.0f} | {sup or 'none'} | {'PASS' if ok else 'FAIL'} |")
    md = ("| part | qty | size mm | solid cm³ | est. printed g | thinnest wall mm (2nd pct) | watertight | bodies | fits 220x220x250 | "
          "overhang mm² (>45°) / largest flat region | supports | result |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(rows) +
          f"\n\nEstimated printed rocket parts total: **{total_rocket:.0f} g** as flown with the F35 (walls 1.2 mm + 20% infill "
          f"assumption; the 24 mm adapter set, launch pad and build tools not included)\n\n"
          f"Overhangs are measured in the exported print orientation. A part without listed supports passes only if no flat "
          f"downward region is larger than {MAX_UNSUPPORTED_MM2:.0f} mm² apart from narrow bridges; see the table for the parts "
          f"that are printed with support material.\n")
    open(os.path.join(STL, "check_report.md"), "w").write(md)
    print(md)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
