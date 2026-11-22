"""KESTREL-1 parametric CAD generator for Blender (tested with Blender 4.0.2, headless).

    blender -b -P cad/kestrel_cad.py -- [--no-render] [--fast]

Solid modelling uses manifold3d (robust, always-watertight CSG) running inside Blender's Python;
Blender is used for the assembly, materials, the .blend file and rendering.

Outputs
  cad/stl/*.stl          print-oriented, millimetres
  cad/stl/parts.json     part list with print notes
  cad/kestrel.blend      full assembly: printed parts, purchased-part stand-ins, rocket on the pad, exploded view
  cad/renders/*.png      renders
All dimensions come from ../design.json. Blender Z = height above the aft end of the lower body tube.
"""
import json
import math
import os
import sys

import bpy
import manifold3d as mf
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FAST = "--fast" in ARGS
SEG = 48 if FAST else 144

D = json.load(open(os.path.join(ROOT, "design.json")))
AF, NOSE, AV, FIN, TVC = D["airframe"], D["nose"], D["avbay"], D["fins"], D["tvc"]

# --------------------------------------------------------------------------------------
# Key dimensions (mm)
# --------------------------------------------------------------------------------------
OD, ID = AF["od"], AF["id"]
R, RI = OD / 2, ID / 2
L_LOW, L_UP, BAND = AF["lower_tube_length"], AF["upper_tube_length"], AV["band"]
Z_BAND0 = L_LOW                       # 580
Z_UP0 = L_LOW + BAND                  # 584
Z_NOSE0 = Z_UP0 + L_UP                # 834
NOSE_L = NOSE["length"]
SHOULDER = NOSE["shoulder_length"]
FIT = 0.10                            # radial clearance, printed part inside kraft tube
INS_R = AV["insert_od"] / 2           # 27.5
WALL = AV["wall"]
Z_AV0 = Z_BAND0 - AV["lower_insert"]  # 480
SH_R = AV["shoulder_od"] / 2          # 25.4
Z_SH1 = Z_UP0 + 28.0                  # underside of the top bulkhead (612)
BULK_T = 2.4
COLLAR_RI = 51.0 / 2
COLLAR_H = 20.0
Z_LATCH = Z_UP0 + 10.0                # latch bolt centre plane (594)
MOTOR_D = TVC["motor_diameter"]
MOTOR_L = 95.0
Z_MOTOR0 = -TVC["nozzle_protrusion"]
Z_PIVOT = TVC["pivot_from_tail"]
HOLD_RI = MOTOR_D / 2 + 0.2
HOLD_R = HOLD_RI + 1.6                # 13.8
RING_RI, RING_R = HOLD_R + 1.4, HOLD_R + 4.4
FRAME_R = INS_R
FRAME_RI = FRAME_R - 1.6
SV = dict(L=22.8, W=12.2, H=22.5, tab_L=32.2, tab_t=2.5, tab_z=15.9, shaft_off=5.9, spline=5.0, pitch=27.8)
SV1_Z, SV2_Z = 120.0, 145.0           # TVC servo shaft heights (bars clear the holder top at full deflection)
SV_SHAFT_R = 16.0                     # servo shaft exit distance from the axis
PR1 = (9.0, 18.0)                     # pushrod 1 (ring, rotates about X): x, y
PR2 = (18.0, 9.0)                     # pushrod 2 (holder, rotates about Y)
HOLDER_TAB_Z = Z_PIVOT + 12.0
TAIL_SCREW_Z, TAIL_SCREW_ANG = 16.0, (90.0, 210.0)   # fin can + tube + TVC frame radial M3 screws

# --------------------------------------------------------------------------------------
# Flight-computer PCB interface, exported from KiCad by pcb/export_mech.py (run it after any layout change)
# --------------------------------------------------------------------------------------
MECH = json.load(open(os.path.join(ROOT, "pcb", "build", "mech_interface.json")))
BW, BH, BT = MECH["board"]["w"], MECH["board"]["h"], MECH["board"]["thickness"]
PCB_Z_TOP = Z_AV0 + 3.0 + BH          # board stands on the sled disc; top edge (GPS end) towards the nose
PCB_Y_BACK = -11.0                    # back face of the board; through-hole pin tails point to -Y (sled plate)
PCB_Y_FRONT = PCB_Y_BACK + BT
STANDOFF_H = 4.0                      # pin tails are <= 2.5 mm long: 1.5 mm to spare
PLATE_T = 2.0
PLATE_Y = PCB_Y_BACK - STANDOFF_H - PLATE_T / 2
SOCKET_H = 8.5                        # Pico 2 W female header height
KNOB = MECH["parts"]["SW1"]["knob"]
CAM_Z0 = Z_AV0 - 30.0                 # camera pod base: camera stays below the av-bay bulkhead disc
CAM_POCKET = 23.6                     # pocket for a 23 mm cube camera
CAM_FLOOR = 1.8                       # floor under the camera (lens recessed in it)
CAM_RC = R + 1.5                      # lens axis radius: 1.5 mm outside the tube surface
CAM_WIN_W, CAM_WIN_H = CAM_POCKET + 2 * 1.6 + 0.2, 30.0   # window cut in the lower tube for the pod
RADIAL_SCREW_ANG = (0.0, 180.0)       # av-bay retention screws (clear of the camera fairing at 270 deg)
STATIC_PORT_ANG = (30.0, 150.0, 270.0)
BATT = dict(w=30.0, t=10.0, l=45.0, y0=5.5, z0=Z_AV0 + 14.0)     # 2S 200 mAh LiPo stand-in
BAY = dict(w=31.0, t=12.0, l=55.0)    # battery tray accepts packs up to 31 x 12 x 55 mm (2S 300 mAh); foam + strap


def board_to_rocket(bx, by):
    """PCB coordinates (mm, component side up, y down towards the servo headers) -> rocket (x, z).
    The component side faces +Y, so board +x maps to rocket -x."""
    return BW / 2.0 - bx, PCB_Z_TOP - by


SW_X, SW_Z = board_to_rocket(KNOB["tip_x"], KNOB["tip_y"])
SW_Y = PCB_Y_FRONT + KNOB["height_above_pcb"]
SW_ANG = math.degrees(math.atan2(SW_Y, SW_X))     # radial direction of the switch/LED access slot

LOWER_TUBE = f"BT70_lower_tube_{L_LOW:.0f}"
UPPER_TUBE = f"BT70_upper_tube_{L_UP:.0f}"
MOTOR_NAME = "motor_" + D["launch"]["nominal_motor"].replace("-", "_") + "_24x95"
PCB_NAME = f"pcb_kestrel_fc_{BW:.0f}x{BH:.0f}"

STL_DIR = os.path.join(HERE, "stl")
REN_DIR = os.path.join(HERE, "renders")
os.makedirs(STL_DIR, exist_ok=True)
os.makedirs(REN_DIR, exist_ok=True)
PARTS = {}

# --------------------------------------------------------------------------------------
# manifold helpers
# --------------------------------------------------------------------------------------
M3 = mf.Manifold


def cyl(r, h, z0=0.0, x=0.0, y=0.0, r2=None, segs=None):
    return M3.cylinder(h, r, r if r2 is None else r2, segs or SEG).translate((x, y, z0))


def box(sx, sy, sz, cx=0.0, cy=0.0, cz=0.0):
    return M3.cube((sx, sy, sz), True).translate((cx, cy, cz))


def _ccw(pts):
    a = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        a += x1 * y2 - x2 * y1
    return pts if a > 0 else pts[::-1]


def revolve(prof, segs=None):
    """Solid of revolution about Z of a closed (r, z) polygon (any winding)."""
    return M3.revolve(mf.CrossSection([_ccw(list(prof))]), segs or SEG)


