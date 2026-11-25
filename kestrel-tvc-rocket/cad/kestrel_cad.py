"""KESTREL-2 parametric CAD generator for Blender (tested with Blender 4.0.2, headless).

    blender -b -P cad/kestrel_cad.py -- [--no-render] [--fast] [--view=NAME ...]

Solid modelling uses manifold3d (robust, always-watertight CSG) running inside Blender's Python;
Blender is used for the assemblies, materials, the .blend files and rendering.

The rocket comes apart into three parts:
  1. BOTTOM part - fin can (4 fins that are also the legs it stands on, 4 servo-driven control tabs in
                   streamlined pods), TVC module, camera pod, avionics bay (flight computer + battery), coupler
  2. MIDDLE part - payload bay with a lockable door, a wall, the parachute bay, the release latch at the top
  3. NOSE cone   - printed; the ejection spring pushes it off when the release servo pulls the latch bolt

Outputs
  cad/stl/*.stl + parts.json          print-oriented STLs (mm)
  cad/kestrel.blend                   scene 1: the complete rocket, the same rocket cut open (everything inside) and
                                      every part laid out with its name; scenes 2-7: exploded view, cut-aways, payload
                                      door open, fin tabs deflected, fin cut open, rocket on the launch pad
  cad/kestrel_rocket.blend            just the constructed rocket: every part in place, grouped by section, tubes hideable
  cad/kestrel_tvc_module.blend        the TVC module on its own (its two servo leads come out of the top) + assembly steps
  cad/kestrel_parachute_open.blend    the rocket descending under its open parachute
  cad/component_positions.json        where every purchased part sits (read by the simulator's mass model)
  cad/avionics_layout.json, cad/interference_report.md, cad/renders/*.png
All dimensions come from ../design.json. Blender Z = height above the aft end of the bottom body tube.
"""
import json
import math
import os
import sys

import bpy
import manifold3d as mf
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FAST = "--fast" in ARGS
VIEWS = [a.split("=", 1)[1] for a in ARGS if a.startswith("--view=")]
SEG = 48 if FAST else 128

D = json.load(open(os.path.join(ROOT, "design.json")))
AF, NOSE, AV, FIN, TVC = D["airframe"], D["nose"], D["avbay"], D["fins"], D["tvc"]
REC, PAY, BAT = D["recovery"], D["payload"], D["battery"]

# ======================================================================================
# Key dimensions (mm).  Z = height above the aft end of the bottom tube.
# ======================================================================================
OD, ID = AF["od"], AF["id"]
R, RI = OD / 2, ID / 2
L_LOW, L_MID, BAND = AF["lower_tube_length"], AF["upper_tube_length"], AV["band"]
Z_BAND0 = L_LOW                         # 340 top of the bottom tube
Z_MID0 = L_LOW + BAND                   # 344 bottom of the middle tube
Z_MID1 = Z_MID0 + L_MID                 # 724 top of the middle tube
SLEEVE = NOSE["sleeve_length"]          # 25  body-diameter sleeve at the base of the nose cone
Z_NOSE0 = Z_MID1 + SLEEVE               # 749 base of the ogive
NOSE_L = NOSE["length"]
Z_TIP = Z_NOSE0 + NOSE_L                # 899
FIT = 0.10
INS_R = AV["insert_od"] / 2             # 27.5 printed parts that slide inside a body tube
WALL = AV["wall"]
Z_AV0 = Z_BAND0 - AV["lower_insert"]    # 240 bottom of the avionics bay
SH_TOP = Z_MID0 + 28.0                  # 372 top of the coupler shoulder (underside of its bulkhead)
BULK_T = 2.4
Z_FLOOR = SH_TOP + BULK_T               # 374.4 payload-bay floor
Z_WALL0 = Z_FLOOR + PAY["bay_length"]   # 504.4 payload / parachute wall
Z_WALL1 = Z_WALL0 + BULK_T
SPR = REC["spring"]
Z_PISTON = Z_WALL1 + SPR["packed_length"]   # underside of the spring piston with the spring packed
# nose sleeve / top insert shoulder
NS_W = 1.2
SHO_R = R - NS_W - 0.10                 # 26.85
SHO_RI = SHO_R - 1.6                    # 25.25
Z_TOPI0 = Z_MID1 - 36.0                 # bottom of the top (release-latch) insert
# TVC: 29 mm mount for the TSP F35 (the 24 mm D20 / E20 fit with a printed adapter sleeve and their own retainer).
# Same layout as the 24 mm module; the holder and ring are 2.5 mm larger in radius and the pushrods sit 4 mm further
# out (gimbal arms 22 mm) so that they clear the bigger holder when it swings
MOTOR_D = TVC["motor_diameter"]
MOTOR_L = 95.0
Z_MOTOR0 = -TVC["nozzle_protrusion"]
Z_PIVOT = TVC["pivot_from_tail"]
HOLD_RI = MOTOR_D / 2 + 0.2
HOLD_R = HOLD_RI + 1.6
RING_RI, RING_R = HOLD_R + 1.4, HOLD_R + 4.4
FRAME_R = INS_R
FRAME_TOP = 156.0
FRAME_BOT_RI = 26.0                     # bottom ring of the TVC frame (24.6 on the 24 mm mount): clears the 29 mm retainer
SV = dict(L=22.8, W=12.2, H=22.5, tab_L=32.2, tab_t=2.5, tab_z=15.9, shaft_off=5.9, spline=5.0, pitch=27.8)
SV_MASS = 13.4
SV1_Z, SV2_Z = 120.0, 145.0
SV_SHAFT_R = 16.0
PR1 = (9.0, 22.0)                       # ring pushrod: horn hole radius 9 mm, gimbal arm 22 mm (linkage 9/22)
PR2 = (22.0, 9.0)                       # motor-holder pushrod
TAB_BOSS_R = 2.0                        # round boss round each pushrod hole (keeps the tabs inside the frame)
HOLDER_TAB_Z = Z_PIVOT + 12.0
TAIL_SCREW_Z, TAIL_SCREW_ANG = 16.0, (90.0, 210.0)
# fins, legs, control tabs.  KESTREL-2c: normal 4 mm fins; only the bottom band that holds the tab hinge, the tab servo
# and its lead channel is 15 mm thick, faired into the thin fin by a smooth wedge. The servo sits INSIDE that band; its
# output shaft lies on the tab hinge line and turns the tab directly (no pods, no pushrods, no metal hinge pins)
NF = FIN["count"]
FIN_ANG = [FIN["first_fin_deg"] + 360.0 * k / NF for k in range(NF)]     # 45, 135, 225, 315 (X layout)
CAN_RI = R + 0.10
CAN_RO = CAN_RI + FIN["can_wall"]        # 29.25
FT = FIN["thickness"]                   # 15: the bottom band
FT_UP = FIN["upper_thickness"]          # 4: the rest of the fin
RAMP_L = FIN["ramp_mm"]                 # 20: wedge from the band up to the thin fin
TE_EXT = FIN["te_extension_mm"]         # 12: the tab and band trailing edges taper to a thin edge this far below the tail
TE_T = FIN["te_thickness_mm"]           # 1.5
FOOT_T = FIN["leg"]["foot_thickness_mm"]  # 11: the legs taper from 15 mm to this at the foot
TIP_R = CAN_RO + FIN["span"]            # 79.25
TABP = FIN["tab"]
LEGP = FIN["leg"]
LEG_R0 = TIP_R - LEGP["width"]
FOOT_Z = -LEGP["length"]                # -30: the rocket stands on its four fin tips
# fin-local frame: x along the fin (radial), y normal to it (+y = towards the next fin anticlockwise), z up.
HINGE_Z = TABP["hinge_z"]               # 15: tab hinge line = servo output shaft (radial, in the fin's mid-plane)
TAB_LE_R = FT / 2 - 0.3                 # 7.2: round leading edge of the tab about the hinge
BAY_R = TAB_LE_R + 0.4                  # 7.6: matching concave cut in the fin
BAY_X0 = CAN_RO + 2.5                   # the tab bay starts 2.5 mm out from the can (root pin slot there)
SVX1 = TIP_R - 1.0                      # servo base, 1 mm inside the fin tip (the servo slides in from the tip)
SVX0 = SVX1 - SV["H"]                   # servo top (output shaft) face, 55.75
SV_Z0 = HINGE_Z - SV["shaft_off"]       # servo body lower end (shaft end), 9.1
SV_ZC = SV_Z0 + SV["L"] / 2
SV_TAB_X0 = SVX1 - SV["tab_z"] - SV["tab_t"]   # mounting-tab plate; its inboard face rests on the pocket shoulder
BAY_X1 = SVX0 - 0.2
TAB_X0, TAB_X1 = BAY_X0 + 0.3, SVX0 - 0.4      # printed tab, 32.05 .. 55.35
HORN_HUB_X1 = SVX0 - 0.5                # stock single-arm horn: hub on the spline, arm trimmed to a stub
HORN_HUB_L, HORN_ARM_T, HORN_ARM_L = 4.0, 2.0, 5.5
PIN_R = 1.5                             # printed pivot pin at the tab's inner end
CH_Z0, CH_Z1, CH_W = 38.5, 43.5, 9.0    # servo-lead channel through the fin to the root: the 8 x 4 mm plug is pushed through it
BAND_TOP = CH_Z1 + 1.5                  # 45: top of the 15 mm band (1.5 mm of wall above the lead channel)
SCREW_HOLE_D = 4.0                                              # blind pilot holes for the servo's M2 x 6 screws
LEAD_GROOVE_W, LEAD_GROOVE_D = 4.0, 4.0                         # lead groove in the fin tip (flat 3-wire lead, 3.2 x 1.1 mm)
GROOVE_ANG = list(FIN_ANG)              # the lead enters the tube at the fin root and runs up a groove in the TVC frame
CAB_Z0, CAB_Z1 = CH_Z0, CH_Z1
# KESTREL-2d (multi-flight): the tab bay leaves the outer part of each fin (servo housing + leg) joined to the rest only
# above z ~17 mm, so the housing's two side walls carry every landing load on the foot. They are 2.2 mm thick (housing
# 17 mm) instead of 1.2 mm. The legs are separate, replaceable parts: a sleeve slides up over a solid tongue under each
# fin tip (part of the fin can) and one M3 bolt crosses both; a 6 x 9.2 mm post then runs to the foot and is the designed
# weak link, so a hard landing breaks a 5 g leg instead of the fin can.
HSGP = FIN["housing"]
HT = HSGP["thickness"]                  # 17: band thickness round the tab servo
HX0 = BAY_X1 - 0.3                      # 55.25: the housing starts where the tab bay ends (the band tapers 15 -> 17 inboard)
HX_TAPER = HSGP["taper_mm"]
TG_LX, TG_Y, TG_H = LEGP["tongue_mm"]   # 14 x 12.3 x 12 tongue
LEG_CLR = 0.15                          # sleeve-to-tongue clearance per side
TG_X1 = TIP_R - 3.0                     # tongue outer end (the sleeve's outer wall is 2.85 mm, flush with the fin tip)
TG_X0 = TG_X1 - TG_LX                   # 62.25
SL_X0 = LEG_R0                          # 59.6: sleeve inner face (inner wall 2.5 mm); the trailing-edge taper ends 0.2 mm short
SL_Z0 = LEGP["sleeve_bottom_z"]         # -13.95: sleeve floor underside
LEG_BOLT_X, LEG_BOLT_Z = (TG_X0 + TG_X1) / 2, -6.0     # M3 bolt across (along y), 6 mm from both tongue edges
POST_W, POST_T = LEGP["post_mm"]        # 6.0 (along the span) x 9.2 (across the fin)
POST_X0, POST_X1 = TIP_R - 1.25 - POST_W, TIP_R - 1.25  # 72.0 .. 78.0: the foot stays where it was
POST_Z1 = LEGP["post_top_z"]            # -18.5: top of the post (the weak section)
LEG_RECESS = 0.8                        # bolt head / nut sunk this far into the sleeve's side walls
# camera pod, avionics
CAM_Z0 = 200.0
CAM_POCKET = 23.6
CAM_FLOOR = 1.8
CAM_RC = R + 1.5
CAM_WIN_W, CAM_WIN_H = CAM_POCKET + 2 * 1.6 + 0.2, 30.0
RADIAL_SCREW_ANG = (0.0, 180.0)
STATIC_PORT_ANG = (30.0, 150.0, 270.0)
LUG_ANG = 90.0
BATT = dict(w=BAT["width"], t=BAT["thickness"], l=BAT["length"], y0=4.0, z0=Z_AV0 + 14.0)
BAY = dict(w=BAT["width"] + 1.0, t=BAT["thickness"] + 1.0, l=BAT["length"] + 6.0)
# middle part
DOOR_Z0, DOOR_H, DOOR_W = 380.0, PAY["door_height"], PAY["door_width"]
DHX, DHZ = R + 0.45, DOOR_Z0 + 2.0      # door hinge axis (along Y), just outside the tube surface
LATCH_Z = DOOR_Z0 + DOOR_H - 6.0
JOINT_ANG, JOINT_Z = (90.0, 270.0), Z_MID0 + 14.0
# battery hatch (multi-flight), +y side = the launch-rod side: the pack slides out through it and the Pico's own USB
# socket is reached through it with an angled micro-USB cable (nothing extra in the rocket). The door is a 1.2 mm
# curved panel that sits ON the tube and overlaps the opening by 2 mm all round, so there is no gap anywhere; two hooks
# at the top go behind the coupler wall and a quarter-turn latch on the rod line (flush coin slot) pulls the bottom
# tight against a flat catch. The upper launch lug moves to the middle tube, just above the joint screw at 90 deg.
HATCH_X = 13.0
HATCH_Z0, HATCH_Z1 = Z_AV0 + 8.0, Z_AV0 + 86.0        # 248 .. 326: opening through the bottom tube and the coupler
HD_M, HD_T, HD_R0 = 2.0, 1.2, R + 0.02                # door overlap, thickness, inner radius
HL_Z = HATCH_Z0 + 3.5                                 # latch axis (along y, x = 0)
HL_Y0, HL_Y1 = 23.6, 24.75                            # cam between these; it bears on the catch face at y = 24.85
HC_Y = 24.85
HOOK_X = 8.0
PAD_Y = 20.3                                          # door pad face (1.5 mm foam pad to the pack at y 19.5)
UPPER_LUG_Z = JOINT_Z + 5.0                           # 363
# release latch at the top of the middle part
RSV_XC = -16.4
RSV_Z0 = Z_MID1 - 0.3 - SV["H"]          # release servo body bottom (shaft up, long side along Y)
RSV_SH = (RSV_XC, -SV["L"] / 2 + SV["shaft_off"])
RHORN_Z = RSV_Z0 + SV["H"] + 4.0
RHORN_ARM = 7.0
BOLT_Y, BOLT_Z = RSV_SH[1] + RHORN_ARM, RHORN_Z
BOLT_TIP_X, BOLT_IN_X = -28.0, -21.4

# Flight-computer PCB interface, exported from KiCad by pcb/export_mech.py
MECH = json.load(open(os.path.join(ROOT, "pcb", "build", "mech_interface.json")))
BW, BH, BT = MECH["board"]["w"], MECH["board"]["h"], MECH["board"]["thickness"]
PCB_Z_TOP = Z_AV0 + 3.0 + BH
# GPS antenna platform: top face 19 mm above the board, beside (not above) the Pico's USB socket so a USB plug fits;
# U-shaped so the antenna's lead can leave its underside or an edge; carried by two 45 deg gussets (prints without supports)
GPS_SHELF_Z = PCB_Z_TOP + 19.0
GPS_X0, GPS_X1, GPS_Y1 = -18.0, -2.0, 3.0
GPS_X, GPS_Y = (GPS_X0 + GPS_X1) / 2, -6.0             # antenna centre (15 x 15 mm patch)
PCB_Y_BACK = -11.0
PCB_Y_FRONT = PCB_Y_BACK + BT
STANDOFF_H = 4.0
PLATE_T = 2.0
PLATE_Y = PCB_Y_BACK - STANDOFF_H - PLATE_T / 2
SOCKET_H = 8.5
KNOB = MECH["parts"]["SW1"]["knob"]


def board_to_rocket(bx, by):
    """PCB coordinates (mm, component side up, y towards the servo headers) -> rocket (x, z)."""
    return BW / 2.0 - bx, PCB_Z_TOP - by


SW_X, SW_Z = board_to_rocket(KNOB["tip_x"], KNOB["tip_y"])
SW_Y = PCB_Y_FRONT + KNOB["height_above_pcb"]
SW_ANG = math.degrees(math.atan2(SW_Y, SW_X)) % 360.0

LOWER_TUBE = f"BT70_bottom_tube_{L_LOW:.0f}"
MID_TUBE = f"BT70_middle_tube_{L_MID:.0f}"
MOTOR_NAME = "motor_" + D["launch"]["nominal_motor"].replace("-", "_") + f"_{MOTOR_D:.0f}x{MOTOR_L:.0f}"
PCB_NAME = f"pcb_kestrel_fc_{BW:.0f}x{BH:.0f}"

STL_DIR = os.path.join(HERE, "stl")
REN_DIR = os.path.join(HERE, "renders")
os.makedirs(STL_DIR, exist_ok=True)
os.makedirs(REN_DIR, exist_ok=True)
PARTS = {}

# ======================================================================================
# manifold helpers
# ======================================================================================
M3 = mf.Manifold


def cyl(r, h, z0=0.0, x=0.0, y=0.0, r2=None, segs=None):
    return M3.cylinder(h, r, r if r2 is None else r2, segs or SEG).translate((x, y, z0))


def box(sx, sy, sz, cx=0.0, cy=0.0, cz=0.0):
    return M3.cube((sx, sy, sz), True).translate((cx, cy, cz))


def bx(x0, x1, y0, y1, z0, z1):
    """box from min/max corners"""
    return box(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0), (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)


def _ccw(pts):
    a = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        a += x1 * y2 - x2 * y1
    return pts if a > 0 else pts[::-1]


def revolve(prof, segs=None):
    return M3.revolve(mf.CrossSection([_ccw(list(prof))]), segs or SEG)


def tube(ro, ri, h, z0=0.0, segs=None):
    return revolve([(ri, z0), (ro, z0), (ro, z0 + h), (ri, z0 + h)], segs)


def xcyl(r, L, segs=24):
    return M3.cylinder(L, r, r, segs).translate((0, 0, -L / 2)).rotate((0, 90, 0))


def ycyl(r, L, segs=24):
    return M3.cylinder(L, r, r, segs).translate((0, 0, -L / 2)).rotate((90, 0, 0))


def polar(m, ang_deg):
    return m.rotate((0, 0, ang_deg))


def xz_plate(prof, t):
    """plate of thickness t (centred on y=0) from a polygon in the x-z plane"""
    return M3.extrude(mf.CrossSection([_ccw(list(prof))]), t).translate((0, 0, -t / 2)).rotate((90, 0, 0))


def union(ms):
    out = ms[0]
    for m in ms[1:]:
        out = out + m
    return out


# ======================================================================================
# Blender helpers
# ======================================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = "MILLIMETERS"


def collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def mat(name, rgb, metal=0.0, rough=0.5, alpha=1.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        m.blend_method = "BLEND"
    m.diffuse_color = (*rgb, 1.0)
    return m


def to_blender(name, m, material, coll):
    if isinstance(material, str):                 # parts store material names: they survive scene resets
        material = bpy.data.materials[material]
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    f = np.asarray(mesh.tri_verts)
    me = bpy.data.meshes.new(name)
    me.from_pydata(v.tolist(), [], f.tolist())
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    me.materials.append(material)
    return ob


def curve_obj(name, pts, material, coll, radius=0.6):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1)
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(material)
    coll.objects.link(ob)
    return ob


def register(name, m, material, print_rot=(0, 0, 0), qty=1, note="", group="rocket", inst=None, part="", export=None, export_rot=None):
    """export / export_rot: a differently placed copy of the part (e.g. in its own frame) and its print rotation for the STL"""
    st = m.status()
    if str(st) not in ("Error.NoError", "NoError") or m.is_empty():
        raise RuntimeError(f"{name}: manifold status {st}, empty={m.is_empty()}")
    PARTS[name] = dict(m=m, material=material.name, print_rot=export_rot if export is not None else print_rot, qty=qty, note=note,
                       group=group, inst=inst or [m], part=part, export_m=export)
    return m


