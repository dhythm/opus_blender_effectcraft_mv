import bpy
s=bpy.context.scene
print("ENGINES",[e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items])
print("has node_tree",hasattr(s,'node_tree'),"has compositing_node_group",hasattr(s,'compositing_node_group'))
ee=s.eevee
print("EEVEE props",[p.identifier for p in ee.bl_rna.properties if any(k in p.identifier for k in ['blur','bloom','ray','shadow','volum','gtao','fast'])])
print("render motion",[p.identifier for p in s.render.bl_rna.properties if 'motion' in p.identifier])
try:
    ng=bpy.data.node_groups.new("c","CompositorNodeTree"); g=ng.nodes.new("CompositorNodeGlare")
    print("GLARE inputs",[ (i.name, getattr(i,'default_value',None)) for i in g.inputs])
    print("GLARE props",[p.identifier for p in g.bl_rna.properties][-10:])
except Exception as e: print("glare err",e)
import os
for f in ['/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc','/System/Library/Fonts/ヒラギノ角ゴシック W9.ttc','/System/Library/Fonts/HelveticaNeue.ttc','/System/Library/Fonts/Avenir Next.ttc']:
    try: print("FONT ok",bpy.data.fonts.load(f).name)
    except Exception as e: print("FONT fail",f,e)
print("gn nodes sample", [n for n in dir(bpy.types) if n.startswith('GeometryNode')][:5], len([n for n in dir(bpy.types) if n.startswith('GeometryNode')]))
