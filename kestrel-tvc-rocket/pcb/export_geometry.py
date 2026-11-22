"""Export pad / hole / outline geometry of the placed board to JSON for the router (run with /usr/bin/python3)."""
import json
import os
import sys

import pcbnew

import board_build as B
import circuit as C

HERE = os.path.dirname(os.path.abspath(__file__))


def poly_points(poly):
    out = []
    for oi in range(poly.OutlineCount()):
        ol = poly.Outline(oi)
        out.append([(pcbnew.ToMM(ol.CPoint(i).x) - B.OX, pcbnew.ToMM(ol.CPoint(i).y) - B.OY) for i in range(ol.PointCount())])
    return out


def main(out_path):
    b = B.setup_board()
    nets = B.add_nets(b)
    fps = B.place_parts(b, nets)
    pads = []
    holes = []
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            attr = pad.GetAttribute()
            pos = pad.GetPosition()
            entry = dict(ref=fp.GetReference(), num=pad.GetNumber(), net=pad.GetNetname() or None,
                         x=pcbnew.ToMM(pos.x) - B.OX, y=pcbnew.ToMM(pos.y) - B.OY,
                         tht=attr == pcbnew.PAD_ATTRIB_PTH, npth=attr == pcbnew.PAD_ATTRIB_NPTH,
                         F=bool(pad.IsOnLayer(pcbnew.F_Cu)), Bl=bool(pad.IsOnLayer(pcbnew.B_Cu)))
            if attr == pcbnew.PAD_ATTRIB_NPTH:
                holes.append(dict(x=entry["x"], y=entry["y"], r=pcbnew.ToMM(pad.GetDrillSize().x) / 2))
                continue
            poly = pcbnew.SHAPE_POLY_SET()
            lay = pcbnew.F_Cu if entry["F"] else pcbnew.B_Cu
            pad.TransformShapeToPolygon(poly, lay, 0, pcbnew.FromMM(0.003))
            entry["poly"] = poly_points(poly)
            if entry["tht"]:
                entry["drill"] = pcbnew.ToMM(pad.GetDrillSize().x)
            pads.append(entry)
    for h in C.MH:
        holes.append(dict(x=h["pos"][0], y=h["pos"][1], r=1.35))
    keepouts = []
    for fp in b.GetFootprints():
        for z in fp.Zones():
            if not z.GetIsRuleArea():
                continue
            ls = [l for l in z.GetLayerSet().Seq()]
            keepouts.append(dict(ref=fp.GetReference(), tracks=bool(z.GetDoNotAllowTracks()), vias=bool(z.GetDoNotAllowVias()),
                                 F=pcbnew.F_Cu in ls, Bl=pcbnew.B_Cu in ls, poly=poly_points(z.Outline())))
    json.dump(dict(board=[C.BOARD_W, C.BOARD_H], pads=pads, holes=holes, keepouts=keepouts), open(out_path, "w"))
    print(f"exported {len(pads)} pads, {len(holes)} holes")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "build", "geometry.json"))