def MATS():
    return dict(
        orange=mat("PETG orange", (0.90, 0.32, 0.06), rough=0.45),
        white=mat("PETG white", (0.88, 0.88, 0.86)),
        black=mat("PETG black", (0.04, 0.04, 0.045), rough=0.4),
        grey=mat("PETG grey", (0.35, 0.36, 0.38)),
        blue=mat("PETG blue", (0.07, 0.22, 0.62), rough=0.45),
        kraft=mat("Kraft tube", (0.55, 0.38, 0.22), rough=0.8),
        motor=mat("Motor casing", (0.85, 0.73, 0.45), rough=0.7),
        servo=mat("Servo", (0.02, 0.02, 0.03), rough=0.35),
        horn=mat("Servo horn", (0.92, 0.92, 0.9), rough=0.5),
        pcb=mat("PCB green", (0.02, 0.28, 0.12), rough=0.4),
        pico=mat("Pico", (0.05, 0.45, 0.15), rough=0.4),
        steel=mat("Steel", (0.62, 0.63, 0.65), metal=1.0, rough=0.3),
        wood=mat("Wood dowel", (0.62, 0.45, 0.26), rough=0.7),
        lipo=mat("LiPo", (0.12, 0.25, 0.65), rough=0.4),
        nylon=mat("Chute nylon", (0.85, 0.05, 0.08), rough=0.6),
        nylon2=mat("Chute nylon white", (0.92, 0.92, 0.9), rough=0.6),
        cord=mat("Kevlar cord", (0.85, 0.7, 0.2), rough=0.8),
        camera=mat("Camera", (0.07, 0.07, 0.08), rough=0.3),
        antenna=mat("GPS patch", (0.8, 0.75, 0.6), rough=0.6),
        wire_r=mat("Lead red", (0.75, 0.05, 0.05)), wire_br=mat("Lead brown", (0.3, 0.15, 0.05)),
        wire_or=mat("Lead orange", (0.95, 0.5, 0.05)),
        payload=mat("Payload", (0.95, 0.80, 0.10), rough=0.5),
        tile=mat("Ceramic tile", (0.75, 0.74, 0.7), rough=0.6),
    )


# ======================================================================================
# NOSE CONE (part 3)
# ======================================================================================
NOSE_FILL_R = 7.0          # ballast fill hole through the apex of the nose bulkhead
BALLAST_G = next(c["mass_g"] for c in D["components"] if c["name"] == "nose_ballast_M3_nuts_epoxy")
BALLAST_BULK_CM3 = (BALLAST_G - 3.0) / 0.33 * (8.6 / 90.0)   # M3 nuts (0.33 g) poured into the tip, ~45 % packing; 3 g epoxy


def ogive_r(x, L=NOSE_L, Rb=R):
    rho = (Rb ** 2 + L ** 2) / (2 * Rb)
    return math.sqrt(max(rho ** 2 - (L - x) ** 2, 0.0)) + Rb - rho


def nose_cone(M):
    wall = NOSE.get("wall", 1.0) * 1.15
    n = 80
    outer = [(ogive_r(NOSE_L * i / n), Z_TIP - NOSE_L * i / n) for i in range(1, n + 1)]
    inner = []
    for i in range(n, 7, -1):
        x = NOSE_L * i / n
        r = ogive_r(x) - wall
        if r > 1.2:
            inner.append((r, Z_TIP - x))
    # bulkhead: a 45-degree cone (apex up) so the nose prints tip-up with no supports; 2.3 mm thick measured vertically
    zb = Z_NOSE0 - 2.0
    rs = R - NS_W                                            # sleeve inner radius
    z_apex = zb + rs                                         # underside apex on the axis
    t_v = 2.3
    z_top = z_apex + t_v

    def cone_top_meets_wall(z):                              # cone top surface z = z_top - r meets the inner ogive wall
        return (ogive_r(Z_TIP - z) - wall) - (z_top - z)
    lo, hi = Z_NOSE0 - 3.0, z_top
    for _ in range(60):
        mid = (lo + hi) / 2
        if cone_top_meets_wall(mid) > 0:     # wall still outside the cone top here: the meeting point is lower
            hi = mid
        else:
            lo = mid
    z_star = (lo + hi) / 2
    r_star = z_top - z_star
    wall_pts = [(r, z) for r, z in inner if z > z_star + 0.3]
    prof = [(0.0, Z_TIP)] + outer + [(R, Z_MID1), (R - NS_W, Z_MID1), (rs, zb), (0.0, z_apex), (0.0, z_top), (r_star, z_star)]
    prof += wall_pts + [(0.0, wall_pts[-1][1])]
    m = revolve(prof)
    # latch-bolt hole through the sleeve wall (the bolt from the top insert snaps into it)
    m = m - bx(-(R + 1.0), -(R - NS_W - 0.6), BOLT_Y - 2.2, BOLT_Y + 2.2, BOLT_Z - 1.7, BOLT_Z + 1.7)
    # inner chamfer on the sleeve's bottom edge: pushes the bevelled bolt in when the nose is fitted
    m = m - revolve([(R - NS_W - 0.3, Z_MID1 - 0.5), (R - NS_W + 0.6, Z_MID1 - 0.5), (R - NS_W + 0.6, Z_MID1 + 0.05),
                     (R - NS_W - 0.3, Z_MID1 + 0.95)])
    m = m - cyl(0.9, 9.0, zb + (rs - 14.0) - 3.0, 0.0, 14.0, segs=16)        # vent through the cone: the nose cavity breathes
    # alignment groove (rides on the insert's rib) so the bolt always lines up with its hole
    m = m - bx(R - NS_W - 0.3, R - 0.45, -1.3, 1.3, Z_MID1 - 1.0, Z_MID1 + SLEEVE - 3.0)
    # shock-cord bar across the inside of the cone, 9 mm below its apex: an 18 mm bridge when printed tip-up
    z_bar = z_apex - 9.0
    m = m + (bx(-(9.0 + 1.6), 9.0 + 1.6, -1.5, 1.5, z_bar - 1.5, z_bar + 1.5) ^ cyl(rs + 0.5, 60.0, zb))
    # ballast fill hole through the bulkhead apex (above the cord bar): M3 nuts are poured into the tip, then epoxied
    m = m - cyl(NOSE_FILL_R, z_top + 1.0 - (z_apex - NOSE_FILL_R - 0.2), z_apex - NOSE_FILL_R - 0.2, segs=40)
    return register("nose_cone", m, M["orange"], part="nose",
                    note="Print tip-up, 3 walls, 10% gyroid, no supports (the bulkhead is a 45 deg cone). Slides over the top insert; the latch bolt clicks into its hole. "
                         "Ballast (about 90 M3 nuts + epoxy) goes into the tip through the hole in the bulkhead")


def nose_ballast():
    """M3 nuts locked with epoxy in the nose tip, filling the cavity from its top down to the depth that holds
    BALLAST_BULK_CM3 (the slug the simulator and the renders use; the real amount is set by the balance test)"""
    wall = NOSE.get("wall", 1.0) * 1.15
    dx = 0.25
    xs, vol, x = [], 0.0, NOSE_L * 8 / 80 + 0.3 - dx      # the cavity starts 15 mm below the tip (solid tip above)
    while vol < BALLAST_BULK_CM3 * 1000.0 and x < NOSE_L * 0.6:
        x += dx
        r = ogive_r(x) - wall - 0.15
        if r > 1.2:
            xs.append(x)
            vol += math.pi * r * r * dx
    prof = [(0.0, Z_TIP - xs[0])] + [(ogive_r(xx) - wall - 0.15, Z_TIP - xx) for xx in xs[::4]] + \
           [(ogive_r(xs[-1]) - wall - 0.15, Z_TIP - xs[-1]), (0.0, Z_TIP - xs[-1])]
    return revolve(prof)


# ======================================================================================
# MIDDLE PART: top release-latch insert, latch bolt, payload door, wall, piston
# ======================================================================================
def release_servo_solid(clear=0.0):
    """MG90S standing shaft-up at the top of the middle tube, long side along Y (body + mounting tabs + spline)."""
    s, c = SV, clear
    z0 = RSV_Z0
    body = bx(RSV_XC - s["W"] / 2 - c, RSV_XC + s["W"] / 2 + c, -s["L"] / 2 - c, s["L"] / 2 + c, z0 - c, z0 + s["H"] + c)
    tabs = bx(RSV_XC - (s["W"] - 1) / 2 - c, RSV_XC + (s["W"] - 1) / 2 + c, -s["tab_L"] / 2 - c, s["tab_L"] / 2 + c,
              z0 + s["tab_z"] - c, z0 + s["tab_z"] + s["tab_t"] + c)
    spline = cyl(2.4 + c, s["spline"], z0 + s["H"], RSV_SH[0], RSV_SH[1], segs=24)
    return body + tabs + spline


def release_horn(phi_deg=0.0):
    """single-arm horn on the release servo; arm points +Y, hole at RHORN_ARM. phi>0 turns the hole towards +X (release)"""
    hub = cyl(3.5, 2.0, RHORN_Z - 1.0, segs=32)
    arm = M3.batch_hull([cyl(3.0, 2.0, RHORN_Z - 1.0, segs=24), cyl(1.9, 2.0, RHORN_Z - 1.0, 0, RHORN_ARM + 1.0, segs=24)])
    h = (hub + arm) - cyl(0.5, 4.0, RHORN_Z - 2.0, 0, RHORN_ARM, segs=12) - cyl(2.45, 8.0, RHORN_Z - 4.0, segs=24)
    return h.rotate((0, 0, -phi_deg)).translate((RSV_SH[0], RSV_SH[1], 0))


def top_insert(M):
    m = tube(INS_R, INS_R - 1.2, Z_MID1 - Z_TOPI0, Z_TOPI0)                   # glued inside the top of the middle tube
    m = m + tube(SHO_R, SHO_RI, SLEEVE - 2.5, Z_MID1)                          # shoulder: the nose sleeve slides over it
    m = m + tube(INS_R, SHO_RI, 1.6, Z_MID1 - 1.6)                             # web joining the two
    zw = Z_MID1 - 1.6                                                           # 45 deg fillet under the web (prints shoulder-up)
    m = m + revolve([(SHO_RI + 0.05, zw + 0.2), (INS_R - 1.2, zw + 0.2 - (INS_R - 1.2 - SHO_RI - 0.05)), (INS_R - 1.0, zw + 0.2)])
    m = m + bx(SHO_R - 0.1, SHO_R + 0.6, -1.0, 1.0, Z_MID1, Z_MID1 + SLEEVE - 4.0)   # alignment rib (x+)
    # release-servo posts under the mounting tabs (2 self-tapping screws from the servo bag)
    z_tab0 = RSV_Z0 + SV["tab_z"]
    for sy in (1, -1):
        post = bx(RSV_XC - 8.0, RSV_XC + 5.0, sy * (SV["L"] / 2 + 0.3), sy * (SV["L"] / 2 + 5.3), Z_TOPI0, z_tab0)
        post = (post ^ cyl(INS_R - 0.05, 100, Z_TOPI0 - 1)) - cyl(0.8, 12.0, z_tab0 - 10.0, RSV_XC, sy * SV["pitch"] / 2, segs=16)
        m = m + post
    # bolt guide (U-channel) on the inside of the shoulder + slot through the shoulder wall
    g0, g1 = BOLT_IN_X - 0.1, -(SHO_RI + 0.4)
    guide = bx(g1, g0, BOLT_Y - 3.4, BOLT_Y + 3.4, BOLT_Z - 2.9, BOLT_Z + 2.9)
    guide = guide - bx(g1 - 1, g0 + 1, BOLT_Y - 2.2, BOLT_Y + 2.2, BOLT_Z - 1.7, BOLT_Z + 1.7)
    m = m + guide
    m = m - bx(-(SHO_R + 1.0), -(SHO_RI - 0.5), BOLT_Y - 2.2, BOLT_Y + 2.2, BOLT_Z - 1.7, BOLT_Z + 1.7)
    # room for the servo, its horn and the spring link
    m = m - release_servo_solid(0.3)
    m = m - cyl(10.0, 6.0, RHORN_Z - 2.5, RSV_SH[0], RSV_SH[1])
    return register("top_latch_insert", m, M["black"], part="middle",
                    note="PETG. Print shoulder-up, as exported. Glue 36 mm into the top of the middle tube, rib towards the payload door")


def latch_bolt(M, x_shift=0.0):
    m = bx(BOLT_TIP_X, BOLT_IN_X, BOLT_Y - 2.0, BOLT_Y + 2.0, BOLT_Z - 1.5, BOLT_Z + 1.5)
    m = m + bx(BOLT_IN_X - 0.5, BOLT_IN_X + 1.6, BOLT_Y - 3.0, BOLT_Y + 3.0, BOLT_Z - 1.5, BOLT_Z + 1.5)    # stop flange
    m = m - cyl(0.45, 6.0, BOLT_Z - 3.0, BOLT_IN_X + 0.8, BOLT_Y, segs=16)                              # spring-link hole
    a = 1.6 * math.sqrt(2.0)                       # 45 deg bevel on the top outer edge: the nose sleeve pushes it in
    m = m - box(a, 8.0, a).rotate((0, 45, 0)).translate((BOLT_TIP_X, BOLT_Y, BOLT_Z + 1.5))
    return m.translate((x_shift, 0, 0))


def door_solid(theta=0.0):
    """payload door (printed) - curved panel flush with the tube, hinge knuckle at the bottom, latch hole near the top"""
    zc = DOOR_Z0 + DOOR_H / 2
    plate = tube(R - 0.02, RI - 1.05, DOOR_H - 0.8, DOOR_Z0 + 0.4) ^ bx(10, 40, -(DOOR_W / 2 - 0.3), DOOR_W / 2 - 0.3,
                                                                       DOOR_Z0, DOOR_Z0 + DOOR_H)
    for sy in (1, -1):                                                         # notches for the frame's hinge knuckles
        plate = plate - bx(20, 40, sy * 6.2, sy * 12.2, DOOR_Z0 - 1, DHZ + 3.0)
    kn = ycyl(1.7, 12.0, 32).translate((DHX, 0, DHZ)) + bx(DHX - 1.8, DHX, -6.0, 6.0, DHZ - 1.35, DHZ + 2.6)
    m = (plate + kn) - ycyl(0.95, 14.0, 16).translate((DHX, 0, DHZ))
    m = m - xcyl(2.2, 10, 24).translate((R, 0, LATCH_Z))                       # latch shaft hole
    m = m - xcyl(4.6, 2.0, 32).translate((R - 0.02, 0, LATCH_Z))               # counterbore for the latch knob (flush)
    return m.translate((-DHX, 0, -DHZ)).rotate((0, theta, 0)).translate((DHX, 0, DHZ))


def latch_knob_solid(theta=0.0):
    m = xcyl(4.4, 0.95, 40).translate((R - 0.5, 0, LATCH_Z)) + xcyl(2.0, 4.6, 24).translate((R - 2.75, 0, LATCH_Z))
    m = m - bx(R - 0.4, R + 0.2, -3.2, 3.2, LATCH_Z - 0.5, LATCH_Z + 0.5)             # coin slot
    m = m - bx(R - 5.3, R - 3.4, -2.5, 2.5, LATCH_Z - 2.5, LATCH_Z + 2.5) + bx(R - 5.3, R - 3.4, -1.25, 1.25, LATCH_Z - 1.25, LATCH_Z + 1.25)
    return m.translate((-DHX, 0, -DHZ)).rotate((0, theta, 0)).translate((DHX, 0, DHZ))


def latch_cam_solid(locked=True, theta=0.0):
    arm = bx(R - 4.75, R - 3.55, -2.0, 2.0, LATCH_Z - 2.6, LATCH_Z + 7.0) + xcyl(2.6, 1.2, 32).translate((R - 4.15, 0, LATCH_Z))
    arm = arm - bx(R - 6.0, R - 2.0, -1.35, 1.35, LATCH_Z - 1.35, LATCH_Z + 1.35)            # square socket on the shaft end
    if not locked:
        arm = arm.translate((0, 0, -LATCH_Z)).rotate((90, 0, 0)).translate((0, 0, LATCH_Z))
    return arm.translate((-DHX, 0, -DHZ)).rotate((0, theta, 0)).translate((DHX, 0, DHZ))


def door_frame(M):
    zc = DOOR_Z0 + DOOR_H / 2
    m = tube(INS_R, 25.0, DOOR_H + 10.0, DOOR_Z0 - 4.0) ^ bx(10, 40, -(DOOR_W / 2 + 6), DOOR_W / 2 + 6, 0, 1000)
    m = m - bx(10, 40, -(DOOR_W / 2 - 2), DOOR_W / 2 - 2, DOOR_Z0, DOOR_Z0 + DOOR_H - 2)                # opening, 2 mm ledges
    m = m - (tube(27.7, RI - 1.15, DOOR_H + 0.4, DOOR_Z0 - 0.2) ^ bx(10, 40, -(DOOR_W / 2 + 0.2), DOOR_W / 2 + 0.2, 0, 1000))  # rebate
    for sy in (1, -1):                                                                 # hinge knuckles + arms
        kn = ycyl(1.7, 5.6, 32).translate((DHX, sy * 9.2, DHZ)) + bx(24.6, DHX, sy * 6.4, sy * 12.0, DOOR_Z0 + 0.2, DHZ + 1.2)
        kn = kn + (bx(24.6, 26.3, sy * 6.4, sy * 12.0, DOOR_Z0 - 4.0, DOOR_Z0 + 0.5) ^ cyl(INS_R, 20, DOOR_Z0 - 10))
        m = m + (kn - ycyl(0.9, 8.0, 16).translate((DHX, sy * 9.2, DHZ)))
    return register("payload_door_frame", m, M["grey"], part="middle",
                    note="PETG, print upright as exported. Epoxy inside the middle tube behind the door window (drill guide marks it); hinge pin = 1.75 mm filament")


def payload_door_parts(M):
    register("payload_door", door_solid(), M["orange"], part="middle",
             note="PETG, print standing on its hinge end as exported, with a brim. Hinge pin: 22 mm of 1.75 mm filament, ends melted/glued")
    register("payload_door_latch_knob", latch_knob_solid(), M["black"], part="middle", print_rot=(0, 90, 0),
             note="Quarter-turn latch: knob from outside, coin slot. Print head-down, 100% infill")
    register("payload_door_latch_cam", latch_cam_solid(True), M["black"], part="middle", print_rot=(0, 90, 0),
             note="Push onto the knob's square end from inside + drop of CA. Arm UP = locked, sideways = open")


def hatch_cut():
    """the battery-hatch opening (+y side), through the bottom tube and the av-bay coupler"""
    return bx(-HATCH_X, HATCH_X, 15.0, 40.0, HATCH_Z0, HATCH_Z1)


def hatch_door_solid():
    """battery-hatch door: a curved panel ON the tube, 2 mm larger than the opening all round (so no gap anywhere), its
    outer half stepped in 0.6 mm at the edges; inside: two hooks at the top, a pad on a rib that holds the pack, and the
    boss for the quarter-turn latch on the rod line"""
    z0, z1, w = HATCH_Z0 - HD_M, HATCH_Z1 + HD_M, HATCH_X + HD_M
    m = tube(HD_R0 + 0.6, HD_R0, z1 - z0, z0) ^ bx(-w, w, 0.0, 40.0, z0, z1)
    m = m + (tube(HD_R0 + HD_T, HD_R0 + 0.55, z1 - z0 - 1.2, z0 + 0.6) ^ bx(-(w - 0.6), w - 0.6, 0.0, 40.0, z0, z1))
    zc = BATT["z0"] + BATT["l"] / 2
    m = m + bx(-0.8, 0.8, PAD_Y + 1.0, HD_R0 + 0.4, zc - 12.0, zc + 12.0) + bx(-6.0, 6.0, PAD_Y, PAD_Y + 1.2, zc - 12.0, zc + 12.0)
    hook = M3.batch_hull([bx(HD_R0 - 0.3, HD_R0 + 0.3, -2.5, 2.5, HATCH_Z1 - 6.0, HATCH_Z1 - 0.4),
                          bx(25.1, 25.4, -2.5, 2.5, HATCH_Z1 - 2.6, HATCH_Z1 - 0.4)])
    hook = hook + bx(25.1, 26.15, -2.5, 2.5, HATCH_Z1 - 2.6, HATCH_Z1 + 3.5)
    for sx in (1, -1):
        m = m + polar(hook, 90.0 - sx * math.degrees(math.asin(HOOK_X / R)))
    m = m + ycyl(3.3, HD_R0 + 0.3 - (HL_Y1 + 0.3), 32).translate((0, (HD_R0 + 0.3 + HL_Y1 + 0.3) / 2, HL_Z))
    m = m - ycyl(2.2, 12.0, 24).translate((0, HD_R0, HL_Z))
    ro = HD_R0 + HD_T
    m = m - ycyl(4.6, 2.0, 32).translate((0, ro - 0.97 + 1.0, HL_Z))               # counterbore: knob head flush
    return m


def hatch_latch_knob():
    ro = HD_R0 + HD_T
    m = ycyl(4.4, 0.95, 40).translate((0, ro - 0.475, HL_Z))
    m = m + ycyl(2.0, ro - 0.95 - (HL_Y1 + 0.05), 24).translate((0, (ro - 0.95 + HL_Y1 + 0.05) / 2, HL_Z))
    m = m + bx(-1.25, 1.25, HL_Y0, HL_Y1 + 0.15, HL_Z - 1.25, HL_Z + 1.25)       # square end into the cam
    m = m - bx(-3.2, 3.2, ro - 0.4, ro + 0.2, HL_Z - 0.5, HL_Z + 0.5)            # coin slot
    return m


