"""Make the JLCPCB order package for KESTREL FC: gerbers + drill (zipped), BOM and CPL (pick & place).

Run with the system Python that ships pcbnew (KiCad 7):
    /usr/bin/python3 jlc_fab.py
Output goes to pcb/production/.

CPL notes
* JLCPCB's assembly library draws some packages rotated relative to KiCad's footprints.  The
  corrections below are the community-maintained values used by the KiCad JLCPCB plugins
  (matthewlai/JLCKicadTools cpl_rotations_db.csv, the default table of Bouni/kicad-jlcpcb-tools).
* "Mid X / Mid Y" is the centre of the pads' bounding box, which is the part body centre for every
  footprint used here (KiCad anchors pin headers / sockets / JST XH on pin 1, not the centre).
* Parts with no community rule (LGA sensors, GPS module, U.FL, PCM12, JST-SH) go in as KiCad
  rotation + 0.  JLCPCB shows every part on its placement preview before you pay and their DFM
  engineers check polarity, but you should still glance at pin 1 of U4/U5/U7/J7 there (see
  docs/BUILD_GUIDE.md -> "Ordering the PCB").
"""
import csv
import os
import re
import shutil
import subprocess
import sys
import zipfile
from collections import OrderedDict

import pcbnew

import circuit as C

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "kestrel_fc.kicad_pcb")
OUT = os.path.join(HERE, "production")
OX, OY = 100.0, 100.0

# (regex on footprint name, rotation correction in degrees) -- first match wins
ROTATION_RULES = [
    (r"^TSOT-23", 180),
    (r"^SOT-23", -90),
    (r"^SOIC-", 270),
]
REVIEW = {"U4": "LSM6DSO LGA-14: pin-1 dot must sit at the chamfered silkscreen corner",
          "U5": "BMP580 LGA-10: pin-1 dot must sit at the silkscreen dot",
          "U7": "ATGM336H: pin 1 (GND) corner, module label upright when the U.FL is at the top",
          "J7": "Qwiic JST-SH: cable entry must face the board edge",
          "U2": "TPS563201: pin 1 dot next to the silkscreen dot (community rule 180 deg applied)",
          "U3": "TPS563201: pin 1 dot next to the silkscreen dot (community rule 180 deg applied)"}

GERBER_LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"


def env():
    e = dict(os.environ)
    e.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
    e.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
    e.setdefault("KICAD7_3DMODEL_DIR", "/usr/share/kicad/3dmodels")
    return e


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env())
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit("command failed: " + " ".join(cmd))
    return r.stdout


def export_gerbers(gdir):
    if os.path.isdir(gdir):
        shutil.rmtree(gdir)
    os.makedirs(gdir)
    run(["kicad-cli", "pcb", "export", "gerbers", "--layers", GERBER_LAYERS, "--subtract-soldermask",
         "--exclude-value", "-o", gdir + os.sep, BOARD])
    run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--drill-origin", "absolute",
         "--excellon-units", "mm", "--excellon-zeros-format", "decimal", "--excellon-oval-format", "alternate",
         "--excellon-separate-th", "-o", gdir + os.sep, BOARD])
    files = sorted(os.listdir(gdir))
    return files


def rotation_correction(fpname):
    for pat, rot in ROTATION_RULES:
        if re.search(pat, fpname):
            return rot
    return 0


def norm_angle(a):
    a = a % 360.0
    return a - 360.0 if a > 180.0 else a