def tube(ro, ri, h, z0=0.0, segs=None):
    return revolve([(ri, z0), (ro, z0), (ro, z0 + h), (ri, z0 + h)], segs)


def xcyl(r, L, segs=24):
    """cylinder along X, centred on the origin"""
    return M3.cylinder(L, r, r, segs).translate((0, 0, -L / 2)).rotate((0, 90, 0))


def ycyl(r, L, segs=24):
    return M3.cylinder(L, r, r, segs).translate((0, 0, -L / 2)).rotate((90, 0, 0))


def polar(m, ang_deg):
    return m.rotate((0, 0, ang_deg))


def union(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = out + m
    return out


# --------------------------------------------------------------------------------------
# Blender helpers
# --------------------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = "MILLIMETERS"


def collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def mat(name, rgb, metal=0.0, rough=0.5):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*rgb, 1.0)
    return m


def to_blender(name, m, material, coll):
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    f = np.asarray(mesh.tri_verts)
    me = bpy.data.meshes.new(name)
    me.from_pydata(v.tolist(), [], f.tolist())
    me.update()
    for p in me.polygons:
        p.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    me.materials.append(material)
    return ob


def register(name, m, material, print_rot=(0, 0, 0), qty=1, note="", group="rocket"):
    st = m.status()
    if str(st) not in ("Error.NoError", "NoError") or m.is_empty():
        raise RuntimeError(f"{name}: manifold status {st}, empty={m.is_empty()}")
    PARTS[name] = dict(m=m, material=material, print_rot=print_rot, qty=qty, note=note, group=group)
    return m


def MATS():
    return dict(
        orange=mat("PETG orange", (0.90, 0.32, 0.06), rough=0.45),
        white=mat("PLA white", (0.88, 0.88, 0.86)),
        black=mat("PETG black", (0.04, 0.04, 0.045), rough=0.4),
        grey=mat("PLA grey", (0.35, 0.36, 0.38)),
        kraft=mat("Kraft tube", (0.55, 0.38, 0.22), rough=0.8),
        motor=mat("Motor casing", (0.85, 0.73, 0.45), rough=0.7),
        servo=mat("Servo", (0.02, 0.02, 0.03), rough=0.35),
        pcb=mat("PCB green", (0.02, 0.28, 0.12), rough=0.4),
        pico=mat("Pico", (0.05, 0.45, 0.15), rough=0.4),
        steel=mat("Steel", (0.62, 0.63, 0.65), metal=1.0, rough=0.3),
        wood=mat("Wood dowel", (0.62, 0.45, 0.26), rough=0.7),
        lipo=mat("LiPo", (0.12, 0.25, 0.65), rough=0.4),
        nylon=mat("Chute nylon", (0.85, 0.05, 0.08), rough=0.6),
        camera=mat("Camera", (0.07, 0.07, 0.08), rough=0.3),
        antenna=mat("GPS patch", (0.8, 0.75, 0.6), rough=0.6),
    )


# ======================================================================================
# ROCKET PARTS
# ======================================================================================
def ogive_r(x, L=NOSE_L, Rb=R):
    """radius of a tangent ogive at distance x from the tip"""
    rho = (Rb ** 2 + L ** 2) / (2 * Rb)
    return math.sqrt(max(rho ** 2 - (L - x) ** 2, 0.0)) + Rb - rho


def nose_cone(M):
    wall = NOSE.get("wall", 1.2)
    n = 80
    outer = [(ogive_r(NOSE_L * i / n), Z_NOSE0 + NOSE_L - NOSE_L * i / n) for i in range(n + 1)]
    sh_r = RI - FIT
    z_sh0 = Z_NOSE0 - SHOULDER
    inner = []
    for i in range(n, 6, -1):           # inner surface, from the base back towards the tip
        x = NOSE_L * i / n
        r = ogive_r(x) - wall * 1.15
        if r > 1.0:
            inner.append((min(r, sh_r - 1.6), Z_NOSE0 + NOSE_L - x))
    prof = [(0.0, Z_NOSE0 + NOSE_L)] + outer[1:] + [(sh_r, Z_NOSE0), (sh_r, z_sh0), (sh_r - 1.6, z_sh0)]
    prof += inner
    prof += [(0.0, inner[-1][1] + 2.0)]
    m = revolve(prof)
    # shock-cord bar across the shoulder (printed as a bridge) with a gap underneath
    bar = box(2 * (sh_r - 1.0), 6.0, 4.0, 0, 0, z_sh0 + 10.0)
    m = m + (bar ^ cyl(sh_r - 0.5, 20, z_sh0))
    # solid tip (adds a little nose weight, improves the print)
    m = m + (revolve(outer[:12] + [(0.0, outer[11][1])]))
    return register("nose_cone", m, M["orange"], note="Print tip-up, 3 walls, 10% gyroid, no supports. Glue/tape into the upper tube.")


def latch_collar(M):
    m = tube(RI - FIT, COLLAR_RI, COLLAR_H, Z_UP0)
    for sx in (1, -1):
        m = m - box(5.0, 4.8, 3.9, sx * (COLLAR_RI + 0.9), 0, Z_LATCH)        # bolt pockets (1.9 mm deep)
    m = m - box(2.0, 3.0, 4.2, 0, RI - 1.0, Z_UP0 + 2.0 - 0.01)               # alignment notch (+Y)
    return register("latch_collar", m, M["black"],
                    note="Epoxy flush with the BOTTOM edge of the upper tube; align its notch with the av-bay band notch")


def servo_tab_positions(cz_body_axis, along):
    return [cz_body_axis - SV["pitch"] / 2, cz_body_axis + SV["pitch"] / 2]


def avbay_coupler(M):
    zt = Z_SH1 + BULK_T
    iw = 1.2
    prof = [
        (INS_R - iw, Z_AV0), (INS_R, Z_AV0), (INS_R, Z_BAND0), (R, Z_BAND0), (R, Z_UP0),
        (SH_R, Z_UP0), (SH_R, zt), (0.0, zt), (0.0, Z_SH1), (SH_R - WALL, Z_SH1),
        (SH_R - WALL, Z_BAND0 + 3.0), (INS_R - iw, Z_BAND0 - 2.0),
    ]
    m = revolve(prof)
    for a in (0.0, 120.0, 240.0):          # weight-saving windows between the screw band and the band ring
        w = (tube(INS_R + 1, INS_R - iw - 1, 52.0, Z_AV0 + 22.0, segs=96) ^ polar(box(60, 34, 60, 30, 0, Z_AV0 + 48.0), a + 60.0))
        m = m - w
    # top side: spring boss + shock-cord bridge
    m = m + tube(11.0, 7.5, 6.0, zt - 0.5)
    bridge = box(18.0, 5.0, 9.5, 0, 18.5, zt + 4.25) - box(12.0, 6.0, 5.0, 0, 18.5, zt + 2.0)
    m = m + bridge
    # latch: slots in the shoulder wall + U-channel guides cantilevered from the wall
    for sx in (1, -1):
        m = m - box(6.0, 4.6, 3.6, sx * (SH_R - 1.0), 0, Z_LATCH)
        gx = sx * (SH_R - WALL - 4.0)
        guide = box(8.6, 7.4, 5.2, gx, 0, Z_LATCH + 0.4) - box(9.0, 4.4, 3.4, gx, 0, Z_LATCH)
        guide = guide - box(9.0, 2.6, 3.0, gx, 0, Z_LATCH + 2.6)               # open top for the wire link
        m = m + guide
    # deploy servo (shaft up, on the axis, long axis along Y): two posts hanging from the bulkhead
    z_shaft_top = Z_LATCH + 4.0
    z_body_top = z_shaft_top - SV["spline"]
    z_tab_top = z_body_top - (SV["H"] - SV["tab_z"]) + SV["tab_t"]
    body_cy = -(SV["L"] / 2 - SV["shaft_off"])
    for hy in (body_cy - SV["pitch"] / 2, body_cy + SV["pitch"] / 2):
        off = 1.5 if hy > body_cy else -1.5
        post = box(7.0, 6.0, Z_SH1 - z_tab_top + 0.25, 0, hy + off, (Z_SH1 + 0.3 + z_tab_top + 0.05) / 2)
        post = post - cyl(0.8, 10.0, z_tab_top - 1.0, 0, hy, segs=16)         # 1.6 mm pilot for servo screw
        m = m + (post ^ cyl(SH_R - 0.5, 200, Z_AV0))
    # 2 x M3 radial screw holes (through lower tube -> insert -> sled nut traps)
    for ang in RADIAL_SCREW_ANG:
        m = m - polar(xcyl(1.65, 12).translate((INS_R, 0, Z_AV0 + 12)), ang)
    # switch / LED slot on the radial line through the power-switch knob (from the KiCad layout), 3 static ports
    m = m - polar(box(8.0, 7.0, 20.0, INS_R - 1.0, 0, SW_Z), SW_ANG)
    for ang in STATIC_PORT_ANG:
        m = m - polar(xcyl(1.0, 8, 16).translate((INS_R, 0, Z_AV0 + 40)), ang)
    m = m - box(2.0, 2.0, 2.2, 0, R - 0.6, Z_BAND0 + 2.9)                       # alignment notch
    return register("avbay_coupler", m, M["white"], print_rot=(180, 0, 0),
                    note="Print UPSIDE-DOWN (bulkhead on the bed), 4 walls, 25% gyroid, no supports")