def hatch_latch_cam(locked=True):
    """arm DOWN = locked (behind the catch below the opening); arm towards the middle (sideways) = open"""
    arm = bx(-2.0, 2.0, HL_Y0, HL_Y1, HL_Z - 7.5, HL_Z + 2.6) + ycyl(2.6, HL_Y1 - HL_Y0, 32).translate((0, (HL_Y0 + HL_Y1) / 2, HL_Z))
    arm = arm - bx(-1.35, 1.35, HL_Y0 - 1.0, HL_Y1 + 1.0, HL_Z - 1.35, HL_Z + 1.35)
    if not locked:
        arm = arm.translate((0, 0, -HL_Z)).rotate((0, 90, 0)).translate((0, 0, HL_Z))
    return arm


def hatch_parts(M):
    register("battery_hatch_door", hatch_door_solid(), M["orange"], part="bottom",
             note="PETG, print standing on its bottom edge as exported, with a brim (no supports). Stick a 20 x 20 mm piece of the 1-2 mm "
                  "foam tape on the pad. Fit: hooks in at the top, slide up, swing the bottom in, turn the latch")
    register("battery_hatch_latch_knob", hatch_latch_knob(), M["black"], part="bottom", print_rot=(90, 0, 0),
             note="Quarter-turn latch: knob from outside, coin slot, flush. Print head-down, 100% infill")
    register("battery_hatch_latch_cam", hatch_latch_cam(True), M["black"], part="bottom", print_rot=(90, 0, 0),
             note="Push onto the knob's square end from inside + drop of CA. Arm DOWN = locked, towards the middle = open")


def payload_wall(M):
    m = cyl(INS_R, BULK_T, Z_WALL0) + tube(INS_R, INS_R - 1.2, 13.0, Z_WALL1 - 1.0)      # glue skirt on the parachute side
    m = m + tube(6.8, 5.0, 8.5, Z_WALL1 - 0.5)                                   # locates the ejection spring
    zt = Z_WALL1
    bridge = box(18.0, 5.0, 9.5, 0, 18.5, zt + 4.25) - box(12.0, 6.0, 5.0, 0, 18.5, zt + 2.0)
    m = m + bridge
    m = m - polar(bx(INS_R - 4.5, INS_R + 1.0, -3.0, 3.0, Z_WALL0 - 1, Z_WALL1 + 14), 180)   # release-servo lead notch
    return register("payload_wall", m, M["white"], part="middle",
                    note="PETG, disc on the bed as exported, no supports. Epoxy into the middle tube, underside 160 mm from its bottom end: carries the parachute load")


def spring_piston(M):
    z0 = Z_PISTON
    m = cyl(RI - 0.6, 3.0, z0) + tube(RI - 0.7, RI - 1.8, 11.5, z0 - 10.0)
    m = m + tube(SPR["od"] / 2 + 1.6, SPR["od"] / 2 + 0.4, 5.5, z0 - 4.0)
    m = m - polar(bx(RI - 7.5, RI + 1.0, -5.0, 5.0, z0 - 11, z0 + 4), 90)          # shock-cord notch
    m = m - polar(bx(RI - 4.0, RI + 1.0, -3.0, 3.0, z0 - 11, z0 + 4), 180)         # release-servo lead notch
    return register("spring_piston", m, M["white"], part="middle", print_rot=(180, 0, 0),
                    note="Print flat face down as exported, no supports. Sits on the spring, under the parachute")


# ======================================================================================
# BOTTOM PART
# ======================================================================================
def avbay_coupler(M):
    zt = SH_TOP + BULK_T
    iw = 1.2
    prof = [(INS_R - iw, Z_AV0), (INS_R, Z_AV0), (INS_R, Z_BAND0), (R, Z_BAND0), (R, Z_MID0), (INS_R, Z_MID0),
            (INS_R, zt), (0.0, zt), (0.0, SH_TOP), (INS_R - WALL, SH_TOP), (INS_R - WALL, Z_BAND0 + 3.0),
            (INS_R - iw, Z_BAND0 - 2.0)]
    m = revolve(prof)
    for a in (120.0, 240.0):     # lightening windows at 180 / 300 deg (the one at 60 deg gave way to the battery hatch)
        w = (tube(INS_R + 1, INS_R - iw - 1, 52.0, Z_AV0 + 22.0, segs=96) ^ polar(box(60, 34, 60, 30, 0, Z_AV0 + 48.0), a + 60.0))
        m = m - w
    # battery hatch: the opening, and a flat catch below it for the latch cam (above the sled's disc)
    m = m - hatch_cut()
    m = m + (bx(-8.0, 8.0, HC_Y, 27.0, Z_AV0 + 3.6, HATCH_Z0) ^ cyl(INS_R - 0.05, 20.0, Z_AV0, segs=96))
    # middle-part joint: 2 x M3 radial screws into nut pockets inside the shoulder
    ri = INS_R - WALL
    for a in JOINT_ANG:
        wedge = xz_plate([(ri - 5.5, JOINT_Z + 4.0), (ri + 1.0, JOINT_Z + 4.0), (ri + 1.0, JOINT_Z + 10.5)], 7.6)   # 45 deg, prints bulkhead-down
        nut = (box(6.0, 8.0, 9.0, ri - 2.0, 0, JOINT_Z) + wedge - box(2.8, 5.9, 6.5, ri - 3.8, 0, JOINT_Z) -
               box(2.8, 5.9, 6.5, ri - 2.6, 0, JOINT_Z)) ^ cyl(INS_R, 40, JOINT_Z - 20)
        m = m + polar(nut, a)
        m = m - polar(xcyl(1.65, 12, 16).translate((INS_R - 2, 0, JOINT_Z)), a)
    # payload mounting holes (4 x M3 on a 20 mm square) + release-servo lead slot
    for x, y in ((10, 10), (-10, 10), (10, -10), (-10, -10)):
        m = m - cyl(1.65, 10.0, SH_TOP - 2, x, y, segs=16)
    m = m - bx(-25.5, -20.5, -4.5, 4.5, SH_TOP - 1, zt + 1)
    for ang in RADIAL_SCREW_ANG:
        m = m - polar(xcyl(1.65, 12).translate((INS_R, 0, Z_AV0 + 12)), ang)
    m = m - polar(box(8.0, 7.0, 20.0, INS_R - 1.0, 0, SW_Z), SW_ANG)
    for ang in STATIC_PORT_ANG:
        m = m - polar(xcyl(1.0, 8, 16).translate((INS_R, 0, Z_AV0 + 40)), ang)
    m = m - box(2.0, 2.0, 2.2, 0, R - 0.6, Z_BAND0 + 2.9)                          # alignment notch (+Y, lug side)
    return register("avbay_coupler", m, M["white"], print_rot=(180, 0, 0), part="bottom",
                    note="Print UPSIDE-DOWN (bulkhead on the bed), 4 walls, 25% gyroid. Its bulkhead is the payload-bay floor")


def avbay_sled(M):
    z0 = Z_AV0
    rb = INS_R - WALL - 0.25
    plate = box(38.0, PLATE_T, BH + 9.0, 0, PLATE_Y, z0 + 2.5 + (BH + 9.0) / 2)     # reaches up to the antenna shelf
    groups = {}
    for p in MECH["tht_pins"]:
        groups.setdefault(p["ref"], []).append(board_to_rocket(p["x"], p["y"]))
    for ref, pts in groups.items():
        xs, zs = [q[0] for q in pts], [q[1] for q in pts]
        mg = 1.7
        plate = plate - box(max(xs) - min(xs) + 2 * mg, 10.0, max(zs) - min(zs) + 2 * mg,
                            (max(xs) + min(xs)) / 2, PLATE_Y, (max(zs) + min(zs)) / 2)
    for (xa, xb) in ((-0.9, 11.1), (-17.0, -7.4)):
        for (za, zb) in ((22.0, 44.0), (48.0, 70.0)):
            plate = plate - box(xb - xa, 10.0, zb - za, (xa + xb) / 2, PLATE_Y, z0 + (za + zb) / 2)
    m = cyl(rb, 3.0, z0) + plate
    # GPS antenna shelf just above the board's U.FL end (the Adafruit 2461 lead is only 50 mm long)
    plate_top = z0 + 2.5 + BH + 9.0
    m = m + bx(GPS_X0 - 1.0, GPS_X1 + 1.0, PLATE_Y - 1.0, PLATE_Y + 1.0, plate_top - 0.5, GPS_SHELF_Z)   # plate extension
    shelf = bx(GPS_X0, GPS_X1, PLATE_Y - 1.0, GPS_Y1, GPS_SHELF_Z - 2.0, GPS_SHELF_Z)
    shelf = shelf - bx(GPS_X0 + 4.0, GPS_X1 - 4.0, PLATE_Y + 4.0, GPS_Y1 + 1.0, GPS_SHELF_Z - 3.0, GPS_SHELF_Z + 1.0)
    span = GPS_Y1 - (PLATE_Y + 1.0)
    tri = xz_plate([(PLATE_Y + 0.5, GPS_SHELF_Z - 2.0 - span - 0.5), (PLATE_Y + 0.5, GPS_SHELF_Z - 1.0), (GPS_Y1, GPS_SHELF_Z - 1.0)], 1.6)
    tri = tri.rotate((0, 0, 90))                                  # triangle in the y-z plane, 1.6 mm thick along x
    for gx in (GPS_X0 + 1.0, GPS_X1 - 1.0):
        shelf = shelf + tri.translate((gx, 0, 0))
    m = m + shelf
    for h in MECH["holes"]:
        x, z = board_to_rocket(h["x"], h["y"])
        L = STANDOFF_H + 0.5
        m = m + ycyl(2.6, L, 32).translate((x, PCB_Y_BACK - L / 2, z))
        m = m - ycyl(1.05, 3 * L, 16).translate((x, PCB_Y_BACK - L, z))
    # battery pocket behind the Pico (multi-flight): the pack slides in and out through the battery hatch (+y); the hatch
    # door's pad holds it against a backing wall that keeps it off the Pico, and the 45 deg ledge carries it in flight.
    # The tray plate has a window the pack passes through; the inner side walls start above the servo plugs
    ty = BATT["y0"] + BAY["t"] + 0.8
    th = BAY["l"] + 10.0
    zb0, zb1 = BATT["z0"] - 2.0, BATT["z0"] + BATT["l"] + 2.0
    ybw = BATT["y0"] - 1.6                                            # backing wall 2.4 .. 4.0 (pack from 4.5)
    tray = box(BAY["w"] + 5.0, 1.6, th, 0, ty, z0 + 2.5 + th / 2)
    tray = tray - bx(-(BATT["w"] / 2 + 0.5), BATT["w"] / 2 + 0.5, ty - 2.0, ty + 2.0, BATT["z0"] - 1.0, BATT["z0"] + BATT["l"] + 1.5)
    for sx in (1, -1):
        xw = sx * (BAY["w"] / 2 + 0.8)
        tray = tray + box(1.6, 6.0, th, xw, ty - 3.6, z0 + 2.5 + th / 2)
        tray = tray + bx(xw - 0.8, xw + 0.8, ybw, ty, zb0, zb1)
    tray = tray + bx(-(BAY["w"] / 2 + 1.6), BAY["w"] / 2 + 1.6, ybw, ybw + 1.6, zb0, zb1)
    # battery ledge: a 45 deg wedge growing out of the tray wall (prints without supports, leaves room for the servo leads)
    y_w = ty - 0.5
    ledge = xz_plate([(11.0, BATT["z0"]), (y_w, BATT["z0"]), (y_w, BATT["z0"] - (y_w - 11.0))], BAY["w"] - 1.0).rotate((0, 0, 90))
    tray = tray + ledge
    m = m + (tray ^ cyl(rb, 200, z0))
    for ang in RADIAL_SCREW_ANG:
        nt = box(5.9, 6.0, 2.8, rb - 3.2, 0, z0 + 12)
        boss = (box(5.0, 9.0, 12.0, rb - 2.6, 0, z0 + 8.0) - nt - xcyl(1.65, 10).translate((rb - 3, 0, z0 + 12)))
        m = m - polar(nt, ang) - polar(xcyl(1.65, 10).translate((rb - 3, 0, z0 + 12)), ang)
        m = m + (polar(boss, ang) ^ cyl(rb, 30, z0))
    m = m - bx(4.0, 19.0, -9.0, 2.5, z0 - 2.0, z0 + 6.0)          # pass-through for the 6 servo leads from below
    return register("avbay_sled", m, M["grey"], part="bottom",
                    note="Print with the bulkhead disc on the bed. 4 x M2.5x8 self-tapping screws hold the PCB")


def tvc_holder(M):
    # closed top: 2.2 mm roof, a 1.9 mm deep recess for the 25 mm penny washer, and 0.3 mm of play above the motor
    # (the F35's rim bears on the ledge round the recess, a 24 mm motor on the washer)
    z1 = Z_MOTOR0 + MOTOR_L + 0.3 + 1.9 + 2.2
    zc = z1 - 2.2
    m = revolve([(HOLD_RI, 0.0), (HOLD_R, 0.0), (HOLD_R, z1), (0.0, z1), (0.0, zc), (12.6, zc),
                 (12.6, zc - 1.9), (HOLD_RI, zc - 1.9)])
    for sy in (1, -1):
        m = m + ycyl(3.4, 1.1, 32).translate((0, sy * (HOLD_R + 0.15), Z_PIVOT))
    for sy in (1, -1):
        m = m - ycyl(1.25, 3.0, 16).translate((0, sy * (HOLD_R + 0.15), Z_PIVOT))
    tab = (bx(HOLD_R - 0.85, PR2[0], PR2[1] - 2.0, PR2[1] + 2.0, HOLDER_TAB_Z - 2.0, HOLDER_TAB_Z + 2.0)
           + cyl(TAB_BOSS_R, 4.0, HOLDER_TAB_Z - 2.0, PR2[0], PR2[1], segs=32)
           + box(5.0, PR2[1] + 2.0, 4.0, HOLD_R + 0.8, PR2[1] / 2, HOLDER_TAB_Z))
    tab = tab - cyl(HOLD_R - 0.6, 10, HOLDER_TAB_Z - 5)
    m = m + tab - cyl(0.7, 6.0, HOLDER_TAB_Z - 3.0, PR2[0], PR2[1], segs=16)
    for a in (45, 225):
        m = m + polar(box(3.0, 5.0, 3.0, HOLD_R + 1.2, 0, 4.0), a)
    return register("tvc_motor_holder", m, M["black"], part="tvc",
                    note="PETG/ASA. Press/glue an M10 x 25 mm steel penny washer into the top recess (burn-through shield)")


def tvc_ring(M):
    h = 8.0
    m = tube(RING_R, RING_RI, h, Z_PIVOT - h / 2)
    for sx in (1, -1):
        m = m + xcyl(3.4, 2.4, 32).translate((sx * (RING_R + 0.9), 0, Z_PIVOT))
    for sy in (1, -1):
        m = m + ycyl(3.0, 0.8, 32).translate((0, sy * (RING_RI - 0.1), Z_PIVOT))
    m = m - xcyl(1.25, 2 * RING_R + 8, 16).translate((0, 0, Z_PIVOT))
    m = m - ycyl(1.65, 2 * RING_R + 8, 16).translate((0, 0, Z_PIVOT))
    m = m - cyl(HOLD_R + 0.6, 40, Z_PIVOT - 20)
    tab = (bx(PR1[0] - 2.0, PR1[0] + 2.0, RING_R - 1.0, PR1[1], Z_PIVOT - 1.5, Z_PIVOT + 1.5)
           + cyl(TAB_BOSS_R, 3.0, Z_PIVOT - 1.5, PR1[0], PR1[1], segs=32)
           + box(5.0, 6.0, 3.0, PR1[0] - 2.0, RING_R - 0.5, Z_PIVOT))
    m = m + tab - cyl(0.7, 6.0, Z_PIVOT - 3.0, PR1[0], PR1[1], segs=16)
    return register("tvc_gimbal_ring", m, M["orange"], part="tvc", note="PETG")


def tvc_frame(M):
    ro = FRAME_R
    ri = ro - 1.0
    m = tube(ro, ri, FRAME_TOP, 0.0)
    windows = [(22.0, 40.0), (54.0, 94.0), (105.0, 121.0), (133.0, 149.0)]   # 54: the holder's pushrod tab swings here
    for z0, z1 in windows:
        w = tube(ro + 1.0, ri - 1.0, z1 - z0, z0, segs=96)
        for a in GROOVE_ANG:
            w = w - polar(box(14.0, 9.0, z1 - z0 + 2.0, ro - 2.0, 0, (z0 + z1) / 2), a)
        m = m - w
    # longerons carrying the 4 tab-servo leads in outside grooves (each lead comes in through its fin's lead channel)
    for a in GROOVE_ANG:
        lon = polar(bx(ro - 3.0, ro, -3.5, 3.5, CAB_Z0 - 4.0, FRAME_TOP), a) ^ cyl(ro, 300, -1)
        m = m + lon
        m = m - polar(bx(ro - 1.6, ro + 1.0, -2.1, 2.1, CAB_Z0 - 2.0, FRAME_TOP + 1.0), a)
    m = m + tube(ro, FRAME_BOT_RI, 4.0, 0.0)
    for sx in (1, -1):
        post = box(ri - (RING_R + 2.7) + 0.8, 8.0, 12.0, sx * ((ri + RING_R + 2.7) / 2 + 0.4), 0, Z_PIVOT)
        m = m + post
    m = m - xcyl(1.65, 2 * ro + 4, 16).translate((0, 0, Z_PIVOT))

    def bar_x(y0, z0):
        return box(2 * ro, 2.2, 5.0, 0, y0, z0) ^ cyl(ri + 0.8, 200, -10)

    def bar_y(x0, z0):
        return box(2.2, 2 * ro, 5.0, x0, 0, z0) ^ cyl(ri + 0.8, 200, -10)
    tab_y = -(SV["H"] - SV_SHAFT_R) + SV["tab_z"] - 1.1
    c1 = SV1_Z + SV["shaft_off"] - SV["L"] / 2
    c2 = SV2_Z + SV["shaft_off"] - SV["L"] / 2
    for dz in (-1, 1):
        zz = c1 + dz * SV["pitch"] / 2
        b = bar_x(tab_y, zz) - box(SV["W"] + 0.6, 10, 30, 0, tab_y, c1)
        b = b - ycyl(0.8, 8, 12).translate((0, tab_y, zz))
        b = b - cyl(2.2, 12.0, zz - 6, PR2[0], PR2[1], segs=16)
        m = m + b
        zz2 = c2 + dz * SV["pitch"] / 2
        b2 = bar_y(tab_y, zz2) - box(10, SV["W"] + 0.6, 30, tab_y, 0, c2)
        b2 = b2 - xcyl(0.8, 8, 12).translate((tab_y, 0, zz2))
        b2 = b2 - cyl(2.2, 12.0, zz2 - 6, PR1[0], PR1[1], segs=16)
        m = m + b2
    for a in TAIL_SCREW_ANG:
        m = m - polar(xcyl(1.65, 8, 16).translate((ro - 1.5, 0, TAIL_SCREW_Z)), a)
        m = m + polar((box(6.0, 8.0, 8.0, ri - 2.0, 0, TAIL_SCREW_Z) - box(2.8, 5.9, 6.5, ri - 2.6 - 1.2, 0, TAIL_SCREW_Z) -
                       box(2.8, 5.9, 6.5, ri - 2.6, 0, TAIL_SCREW_Z) - xcyl(1.65, 12, 16).translate((ri, 0, TAIL_SCREW_Z)))
                      ^ cyl(ro, 40, 0), a)
    return register("tvc_frame", m, M["grey"], part="tvc", note="PETG, print upright; supports only under the servo bars")


def retainer_solid(lip_r):
    z0 = Z_MOTOR0 - 1.5
    m = tube(HOLD_R + 3.4, HOLD_R + 0.3, 13.0, z0) + tube(HOLD_R + 3.4, lip_r, 1.5, z0)
    for a in (45, 225):
        m = m - polar(box(4.0, 5.6, 7.0, HOLD_R + 1.4, 0, z0 + 1.5 + 3.5 + 4.5), a)
        m = m - polar(box(4.0, 9.0, 3.6, HOLD_R + 1.4, 3.0, 4.0), a)
    return m


RET_LIP_R = 11.0          # 29 mm retainer: 22 mm opening, the lip holds the F35 by its case (3.5 mm of lip)
RET24_LIP_R = 8.0         # 24 mm retainer: 16 mm opening, holds a 24 mm motor in the adapter sleeve
ADAPT_RO = MOTOR_D / 2 - 0.05             # adapter sleeve: slides into the 29 mm bore like the F35 does
ADAPT_RI = 12.0 + 0.2                     # 24 mm motor + 0.2 mm
D_MOTOR_L = 70.0                          # TSP D20 / D12 length; the spacer fills the rest of the 95 mm bore


