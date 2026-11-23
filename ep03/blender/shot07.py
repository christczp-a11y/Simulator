import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
from lib import *
PREV = '--final' not in sys.argv
VIEW = sys.argv[sys.argv.index('--view')+1] if '--view' in sys.argv else 'in'
sc = reset()
import addon_utils; addon_utils.enable('rigify', default_set=True)
import world, charsys as C, people as PP, signalbox as SB
world.lighting(exposure=-1.1 if VIEW=='in' else -1.3, haze=0.00012)
world.build(y_min=-200, y_max=400, quality=0.5, trains=False)
BX = 9.6
sb = SB.signal_box('SB', loc=(BX, 60, -0.6), occupied_lights={5: 'red', 6: 'red', 7: 'red', 8: 'yel', 9: 'off', 10: 'grn'})
cx, cy, cz = sb['console']
cz += -0.6
if VIEW == 'in':
    r, b = C.make_character(name='op', sex='m', age='adult', height=1.74, skin='brown', hair='short', facial='moustache',
                            top='uniform', top_col=(0.22, 0.26, 0.34), sleeve='long', bottom_col=(0.15, 0.17, 0.22))
    bpy.context.view_layer.update()
    # sits on the pulled-back chair, turned side-on, back to the console (as described by prosecutors: panel not monitored)
    PP.sit(r, (BX + cx + 0.85, 60 + 0.35, cz + 0.50), facing=180 - 70)
    PP.head_turn(r, yaw=-10, pitch=-22)
    cam = camera((BX + cx + 1.05, 60 - 1.95, cz + 1.40), (BX + cx + 0.30, 60 + 0.35, cz + 0.95), lens=24)
    cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 2.2; cam.data.dof.aperture_fstop = 4
    al = bpy.data.lights.new('fill', 'AREA'); al.energy = 70; al.size = 2.0; al.color = (1, 0.96, 0.9)
    alo = bpy.data.objects.new('fill', al); alo.location = (BX, 60, cz + 2.55); link(alo)
else:  # exterior (shot 18)
    cam = camera((BX - 16, 60 - 22, 1.6), (BX, 60, 3.9), lens=75)
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 48 if PREV else 160
sc.render.filepath = f'/home/claude/ep03/out/s07{VIEW}' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath=f'/home/claude/ep03/s07{VIEW}.blend')
bpy.ops.render.render(write_still=True)