def latch_bolt(M, sx):
    r_tip = COLLAR_RI + 1.7
    L = 13.0
    m = box(L, 4.0, 3.0, sx * (r_tip - L / 2), 0, Z_LATCH)
    m = m - cyl(0.7, 6.0, Z_LATCH - 3.0, sx * 22.0, 0, segs=16)               # 1.4 mm hole for the wire link
    return register("latch_bolt_" + ("pos" if sx > 0 else "neg"), m, M["black"], note="PETG. Must slide freely; rub with graphite/wax")


def spring_piston(M):
    z0 = Z_SH1 + BULK_T + 20.0
    m = cyl(RI - 0.6, 3.0, z0) + tube(13.5, 11.2, 5.5, z0 - 5.0)
    m = m - box(8.0, 10.0, 7.0, 0, RI - 3.5, z0 + 1.5)
    return register("spring_piston", m, M["white"], note="Sits on the spring, under the parachute; notch lets the shock cord pass")


def avbay_sled(M):
    """Bulkhead disc + backbone plate.  The PCB stands on 4 printed standoffs at its real mounting holes;
    every through-hole pin tail gets a clearance slot in the plate; the LiPo sits on a ledge in a ribbed tray."""
    z0 = Z_AV0
    rb = INS_R - WALL - 0.25
    plate = box(38.0, PLATE_T, BH + 1.0, 0, PLATE_Y, z0 + 2.5 + (BH + 1.0) / 2)
    # clearance slots behind every group of through-hole pins (Pico sockets, servo headers, battery plug, buzzer)
    groups = {}
    for p in MECH["tht_pins"]:
        groups.setdefault(p["ref"], []).append(board_to_rocket(p["x"], p["y"]))
    for ref, pts in groups.items():
        xs, zs = [q[0] for q in pts], [q[1] for q in pts]
        mg = 1.7
        plate = plate - box(max(xs) - min(xs) + 2 * mg, 10.0, max(zs) - min(zs) + 2 * mg,
                            (max(xs) + min(xs)) / 2, PLATE_Y, (max(zs) + min(zs)) / 2)
    # lightening windows between the pin rows
    for (xa, xb) in ((-0.9, 11.1), (-17.0, -7.4)):
        for (za, zb) in ((22.0, 44.0), (48.0, 70.0)):
            plate = plate - box(xb - xa, 10.0, zb - za, (xa + xb) / 2, PLATE_Y, z0 + (za + zb) / 2)
    m = cyl(rb, 3.0, z0) + plate
    # standoffs (M2.5 x 8 self-tapping screws from the component side, 2.1 mm pilot)
    for h in MECH["holes"]:
        x, z = board_to_rocket(h["x"], h["y"])
        L = STANDOFF_H + 0.5
        m = m + ycyl(2.6, L, 32).translate((x, PCB_Y_BACK - L / 2, z))
        m = m - ycyl(1.05, 3 * L, 16).translate((x, PCB_Y_BACK - L, z))
    # battery tray: plate + side ribs + ledge under the pack
    ty = BATT["y0"] + BAY["t"] + 0.8
    tray = box(34.0, 1.6, 70.5, 0, ty, z0 + 2.5 + 70.5 / 2)
    for sx in (1, -1):
        tray = tray + box(1.6, 5.0, 70.5, sx * (BAY["w"] / 2 + 0.8 + 0.3), ty - 3.3, z0 + 2.5 + 70.5 / 2)
    tray = tray + box(BAY["w"] - 1.0, BAY["t"] + 1.6, 1.6, 0, BATT["y0"] + (BAY["t"] + 1.6) / 2, BATT["z0"] - 0.8)
    for zz in (25.0, 55.0):
        tray = tray - box(26.0, 4.0, 3.2, 0, ty, z0 + zz)                    # velcro-strap slots
    m = m + (tray ^ cyl(rb, 200, z0))
    for ang in RADIAL_SCREW_ANG:                                              # M3 nut traps for the retention screws
        nt = box(5.9, 6.0, 2.8, rb - 3.2, 0, z0 + 12)
        boss = (box(5.0, 9.0, 12.0, rb - 2.6, 0, z0 + 8.0) - nt - xcyl(1.65, 10).translate((rb - 3, 0, z0 + 12)))
        m = m - polar(nt, ang) - polar(xcyl(1.65, 10).translate((rb - 3, 0, z0 + 12)), ang)
        m = m + (polar(boss, ang) ^ cyl(rb, 30, z0))
    m = m - cyl(4.0, 10.0, z0 - 2.0, 12.0, 4.0, segs=24)                         # servo-cable pass-through
    return register("avbay_sled", m, M["grey"],
                    note="Print with the bulkhead disc on the bed. 4 x M2.5x8 self-tapping screws hold the PCB")


def tvc_holder(M):
    z1 = Z_MOTOR0 + MOTOR_L + 1.5 + 2.5
    zc = z1 - 2.2                     # underside of the 2.2 mm thrust cap
    # single revolved profile: motor bore, 25 mm washer recess, closed thrust cap (no coincident faces)
    m = revolve([(HOLD_RI, 0.0), (HOLD_R, 0.0), (HOLD_R, z1), (0.0, z1), (0.0, zc), (12.6, zc),
                 (12.6, zc - 1.9), (HOLD_RI, zc - 1.9)])
    for sy in (1, -1):                 # pivot bosses: 13.4 -> 14.5 mm from the axis (0.2 mm gap to the ring pads)
        m = m + ycyl(3.4, 1.1, 32).translate((0, sy * (HOLD_R + 0.15), Z_PIVOT))
    # re-cut the M3 pilot only through the bosses (not the bore)
    for sy in (1, -1):
        m = m - ycyl(1.25, 3.0, 16).translate((0, sy * (HOLD_R + 0.15), Z_PIVOT))
    tab = box(8.5, 4.0, 4.0, HOLD_R + 3.4, PR2[1], HOLDER_TAB_Z) + box(5.0, PR2[1] + 2.0, 4.0, HOLD_R + 0.8, PR2[1] / 2, HOLDER_TAB_Z)
    tab = tab - cyl(HOLD_R - 0.6, 10, HOLDER_TAB_Z - 5)   # tab root buried inside the wall (no coincident faces)
    m = m + tab - cyl(0.7, 6.0, HOLDER_TAB_Z - 3.0, PR2[0], PR2[1], segs=16)
    for a in (45, 225):
        m = m + polar(box(3.0, 5.0, 3.0, HOLD_R + 1.2, 0, 4.0), a)
    return register("tvc_motor_holder", m, M["black"],
                    note="PETG/ASA. Press/glue an M10 x 25 mm steel penny washer into the top recess (burn-through shield)")