def retainer(M):
    return register("tvc_motor_retainer", retainer_solid(RET_LIP_R), M["orange"], part="tvc",
                    note="Twist-lock: push up over the lugs and turn 45 deg. For the 29 mm F35")


def motor_adapter(M):
    """24 mm motors (D20, E20) in the 29 mm mount: a sleeve as long as the bore, their own retainer with a smaller
    opening, and a spacer above the 70 mm D motors so that every motor sits against the penny washer"""
    sleeve = tube(ADAPT_RO, ADAPT_RI, MOTOR_L - 0.2, Z_MOTOR0)
    register("tvc_motor_adapter_24mm", sleeve, M["orange"], part="tvc", group="adapter",
             note="24 mm motors only: slide it into the motor holder, then the motor into it. PETG, 3 walls")
    register("tvc_motor_retainer_24mm", retainer_solid(RET24_LIP_R), M["orange"], part="tvc", group="adapter",
             note="24 mm motors only (with the adapter sleeve): its 16 mm opening holds the 24 mm motor")
    spacer = cyl(ADAPT_RI - 0.3, MOTOR_L - D_MOTOR_L - 0.4, Z_MOTOR0 + D_MOTOR_L, segs=64)
    register("tvc_motor_spacer_D", spacer, M["orange"], part="tvc", group="adapter",
             note="D20 / D12 only (70 mm long): goes into the sleeve first, above the motor. 3 walls, 30 %")


# ---------------- fins, legs, control tabs and their servos (built for one fin in the local frame) ----------------
def seg_cyl_xz(p0, p1, r, segs=48):
    """cylinder of radius r between two points of the x-z plane (y = 0)"""
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dz)
    return M3.cylinder(L, r, r, segs).rotate((0, math.degrees(math.atan2(dx, dz)), 0)).translate((p0[0], 0, p0[1]))


def fin_local():
    """Normal FT_UP-thick fin with a half-round leading edge. Only the bottom band (tab hinge, servo, lead channel) is
    FT thick; a smooth wedge fairs it into the thin fin (shortened near the tip so that it stays clear of the leading
    edge). Below the tail the band ends in a tapered trailing edge and the leg tapers to its foot. Inside: the tab
    bay, the servo pocket (open at the tip), the shoulder + screw holes for the servo's mounting tabs, the root slot
    for the tab's pin, the lead channel and the lead groove in the tip"""
    cr, ct = FIN["root_chord"], FIN["tip_chord"]
    x_root = CAN_RO - 0.6
    h = FT_UP / 2
    ax0, az0, ax1, az1 = x_root, float(cr), TIP_R, float(ct)
    L = math.hypot(ax1 - ax0, az1 - az0)
    ux, uz = (ax1 - ax0) / L, (az1 - az0) / L
    nx, nz = uz, -ux                                          # inward normal of the leading edge
    a0 = (ax0 + h * nx, az0 + h * nz)
    a1 = (ax1 + h * nx, az1 + h * nz)
    slope = (a1[1] - a0[1]) / (a1[0] - a0[0])
    z_root = a0[1] + (ax0 - a0[0]) * slope
    z_tip = a0[1] + (ax1 - a0[0]) * slope
    # 1. the thin fin over the whole planform (its lower edge hidden inside the band): one convex hull of the plate
    #    and a cylinder along its leading edge, so the half-round edge blends into the faces without slivers
    ext = 20.0
    thin = M3.batch_hull([xz_plate([(x_root, 0.3), (TIP_R, 0.3), (TIP_R, z_tip), (x_root, z_root)], FT_UP),
                          seg_cyl_xz((a0[0] - ext * ux, a0[1] - ext * uz), (a1[0] + ext * ux, a1[1] + ext * uz), h, 48)])
    f = thin ^ bx(x_root, TIP_R, -FT, FT, 0.3, cr + 20.0)
    # 2. the 15 mm band and its wedge; the wedge ends RAMP_L above the band, or 1 mm short of the leading-edge
    #    rounding where the chord gets short near the tip
    le_z = lambda x: cr + (ct - cr) * (x - x_root) / (TIP_R - x_root)
    z_ramp = BAND_TOP + RAMP_L
    x_k = x_root + (cr - (z_ramp + 2 * h + 1.0)) * (TIP_R - x_root) / (cr - ct)
    hs = h - 0.05
    pieces = [bx(x_root, TIP_R, -FT / 2, FT / 2, 0.0, BAND_TOP),
              bx(x_root, x_k, -hs, hs, z_ramp - 0.01, z_ramp)]
    z_tip_ramp = le_z(TIP_R) - 2 * h - 1.0
    if x_k < TIP_R:
        pieces.append(bx(TIP_R - 0.01, TIP_R, -hs, hs, z_tip_ramp - 0.01, z_tip_ramp))
    f = f + M3.batch_hull(pieces)
    # 2b. the servo housing: the band's outer part is HT thick (tapering from FT over HX_TAPER inboard), with its own
    #     wedge up to the thin fin so the thicker band is faired exactly like the rest
    hp = [bx(HX0, TIP_R, -HT / 2, HT / 2, 0.0, BAND_TOP),
          bx(HX0 - HX_TAPER, HX0 - HX_TAPER + 0.01, -FT / 2, FT / 2, 0.0, BAND_TOP)]
    if x_k > HX0 - HX_TAPER:
        hp.append(bx(HX0 - HX_TAPER, min(x_k, TIP_R), -hs, hs, z_ramp - 0.01, z_ramp))
    if x_k < TIP_R:
        hp.append(bx(TIP_R - 0.01, TIP_R, -hs, hs, z_tip_ramp - 0.01, z_tip_ramp))
    f = f + M3.batch_hull(hp)
    # 3. tapered trailing edge below the band, from the tab bay out to the leg's sleeve (the tab has its own); the bay
    #    cut trims it
    f = f + M3.batch_hull([bx(BAY_X1 - 0.3, SL_X0 - 0.2, -HT / 2, HT / 2, -0.01, 0.5),
                           bx(BAY_X1 - 0.3, SL_X0 - 0.2, -TE_T / 2, TE_T / 2, -TE_EXT, -TE_EXT + 0.5)])
    # 4. the tongue the replaceable leg slides onto (solid; bolt hole across it)
    f = f + bx(TG_X0, TG_X1, -TG_Y / 2, TG_Y / 2, -TG_H, 0.5)
    f = f - ycyl(1.7, HT + 2.0, 24).translate((LEG_BOLT_X, 0, LEG_BOLT_Z))
    s = SV
    # tab bay through the whole thickness (and everything below it), round-topped about the hinge line
    f = f - bx(BAY_X0, BAY_X1, -FT, FT, -TE_EXT - 2.0, HINGE_Z)
    f = f - xcyl(BAY_R, BAY_X1 - BAY_X0, 64).translate(((BAY_X0 + BAY_X1) / 2, 0, HINGE_Z))
    # servo pocket and the slot for its mounting tabs, open at the fin tip
    f = f - bx(SVX0 - 0.2, TIP_R + 1.0, -(s["W"] / 2 + 0.2), s["W"] / 2 + 0.2, SV_Z0 - 0.2, SV_Z0 + s["L"] + 0.2)
    f = f - bx(SV_TAB_X0 - 0.1, TIP_R + 1.0, -((s["W"] - 1) / 2 + 0.3), (s["W"] - 1) / 2 + 0.3,
               SV_ZC - s["tab_L"] / 2 - 0.3, SV_ZC + s["tab_L"] / 2 + 0.3)
    for dz in (-1, 1):   # 2 x M2 x 6 self-tapping screws into blind holes (the lower one ends 0.35 mm short of the tab bay)
        f = f - xcyl(0.8, SCREW_HOLE_D, 12).translate((SV_TAB_X0 + 0.05 - SCREW_HOLE_D / 2, 0, SV_ZC + dz * s["pitch"] / 2))
    # slot at the fin root for the tab's printed pivot pin (open downwards: the tab is pushed up into the bay)
    f = f - xcyl(PIN_R + 0.15, BAY_X0 - CAN_RO, 24).translate(((CAN_RO + 0.35 + BAY_X0 + 0.1) / 2, 0, HINGE_Z))
    f = f - bx(CAN_RO + 0.35, BAY_X0 + 0.1, -(PIN_R + 0.15), PIN_R + 0.15, -1.0, HINGE_Z)
    # lead channel from the fin tip to the root and on through the can and tube (the plug is pushed through it)
    f = f - bx(CAN_RI - 3.0, TIP_R + 1.0, -CH_W / 2, CH_W / 2, CH_Z0, CH_Z1)
    # groove in the fin tip from the servo pocket up to the lead channel: the lead lies in it below the tip surface
    f = f - bx(TIP_R - LEAD_GROOVE_D, TIP_R + 1.0, -LEAD_GROOVE_W / 2, LEAD_GROOVE_W / 2, SV_Z0 + s["L"], CH_Z0 + 0.5)
    return f


def leg_local():
    """replaceable leg (tough PLA) in the fin-local frame: a sleeve flush with the 17 mm housing that slides up over the
    fin can's tongue, one M3 x 18 button-head bolt across (head and nut sunk 0.8 mm into the side walls, the nut in a hex
    pocket so one key tightens it), a 4.5 mm boat-tail down to a 6 x 9.2 mm post and the foot 30 mm below the tail.
    The top of the post is the weakest section of the whole leg / tongue / housing chain"""
    sl = bx(SL_X0, TIP_R, -HT / 2, HT / 2, SL_Z0, 0.0)
    sl = sl + M3.batch_hull([bx(SL_X0, TIP_R, -HT / 2, HT / 2, SL_Z0, SL_Z0 + 0.01),
                             bx(POST_X0, POST_X1, -POST_T / 2, POST_T / 2, POST_Z1 - 0.01, POST_Z1)])
    sl = sl + M3.batch_hull([bx(POST_X0, POST_X1, -POST_T / 2, POST_T / 2, FOOT_Z + 0.6, POST_Z1),
                             bx(POST_X0 + 0.6, POST_X1 - 0.6, -POST_T / 2 + 0.6, POST_T / 2 - 0.6, FOOT_Z, FOOT_Z + 0.6)])
    c = LEG_CLR
    sl = sl - bx(TG_X0 - c, TG_X1 + c, -(TG_Y / 2 + c), TG_Y / 2 + c, -TG_H - c, 1.0)
    sl = sl - ycyl(1.7, HT + 2.0, 24).translate((LEG_BOLT_X, 0, LEG_BOLT_Z))
    sl = sl - ycyl(3.1, 2 * LEG_RECESS, 32).translate((LEG_BOLT_X, HT / 2, LEG_BOLT_Z))            # button head (5.7 mm)
    sl = sl - ycyl(5.75 / math.sqrt(3), 2 * LEG_RECESS, 6).translate((LEG_BOLT_X, -HT / 2, LEG_BOLT_Z))   # M3 nut, 5.5 mm A/F
    return sl


def leg_bolt_local():
    """M3 x 18 button-head bolt + nut, in place"""
    y_head = HT / 2 - LEG_RECESS
    b = ycyl(1.5, 18.0, 16).translate((LEG_BOLT_X, y_head - 9.0, LEG_BOLT_Z))
    b = b + ycyl(2.85, 1.65, 24).translate((LEG_BOLT_X, y_head + 0.825, LEG_BOLT_Z))
    y_nut = -HT / 2 + LEG_RECESS
    n = ycyl(5.5 / math.sqrt(3), 2.4, 6).translate((LEG_BOLT_X, y_nut - 1.2, LEG_BOLT_Z)) - ycyl(1.6, 3.0, 16).translate((LEG_BOLT_X, y_nut - 1.2, LEG_BOLT_Z))
    return b + n


def cable_hole_local():
    """where the lead channel crosses the fin-can wall and the bottom tube"""
    return bx(CAN_RI - 3.0, CAN_RO + 1.0, -CH_W / 2, CH_W / 2, CH_Z0, CH_Z1)


def tab_local(delta=0.0):
    """printed control tab: round leading edge about the hinge, tapering to a 2 mm trailing edge; a stock single-arm
    horn (arm cut to a stub) is epoxied into the pocket at its outer end, and the servo spline slides into that horn
    when the servo goes in from the fin tip; a printed pin at the inner end sits in the slot at the fin root.
    +delta moves the trailing edge towards -y (the firmware's sign: away from the next fin anticlockwise)"""
    L = TAB_X1 - TAB_X0
    xc = (TAB_X0 + TAB_X1) / 2
    t = M3.batch_hull([xcyl(TAB_LE_R, L, 64).translate((xc, 0, HINGE_Z)),
                       bx(TAB_X0, TAB_X1, -TE_T / 2, TE_T / 2, -TE_EXT, -TE_EXT + 1.0)])        # thin edge below the tail
    hub0 = SVX0 - SV["spline"] - 0.5
    t = t - xcyl(3.5 + 0.3, TAB_X1 - hub0 + 0.2, 40).translate(((hub0 + TAB_X1 + 0.2) / 2, 0, HINGE_Z))        # hub pocket
    arm0 = HORN_HUB_X1 - HORN_HUB_L - 0.3
    t = t - M3.batch_hull([xcyl(3.0 + 0.3, HORN_ARM_T + 0.6, 32).translate((arm0 + (HORN_ARM_T + 0.6) / 2, 0, HINGE_Z)),
                           xcyl(1.9 + 0.3, HORN_ARM_T + 0.6, 24).translate((arm0 + (HORN_ARM_T + 0.6) / 2, 0, HINGE_Z - HORN_ARM_L))])
    t = t + xcyl(PIN_R, TAB_X0 - (CAN_RO + 0.6) + 0.6, 32).translate(((CAN_RO + 0.6 + TAB_X0 + 0.6) / 2, 0, HINGE_Z))
    return t.translate((0, 0, -HINGE_Z)).rotate((-delta, 0, 0)).translate((0, 0, HINGE_Z))


def tab_servo_local():
    """MG90S inside the fin: output shaft pointing in along the hinge line, body towards the fin tip"""
    s = SV
    body = bx(SVX0, SVX1, -s["W"] / 2, s["W"] / 2, SV_Z0, SV_Z0 + s["L"])
    tabs = bx(SV_TAB_X0, SV_TAB_X0 + s["tab_t"], -(s["W"] - 1) / 2, (s["W"] - 1) / 2, SV_ZC - s["tab_L"] / 2, SV_ZC + s["tab_L"] / 2)
    spline = xcyl(2.4, s["spline"], 20).translate((SVX0 - s["spline"] / 2, 0, HINGE_Z))
    return body + tabs + spline


def tab_horn_local(delta=0.0):
    """stock single-arm horn on the servo spline, arm cut to a stub, glued into the tab (turns with it)"""
    x0 = HORN_HUB_X1 - HORN_HUB_L
    hub = xcyl(3.5, HORN_HUB_L, 32).translate(((x0 + HORN_HUB_X1) / 2, 0, HINGE_Z))
    arm = M3.batch_hull([xcyl(3.0, HORN_ARM_T, 24).translate((x0 + HORN_ARM_T / 2, 0, HINGE_Z)),
                         xcyl(1.9, HORN_ARM_T, 24).translate((x0 + HORN_ARM_T / 2, 0, HINGE_Z - HORN_ARM_L))])
    h = (hub + arm) - xcyl(2.45, HORN_HUB_L + 2, 24).translate(((x0 + HORN_HUB_X1) / 2, 0, HINGE_Z))
    return h.translate((0, 0, -HINGE_Z)).rotate((-delta, 0, 0)).translate((0, 0, HINGE_Z))


def fin_can(M):
    f = FIN
    m = tube(CAN_RO, CAN_RI, f["can_length"], 0.0)
    fin, hole = fin_local(), cable_hole_local()
    for a in FIN_ANG:
        m = m + polar(fin, a)
    for a in FIN_ANG:
        m = m - polar(hole, a)
    # fin #1 marker pip (fin at FIN_ANG[0]) on both faces near the root
    for sy in (1, -1):
        m = m + polar(ycyl(1.5, 1.4, 24).translate((CAN_RO + 14.0, sy * (FT_UP / 2 + 0.4), 85.0)), FIN_ANG[0])
    lug = tube(4.75, 3.4, 25.0, 50.0, segs=40).translate((CAN_RO + 4.4, 0, 0)) + box(5.0, 3.0, 25.0, CAN_RO + 1.6, 0, 62.5)
    # top end cut at 45 deg from the can: the lug then grows out of the can when the fin can prints upside down
    lug = lug - xz_plate([(CAN_RO - 1.0, 75.0 + 1.0), (CAN_RO + 20.0, 75.0 - 20.0), (CAN_RO + 20.0, 90.0), (CAN_RO - 1.0, 90.0)], 20.0)
    m = m + polar(lug, LUG_ANG)
    for a in TAIL_SCREW_ANG:
        m = m - polar(xcyl(1.65, 8, 16).translate((CAN_RO - 0.4, 0, TAIL_SCREW_Z)), a)
    return register("fin_can", m, M["orange"], print_rot=(180, 0, 0), part="bottom",
                    note="PETG, print upside-down (top ring on the bed), 3 walls, 20%, but 100% infill for the last 13 mm (the four leg tongues: "
                         "a height-range modifier in the slicer). Can, 4 thick fins (servo pockets, lead channels) and the tongues the legs bolt to")


def fin_legs(M):
    lg = leg_local()
    inst = [polar(lg, a) for a in FIN_ANG]
    return register("fin_leg", inst[0], M["black"], qty=NF, inst=inst, part="bottom", export=lg, export_rot=(180, 0, 0),
                    note="Tough PLA, 100% infill, print sleeve-rim down as exported (layers across the leg, like the fin can: the post is "
                         "then the weakest section on purpose). Print 2 spares. Slide onto the fin can's tongue, M3 x 18 button head + nut")


def fin_tabs(M):
    t = tab_local(0.0)
    inst = [polar(t, a) for a in FIN_ANG]
    return register("fin_control_tab", inst[0], M["blue"], qty=NF, inst=inst, part="bottom", export=t, export_rot=(0, 90, 0),
                    note="PETG, print standing on its outer end (horn pocket down), no supports. Epoxy a servo horn, arm cut ~7 mm from the hub centre, "
                         "into the pocket; the printed pin at the other end sits in the slot at the fin root")


def upper_lug(M):
    z0 = UPPER_LUG_Z
    m = tube(4.75, 3.4, 25.0, z0, segs=40).translate((CAN_RO + 4.4, 0, 0)) + box(6.5, 4.0, 25.0, R + 2.6, 0, z0 + 12.5)
    m = m - cyl(R, 40.0, z0 - 5)
    return register("upper_launch_lug", polar(m, LUG_ANG), M["black"], part="middle",
                    note="Glue to the MIDDLE tube just above the joint screw, on the lug line: assemble the rocket, slide both lugs on the rod "
                         "while the glue sets (the joint's alignment notch keeps them in line afterwards)")


def camera_pod(M):
    z0, cam, wl = CAM_Z0, CAM_POCKET, 1.2
    rc, w = CAM_RC, CAM_POCKET + 2 * 1.6
    r_in, r_out = rc - cam / 2 - wl, rc + cam / 2 + wl
    zt = z0 + CAM_FLOOR + cam + wl
    base = box(w, r_out - r_in, zt - z0, 0, (r_in + r_out) / 2, (z0 + zt) / 2)
    tip = box(4.0, 0.1, 1.0, 0, R + 2.0, zt + 24.0)
    shell = M3.batch_hull([base, tip])
    shell = shell - box(cam, cam, cam, 0, rc, z0 + CAM_FLOOR + cam / 2)
    shell = shell - cyl(4.6, 6.0, z0 - 3.0, 0, rc, segs=40)
    shell = shell - box(cam - 6.0, 10.0, 8.0, 0, r_out, z0 + CAM_FLOOR + cam - 2.0)
    shell = shell - cyl(R + 0.1, 150.0, zt)
    flange = (tube(R + 1.2, R + 0.1, CAM_WIN_H + 3.0, z0) ^ box(w + 10.0, 40.0, CAM_WIN_H + 3.0, 0, R, z0 + (CAM_WIN_H + 3.0) / 2)) - \
        box(w - 0.1, 40, CAM_WIN_H + 30, 0, R, z0 + CAM_WIN_H / 2)
    m = shell + flange
    m = m - box(cam, cam, cam, 0, rc, z0 + CAM_FLOOR + cam / 2)
    return register("camera_pod", polar(m, 180), M["black"], part="bottom",
                    note=f"Cut a {CAM_WIN_W:.0f} x {CAM_WIN_H:.0f} mm window in the bottom tube (drill guide marks it); glue the flange")


