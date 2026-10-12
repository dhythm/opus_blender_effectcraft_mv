"""S6: ロゴ集合（グローバル 32.0s〜40.0s, 240f）

S5 の爆散破片が飛び込み、ボクセルが左から順に「OPUS 5.5」へ集まる → f61（34.0s）で実体化。
チートシート技: クレーンアップ / （EffectCraft 側で）ライトスイープ・L カット
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import common as C  # noqa: E402

a = C.args()
s = C.reset_scene()
C.studio_world(horizon=(0.15, 0.25, 0.5))
FRAMES = 240
SOLID_AT = 61

# --- 3D テキスト ---
font = bpy.data.fonts.load("/System/Library/Fonts/Avenir Next.ttc")
td = bpy.data.curves.new("Logo", "FONT")
td.body = "OPUS 5.5"
td.font = font
td.size = 1.6
td.extrude = 0.16
td.bevel_depth = 0.025
td.bevel_resolution = 3
td.align_x = "CENTER"
td.align_y = "CENTER"
td.space_character = 1.05
logo = bpy.data.objects.new("Logo", td)
s.collection.objects.link(logo)
logo.rotation_euler = (math.radians(90), 0, 0)
logo.location = (0, 0, 1.0)
bpy.context.view_layer.objects.active = logo
logo.select_set(True)
bpy.ops.object.convert(target="MESH")
logo = bpy.context.object

logo_mat = bpy.data.materials.new("LogoMat")
logo_mat.use_nodes = True
pb = logo_mat.node_tree.nodes["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.75, 0.78, 0.85, 1)
pb.inputs["Metallic"].default_value = 1.0
pb.inputs["Roughness"].default_value = 0.12
pb.inputs["Thin Film Thickness"].default_value = 380.0
logo.data.materials.append(logo_mat)

# --- GN: ボクセル集合 → 実体化 ---
g = C.GN(logo, "LogoGN")
asm = g.ng.interface.new_socket("Assemble", in_out="INPUT", socket_type="NodeSocketFloat")
dist = g.n("GeometryNodeDistributePointsOnFaces")
dist.inputs["Density"].default_value = 2600.0
g.link((g.inp, 0), (dist, "Mesh"))
pos = g.n("GeometryNodeInputPosition")
sep = g.n("ShaderNodeSeparateXYZ")
g.link((pos, "Position"), (sep, "Vector"))
# 遅延 = 左→右 (x: -4..4 → 0..1) * 0.9 + 乱数 * 0.25
dl = g.n("ShaderNodeMapRange")
dl.inputs["From Min"].default_value = -4.0
dl.inputs["From Max"].default_value = 4.0
dl.inputs["To Max"].default_value = 0.9
g.link((sep, "X"), (dl, "Value"))
delay = g.math("ADD", (dl, "Result"), g.math("MULTIPLY", g.rand("FLOAT", 0.0, 1.0, 3), 0.25))
# 各点の進行度 f = clamp((A - delay) / 0.45) → smoothstep
fr = g.math("DIVIDE", g.math("SUBTRACT", (g.inp, "Assemble"), delay), 0.45)
ease = g.math("MINIMUM", g.math("MAXIMUM", fr, 0.0), 1.0)
inv = g.math("SUBTRACT", 1.0, ease)
inv3 = g.math("POWER", inv, 3.0)  # ease-out cubic の残差
# 散らばり位置: 手前上方から飛び込む（乱方向 * 9 + 手前 -Y 6）
scat = g.vmath("ADD", g.vmath("SCALE", g.rand("FLOAT_VECTOR", (-1, -1.6, -0.6), (1, 0.2, 1), 5), scale=9.0),
               (0, -4.0, 2.0))
off = g.vmath("SCALE", (scat, "Vector"), scale=inv3)
vox = g.n("GeometryNodeMeshCube")
vox.inputs["Size"].default_value = (0.045, 0.045, 0.045)
vi = g.n("GeometryNodeInstanceOnPoints")
g.link((dist, "Points"), (vi, "Points"))
g.link((vox, "Mesh"), (vi, "Instance"))
g.link((dist, "Rotation"), (vi, "Rotation"))
vt = g.n("GeometryNodeTranslateInstances")
vt.inputs["Local Space"].default_value = False
g.link((vi, "Instances"), (vt, "Instances"))
g.link((off, "Vector"), (vt, "Translation"))
vr = g.n("GeometryNodeRotateInstances")
g.link((vt, "Instances"), (vr, "Instances"))
g.link((g.vmath("SCALE", g.rand("FLOAT_VECTOR", (-6, -6, -6), (6, 6, 6), 8), scale=inv3), "Vector"), (vr, "Rotation"))
# 到着の瞬間に光る: glow = 4 f (1-f) 的なパルス
gl = g.math("MULTIPLY", g.math("MULTIPLY", ease, inv), 4.0)
gl = g.math("ADD", gl, g.math("MULTIPLY", inv, 0.12))
vs = g.n("GeometryNodeStoreNamedAttribute")
vs.data_type = "FLOAT"
vs.domain = "INSTANCE"
vs.inputs["Name"].default_value = "glow"
g.link((vr, "Instances"), (vs, "Geometry"))
g.link((gl, 0), (vs, "Value"))
vmat = C.attr_emission_mat("Voxel", "glow", (0.1, 0.6, 1.0, 1), (1.0, 0.95, 0.9, 1), 7.0,
                           base=(0.7, 0.72, 0.8, 1), roughness=0.15, metallic=1.0)
vsm = g.n("GeometryNodeSetMaterial")
vsm.inputs["Material"].default_value = vmat
g.link((vs, "Geometry"), (vsm, "Geometry"))

sw = g.n("GeometryNodeSwitch")
sw.input_type = "GEOMETRY"
g.link((g.math("GREATER_THAN", (g.inp, "Assemble"), 1.62), 0), (sw, "Switch"))
g.link((vsm, "Geometry"), (sw, "False"))
g.link((g.inp, 0), (sw, "True"))
g.link((sw, "Output"), (g.out, 0))

sockp = getattr(g.mod.properties.inputs, asm.identifier)
for f, v in ((1, 0.0), (SOLID_AT - 1, 1.6), (SOLID_AT, 1.7), (FRAMES, 1.7)):
    sockp.value = v
    sockp.keyframe_insert("value", frame=f)
for fc in C.fcurves(logo.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"

# --- 反射床 ---
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
floor = bpy.context.object
floor.data.materials.append(C.principled_mat("Floor", (0.004, 0.004, 0.005, 1), 0.0, 0.14))

# --- ライト: キー / リム / スイープバー ---
C.area_light("Key", (-4, -6, 5), (math.radians(55), 0, math.radians(-35)), 4, 600, (0.85, 0.9, 1.0))
C.area_light("RimC", (5, 3, 6), (math.radians(45), 0, math.radians(125)), 0.6, 900, (0.1, 0.6, 1.0))
C.area_light("RimM", (-5, 3, 6), (math.radians(45), 0, math.radians(-125)), 0.6, 900, (1.0, 0.15, 0.45))
# 実体化後、文字の表面を横切る光のバー（映り込み用の発光板）
bpy.ops.mesh.primitive_plane_add(size=1)
bar = bpy.context.object
bar.scale = (0.35, 6, 1)
bar.rotation_euler = (math.radians(90), math.radians(18), 0)
bar.data.materials.append(C.emission_mat("Bar", (1, 1, 1, 1), 40))
bar.visible_camera = False
for f, x in ((1, -14), (SOLID_AT + 6, -14), (SOLID_AT + 70, 14), (FRAMES, 14)):
    bar.location = (x, -4.5, 1.2)
    bar.keyframe_insert("location", frame=f)

# --- カメラ: 低い位置から見上げ → クレーンアップで正面へ、ゆっくり寄る ---
cam = C.camera("Cam", lens=40, loc=(0, -9, 0.15), clip_end=300)
tgt = C.empty("Tgt", (0, 0, 1.0))
C.track_to(cam, tgt)
for f, loc, ln in ((1, (1.2, -10.5, 0.12), 32), (SOLID_AT, (0.4, -9.5, 0.6), 36), (FRAMES, (0.0, -8.6, 1.35), 42)):
    cam.location = loc
    cam.keyframe_insert("location", frame=f)
    cam.data.lens = ln
    cam.data.keyframe_insert("lens", frame=f)
for idb in (cam, cam.data):
    for fc in C.fcurves(idb.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "SINE"
            kp.easing = "EASE_IN_OUT"
cam.data.dof.use_dof = True
cam.data.dof.focus_object = tgt
cam.data.dof.aperture_fstop = 2.0

C.compositor_bloom(s, threshold=0.9, strength=0.9, size=0.75, streak=True, lens_disp=0.012)
C.render(s, "s6", a, 1, FRAMES)
