import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from lib import *
import world
PREV = '--final' not in sys.argv
sc = reset()
world.lighting(exposure=-1.9)
GAP = float(sys.argv[sys.argv.index('--gap')+1]) if '--gap' in sys.argv else 450
NAME = 's09' if GAP < 400 else 's01'
W = world.build(y_min=-150, y_max=900, quality=0.8 if PREV else 1.0, gap134=GAP)
world.ballast_rocks(0.0, -150, 40, 700 if PREV else 1100)
world.ballast_rocks(-4.6, -120, 60, 300, 3)
cam = camera((2.45, -46.0, 0.45), (-0.35, GAP, 1.6 if GAP >= 400 else 1.9), lens=85)
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 30 if GAP >= 400 else GAP + 40; cam.data.dof.aperture_fstop = 8
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 32 if PREV else 128
sc.render.filepath = f'/home/claude/ep03/out/{NAME}' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath=f'/home/claude/ep03/{NAME}.blend')
bpy.ops.render.render(write_still=True)
