import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from lib import reset, mat, sun, camera
sc=reset()
import charsys as C
sc.render.resolution_x=1800; sc.render.resolution_y=1000; sc.cycles.samples=24
sc.view_settings.look='AgX - Base Contrast'
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.93,0.925,0.91,1); w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.7
sun(42,215,strength=3.0,color=(1,0.97,0.92),angle=5)
bpy.ops.mesh.primitive_plane_add(size=60); bpy.context.object.data.materials.append(mat('floor',(0.80,0.795,0.78),rough=0.8))
people=[
 dict(name='m1',sex='m',age='adult',height=1.76,skin='tan',hair='short',facial='moustache',top='shirt',top_col=(0.62,0.66,0.70),sleeve='short',bottom_col=(0.15,0.15,0.17)),
 dict(name='f1',sex='f',age='adult',height=1.63,skin='light',hair='none',hijab=(0.36,0.20,0.22),top='tee',top_col=(0.20,0.22,0.26),sleeve='long',bottom_col=(0.12,0.12,0.14)),
 dict(name='o1',sex='m',age='old',height=1.70,build=1.15,skin='brown',hair='receding',hair_col=(0.55,0.54,0.52),facial='full',top='shirt',top_col=(0.78,0.76,0.70),sleeve='long',bottom_col=(0.28,0.25,0.21),glasses=True),
 dict(name='c1',sex='m',age='child',height=1.28,skin='tan',hair='curly',top='tee',top_col=(0.55,0.15,0.12),sleeve='short',bottom='shorts',bottom_col=(0.18,0.22,0.32)),
 dict(name='u1',sex='m',age='adult',height=1.80,skin='brown',hair='short',facial='stubble',top='uniform',top_col=(0.20,0.24,0.32),sleeve='long',bottom_col=(0.14,0.16,0.22),cap=(0.16,0.19,0.26)),
]
xs=[-1.6,-0.8,0,0.8,1.6]
rigs=[]
for x,p in zip(xs,people):
    r,b=C.make_character(loc=(x,0,0),**p); rigs.append(r); bpy.context.view_layer.update(); import poses; poses.stand(r)
cam=camera((0.4,-6.2,1.35),(0,0,0.85),lens=55)
sc.render.filepath='/home/claude/ep03/out/v7_lineup.png'
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/chars_v7.blend')
print('DONE')
