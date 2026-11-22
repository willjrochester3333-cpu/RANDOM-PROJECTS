"""Build the KESTREL FC board (outline, stack-up, footprints, nets, zones) with KiCad 7's pcbnew API.
Run with the system Python that ships pcbnew:  /usr/bin/python3 ..."""
import os
import sys

import pcbnew

import circuit as C

HERE = os.path.dirname(os.path.abspath(__file__))
FPDIR = "/usr/share/kicad/footprints"
OX, OY = 100.0, 100.0          # board origin in the KiCad page
MM = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = os.path.join(HERE, "kestrel.pretty") if lib == "kestrel" else os.path.join(FPDIR, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError("footprint not found: " + fpid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def setup_board():
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(4)
    ds = b.GetDesignSettings()
    ds.SetCopperLayerCount(4)
    ds.m_MinClearance = MM(0.127)
    ds.m_TrackMinWidth = MM(0.127)
    ds.m_ViasMinSize = MM(0.45)
    ds.m_MinThroughDrill = MM(0.25)
    ds.m_CopperEdgeClearance = MM(0.3)
    ds.m_HoleClearance = MM(0.25)
    ds.m_HoleToHoleMin = MM(0.25)
    ds.m_SolderMaskMinWidth = MM(0.1)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(MM(0.13))
    nc.SetTrackWidth(MM(0.2))
    nc.SetViaDiameter(MM(0.6))
    nc.SetViaDrill(MM(0.3))
    b.SetLayerName(pcbnew.In1_Cu, "In1.GND")
    b.SetLayerName(pcbnew.In2_Cu, "In2.3V3")
    # outline with 1 mm corner radius
    W, H, r = C.BOARD_W, C.BOARD_H, 1.0
    segs = [((r, 0), (W - r, 0)), ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))]
    for (a, c) in segs:
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a))
        s.SetEnd(P(*c))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        b.Add(s)
    for (cx, cy, sx, sy) in ((r, r, 0, r), (W - r, r, W - r, 0), (W - r, H - r, W, H - r), (r, H - r, r, H)):
        a = pcbnew.PCB_SHAPE(b)
        a.SetShape(pcbnew.SHAPE_T_ARC)
        a.SetCenter(P(cx, cy))
        a.SetStart(P(sx, sy))
        a.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
        a.SetLayer(pcbnew.Edge_Cuts)
        a.SetWidth(MM(0.1))
        b.Add(a)
    return b


def add_nets(b):
    nets = {}
    for n in C.nets():
        ni = pcbnew.NETINFO_ITEM(b, n)
        b.Add(ni)
        nets[n] = ni
    return nets


def place_parts(b, nets):
    fps = {}
    for p in C.PARTS:
        fp = load_fp(p["fp"])
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        x, y, rot = p["pos"]
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        b.Add(fp)
        for pad in fp.Pads():
            num = pad.GetNumber()
            net = p["pins"].get(num)
            if num == "" or num is None:
                continue
            if net:
                pad.SetNet(nets[net])
        fp.SetField("LCSC", p["lcsc"] or "") if hasattr(fp, "SetField") else None
        if p["ref"] == "J8":   # U.FL: one mask opening spans signal + shield pads by design
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_ALLOW_SOLDERMASK_BRIDGES)
        fps[p["ref"]] = fp
    for h in C.MH:
        fp = load_fp("MountingHole:MountingHole_2.7mm_M2.5")
        fp.SetReference(h["ref"])
        fp.SetPosition(P(*h["pos"]))
        b.Add(fp)
        fps[h["ref"]] = fp
    return fps


def add_zone(b, net, layer, priority=0, inset=0.3, clearance=0.25, thermal_gap=0.3, thermal_w=0.35, smd_solid=False):
    W, H = C.BOARD_W, C.BOARD_H
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(priority) if hasattr(z, "SetAssignedPriority") else z.SetPriority(priority)
    ol = z.Outline()
    ol.NewOutline()
    for (x, y) in ((inset, inset), (W - inset, inset), (W - inset, H - inset), (inset, H - inset)):
        ol.Append(MM(OX + x), MM(OY + y))
    z.SetLocalClearance(MM(clearance))
    z.SetMinThickness(MM(0.2))
    z.SetThermalReliefGap(MM(thermal_gap))
    z.SetThermalReliefSpokeWidth(MM(thermal_w))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL if smd_solid else pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIsFilled(False)
    b.Add(z)
    return z


def courtyard_overlaps(b):
    """Return list of overlapping front-courtyard pairs (bounding-box test on courtyard polygons)."""
    boxes = []
    for fp in b.GetFootprints():
        try:
            cy = fp.GetCourtyard(pcbnew.F_CrtYd)
            bb = cy.BBox()
            if bb.GetWidth() == 0:
                continue
            boxes.append((fp.GetReference(), pcbnew.ToMM(bb.GetLeft()) - OX, pcbnew.ToMM(bb.GetTop()) - OY,
                          pcbnew.ToMM(bb.GetRight()) - OX, pcbnew.ToMM(bb.GetBottom()) - OY))
        except Exception:
            pass
    out = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, c = boxes[i], boxes[j]
            if a[1] < c[3] - 0.01 and c[1] < a[3] - 0.01 and a[2] < c[4] - 0.01 and c[2] < a[4] - 0.01:
                out.append((a[0], c[0]))
    return out, boxes


if __name__ == "__main__":
    b = setup_board()
    nets = add_nets(b)
    fps = place_parts(b, nets)
    ov, boxes = courtyard_overlaps(b)
    print(f"{len(fps)} footprints placed, {len(ov)} courtyard overlaps")
    for o in ov:
        print("  overlap", o)
    out_of_board = [bx for bx in boxes if bx[1] < 0 or bx[2] < 0 or bx[3] > C.BOARD_W or bx[4] > C.BOARD_H]
    for bx in out_of_board:
        print("  outside board:", bx[0], [round(v, 2) for v in bx[1:]])
    pcbnew.SaveBoard(os.path.join(HERE, "placement_check.kicad_pcb"), b)
