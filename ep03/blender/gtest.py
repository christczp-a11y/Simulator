import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from lib import reset, mat, sun, camera, box
sc=reset(); sc.render.fps=30
import charsys as C, retarget as RT
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.93,0.925,0.91,1); w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.8
sun(42,215,strength=3.0,color=(1,0.97,0.92),angle=5)
bpy.ops.mesh.primitive_plane_add(size=200); bpy.context.object.data.materials.append(mat('floor',(0.80,0.795,0.78),rough=0.8))
A=dict(sex='m',age='old',height=1.70,build=1.1,skin='brown',hair='receding',hair_col=(0.55,0.54,0.52),facial='full',top='galabeya',top_col=(0.42,0.36,0.28),bottom='none')
Bp=dict(sex='m',age='adult',height=1.76,skin='tan',hair='short',facial='moustache',top='galabeya',top_col=(0.62,0.64,0.66),bottom='none')
r1,b1=C.make_character(name='g1',loc=(0,0,0),**A)
r2,b2=C.make_character(name='g2',loc=(1.2,0,0),**Bp)
bpy.context.view_layer.update()
l1=RT.retarget(r1,'/home/claude/ep03/mocap/02_01.bvh',step=4); RT.fix_feet(r1,1,l1); RT.ground(r1,1,l1)
l2=RT.retarget(r2,'/home/claude/ep03/mocap/114_05.bvh',step=4)
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/gal_test.blend')
print('frames',l1,l2)
