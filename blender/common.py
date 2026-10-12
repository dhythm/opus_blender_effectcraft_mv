"""Blender ショット共通ヘルパー（Blender 5.2 / EEVEE）

各ショットスクリプトから import して使う:
    blender -b --factory-startup -P shot_xx.py -- --preview
"""
import math
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDERS = os.path.join(ROOT, "renders")
FPS = 30

# ブランドパレット（リニア RGB）
CYAN = (0.0, 0.75, 1.0, 1.0)
MAGENTA = (1.0, 0.05, 0.45, 1.0)
AMBER = (1.0, 0.45, 0.05, 1.0)
WHITE = (1.0, 1.0, 1.0, 1.0)


def args():
    """`--` 以降のコマンドライン引数を辞書化する"""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"preview": "--preview" in argv, "frames": None, "still": None}
    for i, a in enumerate(argv):
        if a == "--frames" and i + 1 < len(argv):
            s, e = argv[i + 1].split(":")
            out["frames"] = (int(s), int(e))
        if a == "--still" and i + 1 < len(argv):
            out["still"] = int(argv[i + 1])
        if a == "--step" and i + 1 < len(argv):
            out["step"] = int(argv[i + 1])
    return out


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "BLENDER_EEVEE"
    s.render.fps = FPS
    s.render.resolution_x = 1920
    s.render.resolution_y = 1080
    s.render.film_transparent = False
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Punchy"
    s.render.use_motion_blur = True
    s.render.motion_blur_shutter = 0.5
    ee = s.eevee
    ee.taa_render_samples = 48
    ee.use_raytracing = True
    ee.use_shadows = True
    ee.use_volumetric_shadows = True
    ee.volumetric_tile_size = "4"
    ee.volumetric_samples = 64
    return s


def world(color=(0.0, 0.0, 0.0), strength=1.0, fog_density=0.0, fog_color=(0.6, 0.7, 1.0)):
    w = bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (*color, 1.0)
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    if fog_density > 0:
        vol = nt.nodes.new("ShaderNodeVolumePrincipled")
        vol.inputs["Density"].default_value = fog_density
        vol.inputs["Color"].default_value = (*fog_color, 1.0)
        vol.inputs["Anisotropy"].default_value = 0.6
        nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return w


