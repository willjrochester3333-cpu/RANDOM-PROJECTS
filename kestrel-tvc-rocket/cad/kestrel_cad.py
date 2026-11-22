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
SV1_Z, SV2_Z = 116.0, 141.0           # TVC servo shaft heights
SV_SHAFT_R = 16.0                     # servo shaft exit distance from the axis
PR1 = (9.0, 18.0)                     # pushrod 1 (ring, rotates about X): x, y
PR2 = (18.0, 9.0)                     # pushrod 2 (holder, rotates about Y)
HOLDER_TAB_Z = Z_PIVOT + 12.0

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
        post = box(7.0, 6.0, Z_SH1 - z_tab_top + 0.6, 0, hy + off, (Z_SH1 + z_tab_top) / 2)
        post = post - cyl(0.8, 10.0, z_tab_top - 1.0, 0, hy, segs=16)         # 1.6 mm pilot for servo screw
        m = m + (post ^ cyl(SH_R - 0.5, 200, Z_AV0))
    # 2 x M3 radial screw holes (through lower tube -> insert -> sled nut traps)
    for ang in (90, 270):
        m = m - polar(xcyl(1.65, 12).translate((INS_R, 0, Z_AV0 + 12)), ang)
    # switch / LED window at -X (aligned with the PCB edge) and 3 static ports
    m = m - box(8.0, 12.0, 16.0, -(INS_R - 1.0), -2.0, Z_AV0 + 62)
    for ang in (30, 150, 270):
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
    z0 = Z_AV0
    rb = INS_R - WALL - 0.25
    m = cyl(rb, 3.0, z0)
    plate = box(40.0, 2.0, 83.0, 0, -17.6, z0 + 2.5 + 41.5)
    plate = plate - box(26.0, 4.0, 22.0, 0, -17.6, z0 + 28.0) - box(26.0, 4.0, 22.0, 0, -17.6, z0 + 58.0)   # lightening
    m = m + plate
    for (px, pz) in ((-16.5, 6.5), (16.5, 6.5), (-16.5, 76.5), (16.5, 76.5)):
        so = ycyl(2.5, 3.0, 24).translate((px, -15.4, z0 + 3 + pz)) - ycyl(1.1, 8.0, 16).translate((px, -16.0, z0 + 3 + pz))
        m = m + so
        m = m - ycyl(1.1, 8.0, 16).translate((px, -16.0, z0 + 3 + pz))
    tray = box(34.0, 1.6, 66.0, 0, 21.0, z0 + 2.5 + 33.0)
    tray = tray + box(34.0, 6.0, 1.6, 0, 18.4, z0 + 2.8)
    m = m + (tray ^ cyl(rb, 200, z0))
    for zz in (18, 52):
        m = m - box(26.0, 4.0, 3.2, 0, 21.0, z0 + 3 + zz)   # closed velcro-strap slots
    for ang in (90, 270):
        nt = box(5.9, 6.0, 2.8, rb - 3.2, 0, z0 + 12).rotate((0, 0, 0))
        m = m - polar(nt, ang) - polar(xcyl(1.65, 10).translate((rb - 3, 0, z0 + 12)), ang)
        boss = (box(5.0, 9.0, 12.0, rb - 2.6, 0, z0 + 8.0) - box(5.9, 6.0, 2.8, rb - 3.2, 0, z0 + 12) -
                xcyl(1.65, 10).translate((rb - 3, 0, z0 + 12)))
        m = m + (polar(boss, ang) ^ cyl(rb, 30, z0))
    m = m - cyl(4.0, 10.0, z0 - 2.0, 12.0, 4.0, segs=24)                         # cable pass-through
    return register("avbay_sled", m, M["grey"], note="Print with the bulkhead disc on the bed. 4 x M2.5x6 screws hold the PCB")