# ======================================================================================
# LAUNCH PAD
# ======================================================================================
HUB_H, LEG_ANG, LEG_D, LEG_L = 60.0, 38.0, 22.0, 600.0
PLATE = 200.0                       # 200 x 200 mm ceramic floor tile: the rocket stands on it on its fin feet
LUG_R = CAN_RO + 4.4                # rod axis distance from the rocket axis
ROCKET_XY = (-LUG_R * math.cos(math.radians(LUG_ANG)), -LUG_R * math.sin(math.radians(LUG_ANG)))  # rocket axis rel. to the rod


def leg_axis_transform(m, k):
    return polar(m.rotate((0, LEG_ANG, 0)).translate((38.0, 0, 30.0)), 120.0 * k + 30.0)


def pad_hub(M):
    m = cyl(55.0, HUB_H, 0.0) + cyl(42.0, 10.0, HUB_H)
    for k in range(3):
        m = m + leg_axis_transform(cyl(LEG_D / 2 + 3.5, 75.0, -75.0, segs=48), k)
    for k in range(3):
        m = m - leg_axis_transform(cyl(LEG_D / 2 + 0.3, 80.0, -82.0, segs=48), k)
        m = m - leg_axis_transform(ycyl(1.8, 60, 16).translate((0, 0, -40.0)), k)
    m = m - box(23.0, 17.0, 60.0, 0, 0, HUB_H + 5.0)
    m = m - ycyl(3.1, 130, 24).translate((0, 0, HUB_H - 10.0))
    for x, y in ((28, 28), (-28, 28), (28, -28), (-28, -28)):
        m = m - cyl(2.2, 40.0, HUB_H - 25, x, y, segs=16)
    for a in (0, 5, 10, 15):
        tick = box(0.8, 1.2, 7.0, 0, 0, 0).translate((0, 0, 32.0)).rotate((0, a, 0)).translate((0, 8.5 + 0.3, HUB_H - 10.0))
        m = m - tick
    return register("pad_hub", m, M["grey"], group="pad", note="PETG, 5 walls, 40% infill, print upright with tree supports in the leg sockets")


def pad_rod_block(M):
    m = box(15.0, 16.0, 46.0, 0, 0, HUB_H + 4.0)
    m = m - ycyl(3.1, 40, 24).translate((0, 0, HUB_H - 10.0))
    m = m - cyl(3.15, 40.0, HUB_H - 4.0, segs=24)
    m = m - xcyl(1.7, 20, 16).translate((0, 0, HUB_H + 18.0)) - box(4.0, 7.2, 3.2, 4.5, 0, HUB_H + 18.0)
    return register("pad_rod_block", m, M["orange"], group="pad", note="Tilts 0-15 deg on an M6 bolt + wing nut; M4 thumb screw clamps the rod")


def pad_rod_stop(M, z):
    m = tube(9.0, 3.15, 12.0, z, segs=48) - xcyl(1.4, 12, 16).translate((5.0, 0, z + 6.0))
    m = m - box(3.0, 5.6, 6.0, 6.5, 0, z + 6.0)
    return register("pad_rod_stop", m, M["orange"], group="pad",
                    note="Only for tilted launches: holds the rocket on the rod with its feet just clear of the tile")


def pad_leg_foot(M):
    ri, ro = LEG_D / 2 + 0.3, LEG_D / 2 + 3.0
    m = revolve([(4.2, 0.0), (17.0, 0.0), (17.0, 4.0), (ro, 4.0), (ro, 30.0), (ri, 30.0), (ri, 5.0), (4.2, 5.0)], 64)
    return register("pad_leg_foot", m, M["black"], qty=3, group="pad", note="Tent peg through the foot holds the pad down")


def rod_cap(M):
    m = cyl(9.0, 30.0, 0.0, r2=6.0, segs=48) - cyl(3.2, 25.0, -1.0, segs=24)
    return register("rod_tip_safety_cap", m, M["orange"], group="pad", note="Keep on the rod tip whenever there is no rocket on the pad")


def pad_tile_clamp(M):
    """4 corner clamps hold the 200 mm tile to the hub (M4 screws), offset so the motor sits over the tile centre"""
    m = None
    for k, (sx, sy) in enumerate(((1, 1), (-1, 1), (1, -1), (-1, -1))):
        c = box(16.0, 16.0, 4.0, sx * 28, sy * 28, HUB_H + 10.0 + 2.0)
        c = c - cyl(2.2, 10, HUB_H + 5, sx * 28, sy * 28, segs=16)
        m = c if m is None else m + c
    return m


# ======================================================================================
# drilled / cut purchased parts and build tools
# ======================================================================================
def lower_tube_cut():
    t = tube(R, RI, L_LOW, 0.0)
    t = t - polar(box(8.0, CAM_WIN_W, CAM_WIN_H, R, 0, CAM_Z0 + CAM_WIN_H / 2), 270)
    t = t - polar(box(8.0, 7.0, 20.0, R, 0, SW_Z), SW_ANG)
    t = t - hatch_cut()
    for a in STATIC_PORT_ANG:
        t = t - polar(xcyl(1.0, 6, 16).translate((R, 0, Z_AV0 + 40.0)), a)
    for a in RADIAL_SCREW_ANG:
        t = t - polar(xcyl(1.65, 6, 16).translate((R, 0, Z_AV0 + 12.0)), a)
    for a in TAIL_SCREW_ANG:
        t = t - polar(xcyl(1.65, 6, 16).translate((R, 0, TAIL_SCREW_Z)), a)
    for a in FIN_ANG:
        t = t - polar(cable_hole_local(), a)
    return t


def middle_tube_cut():
    t = tube(R, RI, L_MID, Z_MID0)
    t = t - bx(15.0, 45.0, -DOOR_W / 2, DOOR_W / 2, DOOR_Z0, DOOR_Z0 + DOOR_H)
    for a in JOINT_ANG:
        t = t - polar(xcyl(1.65, 6, 16).translate((R, 0, JOINT_Z)), a)
    return t


def drill_guide(M):
    z_top, z_bot = Z_BAND0, CAM_Z0 - 6.0
    m = tube(R + 2.2, R + 0.25, z_top - z_bot, z_bot) + tube(R + 2.2, RI - 0.8, 2.0, z_top)
    for a in RADIAL_SCREW_ANG:
        m = m - polar(xcyl(1.6, 10, 24).translate((R + 1, 0, Z_AV0 + 12.0)), a)
    for a in STATIC_PORT_ANG:
        m = m - polar(xcyl(1.0, 10, 16).translate((R + 1, 0, Z_AV0 + 40.0)), a)
    m = m - polar(box(8.0, 7.0, 20.0, R + 1.0, 0, SW_Z), SW_ANG)
    m = m - polar(box(8.0, CAM_WIN_W, CAM_WIN_H, R + 1.0, 0, CAM_Z0 + CAM_WIN_H / 2), 270)
    m = m - hatch_cut()
    m = m - polar(box(1.6, 1.2, z_top - z_bot + 10.0, R + 2.2, 0, (z_top + z_bot) / 2), LUG_ANG)
    return register("tool_drill_guide_bottom_tube", m, M["orange"], print_rot=(180, 0, 0), group="tool",
                    note="Build tool (not flown). Slides over the TOP of the bottom tube: av-bay screws, static ports, switch slot, camera window, "
                         "battery-hatch opening (cut along the guide's edges with a sharp knife), lug line")


def tool_leg_test_block(M):
    """build tool (not flown): a copy of the fin can's leg tongue on a block that clamps in a vice, to break-test spare
    legs with a luggage scale (TEST_PLAN A19)"""
    base = bx(TG_X0 - 8.0, TG_X1 + 8.0, -14.0, 14.0, 0.0, 10.0)
    tongue = bx(TG_X0, TG_X1, -TG_Y / 2, TG_Y / 2, -TG_H, 0.5) - ycyl(1.7, HT + 2.0, 24).translate((LEG_BOLT_X, 0, LEG_BOLT_Z))
    m = (base + tongue).translate((-(TG_X0 + TG_X1) / 2, 0, 0))
    return register("tool_leg_test_block", m, M["orange"], print_rot=(180, 0, 0), group="tool",
                    note="Build tool (not flown). PETG like the fin can, 3 walls, 100% infill, block on the bed (tongue up). Clamp the "
                         "block in a vice, bolt a spare leg on and pull its foot with a luggage scale")


def drill_guide_mid(M):
    z_bot, z_top = Z_MID0, DOOR_Z0 + DOOR_H + 6.0
    m = tube(R + 2.2, R + 0.25, z_top - z_bot, z_bot) + tube(R + 2.2, RI - 0.8, 2.0, z_bot - 2.0)
    m = m - bx(15.0, 45.0, -DOOR_W / 2, DOOR_W / 2, DOOR_Z0, DOOR_Z0 + DOOR_H)
    for a in JOINT_ANG:
        m = m - polar(xcyl(1.6, 10, 24).translate((R + 1, 0, JOINT_Z)), a)
    m = m - polar(box(1.6, 1.2, z_top - z_bot + 10.0, R + 2.2, 0, (z_top + z_bot) / 2), LUG_ANG)     # lug line (upper lug)
    return register("tool_drill_guide_middle_tube", m, M["orange"], group="tool",
                    note="Build tool (not flown). Slides over the BOTTOM of the middle tube: joint screws, the payload-door window and the upper-lug line")


# ======================================================================================
# purchased-part stand-ins (assembly positions)
# ======================================================================================
def purchased(M, tab_delta=0.0, latch_open=False):
    s = SV
    out = {}
    out[LOWER_TUBE] = (lower_tube_cut(), M["kraft"])
    out[MID_TUBE] = (middle_tube_cut(), M["kraft"])
    out[MOTOR_NAME] = (cyl(MOTOR_D / 2, MOTOR_L, Z_MOTOR0) - cyl(4.0, 12.0, Z_MOTOR0 - 1.0, segs=24), M["motor"])
    out["nose_ballast_M3_nuts"] = (nose_ballast(), M["steel"])
    c1 = SV1_Z + s["shaft_off"] - s["L"] / 2
    c2 = SV2_Z + s["shaft_off"] - s["L"] / 2
    sv1 = box(s["W"], s["H"], s["L"], 0, SV_SHAFT_R - s["H"] / 2, c1) + box(s["W"] - 1, 2.5, s["tab_L"], 0, SV_SHAFT_R - s["H"] + s["tab_z"] + 1.25, c1)
    sv1 = sv1 + ycyl(2.4, s["spline"], 16).translate((0, SV_SHAFT_R + s["spline"] / 2, SV1_Z))
    out["servo_MG90S_tvc_ring"] = (sv1, M["servo"])
    out["horn_tvc_ring"] = (box(PR1[0] + 6.0, 2.0, 4.5, (PR1[0] - 1.0) / 2, SV_SHAFT_R + 4.0, SV1_Z) -
                            ycyl(2.45, 8, 24).translate((0, SV_SHAFT_R + 4.0, SV1_Z)), M["horn"])
    sv2 = box(s["H"], s["W"], s["L"], SV_SHAFT_R - s["H"] / 2, 0, c2) + box(2.5, s["W"] - 1, s["tab_L"], SV_SHAFT_R - s["H"] + s["tab_z"] + 1.25, 0, c2)
    sv2 = sv2 + xcyl(2.4, s["spline"], 16).translate((SV_SHAFT_R + s["spline"] / 2, 0, SV2_Z))
    out["servo_MG90S_tvc_holder"] = (sv2, M["servo"])
    out["horn_tvc_holder"] = (box(2.0, PR2[1] + 6.0, 4.5, SV_SHAFT_R + 4.0, (PR2[1] - 1.0) / 2, SV2_Z) -
                              xcyl(2.45, 8, 24).translate((SV_SHAFT_R + 4.0, 0, SV2_Z)), M["horn"])
    out["pushrod_ring_1.2mm"] = (cyl(0.6, SV1_Z - Z_PIVOT, Z_PIVOT, PR1[0], PR1[1], segs=12), M["steel"])
    out["pushrod_holder_1.2mm"] = (cyl(0.6, SV2_Z - HOLDER_TAB_Z, HOLDER_TAB_Z, PR2[0], PR2[1], segs=12), M["steel"])
    # four tab servos inside the fins, horns glued into the tabs (direct drive)
    for k, a in enumerate(FIN_ANG):
        out[f"servo_MG90S_tab{k + 1}"] = (polar(tab_servo_local(), a), M["servo"])
        out[f"horn_tab{k + 1}"] = (polar(tab_horn_local(tab_delta), a), M["horn"])
        out[f"leg_bolt_M3x18_nut_{k + 1}"] = (polar(leg_bolt_local(), a), M["steel"])
    # release servo, horn, spring link
    phi = 30.0 if latch_open else 0.0
    out["servo_MG90S_release"] = (release_servo_solid(0.0), M["servo"])
    out["horn_release"] = (release_horn(phi), M["horn"])
    hx = RSV_SH[0] + RHORN_ARM * math.sin(math.radians(phi))
    bxs = 3.5 if latch_open else 0.0
    lx = BOLT_IN_X + 0.8 + bxs
    link = (cyl(0.3, 4.5, BOLT_Z - 1.0, lx, BOLT_Y, segs=8) + cyl(0.3, 4.5, BOLT_Z - 1.0, hx, BOLT_Y, segs=8) +
            bx(min(lx, hx) - 0.3, max(lx, hx) + 0.3, BOLT_Y - 0.3, BOLT_Y + 0.3, BOLT_Z + 3.0, BOLT_Z + 3.6))
    out["latch_spring_link_0.6mm"] = (link, M["steel"])
    # flight computer
    out[PCB_NAME] = (box(BW, BT, BH, 0, PCB_Y_BACK + BT / 2, PCB_Z_TOP - BH / 2), M["pcb"])
    x10 = board_to_rocket(MECH["parts"]["J10"]["x"], 0)[0]
    x11 = board_to_rocket(MECH["parts"]["J11"]["x"], 0)[0]
    pz = PCB_Z_TOP - (MECH["parts"]["J10"]["y"] + MECH["parts"]["J11"]["y"]) / 2
    yp = PCB_Y_FRONT + SOCKET_H
    pico = box(2.5, SOCKET_H, 50.8, x10, PCB_Y_FRONT + SOCKET_H / 2, pz) + box(2.5, SOCKET_H, 50.8, x11, PCB_Y_FRONT + SOCKET_H / 2, pz)
    pico = pico + box(21.0, 1.0, 51.0, (x10 + x11) / 2, yp + 0.5, pz)
    pico = pico + box(11.0, 1.6, 13.0, (x10 + x11) / 2, yp + 1.8, pz - 12.0)
    pico = pico + box(8.0, 2.6, 5.5, (x10 + x11) / 2, yp + 2.3, pz + 25.5 - 2.75)
    out["pico2w_on_sockets"] = (pico, M["pico"])
    bxz = board_to_rocket(13.25, 7.15)
    parts_fc = ycyl(6.0, 9.5, 32).translate((bxz[0], PCB_Y_FRONT + 4.75, bxz[1]))
    jx, jz = board_to_rocket(MECH["parts"]["J1"]["x"], (MECH["parts"]["J1"]["y"] - 2.5))
    parts_fc = parts_fc + box(5.75, 7.0, 9.9, jx, PCB_Y_FRONT + 3.5, jz)
    sx_, sz_ = board_to_rocket(MECH["parts"]["SW1"]["x"], MECH["parts"]["SW1"]["y"])
    parts_fc = parts_fc + box(2.6, 1.4, 6.7, sx_ - 0.2, PCB_Y_FRONT + 0.7, sz_)
    for r in sorted(k for k, v in MECH["parts"].items() if v["value"].startswith("SERVO")):
        hx_, hz_ = board_to_rocket(MECH["parts"][r]["x"], MECH["parts"][r]["y"] + 2.54)
        parts_fc = parts_fc + box(2.6, 14.0, 7.6, hx_, PCB_Y_FRONT + 2.5 + 7.0, hz_)
    out["fc_connectors_buzzer_switch"] = (parts_fc, M["servo"])
    out["lipo_overlander_350_2s"] = (box(BATT["w"], BATT["t"], BATT["l"], 0, BATT["y0"] + BATT["t"] / 2 + 0.5, BATT["z0"] + BATT["l"] / 2), M["lipo"])
    out["gps_patch_antenna_15mm"] = (box(15.0, 15.0, 4.0, GPS_X, GPS_Y, GPS_SHELF_Z + 2.05), M["antenna"])
    # 36 in chute rolled to ~44 x 90 mm on the piston (1.44 x the volume of the 30 in pack), cord coiled on top
    out["parachute_packed"] = (cyl(22.0, 90.0, Z_PISTON + 3.5, 0.0, 0.0, segs=48), M["nylon"])
    out["shock_cord_kevlar_elastic"] = (cyl(7.0, 20.0, Z_PISTON + 94.5, 7.0, -1.0, segs=32), M["cord"])
    cam = box(23.0, 23.0, 23.0, 0, -CAM_RC, CAM_Z0 + CAM_FLOOR + 0.3 + 11.5) + cyl(4.0, 1.9, CAM_Z0 + 0.2, 0, -CAM_RC, segs=24)
    out["camera_SQ12_class"] = (cam, M["camera"])
    out["payload_example_25g"] = (bx(-8.0, 16.0, -12.0, 12.0, Z_FLOOR + 0.2, Z_FLOOR + 30.0), M["payload"])
    return out


def spring_pts(packed=True):
    n = 600
    z0, h = Z_WALL1, SPR["packed_length"] if packed else SPR["free_length"]
    turns = 9
    r = SPR["od"] / 2 - 0.8
    return [(r * math.cos(2 * math.pi * turns * i / n), r * math.sin(2 * math.pi * turns * i / n), z0 + h * i / n) for i in range(n + 1)]


def lead_paths():
    """servo leads as poly-lines (the 2 TVC leads come out of the top of the TVC module)"""
    s = SV
    c1 = SV1_Z + s["shaft_off"] - s["L"] / 2
    c2 = SV2_Z + s["shaft_off"] - s["L"] / 2
    z_fc = PCB_Z_TOP - 74.85                       # servo headers at the bottom edge of the board
    hx = board_to_rocket(MECH["parts"]["J2"]["x"], 0)[0]
    p = {}
    p["lead_tvc_ring"] = [(4.0, 4.0, c1 - s["L"] / 2 + 2), (6.0, 2.0, c1 - s["L"] / 2 - 4), (7.0, -4.0, c1 - 10), (8.0, -8.0, FRAME_TOP - 2),
                          (8.0, -8.0, FRAME_TOP + 30), (6.0, -4.0, Z_AV0 - 2), (hx, 1.0, Z_AV0 + 4)]
    p["lead_tvc_holder"] = [(4.0, -4.0, c2 - s["L"] / 2 + 2), (2.0, -6.5, c2 - s["L"] / 2 - 3), (-2.0, -9.0, c2 + 6), (-1.0, -9.0, FRAME_TOP - 2),
                            (-1.0, -9.0, FRAME_TOP + 30), (4.0, -4.0, Z_AV0 - 2), (hx + 2.5, 1.0, Z_AV0 + 4)]
    for k, a in enumerate(GROOVE_ANG):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        r_g = FRAME_R - 0.8
        zc = (CAB_Z0 + CAB_Z1) / 2
        xg = TIP_R - LEAD_GROOVE_D / 2 - 0.3
        pts = [(SVX1 - 2.0, SV_Z0 + SV["L"] - 2.0), (xg, SV_Z0 + SV["L"] + 1.5), (xg, zc), (TIP_R - 6.0, zc),
               (CAN_RI - 1.0, zc), (r_g, zc + 3), (r_g, FRAME_TOP + 2), (r_g - 6, FRAME_TOP + 25)]
        path = [(rr * ca, rr * sa, z) for rr, z in pts] + [(8.0, -4.0 + k, Z_AV0 - 4), (hx + 4.5 * (k + 1), 1.0, Z_AV0 + 4)]
        p[f"lead_tab{k + 1}"] = path
    p["lead_release"] = [(RSV_XC, -11.0, RSV_Z0 + 2), (-24.0, -2.0, RSV_Z0 - 4), (-25.5, 0.0, Z_WALL1 + 4), (-25.0, 0.0, Z_WALL0 - 14),
                         (-25.0, 0.0, Z_FLOOR + 2), (-23.0, 0.0, SH_TOP - 4), (-22.0, 7.0, GPS_SHELF_Z + 6),
                         (-20.0, 8.0, GPS_SHELF_Z - 8), (-12.0, 6.0, PCB_Z_TOP + 2)]
    return p


def pad_purchased(M, rod_z0):
    out = {}
    tile = box(PLATE, PLATE, 8.0, ROCKET_XY[0], ROCKET_XY[1], HUB_H + 10.0 + 4.0) - cyl(4.0, 40, HUB_H, segs=24)
    out["blast_tile_200x200"] = (tile, M["tile"])
    out["launch_rod_6mm_1m"] = (cyl(3.0, 1000.0, rod_z0, segs=24), M["steel"])
    for k in range(3):
        out[f"leg_dowel_22mm_{k + 1}"] = (leg_axis_transform(cyl(LEG_D / 2, LEG_L, -LEG_L + 25.0, segs=32), k), M["wood"])
    return out


