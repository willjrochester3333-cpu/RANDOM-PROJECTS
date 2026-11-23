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
  cad/kestrel.blend                   full assembly, rocket on the pad, exploded view, sections, launch pad
  cad/kestrel_tvc_module.blend        the TVC module on its own (its two servo leads come out of the top)
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
# TVC (unchanged from KESTREL-1, flight-proven geometry in the gimbal sweep)
MOTOR_D = TVC["motor_diameter"]
MOTOR_L = 95.0
Z_MOTOR0 = -TVC["nozzle_protrusion"]
Z_PIVOT = TVC["pivot_from_tail"]
HOLD_RI = MOTOR_D / 2 + 0.2
HOLD_R = HOLD_RI + 1.6
RING_RI, RING_R = HOLD_R + 1.4, HOLD_R + 4.4
FRAME_R = INS_R
FRAME_TOP = 156.0
SV = dict(L=22.8, W=12.2, H=22.5, tab_L=32.2, tab_t=2.5, tab_z=15.9, shaft_off=5.9, spline=5.0, pitch=27.8)
SV_MASS = 13.4
SV1_Z, SV2_Z = 120.0, 145.0
SV_SHAFT_R = 16.0
PR1 = (9.0, 18.0)
PR2 = (18.0, 9.0)
HOLDER_TAB_Z = Z_PIVOT + 12.0
TAIL_SCREW_Z, TAIL_SCREW_ANG = 16.0, (90.0, 210.0)
# fins, legs, control tabs, tab-servo pods
NF = FIN["count"]
FIN_ANG = [FIN["first_fin_deg"] + 360.0 * k / NF for k in range(NF)]     # 45, 135, 225, 315 (X layout)
CAN_RI = R + 0.10
CAN_RO = CAN_RI + FIN["can_wall"]        # 29.45
FT = FIN["thickness"]
TIP_R = CAN_RO + FIN["span"]            # 79.45
TABP = FIN["tab"]
HINGE_RB = 1.8                          # hinge bead radius (fin knuckles, tab knuckle, stiffening rib)
HINGE_Z = TABP["chord"] - HINGE_RB      # 16.2
TAB_R0, TAB_R1 = CAN_RO + TABP["r_from"], CAN_RO + TABP["r_to"]
KN = 4.0
LEGP = FIN["leg"]
LEG_R0 = TIP_R - LEGP["width"]
FOOT_Z = -LEGP["length"]                # -30: the rocket stands on its four fin tips
# fin-local frame: x along the fin (radial), y normal to it (+y = pod side), z.  Fin k = local frame rotated by FIN_ANG[k].
PSV_Y0 = FT / 2 + 1.2                   # servo side face nearest the fin
PSV_YC = PSV_Y0 + SV["W"] / 2           # 8.5
PSV_X0 = 31.0                           # servo base; the output shaft points radially outwards
PSV_Z0 = 32.1                           # servo body aft end (shaft end, nearest the tab)
PSV_SHAFT_Z = PSV_Z0 + SV["shaft_off"]  # 38.0
PSV_ZC = PSV_Z0 + SV["L"] / 2
HORN_X = PSV_X0 + SV["H"] + 3.0         # 56.5 horn plane (servo horn and tab horn)
HORN_ARM = 6.0                          # servo horn hole radius
PUSH_Y = PSV_YC + HORN_ARM              # 14.5 pushrod line, also the tab-horn lever arm
PUSH_X = HORN_X + 1.5                   # wire runs just outboard of both horns, Z-bends into them
POD_Y1 = PSV_Y0 + SV["W"] + 1.2         # 15.8 pod outer wall
POD_X1 = PSV_X0 + 21.5                  # 52.5 top of the pod walls
POD_Z0, POD_Z1, POD_ZN = PSV_Z0 - 6.2, PSV_Z0 + SV["L"] + 8.1, PSV_Z0 + SV["L"] + 33.0
GROOVE_ANG = [a + math.degrees(math.atan2(PSV_YC, CAN_RO)) for a in FIN_ANG]   # tab-servo lead entry / frame groove
# tab-servo lead slot through the pod floor, the fin-can wall and the tube: as long as the servo, so the plug
# (about 7.6 x 2.6 mm) passes whichever end of the servo case the lead leaves from
CAB_Z0, CAB_Z1 = PSV_Z0 + 2.0, PSV_Z0 + SV["L"] - 2.0
# camera pod, avionics
CAM_Z0 = 200.0
CAM_POCKET = 23.6
CAM_FLOOR = 1.8
CAM_RC = R + 1.5
CAM_WIN_W, CAM_WIN_H = CAM_POCKET + 2 * 1.6 + 0.2, 30.0
RADIAL_SCREW_ANG = (0.0, 180.0)
STATIC_PORT_ANG = (30.0, 150.0, 270.0)
LUG_ANG = 90.0
UPPER_LUG_Z = 300.0
BATT = dict(w=BAT["width"], t=BAT["thickness"], l=BAT["length"], y0=4.0, z0=Z_AV0 + 14.0)
BAY = dict(w=BAT["width"] + 1.0, t=BAT["thickness"] + 1.0, l=BAT["length"] + 6.0)
# middle part
DOOR_Z0, DOOR_H, DOOR_W = 380.0, PAY["door_height"], PAY["door_width"]
DHX, DHZ = R + 0.45, DOOR_Z0 + 2.0      # door hinge axis (along Y), just outside the tube surface
LATCH_Z = DOOR_Z0 + DOOR_H - 6.0
JOINT_ANG, JOINT_Z = (90.0, 270.0), Z_MID0 + 14.0
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
MOTOR_NAME = "motor_" + D["launch"]["nominal_motor"].replace("-", "_") + "_24x95"
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
    return register("nose_cone", m, M["orange"], part="nose",
                    note="Print tip-up, 3 walls, 10% gyroid, no supports (the bulkhead is a 45 deg cone). Slides over the top insert; the latch bolt clicks into its hole")


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
    for a in (0.0, 120.0, 240.0):
        w = (tube(INS_R + 1, INS_R - iw - 1, 52.0, Z_AV0 + 22.0, segs=96) ^ polar(box(60, 34, 60, 30, 0, Z_AV0 + 48.0), a + 60.0))
        m = m - w
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
    # battery tray behind the Pico (pack on a ledge, velcro strap through two slots)
    ty = BATT["y0"] + BAY["t"] + 0.8
    th = BAY["l"] + 16.0
    tray = box(BAY["w"] + 5.0, 1.6, th, 0, ty, z0 + 2.5 + th / 2)
    for sx in (1, -1):
        tray = tray + box(1.6, 6.0, th, sx * (BAY["w"] / 2 + 0.8), ty - 3.6, z0 + 2.5 + th / 2)
    # battery ledge: a 45 deg wedge growing out of the tray wall (prints without supports, leaves room for the servo leads)
    y_w = ty - 0.5
    ledge = xz_plate([(11.0, BATT["z0"]), (y_w, BATT["z0"]), (y_w, BATT["z0"] - (y_w - 11.0))], BAY["w"] - 1.0).rotate((0, 0, 90))
    tray = tray + ledge
    for zz in (BATT["z0"] - z0 + 8.0, BATT["z0"] - z0 + BATT["l"] - 8.0):
        tray = tray - box(BAY["w"] - 4.0, 4.0, 3.2, 0, ty, z0 + zz)
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
    z1 = Z_MOTOR0 + MOTOR_L + 1.5 + 2.5
    zc = z1 - 2.2
    m = revolve([(HOLD_RI, 0.0), (HOLD_R, 0.0), (HOLD_R, z1), (0.0, z1), (0.0, zc), (12.6, zc),
                 (12.6, zc - 1.9), (HOLD_RI, zc - 1.9)])
    for sy in (1, -1):
        m = m + ycyl(3.4, 1.1, 32).translate((0, sy * (HOLD_R + 0.15), Z_PIVOT))
    for sy in (1, -1):
        m = m - ycyl(1.25, 3.0, 16).translate((0, sy * (HOLD_R + 0.15), Z_PIVOT))
    tab = box(8.5, 4.0, 4.0, HOLD_R + 3.4, PR2[1], HOLDER_TAB_Z) + box(5.0, PR2[1] + 2.0, 4.0, HOLD_R + 0.8, PR2[1] / 2, HOLDER_TAB_Z)
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
    tab = box(6.0, 5.0, 3.0, PR1[0], PR1[1] + 0.5, Z_PIVOT) + box(5.0, 6.0, 3.0, PR1[0] - 2.0, RING_R - 0.5, Z_PIVOT)
    m = m + tab - cyl(0.7, 6.0, Z_PIVOT - 3.0, PR1[0], PR1[1], segs=16)
    return register("tvc_gimbal_ring", m, M["orange"], part="tvc", note="PETG")


