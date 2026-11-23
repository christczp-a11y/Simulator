"""Shot 17: signal logbook close-up, one entry struck through (illustrative prop, no real names/handwriting)."""
import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
from lib import *
PREV = '--final' not in sys.argv
sc = reset()
import world, signalbox as SB
world.lighting(exposure=-1.2, haze=0.00012)
world.build(y_min=-100, y_max=250, quality=0.4, trains=False)
BX = 9.6
sb = SB.signal_box('SB', loc=(BX, 60, -0.6))
cx, cy, cz = sb['console']; cz += -0.6
bx, by, bz = BX + cx + 0.15, 60 + 0.9, cz + 0.812
# page with the ledger texture (lines run across X; top of page toward -X = the window)
me = bpy.data.meshes.new('page'); me.from_pydata([(-0.145,-0.205,0),(0.145,-0.205,0),(0.145,0.205,0),(-0.145,0.205,0)],[],[(0,1,2,3)])
me.uv_layers.new(); uv = me.uv_layers[0].data
for i,(u,v) in enumerate(((0,0),(1,0),(1,1),(0,1))): uv[i].uv = (u, v)
pg = bpy.data.objects.new('page', me); link(pg); pg.location = (bx, by, bz)
m = bpy.data.materials.new('pageM'); m.use_nodes = True; N = m.node_tree.nodes
tx = N.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load('/home/claude/ep03/assets/tex/logbook.png')
m.node_tree.links.new(tx.outputs['Color'], N['Principled BSDF'].inputs['Base Color']); N['Principled BSDF'].inputs['Roughness'].default_value = 0.85
me.materials.append(m)
# ballpoint pen lying across the page
pen = cyl('pen', 0.0045, 0.14, (bx + 0.05, by + 0.06, bz + 0.006), rot=(math.pi/2, 0, math.radians(62)), m=mat('penBlue', (0.05, 0.08, 0.25), rough=0.35), verts=12)
# the struck row is about 60% down the page: v ~ 0.40 -> local y ~ -0.04 ; across x ~ +0.0
focus = Vector((bx + 0.02, by - 0.045, bz))
cam = camera((bx + 0.16, by - 0.42, bz + 0.36), tuple(focus), lens=50)
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = (Vector(cam.location) - focus).length; cam.data.dof.aperture_fstop = 2.0
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 48 if PREV else 160
sc.render.filepath = '/home/claude/ep03/out/s17' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/s17.blend')
bpy.ops.render.render(write_still=True)