PAD_TOP = HUB_H + 10.0 + 8.0            # top face of the tile = where the fin feet stand


# ======================================================================================
def build_all(M):
    nose_cone(M)
    top_insert(M)
    register("latch_bolt", latch_bolt(M), M["black"], part="middle", note="PETG. Bevel UP. Must slide freely; rub with graphite")
    door_frame(M); payload_door_parts(M); payload_wall(M); spring_piston(M)
    avbay_coupler(M); avbay_sled(M)
    tvc_holder(M); tvc_ring(M); tvc_frame(M); retainer(M); motor_adapter(M)
    fin_can(M); fin_legs(M); fin_tabs(M); upper_lug(M); camera_pod(M); hatch_parts(M)
    pad_hub(M); pad_rod_block(M)
    tail_z = PAD_TOP - FOOT_Z
    pad_rod_stop(M, 150.0); pad_leg_foot(M); rod_cap(M)
    clamps = pad_tile_clamp(M).decompose()
    register("pad_tile_clamp", clamps[0], M["black"], group="pad", qty=4, inst=clamps, note="4 corner clamps, M4 screws into the hub")
    drill_guide(M); drill_guide_mid(M); tool_leg_test_block(M)
    return tail_z


def write_stl(path, V, F):
    import struct
    V = np.asarray(V, dtype=float)
    F = np.asarray(F)
    # drop stray zero-area islands (2-triangle slivers left where cuts coincide): faces are grouped by shared edges, as a
    # slicer sees them; a zero-area triangle that is part of a closed surface stays, so the solid stays watertight
    parent = list(range(len(F)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    edge_faces = {}
    for fi, (f0, f1, f2) in enumerate(F):
        for e in ((f0, f1), (f1, f2), (f2, f0)):
            edge_faces.setdefault((min(e), max(e)), []).append(fi)
    for fl in edge_faces.values():
        if len(fl) == 2:                                    # manifold edge; slivers hang on edges shared by more faces
            ra, rb = find(fl[0]), find(fl[1])
            parent[ra] = rb
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    comp = np.array([find(i) for i in range(len(F))])
    tot = {}
    for cid, ar in zip(comp, area):
        tot[cid] = tot.get(cid, 0.0) + ar
    F = F[np.array([tot[cid] > 1e-6 for cid in comp], dtype=bool)]
    with open(path, "wb") as fh:
        fh.write(b"KESTREL-2 STL (mm)".ljust(80, b" "))
        fh.write(struct.pack("<I", len(F)))
        for a, b, c in F:
            va, vb, vc = V[a], V[b], V[c]
            n = np.cross(vb - va, vc - va)
            ln = np.linalg.norm(n)
            n = n / ln if ln > 0 else n
            fh.write(struct.pack("<12fH", *n, *va, *vb, *vc, 0))


def solid_props(m):
    mm = m.to_mesh()
    V = np.asarray(mm.vert_properties)[:, :3].astype(float)
    F = np.asarray(mm.tri_verts)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    vol6 = np.einsum("ij,ij->i", a, np.cross(b, c))
    cen = ((a + b + c) * vol6[:, None]).sum(0) / (4.0 * vol6.sum())
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum()
    rxy = np.sqrt((((a + b + c) / 3.0)[:, :2] ** 2).sum(1))
    return cen, area, rxy, V


def export_stls():
    for f in os.listdir(STL_DIR):                    # drop STLs of parts that no longer exist
        if f.endswith(".stl") and f[:-4] not in PARTS:
            os.remove(os.path.join(STL_DIR, f))
    report = []
    for name, p in PARTS.items():
        m = p["m"]
        rx, ry, rz = p["print_rot"]
        m2 = (p["export_m"] if p.get("export_m") is not None else m).rotate((rx, ry, rz))
        bb = m2.bounding_box()
        m2 = m2.translate((-(bb[0] + bb[3]) / 2, -(bb[1] + bb[4]) / 2, -bb[2]))
        mesh = m2.to_mesh()
        write_stl(os.path.join(STL_DIR, name + ".stl"), np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts))
        nb = len(m.decompose())
        if nb != 1:
            print(f"WARNING {name}: {nb} separate bodies")
        cen, area, rxy, V = solid_props(m)
        report.append(dict(name=name, qty=p["qty"], note=p["note"], group=p["group"], part=p["part"], volume_mm3=float(m.volume()),
                           area_mm2=float(area), centroid_assembly_mm=[float(x) for x in cen],
                           r_gyr_mm=float(np.sqrt((rxy ** 2).mean())), z_len_mm=float(V[:, 2].max() - V[:, 2].min())))
    with open(os.path.join(STL_DIR, "parts.json"), "w") as fh:
        json.dump(report, fh, indent=1)


def component_positions(buy, leads):
    """centroid (from the nose tip), axial length and max radius of every purchased part - the simulator reads these"""
    out = {}
    for name, (m, _) in buy.items():
        cen, _, _, V = solid_props(m)
        out[name] = dict(z_from_tip=round(Z_TIP - float(cen[2]), 1), length=round(float(V[:, 2].max() - V[:, 2].min()), 1),
                         radius=round(float(np.sqrt((V[:, :2] ** 2).sum(1)).max()), 1))
    for name, pts in leads.items():
        P = np.array(pts)
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        mid = (P[1:] + P[:-1]) / 2
        zc = float((mid[:, 2] * seg).sum() / seg.sum())
        out[name] = dict(z_from_tip=round(Z_TIP - zc, 1), length=round(float(P[:, 2].max() - P[:, 2].min()), 1),
                         radius=round(float(np.sqrt((P[:, :2] ** 2).sum(1)).max()), 1), path_length_mm=round(float(seg.sum()), 0))
    P = np.array(spring_pts())
    out["ejection_spring"] = dict(z_from_tip=round(Z_TIP - float(P[:, 2].mean()), 1), length=round(float(np.ptp(P[:, 2])), 1),
                                  radius=round(SPR["od"] / 2, 1))
    out["_z_tip_above_tail_mm"] = Z_TIP
    json.dump(out, open(os.path.join(HERE, "component_positions.json"), "w"), indent=1)
    return out


def check_layout():
    """Values the simulator / firmware take from design.json must match this CAD + the PCB layout."""
    u4 = MECH["parts"]["U4"]
    imu_from_tip = Z_TIP - board_to_rocket(u4["x"], u4["y"])[1]
    want = {
        "avbay.imu_z (LSM6DSO U4)": (D["avbay"]["imu_z"], imu_from_tip),
        "camera_pod.protrusion_mm": (D["camera_pod"]["protrusion_mm"], CAM_RC + CAM_POCKET / 2 + 1.2 - R),
        "camera_pod.width_mm": (D["camera_pod"]["width_mm"], CAM_POCKET + 2 * 1.6),
        "fins.tab.r_from": (TABP["r_from"], TAB_X0 - CAN_RO),
        "fins.tab.r_to": (TABP["r_to"], TAB_X1 - CAN_RO),
        "fins.tab.chord": (TABP["chord"], HINGE_Z + TAB_LE_R + TE_EXT),
        "fins.leg.foot_base_mm2 /10": (LEGP["foot_base_mm2"] / 10.0, POST_W * POST_T / 10.0),
        "fins.leg.side_area_mm2 /10": (LEGP["side_area_mm2"] / 10.0, leg_local().rotate((90, 0, 0)).project().area() / 10.0),
        "fins.leg.width (sleeve)": (LEGP["width"], TIP_R - SL_X0),
        "tvc.linkage_ratio x100 (ring)": (TVC["linkage_ratio"] * 100.0, 100.0 * PR1[0] / PR1[1]),
        "tvc.linkage_ratio x100 (motor holder)": (TVC["linkage_ratio"] * 100.0, 100.0 * PR2[1] / PR2[0]),
    }
    bad = []
    for k, (have, real) in want.items():
        flag = have is None or abs(have - real) > 1.5
        print(f"layout check {k:34s} design.json {have if have is not None else float('nan'):8.1f}   CAD/PCB {real:8.1f}   {'MISMATCH' if flag else 'ok'}")
        if flag:
            bad.append(f"{k}: set {real:.1f}")
    lay = {k: round(v[1], 1) for k, v in want.items()}
    lay.update(dict(z_tip_above_tail=Z_TIP, switch_slot_deg=round(SW_ANG, 1), groove_deg=[round(g, 1) for g in GROOVE_ANG],
                    fin_deg=FIN_ANG, lug_deg=LUG_ANG, camera_deg=270.0, door_deg=0.0,
                    rocket_xy_on_pad=[round(v, 2) for v in ROCKET_XY], tail_z_on_pad=PAD_TOP - FOOT_Z,
                    camera_lens_xyz=[0.0, -round(CAM_RC, 2), CAM_Z0], cord_exit_xyz=[0.0, 18.5, Z_MID1],
                    nozzle_z=Z_MOTOR0, mid_top_z=Z_MID1, tab_hinge_z=HINGE_Z,
                    battery_hatch=dict(deg=90.0, z=[HATCH_Z0, HATCH_Z1], half_width=HATCH_X), upper_lug_z=[UPPER_LUG_Z, UPPER_LUG_Z + 25.0],
                    nose_cord_bar_z=round(Z_NOSE0 - 2.0 + (R - NS_W) - 9.0, 1)))
    json.dump(lay, open(os.path.join(HERE, "avionics_layout.json"), "w"), indent=1)
    # angular clearances on the airframe surface: things that must not land on top of each other
    for nm, ang, z in (("switch slot", SW_ANG, SW_Z), ("upper lug", LUG_ANG, UPPER_LUG_Z + 12)):
        for a in STATIC_PORT_ANG:
            if abs(((ang - a + 180) % 360) - 180) < 12 and abs(z - (Z_AV0 + 40)) < 15:
                bad.append(f"{nm} too close to the static port at {a}")
    if bad:
        raise SystemExit("design.json is out of date with the CAD/PCB layout -> " + "; ".join(bad))


def interference_report(buy):
    objs = []
    for n, p in PARTS.items():
        if p["group"] != "rocket":
            continue
        for i, m in enumerate(p["inst"]):
            objs.append((n if len(p["inst"]) == 1 else f"{n}#{i + 1}", m))
    objs += [(n, v[0]) for n, v in buy.items()]
    boxes = [m.bounding_box() for _, m in objs]
    bad = []
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = boxes[i], boxes[j]
            if a[0] > b[3] or b[0] > a[3] or a[1] > b[4] or b[1] > a[4] or a[2] > b[5] or b[2] > a[5]:
                continue
            x = objs[i][1] ^ objs[j][1]
            v = x.volume()
            if v > 1.0:
                bb = x.bounding_box()
                bad.append((objs[i][0], objs[j][0], v, bb))
    n_pairs = len(objs) * (len(objs) - 1) // 2
    md = [f"# Interference check\n\n{len(objs)} solids ({n_pairs} pairs) checked with exact mesh booleans.\n"]
    if bad:
        md.append("| part A | part B | overlap mm^3 | where (x, y, z mm) |\n|---|---|---|---|")
        md += [f"| {a} | {b} | {v:.1f} | ({bb[0]:.1f}..{bb[3]:.1f}, {bb[1]:.1f}..{bb[4]:.1f}, {bb[2]:.1f}..{bb[5]:.1f}) |" for a, b, v, bb in bad]
    else:
        md.append("**No overlaps** (> 1 mm^3) between any printed part and any purchased part.")
    open(os.path.join(HERE, "interference_report.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))
    return bad


def sweep_reports(buy):
    """moving parts swept through their whole travel against everything they could touch"""
    md, rows = [], []
    # 1) TVC gimbal: deflection circle at the firmware limit + 1 deg
    max_deg = TVC["max_deflection_deg"] + 1.0
    inner = [("tvc_motor_holder", PARTS["tvc_motor_holder"]["m"]), ("tvc_motor_retainer", PARTS["tvc_motor_retainer"]["m"]),
             (MOTOR_NAME, buy[MOTOR_NAME][0])]
    ring = ("tvc_gimbal_ring", PARTS["tvc_gimbal_ring"]["m"])
    static = [(n, PARTS[n]["m"]) for n in ("tvc_frame", "fin_can")]
    static += [(n, buy[n][0]) for n in (LOWER_TUBE, "servo_MG90S_tvc_ring", "servo_MG90S_tvc_holder",
                                        "pushrod_ring_1.2mm", "pushrod_holder_1.2mm", "horn_tvc_ring", "horn_tvc_holder")]
    # the 24 mm adapter sleeve and retainer swing with the holder too
    inner += [(n, PARTS[n]["m"]) for n in ("tvc_motor_adapter_24mm", "tvc_motor_retainer_24mm")]
    linked = {("tvc_gimbal_ring", "pushrod_ring_1.2mm"), ("tvc_motor_holder", "pushrod_holder_1.2mm")}  # rod in its tab hole

    def piv(m, rx, ry):
        return m.translate((0, 0, -Z_PIVOT)).rotate((0, ry, 0)).rotate((rx, 0, 0)).translate((0, 0, Z_PIVOT))
    envelope = [(0.0, 0.0)] + [(max_deg * math.cos(math.radians(a)), max_deg * math.sin(math.radians(a))) for a in range(0, 360, 15)]
    n = 0
    for rx, ry in envelope:
        moving = [(nm, piv(m, rx, ry)) for nm, m in inner] + [(ring[0], piv(ring[1], rx, 0.0))]
        for nm, m in moving:
            for sn, sm in static:
                if (nm, sn) in linked:
                    continue
                v = (m ^ sm).volume()
                n += 1
                if v > 0.5:
                    rows.append(("gimbal", f"{rx:+.1f}/{ry:+.1f} deg", nm, sn, v))
        for nm, m in moving[:2]:
            v = (m ^ moving[-1][1]).volume()
            n += 1
            if v > 0.5:
                rows.append(("gimbal", f"{rx:+.1f}/{ry:+.1f} deg", nm, ring[0], v))
    md.append(f"\n## Gimbal sweep\n\nMotor, holder, both retainers, the 24 mm adapter sleeve and the ring swung round the whole "
              f"deflection circle ({len(envelope) - 1} directions at {max_deg:.0f} deg = firmware limit {TVC['max_deflection_deg']} deg "
              f"+ 1 deg margin) against the frame, fin can, tube, servos, horns and pushrods: {n} contact checks.")
    # 24 mm motors in the 29 mm mount: sleeve, retainer, spacer and a D / E motor must fit together and in the holder
    hold = PARTS["tvc_motor_holder"]["m"]
    sleeve = PARTS["tvc_motor_adapter_24mm"]["m"]
    ret24 = PARTS["tvc_motor_retainer_24mm"]["m"]
    spacer = PARTS["tvc_motor_spacer_D"]["m"]
    e_mot = cyl(12.0, MOTOR_L, Z_MOTOR0, segs=64)
    d_mot = cyl(12.0, D_MOTOR_L, Z_MOTOR0, segs=64)
    fit = [("adapter sleeve", sleeve, "motor holder", hold), ("adapter sleeve", sleeve, "24 mm retainer", ret24),
           ("24 mm retainer", ret24, "motor holder", hold), ("E motor 24 x 95", e_mot, "adapter sleeve", sleeve),
           ("E motor 24 x 95", e_mot, "24 mm retainer", ret24), ("E motor 24 x 95", e_mot, "motor holder", hold),
           ("D motor 24 x 70", d_mot, "D spacer", spacer), ("D spacer", spacer, "adapter sleeve", sleeve),
           ("D spacer", spacer, "motor holder", hold)]
    for an, am, bn, bm in fit:
        v = (am ^ bm).volume()
        if v > 0.5:
            rows.append(("24 mm adapter", "fitted", an, bn, v))
    gap_top = (Z_MOTOR0 + MOTOR_L + 0.3) - (Z_MOTOR0 + D_MOTOR_L + (MOTOR_L - D_MOTOR_L - 0.4))
    md.append(f"\n## 24 mm adapter\n\nAdapter sleeve, 24 mm retainer, D-motor spacer, a 24 x 95 mm (E) and a 24 x 70 mm (D) motor "
              f"checked against each other and the holder: {len(fit)} checks; the D motor + spacer stack is {gap_top:.1f} mm "
              f"short of the washer ledge.")
    # 2) control tabs: every fin, tab + its glued-in horn through +/- (limit + 2 deg)
    lim = TABP["max_deflection_deg"] + 2.0
    fc = PARTS["fin_can"]["m"]
    n2 = 0
    for k, a in enumerate(FIN_ANG):
        sv = polar(tab_servo_local(), a)
        statics = [("fin_can", fc), (f"servo_MG90S_tab{k + 1}", sv), (LOWER_TUBE, buy[LOWER_TUBE][0])]
        for d in np.linspace(-lim, lim, 9):
            mov = [("tab", polar(tab_local(d), a)), ("horn", polar(tab_horn_local(d), a))]
            for mn, mm in mov:
                for sn, sm in statics:
                    if mn == "horn" and sn.startswith("servo"):
                        continue                      # the horn sits on the servo's own spline
                    v = (mm ^ sm).volume()
                    n2 += 1
                    if v > 0.5:
                        rows.append((f"tab {k + 1}", f"{d:+.1f} deg", mn, sn, v))
            v = (mov[0][1] ^ mov[1][1]).volume()       # the horn must stay inside its pocket
            n2 += 1
            if v > 0.5:
                rows.append((f"tab {k + 1}", f"{d:+.1f} deg", "tab", "horn", v))
    md.append(f"\n## Control-tab sweep\n\nAll {NF} tabs with their glued-in servo horns swept through +/-{lim:.0f} deg "
              f"(limit {TABP['max_deflection_deg']:.0f} deg + 2 deg): {n2} contact checks.")
    # 3) payload door opening 0..100 deg (latch turned to open)
    statics = [(MID_TUBE, buy[MID_TUBE][0]), ("payload_door_frame", PARTS["payload_door_frame"]["m"]),
               ("avbay_coupler", PARTS["avbay_coupler"]["m"]), ("payload_example_25g", buy["payload_example_25g"][0])]
    n3 = 0
    for th in np.linspace(0.0, 100.0, 11):
        mov = [("door", door_solid(th)), ("latch knob", latch_knob_solid(th)), ("latch cam", latch_cam_solid(False, th))]
        for mn, mm in mov:
            for sn, sm in statics:
                v = (mm ^ sm).volume()
                n3 += 1
                if v > 0.5:
                    rows.append(("door", f"{th:.0f} deg", mn, sn, v))
    md.append(f"\n## Payload-door sweep\n\nDoor, latch knob and cam (turned to open) swung 0-100 deg about the hinge: {n3} contact checks.")
    # 4) release latch: bolt pulled in, horn at the release angle
    bolt_in = latch_bolt(None, 3.5)
    statics = [("top_latch_insert", PARTS["top_latch_insert"]["m"]), ("nose_cone", PARTS["nose_cone"]["m"]),
               ("servo_MG90S_release", buy["servo_MG90S_release"][0])]
    n4 = 0
    for mn, mm in (("latch bolt (released)", bolt_in), ("horn (released)", release_horn(30.0))):
        for sn, sm in statics:
            if mn.startswith("horn") and sn.startswith("servo"):
                continue
            v = (mm ^ sm).volume()
            n4 += 1
            if v > 0.5:
                rows.append(("release latch", "open", mn, sn, v))
    # bolt fully out must engage the sleeve by >= 1 mm, fully in must clear it
    eng = (-BOLT_TIP_X) - (R - NS_W)
    clear = (R - NS_W) - (-(BOLT_TIP_X + 3.5))
    md.append(f"\n## Release latch\n\nBolt engages the nose sleeve by {eng:.2f} mm when locked and clears it by {clear:.2f} mm when "
              f"pulled in 3.5 mm; released bolt and horn checked against the insert, nose and servo: {n4} checks.")
    if rows:
        md.append("\n| mechanism | position | moving part | hits | overlap mm^3 |\n|---|---|---|---|---|")
        md += [f"| {a} | {b} | {c} | {d} | {v:.1f} |" for a, b, c, d, v in rows]
    else:
        md.append("\n**No contact** anywhere in any mechanism's travel.")
    with open(os.path.join(HERE, "interference_report.md"), "a") as fh:
        fh.write("\n".join(md) + "\n")
    print("\n".join(md))
    if eng < 1.0 or clear < 0.5:
        rows.append(("release latch", "", "bolt", "engagement", 0))
    return rows


# ======================================================================================
# rendering
# ======================================================================================
def setup_render(res=(1600, 1000), samples=None, world=(0.80, 0.85, 0.92), strength=0.45):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    ee = sc.eevee
    ee.taa_render_samples = samples or (16 if FAST else 64)
    ee.use_gtao = True
    ee.gtao_distance = 40.0
    ee.use_soft_shadows = True
    ee.shadow_cascade_size = "4096"
    ee.shadow_cube_size = "2048"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (*world, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = strength
    sc.world = w
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    for nm, en, rot in (("key", 3.2, (50, 10, 30)), ("fill", 0.8, (70, 0, 200)), ("rim", 1.2, (110, 0, 120))):
        l = bpy.data.lights.new(nm, "SUN")
        l.energy = en
        l.angle = math.radians(4.0)
        o = bpy.data.objects.new(nm, l)
        o.rotation_euler = tuple(math.radians(a) for a in rot)
        sc.collection.objects.link(o)


def camera_at(name, loc, target, lens=50):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    dist = (Vector(target) - Vector(loc)).length
    cam.clip_start = max(0.5, dist / 250.0)          # tight depth range: no z-fighting on the 0.55 mm tube walls
    cam.clip_end = dist * 40.0
    co = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return co


def render_views(views):
    sc = bpy.context.scene
    for name, loc, tgt, lens, vis, res in views:
        if VIEWS and name not in VIEWS:
            continue
        cam = camera_at("cam_" + name, loc, tgt, lens)
        sc.camera = cam
        sc.render.resolution_x, sc.render.resolution_y = res
        for c in bpy.data.collections:
            c.hide_render = c.name not in vis
        sc.render.filepath = os.path.join(REN_DIR, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("rendered", name)
    for c in bpy.data.collections:
        c.hide_render = False


def add_solids(items, coll, offset=(0, 0, 0), suffix=""):
    obs = []
    for name, m, material in items:
        ob = to_blender(name + suffix, m, material, coll)
        ob.location = offset
        obs.append(ob)
    return obs


def rocket_items(buy, cut=None, skip=()):
    """(name, manifold, material) for every rocket solid; cut = (y0, names) removes everything at y > y0 from those"""
    items = []
    for name, p in PARTS.items():
        if p["group"] != "rocket" or name in skip:
            continue
        for i, m in enumerate(p["inst"]):
            nm = name if len(p["inst"]) == 1 else f"{name}_{i + 1}"
            if cut and name in cut[1]:
                m = m - box(2000.0, 1000.0, 4000.0, 0, 500.0 + cut[0], 500.0)
            if not m.is_empty():
                items.append((nm, m, p["material"]))
    for name, (m, material) in buy.items():
        if name in skip:
            continue
        if cut and name in cut[1]:
            m = m - box(2000.0, 1000.0, 4000.0, 0, 500.0 + cut[0], 500.0)
        if not m.is_empty():
            items.append((name, m, material))
    return items


def lead_objects(M, coll, offset=(0, 0, 0), only=None, suffix=""):
    cols = [M["wire_br"], M["wire_r"], M["wire_or"]]
    for name, pts in lead_paths().items():
        if only and name not in only:
            continue
        for i, c in enumerate(cols):          # 3-core servo lead: brown / red / orange side by side
            d = (i - 1) * 0.9
            pp = [(x + d * 0.7, y + d * 0.7, z) for x, y, z in pts]
            ob = curve_obj(f"{name}_{i}{suffix}", pp, c, coll, radius=0.45)
            ob.location = offset


def parachute_open_solids(M):
    """24 in canopy inflated (projected ~0.67 D0), 8 gores, spill hole, 8 shroud lines to a swivel"""
    D0 = REC["parachute_diameter_in"] * 25.4
    Rp = 0.335 * D0
    H = 0.55 * Rp
    prof_o = [(Rp * math.sin(t), H * math.cos(t)) for t in np.linspace(0.18, math.pi / 2, 30)]
    shell = revolve([(r, z) for r, z in prof_o] + [(r - 1.0, z - 0.6) for r, z in prof_o[::-1]], 96)
    gores = []
    for k in range(8):
        wedge = M3.batch_hull([cyl(0.1, 2 * H + 10, -H - 5, segs=8),
                               box(1, 1, 2 * H + 10, 2 * Rp * math.cos(math.radians(45 * k)), 2 * Rp * math.sin(math.radians(45 * k)), 0),
                               box(1, 1, 2 * H + 10, 2 * Rp * math.cos(math.radians(45 * (k + 1))), 2 * Rp * math.sin(math.radians(45 * (k + 1))), 0)])
        gores.append(shell ^ wedge)
    return gores, Rp, H


# ------------------------------------------------------------------------------- tidy .blend files for people
# The script builds every view in one scene (that is how the renders are made). Before saving, each file is
# reorganised so that nothing overlaps when someone opens it: one scene per view, the viewport framed on the model.
LAYOUT = [
    ("Nose cone and middle part (printed)", [
        ("part", "nose_cone", "nose cone"), ("part", "top_latch_insert", "release-latch\ninsert"),
        ("part", "latch_bolt", "latch bolt"), ("part", "payload_wall", "parachute wall"),
        ("part", "spring_piston", "spring piston"), ("part", "payload_door_frame", "door frame"),
        ("part", "payload_door", "payload door"), ("part", "payload_door_latch_knob", "door latch\nknob"),
        ("part", "payload_door_latch_cam", "door latch\ncam"), ("part", "upper_launch_lug", "upper\nlaunch lug")]),
    ("Bottom part (printed)", [
        ("part", "fin_can", "fin can\n(4 fins, 4 leg tongues)"), ("part", "fin_leg", "replaceable\nleg x 4"),
        ("part", "fin_control_tab", "control tab\nx 4"),
        ("part", "avbay_coupler", "av-bay coupler"), ("part", "avbay_sled", "av-bay sled"),
        ("part", "battery_hatch_door", "battery-hatch\ndoor"), ("part", "battery_hatch_latch_knob", "hatch latch\nknob"),
        ("part", "battery_hatch_latch_cam", "hatch latch\ncam"), ("part", "camera_pod", "camera pod")]),
    ("TVC module (printed)", [
        ("part", "tvc_frame", "TVC frame"), ("part", "tvc_gimbal_ring", "gimbal ring"),
        ("part", "tvc_motor_holder", "motor holder"), ("part", "tvc_motor_retainer", "motor retainer"),
        ("part", "tvc_motor_adapter_24mm", "24 mm adapter\n(D20 / E20)"),
        ("part", "tvc_motor_retainer_24mm", "24 mm motor\nretainer"), ("part", "tvc_motor_spacer_D", "D-motor\nspacer")]),
    ("Electronics (bought; the PCB comes assembled from JLCPCB)", [
        ("buy", "pcb_kestrel_fc_40x82", "flight-computer\nPCB"), ("buy", "pico2w_on_sockets", "Pico 2 W\non its sockets"),
        ("buy", "fc_connectors_buzzer_switch", "servo headers,\nbuzzer, switch"),
        ("buy", "lipo_overlander_350_2s", "2S 350 mAh\nLiPo"), ("buy", "gps_patch_antenna_15mm", "GPS patch\nantenna"),
        ("buy", "camera_SQ12_class", "SQ12 camera")]),
    ("Servos and linkages (bought)", [
        ("buy", "servo_MG90S_tab1", "MG90S servo\nx 7"), ("buy", "horn_tvc_ring", "servo horn,\nTVC x 2"),
        ("buy", "horn_tab1", "horn stub,\nin each tab x 4"), ("buy", "horn_release", "servo horn,\nrelease latch"),
        ("buy", "pushrod_ring_1.2mm", "1.2 mm pushrod\nx 2 (TVC)"), ("buy", "latch_spring_link_0.6mm", "0.6 mm\nlatch link")]),
    ("Airframe, motor and recovery (bought)", [
        ("buyflat", LOWER_TUBE, "BT-70 bottom tube, 340 mm"), ("buyflat", MID_TUBE, "BT-70 middle tube, 380 mm"),
        ("buy", MOTOR_NAME, D["launch"]["nominal_motor"].replace("-", " ") + "\nmotor"), ("buy", "parachute_packed", "36 in parachute\n(packed)"),
        ("buy", "shock_cord_kevlar_elastic", "shock cord\n(coiled)"), ("spring", None, "ejection\nspring"),
        ("buy", "nose_ballast_M3_nuts", "nose ballast:\nM3 nuts + epoxy"), ("buy", "payload_example_25g", "example\npayload 25 g")]),
    ("Launch pad", [
        ("part", "pad_hub", "pad hub"), ("part", "pad_rod_block", "rod block"), ("part", "pad_rod_stop", "rod stop"),
        ("part", "pad_leg_foot", "leg foot\nx 3"), ("part", "pad_tile_clamp", "tile clamp\nx 4"),
        ("part", "rod_tip_safety_cap", "rod-tip\nsafety cap"), ("pad", "blast_tile_200x200", "200 mm tile"),
        ("rod", None, "6 mm launch rod, 1 m"), ("dowel", None, "22 mm dowel leg, 600 mm, x 3")]),
    ("Build tools (printed, not flown)", [
        ("part", "tool_drill_guide_bottom_tube", "drill guide,\nbottom tube"),
        ("part", "tool_drill_guide_middle_tube", "drill guide,\nmiddle tube"),
        ("part", "tool_leg_test_block", "leg test\nblock")]),
]
CUT_DX = 220.0            # the cut-open rocket stands this far beside the complete one
CUTOPEN = ("avbay_coupler", "fin_can", "fin_control_tab", "tvc_frame", "nose_cone", "top_latch_insert", "payload_wall",
           "spring_piston", "payload_door", "camera_pod", "camera_SQ12", "servo_MG90S_tab", "horn_tab", "upper_launch_lug",
           LOWER_TUBE, MID_TUBE)


def _scene_like(name, like):
    sc = bpy.data.scenes.new(name)
    _mm_units(sc)
    sc.render.engine = like.render.engine
    sc.render.resolution_x, sc.render.resolution_y = like.render.resolution_x, like.render.resolution_y
    sc.world = like.world
    try:
        sc.view_settings.view_transform = like.view_settings.view_transform
        sc.view_settings.look = like.view_settings.look
    except TypeError:
        pass
    return sc


def _lights(sc):
    """world + the three sun lights, in a 'Lights' collection that every scene of the file links"""
    if sc.world is None:
        w = bpy.data.worlds.new("w")
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.80, 0.85, 0.92, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = 0.45
        sc.world = w
    lc = bpy.data.collections.get("Lights")
    if lc is None:
        lc = bpy.data.collections.new("Lights")
        sc.collection.children.link(lc)
    for o in [o for o in sc.collection.objects if o.type == "LIGHT"]:
        sc.collection.objects.unlink(o)
        lc.objects.link(o)
    if not lc.objects:
        for nm, en, rot in (("key", 3.2, (50, 10, 30)), ("fill", 0.8, (70, 0, 200)), ("rim", 1.2, (110, 0, 120))):
            l = bpy.data.lights.new(nm, "SUN")
            l.energy = en
            l.angle = math.radians(4.0)
            o = bpy.data.objects.new(nm, l)
            o.rotation_euler = tuple(math.radians(a) for a in rot)
            lc.objects.link(o)
    return lc


def _move_to_scene(sc, main, coll_names, cam_names=(), dx=0.0):
    """move collections (spaced dx apart along x) and their render cameras into scene sc"""
    for k, cn in enumerate(coll_names):
        c = bpy.data.collections[cn]
        if c.name in main.collection.children:
            main.collection.children.unlink(c)
        sc.collection.children.link(c)
        if dx * k:
            for o in c.all_objects:
                o.location.x += dx * k
    for k, cam_name in enumerate(cam_names):
        cam = bpy.data.objects.get(cam_name)
        if cam is None:
            continue
        if cam.name in main.collection.objects:
            main.collection.objects.unlink(cam)
        sc.collection.objects.link(cam)
        cam.location.x += dx * k
        if sc.camera is None:
            sc.camera = cam


def _mm_units(sc):
    # assigning unit_settings.system (even unchanged) resets the *active* scene's length unit (Blender quirk), so
    # only touch it when it really differs
    u = sc.unit_settings
    if u.system != "METRIC":
        u.system = "METRIC"
    u.scale_length = 0.001
    u.length_unit = "MILLIMETERS"


def _finish_scenes(dirs=None, default_dir=(0.75, -1.6, 0.95)):
    """millimetre units everywhere, object matrices up to date in every scene (positions changed in scenes that were
    never evaluated), and a camera in each scene that has none (framing its content), so F12 works everywhere"""
    active = bpy.context.scene
    for sc in sorted(bpy.data.scenes, key=lambda x: x == active):     # the active scene last
        _mm_units(sc)
        for vl in sc.view_layers:
            vl.update()
        if sc.camera is None:
            lo, hi = _content_bbox(sc.collection.children_recursive, update=False)
            if hi.x > lo.x:
                _overview_camera(sc, "cam_" + sc.name.split(" ", 1)[-1].lower().replace(" ", "_"), (lo + hi) / 2,
                                 (dirs or {}).get(sc.name, default_dir), min((hi - lo).length, 3000.0) * 0.95)


def _view(center, direction, dist):
    d = Vector(direction).normalized()
    return (-d).to_track_quat("-Z", "Y"), Vector(center) + d * dist


def _frame_viewports(center, direction, dist):
    """every 3D viewport of the saved file looks at `center` from `direction` (mm scene: wide clipping range)"""
    rot, _ = _view(center, direction, dist)
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type != "VIEW_3D":
                continue
            for sp in area.spaces:
                if sp.type == "VIEW_3D":
                    sp.clip_start = 1.0
                    sp.clip_end = 200000.0
                    r3 = sp.region_3d
                    r3.view_perspective = "PERSP"
                    r3.view_location = Vector(center)
                    r3.view_rotation = rot
                    r3.view_distance = dist


def _overview_camera(sc, name, center, direction, dist, lens=35.0):
    rot, loc = _view(center, direction, dist)
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_start = 5.0
    cam.clip_end = dist * 30.0
    co = bpy.data.objects.new(name, cam)
    sc.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = rot.to_euler()
    sc.camera = co
    return co


def _extent(ob):
    if ob.type == "MESH":
        co = np.empty(len(ob.data.vertices) * 3)
        ob.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        return co.min(0), co.max(0)
    co = np.array([p.co[:3] for sp in ob.data.splines for p in sp.points])
    r = ob.data.bevel_depth
    return co.min(0) - r, co.max(0) + r


def _content_bbox(colls, update=True):
    if update:
        bpy.context.view_layer.update()
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for c in colls:
        for o in c.all_objects:
            if o.type in ("MESH", "CURVE", "FONT"):
                for v in o.bound_box:
                    w = o.matrix_world @ Vector(v)
                    lo, hi = Vector(map(min, lo, w)), Vector(map(max, hi, w))
    return lo, hi


def _flat_text(coll, body, x, y, z, size, align="CENTER", upright=False):
    cu = bpy.data.curves.new("label", "FONT")
    cu.body = body
    cu.size = size
    cu.space_line = 1.05
    cu.align_x = align
    ob = bpy.data.objects.new("label " + body.split("\n")[0][:30], cu)
    ob.data.materials.append(mat("Label", (0.05, 0.05, 0.06), rough=0.6))
    ob.location = (x, y, z)
    if upright:                                   # a sign facing the viewer (-y)
        ob.rotation_euler = (math.radians(90), 0, 0)
    coll.objects.link(ob)
    return ob


def build_cutopen_rocket(M, items, coll, dx):
    """the complete rocket again, with its outer shells cut away on the viewer's side (y < 0) so that everything
    inside shows; parts that would only float in the removed half are left out"""
    half = box(2000.0, 1000.0, 4000.0, 0, -500.0, 500.0)
    for name, m, material in items:
        if name.startswith(CUTOPEN):
            m = m - half
            if m.is_empty():
                continue
        to_blender(name + "_cutopen", m, material, coll).location = (dx, 0, 0)
    keep = [n for n in lead_paths() if n not in ("lead_tab3", "lead_tab4")]     # those two go to the removed fins
    lead_objects(M, coll, (dx, 0, 0), only=keep, suffix="_cutopen")
    curve_obj("ejection_spring_cutopen", spring_pts(), M["steel"], coll, radius=0.75).location = (dx, 0, 0)


def build_parts_layout(M, buy, coll, x0, y_start, floor_z):
    """every part on its own, standing on the floor in labelled rows (one of each, with its quantity)"""
    padbuy = pad_purchased(M, HUB_H - 4.0)
    TXT, GAP, MAX_W = 9.0, 35.0, 1500.0
    y = y_start
    for title, entries in LAYOUT:
        made = []
        for kind, key, label in entries:
            if kind == "part":
                ob = to_blender(key + " (part)", PARTS[key]["inst"][0], PARTS[key]["material"], coll)
            elif kind == "buy":
                ob = to_blender(key + " (part)", buy[key][0], buy[key][1], coll)
            elif kind == "buyflat":                                   # long tubes lie down so they hide nothing
                ob = to_blender(key + " (part)", buy[key][0].rotate((0, 90, 0)), buy[key][1], coll)
            elif kind == "pad":
                ob = to_blender(key + " (part)", padbuy[key][0], padbuy[key][1], coll)
            elif kind == "rod":
                ob = to_blender("launch_rod_6mm_1m (part)", cyl(3.0, 1000.0, 0.0, segs=24).rotate((0, 90, 0)), M["steel"], coll)
            elif kind == "dowel":
                ob = to_blender("leg_dowel_22mm (part)", cyl(LEG_D / 2, LEG_L, 0.0, segs=32).rotate((0, 90, 0)), M["wood"], coll)
            else:
                ob = curve_obj("ejection_spring (part)", spring_pts(), M["steel"], coll, radius=0.75)
            lo, hi = _extent(ob)
            wl = max(len(line) for line in label.split("\n")) * TXT * 0.56
            made.append((ob, lo, hi, label, max(hi[0] - lo[0], wl)))
        h_max = max(it[2][2] - it[1][2] for it in made)      # a sign above the group, clear of its tallest part
        _flat_text(coll, title, x0, y, floor_z + h_max + 14.0, 16.0, align="LEFT", upright=True)
        y -= 12.0
        rows, x = [[]], x0
        for it in made:
            if rows[-1] and x + it[4] > x0 + MAX_W:
                rows.append([])
                x = x0
            rows[-1].append((it, x))
            x += it[4] + GAP
        for row in rows:
            depth = max(it[2][1] - it[1][1] for it, _ in row)
            y -= 0.8 * max(it[2][2] - it[1][2] for it, _ in row)     # tall parts stand clear of the labels behind them
            cy = y - depth / 2
            nl = max(len(it[3].split("\n")) for it, _ in row)
            for (ob, lo, hi, label, w), cx in row:
                ob.location = (cx + (w - (hi[0] - lo[0])) / 2 - lo[0], cy - (lo[1] + hi[1]) / 2, floor_z - lo[2])
                _flat_text(coll, label, cx + w / 2, y - depth - 12.0, floor_z + 0.2, TXT)
            y -= depth + 12.0 + nl * TXT * 1.3 + 18.0
        y -= 30.0


def part_of(name):
    """'nose', 'middle', 'bottom' or 'tvc': where a rocket solid belongs when the rocket comes apart"""
    pname = None
    for n2, p in PARTS.items():
        if name == n2 or name.startswith(n2 + "_"):
            pname = p["part"]
    if pname is None:
        if name.startswith("nose_ballast"):
            pname = "nose"
        elif name.startswith(("servo_MG90S_tvc", "horn_tvc", "pushrod_ring", "pushrod_holder", MOTOR_NAME)):
            pname = "tvc"
        elif name.startswith(("servo_MG90S_release", "horn_release", "latch_spring", MID_TUBE, "parachute", "shock_cord", "payload")):
            pname = "middle"
        else:
            pname = "bottom"
    return pname


def build_rocket_file(path):
    """kestrel_rocket.blend: only the constructed rocket, every part in place (inside and out) and the servo leads,
    grouped by the part of the rocket it belongs to; the body tubes in a collection of their own so they can be hidden
    to look inside"""
    reset_scene()
    M = MATS()
    buy = purchased(M)
    groups = {"nose": "1 Nose cone (with its ballast)", "middle": "2 Middle part (payload bay, parachute bay, release latch)",
              "bottom": "3 Bottom part (fins, tabs + servos, camera, flight computer)", "tvc": "4 TVC module (motor gimbal)"}
    for g in groups.values():
        collection(g)
    tubes = collection("Body tubes (hide them to look inside)")
    for name, m, material in rocket_items(buy):
        to_blender(name, m, material, tubes if name in (LOWER_TUBE, MID_TUBE) else collection(groups[part_of(name)]))
    curve_obj("ejection_spring", spring_pts(), M["steel"], collection(groups["middle"]), radius=0.75)
    lead_objects(M, collection("5 Servo leads"))
    sc = bpy.context.scene
    sc.name = "KESTREL-2 (constructed)"
    _lights(sc)
    sc.render.resolution_x, sc.render.resolution_y = 1100, 1600
    _overview_camera(sc, "cam_rocket", (0, 0, 435), (0.55, -1.25, 0.35), 1750.0, lens=50.0)
    _frame_viewports((0, 0, 435), (0.55, -1.25, 0.35), 1500.0)
    _finish_scenes()
    bpy.ops.wm.save_as_mainfile(filepath=path)


def organize_main_file(M, buy, items):
    main = bpy.context.scene
    lights = _lights(main)
    main.name = "1 Rocket + all parts"
    plan = [("2 Exploded view", ["Exploded view"], ["cam_rocket_exploded"], 0.0),
            ("3 Cut-aways", ["Section av-bay", "Section TVC", "Section latch"],
             ["cam_avbay_cutaway", "cam_tvc_gimbal_cutaway", "cam_release_latch_cutaway"], 250.0),
            ("4 Payload door open", ["Payload door open"], ["cam_payload_bay_open"], 0.0),
            ("5 Fin tabs deflected", ["Tab deflected"], ["cam_fin_tab_closeup"], 0.0),
            ("6 Fin cut open", ["Section fin"], ["cam_fin_servo_cutaway"], 0.0),
            ("7 On the launch pad", ["Rocket on pad", "Launch pad", "Ground"], ["cam_rocket_on_pad", "cam_launch_pad"], 0.0)]
    for sname, colls, cams, dx in plan:
        sc = _scene_like(sname, main)
        sc.collection.children.link(lights)
        _move_to_scene(sc, main, colls, cams, dx)
    tools = bpy.data.collections.get("Build tools")          # shown in the parts layout instead
    if tools is not None:
        main.collection.children.unlink(tools)
        for o in list(tools.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(tools)
    c_cut = collection("Rocket cut open (everything inside)")
    build_cutopen_rocket(M, items, c_cut, CUT_DX)
    c_lay = collection("All parts (laid out)")
    build_parts_layout(M, buy, c_lay, CUT_DX + 200.0, 300.0, FOOT_Z)
    for x, txt in ((0.0, "complete rocket\n(everything on it\nand inside it)"), (CUT_DX, "the same rocket\ncut open")):
        _flat_text(c_cut, txt, x, -120.0, FOOT_Z + 0.2, 11.0)
    lo, hi = _content_bbox([bpy.data.collections["Rocket (assembled)"], c_cut, c_lay])
    center = (lo + hi) / 2
    dist = (hi - lo).length * 1.15
    _overview_camera(main, "cam_overview", center, (0.55, -1.25, 1.3), dist)
    _frame_viewports(center, (0.55, -1.25, 1.3), dist)
    _finish_scenes({"3 Cut-aways": (0.5, 1.6, 0.6), "6 Fin cut open": (0.25, 1.0, 0.2)})


def organize_tvc_file(c_tex_name):
    main = bpy.context.scene
    lights = _lights(main)
    main.name = "1 TVC module"
    sc = _scene_like("2 Assembly steps", main)
    sc.collection.children.link(lights)
    _move_to_scene(sc, main, [c_tex_name], ["cam_tvc_module_assembly_steps"])
    cam = bpy.data.objects.get("cam_tvc_module")
    if cam is not None:
        main.camera = cam
    else:
        _overview_camera(main, "cam_tvc_module", (0, 0, 112), (215, -265, 103), 370.0, lens=50.0)
    _frame_viewports((0, 0, 100), (215, -265, 103), 600.0)
    _finish_scenes(default_dir=(0.2, -1.0, 0.25))


def organize_parachute_file():
    _lights(bpy.context.scene)
    _frame_viewports((0, 0, 1950), (2100, -3300, -150), 4300.0)
    if bpy.context.scene.camera is None:
        _overview_camera(bpy.context.scene, "cam_parachute_open", (0, 0, 1900), (2100, -3300, -150), 3915.0, lens=60.0)
    _finish_scenes()


def main():
    reset_scene()
    M = MATS()
    tail_z = build_all(M)
    export_stls()
    check_layout()
    buy0 = purchased(M)
    bad = interference_report(buy0)
    rows = sweep_reports(buy0)
    leads = lead_paths()
    comp = component_positions(buy0, leads)
    if bad or rows:
        raise SystemExit(f"{len(bad)} interfering pairs, {len(rows)} mechanism contacts - see cad/interference_report.md")

    # ------------------------------------------------------------------ main assembly file
    c_rk = collection("Rocket (assembled)")
    c_pad = collection("Launch pad")
    c_tool = collection("Build tools")
    c_on = collection("Rocket on pad")
    c_ex = collection("Exploded view")
    c_gnd = collection("Ground")
    buy = purchased(M)
    items = rocket_items(buy)
    add_solids(items, c_rk)
    lead_objects(M, c_rk)
    curve_obj("ejection_spring", spring_pts(), M["steel"], c_rk, radius=0.75)
    for name, p in PARTS.items():
        if p["group"] == "tool":
            to_blender(name, p["m"], p["material"], c_tool)
        elif p["group"] == "pad" and name not in ("pad_leg_foot", "rod_tip_safety_cap", "pad_rod_stop"):
            for i, mi in enumerate(p["inst"]):
                to_blender(name if i == 0 else f"{name}_{i + 1}", mi, p["material"], c_pad)
    for k in range(3):
        foot = leg_axis_transform(PARTS["pad_leg_foot"]["m"].translate((0, 0, -LEG_L + 25.0 - 5.0)), k)
        to_blender(f"pad_leg_foot_{k + 1}", foot, PARTS["pad_leg_foot"]["material"], c_pad)
    for name, (m, material) in pad_purchased(M, HUB_H - 4.0).items():
        to_blender(name, m, material, c_pad)
    on_off = (ROCKET_XY[0], ROCKET_XY[1], tail_z)
    add_solids(items, c_on, on_off, suffix="_pad")
    lead_objects(M, c_on, on_off, suffix="_pad")
    curve_obj("ejection_spring_pad", spring_pts(), M["steel"], c_on, radius=0.75).location = on_off
    # exploded view: the three parts pulled apart along the axis, sub-assemblies beside them
    part_dz = {"nose": 300.0, "middle": 150.0, "bottom": 0.0, "tvc": -260.0}
    side = {"tvc": 0.0}
    for name, m, material in items:
        pname = part_of(name)
        dz = part_dz.get(pname, 0.0)
        ob = to_blender(name + "_ex", m, material, c_ex)
        ob.location = (side.get(pname, 0.0), 0, dz)
    curve_obj("ejection_spring_ex", spring_pts(), M["steel"], c_ex, radius=0.75).location = (0, 0, part_dz["middle"])
    lab = mat("Label", (0.05, 0.05, 0.06), rough=0.6)
    for txt, z in (("3  NOSE CONE", Z_NOSE0 + part_dz["nose"] + 20), ("2  MIDDLE PART\n   payload bay + door\n   wall\n   parachute bay\n   release latch\n   upper launch lug", 520 + part_dz["middle"]),
                   ("1  BOTTOM PART\n   avionics bay + battery hatch\n   camera\n   4 fins\n   4 replaceable legs\n   4 control tabs", 230),
                   ("TVC module\n(slides out of\nthe bottom)", 40 + part_dz["tvc"])):
        cu = bpy.data.curves.new("label", "FONT")
        cu.body = txt
        cu.size = 26.0
        cu.space_line = 1.05
        ob = bpy.data.objects.new("label_" + txt.split()[0], cu)
        ob.data.materials.append(lab)
        ob.location = (120.0, 0.0, z)
        ob.rotation_euler = (math.radians(90), 0, math.radians(28))
        c_ex.objects.link(ob)
    foot_z = min((ob.matrix_world @ Vector(v)).z for ob in c_pad.objects if ob.type == "MESH" for v in ob.bound_box)
    to_blender("ground", cyl(60000.0, 2.0, foot_z - 2.0, segs=96), mat("Ground", (0.30, 0.34, 0.26), rough=0.95), c_gnd)
    # half sections
    shells = {"avbay_coupler", "fin_can", "tvc_frame", "nose_cone", "top_latch_insert", "payload_wall", "spring_piston",
              "payload_door_frame", LOWER_TUBE, MID_TUBE}
    cut_sets = {"Section av-bay": (4.5, shells | {"avbay_sled", "lipo_overlander_350_2s"}),
                "Section TVC": (0.0, shells),
                "Section latch": (BOLT_Y, shells | {"latch_bolt", "parachute_packed", "shock_cord_kevlar_elastic"})}
    for cname, cut in cut_sets.items():
        cc = collection(cname)
        add_solids(rocket_items(buy, cut=cut, skip=("upper_launch_lug",)), cc, suffix="_" + cname[-3:])
    # payload door open
    c_door = collection("Payload door open")
    door_items = [it for it in items if not it[0].startswith(("payload_door", "fin_", "servo_MG90S_tab", "horn_tab"))]
    add_solids(door_items, c_door, suffix="_dr")
    for nm, m, mt in (("payload_door_open", door_solid(75.0), M["orange"]), ("latch_knob_open", latch_knob_solid(75.0), M["black"]),
                      ("latch_cam_open", latch_cam_solid(False, 75.0), M["black"])):
        to_blender(nm, m, mt, c_door)
    # fin / tab close-up with the tab deflected
    c_tab = collection("Tab deflected")
    buy_t = purchased(M, tab_delta=12.0)
    tab_items = [it for it in rocket_items(buy_t) if not it[0].startswith("fin_control_tab")]
    add_solids(tab_items, c_tab, suffix="_tb")
    for k, a in enumerate(FIN_ANG):
        to_blender(f"fin_control_tab_def_{k + 1}", polar(tab_local(12.0), a), M["blue"], c_tab)
    # one fin cut through its mid-plane: servo in its pocket, horn glued in the tab, pin in the root slot, lead in its
    # groove and channel (fin 1 turned to +x, the half at y > 0 removed)
    c_fs = collection("Section fin")
    half = box(2000.0, 1000.0, 4000.0, 0, 500.0, 500.0)
    fc1 = PARTS["fin_can"]["m"].rotate((0, 0, -FIN_ANG[0])) ^ bx(CAN_RI - 6.0, TIP_R + 5.0, -40.0, 40.0, FOOT_Z - 5.0,
                                                                   FIN["root_chord"] + 15.0)
    for nm, m, mt in (("fin_can_fs", fc1 - half, M["orange"]), ("fin_control_tab_fs", tab_local(0.0) - half, M["blue"]),
                      ("servo_MG90S_tab_fs", tab_servo_local() - half, M["servo"]),
                      ("horn_tab_fs", tab_horn_local(0.0) - half, M["horn"]),
                      ("fin_leg_fs", leg_local() - half, M["black"]), ("leg_bolt_fs", leg_bolt_local() - half, M["steel"])):
        to_blender(nm, m, mt, c_fs)
    a0 = math.radians(GROOVE_ANG[0])
    lead1 = [(x * math.cos(a0) + y * math.sin(a0), -x * math.sin(a0) + y * math.cos(a0), z) for x, y, z in lead_paths()["lead_tab1"]]
    lead1 = [q for q in lead1 if q[0] > CAN_RI - 6.0 and q[2] < FIN["root_chord"]]
    for i, c in enumerate((M["wire_br"], M["wire_r"], M["wire_or"])):
        curve_obj(f"lead_tab1_fs_{i}", [(x, y - 1.6 + (i - 1) * 0.9, z) for x, y, z in lead1], c, c_fs, radius=0.45)
    # labels (the camera looks at the cut face from +y, so the fin tip is on the left of the picture)
    lab_fs = mat("Label", (0.05, 0.05, 0.06), rough=0.6)
    for txt, x, z in (("MG90S tab servo,\nslid in from the fin tip", TIP_R + 47.0, SV_ZC + 2.0),
                      ("lead groove", TIP_R + 30.0, (SV_Z0 + SV["L"] + CH_Z0) / 2 - 1.0),
                      ("lead channel to the can", TAB_X1 + 12.0, CH_Z1 + 4.0),
                      ("control tab", TAB_X1 - 4.0, -TE_EXT - 6.0),
                      ("horn glued in the tab,\non the servo spline", TAB_X1 + 4.0, -TE_EXT - 14.0),
                      ("root pin", CAN_RO - 1.5, HINGE_Z - 1.0),
                      ("replaceable leg (tough PLA)\non the fin can's tongue,\none M3 bolt", TIP_R + 47.0, FOOT_Z + 10.0)):
        cu = bpy.data.curves.new("label_fs", "FONT")
        cu.body = txt
        cu.size = 3.6
        cu.space_line = 1.1
        ob = bpy.data.objects.new("label_fs_" + txt.split()[0], cu)
        ob.data.materials.append(lab_fs)
        ob.location = (x, 3.0, z)
        ob.rotation_euler = (math.radians(90), 0, math.radians(180))
        c_fs.objects.link(ob)
    if "--no-render" not in ARGS:
        setup_render()
        top = tail_z + Z_TIP
        zav = (Z_AV0 + SH_TOP) / 2
        views = [
            ("rocket_on_pad", (1100, -2600, 520), (0, 0, (foot_z + top) / 2 + 30), 50, {c_on.name, c_pad.name, c_gnd.name}, (1100, 1600)),
            ("rocket_exploded", (1250, -2350, 560), (110, 0, 500), 50, {c_ex.name}, (1200, 1700)),
            ("avbay_cutaway", (90, 360, zav + 60), (0, -4, zav + 20), 50, {"Section av-bay"}, (1200, 1600)),
            ("tvc_gimbal_cutaway", (110, 330, 140), (0, -4, 70), 50, {"Section TVC"}, (1200, 1600)),
            ("release_latch_cutaway", (-120, 230, BOLT_Z + 40), (-14, 0, BOLT_Z - 15), 50, {"Section latch"}, (1200, 1200)),
            ("payload_bay_open", (175, -120, 450), (24, 0, 408), 50, {c_door.name}, (1200, 1200)),
            ("fin_tab_closeup", (-60, 270, 75), (30, 45, 22), 50, {c_tab.name}, (1400, 1100)),
            ("fin_servo_cutaway", (70, 250, 35), (53, 0, 25), 50, {c_fs.name}, (1400, 1200)),
            ("launch_pad", (1000, -1250, 420), (0, 0, foot_z / 2 + 60), 40, {c_pad.name, c_gnd.name}, (1600, 1000)),
        ]
        render_views(views)
    organize_main_file(M, buy, items)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "kestrel.blend"))

    # ------------------------------------------------------------------ the constructed rocket on its own
    build_rocket_file(os.path.join(HERE, "kestrel_rocket.blend"))

    # ------------------------------------------------------------------ TVC module file
    reset_scene()
    M = MATS()
    c_tvc = collection("TVC module (assembled)")
    c_tex = collection("TVC module (assembly steps)")
    buy = purchased(M)
    tvc_names = ["tvc_frame", "tvc_gimbal_ring", "tvc_motor_holder", "tvc_motor_retainer"]
    tvc_buy = [MOTOR_NAME, "servo_MG90S_tvc_ring", "servo_MG90S_tvc_holder", "horn_tvc_ring", "horn_tvc_holder",
               "pushrod_ring_1.2mm", "pushrod_holder_1.2mm"]
    tvc_items = [(n, PARTS[n]["m"], PARTS[n]["material"]) for n in tvc_names] + [(n, buy[n][0], buy[n][1]) for n in tvc_buy]
    add_solids(tvc_items, c_tvc)
    tops = {}
    for n in ("lead_tvc_ring", "lead_tvc_holder"):
        pts = [p for p in lead_paths()[n] if p[2] <= FRAME_TOP + 30] + [(lead_paths()[n][3][0], lead_paths()[n][3][1], FRAME_TOP + 90)]
        tops[n] = pts
    cols = [M["wire_br"], M["wire_r"], M["wire_or"]]
    for n, pts in tops.items():
        for i, c in enumerate(cols):
            d = (i - 1) * 0.9
            curve_obj(f"{n}_{i}", [(x + d * 0.7, y + d * 0.7, z) for x, y, z in pts], c, c_tvc, radius=0.45)
        x, y, z = pts[-1]
        to_blender(n + "_plug", box(8.0, 4.0, 14.0, x, y, z + 7.0), M["servo"], c_tvc)
    # assembly steps, left to right in build order (the motor + retainer go in at the field)
    steps = {"tvc_motor_holder": (-150, 0), "tvc_gimbal_ring": (-85, 0), "tvc_frame": (0, 0),
             "servo_MG90S_tvc_ring": (75, 0), "horn_tvc_ring": (75, 0), "servo_MG90S_tvc_holder": (118, 0),
             "horn_tvc_holder": (118, 0), "pushrod_ring_1.2mm": (158, 0), "pushrod_holder_1.2mm": (162, 0),
             MOTOR_NAME: (-228, -40), "tvc_motor_retainer": (-228, -62)}
    for n, m, mt in tvc_items:
        dx, dz = steps[n]
        ob = to_blender(n + "_step", m, mt, c_tex)
        ob.location = (dx, 0, dz)
    lab = mat("Label", (0.05, 0.05, 0.06), rough=0.6)
    for x, txt in ((-150, "1  holder +\npenny washer"), (-85, "2  gimbal\nring"), (0, "3  frame"), (100, "4  servos\nports 1 + 2"),
                   (172, "5  pushrods"), (-228, "6  motor +\nretainer\n(at the field)")):
        cu = bpy.data.curves.new("step_label", "FONT")
        cu.body = txt
        cu.size = 11.0
        cu.space_line = 1.05
        cu.align_x = "CENTER"
        ob = bpy.data.objects.new("step_label_" + txt.split()[0], cu)
        ob.data.materials.append(lab)
        ob.location = (x, 0.0, -96.0)
        ob.rotation_euler = (math.radians(90), 0, 0)
        c_tex.objects.link(ob)
    if "--no-render" not in ARGS:
        setup_render()
        render_views([("tvc_module", (215, -265, 215), (0, 0, 112), 50, {c_tvc.name}, (1100, 1500)),
                      ("tvc_module_assembly_steps", (-22, -780, 150), (-22, 0, 18), 50, {c_tex.name}, (1700, 1000))])
    organize_tvc_file(c_tex.name)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "kestrel_tvc_module.blend"))

    # ------------------------------------------------------------------ parachute-open file
    reset_scene()
    M = MATS()
    c_ch = collection("Descent under parachute")
    buy = purchased(M)
    gores, Rp, H = parachute_open_solids(M)
    z_canopy = 2900.0
    for k, g in enumerate(gores):
        to_blender(f"canopy_gore_{k + 1}", g.translate((0, 0, z_canopy)), M["nylon"] if k % 2 == 0 else M["nylon2"], c_ch)
    conf = (0.0, 0.0, z_canopy - 0.9 * 2 * Rp)
    for k in range(8):
        a = math.radians(45 * k)
        curve_obj(f"shroud_line_{k + 1}", [(Rp * math.cos(a) * 0.98, Rp * math.sin(a) * 0.98, z_canopy + H * math.cos(1.45)), conf],
                  M["nylon2"], c_ch, radius=0.5)
    # rocket hangs from the cord leaving the open top of the middle tube; nose cone on the cord in between
    tilt = 14.0
    hang = (60.0, 0.0, 950.0)
    skip = {"nose_cone", "nose_ballast_M3_nuts", "parachute_packed", "shock_cord_kevlar_elastic", "pad_rod_stop"}
    rk = [it for it in rocket_items(buy, skip=skip)]
    ob_list = add_solids(rk, c_ch)
    lead_objects(M, c_ch)
    for ob in list(c_ch.objects):
        if ob.name.startswith(("canopy", "shroud")):
            continue
        ob.rotation_euler = (0, math.radians(tilt), 0)
        ob.location = hang
    top_pt = Vector((0, 0, Z_WALL1 + 10)).copy()
    import mathutils
    rot = mathutils.Matrix.Rotation(math.radians(tilt), 3, "Y")
    top_w = rot @ Vector((0, 0, Z_MID1)) + Vector(hang)
    wall_w = rot @ Vector((0, 18.5, Z_WALL1 + 6)) + Vector(hang)
    nose_pos = Vector((-90.0, 30.0, conf[2] - 620.0))
    cpath = [wall_w, top_w + Vector((0, 0, 40))]
    for f in (0.25, 0.5, 0.75):
        cpath.append(top_w.lerp(nose_pos, f) + Vector((14.0 * math.sin(math.pi * f), 0, 0)))
    cpath.append(nose_pos)
    for f in (0.33, 0.66):
        cpath.append(nose_pos.lerp(Vector(conf), f) + Vector((-10.0 * math.sin(math.pi * f), 0, 0)))
    cpath.append(Vector(conf))
    curve_obj("shock_cord", [tuple(v) for v in cpath], M["cord"], c_ch, radius=0.9)
    nose = PARTS["nose_cone"]["m"].translate((0, 0, -Z_MID1))
    ob = to_blender("nose_cone_on_cord", nose, M["orange"], c_ch)
    ob.rotation_euler = (math.radians(170), math.radians(10), 0)
    ob.location = nose_pos
    if "--no-render" not in ARGS:
        setup_render(world=(0.45, 0.62, 0.88), strength=0.7)
        render_views([("parachute_open", (2100, -3300, 1750), (0, 0, 1900), 60, {c_ch.name}, (1100, 1600))])
    organize_parachute_file()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "kestrel_parachute_open.blend"))
    print("CAD done. component positions:", len(comp))


if not os.environ.get("KESTREL_CAD_LIB"):
    main()
