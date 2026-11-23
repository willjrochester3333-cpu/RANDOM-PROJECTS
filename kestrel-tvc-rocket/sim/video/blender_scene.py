"""Blender (4.0, headless, EEVEE) side of the KESTREL-2 launch video.

    blender -b -P sim/video/blender_scene.py -- --traj traj.json --camera ground|onboard --out DIR [--draft]

Builds a field with the launch pad, appends the real CAD rocket (cad/kestrel.blend) and the open canopy
(cad/kestrel_parachute_open.blend), animates them from the simulated trajectory and renders one camera:
  ground  - tracking camera on a tripod 30 m from the pad, zooming to keep the rocket framed
  onboard - the rocket's own camera, in the camera pod, looking down past the fins (lens position from the CAD)
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

ARGS = sys.argv[sys.argv.index("--") + 1:]


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


DRAFT = "--draft" in ARGS
TRAJ = json.load(open(arg("--traj")))
CAM = arg("--camera", "ground")
OUT = arg("--out")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CAD = os.path.join(ROOT, "cad")
LAY = json.load(open(os.path.join(CAD, "avionics_layout.json")))
META, FR = TRAJ["meta"], TRAJ["frames"]
FPS = META["fps"]
ZCG = META["z_cg_above_tail_mm"]
P_CAD2BODY = Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0)))       # body = P * cad   (cad Z = rocket axis)


def mat(name, rgb, rough=0.6, metal=0.0, emit=None, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit[0], 1)
        b.inputs["Emission Strength"].default_value = emit[1]
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        m.blend_method = "BLEND"
        m.shadow_method = "NONE"
    return m


def link_to_scene(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


# --------------------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 0.001
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, len(FR)

# rocket + pad from the CAD assembly
with bpy.data.libraries.load(os.path.join(CAD, "kestrel.blend"), link=False) as (src, dst):
    dst.collections = [c for c in src.collections if c in ("Rocket (assembled)", "Launch pad")]
with bpy.data.libraries.load(os.path.join(CAD, "kestrel_parachute_open.blend"), link=False) as (src, dst):
    dst.objects = [o for o in src.objects if o.startswith(("canopy_gore", "shroud_line"))]
rocket_objs = list(bpy.data.collections["Rocket (assembled)"].all_objects)
pad_objs = [o for o in bpy.data.collections["Launch pad"].all_objects if not o.name.startswith("ground")]
chute_objs = [o for o in bpy.data.objects if o.name.startswith(("canopy_gore", "shroud_line"))]
for o in rocket_objs + pad_objs + chute_objs:
    link_to_scene(o)

# pad: feet on the ground (Z=0), rocket axis over the world origin
zmin = min((o.matrix_world @ Vector(c)).z for o in pad_objs if o.type == "MESH" for c in o.bound_box)
rx, ry = LAY["rocket_xy_on_pad"]
for o in pad_objs:
    o.location = (o.location.x - rx, o.location.y - ry, o.location.z - zmin)
H0 = -zmin + LAY["tail_z_on_pad"] + ZCG                     # CG height above the grass at lift-off (mm)

# rocket body: everything parented to RK (origin = CG), nose cone to its own empty (it separates)
RK = bpy.data.objects.new("RK", None); link_to_scene(RK)
NOSE = bpy.data.objects.new("NOSE", None); link_to_scene(NOSE)
off = Matrix.Translation((0, 0, -ZCG))
for o in rocket_objs:
    o.parent = NOSE if o.name.startswith(("nose_cone", "nose_ballast")) else RK      # the ballast rides in the nose
    o.matrix_parent_inverse = off
TOP = bpy.data.objects.new("CORD_TOP", None); link_to_scene(TOP)
TOP.parent = RK; TOP.matrix_parent_inverse = off; TOP.location = LAY["cord_exit_xyz"]
NOSE_EYE = bpy.data.objects.new("NOSE_EYE", None); link_to_scene(NOSE_EYE)          # cord bridge in the nose
NOSE_EYE.parent = NOSE; NOSE_EYE.matrix_parent_inverse = off
NOSE_EYE.location = (0, 0, LAY.get("nose_cord_bar_z", LAY["mid_top_z"] + 18))        # cord bar inside the nose cone

# fin tabs: each one turns about its own hinge line by the simulated tab angle
# (+ = trailing edge away from its servo pod, the firmware's convention; the CAD models + towards the pod)
TAB_PIV = []
HZ = LAY.get("tab_hinge_z", 16.2)
for kk, fin_deg in enumerate(LAY["fin_deg"]):
    obs = [o for o in rocket_objs if o.name.startswith(f"fin_control_tab_{kk + 1}")]
    if not obs:
        continue
    phi = math.radians(fin_deg)
    piv = bpy.data.objects.new(f"TAB_PIVOT_{kk + 1}", None); link_to_scene(piv)
    piv.parent = RK; piv.matrix_parent_inverse = off
    piv.location = (0.0, 0.0, HZ)
    piv.rotation_mode = "XYZ"; piv.rotation_euler = (0.0, 0.0, phi)       # local X runs out along the fin
    for o in obs:
        o.parent = piv
        o.matrix_parent_inverse = Matrix.Rotation(-phi, 4, "Z") @ Matrix.Translation((0.0, 0.0, -HZ))
    TAB_PIV.append((piv, kk, phi))

# flame (two emissive cones, length follows the thrust)
FLAME = bpy.data.objects.new("FLAME", None); link_to_scene(FLAME)
FLAME.parent = RK; FLAME.matrix_parent_inverse = off; FLAME.location = (0, 0, LAY["nozzle_z"])
for nm, r, L, col, st in (("flame_outer", 13.0, 220.0, (1.0, 0.45, 0.08), 45.0), ("flame_core", 7.0, 130.0, (1.0, 0.85, 0.5), 120.0)):
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=r, radius2=1.0, depth=L, location=(0, 0, -L / 2), rotation=(math.pi, 0, 0))
    c = bpy.context.active_object
    c.name = nm
    c.data.materials.append(mat(nm, col, emit=(col, st), alpha=0.85))
    c.parent = FLAME
    for coll in c.users_collection:
        if coll != sc.collection:
            coll.objects.unlink(c)

# canopy (built around the confluence of its lines in the source file)
CH = bpy.data.objects.new("CHUTE", None); link_to_scene(CH)
gores = [o for o in chute_objs if o.name.startswith("canopy_gore")]
zc_low = min((o.matrix_world @ Vector(c)).z for o in gores for c in o.bound_box)
conf_z = zc_low - 0.9 * 2 * 255.0
for o in chute_objs:
    o.parent = CH
    o.matrix_parent_inverse = Matrix.Translation((0, 0, -conf_z))

# shock cord: rocket top -> nose cone -> canopy, curve hooked to three empties
cu = bpy.data.curves.new("cord", "CURVE"); cu.dimensions = "3D"
sp = cu.splines.new("POLY"); sp.points.add(2)
cu.bevel_depth = 1.6
CORD = bpy.data.objects.new("CORD", cu); link_to_scene(CORD)
CORD.data.materials.append(mat("kevlar", (0.85, 0.68, 0.2), 0.8))
for i, tgt in enumerate((TOP, NOSE_EYE, CH)):
    h = CORD.modifiers.new(f"hook{i}", "HOOK")
    h.object = tgt
    h.vertex_indices_set([i])

# smoke trail: the burn-phase path, revealed as the rocket climbs
burn = [f for f in FR if 0.0 <= f["t"] <= META["burn_time"] + 0.4]
sm = bpy.data.curves.new("smoke", "CURVE"); sm.dimensions = "3D"
spl = sm.splines.new("POLY"); spl.points.add(len(burn) - 1)
for i, f in enumerate(burn):
    spl.points[i].co = (f["x"] * 1000, f["y"] * 1000, f["z"] * 1000 + H0 - ZCG - 150.0, 1)
sm.bevel_depth = 70.0
sm.bevel_resolution = 3
SMOKE = bpy.data.objects.new("SMOKE", sm); link_to_scene(SMOKE)
smoke_mat = mat("smoke", (0.85, 0.85, 0.83), rough=1.0, alpha=0.35)
smoke_mat.show_transparent_back = False                      # no sorting artifacts when seen from inside the trail
smoke_mat.use_screen_refraction = False
SMOKE.data.materials.append(smoke_mat)

# --------------------------------------------------------------------------- environment
gnd_mat = bpy.data.materials.new("field"); gnd_mat.use_nodes = True
nt = gnd_mat.node_tree; N = nt.nodes; Lk = nt.links
bsdf = N["Principled BSDF"]; bsdf.inputs["Roughness"].default_value = 0.95
tc = N.new("ShaderNodeTexCoord")
vor = N.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 1.0 / 70000.0
Lk.new(tc.outputs["Object"], vor.inputs["Vector"])
ramp_f = N.new("ShaderNodeValToRGB")
ramp_f.color_ramp.elements[0].color = (0.16, 0.30, 0.07, 1); ramp_f.color_ramp.elements[1].color = (0.42, 0.45, 0.16, 1)
el = ramp_f.color_ramp.elements.new(0.55); el.color = (0.22, 0.36, 0.10, 1)
Lk.new(vor.outputs["Color"], ramp_f.inputs["Fac"])
noi = N.new("ShaderNodeTexNoise"); noi.inputs["Scale"].default_value = 1.0 / 1800.0; noi.inputs["Detail"].default_value = 12
noi.inputs["Roughness"].default_value = 0.65
Lk.new(tc.outputs["Object"], noi.inputs["Vector"])
mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs["Factor"].default_value = 0.85
Lk.new(ramp_f.outputs["Color"], mix.inputs[6]); Lk.new(noi.outputs["Color"], mix.inputs[7])
grad = N.new("ShaderNodeTexGradient"); grad.gradient_type = "SPHERICAL"
mapn = N.new("ShaderNodeMapping"); mapn.inputs["Scale"].default_value = (1 / 16000.0, 1 / 16000.0, 1)
Lk.new(tc.outputs["Object"], mapn.inputs["Vector"]); Lk.new(mapn.outputs["Vector"], grad.inputs["Vector"])
mown = N.new("ShaderNodeMix"); mown.data_type = "RGBA"
mown.inputs[7].default_value = (0.36, 0.52, 0.18, 1)
step = N.new("ShaderNodeMath"); step.operation = "GREATER_THAN"; step.inputs[1].default_value = 0.0005
Lk.new(grad.outputs["Fac"], step.inputs[0])
Lk.new(mix.outputs[2], mown.inputs[6]); Lk.new(step.outputs[0], mown.inputs["Factor"])
sep = N.new("ShaderNodeSeparateXYZ"); Lk.new(tc.outputs["Object"], sep.inputs[0])
dx = N.new("ShaderNodeMath"); dx.operation = "ADD"; dx.inputs[1].default_value = 70000.0
Lk.new(sep.outputs["X"], dx.inputs[0])
adx = N.new("ShaderNodeMath"); adx.operation = "ABSOLUTE"; Lk.new(dx.outputs[0], adx.inputs[0])
trk = N.new("ShaderNodeMath"); trk.operation = "LESS_THAN"; trk.inputs[1].default_value = 2000.0
Lk.new(adx.outputs[0], trk.inputs[0])
track = N.new("ShaderNodeMix"); track.data_type = "RGBA"; track.inputs[7].default_value = (0.45, 0.38, 0.28, 1)
Lk.new(mown.outputs[2], track.inputs[6]); Lk.new(trk.outputs[0], track.inputs["Factor"])
Lk.new(track.outputs[2], bsdf.inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(size=4.0e6, location=(0, 0, 0))
g = bpy.context.active_object; g.name = "field"; g.data.materials.append(gnd_mat)
# mown launch area (lighter, short grass) and a few safety-distance flags so the onboard view has landmarks
flag_mat = mat("flag", (0.95, 0.35, 0.05), 0.6)
for a in range(0, 360, 30):
    fx, fy = 15000 * math.cos(math.radians(a)), 15000 * math.sin(math.radians(a))
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=25, depth=1000, location=(fx, fy, 500))
    bpy.context.active_object.data.materials.append(flag_mat)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(fx + 150, fy, 900))
    o = bpy.context.active_object; o.scale = (300, 20, 200); o.data.materials.append(flag_mat)

# trees, hedges, a track, people and a car (deterministic layout, independent of the flight)
import random
rnd = random.Random(42)
tree_mat = mat("tree", (0.06, 0.18, 0.05), 0.9); trunk_mat = mat("trunk", (0.25, 0.16, 0.08), 0.9)
hedge_mat = mat("hedge", (0.08, 0.22, 0.06), 0.9)
for i in range(140):
    while True:
        x, y = rnd.uniform(-900e3, 900e3), rnd.uniform(-900e3, 900e3)
        if math.hypot(x, y) > 45e3:
            break
    h = rnd.uniform(6e3, 14e3)
    bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=h * 0.32, radius2=0, depth=h * 0.8, location=(x, y, h * 0.6))
    bpy.context.active_object.data.materials.append(tree_mat)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=h * 0.04, depth=h * 0.25, location=(x, y, h * 0.12))
    bpy.context.active_object.data.materials.append(trunk_mat)
for i in range(10):
    horiz = i % 2 == 0
    c = rnd.uniform(-600e3, 600e3)
    if abs(c) < 60e3:
        c += 120e3
    L = rnd.uniform(200e3, 700e3)
    s = rnd.uniform(-300e3, 300e3)
    loc = (s, c, 800) if horiz else (c, s, 800)
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.scale = (L, 1200, 1600) if horiz else (1200, L, 1600)
    o.data.materials.append(hedge_mat)
people = mat("jacket", (0.75, 0.2, 0.1), 0.7)
for (x, y) in ((-26e3, -16e3), (-27.5e3, -15e3), (-25e3, -13.5e3)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=230, depth=1500, location=(x, y, 750))
    bpy.context.active_object.data.materials.append(people)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=120, location=(x, y, 1630))
    bpy.context.active_object.data.materials.append(mat("skin", (0.8, 0.6, 0.45), 0.6))
bpy.ops.mesh.primitive_cube_add(size=1, location=(-60e3, -40e3, 750))
car = bpy.context.active_object; car.scale = (4300, 1800, 1500); car.data.materials.append(mat("car", (0.1, 0.25, 0.6), 0.3, 0.6))

# sky + sun
w = bpy.data.worlds.new("sky"); sc.world = w; w.use_nodes = True
# a simple blue gradient (a physical sky renders almost white near the horizon, where the descending rocket is seen)
wn = w.node_tree.nodes
tco = wn.new("ShaderNodeTexCoord"); sep = wn.new("ShaderNodeSeparateXYZ")
mr = wn.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -0.05; mr.inputs["From Max"].default_value = 0.6
ramp = wn.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].color = (0.48, 0.64, 0.90, 1)          # horizon
ramp.color_ramp.elements[1].color = (0.16, 0.34, 0.78, 1)          # zenith
w.node_tree.links.new(tco.outputs["Generated"], sep.inputs["Vector"])
w.node_tree.links.new(sep.outputs["Z"], mr.inputs["Value"])
w.node_tree.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
w.node_tree.links.new(ramp.outputs["Color"], wn["Background"].inputs["Color"])
wn["Background"].inputs["Strength"].default_value = 1.0
sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 3.5; sun.angle = math.radians(1.0)
sun.shadow_buffer_bias = 0.6                                   # no shadow acne on the tube at grazing angles
so = bpy.data.objects.new("sun", sun); link_to_scene(so)
so.rotation_euler = (math.radians(52), 0, math.radians(210 + 90))

# --------------------------------------------------------------------------- animation
def world_q(fr):
    qb = Quaternion(fr["q"])                                   # body -> world (body x = rocket axis)
    m = qb.to_matrix() @ P_CAD2BODY
    return m.to_quaternion()


def pos_mm(fr):
    return Vector((fr["x"] * 1000.0, fr["y"] * 1000.0, fr["z"] * 1000.0 + H0))


for o in (RK, NOSE, CH):
    o.rotation_mode = "QUATERNION"
t_sep = META.get("t_sep")
nose_sep_pos = None
last_q = None
for k, fr in enumerate(FR, start=1):
    p = pos_mm(fr)
    q = world_q(fr)
    if last_q is not None and q.dot(last_q) < 0:
        q.negate()
    last_q = q.copy()
    RK.location = p; RK.rotation_quaternion = q
    RK.keyframe_insert("location", frame=k); RK.keyframe_insert("rotation_quaternion", frame=k)
    for piv, kk, phi in TAB_PIV:
        piv.rotation_euler = (math.radians(-fr["tabs"][kk]), 0.0, phi)
        piv.keyframe_insert("rotation_euler", frame=k)
    axis = q.to_matrix() @ Vector((0, 0, 1))
    top = p + axis * (LAY["mid_top_z"] - ZCG)
    if not fr["sep"]:
        NOSE.location = p; NOSE.rotation_quaternion = q
        CH.location = top; CH.scale = (0.05, 0.05, 0.05)
        CH.rotation_quaternion = Quaternion()
        nose_sep_pos = None
    else:
        ts = fr["t"] - t_sep
        drift = Vector((math.cos(math.radians(META["wind_to"])), math.sin(math.radians(META["wind_to"])), 0)) * 250.0
        ch_pos = top + Vector((0, 0, 1700.0 * min(1.0, 0.25 + ts / 0.9))) + drift * min(1.0, ts)
        s = 0.12 + 0.88 * fr["chute"]
        CH.location = ch_pos; CH.scale = (s, s, max(s, 0.3))
        sway = Quaternion((1, 0, 0), math.radians(4.0 * math.sin(fr["t"] * 2.1)))
        CH.rotation_quaternion = sway
        t_land = META["events"].get("landing_t")
        if t_land is not None and fr["t"] > t_land:             # after touchdown the canopy settles downwind and collapses
            fl = min(1.0, (fr["t"] - t_land) / 1.6)
            settle = Vector((ch_pos.x, ch_pos.y, 150.0)) + drift * 4.0
            CH.location = ch_pos.lerp(settle, fl)
            CH.scale = (s * (1.0 + 0.25 * fl), s * (1.0 + 0.25 * fl), max(0.05, max(s, 0.3) * (1.0 - fl)))
            CH.rotation_quaternion = sway.slerp(Quaternion(), fl)
        hang = (top + CH.location) * 0.5 + Vector((0, 0, -250))     # the nose hangs on the cord between rocket and canopy
        if nose_sep_pos is None:
            nose_sep_pos = NOSE.location.copy()
        f = min(1.0, ts / 0.7)
        nose_to = hang + Vector((0, 0, 170))
        nose_to.z = max(nose_to.z, 45.0)                            # lies on the grass once everything is down
        NOSE.location = nose_sep_pos.lerp(nose_to, f)
        NOSE.rotation_quaternion = q.slerp(Quaternion((1, 0, 0), math.pi) @ Quaternion((0, 0, 1), ts), f)
    NOSE.keyframe_insert("location", frame=k); NOSE.keyframe_insert("rotation_quaternion", frame=k)
    CH.keyframe_insert("location", frame=k); CH.keyframe_insert("scale", frame=k); CH.keyframe_insert("rotation_quaternion", frame=k)
    vis_chute = fr["sep"] and fr["t"] - t_sep > 0.25
    for o in chute_objs + [CORD]:
        o.hide_render = not (vis_chute or (o is CORD and fr["sep"]))
        o.keyframe_insert("hide_render", frame=k)
    th = fr["thrust"]
    FLAME.scale = (1, 1, max(0.05, min(1.6, th / 22.0)))
    FLAME.keyframe_insert("scale", frame=k)
    FLAME.hide_render = th < 0.5
    FLAME.keyframe_insert("hide_render", frame=k)
    for c in FLAME.children:
        c.hide_render = th < 0.5
        c.keyframe_insert("hide_render", frame=k)
    # smoke: reveal along the path, then fade
    if fr["t"] < 0:
        endf = 0.0
    else:
        endf = min(1.0, max(0.0, fr["t"]) / (META["burn_time"] + 0.4))
    SMOKE.data.bevel_factor_end = max(endf, 0.0001)
    SMOKE.data.keyframe_insert("bevel_factor_end", frame=k)
    a = 0.35 if fr["t"] < META["burn_time"] + 2 else max(0.0, 0.35 * (1 - (fr["t"] - META["burn_time"] - 2) / 8.0))
    smoke_mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = a
    smoke_mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].keyframe_insert("default_value", frame=k)

for o in bpy.data.objects:
    ad = o.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# --------------------------------------------------------------------------- cameras
cam = bpy.data.cameras.new(CAM)
co = bpy.data.objects.new("CAM_" + CAM, cam); link_to_scene(co)
sc.camera = co
cam.sensor_width = 36.0
if CAM == "ground":
    co.location = (-24000.0, -18000.0, 1600.0)
    TRK = bpy.data.objects.new("TRACK", None); link_to_scene(TRK)
    for k, fr in enumerate(FR, start=1):
        p = pos_mm(fr)
        if fr["sep"]:
            ts = fr["t"] - t_sep
            p = p + Vector((0, 0, 900.0 * min(1.0, ts)))
        TRK.location = p
        TRK.keyframe_insert("location", frame=k)
        d = (p - co.location).length / 1000.0
        hf = 3.2 if not fr["sep"] else 3.2 + 2.6 * min(1.0, (fr["t"] - t_sep) / 1.5)
        cam.lens = max(24.0, min(600.0, 20.25 * d / hf))
        cam.keyframe_insert("lens", frame=k)
    tcon = co.constraints.new("TRACK_TO"); tcon.target = TRK
    tcon.track_axis = "TRACK_NEGATIVE_Z"; tcon.up_axis = "UP_Y"
    cam.clip_start = 200.0; cam.clip_end = 3.0e6
else:
    co.parent = RK
    co.matrix_parent_inverse = off
    lx, ly, lz = LAY["camera_lens_xyz"]
    co.location = (lx, ly, lz - 1.0)
    co.rotation_euler = (0, 0, 0)                               # looks along CAD -Z (down the rocket), up = towards the tube
    cam.lens = 9.0
    cam.clip_start = 1.0; cam.clip_end = 1.5e6                 # the body tube is only 1.5 mm from the lens

# --------------------------------------------------------------------------- render
sc.render.engine = "BLENDER_EEVEE"
ee = sc.eevee
ee.taa_render_samples = 4 if DRAFT else 16
ee.use_gtao = CAM == "ground"; ee.gtao_distance = 2000.0      # screen-space AO streaks on the tube 1.5 mm from the onboard lens
ee.use_bloom = True; ee.bloom_intensity = 0.06; ee.bloom_threshold = 1.2
ee.use_soft_shadows = True
ee.shadow_cascade_size = "2048"
sun.shadow_cascade_max_distance = 80000.0
sc.render.resolution_x, sc.render.resolution_y = (640, 360) if DRAFT else (960, 540)
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = os.path.join(OUT, "")
try:
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = float(arg("--exposure", -0.35 if CAM == "ground" else -0.25))
except TypeError:
    pass
os.makedirs(OUT, exist_ok=True)
ONLY = arg("--only")
if ONLY:                                                       # quick look at a few frames
    for k in [int(v) for v in ONLY.split(",")]:
        sc.frame_set(k)
        sc.render.filepath = os.path.join(OUT, f"{k:04d}.png")
        bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
print("done", CAM, len(FR), "frames")