def tvc_ring(M):
    h = 8.0
    m = tube(RING_R, RING_RI, h, Z_PIVOT - h / 2)
    for sx in (1, -1):
        m = m + xcyl(3.4, 2.4, 32).translate((sx * (RING_R + 0.9), 0, Z_PIVOT))
    for sy in (1, -1):
        m = m + ycyl(3.0, 0.8, 32).translate((0, sy * (RING_RI - 0.1), Z_PIVOT))   # inner bearing pads 14.7 -> 15.5
    m = m - xcyl(1.25, 2 * RING_R + 8, 16).translate((0, 0, Z_PIVOT))
    m = m - ycyl(1.65, 2 * RING_R + 8, 16).translate((0, 0, Z_PIVOT))
    m = m - cyl(HOLD_R + 0.6, 40, Z_PIVOT - 20)                                  # keep the bore clear
    tab = box(6.0, 5.0, 3.0, PR1[0], PR1[1] + 0.5, Z_PIVOT) + box(5.0, 6.0, 3.0, PR1[0] - 2.0, RING_R - 0.5, Z_PIVOT)
    m = m + tab - cyl(0.7, 6.0, Z_PIVOT - 3.0, PR1[0], PR1[1], segs=16)
    return register("tvc_gimbal_ring", m, M["orange"], note="PETG")


def tvc_frame(M):
    ro = FRAME_R
    ri = ro - 1.0                      # 1.0 mm skin: the kraft body tube carries the bending loads
    m = tube(ro, ri, 156.0, 0.0)
    # keep solid bands where loads go in (aft ring + screws, pivot posts, servo brackets); open windows elsewhere
    windows = [(22.0, 40.0), (56.0, 94.0), (105.0, 121.0), (133.0, 149.0)]
    longerons = (30.0, 150.0, 270.0)
    for z0, z1 in windows:
        w = tube(ro + 1.0, ri - 1.0, z1 - z0, z0, segs=96)
        for a in longerons:
            w = w - polar(box(14.0, 9.0, z1 - z0 + 2.0, ro - 2.0, 0, (z0 + z1) / 2), a)
        m = m - w
    m = m + tube(ro, 24.6, 4.0, 0.0)                                               # aft ring lip (clears the swung retainer)
    # pivot posts on +/-X
    for sx in (1, -1):
        post = box(ri - (RING_R + 2.7) + 0.8, 8.0, 12.0, sx * ((ri + RING_R + 2.7) / 2 + 0.4), 0, Z_PIVOT)
        m = m + post
    m = m - xcyl(1.65, 2 * ro + 4, 16).translate((0, 0, Z_PIVOT))
    # servo brackets: bars under the servo tabs, spanning wall to wall
    def bar_x(y0, z0):     # bar along X (for servo 1, tabs face +Y)
        b = box(2 * ro, 2.2, 5.0, 0, y0, z0)
        return b ^ cyl(ri + 0.8, 200, -10)
    def bar_y(x0, z0):
        b = box(2.2, 2 * ro, 5.0, x0, 0, z0)
        return b ^ cyl(ri + 0.8, 200, -10)
    tab_y = -(SV["H"] - SV_SHAFT_R) + SV["tab_z"] - 1.1          # just under the tab plane
    c1 = SV1_Z + SV["shaft_off"] - SV["L"] / 2
    c2 = SV2_Z + SV["shaft_off"] - SV["L"] / 2
    for dz in (-1, 1):
        zz = c1 + dz * SV["pitch"] / 2
        b = bar_x(tab_y, zz) - box(SV["W"] + 0.6, 10, 30, 0, tab_y, c1)            # never through the servo body
        b = b - ycyl(0.8, 8, 12).translate((0, tab_y, zz))                         # pilot for the servo screw
        b = b - cyl(2.2, 12.0, zz - 6, PR2[0], PR2[1], segs=16)                     # pushrod 2 passes through
        m = m + b
        zz2 = c2 + dz * SV["pitch"] / 2
        b2 = bar_y(tab_y, zz2) - box(10, SV["W"] + 0.6, 30, tab_y, 0, c2)
        b2 = b2 - xcyl(0.8, 8, 12).translate((tab_y, 0, zz2))
        b2 = b2 - cyl(2.2, 12.0, zz2 - 6, PR1[0], PR1[1], segs=16)
        m = m + b2
    # 2 x M3 radial screws (shared with the fin can)
    for a in TAIL_SCREW_ANG:     # nut traps sit above the retainer's swing (gimbal sweep check)
        m = m - polar(xcyl(1.65, 8, 16).translate((ro - 1.5, 0, TAIL_SCREW_Z)), a)
        m = m + polar((box(6.0, 8.0, 8.0, ri - 2.0, 0, TAIL_SCREW_Z) - box(2.8, 5.9, 6.5, ri - 2.6, 0, TAIL_SCREW_Z) -
                       xcyl(1.65, 12, 16).translate((ri, 0, TAIL_SCREW_Z))) ^ cyl(ro, 40, 0), a)
    return register("tvc_frame", m, M["grey"], note="PETG, print upright; supports only under the servo bars")


def retainer(M):
    z0 = Z_MOTOR0 - 1.5
    m = tube(HOLD_R + 3.4, HOLD_R + 0.3, 13.0, z0) + tube(HOLD_R + 3.4, 8.0, 1.5, z0)   # 1.7 mm bridge over the lock slot
    for a in (45, 225):
        m = m - polar(box(4.0, 5.6, 7.0, HOLD_R + 1.4, 0, z0 + 1.5 + 3.5 + 4.5), a)
        m = m - polar(box(4.0, 9.0, 3.6, HOLD_R + 1.4, 3.0, 4.0), a)
    return register("tvc_motor_retainer", m, M["orange"], note="Twist-lock: push up over the lugs and turn 45 deg")


def fin_can(M):
    f = FIN
    ri = R + 0.10
    ro = ri + f["can_wall"]
    m = tube(ro, ri, f["can_length"], 0.0)
    cr, ct, s, t = f["root_chord"], f["tip_chord"], f["span"], f["thickness"]
    prof = [(ro - 0.6, 0.0), (ro + s, 0.0), (ro + s, ct), (ro - 0.6, cr)]
    fin = M3.extrude(mf.CrossSection([_ccw(prof)]), t).translate((0, 0, -t / 2)).rotate((90, 0, 0))
    # rounded leading edge: intersect with a slab whose edge is rounded (approximation: chamfer both faces)
    for k in range(f["count"]):
        m = m + polar(fin, 120.0 * k)
    lug = tube(4.75, 3.4, 25.0, 50.0, segs=40).translate((ro + 4.4, 0, 0)) + box(5.0, 3.0, 25.0, ro + 1.6, 0, 62.5)
    m = m + polar(lug, 60)
    for a in TAIL_SCREW_ANG:
        m = m - polar(xcyl(1.65, 8, 16).translate((ro - 0.4, 0, TAIL_SCREW_Z)), a)
    return register("fin_can", m, M["orange"], note="PETG, print upright (fins vertical), 3 walls")


def upper_lug(M):
    z0 = Z_AV0 - 30.0
    ro_can = R + 0.10 + FIN["can_wall"]
    m = tube(4.75, 3.4, 25.0, z0, segs=40).translate((ro_can + 4.4, 0, 0)) + box(6.5, 4.0, 25.0, R + 2.6, 0, z0 + 12.5)
    m = m - cyl(R, 40.0, z0 - 5)
    return register("upper_launch_lug", polar(m, 60), M["black"], note="Glue to the lower tube in line with the fin-can lug (slide both on the rod while the glue sets)")