def studio_world(top=(0.002, 0.003, 0.008), horizon=(0.25, 0.4, 0.7), bottom=(0.0, 0.0, 0.0), strength=1.0):
    """クロムの映り込み用: 地平線が明るいグラデーションのワールド（カメラには暗く見える）"""
    w = bpy.data.worlds.new("Studio")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sx = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sx.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "EASE"
    els = ramp.color_ramp.elements
    els[0].position = 0.35
    els[0].color = (*bottom, 1)
    els[1].position = 0.5
    els[1].color = (*horizon, 1)
    e3 = els.new(0.62)
    e3.color = (*top, 1)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1
    mr.inputs["From Max"].default_value = 1
    nt.links.new(sx.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    # カメラ光線には暗い単色、反射には上記グラデーション
    lp = nt.nodes.new("ShaderNodeLightPath")
    dark = nt.nodes.new("ShaderNodeBackground")
    dark.inputs["Color"].default_value = (*top, 1)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(dark.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return w


def emission_mat(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def principled_mat(name, color=(0.02, 0.02, 0.025, 1), metallic=0.0, roughness=0.3,
                   emission=None, emission_strength=0.0, coat=0.0, transmission=0.0, ior=1.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = color
    p.inputs["Metallic"].default_value = metallic
    p.inputs["Roughness"].default_value = roughness
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Transmission Weight"].default_value = transmission
    p.inputs["IOR"].default_value = ior
    if emission:
        p.inputs["Emission Color"].default_value = emission
        p.inputs["Emission Strength"].default_value = emission_strength
    return m


def attr_emission_mat(name, attr, color_a, color_b, strength, base=(0.01, 0.01, 0.012, 1),
                      roughness=0.25, metallic=0.6, top_mask=False, floor=0.0):
    """GN で書き込んだ float 属性 `attr`(0..1) で発光色と強度を決めるマテリアル"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = base
    p.inputs["Roughness"].default_value = roughness
    p.inputs["Metallic"].default_value = metallic
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_type = "INSTANCER"
    a.attribute_name = attr
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = color_a
    ramp.color_ramp.elements[1].color = color_b
    nt.links.new(a.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Emission Color"])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 3.0
    nt.links.new(a.outputs["Fac"], pw.inputs[0])
    fl = nt.nodes.new("ShaderNodeMath")
    fl.operation = "ADD"
    fl.inputs[1].default_value = floor
    nt.links.new(pw.outputs[0], fl.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = strength
    nt.links.new(fl.outputs[0], mul.inputs[0])
    last = mul
    if top_mask:
        # インスタンスのローカル Z（Generated 座標）で上端だけを光らせる
        lz = nt.nodes.new("ShaderNodeAttribute")
        lz.attribute_type = "GEOMETRY"
        lz.attribute_name = "lz"
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.93
        mr.inputs["From Max"].default_value = 1.0
        mr.inputs["To Min"].default_value = 0.0
        nt.links.new(lz.outputs["Fac"], mr.inputs["Value"])
        m2 = nt.nodes.new("ShaderNodeMath")
        m2.operation = "MULTIPLY"
        nt.links.new(mul.outputs[0], m2.inputs[0])
        nt.links.new(mr.outputs["Result"], m2.inputs[1])
        last = m2
    nt.links.new(last.outputs[0], p.inputs["Emission Strength"])
    return m


def camera(name="Cam", lens=35, loc=(0, -10, 2), clip_end=1000):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_end = clip_end
    co = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(co)
    co.location = loc
    bpy.context.scene.camera = co
    return co


def look_at(obj, target):
    """obj を target(Vector or tuple) に向ける（静的）"""
    from mathutils import Vector
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def track_to(obj, target_obj):
    c = obj.constraints.new("TRACK_TO")
    c.target = target_obj
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return c


def empty(name, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = loc
    return e


def key(obj, path, frame, value, interp=None, index=-1):
    """値をセットしてキーフレームを打つ"""
    target = obj
    attr = path
    if "." in path:
        head, attr = path.rsplit(".", 1)
        target = obj.path_resolve(head)
    setattr(target, attr, value)
    target.keyframe_insert(attr, frame=frame, index=index)
    if interp:
        set_interp(obj, interp)


def set_interp(idblock, interp="BEZIER", easing="AUTO"):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return
    for fc in fcurves(ad.action):
        for kp in fc.keyframe_points:
            kp.interpolation = interp
            kp.easing = easing


def fcurves(action):
    """Blender 5.x のレイヤードアクションにも対応した fcurve 列挙"""
    if hasattr(action, "fcurves") and action.fcurves:
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def area_light(name, loc, rot, size, energy, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.size = size
    ld.energy = energy
    ld.color = color
    lo = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = rot
    return lo


def point_light(name, loc, energy, color=(1, 1, 1), radius=0.1):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = energy
    ld.color = color
    ld.shadow_soft_size = radius
    lo = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = loc
    return lo


# ---------- Geometry Nodes ヘルパー ----------

class GN:
    """GN ノードツリー組み立ての薄いラッパー（関数群をまとめた名前空間）"""

    def __init__(self, obj, name):
        mod = obj.modifiers.new(name, "NODES")
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        mod.node_group = ng
        self.mod = mod
        self.ng = ng
        self.inp = ng.nodes.new("NodeGroupInput")
        self.out = ng.nodes.new("NodeGroupOutput")

    def n(self, t, **props):
        node = self.ng.nodes.new(t)
        for k, v in props.items():
            setattr(node, k, v)
        return node

    def link(self, a, b):
        """a, b は (node, socket名 or index)"""
        an, ao = a
        bn, bi = b
        self.ng.links.new(an.outputs[ao], bn.inputs[bi])

    def math(self, op, a=None, b=None, c=None):
        """Math ノード。引数は数値 or (node, out) のタプル"""
        node = self.n("ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if hasattr(v, "outputs"):
                v = (v, 0)
            if isinstance(v, tuple):
                self.link(v, (node, i))
            else:
                node.inputs[i].default_value = v
        return node

    def vmath(self, op, a=None, b=None, scale=None):
        node = self.n("ShaderNodeVectorMath", operation=op)
        if hasattr(scale, "outputs"):
            scale = (scale, 0)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if hasattr(v, "outputs"):
                v = (v, 0)
            if isinstance(v, tuple) and len(v) == 2 and hasattr(v[0], "outputs"):
                self.link(v, (node, i))
            else:
                node.inputs[i].default_value = v
        if scale is not None:
            if isinstance(scale, tuple):
                self.link(scale, (node, "Scale"))
            else:
                node.inputs["Scale"].default_value = scale
        return node

    def rand(self, dtype, mn, mx, seed=0):
        """Random Value ノード。dtype: FLOAT / FLOAT_VECTOR。(node, 出力index) を返す"""
        node = self.n("FunctionNodeRandomValue", data_type=dtype)
        st = {"FLOAT": "VALUE", "FLOAT_VECTOR": "VECTOR"}[dtype]
        ins = [i for i in node.inputs if i.type == st]
        ins[0].default_value = mn
        ins[1].default_value = mx
        node.inputs["Seed"].default_value = seed
        oi = [k for k, o in enumerate(node.outputs) if o.type == st][0]
        return (node, oi)

    def value(self, v):
        node = self.n("ShaderNodeValue")
        node.outputs[0].default_value = v
        return node


def compositor_bloom(scene, threshold=0.8, strength=0.9, size=0.7, streak=False, lens_disp=0.012):
    """Blender 側の基本ポスト（ブルーム＋光学的な色収差）。グレードは EffectCraft 側で行う"""
    ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = ng
    rl = ng.nodes.new("CompositorNodeRLayers")
    out = ng.nodes.new("NodeGroupOutput")
    g = ng.nodes.new("CompositorNodeGlare")
    g.inputs["Type"].default_value = "Bloom"
    g.inputs["Quality"].default_value = "High"
    g.inputs["Threshold"].default_value = threshold
    g.inputs["Strength"].default_value = strength
    g.inputs["Size"].default_value = size
    ng.links.new(rl.outputs["Image"], g.inputs["Image"])
    last = g
    if streak:
        g2 = ng.nodes.new("CompositorNodeGlare")
        g2.inputs["Type"].default_value = "Streaks"
        g2.inputs["Threshold"].default_value = threshold * 2.5
        g2.inputs["Strength"].default_value = 0.35
        g2.inputs["Streaks"].default_value = 2
        g2.inputs["Streaks Angle"].default_value = 0.0
        g2.inputs["Fade"].default_value = 0.93
        ng.links.new(last.outputs["Image"], g2.inputs["Image"])
        last = g2
    if lens_disp > 0:
        ld = ng.nodes.new("CompositorNodeLensdist")
        ld.inputs["Dispersion"].default_value = lens_disp
        ld.inputs["Distortion"].default_value = -0.01
        ld.inputs["Fit"].default_value = True
        ng.links.new(last.outputs["Image"], ld.inputs["Image"])
        last = ld
    ng.links.new(last.outputs["Image"], out.inputs[0])
    return ng


def render(scene, shot, a, frame_start, frame_end):
    """プレビュー時は 1/4 解像度・低サンプル。PNG 連番で renders/<shot>/ に出す"""
    if os.environ.get("NO_RENDER"):
        return  # 統計取得用: シーン構築だけ行う
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    if a.get("frames"):
        scene.frame_start, scene.frame_end = a["frames"]
    scene.frame_step = a.get("step", 1)
    sub = shot
    if a["preview"]:
        scene.render.resolution_percentage = 33
        scene.eevee.taa_render_samples = 12
        sub = shot + "_preview"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    d = os.path.join(RENDERS, sub)
    os.makedirs(d, exist_ok=True)
    if a.get("still") is not None:
        scene.frame_set(a["still"])
        scene.render.filepath = os.path.join(d, f"still_{a['still']:04d}.png")
        bpy.ops.render.render(write_still=True)
        return
    scene.render.filepath = os.path.join(d, "f_")
    bpy.ops.render.render(animation=True)
