"""シーンを評価して実数を出す（NO_RENDER=1 で shot スクリプトの後に実行）"""
import bpy
s = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()


def inst_count(frame):
    s.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for di in dg.object_instances:
        if di.is_instance:
            n += 1
    return n


name = bpy.data.filepath or s.name
for f in getattr(bpy.types.Scene, "_stat_frames", [1]):
    pass
import os
shot = os.environ.get("SHOT")
if shot == "s2":
    print("STAT s2 instances f1", inst_count(1), "f90", inst_count(90))
elif shot == "s3":
    path = bpy.data.objects["Path"]
    sp = path.data.splines[0]
    # パス長を評価済みメッシュから算出
    me = path.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    L = sum((me.vertices[e.vertices[0]].co - me.vertices[e.vertices[1]].co).length for e in me.edges)
    print("STAT s3 path_length", round(L, 1), "instances", inst_count(60))
    rig = bpy.data.objects["Rig"]
    fc = [f for f in __import__("common").fcurves(rig.animation_data.action)][0]
    for a_, b_ in ((1, 60), (60, 78), (88, 128), (140, 172)):
        v = (fc.evaluate(b_) - fc.evaluate(a_)) * L / ((b_ - a_) / 30)
        print("STAT s3 speed", a_, b_, round(v, 1), "m/s")
    mid = [(fc.evaluate(f + 1) - fc.evaluate(f)) * L * 30 for f in range(1, 179)]
    print("STAT s3 speed max", round(max(mid), 1), "min(after 60)", round(min(mid[60:170]), 1))
elif shot == "s5":
    print("STAT s5 instances f100", inst_count(100), "f230", inst_count(230))
elif shot == "s6":
    print("STAT s6 instances f20", inst_count(20))