def camera_pod(M):
    """Pod for a ~23 mm cube mini camera (SQ12 class), lens looking straight down the body.
    The lens axis sits 1.5 mm OUTSIDE the tube surface (CAM_RC), so the view clears the airframe: the body tube
    fills one side of the frame, the ground the rest.  The inner part of the pod drops through a
    CAM_WIN_W x CAM_WIN_H window cut in the lower tube; the saddle flange is glued to the tube."""
    z0, cam, wl = CAM_Z0, CAM_POCKET, 1.2
    rc, w = CAM_RC, CAM_POCKET + 2 * 1.6
    r_in, r_out = rc - cam / 2 - wl, rc + cam / 2 + wl
    zt = z0 + CAM_FLOOR + cam + wl                                      # top of the pocket roof
    base = box(w, r_out - r_in, zt - z0, 0, (r_in + r_out) / 2, (z0 + zt) / 2)
    tip = box(4.0, 0.1, 1.0, 0, R + 2.0, zt + 24.0)                      # faired nose of the pod
    shell = M3.batch_hull([base, tip])
    shell = shell - box(cam, cam, cam, 0, rc, z0 + CAM_FLOOR + cam / 2)  # camera pocket
    shell = shell - cyl(4.6, 6.0, z0 - 3.0, 0, rc, segs=40)               # lens hole through the floor
    shell = shell - box(cam - 6.0, 10.0, 8.0, 0, r_out, z0 + CAM_FLOOR + cam - 2.0)   # button / SD access slot (outer face)
    shell = shell - cyl(R + 0.1, 150.0, zt)                              # above the pocket nothing goes inside the tube
    flange = (tube(R + 1.2, R + 0.1, CAM_WIN_H + 6.0, z0 - 3.0) ^ box(w + 10.0, 40.0, CAM_WIN_H + 6.0, 0, R, z0 + CAM_WIN_H / 2)) - \
        box(w - 0.1, 40, CAM_WIN_H + 30, 0, R, z0 + CAM_WIN_H / 2)
    m = shell + flange
    m = m - box(cam, cam, cam, 0, rc, z0 + CAM_FLOOR + cam / 2)
    return register("camera_pod", polar(m, 180), M["black"],
                    note=f"Cut a {CAM_WIN_W:.0f} x {CAM_WIN_H:.0f} mm window in the lower tube (drill guide marks it); glue the flange, foam-pad the camera")


# ======================================================================================
# LAUNCH PAD
# ======================================================================================
HUB_H, LEG_ANG, LEG_D, LEG_L = 60.0, 38.0, 22.0, 600.0


def leg_axis_transform(m, k):
    return polar(m.rotate((0, LEG_ANG, 0)).translate((38.0, 0, 30.0)), 120.0 * k)


def pad_hub(M):
    m = cyl(55.0, HUB_H, 0.0) + cyl(42.0, 10.0, HUB_H)
    for k in range(3):
        m = m + leg_axis_transform(cyl(LEG_D / 2 + 3.5, 75.0, -75.0, segs=48), k)
    for k in range(3):
        m = m - leg_axis_transform(cyl(LEG_D / 2 + 0.3, 80.0, -82.0, segs=48), k)
        m = m - leg_axis_transform(ycyl(1.8, 60, 16).translate((0, 0, -40.0)), k)
    m = m - box(23.0, 17.0, 60.0, 0, 0, HUB_H + 5.0)                       # rod-block slot (tilt plane = XZ)
    m = m - ycyl(3.1, 130, 24).translate((0, 0, HUB_H - 10.0))             # M6 hinge bolt
    for x, y in ((28, 28), (-28, 28), (28, -28), (-28, -28)):
        m = m - cyl(2.2, 40.0, HUB_H - 25, x, y, segs=16)                  # plate screws (M4)
    # tilt scale: radial ticks at 0/5/10/15 deg around the hinge axis, engraved 0.6 mm on the +Y face
    for a in (0, 5, 10, 15):
        tick = box(0.8, 1.2, 7.0, 0, 0, 0).translate((0, 0, 32.0)).rotate((0, a, 0)).translate((0, 8.5 + 0.3, HUB_H - 10.0))
        m = m - tick
    return register("pad_hub", m, M["grey"], note="PETG, 5 walls, 40% infill, print upright with tree supports in the leg sockets",
                    group="pad")


def pad_rod_block(M):
    m = box(15.0, 16.0, 46.0, 0, 0, HUB_H + 4.0)
    m = m - ycyl(3.1, 40, 24).translate((0, 0, HUB_H - 10.0))
    m = m - cyl(3.15, 40.0, HUB_H - 4.0, segs=24)
    m = m - xcyl(1.7, 20, 16).translate((0, 0, HUB_H + 18.0)) - box(4.0, 7.2, 3.2, 4.5, 0, HUB_H + 18.0)
    return register("pad_rod_block", m, M["orange"], note="Tilts 0-15 deg on an M6 bolt + wing nut; M4 thumb screw clamps the rod", group="pad")


def pad_rod_stop(M, z):
    m = tube(9.0, 3.15, 12.0, z, segs=48) - xcyl(1.4, 12, 16).translate((5.0, 0, z + 6.0))
    m = m - box(3.0, 5.6, 6.0, 6.5, 0, z + 6.0)   # M3 nut trap
    return register("pad_rod_stop", m, M["orange"], note="M3 screw + nut; sets the rocket height (nozzle 45 mm above the plate)", group="pad")


def pad_leg_foot(M):
    ri, ro = LEG_D / 2 + 0.3, LEG_D / 2 + 3.0
    m = revolve([(4.2, 0.0), (17.0, 0.0), (17.0, 4.0), (ro, 4.0), (ro, 30.0), (ri, 30.0), (ri, 5.0), (4.2, 5.0)], 64)
    return register("pad_leg_foot", m, M["black"], qty=3, note="Tent peg through the foot holds the pad down", group="pad")


def rod_cap(M):
    m = cyl(9.0, 30.0, 0.0, r2=6.0, segs=48) - cyl(3.2, 25.0, -1.0, segs=24)
    return register("rod_tip_safety_cap", m, M["orange"], note="Keep on the rod tip whenever there is no rocket on the pad", group="pad")


def lower_tube_cut():
    """The lower body tube as the builder leaves it: camera window, switch/LED slot, static ports, screw holes."""
    t = tube(R, RI, L_LOW, 0.0)
    t = t - polar(box(8.0, CAM_WIN_W, CAM_WIN_H, R, 0, CAM_Z0 + CAM_WIN_H / 2), 270)
    t = t - polar(box(8.0, 7.0, 20.0, R, 0, SW_Z), SW_ANG)
    for a in STATIC_PORT_ANG:
        t = t - polar(xcyl(1.0, 6, 16).translate((R, 0, Z_AV0 + 40.0)), a)
    for a in RADIAL_SCREW_ANG:
        t = t - polar(xcyl(1.65, 6, 16).translate((R, 0, Z_AV0 + 12.0)), a)
    for a in TAIL_SCREW_ANG:
        t = t - polar(xcyl(1.65, 6, 16).translate((R, 0, TAIL_SCREW_Z)), a)
    return t