def tvc_frame(M):
    ro = FRAME_R
    ri = ro - 1.0
    m = tube(ro, ri, FRAME_TOP, 0.0)
    windows = [(22.0, 40.0), (56.0, 94.0), (105.0, 121.0), (133.0, 149.0)]
    for z0, z1 in windows:
        w = tube(ro + 1.0, ri - 1.0, z1 - z0, z0, segs=96)
        for a in GROOVE_ANG:
            w = w - polar(box(14.0, 9.0, z1 - z0 + 2.0, ro - 2.0, 0, (z0 + z1) / 2), a)
        m = m - w
    # longerons carrying the 4 tab-servo leads in outside grooves (lead enters through the tube next to its pod)
    for a in GROOVE_ANG:
        lon = polar(bx(ro - 3.0, ro, -3.5, 3.5, CAB_Z0 - 4.0, FRAME_TOP), a) ^ cyl(ro, 300, -1)
        m = m + lon
        m = m - polar(bx(ro - 1.6, ro + 1.0, -2.1, 2.1, CAB_Z0 - 2.0, FRAME_TOP + 1.0), a)
    m = m + tube(ro, 24.6, 4.0, 0.0)
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


def retainer(M):
    z0 = Z_MOTOR0 - 1.5
    m = tube(HOLD_R + 3.4, HOLD_R + 0.3, 13.0, z0) + tube(HOLD_R + 3.4, 8.0, 1.5, z0)
    for a in (45, 225):
        m = m - polar(box(4.0, 5.6, 7.0, HOLD_R + 1.4, 0, z0 + 1.5 + 3.5 + 4.5), a)
        m = m - polar(box(4.0, 9.0, 3.6, HOLD_R + 1.4, 3.0, 4.0), a)
    return register("tvc_motor_retainer", m, M["orange"], part="tvc", note="Twist-lock: push up over the lugs and turn 45 deg")