def tvc_holder(M):
    z1 = Z_MOTOR0 + MOTOR_L + 1.5 + 2.5
    zc = z1 - 2.2                     # underside of the 2.2 mm thrust cap
    # single revolved profile: motor bore, 25 mm washer recess, closed thrust cap (no coincident faces)
    m = revolve([(HOLD_RI, 0.0), (HOLD_R, 0.0), (HOLD_R, z1), (0.0, z1), (0.0, zc), (12.6, zc),
                 (12.6, zc - 1.9), (HOLD_RI, zc - 1.9)])
    for sy in (1, -1):
        m = m + ycyl(3.4, 2.4, 32).translate((0, sy * (HOLD_R + 0.9), Z_PIVOT))
    # re-cut the M3 pilot only through the bosses (not the bore)
    for sy in (1, -1):
        m = m - ycyl(1.25, 3.0, 16).translate((0, sy * (HOLD_R + 0.9), Z_PIVOT))
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
        m = m + ycyl(3.0, 2.0, 32).translate((0, sy * (RING_RI + 0.6), Z_PIVOT))   # inner bearing pads
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
    windows = [(10.0, 40.0), (56.0, 92.0), (101.0, 116.0), (129.0, 143.0)]
    longerons = (30.0, 150.0, 270.0)
    for z0, z1 in windows:
        w = tube(ro + 1.0, ri - 1.0, z1 - z0, z0, segs=96)
        for a in longerons:
            w = w - polar(box(14.0, 9.0, z1 - z0 + 2.0, ro - 2.0, 0, (z0 + z1) / 2), a)
        m = m - w
    m = m + tube(ro, 23.4, 4.0, 0.0)                                               # aft ring lip
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
    for a in (90, 210):
        m = m - polar(xcyl(1.65, 8, 16).translate((ro - 1.5, 0, 6.0)), a)
        m = m + polar((box(6.0, 8.0, 8.0, ri - 2.0, 0, 6.0) - box(2.8, 5.9, 6.5, ri - 2.6, 0, 6.0) -
                       xcyl(1.65, 12, 16).translate((ri, 0, 6.0))) ^ cyl(ro, 40, 0), a)
    return register("tvc_frame", m, M["grey"], note="PETG, print upright; supports only under the servo bars")


def retainer(M):
    z0 = Z_MOTOR0 - 1.5
    m = tube(HOLD_R + 3.4, HOLD_R + 0.3, 11.5, z0) + tube(HOLD_R + 3.4, 8.0, 1.5, z0)
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
    for a in (90, 210):
        m = m - polar(xcyl(1.65, 8, 16).translate((ro - 0.4, 0, 6.0)), a)
    return register("fin_can", m, M["orange"], note="PETG, print upright (fins vertical), 3 walls")


def upper_lug(M):
    z0 = Z_AV0 - 30.0
    ro_can = R + 0.10 + FIN["can_wall"]
    m = tube(4.75, 3.4, 25.0, z0, segs=40).translate((ro_can + 4.4, 0, 0)) + box(6.5, 4.0, 25.0, R + 2.6, 0, z0 + 12.5)
    m = m - cyl(R, 40.0, z0 - 5)
    return register("upper_launch_lug", polar(m, 60), M["black"], note="Glue to the lower tube in line with the fin-can lug (slide both on the rod while the glue sets)")


