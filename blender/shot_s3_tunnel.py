"""S3: FPV トンネル（グローバル 10.0s〜16.0s, 180f）

チートシート技: ホイップパン(入り) / FPV / スピードランプ / ダッチアングル / マッチカット(出口のポータル→S4 の円)
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import common as C  # noqa: E402

a = C.args()
s = C.reset_scene()
C.world(color=(0.0005, 0.0008, 0.002), strength=1.0, fog_density=0.0006, fog_color=(0.6, 0.7, 1.0))
FRAMES = 180

# --- 飛行パス（ゆるい S 字） ---
cd = bpy.data.curves.new("Path", "CURVE")
cd.dimensions = "3D"
cd.path_duration = 1000
sp = cd.splines.new("BEZIER")
N = 11
sp.bezier_points.add(N - 1)
for i, bp in enumerate(sp.bezier_points):
    y = i * 45.0
    bp.co = (16 * math.sin(y / 70.0), y, 5 * math.sin(y / 110.0))
    bp.handle_left_type = bp.handle_right_type = "AUTO"
path = bpy.data.objects.new("Path", cd)
s.collection.objects.link(path)

# --- GN: リング・レール・デブリ ---
holder = bpy.data.objects.new("Tunnel", bpy.data.meshes.new("TunnelBase"))
s.collection.objects.link(holder)
g = C.GN(holder, "TunnelGN")
oi = g.n("GeometryNodeObjectInfo")
oi.inputs["Object"].default_value = path
oi.transform_space = "RELATIVE"

t = g.n("GeometryNodeInputSceneTime")

# リング
rs = g.n("GeometryNodeResampleCurve")
rs.inputs["Count"].default_value = 120
g.link((oi, "Geometry"), (rs, "Curve"))
cpts = g.n("GeometryNodeCurveToPoints")
cpts.mode = "EVALUATED"
g.link((rs, "Curve"), (cpts, "Curve"))

ring_c = g.n("GeometryNodeCurvePrimitiveCircle")
ring_c.inputs["Resolution"].default_value = 6
ring_c.inputs["Radius"].default_value = 5.0
prof = g.n("GeometryNodeCurvePrimitiveQuadrilateral")
prof.inputs["Width"].default_value = 0.18
prof.inputs["Height"].default_value = 0.7
ring_m = g.n("GeometryNodeCurveToMesh")
g.link((ring_c, "Curve"), (ring_m, "Curve"))
g.link((prof, "Curve"), (ring_m, "Profile Curve"))

inst = g.n("GeometryNodeInstanceOnPoints")
g.link((cpts, "Points"), (inst, "Points"))
g.link((ring_m, "Mesh"), (inst, "Instance"))
align = g.n("FunctionNodeAlignRotationToVector")
align.axis = "Z"
g.link((cpts, "Tangent"), (align, "Vector"))
g.link((align, "Rotation"), (inst, "Rotation"))

# 各リングを接線軸まわりにねじる（index に比例 → らせん状の見え方）
idx = g.n("GeometryNodeInputIndex")
tw = g.n("ShaderNodeCombineXYZ")
g.link((g.math("MULTIPLY", (idx, "Index"), 0.13), 0), (tw, "Z"))
rot = g.n("GeometryNodeRotateInstances")
rot.inputs["Local Space"].default_value = True
g.link((inst, "Instances"), (rot, "Instances"))
g.link((tw, "Vector"), (rot, "Rotation"))
# CurveToPoints の回転は X 軸が接線方向なので、リング平面を接線に直交させるため Y 軸 90°
fix = g.n("GeometryNodeRotateInstances")
fix.inputs["Local Space"].default_value = True
fix.inputs["Rotation"].default_value = (0, 0, 0)
g.link((rot, "Instances"), (fix, "Instances"))

# 発光：ビート(2Hz)に合わせて光のパルスが奥へ走る
arg = g.math("SUBTRACT", g.math("MULTIPLY", (idx, "Index"), 0.35), g.math("MULTIPLY", (t, "Seconds"), 4 * math.pi))
pulse = g.math("POWER", g.math("MULTIPLY_ADD", g.math("COSINE", arg), 0.5, 0.5), 10.0)
glow = g.math("ADD", pulse, 0.025)
st = g.n("GeometryNodeStoreNamedAttribute")
st.data_type = "FLOAT"
st.domain = "INSTANCE"
st.inputs["Name"].default_value = "glow"
g.link((fix, "Instances"), (st, "Geometry"))
g.link((glow, 0), (st, "Value"))
# 色: 4 本に 1 本マゼンタ
hue = g.math("FLOORED_MODULO", (idx, "Index"), 4.0)
hue = g.math("LESS_THAN", hue, 0.5)
st2 = g.n("GeometryNodeStoreNamedAttribute")
st2.data_type = "FLOAT"
st2.domain = "INSTANCE"
st2.inputs["Name"].default_value = "hue"
g.link((st, "Geometry"), (st2, "Geometry"))
g.link((hue, 0), (st2, "Value"))

ring_mat = bpy.data.materials.new("Ring")
ring_mat.use_nodes = True
nt = ring_mat.node_tree
p = nt.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.01, 0.01, 0.012, 1)
p.inputs["Metallic"].default_value = 0.8
p.inputs["Roughness"].default_value = 0.25
ga = nt.nodes.new("ShaderNodeAttribute"); ga.attribute_type = "INSTANCER"; ga.attribute_name = "glow"
ha = nt.nodes.new("ShaderNodeAttribute"); ha.attribute_type = "INSTANCER"; ha.attribute_name = "hue"
mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
mix.inputs["A"].default_value = (0.05, 0.6, 1.0, 1)
mix.inputs["B"].default_value = (1.0, 0.08, 0.4, 1)
nt.links.new(ha.outputs["Fac"], mix.inputs["Factor"])
nt.links.new(mix.outputs["Result"], p.inputs["Emission Color"])
em = nt.nodes.new("ShaderNodeMath"); em.operation = "MULTIPLY"; em.inputs[1].default_value = 60.0
nt.links.new(ga.outputs["Fac"], em.inputs[0])
nt.links.new(em.outputs[0], p.inputs["Emission Strength"])
sm = g.n("GeometryNodeSetMaterial")
sm.inputs["Material"].default_value = ring_mat
g.link((st2, "Geometry"), (sm, "Geometry"))

# レール：パスを法線/従法線方向にオフセットした 4 本の光の線
rails = g.n("GeometryNodeJoinGeometry")
tan = g.n("GeometryNodeInputTangent")
nrm = g.n("GeometryNodeInputNormal")
bin_ = g.vmath("CROSS_PRODUCT", (tan, "Tangent"), (nrm, "Normal"))
rail_prof = g.n("GeometryNodeCurvePrimitiveCircle")
rail_prof.inputs["Resolution"].default_value = 6
rail_prof.inputs["Radius"].default_value = 0.02
rs2 = g.n("GeometryNodeResampleCurve")
rs2.inputs["Count"].default_value = 400
g.link((oi, "Geometry"), (rs2, "Curve"))
for vec, sc in (((nrm, "Normal"), 4.4), ((nrm, "Normal"), -4.4), ((bin_, "Vector"), 4.4), ((bin_, "Vector"), -4.4)):
    off = g.vmath("SCALE", vec, scale=sc)
    spn = g.n("GeometryNodeSetPosition")
    g.link((rs2, "Curve"), (spn, "Geometry"))
    g.link((off, "Vector"), (spn, "Offset"))
    cm = g.n("GeometryNodeCurveToMesh")
    g.link((spn, "Geometry"), (cm, "Curve"))
    g.link((rail_prof, "Curve"), (cm, "Profile Curve"))
    g.link((cm, "Mesh"), (rails, "Geometry"))
rail_mat = C.emission_mat("Rail", (0.75, 0.9, 1.0, 1), 10)
rsm = g.n("GeometryNodeSetMaterial")
rsm.inputs["Material"].default_value = rail_mat
g.link((rails, "Geometry"), (rsm, "Geometry"))

# デブリ：パス周辺に浮かぶ金属片
rs3 = g.n("GeometryNodeResampleCurve")
rs3.inputs["Count"].default_value = 2500
g.link((oi, "Geometry"), (rs3, "Curve"))
dp = g.n("GeometryNodeCurveToPoints")
dp.mode = "EVALUATED"
g.link((rs3, "Curve"), (dp, "Curve"))
rnd_dir = g.rand("FLOAT_VECTOR", (-1, -1, -1), (1, 1, 1), 1)
dirn = g.vmath("NORMALIZE", rnd_dir)
rnd_r = g.rand("FLOAT", 7.0, 22.0, 3)
doff = g.vmath("SCALE", (dirn, "Vector"), scale=rnd_r)
dsp = g.n("GeometryNodeSetPosition")
g.link((dp, "Points"), (dsp, "Geometry"))
g.link((doff, "Vector"), (dsp, "Offset"))
dcube = g.n("GeometryNodeMeshCube")
dcube.inputs["Size"].default_value = (1, 1, 1)
dinst = g.n("GeometryNodeInstanceOnPoints")
g.link((dsp, "Geometry"), (dinst, "Points"))
g.link((dcube, "Mesh"), (dinst, "Instance"))
g.link(g.rand("FLOAT_VECTOR", (0, 0, 0), (6.3, 6.3, 6.3), 7), (dinst, "Rotation"))
g.link(g.rand("FLOAT_VECTOR", (0.05, 0.05, 0.05), (0.5, 0.25, 0.9), 11), (dinst, "Scale"))
# 1 割だけ発光させる
dglow = g.math("POWER", g.rand("FLOAT", 0.0, 1.0, 5), 12.0)
dst = g.n("GeometryNodeStoreNamedAttribute")
dst.data_type = "FLOAT"
dst.domain = "INSTANCE"
dst.inputs["Name"].default_value = "glow"
g.link((dinst, "Instances"), (dst, "Geometry"))
g.link((dglow, 0), (dst, "Value"))
deb_mat = C.attr_emission_mat("Debris", "glow", (1.0, 0.4, 0.05, 1), (0.6, 0.9, 1.0, 1), 30.0,
                              base=(0.02, 0.02, 0.025, 1), roughness=0.3, metallic=0.9)
dsm = g.n("GeometryNodeSetMaterial")
dsm.inputs["Material"].default_value = deb_mat
g.link((dst, "Geometry"), (dsm, "Geometry"))

join = g.n("GeometryNodeJoinGeometry")
for node in (sm, rsm, dsm):
    g.link((node, "Geometry"), (join, "Geometry"))
g.link((join, "Geometry"), (g.out, 0))

# --- 出口のポータル（S4 の白い円へマッチカット） ---
PORTAL_AT = 0.86
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=3.2, fill_type="NGON")
portal = bpy.context.object
portal.data.materials.append(C.emission_mat("Portal", (1, 1, 1, 1), 60))
fp = portal.constraints.new("FOLLOW_PATH")
fp.target = path
fp.use_curve_follow = True
fp.use_fixed_location = True
fp.offset_factor = PORTAL_AT
fp.forward_axis = "FORWARD_Y"
fp.up_axis = "UP_Z"
portal.rotation_euler = (math.radians(90), 0, 0)

# --- ライト（デブリの金属にハイライトを入れる） ---
C.area_light("Key", (0, 150, 60), (math.radians(-30), 0, 0), 40, 4000, (0.6, 0.75, 1.0))
C.area_light("Warm", (30, 260, -20), (math.radians(80), 0, math.radians(120)), 40, 3000, (1.0, 0.35, 0.15))

# --- カメラリグ: Follow Path の空 → 子にカメラ（ロール/ヨーを独立に付ける） ---
rig = C.empty("Rig")
fpc = rig.constraints.new("FOLLOW_PATH")
fpc.target = path
fpc.use_curve_follow = True
fpc.use_fixed_location = True
fpc.forward_axis = "FORWARD_Y"
fpc.up_axis = "UP_Z"
# rig(+Y=進行方向) → head(ヨー=Z回転, ロール=Y回転) → cam(X=90°で +Y を向く)
head = C.empty("Head")
head.parent = rig
cam = C.camera("Cam", lens=20, loc=(0, 0, 0), clip_end=800)
cam.parent = head
cam.rotation_euler = (math.radians(90), 0, 0)
cam.data.dof.use_dof = False

# スピードランプ：速い → スロー(ダッチ) → 超高速でポータルへ
ramp = [(1, 0.0), (60, 0.30), (78, 0.40), (88, 0.415), (128, 0.445), (140, 0.48), (172, 0.84), (180, 0.885)]
for f, v in ramp:
    fpc.offset_factor = v
    fpc.keyframe_insert("offset_factor", frame=f)
for fc in C.fcurves(rig.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = "BEZIER"
        kp.handle_left_type = kp.handle_right_type = "AUTO"

# カメラのローカル回転: 前方 = -Z を +Y へ向ける基本姿勢 (X=90°)
# ホイップパン（f1→f9 で 75° からヨーが戻る）／スロー区間でダッチアングル 28°
yaw_keys = [(1, 75), (9, -4), (14, 0), (180, 0)]
roll_keys = [(1, 0), (70, 0), (95, 28), (130, 22), (150, -8), (180, 0)]
for f, yv in yaw_keys:
    head.rotation_euler[2] = math.radians(yv)
    head.keyframe_insert("rotation_euler", index=2, frame=f)
for f, rv in roll_keys:
    head.rotation_euler[1] = math.radians(rv)
    head.keyframe_insert("rotation_euler", index=1, frame=f)
# スロー区間は少しズームイン、最後は広角で疾走感
for f, l in ((1, 20), (80, 20), (110, 32), (138, 30), (165, 14), (180, 12)):
    cam.data.lens = l
    cam.data.keyframe_insert("lens", frame=f)

s.render.motion_blur_shutter = 0.8
C.compositor_bloom(s, threshold=0.8, strength=1.1, size=0.8, streak=True, lens_disp=0.02)
C.render(s, "s3", a, 1, FRAMES)