# ---------------- fins, legs, control tabs and their servos (built for one fin in the local frame) ----------------
def fin_local():
    cr, ct = FIN["root_chord"], FIN["tip_chord"]
    prof = [(CAN_RO - 0.6, 0.0), (LEG_R0, 0.0), (LEG_R0 + 3.0, FOOT_Z + 3.0), (LEG_R0 + 4.0, FOOT_Z), (TIP_R - 1.0, FOOT_Z),
            (TIP_R, FOOT_Z + 1.0), (TIP_R, ct), (CAN_RO - 0.6, cr)]
    f = xz_plate(prof, FT)
    f = f + bx(LEG_R0 + 4.6, TIP_R - 1.6, -3.0, 3.0, FOOT_Z, FOOT_Z + 2.6)                     # foot pad
    f = f + xcyl(HINGE_RB, TAB_R1 - TAB_R0, 32).translate(((TAB_R0 + TAB_R1) / 2, 0, HINGE_Z))   # knuckle bead
    f = f - bx(TAB_R0 + KN, TAB_R1 - KN, -5, 5, -1.0, TABP["chord"] + 0.4)                    # tab cut-out
    f = f - bx(TAB_R0, TAB_R1, -5, 5, -1.0, HINGE_Z - HINGE_RB - 0.4)                          # (under the fin knuckles too)
    # the two fin knuckles are C-clips: the tab's 1.2 mm wire pin snaps in from behind through a 0.95 mm slot
    f = f - xcyl(0.63, TAB_R1 - TAB_R0 + 1.0, 16).translate(((TAB_R0 + TAB_R1) / 2, 0, HINGE_Z))
    f = f - bx(TAB_R0 - 0.5, TAB_R1 + 0.5, -0.475, 0.475, HINGE_Z - HINGE_RB - 1.0, HINGE_Z)
    return f