def collect():
    b = pcbnew.LoadBoard(BOARD)
    parts = {p["ref"]: p for p in C.PARTS}
    rows = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        p = parts.get(ref)
        if p is None or p.get("dnp") or not p.get("lcsc"):
            continue                                   # mounting holes, PWR flags, DNP parts
        xs, ys = [], []
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            xs += [bb.GetLeft(), bb.GetRight()]
            ys += [bb.GetTop(), bb.GetBottom()]
        cx = pcbnew.ToMM((min(xs) + max(xs)) / 2) - OX
        cy = pcbnew.ToMM((min(ys) + max(ys)) / 2) - OY
        fpname = fp.GetFPID().GetLibItemName().wx_str() if hasattr(fp.GetFPID().GetLibItemName(), "wx_str") \
            else str(fp.GetFPID().GetLibItemName())
        corr = rotation_correction(fpname)
        rot = norm_angle(fp.GetOrientationDegrees() + corr)
        tht = bool(fp.GetAttributes() & pcbnew.FP_THROUGH_HOLE)
        rows.append(dict(ref=ref, value=p["value"], fp=fpname, lcsc=p["lcsc"], x=cx, y=-cy, rot=rot,
                         kicad_rot=fp.GetOrientationDegrees(), corr=corr, tht=tht,
                         layer="Top" if fp.GetLayer() == pcbnew.F_Cu else "Bottom"))
    rows.sort(key=lambda r: (re.sub(r"\d+", "", r["ref"]), int(re.sub(r"\D", "", r["ref"]) or 0)))
    return rows


def write_bom(rows, path):
    groups = OrderedDict()
    for r in rows:
        groups.setdefault((r["value"], r["fp"], r["lcsc"]), []).append(r["ref"])
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (val, fp, lcsc), refs in groups.items():
            w.writerow([val, ",".join(refs), fp, lcsc])
    return len(groups)


def write_cpl(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            w.writerow([r["ref"], f"{r['x']:.4f}mm", f"{r['y']:.4f}mm", r["layer"], f"{r['rot']:.1f}"])


def gerber_outline_extent(gdir):
    """Sanity check: read Edge.Cuts gerber coordinates (format 4.6, mm) and return width/height."""
    gm = [f for f in os.listdir(gdir) if f.endswith(".gm1")][0]
    xs, ys = [], []
    body = "\n".join(l for l in open(os.path.join(gdir, gm)) if not l.startswith(("%", "G04")))
    for m in re.finditer(r"X(-?\d+)Y(-?\d+)", body):
        xs.append(int(m.group(1)) / 1e6)
        ys.append(int(m.group(2)) / 1e6)
    return max(xs) - min(xs), max(ys) - min(ys)


def drill_summary(gdir):
    out = {}
    for f in os.listdir(gdir):
        if not f.endswith(".drl"):
            continue
        tools, hits, cur = {}, {}, None
        for line in open(os.path.join(gdir, f)):
            m = re.match(r"^T(\d+)C([\d.]+)", line)
            if m:
                tools[m.group(1)] = float(m.group(2))
                continue
            m = re.match(r"^T(\d+)\s*$", line)
            if m:
                cur = m.group(1)
                continue
            if line.startswith("X") and cur:
                hits[tools[cur]] = hits.get(tools[cur], 0) + 1
        out[f] = dict(sorted(hits.items()))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    gdir = os.path.join(OUT, "gerbers")
    files = export_gerbers(gdir)
    zpath = os.path.join(OUT, "kestrel_fc_gerbers_jlcpcb.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in files:
            z.write(os.path.join(gdir, fn), fn)
    rows = collect()
    nb = write_bom(rows, os.path.join(OUT, "kestrel_fc_bom_jlcpcb.csv"))
    write_cpl(rows, os.path.join(OUT, "kestrel_fc_cpl_jlcpcb.csv"))
    w, h = gerber_outline_extent(gdir)
    print(f"gerber files: {len(files)} -> {os.path.relpath(zpath, HERE)}")
    print(f"  board outline from Edge.Cuts gerber: {w:.2f} x {h:.2f} mm (expected {C.BOARD_W} x {C.BOARD_H})")
    for f, hits in drill_summary(gdir).items():
        print(f"  {f}: " + ", ".join(f"{d:.2f}mm x{n}" for d, n in hits.items()))
    n_smd = sum(1 for r in rows if not r["tht"])
    print(f"BOM: {nb} lines, {len(rows)} placements ({n_smd} SMD, {len(rows) - n_smd} through-hole)")
    corrected = [r for r in rows if r["corr"]]
    print("rotation corrections applied: " + ", ".join(f"{r['ref']}({r['fp']}:{r['corr']:+d})" for r in corrected))
    print("check on JLCPCB's placement preview: " + "; ".join(f"{k}: {v}" for k, v in REVIEW.items()))


if __name__ == "__main__":
    main()