def drill_guide(M):
    """Build tool: slides down over the top of the lower body tube (lip on the tube end) and marks every hole
    the airframe needs - 2 x M3 av-bay screws, 3 static ports, the switch/LED slot and the camera window -
    plus a groove on the launch-lug line.  Drill/cut BEFORE gluing the upper lug."""
    z_top, z_bot = Z_BAND0, CAM_Z0 - 6.0
    m = tube(R + 2.2, R + 0.25, z_top - z_bot, z_bot) + tube(R + 2.2, RI - 0.8, 2.0, z_top)
    for a in RADIAL_SCREW_ANG:
        m = m - polar(xcyl(1.6, 10, 24).translate((R + 1, 0, Z_AV0 + 12.0)), a)
    for a in STATIC_PORT_ANG:
        m = m - polar(xcyl(1.0, 10, 16).translate((R + 1, 0, Z_AV0 + 40.0)), a)
    m = m - polar(box(8.0, 7.0, 20.0, R + 1.0, 0, SW_Z), SW_ANG)
    m = m - polar(box(8.0, CAM_WIN_W, CAM_WIN_H, R + 1.0, 0, CAM_Z0 + CAM_WIN_H / 2), 270)
    m = m - polar(box(1.6, 1.2, z_top - z_bot + 10.0, R + 2.2, 0, (z_top + z_bot) / 2), 60)
    return register("tool_drill_guide_lower_tube", m, M["orange"], print_rot=(180, 0, 0), group="tool",
                    note="Build tool (not flown). Print lip-down. Slide over the top of the lower tube, then drill/cut through it")


# ======================================================================================
# purchased-part stand-ins
# ======================================================================================
def purchased(M):
    s = SV
    out = {}
    out[LOWER_TUBE] = (lower_tube_cut(), M["kraft"])
    out[UPPER_TUBE] = (tube(R, RI, L_UP, Z_UP0), M["kraft"])
    out[MOTOR_NAME] = (cyl(MOTOR_D / 2, MOTOR_L, Z_MOTOR0) - cyl(4.0, 12.0, Z_MOTOR0 - 1.0, segs=24), M["motor"])
    c1 = SV1_Z + s["shaft_off"] - s["L"] / 2
    c2 = SV2_Z + s["shaft_off"] - s["L"] / 2
    sv1 = box(s["W"], s["H"], s["L"], 0, SV_SHAFT_R - s["H"] / 2, c1) + box(s["W"] - 1, 2.5, s["tab_L"], 0, SV_SHAFT_R - s["H"] + s["tab_z"] + 1.25, c1)
    sv1 = sv1 + ycyl(2.4, s["spline"], 16).translate((0, SV_SHAFT_R + s["spline"] / 2, SV1_Z)) + box(PR1[0] + 6.0, 2.0, 4.5, (PR1[0] - 1.0) / 2, SV_SHAFT_R + 4.0, SV1_Z)
    out["servo_MG90S_tvc_ring"] = (sv1, M["servo"])
    sv2 = box(s["H"], s["W"], s["L"], SV_SHAFT_R - s["H"] / 2, 0, c2) + box(2.5, s["W"] - 1, s["tab_L"], SV_SHAFT_R - s["H"] + s["tab_z"] + 1.25, 0, c2)
    sv2 = sv2 + xcyl(2.4, s["spline"], 16).translate((SV_SHAFT_R + s["spline"] / 2, 0, SV2_Z)) + box(2.0, PR2[1] + 6.0, 4.5, SV_SHAFT_R + 4.0, (PR2[1] - 1.0) / 2, SV2_Z)
    out["servo_MG90S_tvc_holder"] = (sv2, M["servo"])
    out["pushrod_ring_1.2mm"] = (cyl(0.6, SV1_Z - Z_PIVOT, Z_PIVOT, PR1[0], PR1[1], segs=12), M["steel"])
    out["pushrod_holder_1.2mm"] = (cyl(0.6, SV2_Z - HOLDER_TAB_Z, HOLDER_TAB_Z, PR2[0], PR2[1], segs=12), M["steel"])
    z_shaft_top = Z_LATCH + 4.0
    zb = z_shaft_top - s["spline"] - s["H"]
    dep = box(s["W"], s["L"], s["H"], 0, -(s["L"] / 2 - s["shaft_off"]), zb + s["H"] / 2)
    dep = dep + box(s["W"] - 1, s["tab_L"], 2.5, 0, -(s["L"] / 2 - s["shaft_off"]), zb + s["tab_z"] + 1.25)
    dep = dep + cyl(2.4, s["spline"], z_shaft_top - s["spline"], segs=16)
    out["servo_MG90S_deploy"] = (dep, M["servo"])
    out["servo_horn_deploy"] = (box(30.0, 5.0, 2.2, 0, 0, z_shaft_top + 1.1), M["white"])
    out[PCB_NAME] = (box(BW, BT, BH, 0, PCB_Y_BACK + BT / 2, PCB_Z_TOP - BH / 2), M["pcb"])
    x10 = board_to_rocket(MECH["parts"]["J10"]["x"], 0)[0]
    x11 = board_to_rocket(MECH["parts"]["J11"]["x"], 0)[0]
    pz = PCB_Z_TOP - (MECH["parts"]["J10"]["y"] + MECH["parts"]["J11"]["y"]) / 2
    yp = PCB_Y_FRONT + SOCKET_H
    pico = box(2.5, SOCKET_H, 50.8, x10, PCB_Y_FRONT + SOCKET_H / 2, pz) + box(2.5, SOCKET_H, 50.8, x11, PCB_Y_FRONT + SOCKET_H / 2, pz)
    pico = pico + box(21.0, 1.0, 51.0, (x10 + x11) / 2, yp + 0.5, pz)                       # Pico 2 W board
    pico = pico + box(11.0, 1.6, 13.0, (x10 + x11) / 2, yp + 1.8, pz - 12.0)                # radio module can
    pico = pico + box(8.0, 2.6, 5.5, (x10 + x11) / 2, yp + 2.3, pz + 25.5 - 2.75)            # micro-USB (top end)
    out["pico2w_on_sockets"] = (pico, M["pico"])
    bx, bz = board_to_rocket(13.25, 7.15)
    parts_fc = ycyl(6.0, 9.5, 32).translate((bx, PCB_Y_FRONT + 4.75, bz))                # buzzer
    jx, jz = board_to_rocket(MECH["parts"]["J1"]["x"], (MECH["parts"]["J1"]["y"] - 2.5))
    parts_fc = parts_fc + box(5.75, 7.0, 9.9, jx, PCB_Y_FRONT + 3.5, jz)                  # JST-XH balance plug socket
    sx_, sz_ = board_to_rocket(MECH["parts"]["SW1"]["x"], MECH["parts"]["SW1"]["y"])
    parts_fc = parts_fc + box(2.6, 1.4, 6.7, sx_ - 0.2, PCB_Y_FRONT + 0.7, sz_)               # PCM12 power switch
    for r in ("J2", "J3", "J4", "J5"):                                                      # servo plugs on the headers
        hx, hz = board_to_rocket(MECH["parts"][r]["x"], MECH["parts"][r]["y"] + 2.54)
        parts_fc = parts_fc + box(2.6, 14.0, 7.6, hx, PCB_Y_FRONT + 2.5 + 7.0, hz)
    out["fc_connectors_buzzer_switch"] = (parts_fc, M["servo"])
    out["lipo_2s_200mah"] = (box(BATT["w"], BATT["t"], BATT["l"], 0, BATT["y0"] + BAY["t"] - BATT["t"] / 2, BATT["z0"] + BATT["l"] / 2), M["lipo"])
    out["gps_patch_antenna_18mm"] = (box(18.0, 18.0, 4.0, 0, -(SV["L"] / 2 - SV["shaft_off"]), Z_SH1 - 3.0), M["antenna"])
    spring = None
    n = 400
    pts = [(12.5 * math.cos(2 * math.pi * 8 * i / n), 12.5 * math.sin(2 * math.pi * 8 * i / n),
            Z_SH1 + BULK_T + 20.0 * i / n) for i in range(n + 1)]
    out["_spring_curve"] = pts
    out["parachute_24in_packed"] = (cyl(21.0, 110.0, Z_SH1 + BULK_T + 27.0, segs=48), M["nylon"])
    cam = box(23.0, 23.0, 23.0, 0, -CAM_RC, CAM_Z0 + CAM_FLOOR + 0.3 + 11.5) + cyl(4.0, 1.9, CAM_Z0 + 0.2, 0, -CAM_RC, segs=24)
    out["camera_SQ12_class"] = (cam, M["camera"])
    return out


