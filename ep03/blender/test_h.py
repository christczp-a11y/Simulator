import sys; sys.path.insert(0,'/home/claude/ep03')
import bpy, math
from lib import *; from human import *
sc=reset(); sky_world(40,150,0.3,1.0); sun(40,150,3.5)
bpy.ops.mesh.primitive_plane_add(size=20); bpy.context.object.data.materials.append(mat('fl',(0.3,0.3,0.3),0.8))
person('a', {}, seed=1, loc=(-1.2,0,0))
person('b', {}, seed=2, galabeya=True, loc=(-0.4,0,0), width=1.1)
person('c', {}, seed=3, hijab=True, height=1.62, loc=(0.4,0,0), width=0.92)
person('d', SEATED, seed=4, loc=(1.3,0,0))
box('seat',(0.5,0.5,0.45),(1.3,0.05,0.225),mat('st',(0.1,0.2,0.4),0.6))
camera((0.2,-5.5,1.3),(0.1,0,0.9),lens=50)
sc.render.resolution_x, sc.render.resolution_y=1080,1080; sc.render.resolution_percentage=60; sc.cycles.samples=24
sc.view_settings.exposure=-1.0
sc.render.filepath='/home/claude/ep03/out/humans.png'; bpy.ops.render.render(write_still=True); print('DONE')