def pod_local():
    """streamlined pod on the +y side of the fin root holding an MG90S, shaft radially out"""
    shell = M3.batch_hull([bx(CAN_RO - 3.0, POD_X1, FT / 2 - 0.2, POD_Y1, POD_Z0, POD_Z1),
                           bx(CAN_RO - 3.0, CAN_RO + 3.0, FT / 2 - 0.2, FT / 2 + 2.5, POD_ZN - 1.0, POD_ZN)])
    shell = shell - cyl(CAN_RI, 300, -10)
    s = SV
    shell = shell - bx(PSV_X0 - 0.2, 90, PSV_Y0 - 0.2, PSV_Y0 + s["W"] + 0.2, PSV_Z0 - 0.2, PSV_Z0 + s["L"] + 0.2)
    shell = shell - bx(PSV_X0 + s["tab_z"] - 0.1, 90, PSV_YC - (s["W"] - 1) / 2 - 0.3, PSV_YC + (s["W"] - 1) / 2 + 0.3,
                       PSV_ZC - s["tab_L"] / 2 - 0.3, PSV_ZC + s["tab_L"] / 2 + 0.3)
    for dz in (-1, 1):
        shell = shell - xcyl(0.8, 14, 12).translate((PSV_X0 + s["tab_z"] - 6.0, PSV_YC, PSV_ZC + dz * s["pitch"] / 2))
    return shell


def cable_hole_local():
    return bx(CAN_RI - 3.0, PSV_X0 + 1.0, PSV_YC - 2.0, PSV_YC + 2.0, CAB_Z0, CAB_Z1)


def tab_local(delta=0.0):
    """control tab (printed separately), hinged on a 1.2 mm music-wire pin; horn on the pod side"""
    c = TABP["chord"]
    t = bx(TAB_R0 + KN + 0.4, TAB_R1 - KN - 0.4, -FT / 2, FT / 2, 0.4, HINGE_Z)
    t = t + bx(TAB_R0 + 0.4, TAB_R1 - 0.4, -FT / 2, FT / 2, 0.4, HINGE_Z - HINGE_RB - 0.8)
    t = t + xcyl(HINGE_RB, TAB_R1 - TAB_R0 - 2 * KN - 0.8, 32).translate(((TAB_R0 + TAB_R1) / 2, 0, HINGE_Z))
    # trailing-edge taper (2.4 -> 1.2 mm) on both faces
    for sy in (1, -1):
        t = t - box(60, 2.0, 30).rotate((sy * -4.5, 0, 0)).translate(((TAB_R0 + TAB_R1) / 2, sy * (FT / 2 + 1.0), 0.0))
    horn = bx(HORN_X - 0.8, HORN_X + 0.8, 0.0, PUSH_Y + 2.0, HINGE_Z - 3.6, HINGE_Z + 1.6)
    horn = horn - xcyl(0.7, 4, 16).translate((HORN_X, PUSH_Y, HINGE_Z))
    t = t + horn
    t = t - xcyl(0.62, TAB_R1 - TAB_R0 + 2, 16).translate(((TAB_R0 + TAB_R1) / 2, 0, HINGE_Z))   # pin glued in the tab
    return t.translate((0, 0, -HINGE_Z)).rotate((delta, 0, 0)).translate((0, 0, HINGE_Z))


def tab_pin_local():
    return xcyl(0.6, TAB_R1 - TAB_R0 - 0.4, 12).translate(((TAB_R0 + TAB_R1) / 2, 0, HINGE_Z))


