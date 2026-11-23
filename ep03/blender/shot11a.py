import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
from lib import *
import world, charsys as C, people as PP
PREV = '--final' not in sys.argv
sc = reset(); sc.render.fps = 30
import addon_utils; addon_utils.enable('rigify', default_set=True)
world.lighting(exposure=-1.4, haze=0.0)
W = world.build(y_min=-120, y_max=300, quality=0.5, gap134=None)
FZ = 1.20; ST = FZ + 0.465
def row_y(r): return -24 + 1.95 + 1.02*r
def seat_x(side, k): return side*(0.52 + k*0.50)
cast = [
  ('q1', dict(sex='m',age='adult',height=1.78,skin='tan',hair='side',facial='stubble',top='shirt',top_col=(0.62,0.64,0.68),sleeve='long',bottom_col=(0.16,0.16,0.20)), 9, -1, 0),
  ('q2', dict(sex='f',age='adult',height=1.62,skin='tan',hair='none',hijab=(0.30,0.12,0.14),top='tee',top_col=(0.14,0.16,0.20),sleeve='long',bottom_col=(0.10,0.10,0.12)), 9, -1, 1),
  ('q3', dict(sex='m',age='old',height=1.70,build=1.1,skin='brown',hair='receding',hair_col=(0.55,0.54,0.52),facial='full',top='galabeya',top_col=(0.36,0.30,0.24),bottom='none'), 10, 1, 1),
  ('q4', dict(sex='m',age='adult',height=1.74,skin='brown',hair='short',facial='moustache',top='polo',top_col=(0.20,0.30,0.25),sleeve='short',bottom_col=(0.20,0.18,0.15)), 10, 1, 0),
  ('q5', dict(sex='f',age='old',height=1.58,build=1.15,skin='tan',hair='none',hijab=(0.05,0.05,0.06),top='tee',top_col=(0.06,0.06,0.07),sleeve='long',bottom_col=(0.06,0.06,0.07)), 11, -1, 1),
]
import random as _r
_rr = _r.Random(21)
SKINS = ['brown', 'tan', 'tan', 'light', 'brown']
occupied = {(9, -1, 0), (9, -1, 1), (10, 1, 1), (10, 1, 0), (11, -1, 1)}
extra = []
for row in range(8, 16):
    for side in (-1, 1):
        for k in (0, 1):
            if (row, side, k) in occupied or (row == 8 and k == 0): continue
            if _rr.random() < 0.18: continue          # a few empty seats
            sex = _rr.choice('mf'); age = _rr.choice(['adult', 'adult', 'adult', 'old', 'child' if k == 1 else 'adult'])
            P = dict(sex=sex, age=age, height=(1.25 if age == 'child' else _rr.uniform(1.58, 1.82)), skin=_rr.choice(SKINS))
            if sex == 'f':
                P.update(hair='none', hijab=_rr.choice([(0.05,0.05,0.06), (0.30,0.12,0.14), (0.14,0.16,0.24), (0.45,0.32,0.22), (0.55,0.52,0.48)]),
                         top='tee', top_col=_rr.choice([(0.08,0.08,0.09), (0.22,0.16,0.20), (0.18,0.22,0.30)]), sleeve='long', bottom_col=(0.08,0.08,0.1))
            else:
                if _rr.random() < 0.35:
                    P.update(hair=_rr.choice(['short', 'receding']), facial=_rr.choice(['moustache', 'full', None]), top='galabeya',
                             top_col=_rr.choice([(0.55,0.50,0.42), (0.30,0.32,0.36), (0.70,0.70,0.68), (0.36,0.30,0.24)]), bottom='none')
                else:
                    P.update(hair=_rr.choice(['short', 'side', 'curly']), facial=_rr.choice(['stubble', 'moustache', None]),
                             top=_rr.choice(['shirt', 'polo', 'tee']), top_col=_rr.choice([(0.62,0.64,0.68), (0.25,0.30,0.40), (0.45,0.35,0.25), (0.15,0.15,0.17)]),
                             sleeve=_rr.choice(['long', 'short', 'rolled']), bottom_col=(0.15,0.15,0.18))
                    if age == 'child': P.update(bottom='shorts', facial=None)
            extra.append((f'x{row}{side}{k}', P, row, side, k))
cast += extra
R = {}
for name, P, row, side, k in cast:
    r, b = C.make_character(name=name, **P)
    bpy.context.view_layer.update()
    PP.sit(r, (seat_x(side, k), row_y(row) - 0.06, ST), knees=0.36, lean=24)
    R[name] = (r, row, side, k)
# emergency braking: bodies pitch forward (-Y), arms thrown out to brace on the seat back ahead
from mathutils import Matrix
for i, (name, (r, row, side, k)) in enumerate(R.items()):
    sx = seat_x(side, k); by = row_y(row - 1) + 0.38
    for sd, dx in (('L', 0.17), ('R', -0.17)):
        r.pose.bones[f'upper_arm_parent.{sd}']['IK_FK'] = 0.0
        tgt = Vector((sx + dx * 1.25 + (0.03 if i % 2 else -0.02), by + (0.02 if sd == 'L' else 0.0), FZ + (0.92 if sd == 'L' else 0.86)))
        fdir = Vector((dx * 0.8, -0.15, 1.0)).normalized(); nrm = Vector((0, 1.0, 0.1))
        wrist = tgt - fdir * 0.07 + Vector((0, 0.025, 0))
        zax = (nrm - fdir * fdir.dot(nrm)).normalized(); xax = fdir.cross(zax)
        Mw = Matrix((xax, fdir, zax)).transposed().to_4x4(); Mw.translation = wrist
        r.pose.bones[f'hand_ik.{sd}'].matrix = r.matrix_world.inverted() @ Mw
        bpy.context.view_layer.update()
    PP.head_turn(r, yaw=_rr.uniform(-15, 15), pitch=_rr.uniform(6, 18))
    PP.expr(r, 'alarm')
# loose objects caught mid-air: water bottle, phone, a carrier bag
bott = cyl('bottle', 0.035, 0.22, (0.02, row_y(9) - 0.35, FZ + 1.62), rot=(math.radians(70), 0.4, 0), m=mat('pet', (0.75, 0.85, 0.9), rough=0.05, trans=0.85), verts=16)
ph = box('phone', (0.075, 0.15, 0.009), (-0.10, row_y(10) - 0.75, FZ + 1.45), mat('phoneM', (0.02, 0.02, 0.025), rough=0.2), bevel=0.2); ph.rotation_euler = (0.9, 0.3, 0.6)
bag = box('bag', (0.30, 0.12, 0.34), (0.45, row_y(11) - 0.70, FZ + 1.05), mat('bagM', (0.60, 0.58, 0.52), rough=0.8), bevel=0.15); bag.rotation_euler = (0.5, 0.2, -0.3)
# camera in the aisle ahead of them, looking back at the faces; low handheld tilt
cam = camera((0.10, row_y(9) - 1.55, FZ + 1.30), (-0.25, row_y(10) - 0.10, FZ + 1.00), lens=22)
cam.rotation_euler.y += math.radians(6)
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 1.35; cam.data.dof.aperture_fstop = 3.5
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 48 if PREV else 160
sc.render.filepath = '/home/claude/ep03/out/s11a' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/s11a.blend')
bpy.ops.render.render(write_still=True)