def camera_pod(M):
    """Half-recessed pod for a ~23 mm cube mini camera, lens looking aft. Sits in a 26 x 30 mm
    window cut in the lower tube; the flange is glued/taped to the tube."""
    z0, cam = 425.0, 23.6
    w = cam + 3.2
    base = box(w, 0.1, cam + 6.0, 0, R + 10.0, z0 + (cam + 6.0) / 2)
    tip = box(4.0, 0.1, 1.0, 0, R + 2.0, z0 + cam + 26.0)
    shell = M3.batch_hull([base, tip, box(w, 0.1, cam + 6, 0, R - 6.0, z0 + (cam + 6) / 2),
                           box(w, 0.1, 1.0, 0, R - 6.0, z0 + cam + 24.0)])
    shell = shell - box(cam, cam + 2, cam + 1.0, 0, R - 2.5, z0 + cam / 2 + 1.5)             # camera pocket
    shell = shell - box(14.0, 16.0, 6.0, 0, R - 2.5, z0)                                         # lens opening
    shell = shell - (cyl(RI - 0.3, 200, z0 - 50) - box(cam + 3.2, 60, 200, 0, RI - 12.0, z0))      # stay outside the bore except pocket
    flange = (tube(R + 1.2, R + 0.1, cam + 10.0, z0 - 2.0) ^ box(w + 10.0, 30.0, cam + 10.0, 0, R, z0 + cam / 2 + 3.0)) - \
        box(w - 0.1, 30, cam + 30, 0, R, z0)
    m = shell + flange
    m = m - box(cam, cam + 2, cam + 1.0, 0, R - 2.5, z0 + cam / 2 + 1.5)
    return register("camera_pod", polar(m, 180), M["black"], note="Cut a 27 x 30 mm window in the lower tube at the marked position; glue flange, foam-pad the camera")


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


# ======================================================================================
# purchased-part stand-ins
# ======================================================================================
def purchased(M):
    s = SV
    out = {}
    out["BT70_lower_tube_580"] = (tube(R, RI, L_LOW, 0.0), M["kraft"])
    out["BT70_upper_tube_250"] = (tube(R, RI, L_UP, Z_UP0), M["kraft"])
    out["motor_TSP_E12_24x95"] = (cyl(MOTOR_D / 2, MOTOR_L, Z_MOTOR0) - cyl(4.0, 12.0, Z_MOTOR0 - 1.0, segs=24), M["motor"])
    c1 = SV1_Z + s["shaft_off"] - s["L"] / 2
    c2 = SV2_Z + s["shaft_off"] - s["L"] / 2
    sv1 = box(s["W"], s["H"], s["L"], 0, SV_SHAFT_R - s["H"] / 2, c1) + box(s["W"] - 1, 2.5, s["tab_L"], 0, SV_SHAFT_R - s["H"] + s["tab_z"] + 1.25, c1)
    sv1 = sv1 + ycyl(2.4, s["spline"], 16).translate((0, SV_SHAFT_R + s["spline"] / 2, SV1_Z)) + box(22.0, 2.0, 4.5, PR1[0] - 2.0, SV_SHAFT_R + 4.0, SV1_Z)
    out["servo_MG90S_tvc_ring"] = (sv1, M["servo"])
    sv2 = box(s["H"], s["W"], s["L"], SV_SHAFT_R - s["H"] / 2, 0, c2) + box(2.5, s["W"] - 1, s["tab_L"], SV_SHAFT_R - s["H"] + s["tab_z"] + 1.25, 0, c2)
    sv2 = sv2 + xcyl(2.4, s["spline"], 16).translate((SV_SHAFT_R + s["spline"] / 2, 0, SV2_Z)) + box(2.0, 22.0, 4.5, SV_SHAFT_R + 4.0, PR2[1] - 2.0, SV2_Z)
    out["servo_MG90S_tvc_holder"] = (sv2, M["servo"])
    out["pushrod_ring_1.2mm"] = (cyl(0.6, SV1_Z - Z_PIVOT, Z_PIVOT, PR1[0], PR1[1], segs=12), M["steel"])
    out["pushrod_holder_1.2mm"] = (cyl(0.6, SV2_Z - HOLDER_TAB_Z, HOLDER_TAB_Z, PR2[0], PR2[1], segs=12), M["steel"])
    z_shaft_top = Z_LATCH + 4.0
    zb = z_shaft_top - s["spline"] - s["H"]
    dep = box(s["W"], s["L"], s["H"], 0, -(s["L"] / 2 - s["shaft_off"]), zb + s["H"] / 2)
    dep = dep + box(s["W"] - 1, s["tab_L"], 2.5, 0, -(s["L"] / 2 - s["shaft_off"]), zb + s["tab_z"] + 1.25)
    dep = dep + cyl(2.4, s["spline"], z_shaft_top - s["spline"], segs=16)
    out["servo_MG90S_deploy"] = (dep, M["servo"])
    out["servo_horn_deploy"] = (box(30.0, 5.0, 2.2, 0, 0, z_shaft_top + 0.2), M["white"])
    out["pcb_kestrel_fc_40x80"] = (box(40.0, 1.6, 80.0, 0, -15.8, Z_AV0 + 3 + 41), M["pcb"])
    out["pico2w_on_headers"] = (box(21.0, 1.0, 51.0, -6.0, -4.0, Z_AV0 + 3 + 45) + box(2.5, 8.5, 51.0, -14.9, -10.0, Z_AV0 + 48) +
                                box(2.5, 8.5, 51.0, 2.9, -10.0, Z_AV0 + 48), M["pico"])
    out["lipo_2s_300mah"] = (box(31.0, 12.0, 55.0, 0, 13.8, Z_AV0 + 3 + 34), M["lipo"])
    out["gps_patch_antenna"] = (box(25.0, 25.0, 4.0, 0, 0, Z_SH1 - 3.0), M["antenna"])
    spring = None
    n = 400
    pts = [(12.5 * math.cos(2 * math.pi * 8 * i / n), 12.5 * math.sin(2 * math.pi * 8 * i / n),
            Z_SH1 + BULK_T + 20.0 * i / n) for i in range(n + 1)]
    out["_spring_curve"] = pts
    out["parachute_24in_packed"] = (cyl(21.0, 110.0, Z_SH1 + BULK_T + 27.0, segs=48), M["nylon"])
    cam = box(23.0, 23.0, 23.0, 0, -(R - 2.5), 425.0 + 13.0) + cyl(4.0, 3.0, 425.0 - 1.0, 0, -(R - 2.5), segs=24)
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


