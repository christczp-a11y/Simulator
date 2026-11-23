"""Shots 12/13/14/16 from the OpenCourant FE result (60 km/h illustrative): tail coach of 2010 = FE shell mesh,
134 loco = rigid (moves along the track only, as in the solver). No people."""
import sys, math, random
sys.path.insert(0, '/home/claude/ep03')
import bpy, bmesh, numpy as np
from mathutils import Vector, Euler
from lib import *
import world, fe_import as FE
from trains import coach_mats, coach_bogie
PREV = '--final' not in sys.argv
VIEW = sys.argv[sys.argv.index('--view') + 1] if '--view' in sys.argv else 's12'
MS = float(sys.argv[sys.argv.index('--ms') + 1]) if '--ms' in sys.argv else {'s12': 450, 's13': 450, 's14': 160, 's16': 450}[VIEW]
sc = reset()
world.lighting(exposure=-1.6 if VIEW != 's16' else -1.7)
NOSE = FE.loco_front(MS)
world.build(y_min=-150 if VIEW == 's16' else -120, y_max=200 if VIEW == 's16' else 160, quality=0.6 if PREV else 1.0, gap134=NOSE)
if VIEW in ('s12', 's14'): world.ballast_rocks(0.0, -40, 40, 500)
rnd = random.Random(12)
# replace the procedural tail coach with the FE shell
for o in list(bpy.data.objects):
    if o.name == 't2010_0' or o.name.startswith('t2010_0_'): bpy.data.objects.remove(o, do_unlink=True)
m = coach_mats()
mats = {1: m['skin'], 2: m['skin'], 5: m['skin'], 8: m['skin'], 3: m['roof'], 4: m['floor'], 6: m['black'], 7: m['black'], 'default': m['skin']}
objs, nkeep, ndel = FE.coach_mesh(MS, mats)
print('FE frame', MS, 'ms: elements kept', nkeep, 'eroded', ndel, 'loco front', NOSE)
# bogies follow the underframe above them
d = FE.load(); f = FE.frame_at(MS); q = d['quads']; pid = d['part_id']
uf = np.unique(q[np.isin(pid, [6, 7])]); y0 = d['xyz'][0, uf, 1] / 1000.0
for by in (-21.4, -2.6):
    sel = uf[np.abs(y0 - by) < 0.6]
    dy = float((d['xyz'][f, sel, 1] - d['xyz'][0, sel, 1]).mean()) / 1000.0
    dx = float((d['xyz'][f, sel, 0] - d['xyz'][0, sel, 0]).mean()) / 1000.0
    parts = coach_bogie(f'feBg{by:.0f}', 0.0, m)
    for p_ in parts:
        p_.location += Vector((dx, by + dy, 0))
        if by > -5: p_.rotation_euler.z += math.radians(rnd.uniform(-4, 4))
box('feInner', (2.6, 16.5, 2.3), (0, -15.6, 2.45), grime_mat('feInnerM', (0.05, 0.05, 0.055), rough=0.8, amount=0.2, streak=False), bevel=0.0)
for i in range(5):   # under-floor equipment in the uncrushed part
    box(f'feEq{i}', (rnd.uniform(1.0, 2.0), rnd.uniform(0.8, 1.6), rnd.uniform(0.35, 0.5)), (rnd.uniform(-0.3, 0.3), -19.0 + i * 2.4, 0.62), m['black'], bevel=0.03)
dark = grime_mat('debrisDark', (0.10, 0.09, 0.08), rough=0.6, amount=0.4)
glass = mat('debrisGlass', (0.7, 0.75, 0.72), rough=0.05, trans=0.9)
def ico(n, r, loc, mm):
    me = bpy.data.meshes.new(n); bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)
    for v in bm.verts: v.co *= rnd.uniform(0.55, 1.35)
    bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(n, me); link(o); me.materials.append(mm); o.location = loc; return o
