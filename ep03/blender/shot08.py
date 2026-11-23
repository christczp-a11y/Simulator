import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
from lib import *
PREV = '--final' not in sys.argv
VIEW = sys.argv[sys.argv.index('--view')+1] if '--view' in sys.argv else 's08'
sc = reset()
import addon_utils; addon_utils.enable('rigify', default_set=True)
import world, charsys as C, people as PP
GAP = {'s08': 900, 's11': 160, 's19': 900}[VIEW]
world.lighting(exposure=-0.9 if VIEW != 's11' else -1.5, haze=0.00016)
W = world.build(y_min=-150, y_max=GAP + 200, quality=0.6, gap134=None)
from trains import locomotive
lo = locomotive('l134', y0=GAP, lights=True, interior=True, atc_on=False)
fz = 1.55 + 0.05; dx = 0.72
if VIEW == 's08':
    r, b = C.make_character(name='drv', sex='m', age='adult', height=1.76, skin='brown', hair='short', facial='moustache',
                            top='uniform', top_col=(0.20, 0.24, 0.30), sleeve='long', bottom_col=(0.14, 0.16, 0.22))
    bpy.context.view_layer.update()
    PP.sit(r, (dx, GAP + 1.96, fz + 0.67), knees=0.30, lean=-16)
    # left hand to the ATC isolation switch (IK)
    C.set_ik_fk(r, ik=False)
    r.pose.bones['upper_arm_parent.L']['IK_FK'] = 0.0
    bpy.context.view_layer.update()
    a = math.radians(32)
    sw = Vector((dx + 0.19, GAP + 1.30 + 0.17*math.cos(a), fz + 1.12 - 0.17*math.sin(a) + 0.08))
    from mathutils import Matrix
    nrm = Vector((0, math.sin(a), math.cos(a)))
    fdir = Vector((-0.12, -0.85, 0.42)).normalized()          # fingers lie along the panel slope toward the switch
    wrist = sw + Vector((0, 0, -0.03)) - fdir * 0.095 + nrm * 0.05
    zax = (nrm - fdir * fdir.dot(nrm)).normalized(); xax = fdir.cross(zax)
    Mw = Matrix((xax, fdir, zax)).transposed().to_4x4(); Mw.translation = wrist
    pb = r.pose.bones['hand_ik.L']; pb.matrix = r.matrix_world.inverted() @ Mw
    bpy.context.view_layer.update()
    cam = camera((dx + 0.53, GAP + 2.15, fz + 1.80), (dx + 0.23, GAP + 1.30, fz + 1.15), lens=30)
    cam.data.dof.use_dof = True; cam.data.dof.focus_distance = (Vector(cam.location) - sw).length; cam.data.dof.aperture_fstop = 4.0
    bpy.ops.object.light_add(type='AREA', location=(dx + 0.1, GAP + 2.1, fz + 2.2)); L = bpy.context.object
    L.data.energy = 45; L.data.size = 0.6; L.data.color = (1.0, 0.93, 0.82)
elif VIEW == 's11':
    cam = camera((dx - 0.05, GAP + 2.00, fz + 1.45), (-0.3, GAP - 120, -4.0), lens=30)
else:
    cam = camera((dx - 0.9, GAP + 3.2, fz + 1.3), (dx, GAP + 1.9, fz + 0.7), lens=30)
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 48 if PREV else 160
sc.render.filepath = f'/home/claude/ep03/out/{VIEW}' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath=f'/home/claude/ep03/{VIEW}.blend')
bpy.ops.render.render(write_still=True)
