"""F3: brand-style map diorama (paper relief) of the line between El-Ayyat and Al-Raqqa."""
import sys, math, random
sys.path.insert(0, '/home/claude/ep03')
import bpy, bmesh
from mathutils import Vector
from lib import *
PREVIEW = '--final' not in sys.argv
sc = reset()
sc.view_settings.look = 'AgX - Base Contrast'

PAPER=(0.86,0.855,0.84); INK=(0.02,0.02,0.02); GREY=(0.42,0.42,0.42); RED=(0.70,0.04,0.03)
def furrow(name, col, ang):
    m = mat(name, col, rough=0.9); nt=m.node_tree; N=nt.nodes; L=nt.links; b=N['Principled BSDF']
    tc=N.new('ShaderNodeTexCoord'); mp=N.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value[2]=ang
    wv=N.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value=18; wv.wave_profile='SAW'
    L.new(tc.outputs['Object'], mp.inputs['Vector']); L.new(mp.outputs['Vector'], wv.inputs['Vector'])
    bp=N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value=0.25; L.new(wv.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m
paper = mat('paper', PAPER, rough=0.9)
paper2 = furrow('paper2', (0.80,0.79,0.76), 0.0)
paper3 = furrow('paper3', (0.72,0.71,0.68), 1.57)
ink = mat('ink', INK, rough=0.4)
grey = mat('grey', GREY, rough=0.6)
water = mat('water', (0.30,0.31,0.32), rough=0.05, coat=1.0)
red = mat('red', RED, rough=0.35, emit=(1,0.05,0.03), estr=0.0)
white = mat('white', (0.95,0.95,0.94), rough=0.5)

# soft studio world
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.55
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.95,0.94,0.92,1)
sun(28, 250, strength=3.2, color=(1,0.97,0.92), angle=3)

# tile: 1 unit = 100 m. Track runs along Y. Tile 16 x 60 units, thickness 1.2
T = box('tile', (16, 60, 1.2), (0,0,-0.6), paper, bevel=0.05, segs=3)
# field parcels: slightly raised slabs of three paper tones, irregular grid
rnd = random.Random(4)
y = -30
while y < 30:
    h = rnd.uniform(1.5, 4.0)
    for side in (-1, 1):
        x = 0.9 if side>0 else -0.9
        while abs(x) < 7.6:
            wdt = rnd.uniform(1.2, 3.2)
            if abs(x)+wdt > 7.8: wdt = 7.8-abs(x)
            if wdt > 0.4:
                m = rnd.choice([paper, paper2, paper2, paper3])
                cx = x + side*wdt/2
                box('parcel', (wdt-0.08, h-0.08, 0.06+rnd.uniform(0,0.05)), (cx, y+h/2, 0.03), m, bevel=0.015)
            x += side*wdt
    y += h
# canal (Ibrahimiya-like, illustrative) on west side
cv = [Vector((-5.2+math.sin(t*0.13)*0.8, t, 0.02)) for t in range(-30, 31)]
for a,b in zip(cv[:-1], cv[1:]):
    mid=(a+b)/2; d=b-a
    o=box('canal',(0.35, d.length+0.02, 0.04),mid,water,bevel=0); o.rotation_euler=(0,0,math.atan2(-d.x,d.y))
# village blocks
for (vx,vy) in [(-3.0,-12),(3.4,6),(-2.6,18),(4.0,-22)]:
    for k in range(rnd.randint(8,14)):
        hh=rnd.uniform(0.08,0.3)
        box('bld',(rnd.uniform(0.15,0.4),rnd.uniform(0.15,0.4),hh),(vx+rnd.uniform(-1,1),vy+rnd.uniform(-1.2,1.2),hh/2+0.05),white,bevel=0.01)
# palms as small dots
for k in range(140):
    px=rnd.uniform(-7.5,7.5); py=rnd.uniform(-29,29)
    if abs(px)<1.0: continue
    cyl('trunk',0.012,0.16,(px,py,0.13),m=grey,verts=5)
    ico=bpy.data.meshes.new('crown'); import bmesh as _b; bmm=_b.new(); _b.ops.create_icosphere(bmm,subdivisions=1,radius=0.07); bmm.to_mesh(ico); bmm.free()
    co=bpy.data.objects.new('crown',ico); ico.materials.append(grey); co.location=(px,py,0.24); co.scale=(1,1,0.7); link(co)
# track: raised ink line
box('trackbed',(0.42,60,0.10),(0,0,0.05),grey,bevel=0.01)
box('track',(0.10,60,0.04),(0,0,0.12),ink,bevel=0.005)
# stations
for (sy,name) in [(-24,'Kafr Ammar'),(16,'Al-Raqqa')]:
    box('st_'+name,(0.5,1.2,0.22),(0.6,sy,0.13),white,bevel=0.02)
# trains (tiny): 2010 stopped (ink), 134 approaching (red)
# direction: south = -Y? Trains travel south from Kafr Ammar (north) toward Al-Raqqa (south)
box('t2010',(0.16,2.4,0.12),(0,4.0,0.2),ink,bevel=0.02)
box('t134',(0.16,1.6,0.12),(0,-8.0,0.2),red,bevel=0.02)
# signal tower T10 marker (illustrative position)
cyl('t10',0.08,0.5,(0.5,10.5,0.3),m=ink,verts=12)

cam = camera((2.6, 17.0, 8.5), (0.0, -3.0, 0), lens=42)
cam.data.dof.use_dof = True; cam.data.dof.focus_object = bpy.data.objects['t2010']; cam.data.dof.aperture_fstop = 1.4
sc.view_settings.exposure = -0.3
sc.render.resolution_percentage = 50 if PREVIEW else 100
sc.cycles.samples = 24 if PREVIEW else 96
sc.render.filepath = '/home/claude/ep03/out/f3' + ('_prev' if PREVIEW else '') + '.png'
bpy.ops.render.render(write_still=True); print('DONE')