def tab_servo_local():
    s = SV
    body = bx(PSV_X0, PSV_X0 + s["H"], PSV_Y0, PSV_Y0 + s["W"], PSV_Z0, PSV_Z0 + s["L"])
    tabs = bx(PSV_X0 + s["tab_z"], PSV_X0 + s["tab_z"] + s["tab_t"], PSV_YC - (s["W"] - 1) / 2, PSV_YC + (s["W"] - 1) / 2,
              PSV_ZC - s["tab_L"] / 2, PSV_ZC + s["tab_L"] / 2)
    spline = xcyl(2.4, s["spline"], 20).translate((PSV_X0 + s["H"] + s["spline"] / 2, PSV_YC, PSV_SHAFT_Z))
    return body + tabs + spline


def tab_horn_local(psi=0.0):
    hub = xcyl(3.5, 2.0, 32).translate((HORN_X, 0, 0))
    arm = M3.batch_hull([xcyl(3.0, 2.0, 24).translate((HORN_X, 0, 0)), xcyl(1.9, 2.0, 24).translate((HORN_X, HORN_ARM + 1.2, 0))])
    h = (hub + arm) - xcyl(0.7, 4, 12).translate((HORN_X, HORN_ARM, 0)) - xcyl(2.45, 8, 24).translate((HORN_X, 0, 0))
    return h.rotate((psi, 0, 0)).translate((0, PSV_YC, PSV_SHAFT_Z))


def tab_pushrod_local(dz=0.0):
    w = cyl(0.6, PSV_SHAFT_Z - HINGE_Z, HINGE_Z, PUSH_X, PUSH_Y, segs=12)
    for z in (HINGE_Z, PSV_SHAFT_Z):
        w = w + xcyl(0.6, PUSH_X - HORN_X + 2.0, 12).translate(((PUSH_X + HORN_X - 2.0) / 2 + 0.3, PUSH_Y, z))
    return w.translate((0, 0, dz))


def servo_angle_for_tab(delta):
    """servo horn rotation that gives tab deflection delta (pushrod keeps the two horn holes the same height apart)"""
    return math.degrees(math.asin(max(-1.0, min(1.0, PUSH_Y * math.sin(math.radians(delta)) / HORN_ARM))))


def fin_can(M):
    f = FIN
    m = tube(CAN_RO, CAN_RI, f["can_length"], 0.0)
    fin, pod, hole = fin_local(), pod_local(), cable_hole_local()
    for a in FIN_ANG:
        m = m + polar(fin, a) + polar(pod, a)
    for a in FIN_ANG:
        m = m - polar(hole, a)
    # fin #1 marker pip (fin at FIN_ANG[0]) on both faces near the root
    for sy in (1, -1):
        m = m + polar(ycyl(1.5, 1.2, 24).translate((CAN_RO + 14.0, sy * (FT / 2 + 0.5), 95.0)), FIN_ANG[0])
    lug = tube(4.75, 3.4, 25.0, 50.0, segs=40).translate((CAN_RO + 4.4, 0, 0)) + box(5.0, 3.0, 25.0, CAN_RO + 1.6, 0, 62.5)
    # top end cut at 45 deg from the can: the lug then grows out of the can when the fin can prints upside down
    lug = lug - xz_plate([(CAN_RO - 1.0, 75.0 + 1.0), (CAN_RO + 20.0, 75.0 - 20.0), (CAN_RO + 20.0, 90.0), (CAN_RO - 1.0, 90.0)], 20.0)
    m = m + polar(lug, LUG_ANG)
    for a in TAIL_SCREW_ANG:
        m = m - polar(xcyl(1.65, 8, 16).translate((CAN_RO - 0.4, 0, TAIL_SCREW_Z)), a)
    return register("fin_can", m, M["orange"], print_rot=(180, 0, 0), part="bottom",
                    note="PETG, print upside-down (top ring on the bed), 3 walls, 20%. Fins + legs + 4 servo pods in one piece")


def fin_tabs(M):
    t = tab_local(0.0)
    inst = [polar(t, a) for a in FIN_ANG]
    return register("fin_control_tab", inst[0], M["blue"], qty=NF, inst=inst, part="bottom", export=t, export_rot=(90, 0, 0),
                    note="PETG, print lying on its plain face (horn up) with supports on the build plate only (they fill the 0.8 mm under the face "
                         "beside the hinge bead). Glue a 27 mm piece of 1.2 mm music wire through its knuckle; it snaps into the fin's C-clips")


