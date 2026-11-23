"""Export the PCB's mechanical interface for the CAD model (run with /usr/bin/python3, KiCad 7 pcbnew).

Writes pcb/build/mech_interface.json with board-frame coordinates (mm, origin = top-left corner of the
board seen from the component side, x to the right, y down = towards the servo headers):
  board size / thickness, mounting holes, every through-hole pin (their tails stick out of the back),
  and the parts the airframe has to line up with (power switch + its slide knob, status LEDs, buzzer,
  connectors, Pico sockets, sensors).
cad/kestrel_cad.py reads this file, so moving a part in circuit.py moves the sled cut-outs and the
av-bay window with it."""
import json
import os

import pcbnew

import circuit as C

HERE = os.path.dirname(os.path.abspath(__file__))
OX = OY = 100.0
KEY = ["SW1", "D4", "D5", "BZ1", "J1", "J2", "J3", "J4", "J5", "J12", "J13", "J14", "J7", "J8", "J10", "J11", "U4", "U5", "U7", "SW2", "SW3"]


def mm(v):
    return pcbnew.ToMM(v)


def main():
    b = pcbnew.LoadBoard(os.path.join(HERE, "kestrel_fc.kicad_pcb"))
    out = dict(board=dict(w=C.BOARD_W, h=C.BOARD_H,
                          thickness=round(mm(b.GetDesignSettings().GetBoardThickness()), 3)),
               holes=[], tht_pins=[], parts={})
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            p = pad.GetPosition()
            x, y = round(mm(p.x) - OX, 3), round(mm(p.y) - OY, 3)
            if ref.startswith("H"):
                out["holes"].append(dict(ref=ref, x=x, y=y, d=round(mm(pad.GetDrillSize().x), 3)))
            elif pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                out["tht_pins"].append(dict(ref=ref, x=x, y=y, drill=round(mm(pad.GetDrillSize().x), 3)))
        if ref in KEY:
            cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            p = fp.GetPosition()
            out["parts"][ref] = dict(value=fp.GetValue(), x=round(mm(p.x) - OX, 3), y=round(mm(p.y) - OY, 3),
                                     rot=fp.GetOrientationDegrees(),
                                     courtyard=[round(mm(cy.GetLeft()) - OX, 3), round(mm(cy.GetTop()) - OY, 3),
                                                round(mm(cy.GetRight()) - OX, 3), round(mm(cy.GetBottom()) - OY, 3)])
    # PCM12 slide knob: footprint-local knob centre (-0.75, +2.4) mm, 1.3 x 1.5 mm, travel +/-0.75 mm along local x
    sw = [fp for fp in b.GetFootprints() if fp.GetReference() == "SW1"][0]
    # rotate footprint-local offsets by the footprint orientation (KiCad: +angle = CCW on screen, y down)
    import math
    a = math.radians(sw.GetOrientationDegrees())

    def rot(dx, dy):
        return dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
    sx, sy = mm(sw.GetPosition().x) - OX, mm(sw.GetPosition().y) - OY
    kx, ky = rot(-0.75, 2.4)
    tx, ty = rot(-0.75, 3.15)
    out["parts"]["SW1"]["knob"] = dict(x=round(sx + kx, 3), y=round(sy + ky, 3), tip_x=round(sx + tx, 3), tip_y=round(sy + ty, 3),
                                       height_above_pcb=0.7, travel=1.5)
    path = os.path.join(HERE, "build", "mech_interface.json")
    json.dump(out, open(path, "w"), indent=1)
    print(f"board {out['board']}, {len(out['holes'])} holes, {len(out['tht_pins'])} through-hole pins -> {os.path.relpath(path, HERE)}")
    print("SW1 knob:", out["parts"]["SW1"]["knob"])


if __name__ == "__main__":
    main()
