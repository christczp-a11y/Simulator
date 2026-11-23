import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from lib import *
from trains import *
import props
sc = reset(); sc.cycles.samples = 48; sc.view_settings.exposure = -0.3
sky_world(35, 120, strength=0.35, aerosol=1.2)
sun(elev_deg=35, azim_deg=120, strength=4.0, color=(1.0,0.9,0.78), angle=0.8)
bpy.ops.mesh.primitive_plane_add(size=300); g=bpy.context.object; g.location.z=-0.55
g.data.materials.append(grime_mat('gnd',(0.20,0.15,0.10),0.95,amount=0.4))
props.track(0,-60,90)
c = coach('C1', y0=0.0, tail=True)
lo = locomotive('Loco', y0=-22.5)
cam = camera((-6.5,29,2.0),(0,14,2.4), lens=30)
sc.render.resolution_x, sc.render.resolution_y = 1080, 1350; sc.render.resolution_percentage = 60
sc.render.filepath = '/home/claude/ep03/out/coach_v1.png'; bpy.ops.render.render(write_still=True)
# interior
ci = camera((-0.95, 21.0, 2.45),(0.3, 8, 2.1), lens=22, name='Ci'); sc.camera = ci
sc.render.filepath = '/home/claude/ep03/out/coach_int_v1.png'; bpy.ops.render.render(write_still=True)
sc.camera = cam
cl = camera((-9,-26,2.6),(0,-15,2.5), lens=40, name='Cl'); sc.camera=cl
sc.render.filepath = '/home/claude/ep03/out/loco_v2.png'; bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/coach.blend')
