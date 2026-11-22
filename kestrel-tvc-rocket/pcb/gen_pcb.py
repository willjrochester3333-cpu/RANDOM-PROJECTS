"""Assemble the final KESTREL FC board: placement + routes + planes + silkscreen, then DRC.
Run with /usr/bin/python3 (KiCad 7 pcbnew).   Usage: gen_pcb.py build/routes.json"""
import json
import os
import re
import sys

import pcbnew

import board_build as B
import circuit as C

HERE = os.path.dirname(os.path.abspath(__file__))
MM = pcbnew.FromMM
LAYER = {0: pcbnew.F_Cu, 1: pcbnew.B_Cu}


def text(b, s, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0, bold=False, mirror=False):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s)
    t.SetPosition(B.P(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    size = max(size, 0.8)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(max(0.15, size * (0.2 if bold else 0.15))))
    t.SetTextAngleDegrees(rot)
    if mirror:
        t.SetMirrored(True)
    b.Add(t)
    return t


def free_spot(b, w, h, candidates):
    """First candidate centre whose w x h box avoids every via and back-side/THT pad (with 0.3 mm margin)."""
    obst = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            obst.append((pcbnew.ToMM(p.x) - B.OX, pcbnew.ToMM(p.y) - B.OY, 0.6))
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.B_Cu):
                p = pad.GetPosition()
                obst.append((pcbnew.ToMM(p.x) - B.OX, pcbnew.ToMM(p.y) - B.OY, 1.2))
    for (cx, cy) in candidates:
        if all(abs(ox - cx) > w / 2 + r or abs(oy - cy) > h / 2 + r for ox, oy, r in obst):
            return cx, cy
    return candidates[0]


def build(routes_path):
    b = B.setup_board()
    nets = B.add_nets(b)
    fps = B.place_parts(b, nets)
    # silkscreen: shrink reference designators so they stay legible but out of the way
    # silkscreen: show designators only on ICs/connectors/switches (passives are identified in the
    # assembly drawing + CPL); everything >= 0.8 mm tall (JLCPCB legibility minimum)
    KEEP = ("U6", "U7")
    for fp in b.GetFootprints():
        r = fp.Reference()
        ref = fp.GetReference()
        show = ref in KEEP
        r.SetVisible(show)
        r.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        r.SetTextThickness(MM(0.15))
        fp.Value().SetVisible(False)
    routes = json.load(open(routes_path))
    for (net, l, x0, y0, x1, y1, w) in routes["tracks"]:
        if abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6:
            continue
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(B.P(x0, y0))
        t.SetEnd(B.P(x1, y1))
        t.SetWidth(MM(w))
        t.SetLayer(LAYER[l])
        t.SetNet(nets[net])
        b.Add(t)
    for (net, x, y) in routes["vias"]:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(B.P(x, y))
        v.SetDrill(MM(0.3))
        v.SetWidth(MM(0.55))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(nets[net])
        b.Add(v)
    # planes: In1 = GND, In2 = +3V3, outer layers GND pour
    B.add_zone(b, nets["GND"], pcbnew.In1_Cu, priority=0, clearance=0.25)
    B.add_zone(b, nets["+3V3"], pcbnew.In2_Cu, priority=0, clearance=0.25)
    B.add_zone(b, nets["GND"], pcbnew.F_Cu, priority=0, clearance=0.25, smd_solid=True)
    B.add_zone(b, nets["GND"], pcbnew.B_Cu, priority=0, clearance=0.25, smd_solid=True)
    # ---- silkscreen: short markers on the crowded front, full labels on the roomy back ----
    for i, x in enumerate((8.8, 13.3, 17.8, 22.3)):
        text(b, str(i + 1), x + 2.25, 74.85, 0.8)                      # servo port numbers (front)
    for s_, y in (("S", 74.85), ("+", 77.39), ("-", 79.93)):
        text(b, s_, 6.3, y, 0.8)
    text(b, "USB", 15.0, 32.8, 0.8)
    text(b, "^ PICO 2 W", 15.0, 34.0, 0.8)
    # back side (mirrored), positioned under the parts they describe
    BS = pcbnew.B_SilkS
    title = "KESTREL FC v1.0"
    tx, ty = free_spot(b, len(title) * 1.0 * 0.95 + 0.6, 1.6, [(15.0, y / 2.0) for y in range(60, 130)])
    text(b, title, tx, ty, 1.0, layer=BS, mirror=True, bold=True)
    for i, (x, n) in enumerate(((8.8, "RING"), (13.3, "MOTOR"), (17.8, "DEPLOY"), (22.3, "AUX/CAM"))):
        text(b, f"{i+1}:{n}", x, 70.0 - (i % 2) * 1.2, 0.8, layer=BS, mirror=True)
    text(b, "SERVO  S + -", 15.5, 66.6, 0.8, layer=BS, mirror=True)
    text(b, "BATT 2S", 35.0, 63.4, 0.8, layer=BS, mirror=True)
    text(b, "balance plug", 35.0, 62.2, 0.8, layer=BS, mirror=True)
    text(b, "QWIIC I2C", 4.0, 64.6, 0.8, layer=BS, mirror=True, rot=90)
    text(b, "GPS ANT", 22.6, 6.6, 0.8, layer=BS, mirror=True)
    text(b, "PWR ON/OFF", 33.0, 40.0, 0.8, layer=BS, mirror=True, rot=90)
    text(b, "USER  RST", 29.8, 13.2, 0.8, layer=BS, mirror=True)
    text(b, "JLCJLCJLCJLC", 15.0, 52.0, 0.8, layer=BS, mirror=True)   # JLCPCB places its order number here
    out = os.path.join(HERE, "kestrel_fc.kicad_pcb")
    pcbnew.SaveBoard(out, b)
    print("saved unfilled board", flush=True)
    # reload (gives a fully initialised board: connectivity, project) and fill the zones
    b2 = pcbnew.LoadBoard(out)
    b2.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(b2)
    filler.Fill(b2.Zones())
    pcbnew.SaveBoard(out, b2)
    print("zones filled", flush=True)
    return out


def patch_project(path):
    pro = os.path.splitext(path)[0] + ".kicad_pro"
    js = json.load(open(pro))
    ds = js.setdefault("board", {}).setdefault("design_settings", {})
    sev = ds.setdefault("rule_severities", {})
    sev.update({"lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore"})
    json.dump(js, open(pro, "w"), indent=2)


def drc(path):
    patch_project(path)
    b = pcbnew.LoadBoard(path)
    rpt = os.path.join(HERE, "build", "drc_report.txt")
    pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(rpt).read()
    m = re.search(r"\*\* Found (\d+) DRC violations \*\*", txt)
    u = re.search(r"\*\* Found (\d+) unconnected pads \*\*", txt)
    nviol = int(m.group(1)) if m else -1
    nunc = int(u.group(1)) if u else -1
    print(f"DRC: {nviol} violations, {nunc} unconnected")
    kinds = re.findall(r"^\[(\w+)\]", txt, re.M)
    from collections import Counter
    print("  by type:", dict(Counter(kinds)))
    return nviol, nunc, txt


if __name__ == "__main__":
    out = build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "build", "routes.json"))
    drc(out)
