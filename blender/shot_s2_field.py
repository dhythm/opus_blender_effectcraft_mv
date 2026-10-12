"""S2: 光柱フィールド＋モノリス / ドリーズーム（グローバル 4.0s〜10.0s, 180f）

GN で約 2 万本の柱を並べ、120BPM（2Hz）で中心から波紋を出す。
カメラは距離 6m・18mm から 30m・90mm へ移動し、被写体サイズを保ったまま背景だけを圧縮する。
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import common as C  # noqa: E402

a = C.args()
s = C.reset_scene()
C.world(color=(0.001, 0.0015, 0.004), strength=1.0, fog_density=0.0035, fog_color=(0.5, 0.7, 1.0))

FRAMES = 180

# --- 地面（反射） ---
bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
ground = bpy.context.object
ground.data.materials.append(C.principled_mat("Ground", (0.006, 0.006, 0.008, 1), 0.0, 0.12))

# --- 柱フィールド（GN） ---
mesh = bpy.data.meshes.new("FieldBase")
field = bpy.data.objects.new("Field", mesh)
s.collection.objects.link(field)
g = C.GN(field, "FieldGN")
grid = g.n("GeometryNodeMeshGrid")
grid.inputs["Size X"].default_value = 90
grid.inputs["Size Y"].default_value = 90
grid.inputs["Vertices X"].default_value = 150
grid.inputs["Vertices Y"].default_value = 150
pts = g.n("GeometryNodeMeshToPoints")
g.link((grid, "Mesh"), (pts, "Mesh"))

cube = g.n("GeometryNodeMeshCube")
cube.inputs["Size"].default_value = (0.42, 0.42, 1.0)
# 底面を原点に合わせる
shift = g.n("GeometryNodeTransform")
shift.inputs["Translation"].default_value = (0, 0, 0.5)
g.link((cube, "Mesh"), (shift, "Geometry"))
# 立方体のローカル Z(0..1) を保存 → シェーダーで上端マスクに使う
lzs = g.n("GeometryNodeStoreNamedAttribute")
lzs.data_type = "FLOAT"
lzs.domain = "POINT"
lzs.inputs["Name"].default_value = "lz"
g.link((shift, "Geometry"), (lzs, "Geometry"))
lzp = g.n("ShaderNodeSeparateXYZ")
g.link((g.n("GeometryNodeInputPosition"), "Position"), (lzp, "Vector"))
g.link((lzp, "Z"), (lzs, "Value"))
shift = lzs

pos = g.n("GeometryNodeInputPosition")
dist = g.vmath("LENGTH", (pos, "Position"))
t = g.n("GeometryNodeInputSceneTime")

# ベースのうねり（ノイズ）
sep = g.n("ShaderNodeSeparateXYZ")
g.link((pos, "Position"), (sep, "Vector"))
noise = g.n("ShaderNodeTexNoise")
noise.noise_dimensions = "4D"
noise.inputs["Scale"].default_value = 0.09
noise.inputs["Detail"].default_value = 3
g.link((pos, "Position"), (noise, "Vector"))
tw = g.math("MULTIPLY", (t, "Seconds"), 0.25)
g.link((tw, 0), (noise, "W"))
base_h = g.math("MULTIPLY", g.math("POWER", (noise, "Factor"), 2.0), 3.2)

# ビート波紋: cos(d*0.9 - 4πt) を鋭くして距離減衰
ph = g.math("MULTIPLY", (dist, "Value"), 0.9)
tt = g.math("MULTIPLY", (t, "Seconds"), 4 * math.pi)
arg = g.math("SUBTRACT", (ph, 0), (tt, 0))
cs = g.math("COSINE", (arg, 0))
cs01 = g.math("MULTIPLY_ADD", (cs, 0), 0.5, 0.5)
sharp = g.math("POWER", (cs01, 0), 14.0)
decay = g.math("EXPONENT", g.math("MULTIPLY", (dist, "Value"), -0.045))
wave = g.math("MULTIPLY", (sharp, 0), (decay, 0))
wave_h = g.math("MULTIPLY", (wave, 0), 2.6)

h = g.math("ADD", (base_h, 0), (wave_h, 0))
h = g.math("ADD", (h, 0), 0.08)
# 中心（モノリス周り）を空ける
clear = g.n("ShaderNodeMapRange")
clear.inputs["From Min"].default_value = 2.2
clear.inputs["From Max"].default_value = 5.0
g.link((dist, "Value"), (clear, "Value"))
h = g.math("MULTIPLY", (h, 0), (clear, "Result"))
# カメラ通路（-Y 側, |x|<2.4）を空ける
c1 = g.n("ShaderNodeMapRange")
c1.inputs["From Min"].default_value = 2.0
c1.inputs["From Max"].default_value = 3.4
g.link((g.math("ABSOLUTE", (sep, "X")), 0), (c1, "Value"))
c2 = g.n("ShaderNodeMapRange")
c2.inputs["From Min"].default_value = -1.0
c2.inputs["From Max"].default_value = 1.5
g.link((sep, "Y"), (c2, "Value"))
corr = g.math("MAXIMUM", (c1, "Result"), (c2, "Result"))
h = g.math("MULTIPLY", (h, 0), (corr, 0))

inst = g.n("GeometryNodeInstanceOnPoints")
g.link((pts, "Points"), (inst, "Points"))
g.link((shift, "Geometry"), (inst, "Instance"))
comb = g.n("ShaderNodeCombineXYZ")
comb.inputs["X"].default_value = 1.0
comb.inputs["Y"].default_value = 1.0
g.link((h, 0), (comb, "Z"))
g.link((comb, "Vector"), (inst, "Scale"))
# 存在しない柱（高さ 0）は除外
sel = g.math("GREATER_THAN", (h, 0), 0.02)
g.link((sel, 0), (inst, "Selection"))

glow = g.math("ADD", (wave, 0), g.math("MULTIPLY", g.math("POWER", (noise, "Factor"), 6.0), 1.5))
glow = g.math("MINIMUM", (glow, 0), 1.0)
store = g.n("GeometryNodeStoreNamedAttribute")
store.data_type = "FLOAT"
store.domain = "INSTANCE"
store.inputs["Name"].default_value = "glow"
g.link((inst, "Instances"), (store, "Geometry"))
g.link((glow, 0), (store, "Value"))

pillar_mat = C.attr_emission_mat("Pillar", "glow", (0.0, 0.35, 1.0, 1), (0.1, 0.9, 1.0, 1), 40.0,
                                 base=(0.004, 0.004, 0.006, 1), roughness=0.3, metallic=0.5,
                                 top_mask=True, floor=0.05)
setm = g.n("GeometryNodeSetMaterial")
setm.inputs["Material"].default_value = pillar_mat
g.link((store, "Geometry"), (setm, "Geometry"))
g.link((setm, "Geometry"), (g.out, 0))

# --- モノリス ---
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 2.6))
mono = bpy.context.object
mono.scale = (1.1, 0.28, 5.2)
bev = mono.modifiers.new("bev", "BEVEL")
bev.width = 0.02
bev.segments = 3
mono.data.materials.append(C.principled_mat("Mono", (0.005, 0.005, 0.006, 1), 0.9, 0.08, coat=1.0))
# 発光エッジ（縦の細いライン 2 本）
edge_mat = C.emission_mat("Edge", (0.6, 0.9, 1.0, 1), 60)
for x in (-0.56, 0.56):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, -0.145, 2.6))
    e = bpy.context.object
    e.scale = (0.012, 0.012, 5.2)
    e.data.materials.append(edge_mat)

# --- ライト ---
C.area_light("Back", (0, 22, 16), (math.radians(-60), 0, 0), 2, 1500, (0.55, 0.75, 1.0))
C.area_light("Rim", (-6, 4, 3), (math.radians(80), 0, math.radians(-120)), 3, 2500, (1.0, 0.25, 0.55))
C.area_light("Fill", (5, -6, 4), (math.radians(60), 0, math.radians(40)), 4, 40, (0.7, 0.85, 1.0))

# --- カメラ：ドリーズーム ---
cam = C.camera("Cam", lens=18, loc=(0, -6, 1.5), clip_end=500)
target = C.empty("Target", (0, 0, 2.6))
C.track_to(cam, target)
cam.data.dof.use_dof = True
cam.data.dof.focus_object = mono
cam.data.dof.aperture_fstop = 2.8
# 前半ゆっくり → 後半一気に（イーズイン）
C.key(cam, "location", 1, (0, -6.0, 1.5))
C.key(cam.data, "lens", 1, 18.0)
C.key(cam, "location", FRAMES, (0, -32.0, 2.6))
C.key(cam.data, "lens", FRAMES, 18.0 * 32.0 / 6.0)
for idb in (cam, cam.data):
    for fc in C.fcurves(idb.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "QUAD"
            kp.easing = "EASE_IN_OUT"

C.compositor_bloom(s, threshold=0.9, strength=1.0, size=0.75, streak=True)
C.render(s, "s2", a, 1, FRAMES)
