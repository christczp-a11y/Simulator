import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from lib import reset, mat, sun, camera, box
sc=reset()
import charsys as C, retarget as RT
sc.render.fps=30
CLIP=sys.argv[-2]; OUT=sys.argv[-1]
P=dict(sex='m',age='adult',height=1.74,skin='tan',hair='side',facial='moustache',top='shirt',top_col=(0.62,0.66,0.70),sleeve='rolled',bottom_col=(0.15,0.15,0.17))
r,b=C.make_character(name='a',loc=(0,0,0),**P)
bpy.context.view_layer.update()
last=RT.retarget(r, f'/home/claude/ep03/mocap/{CLIP}.bvh', step=4)
RT.fix_feet(r,1,last)
off=RT.ground(r,1,last)
print('frames',last,'float before: max %.3f min %.3f'%(max(off),min(off)))
bpy.ops.wm.save_as_mainfile(filepath=f'/home/claude/ep03/anim_{OUT}.blend')