c0 = Vector((0, NOSE + 0.6, 2.4))
if VIEW in ('s12', 's13', 's14'):
    # dust volumes at the contact, glass and shards (secondary detail; the structure itself is the FE result)
    dm = bpy.data.materials.new('dust'); dm.use_nodes = True; N = dm.node_tree.nodes; Lk = dm.node_tree.links
    N.remove(N['Principled BSDF']); pv = N.new('ShaderNodeVolumePrincipled'); pv.inputs['Color'].default_value = (0.55, 0.47, 0.38, 1)
    nzd = N.new('ShaderNodeTexNoise'); nzd.inputs['Scale'].default_value = 2.2; nzd.inputs['Detail'].default_value = 6
    rp = N.new('ShaderNodeMapRange'); rp.inputs['From Min'].default_value = 0.52; rp.inputs['From Max'].default_value = 0.78; rp.inputs['To Max'].default_value = 2.0
    Lk.new(nzd.outputs['Fac'], rp.inputs['Value']); Lk.new(rp.outputs['Result'], pv.inputs['Density']); Lk.new(pv.outputs['Volume'], N['Material Output'].inputs['Volume'])
    for k, (dx_, dy_, dz_, rr) in enumerate(((1.9, 0.5, 2.6, 1.2), (2.4, -1.4, 1.2, 1.1), (-2.2, 0.2, 1.6, 1.3))):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=rr, location=(dx_, NOSE + dy_, dz_)); d_ = bpy.context.object; d_.data.materials.append(dm); d_.scale = (0.8, 1.0, 0.7)
    for i in range(70):
        dv = Vector((rnd.gauss(0, 1), rnd.uniform(-0.3, 1.2), rnd.uniform(0.0, 1.0))).normalized()
        p = c0 + dv * rnd.uniform(0.8, 4.0)
        p.x = math.copysign(abs(p.x) + 1.5, p.x)
        gl = rnd.random() < 0.5
        b = ico(f'deb{i}', rnd.uniform(0.02, 0.06) if gl else rnd.uniform(0.04, 0.16), tuple(p), glass if gl else (m['skin'] if rnd.random() < 0.4 else dark))
        b.scale = (1, rnd.uniform(0.3, 1.6), rnd.uniform(0.08, 0.5)); b.rotation_euler = (rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3))
if VIEW == 's14':
    stone = grime_mat('stoneFly', (0.30, 0.28, 0.25), rough=0.8, amount=0.4, streak=False)
    for i in range(140):
        ico(f'bal{i}', rnd.uniform(0.02, 0.05), (rnd.uniform(-2.2, 2.2), NOSE + rnd.uniform(-3.0, 2.0), abs(rnd.gauss(0, 0.5)) - 0.3), stone)
    cam = camera((4.4, NOSE - 10.0, 0.32), (0.4, NOSE + 0.2, 1.5), lens=45)
elif VIEW == 's12':
    cam = camera((24.0, NOSE + 4.5, 4.2), (0.0, NOSE - 0.8, 2.3), lens=70)
elif VIEW == 's13':
    cam = camera((7.0, NOSE + 16.0, 30.0), (0.0, NOSE - 4.0, 1.5), lens=55)
else:
    # aftermath aerial: tail coach crushed in place (FE); next coaches pushed and kinked (illustrative)
    for n, (dx_, rz) in (('t2010_1', (1.2, -4)), ('t2010_2', (0.4, -1.5))):
        o = bpy.data.objects.get(n)
        if o: o.location.x += dx_; o.location.y -= 0.6; o.rotation_euler.z = math.radians(rz)
    cam = camera((30.0, 36.0, 46.0), (0.0, -14.0, 0.0), lens=40)
cam.data.dof.use_dof = VIEW != 's16'; cam.data.dof.focus_distance = (Vector(cam.location) - c0).length; cam.data.dof.aperture_fstop = 2.8 if VIEW == 's14' else 5.6
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 40 if PREV else 128
sc.render.filepath = f'/home/claude/ep03/out/{VIEW}' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath=f'/home/claude/ep03/{VIEW}fe.blend')
bpy.ops.render.render(write_still=True)
