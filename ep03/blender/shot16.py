"""Shot 16: aerial after the crash: tail coaches thrown into the fields (illustrative layout; number of derailed coaches not published)."""
import sys, math, random
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector, Matrix, Euler
from lib import *
import world
PREV = '--final' not in sys.argv
sc = reset()
world.lighting(exposure=-1.7)
world.build(y_min=-150, y_max=200, quality=0.6 if PREV else 1.0, gap134=-2.0)
def place(n, loc, rot):
    o = bpy.data.objects[n]; o.location = loc; o.rotation_euler = Euler([math.radians(a) for a in rot]); return o
# tail coach shoved off to the canal side and rolled onto its flank; next coach jack-knifed
place('t2010_0', (6.8, -27.0, -0.2), (0, 82, 24))
place('t2010_1', (2.6, -50.5, 0.1), (0, 9, -11))
place('t2010_2', (0.5, -75.0, 0.0), (0, 2, -3))
place('l134', (0.6, -6.0, 1.1), (-4.5, 6, 4))
for i in range(3):
    o = bpy.data.objects.get(f't134_{i}')
    if o: o.location.y -= 4.0; o.location.x += 0.15 * (2 - i); o.rotation_euler.z = math.radians(1.5 * (2 - i))
# churned soil strip where the coach slid
soil = grime_mat('scar', (0.06, 0.045, 0.035), rough=0.95, amount=0.7, scale=2, streak=False)
sc_ = box('scar', (5.5, 28, 0.05), (4.6, -14, -0.57), soil, bevel=0.0); sc_.rotation_euler.z = math.radians(22)
# dust hanging over the site
dm = bpy.data.materials.new('dust'); dm.use_nodes = True; N = dm.node_tree.nodes; Lk = dm.node_tree.links
N.remove(N['Principled BSDF']); pv = N.new('ShaderNodeVolumePrincipled'); pv.inputs['Color'].default_value = (0.6, 0.52, 0.42, 1)
nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.6; nz.inputs['Detail'].default_value = 5
rp = N.new('ShaderNodeMapRange'); rp.inputs['From Min'].default_value = 0.5; rp.inputs['From Max'].default_value = 0.8; rp.inputs['To Max'].default_value = 0.18
Lk.new(nz.outputs['Fac'], rp.inputs['Value']); Lk.new(rp.outputs['Result'], pv.inputs['Density']); Lk.new(pv.outputs['Volume'], N['Material Output'].inputs['Volume'])
bpy.ops.mesh.primitive_uv_sphere_add(radius=10, location=(4, -18, 2)); d = bpy.context.object; d.scale = (1.4, 2.2, 0.5); d.data.materials.append(dm)
cam = camera((34.0, 38.0, 52.0), (2.0, -22.0, 0.0), lens=32)
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 40 if PREV else 128
sc.render.filepath = '/home/claude/ep03/out/s16' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/s16.blend')
bpy.ops.render.render(write_still=True)
