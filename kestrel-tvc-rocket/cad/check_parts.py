#!/usr/bin/env python3
"""Printability / sanity checks for every exported STL.

* watertight & consistently wound (a valid solid for the slicer)
* positive volume, single body
* fits a 220 x 220 x 250 mm bed (Ender-3 / Prusa MK-class)
* estimated printed mass (PLA/PETG ~1.24-1.27 g/cm^3 with walls + infill)
* thinnest-wall probe via ray casting
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
        if not p["name"].startswith(("pad_", "rod_tip", "tool_")):
            total_rocket += 0 if np.isnan(mass) else mass
        ok = ok_w and ok_v and fits and len(bodies) == 1
        fails += not ok
        rows.append(f"| {p['name']} | {p['qty']} | {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} | {m.volume/1000:.1f} | "
                    f"{mass:.1f} | {wall:.2f} | {'yes' if ok_w else 'NO'} | {len(bodies)} | {'yes' if fits else 'NO'} | "
                    f"{'PASS' if ok else 'FAIL'} |")
    md = ("| part | qty | size mm | solid cm³ | est. printed g | thinnest wall mm (2nd pct) | watertight | bodies | fits 220x220x250 | result |\n"
          "|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(rows) +
          f"\n\nEstimated printed rocket parts total: **{total_rocket:.0f} g** (walls 1.2 mm + 20% infill assumption)\n")
    open(os.path.join(STL, "check_report.md"), "w").write(md)
    print(md)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
