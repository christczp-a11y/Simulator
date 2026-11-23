import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from lib import *
from trains import *
import props
sc = reset(); sc.cycles.samples = 48
sky_world(35, 120, strength=0.35, aerosol=1.2)
sun(elev_deg=35, azim_deg=120, strength=4.0, color=(1.0,0.9,0.78), angle=0.8)
bpy.ops.mesh.primitive_plane_add(size=200); g=bpy.context.object; g.location.z=-0.55
g.data.materials.append(grime_mat('gnd',(0.20,0.15,0.10),0.95,amount=0.4))
props.track(0,-60,60)
lo = locomotive('Loco', y0=0.0)
cam = camera((-7.5,-9.5,2.2),(0.3,6,2.3), lens=35)
sc.render.resolution_x, sc.render.resolution_y = 1080, 1350
sc.render.resolution_percentage = 60
sc.render.filepath = '/home/claude/ep03/out/loco_v1.png'
bpy.ops.render.render(write_still=True)
cam2 = camera((5.5,22,5),(0,10,2.5), lens=30, name='C2'); sc.camera=cam2
sc.render.filepath = '/home/claude/ep03/out/loco_v1b.png'
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/loco.blend')
