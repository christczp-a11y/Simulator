import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
from lib import *
import world, charsys as C, people as PP
PREV = '--final' not in sys.argv
VIEW = sys.argv[sys.argv.index('--view')+1] if '--view' in sys.argv else 'a'
sc = reset(); sc.render.fps = 30
import addon_utils; addon_utils.enable('rigify', default_set=True)
world.lighting(exposure=-1.4, haze=0.0)
W = world.build(y_min=-120, y_max=300, quality=0.5, gap134=None)
FZ = 1.20; ST = FZ + 0.465
def row_y(r): return -24 + 1.95 + 1.02*r
def seat_x(side, k): return side*(0.52 + k*0.50)
cast = [
  # name, preset, row, side(+1 = east/+X), k(0 aisle,1 window), extra
  ('p1', dict(sex='m',age='old',height=1.70,build=1.1,skin='brown',hair='receding',hair_col=(0.55,0.54,0.52),facial='full',top='galabeya',top_col=(0.40,0.33,0.25),bottom='none'), 17, -1, 1, 'window'),
  ('p2', dict(sex='f',age='adult',height=1.62,skin='tan',hair='none',hijab=(0.12,0.14,0.22),top='tee',top_col=(0.30,0.20,0.24),sleeve='long',bottom_col=(0.10,0.10,0.12)), 17, -1, 0, 'talk'),
  ('p3', dict(sex='m',age='adult',height=1.78,skin='tan',hair='side',facial='stubble',top='shirt',top_col=(0.70,0.72,0.74),sleeve='long',bottom_col=(0.16,0.16,0.20)), 17, 1, 0, 'listen'),
  ('p4', dict(sex='m',age='child',height=1.25,skin='tan',hair='curly',top='tee',top_col=(0.62,0.42,0.10),sleeve='short',bottom='shorts',bottom_col=(0.18,0.22,0.32)), 15, 1, 1, 'kidwindow'),
  ('p5', dict(sex='f',age='adult',height=1.60,skin='light',hair='none',hijab=(0.45,0.30,0.22),top='tee',top_col=(0.14,0.16,0.20),sleeve='long',bottom_col=(0.12,0.12,0.14)), 15, 1, 0, 'neutral'),
  ('p6', dict(sex='m',age='adult',height=1.76,skin='brown',hair='short',facial='moustache',top='galabeya',top_col=(0.70,0.71,0.72),bottom='none'), 19, 1, 1, 'turnback'),
  ('p8', dict(sex='m',age='adult',height=1.74,skin='brown',hair='short',facial='moustache',top='shirt',top_col=(0.45,0.50,0.62),sleeve='rolled',bottom_col=(0.15,0.15,0.17)), 18, -1, 1, 'n'),
  ('p9', dict(sex='f',age='old',height=1.58,build=1.15,skin='tan',hair='none',hijab=(0.05,0.05,0.06),top='tee',top_col=(0.06,0.06,0.07),sleeve='long',bottom_col=(0.06,0.06,0.07)), 18, -1, 0, 'n'),
  ('p10', dict(sex='m',age='adult',height=1.80,skin='tan',hair='short',facial='full',top='galabeya',top_col=(0.30,0.32,0.36),bottom='none'), 16, -1, 1, 'n'),
  ('p7', dict(sex='m',age='adult',height=1.72,skin='tan',hair='short',facial=None,top='polo',top_col=(0.20,0.30,0.25),sleeve='short',bottom_col=(0.20,0.18,0.15)), 13, -1, 0, 'down'),
]
R = {}
for name, P, row, side, k, act in cast:
    r, b = C.make_character(name=name, **P)
    bpy.context.view_layer.update()
    PP.sit(r, (seat_x(side, k), row_y(row) - 0.06, ST), knees=0.36 if P.get('age')!='child' else 0.25)
    R[name] = (r, act, side)
# acting
r = R['p1'][0]; PP.head_turn(r, yaw=-55, pitch=4); PP.expr(r, 'look')
r = R['p2'][0]; PP.head_turn(r, yaw=-25); PP.chest_turn(r, -10); PP.gesture(r, 'R', lift=8, fore=-38); PP.expr(r, 'talk')
r = R['p3'][0]; PP.head_turn(r, yaw=-35, pitch=-3); PP.expr(r, 'neutral')
r = R['p4'][0]; PP.head_turn(r, yaw=60, pitch=6); PP.chest_turn(r, 15); PP.expr(r, 'look')
r = R['p5'][0]; PP.head_turn(r, yaw=10, pitch=-8); PP.expr(r, 'squint')
r = R['p6'][0]; PP.chest_turn(r, -42); PP.head_turn(r, yaw=-68, pitch=4); PP.expr(r, 'puzzled')
r = R['p7'][0]; PP.head_turn(r, pitch=-25, yaw=8); PP.expr(r, 'neutral')
if VIEW == 'a':   # shot 5: aisle, looking back at passengers' faces
    cam = camera((0.05, row_y(17)-0.70, FZ+1.25), (-0.80, row_y(17)+0.10, FZ+1.02), lens=24)
    cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 1.05; cam.data.dof.aperture_fstop = 4
elif VIEW == 'b': # shot 5a: close on p6 turning to the rear door window
    r6 = R['p6'][0]; h = r6.matrix_world @ r6.pose.bones['head'].head
    cam = camera((-0.05, h.y + 0.10, h.z + 0.04), (h.x, h.y - 0.02, h.z + 0.03), lens=35)
    cam.data.dof.use_dof = True; cam.data.dof.focus_object = r6; cam.data.dof.focus_subtarget = 'head' if False else ''
    cam.data.dof.focus_distance = (Vector(cam.location) - h).length; cam.data.dof.aperture_fstop = 2.8
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 48 if PREV else 160
sc.render.filepath = f'/home/claude/ep03/out/s05{VIEW}' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath=f'/home/claude/ep03/s05{VIEW}.blend')
bpy.ops.render.render(write_still=True)
