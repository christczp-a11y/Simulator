"""Shot 6: 134 running along the fields, tracking camera alongside (motion blur from real speed)."""
import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
from lib import *
import world
PREV = '--final' not in sys.argv
sc = reset()
world.lighting(exposure=-1.6)
G = 300.0
world.build(y_min=150, y_max=500, quality=0.7 if PREV else 1.0, gap134=G)
world.ballast_rocks(0.0, 240, 330, 500)
sc.render.fps = 25
V = 100 / 3.6 / sc.render.fps          # ~100 km/h per frame (speed not published: illustrative)
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
movers = [o for o in bpy.data.objects if (o.name == 'l134' or o.name.startswith('t134_')) and o.parent is None]
cam = camera((6.8, G - 5.0, 1.9), (0.0, G + 9.0, 2.5), lens=30)
movers.append(cam)
for o in movers:
    o.keyframe_insert('location', frame=1)
    o.location.y -= V * 2; o.keyframe_insert('location', frame=3)
    for fc in (o.animation_data.action.fcurves if hasattr(o.animation_data.action, 'fcurves') else []):
        for k in fc.keyframe_points: k.interpolation = 'LINEAR'
sc.frame_set(2)
sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.5
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 48 if PREV else 160
sc.render.filepath = '/home/claude/ep03/out/s06' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/s06.blend')
bpy.ops.render.render(write_still=True)
