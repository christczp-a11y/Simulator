import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector, Matrix
from lib import *
sc = reset()
import world, crash
from trains import coach, locomotive
world.lighting(exposure=-1.6)
box('gnd', (60, 120, 0.2), (0, -10, -0.7), mat('g', (0.1, 0.08, 0.06), rough=0.9))
t = coach('t2010_0', y0=-24.0, interior=True, tail=True, seed=1)
hy = crash.telescope(t, rear_y=0.0, pen=7.0, crumple=5.0)
print('HINGE', hy)
lo = locomotive('l134', y0=0, lights=False)
crash.nose_damage(lo, 0.5)
lift, pitch = 1.25, math.radians(-4.0)
lo.location = (0.15, hy + 0.2, lift); lo.rotation_euler = (pitch, 0, math.radians(2))
view = sys.argv[-1]
if view == 'side': cam = camera((22, hy + 2, 3.0), (0, hy + 1.5, 2.2), lens=50)
elif view == 'top': cam = camera((4, hy + 3, 26), (0, hy - 1, 1.5), lens=35)
else: cam = camera((-12, hy + 12, 6), (0, hy, 2.4), lens=35)
sc.render.resolution_x, sc.render.resolution_y = 900, 900
sc.cycles.samples = 20
sc.render.filepath = f'/tmp/claude-0/ct_{view}.png'
bpy.ops.render.render(write_still=True)