def pad_purchased(M, rod_z0):
    out = {}
    out["blast_plate_150x150_steel"] = (box(150.0, 150.0, 1.5, 0, 0, HUB_H + 10.75) - cyl(9.0, 5.0, HUB_H + 8, segs=32), M["steel"])
    out["launch_rod_6mm_1m"] = (cyl(3.0, 1000.0, rod_z0, segs=24), M["steel"])
    for k in range(3):
        out[f"leg_dowel_22mm_{k+1}"] = (leg_axis_transform(cyl(LEG_D / 2, LEG_L, -LEG_L + 25.0, segs=32), k), M["wood"])
    return out


# ======================================================================================
def build_all(M):
    nose_cone(M); latch_collar(M); avbay_coupler(M); latch_bolt(M, 1); latch_bolt(M, -1)
    spring_piston(M); avbay_sled(M); tvc_holder(M); tvc_ring(M); tvc_frame(M); retainer(M)
    fin_can(M); upper_lug(M); camera_pod(M)
    pad_hub(M); pad_rod_block(M)
    plate_top = HUB_H + 10.0 + 1.5
    tail_z = plate_top + 45.0 + TVC["nozzle_protrusion"]
    stop_z = tail_z + 50.0 - 12.0
    pad_rod_stop(M, stop_z); pad_leg_foot(M); rod_cap(M)
    drill_guide(M)
    return tail_z


def export_stls():
    report = []
    for name, p in PARTS.items():
        m = p["m"]
        rx, ry, rz = p["print_rot"]
        m2 = m.rotate((rx, ry, rz))
        bb = m2.bounding_box()
        m2 = m2.translate((-(bb[0] + bb[3]) / 2, -(bb[1] + bb[4]) / 2, -bb[2]))
        mesh = m2.to_mesh()
        write_stl(os.path.join(STL_DIR, name + ".stl"), np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts))
        mm = m.to_mesh()
        V = np.asarray(mm.vert_properties)[:, :3].astype(float)
        F = np.asarray(mm.tri_verts)
        a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
        vol6 = np.einsum("ij,ij->i", a, np.cross(b, c))
        cen = ((a + b + c) * vol6[:, None]).sum(0) / (4.0 * vol6.sum())
        area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum()
        rxy = np.sqrt((((a + b + c) / 3.0)[:, :2] ** 2).sum(1))
        report.append(dict(name=name, qty=p["qty"], note=p["note"], group=p["group"], volume_mm3=float(m.volume()),
                           area_mm2=float(area), centroid_assembly_mm=[float(x) for x in cen],
                           r_gyr_mm=float(np.sqrt((rxy ** 2).mean()))))
    with open(os.path.join(STL_DIR, "parts.json"), "w") as fh:
        json.dump(report, fh, indent=1)


def write_stl(path, V, F):
    import struct
    with open(path, "wb") as fh:
        fh.write(b"KESTREL-1 STL (mm)".ljust(80, b" "))
        fh.write(struct.pack("<I", len(F)))
        for a, b, c in F:
            va, vb, vc = V[a], V[b], V[c]
            n = np.cross(vb - va, vc - va)
            ln = np.linalg.norm(n)
            n = n / ln if ln > 0 else n
            fh.write(struct.pack("<12fH", *n, *va, *vb, *vc, 0))


def spring_obj(pts, M, coll, name="spring_25x60", dz=0.0):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2] + dz, 1)
    cu.bevel_depth = 0.6
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(M["steel"])
    coll.objects.link(ob)
    return ob


def setup_render(res=(1600, 1000)):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 12 if FAST else 64
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.87, 0.90, 0.94, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.85
    sc.world = w
    for nm, en, rot in (("key", 3.2, (50, 10, 30)), ("fill", 1.1, (70, 0, 200)), ("rim", 1.5, (110, 0, 120))):
        l = bpy.data.lights.new(nm, "SUN")
        l.energy = en
        o = bpy.data.objects.new(nm, l)
        o.rotation_euler = tuple(math.radians(a) for a in rot)
        sc.collection.objects.link(o)


def camera_at(name, loc, target, lens=50):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_start = 1.0
    cam.clip_end = 50000
    co = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return co


def check_layout():
    """Positions the flight simulator / firmware take from design.json must match this CAD + the PCB layout."""
    z_tip = Z_NOSE0 + NOSE_L
    u4 = MECH["parts"]["U4"]
    imu_from_tip = z_tip - board_to_rocket(u4["x"], u4["y"])[1]
    comp = {c["name"]: c for c in D["components"]}
    want = {
        "avbay.imu_z (LSM6DSO U4)": (D["avbay"]["imu_z"], imu_from_tip),
        "flight_computer_pcb_pico.z": (comp["flight_computer_pcb_pico"]["z"], z_tip - (PCB_Z_TOP - BH / 2)),
        "lipo_2s_200mah.z": (comp["lipo_2s_200mah"]["z"], z_tip - (BATT["z0"] + BATT["l"] / 2)),
        "camera_sq12_class.z": (comp["camera_sq12_class"]["z"], z_tip - (CAM_Z0 + CAM_FLOOR + 0.3 + 11.5)),
        "camera_pod.protrusion_mm": (D["camera_pod"]["protrusion_mm"], CAM_RC + CAM_POCKET / 2 + 1.2 - R),
        "camera_pod.width_mm": (D["camera_pod"]["width_mm"], CAM_POCKET + 2 * 1.6),
    }
    bad = []
    for k, (have, real) in want.items():
        flag = abs(have - real) > 1.5
        print(f"layout check {k:30s} design.json {have:7.1f} mm  CAD/PCB {real:7.1f} mm  {'MISMATCH' if flag else 'ok'}")
        if flag:
            bad.append(f"{k}: set {real:.0f}")
    json.dump({k: round(v[1], 1) for k, v in want.items()}, open(os.path.join(HERE, "avionics_layout.json"), "w"), indent=1)
    if bad:
        raise SystemExit("design.json is out of date with the CAD/PCB layout -> " + "; ".join(bad))


