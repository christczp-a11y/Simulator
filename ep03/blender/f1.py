import sys, math, random
sys.path.insert(0, '/home/claude/ep03')
import bpy
from mathutils import Vector
from lib import *
from props import *

PREVIEW = '--final' not in sys.argv
sc = reset()
random.seed(7)

def ground_mat():
    m = bpy.data.materials.new('soil'); m.use_nodes=True
    nt=m.node_tree; N=nt.nodes; L=nt.links; b=N['Principled BSDF']
    tc=N.new('ShaderNodeTexCoord')
    nz=N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value=0.08; nz.inputs['Detail'].default_value=6
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    rp=N.new('ShaderNodeValToRGB'); e=rp.color_ramp.elements
    e[0].position=0.35; e[0].color=(0.13,0.08,0.045,1); e[1].position=0.65; e[1].color=(0.07,0.11,0.03,1)
    L.new(nz.outputs['Fac'], rp.inputs[0])
    nz2=N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value=3; L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    mx=N.new('ShaderNodeMix'); mx.data_type='RGBA'; mx.inputs['Factor'].default_value=0.25
    L.new(rp.outputs['Color'], mx.inputs['A']); L.new(nz2.outputs['Color'], mx.inputs['B'])
    L.new(mx.outputs['Result'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value=0.95
    bump=N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=0.4
    nz3=N.new('ShaderNodeTexNoise'); nz3.inputs['Scale'].default_value=25; L.new(tc.outputs['Object'], nz3.inputs['Vector'])
    L.new(nz3.outputs['Fac'], bump.inputs['Height']); L.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

sky_world(46, 160, strength=0.3, aerosol=0.9)
sun(elev_deg=46, azim_deg=160, strength=4.5, color=(1.0,0.93,0.82), angle=0.8)

# ground
bpy.ops.mesh.primitive_plane_add(size=1); g = bpy.context.object; g.scale=(3000,3000,1); g.location=(0,0,-0.6)
g.data.materials.append(ground_mat())
# embankment strip
emb = box('emb', (16, 3000, 0.6), (-2.3, 0, -0.9), grime_mat('embsoil',(0.20,0.13,0.075),0.95,amount=0.5,scale=1), bevel=0.3, segs=3)

tuft = grass_tuft(1); tuft.location=(0,0,-500)
bpy.ops.mesh.primitive_plane_add(size=1); gp=bpy.context.object; gp.scale=(3.5,2400,1); gp.location=(4.7,0,-0.59); bpy.ops.object.transform_apply(scale=True)
gp.data.materials.append(bpy.data.materials['embsoil']); gn_scatter(gp, tuft, 5.0, 5, (0.5,1.3), 'tufts')
bpy.ops.mesh.primitive_plane_add(size=1); gp2=bpy.context.object; gp2.scale=(4,2400,1); gp2.location=(-8.5,0,-0.59); bpy.ops.object.transform_apply(scale=True)
gp2.data.materials.append(bpy.data.materials['embsoil']); gn_scatter(gp2, tuft, 1.6, 6, (0.6,1.4), 'tufts2')
mats = M()
track(0.0, -1200, 1500, mats)
track(-4.6, -1200, 1500, mats)

# train 2010 stopped: last coach tail at y=0 facing north, coaches to the south
for i in range(11):
    coach(f'c2010_{i}', -i*24.6, 0.0, 'vip', mats, tail_lamps=(i==0))
# train 134 approaching, ~420 m north
locomotive('loco134', 420.0, 0.0, mats)
for i in range(3):
    coach(f'c134_{i}', 420+20+24.6*(i+1), 0.0, 'improved', mats)

# poles along track (east side)
for y in range(-300, 1500, 50):
    pole((-8.6, y, -0.5))

# vegetation: maize plants scattered with particle hair on field patches
maize = maize_plant(); maize.location=(0,0,-500)
def field(xmin,xmax,ymin,ymax,count,obj,seed):
    bpy.ops.mesh.primitive_plane_add(size=1); f=bpy.context.object
    f.scale=((xmax-xmin),(ymax-ymin),1); f.location=((xmin+xmax)/2,(ymin+ymax)/2,-0.55)
    bpy.ops.object.transform_apply(scale=True)
    f.data.materials.append(bpy.data.materials['soil'])
    gn_scatter(f, obj, count/((xmax-xmin)*(ymax-ymin)), seed)
    return f
dense = 1 if PREVIEW else 1
field(6.5, 60, -420, 700, int(200000*dense), maize, 1)
field(-60, -10.5, -420, 700, int(160000*dense), maize, 2)
field(60, 300, -120, 1400, int(18000*dense), maize, 3)
field(-300, -60, 100, 1400, int(14000*dense), maize, 4)

# palms in clusters
pal = [palm(s) for s in range(5)]
for p in pal: p.location=(0,0,-500)
rnd = random.Random(11)
for cl in [(-25,180),(30,260),(-40,520),(22,640),(-70,900),(90,1100),(-120,760),(140,500),(-160,1300),(45,1350)]:
    for k in range(rnd.randint(3,7)):
        src = rnd.choice(pal)
        inst = bpy.data.objects.new('palm_i', src.data); link(inst)
        inst.location=(cl[0]+rnd.uniform(-9,9), cl[1]+rnd.uniform(-9,9), -0.6)
        inst.rotation_euler=(0,0,rnd.uniform(0,6.28)); s=rnd.uniform(0.8,1.25); inst.scale=(s,s,s)

# village
for i,(x,y,w,d,h) in enumerate([(-55,820,10,9,9),(-68,835,8,12,6),(-48,860,12,8,12),(70,980,9,9,9),(84,1000,11,8,6),(-90,1150,14,10,12),(110,1250,10,10,9)]):
    house(f'h{i}', (x,y,-0.6), (w,d,h), rot=rnd.uniform(-0.2,0.2))

# camera: trackside, beside last coaches of 2010, looking north toward 134
cam = camera((3.6, -175.0, 1.6), (-1.6, 200.0, 3.4), lens=200)
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 170; cam.data.dof.aperture_fstop = 11
sc.view_settings.exposure = -1.6; sc.view_settings.look='AgX - Punchy'
cam.data.shift_y = -0.10
# foreground maize close to lens
for k in range(14):
    fm = bpy.data.objects.new('fgm', maize.data); link(fm)
    fm.rotation_euler = (0, 0, random.uniform(0,6.28))
    fm.location = (random.uniform(7.0, 9.0), -170 + random.uniform(6, 20), -0.55)
    s_ = random.uniform(0.9,1.2); fm.scale=(s_,s_,s_)
vol = box('haze', (6000,6000,300), (0,0,148), None, bevel=0)
vm = bpy.data.materials.new('hazev'); vm.use_nodes=True; nt=vm.node_tree
nt.nodes.remove(nt.nodes['Principled BSDF']); pv=nt.nodes.new('ShaderNodeVolumePrincipled')
pv.inputs['Density'].default_value=0.00015; pv.inputs['Anisotropy'].default_value=0.5; pv.inputs['Color'].default_value=(0.9,0.85,0.78,1)
nt.links.new(pv.outputs[0], nt.nodes['Material Output'].inputs['Volume']); vol.data.materials.append(vm)

if PREVIEW:
    sc.render.resolution_percentage = 50; sc.cycles.samples = 24
else:
    sc.render.resolution_percentage = 100; sc.cycles.samples = 96
sc.render.filepath = '/home/claude/ep03/out/f1' + ('_prev' if PREVIEW else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/f1.blend')
bpy.ops.render.render(write_still=True)
print('DONE')