def main():
    reset_scene()
    M = MATS()
    tail_z = build_all(M)
    export_stls()
    # ---------------- Blender assembly ----------------
    c_rk = collection("Rocket (assembled)")
    c_buy = collection("Rocket purchased parts")
    c_pad = collection("Launch pad")
    c_on = collection("Rocket on pad")
    c_ex = collection("Exploded view")
    buy = purchased(M)
    spring_pts = buy.pop("_spring_curve")
    for name, p in PARTS.items():
        tgt = c_rk if p["group"] == "rocket" else c_pad
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
    offsets = {"nose_cone": 300, "BT70_upper_tube_250": 200, "parachute_24in_packed": 150, "spring_piston": 130,
               "spring_25x60": 95, "latch_collar": 120, "avbay_coupler": 40, "latch_bolt_pos": 55, "latch_bolt_neg": 55,
               "servo_horn_deploy": 70, "gps_patch_antenna": 110, "servo_MG90S_deploy": 18, "avbay_sled": -70,
               "pcb_kestrel_fc_40x80": -70, "pico2w_on_headers": -70, "lipo_2s_300mah": -70, "camera_pod": -30,
               "camera_SQ12_class": -30, "upper_launch_lug": -40, "BT70_lower_tube_580": 0, "fin_can": -190,
               "tvc_frame": -300, "servo_MG90S_tvc_ring": -300, "servo_MG90S_tvc_holder": -300,
               "pushrod_ring_1.2mm": -330, "pushrod_holder_1.2mm": -330, "tvc_gimbal_ring": -370,
               "tvc_motor_holder": -430, "motor_TSP_E12_24x95": -560, "tvc_motor_retainer": -640}
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
         ["BT70_lower_tube_580", "fin_can", "camera_pod", "camera_SQ12_class", "upper_launch_lug"]),
        ("avbay_cutaway", (215, -250, 650), (0, 0, 560), 50, {c_rk.name, c_buy.name},
         ["BT70_lower_tube_580", "BT70_upper_tube_250", "latch_collar", "parachute_24in_packed", "camera_pod", "camera_SQ12_class"]),
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
