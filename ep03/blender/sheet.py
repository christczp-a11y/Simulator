import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
from lib import reset, mat, sun, camera, box
sc=reset()
import charsys as C
from poses import *
MODE=sys.argv[-1]
sc.cycles.samples=40; sc.view_settings.look='AgX - Base Contrast'
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.93,0.925,0.91,1); w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.7
sun(42,215,strength=3.0,color=(1,0.97,0.92),angle=5)
bpy.ops.mesh.primitive_plane_add(size=60); bpy.context.object.data.materials.append(mat('floor',(0.80,0.795,0.78),rough=0.8))
U=dict(sex='m',age='adult',height=1.78,skin='brown',hair='short',facial='stubble',top='uniform',top_col=(0.20,0.24,0.32),sleeve='long',bottom_col=(0.14,0.16,0.22),cap=(0.16,0.19,0.26))
P=dict(sex='m',age='adult',height=1.74,skin='tan',hair='side',facial='moustache',top='shirt',top_col=(0.62,0.66,0.70),sleeve='rolled',bottom_col=(0.15,0.15,0.17))
F=dict(sex='f',age='adult',height=1.63,skin='light',hair='none',hijab=(0.36,0.20,0.22),top='tee',top_col=(0.20,0.22,0.26),sleeve='long',bottom_col=(0.12,0.12,0.14))
if MODE=='action':
    sc.render.resolution_x=2000; sc.render.resolution_y=900
    sets=[(P,stand,'stand'),(P,walk,'walk'),(P,run,'run'),(F,'seated','seated'),(U,brace,'thrown')]
    ys=[2.4,1.2,0.0,-1.2,-2.4]
    for i,((p,fn,nm),y) in enumerate(zip(sets,ys)):
        r,b=C.make_character(name=f'a{i}',loc=(0,y,0),**p); bpy.context.view_layer.update()
        if fn=='seated':
            seated(r,0)
            for o in ('seat','back'):
                ob=[x for x in bpy.data.objects if x.name.startswith(o) and abs(x.location.y-0.10 if o=='seat' else 0)<9 and x.get('done') is None]
                for x in ob: x.location.y += y; x['done']=1
        else: fn(r)
    camera((7.2,0.3,1.25),(0,0,0.8),lens=40)
    sc.render.filepath='/home/claude/ep03/out/chars_v1_action.png'
else:
    sc.render.resolution_x=640; sc.render.resolution_y=640; sc.cycles.samples=32
    r1,_=C.make_character(name='fp',loc=(0,0,0),**P); r2,_=C.make_character(name='ff',loc=(1.5,0,0),**F)
    for r in (r1,r2): arms_down(r,58)
    import os
    seq=[('rest',0),('A',0),('E',0),('O',0),('M',0),('rest',1.0)]
    for who,(r,x,z) in {'p':(r1,0,1.62),'f':(r2,1.5,1.50)}.items():
        cam=camera((x+0.35,-1.05,z+0.02),(x,0,z-0.02),lens=85)
        for k,(v,bl) in enumerate(seq):
            C.mouth(r,v); C.blink(r,bl); bpy.context.view_layer.update()
            sc.render.filepath=f'/home/claude/ep03/out/face_{who}_{k}.png'
            bpy.ops.render.render(write_still=True)
    print('DONE'); sys.exit()
bpy.ops.render.render(write_still=True)
print('DONE')
