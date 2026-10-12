"""S5: クロムコア・オービット（グローバル 24.0s〜32.0s, 240f）

チートシート技: オービット / ラックフォーカス / （EffectCraft 側で）フリーズフレーム
終盤 f196〜 でコアが破片に爆散 → S6 のロゴ集合へつながる。
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import common as C  # noqa: E402

a = C.args()
s = C.reset_scene()
C.studio_world()
FRAMES = 240
EXPLODE_START = 196

# --- コア（GN: ノイズ変形＋ビート脈動＋爆散） ---
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6, radius=1.25)
core = bpy.context.object
core.name = "Core"
bpy.ops.object.shade_smooth()
g = C.GN(core, "CoreGN")
ex_sock = g.ng.interface.new_socket("Explode", in_out="INPUT", socket_type="NodeSocketFloat")

t = g.n("GeometryNodeInputSceneTime")
pos = g.n("GeometryNodeInputPosition")
nrm = g.n("GeometryNodeInputNormal")
noise = g.n("ShaderNodeTexNoise")
noise.noise_dimensions = "4D"
noise.inputs["Scale"].default_value = 0.8
noise.inputs["Detail"].default_value = 2.0
g.link((pos, "Position"), (noise, "Vector"))
g.link((g.math("MULTIPLY", (t, "Seconds"), 0.35), 0), (noise, "W"))
# ビート脈動: (1 - fract(2t))^4
beat = g.math("POWER", g.math("SUBTRACT", 1.0, g.math("FRACT", g.math("MULTIPLY", (t, "Seconds"), 2.0))), 4.0)
amp = g.math("MULTIPLY_ADD", (noise, "Factor"), 1.1, -0.5)  # -0.5..0.6
disp = g.math("ADD", g.math("MULTIPLY", amp, 0.28), g.math("MULTIPLY", beat, 0.07))
off = g.vmath("SCALE", (nrm, "Normal"), scale=(disp, 0))
setp = g.n("GeometryNodeSetPosition")
g.link((g.inp, 0), (setp, "Geometry"))
g.link((off, "Vector"), (setp, "Offset"))

chrome = bpy.data.materials.new("Chrome")
chrome.use_nodes = True
pb = chrome.node_tree.nodes["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.9, 0.9, 0.95, 1)
pb.inputs["Metallic"].default_value = 1.0
pb.inputs["Roughness"].default_value = 0.06
pb.inputs["Thin Film Thickness"].default_value = 520.0
pb.inputs["Thin Film IOR"].default_value = 1.6
sm = g.n("GeometryNodeSetMaterial")
sm.inputs["Material"].default_value = chrome
g.link((setp, "Geometry"), (sm, "Geometry"))

# 破片
dist = g.n("GeometryNodeDistributePointsOnFaces")
dist.inputs["Density"].default_value = 1400.0
g.link((setp, "Geometry"), (dist, "Mesh"))
shard = g.n("GeometryNodeMeshCube")
shard.inputs["Size"].default_value = (0.08, 0.08, 0.08)
si = g.n("GeometryNodeInstanceOnPoints")
g.link((dist, "Points"), (si, "Points"))
g.link((shard, "Mesh"), (si, "Instance"))
g.link(g.rand("FLOAT_VECTOR", (0, 0, 0), (6.3, 6.3, 6.3), 2), (si, "Rotation"))
g.link(g.rand("FLOAT_VECTOR", (0.4, 0.4, 0.4), (2.2, 1.6, 2.6), 4), (si, "Scale"))
speed = g.rand("FLOAT", 1.5, 9.0, 9)
ex = (g.inp, "Explode")
# 爆散オフセット = 法線 * E * speed + 乱方向 * E * 2 ＋ 少し上昇
mag = g.math("MULTIPLY", ex, speed)
o1 = g.vmath("SCALE", (dist, "Normal"), scale=(mag, 0))
o2 = g.vmath("SCALE", g.rand("FLOAT_VECTOR", (-1, -1, -1), (1, 1, 1), 6), scale=g.math("MULTIPLY", ex, 2.0))
otot = g.vmath("ADD", (o1, "Vector"), (o2, "Vector"))
tr = g.n("GeometryNodeTranslateInstances")
tr.inputs["Local Space"].default_value = False
g.link((si, "Instances"), (tr, "Instances"))
g.link((otot, "Vector"), (tr, "Translation"))
# 爆散中に回転
rr = g.n("GeometryNodeRotateInstances")
g.link((tr, "Instances"), (rr, "Instances"))
g.link((g.vmath("SCALE", g.rand("FLOAT_VECTOR", (-3, -3, -3), (3, 3, 3), 8), scale=ex), "Vector"), (rr, "Rotation"))
heat = g.n("GeometryNodeStoreNamedAttribute")
heat.data_type = "FLOAT"
heat.domain = "INSTANCE"
heat.inputs["Name"].default_value = "glow"
g.link((rr, "Instances"), (heat, "Geometry"))
# 発光は爆散初期にピーク → 冷めていく
hv = g.math("MULTIPLY", g.math("POWER", g.rand("FLOAT", 0.0, 1.0, 12), 2.0),
            g.math("EXPONENT", g.math("MULTIPLY", ex, -0.9)))
g.link((hv, 0), (heat, "Value"))
shard_mat = C.attr_emission_mat("Shard", "glow", (1.0, 0.35, 0.05, 1), (0.6, 0.95, 1.0, 1), 60.0,
                                base=(0.8, 0.8, 0.85, 1), roughness=0.1, metallic=1.0)
ssm = g.n("GeometryNodeSetMaterial")
ssm.inputs["Material"].default_value = shard_mat
g.link((heat, "Geometry"), (ssm, "Geometry"))

sw = g.n("GeometryNodeSwitch")
sw.input_type = "GEOMETRY"
cond = g.math("GREATER_THAN", ex, 0.001)
g.link((cond, 0), (sw, "Switch"))
g.link((sm, "Geometry"), (sw, "False"))
g.link((ssm, "Geometry"), (sw, "True"))
g.link((sw, "Output"), (g.out, 0))

ident = ex_sock.identifier
for f, v in ((1, 0.0), (EXPLODE_START, 0.0), (EXPLODE_START + 1, 0.01), (FRAMES, 3.2)):
    sockp = getattr(g.mod.properties.inputs, ident)  # Blender 5.x の GN 入力 API
    sockp.value = v
    sockp.keyframe_insert("value", frame=f)
for fc in C.fcurves(core.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
    # 爆散は初速が速く減速（EXPO ease out）
    fc.keyframe_points[-1].interpolation = "LINEAR"
    fc.keyframe_points[-2].interpolation = "EXPO"
    fc.keyframe_points[-2].easing = "EASE_OUT"

# --- 粒子リング ×3 ---
dot_mats = [C.emission_mat("DotC", (0.1, 0.7, 1.0, 1), 18), C.emission_mat("DotM", (1.0, 0.1, 0.45, 1), 18),
            C.emission_mat("DotW", (1.0, 0.9, 0.8, 1), 20)]
ring_specs = [(2.2, 500, (18, 0, 0), 1, 0), (2.8, 700, (-12, 25, 0), -1, 1), (3.5, 350, (70, 10, 0), 1, 2)]
for i, (rad, cnt, tilt, direction, mi) in enumerate(ring_specs):
    ro = bpy.data.objects.new(f"Ring{i}", bpy.data.meshes.new(f"RingBase{i}"))
    s.collection.objects.link(ro)
    ro.rotation_euler = tuple(math.radians(v) for v in tilt)
    rg = C.GN(ro, f"RingGN{i}")
    circ = rg.n("GeometryNodeCurvePrimitiveCircle")
    circ.inputs["Resolution"].default_value = cnt
    circ.inputs["Radius"].default_value = rad
    cp = rg.n("GeometryNodeCurveToPoints")
    cp.mode = "EVALUATED"
    rg.link((circ, "Curve"), (cp, "Curve"))
    jit = rg.n("GeometryNodeSetPosition")
    rg.link((cp, "Points"), (jit, "Geometry"))
    rg.link(rg.rand("FLOAT_VECTOR", (-0.35, -0.35, -0.12), (0.35, 0.35, 0.12), i), (jit, "Offset"))
    ico = rg.n("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = 0.007
    ico.inputs["Subdivisions"].default_value = 1
    ip = rg.n("GeometryNodeInstanceOnPoints")
    rg.link((jit, "Geometry"), (ip, "Points"))
    rg.link((ico, "Mesh"), (ip, "Instance"))
    rg.link(rg.rand("FLOAT", 0.3, 1.5, 20 + i), (ip, "Scale"))
    rm = rg.n("GeometryNodeSetMaterial")
    rm.inputs["Material"].default_value = dot_mats[mi]
    rg.link((ip, "Instances"), (rm, "Geometry"))
    rg.link((rm, "Geometry"), (rg.out, 0))
    # 自転（リニア）
    ro.rotation_mode = "XYZ"
    base_z = ro.rotation_euler[2]
    ro.rotation_euler[2] = base_z
    ro.keyframe_insert("rotation_euler", index=2, frame=1)
    ro.rotation_euler[2] = base_z + direction * math.radians(160 - i * 30)
    ro.keyframe_insert("rotation_euler", index=2, frame=FRAMES)
    C.set_interp(ro, "LINEAR")

# --- スタジオライト（クロムに映り込む発光ストリップ） ---
strip_mat = C.emission_mat("Strip", (1, 1, 1, 1), 14)
warm_mat = C.emission_mat("StripWarm", (1.0, 0.4, 0.15, 1), 10)
cyan_mat = C.emission_mat("StripCyan", (0.1, 0.6, 1.0, 1), 10)
for ang, h, mat, w in ((0, 4, strip_mat, 0.6), (95, 1, cyan_mat, 0.4), (200, -2, warm_mat, 0.5), (290, 6, strip_mat, 0.3)):
    bpy.ops.mesh.primitive_plane_add(size=1)
    st = bpy.context.object
    r = 12
    st.location = (r * math.cos(math.radians(ang)), r * math.sin(math.radians(ang)), h)
    st.scale = (w * 4, 22, 1)
    C.look_at(st, (0, 0, h))
    st.rotation_euler.rotate_axis("X", math.radians(180))
    st.data.materials.append(mat)
    st.visible_camera = False
C.area_light("Top", (0, 0, 8), (0, 0, 0), 5, 800, (0.8, 0.9, 1.0))
C.area_light("RimM", (-5, 5, 1), (math.radians(90), 0, math.radians(-135)), 3, 900, (1.0, 0.2, 0.5))

# --- カメラ: オービット＋ラックフォーカス ---
pivot = C.empty("Pivot")
cam = C.camera("Cam", lens=60, loc=(0, -9.0, 0.0), clip_end=200)
cam.parent = pivot
C.look_at(cam, (0, 0, 0))
pivot.keyframe_insert("rotation_euler", index=2, frame=1)
pivot.rotation_euler[2] = math.radians(270)
pivot.keyframe_insert("rotation_euler", index=2, frame=FRAMES)
pivot.rotation_euler[0] = math.radians(-6)
pivot.keyframe_insert("rotation_euler", index=0, frame=1)
pivot.rotation_euler[0] = math.radians(14)
pivot.keyframe_insert("rotation_euler", index=0, frame=FRAMES)
for fc in C.fcurves(pivot.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = "SINE"
        kp.easing = "EASE_IN_OUT"
# 手前を横切る粒子（ラックフォーカスの前景）
fg = bpy.data.objects.new("FG", bpy.data.meshes.new("FGBase"))
s.collection.objects.link(fg)
fg.parent = cam
fg.location = (0, 0, -2.4)
fgg = C.GN(fg, "FGGN")
gp = fgg.n("GeometryNodeMeshGrid")
gp.inputs["Size X"].default_value = 3.0
gp.inputs["Size Y"].default_value = 1.8
gp.inputs["Vertices X"].default_value = 9
gp.inputs["Vertices Y"].default_value = 6
gpts = fgg.n("GeometryNodeMeshToPoints")
fgg.link((gp, "Mesh"), (gpts, "Mesh"))
gj = fgg.n("GeometryNodeSetPosition")
fgg.link((gpts, "Points"), (gj, "Geometry"))
fgg.link(fgg.rand("FLOAT_VECTOR", (-0.6, -0.4, -0.8), (0.6, 0.4, 0.6), 3), (gj, "Offset"))
gico = fgg.n("GeometryNodeMeshIcoSphere")
gico.inputs["Radius"].default_value = 0.007
gi = fgg.n("GeometryNodeInstanceOnPoints")
fgg.link((gj, "Geometry"), (gi, "Points"))
fgg.link((gico, "Mesh"), (gi, "Instance"))
gsm = fgg.n("GeometryNodeSetMaterial")
gsm.inputs["Material"].default_value = dot_mats[2]
fgg.link((gi, "Instances"), (gsm, "Geometry"))
fgg.link((gsm, "Geometry"), (fgg.out, 0))

cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 1.2
for f, d in ((1, 2.4), (30, 2.4), (58, 9.0), (FRAMES, 9.0)):
    cam.data.dof.focus_distance = d
    cam.data.keyframe_insert("dof.focus_distance", frame=f)
# 爆散時にわずかにズームアウト
for f, l in ((1, 60), (EXPLODE_START, 60), (FRAMES, 38)):
    cam.data.lens = l
    cam.data.keyframe_insert("lens", frame=f)

C.compositor_bloom(s, threshold=1.0, strength=0.9, size=0.7, streak=False, lens_disp=0.015)
C.render(s, "s5", a, 1, FRAMES)