def upper_lug(M):
    z0 = UPPER_LUG_Z
    m = tube(4.75, 3.4, 25.0, z0, segs=40).translate((CAN_RO + 4.4, 0, 0)) + box(6.5, 4.0, 25.0, R + 2.6, 0, z0 + 12.5)
    m = m - cyl(R, 40.0, z0 - 5)
    return register("upper_launch_lug", polar(m, LUG_ANG), M["black"], part="bottom",
                    note="Glue to the bottom tube in line with the fin-can lug (slide both on the rod while the glue sets)")


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
    m = m - polar(box(1.6, 1.2, z_top - z_bot + 10.0, R + 2.2, 0, (z_top + z_bot) / 2), LUG_ANG)
    return register("tool_drill_guide_bottom_tube", m, M["orange"], print_rot=(180, 0, 0), group="tool",
                    note="Build tool (not flown). Slides over the TOP of the bottom tube: av-bay screws, static ports, switch slot, camera window, lug line")


def drill_guide_mid(M):
    z_bot, z_top = Z_MID0, DOOR_Z0 + DOOR_H + 6.0
    m = tube(R + 2.2, R + 0.25, z_top - z_bot, z_bot) + tube(R + 2.2, RI - 0.8, 2.0, z_bot - 2.0)
    m = m - bx(15.0, 45.0, -DOOR_W / 2, DOOR_W / 2, DOOR_Z0, DOOR_Z0 + DOOR_H)
    for a in JOINT_ANG:
        m = m - polar(xcyl(1.6, 10, 24).translate((R + 1, 0, JOINT_Z)), a)
    return register("tool_drill_guide_middle_tube", m, M["orange"], group="tool",
                    note="Build tool (not flown). Slides over the BOTTOM of the middle tube: joint screws and the payload-door window")


# ======================================================================================
# purchased-part stand-ins (assembly positions)
# ======================================================================================
def purchased(M, tab_delta=0.0, latch_open=False):
    s = SV
    out = {}
    out[LOWER_TUBE] = (lower_tube_cut(), M["kraft"])
    out[MID_TUBE] = (middle_tube_cut(), M["kraft"])
    out[MOTOR_NAME] = (cyl(MOTOR_D / 2, MOTOR_L, Z_MOTOR0) - cyl(4.0, 12.0, Z_MOTOR0 - 1.0, segs=24), M["motor"])
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
    # four tab servos in the fin pods
    psi = servo_angle_for_tab(tab_delta)
    dz = PUSH_Y * math.sin(math.radians(tab_delta))
    for k, a in enumerate(FIN_ANG):
        out[f"servo_MG90S_tab{k + 1}"] = (polar(tab_servo_local(), a), M["servo"])
        out[f"horn_tab{k + 1}"] = (polar(tab_horn_local(psi), a), M["horn"])
        out[f"pushrod_tab{k + 1}_1.2mm"] = (polar(tab_pushrod_local(dz), a), M["steel"])
        out[f"hinge_pin_tab{k + 1}_1.2mm"] = (polar(tab_pin_local(), a), M["steel"])
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
    out["parachute_packed"] = (cyl(16.5, 112.0, Z_PISTON + 3.5, 7.0, -1.0, segs=48), M["nylon"])
    out["shock_cord_kevlar_elastic"] = (cyl(7.0, 20.0, Z_PISTON + 116.5, 7.0, -1.0, segs=32), M["cord"])
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
        pts = [(CAN_RO + 1.5, (CAB_Z0 + CAB_Z1) / 2), (r_g, (CAB_Z0 + CAB_Z1) / 2 + 3), (r_g, FRAME_TOP + 2), (r_g - 6, FRAME_TOP + 25)]
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
    tvc_holder(M); tvc_ring(M); tvc_frame(M); retainer(M)
    fin_can(M); fin_tabs(M); upper_lug(M); camera_pod(M)
    pad_hub(M); pad_rod_block(M)
    tail_z = PAD_TOP - FOOT_Z
    pad_rod_stop(M, 150.0); pad_leg_foot(M); rod_cap(M)
    clamps = pad_tile_clamp(M).decompose()
    register("pad_tile_clamp", clamps[0], M["black"], group="pad", qty=4, inst=clamps, note="4 corner clamps, M4 screws into the hub")
    drill_guide(M); drill_guide_mid(M)
    return tail_z