def interference_report(buy):
    """Pairwise solid-solid overlap between every printed rocket part and purchased stand-in (manifold CSG).
    Writes cad/interference_report.md; fails if any pair overlaps by more than 1 mm^3."""
    objs = [(n, p["m"]) for n, p in PARTS.items() if p["group"] == "rocket"]
    objs += [(n, v[0]) for n, v in buy.items() if not n.startswith("_")]
    boxes = [m.bounding_box() for _, m in objs]
    rows, bad = [], []
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = boxes[i], boxes[j]
            if a[0] > b[3] or b[0] > a[3] or a[1] > b[4] or b[1] > a[4] or a[2] > b[5] or b[2] > a[5]:
                continue
            v = (objs[i][1] ^ objs[j][1]).volume()
            if v > 1.0:
                bad.append((objs[i][0], objs[j][0], v))
    n_pairs = len(objs) * (len(objs) - 1) // 2
    md = [f"# Interference check\n\n{len(objs)} solids ({n_pairs} pairs) checked with exact mesh booleans.\n"]
    if bad:
        md.append("| part A | part B | overlap mm^3 |\n|---|---|---|")
        md += [f"| {a} | {b} | {v:.1f} |" for a, b, v in bad]
    else:
        md.append("**No overlaps** (> 1 mm^3) between any printed part and any purchased part.")
    open(os.path.join(HERE, "interference_report.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))
    if bad:
        raise SystemExit(f"{len(bad)} interfering pairs - see cad/interference_report.md")


def gimbal_sweep_report(buy, max_deg=None):
    """Swing the gimbal to every corner of its travel (design max + 1 deg margin on both axes) and check the
    moving parts (motor, holder, retainer, ring) against the static structure and each other.  Appends to
    cad/interference_report.md; fails on any contact > 0.5 mm^3."""
    max_deg = max_deg or TVC["max_deflection_deg"] + 1.0
    inner = [("tvc_motor_holder", PARTS["tvc_motor_holder"]["m"]), ("tvc_motor_retainer", PARTS["tvc_motor_retainer"]["m"]),
             (MOTOR_NAME, buy[MOTOR_NAME][0])]
    ring = ("tvc_gimbal_ring", PARTS["tvc_gimbal_ring"]["m"])
    static = [(n, PARTS[n]["m"]) for n in ("tvc_frame", "fin_can")]
    static += [(n, buy[n][0]) for n in (LOWER_TUBE, "servo_MG90S_tvc_ring", "servo_MG90S_tvc_holder")]

    def piv(m, rx, ry):   # holder axis (Y) first, then the ring axis (X), both through the pivot point
        return m.translate((0, 0, -Z_PIVOT)).rotate((0, ry, 0)).rotate((rx, 0, 0)).translate((0, 0, Z_PIVOT))
    worst, rows, n = {}, [], 0
    envelope = [(0.0, 0.0)] + [(max_deg * math.cos(math.radians(a)), max_deg * math.sin(math.radians(a)))
                               for a in range(0, 360, 15)]        # firmware clamps the deflection VECTOR (circular)
    for rx, ry in envelope:
        if True:
            moving = [(nm, piv(m, rx, ry)) for nm, m in inner] + [(ring[0], piv(ring[1], rx, 0.0))]
            for nm, m in moving:
                for sn, sm in static:
                    x = m ^ sm
                    n += 1
                    if x.volume() > 0.5:
                        rows.append((rx, ry, nm, sn, x.volume(), x.bounding_box()))
            for nm, m in moving[:2]:
                x = m ^ moving[-1][1]
                n += 1
                if x.volume() > 0.5:
                    rows.append((rx, ry, nm, ring[0], x.volume(), x.bounding_box()))
    md = [f"\n## Gimbal sweep\n\nMotor, holder, retainer and ring swung round the whole deflection circle "
          f"({len(envelope) - 1} directions at {max_deg:.0f} deg = firmware limit {TVC['max_deflection_deg']} deg + 1 deg margin), "
          f"{n} contact checks.\n"]
    if rows:
        md.append("| ring deg | holder deg | moving part | hits | overlap mm^3 | where (x, y, z mm) |\n|---|---|---|---|---|---|")
        md += [f"| {a:+.0f} | {b:+.0f} | {c} | {d} | {v:.1f} | ({(bb[0]+bb[3])/2:.1f}, {(bb[1]+bb[4])/2:.1f}, {bb[2]:.1f}..{bb[5]:.1f}) |"
               for a, b, c, d, v, bb in rows]
    else:
        md.append("**No contact** anywhere in the travel envelope.")
    with open(os.path.join(HERE, "interference_report.md"), "a") as fh:
        fh.write("\n".join(md) + "\n")
    print("\n".join(md))
    if rows:
        raise SystemExit(f"gimbal sweep: {len(rows)} contacts - see cad/interference_report.md")


def main():
    reset_scene()
    M = MATS()
    tail_z = build_all(M)
    export_stls()
    check_layout()
    buy0 = purchased(M)
    interference_report(buy0)
    gimbal_sweep_report(buy0)
    # ---------------- Blender assembly ----------------
    c_rk = collection("Rocket (assembled)")
    c_buy = collection("Rocket purchased parts")
    c_pad = collection("Launch pad")
    c_tool = collection("Build tools")
    c_on = collection("Rocket on pad")
    c_ex = collection("Exploded view")
    buy = purchased(M)
    spring_pts = buy.pop("_spring_curve")
    for name, p in PARTS.items():
        tgt = {"rocket": c_rk, "pad": c_pad}.get(p["group"], c_tool)
        to_blender(name, p["m"], p["material"], tgt)
    for name, (m, material) in buy.items():
        to_blender(name, m, material, c_buy)
    spring_obj(spring_pts, M, c_buy)
    for name, (m, material) in pad_purchased(M, HUB_H - 4.0).items():
        to_blender(name, m, material, c_pad)
    # rocket on the pad
    for coll in (c_rk, c_buy):
        for ob in coll.objects:
            o2 = ob.copy()
            o2.location = (0, 0, tail_z)
            c_on.objects.link(o2)
    # exploded view
    offsets = {"nose_cone": 300, UPPER_TUBE: 200, "parachute_24in_packed": 150, "spring_piston": 130,
               "spring_25x60": 95, "latch_collar": 120, "avbay_coupler": 40, "latch_bolt_pos": 55, "latch_bolt_neg": 55,
               "servo_horn_deploy": 70, "gps_patch_antenna_18mm": 110, "servo_MG90S_deploy": 18, "avbay_sled": -70,
               PCB_NAME: -70, "pico2w_on_sockets": -70, "fc_connectors_buzzer_switch": -70, "lipo_2s_200mah": -70,
               "camera_pod": -30, "camera_SQ12_class": -30, "upper_launch_lug": -40, LOWER_TUBE: 0, "fin_can": -190,
               "tvc_frame": -300, "servo_MG90S_tvc_ring": -300, "servo_MG90S_tvc_holder": -300,
               "pushrod_ring_1.2mm": -330, "pushrod_holder_1.2mm": -330, "tvc_gimbal_ring": -370,
               "tvc_motor_holder": -430, MOTOR_NAME: -560, "tvc_motor_retainer": -640}
    for coll in (c_rk, c_buy):
        for ob in coll.objects:
            o2 = ob.copy()
            dx = 160.0 if ob.name in ("camera_pod", "camera_SQ12_class", "upper_launch_lug") else 0.0
            o2.location = (dx, 0, offsets.get(ob.name, 0))
            c_ex.objects.link(o2)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "kestrel.blend"))
    if "--no-render" in ARGS:
        return
    setup_render()
    views = [
        ("rocket_on_pad", (1700, -2300, 1300), (0, 0, 600), 50, {c_on.name, c_pad.name}, []),
        ("rocket_exploded", (2600, -2600, 700), (0, 0, 380), 42, {c_ex.name}, []),
        ("tvc_gimbal_cutaway", (175, -215, 150), (0, 0, 88), 50, {c_rk.name, c_buy.name},
         [LOWER_TUBE, "fin_can", "camera_pod", "camera_SQ12_class", "upper_launch_lug"]),
        ("avbay_cutaway", (215, -250, 650), (0, 0, 560), 50, {c_rk.name, c_buy.name},
         [LOWER_TUBE, UPPER_TUBE, "latch_collar", "parachute_24in_packed", "camera_pod", "camera_SQ12_class"]),
        ("launch_pad", (1000, -1250, 650), (0, 0, 120), 40, {c_pad.name}, []),
    ]
    sc = bpy.context.scene
    for name, loc, tgt, lens, vis, hide in views:
        cam = camera_at("cam_" + name, loc, tgt, lens)
        sc.camera = cam
        for c in bpy.data.collections:
            c.hide_render = c.name not in vis
        hidden = []
        for o in bpy.data.objects:
            if o.name.split(".")[0] in hide:
                o.hide_render = True
                hidden.append(o)
        sc.render.filepath = os.path.join(REN_DIR, name + ".png")
        bpy.ops.render.render(write_still=True)
        for o in hidden:
            o.hide_render = False
    for c in bpy.data.collections:
        c.hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "kestrel.blend"))


main()