def write_stl(path, V, F):
    import struct
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
    pod_area = (POD_X1 - CAN_RO) * (POD_Y1 - FT / 2)
    want = {
        "avbay.imu_z (LSM6DSO U4)": (D["avbay"]["imu_z"], imu_from_tip),
        "camera_pod.protrusion_mm": (D["camera_pod"]["protrusion_mm"], CAM_RC + CAM_POCKET / 2 + 1.2 - R),
        "camera_pod.width_mm": (D["camera_pod"]["width_mm"], CAM_POCKET + 2 * 1.6),
        "fins.pod.frontal_area_mm2 /10": (FIN["pod"]["frontal_area_mm2"] / 10.0, pod_area / 10.0),
        "fins.pod.length": (FIN["pod"]["length"], POD_ZN - POD_Z0),
        "fins.tab.lever_arm_mm": (TABP["horn_mm"], PUSH_Y),
        "fins.tab.servo_arm_mm": (TABP["servo_arm_mm"], HORN_ARM),
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
                    nozzle_z=Z_MOTOR0, mid_top_z=Z_MID1))
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
    static += [(n, buy[n][0]) for n in (LOWER_TUBE, "servo_MG90S_tvc_ring", "servo_MG90S_tvc_holder")]

    def piv(m, rx, ry):
        return m.translate((0, 0, -Z_PIVOT)).rotate((0, ry, 0)).rotate((rx, 0, 0)).translate((0, 0, Z_PIVOT))
    envelope = [(0.0, 0.0)] + [(max_deg * math.cos(math.radians(a)), max_deg * math.sin(math.radians(a))) for a in range(0, 360, 15)]
    n = 0
    for rx, ry in envelope:
        moving = [(nm, piv(m, rx, ry)) for nm, m in inner] + [(ring[0], piv(ring[1], rx, 0.0))]
        for nm, m in moving:
            for sn, sm in static:
                v = (m ^ sm).volume()
                n += 1
                if v > 0.5:
                    rows.append(("gimbal", f"{rx:+.1f}/{ry:+.1f} deg", nm, sn, v))
        for nm, m in moving[:2]:
            v = (m ^ moving[-1][1]).volume()
            n += 1
            if v > 0.5:
                rows.append(("gimbal", f"{rx:+.1f}/{ry:+.1f} deg", nm, ring[0], v))
    md.append(f"\n## Gimbal sweep\n\nMotor, holder, retainer and ring swung round the whole deflection circle ({len(envelope) - 1} directions at "
              f"{max_deg:.0f} deg = firmware limit {TVC['max_deflection_deg']} deg + 1 deg margin): {n} contact checks.")
    # 2) control tabs: every fin, tab + horn + pushrod + servo horn through +/- (limit + 2 deg)
    lim = TABP["max_deflection_deg"] + 2.0
    fc = PARTS["fin_can"]["m"]
    n2 = 0
    for k, a in enumerate(FIN_ANG):
        sv = polar(tab_servo_local(), a)
        statics = [("fin_can", fc), (f"servo_MG90S_tab{k + 1}", sv), (LOWER_TUBE, buy[LOWER_TUBE][0])]
        for d in np.linspace(-lim, lim, 9):
            mov = [("tab", polar(tab_local(d), a)), ("servo horn", polar(tab_horn_local(servo_angle_for_tab(d)), a)),
                   ("pushrod", polar(tab_pushrod_local(PUSH_Y * math.sin(math.radians(d))), a))]
            for mn, mm in mov:
                for sn, sm in statics:
                    if mn == "servo horn" and sn.startswith("servo"):
                        continue                      # the horn sits on the servo's own spline
                    v = (mm ^ sm).volume()
                    n2 += 1
                    if v > 0.5:
                        rows.append((f"tab {k + 1}", f"{d:+.1f} deg", mn, sn, v))
            v = (mov[0][1] ^ mov[1][1]).volume()
            n2 += 1
            if v > 0.5:
                rows.append((f"tab {k + 1}", f"{d:+.1f} deg", "tab", "servo horn", v))
    md.append(f"\n## Control-tab sweep\n\nAll {NF} tabs with their horns, pushrods and servo horns swept through +/-{lim:.0f} deg "
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
        base = name.split("_")[0]
        pname = None
        for n2, p in PARTS.items():
            if name == n2 or name.startswith(n2 + "_"):
                pname = p["part"]
        if pname is None:
            if name.startswith(("servo_MG90S_tvc", "horn_tvc", "pushrod_ring", "pushrod_holder", MOTOR_NAME)):
                pname = "tvc"
            elif name.startswith(("servo_MG90S_release", "horn_release", "latch_spring", MID_TUBE, "parachute", "shock_cord", "payload")):
                pname = "middle"
            else:
                pname = "bottom"
        dz = part_dz.get(pname, 0.0)
        ob = to_blender(name + "_ex", m, material, c_ex)
        ob.location = (side.get(pname, 0.0), 0, dz)
    curve_obj("ejection_spring_ex", spring_pts(), M["steel"], c_ex, radius=0.75).location = (0, 0, part_dz["middle"])
    lab = mat("Label", (0.05, 0.05, 0.06), rough=0.6)
    for txt, z in (("3  NOSE CONE", Z_NOSE0 + part_dz["nose"] + 20), ("2  MIDDLE PART\n   payload bay + door\n   wall\n   parachute bay\n   release latch", 520 + part_dz["middle"]),
                   ("1  BOTTOM PART\n   avionics bay\n   camera\n   4 fins / legs\n   4 control tabs", 230),
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
    door_items = [it for it in items if not it[0].startswith(("payload_door", "fin_", "servo_MG90S_tab", "horn_tab", "pushrod_tab"))]
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
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "kestrel.blend"))
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
            ("launch_pad", (1000, -1250, 420), (0, 0, foot_z / 2 + 60), 40, {c_pad.name, c_gnd.name}, (1600, 1000)),
        ]
        render_views(views)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "kestrel.blend"))

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
    steps = {"tvc_motor_retainer": (-200, -60), MOTOR_NAME: (-200, -40), "tvc_motor_holder": (-120, 0), "tvc_gimbal_ring": (-60, 0),
             "tvc_frame": (0, 0), "servo_MG90S_tvc_ring": (90, 0), "horn_tvc_ring": (90, 0), "servo_MG90S_tvc_holder": (150, 0),
             "horn_tvc_holder": (150, 0), "pushrod_ring_1.2mm": (220, 0), "pushrod_holder_1.2mm": (250, 0)}
    for n, m, mt in tvc_items:
        dx, dz = steps[n]
        ob = to_blender(n + "_step", m, mt, c_tex)
        ob.location = (dx * 1.4, 0, dz)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "kestrel_tvc_module.blend"))
    if "--no-render" not in ARGS:
        setup_render()
        render_views([("tvc_module", (215, -265, 215), (0, 0, 112), 50, {c_tvc.name}, (1100, 1500)),
                      ("tvc_module_assembly_steps", (100, -1250, 300), (100, 0, 70), 50, {c_tex.name}, (1700, 900))])
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
    skip = {"nose_cone", "parachute_packed", "shock_cord_kevlar_elastic", "pad_rod_stop"}
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
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "kestrel_parachute_open.blend"))
    if "--no-render" not in ARGS:
        setup_render(world=(0.45, 0.62, 0.88), strength=0.7)
        render_views([("parachute_open", (2100, -3300, 1750), (0, 0, 1900), 60, {c_ch.name}, (1100, 1600))])
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "kestrel_parachute_open.blend"))
    print("CAD done. component positions:", len(comp))


if not os.environ.get("KESTREL_CAD_LIB"):
    main()
