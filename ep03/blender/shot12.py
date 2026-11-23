"""Shot 12 still: side view at the instant 134's nose rides into 2010's tail coach. Structure only, no people."""
import sys, math, random
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector, Matrix
from lib import *
import world
PREV = '--final' not in sys.argv
VIEW = sys.argv[sys.argv.index('--view')+1] if '--view' in sys.argv else 's12'
sc = reset()
world.lighting(exposure=-1.6)
NOSE = -3.6
W = world.build(y_min=-120, y_max=160, quality=0.6 if PREV else 1.0, gap134=NOSE)
world.ballast_rocks(0.0, -40, 40, 500)
rnd = random.Random(12)
# --- 134 rides up: lift + pitch nose-up about its front
lift, pitch = 1.35, math.radians(-5.5)
for o in list(bpy.data.objects):
    if o.name == 'l134' or o.name.startswith('t134_'):
        if o.parent: continue
        p = o.location.copy() - Vector((0, NOSE, 0))
        R = Matrix.Rotation(pitch, 3, 'X'); p = R @ p
        o.location = p + Vector((0, NOSE, lift)); o.rotation_euler.x += pitch
# --- crush the tail coach's rear 4.5 m (2010 coach: rear end at y=0)
t = bpy.data.objects['t2010_0']
for mo in list(t.modifiers):
    try:
        bpy.context.view_layer.objects.active = t; bpy.ops.object.modifier_apply(modifier=mo.name)
    except Exception: pass
M = t.matrix_world; Mi = M.inverted(); L0 = 6.0; END = NOSE + 0.9
import bmesh
bm = bmesh.new(); bm.from_mesh(t.data)
for v in bm.verts:
    w = M @ v.co
    if w.y > -L0:
        s = (w.y + L0) / L0
        w.y = -L0 + (w.y + L0) * ((END + L0) / L0)        # crushed so the old rear end sits at END
        fold = abs(math.sin(s * math.pi * 4.5))           # accordion folds in the side panels
        w.x *= 1 + (0.06 + 0.16 * fold) * s ** 0.7 + rnd.uniform(-0.03, 0.03) * s
        w.z += (-0.30 * fold * s if w.z > 2.2 else 0.12 * fold * s) + rnd.uniform(-0.06, 0.06) * s
        if w.z > 2.6: w.y -= 0.8 * s * s; w.z += 0.9 * s * s     # roof buckles up where the nose drives under it     # roof peels up and back
        v.co = Mi @ w
# tear open the end where the loco nose has entered: delete upper faces in the last 1.6 m
gone = [f for f in bm.faces if (M @ f.calc_center_median()).y > END - 1.6 and (M @ f.calc_center_median()).z > 1.45 + rnd.uniform(0, 0.5)]
bmesh.ops.delete(bm, geom=gone, context='FACES')
bm.to_mesh(t.data); bm.free()
def ico(n, r, loc, m):
    me = bpy.data.meshes.new(n); bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)
    for v in bm.verts: v.co *= rnd.uniform(0.55, 1.35)
    bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(n, me); link(o); me.materials.append(m); o.location = loc; return o
# dust: three noisy volume puffs at the contact
dm = bpy.data.materials.new('dust'); dm.use_nodes = True; N = dm.node_tree.nodes; Lk = dm.node_tree.links
N.remove(N['Principled BSDF']); pv = N.new('ShaderNodeVolumePrincipled'); pv.inputs['Color'].default_value = (0.55, 0.47, 0.38, 1)
nzd = N.new('ShaderNodeTexNoise'); nzd.inputs['Scale'].default_value = 2.2; nzd.inputs['Detail'].default_value = 6
rp = N.new('ShaderNodeMapRange'); rp.inputs['From Min'].default_value = 0.5; rp.inputs['From Max'].default_value = 0.75; rp.inputs['To Max'].default_value = 3.0
Lk.new(nzd.outputs['Fac'], rp.inputs['Value']); Lk.new(rp.outputs['Result'], pv.inputs['Density']); Lk.new(pv.outputs['Volume'], N['Material Output'].inputs['Volume'])
for k, (dx_, dy_, dz_, rr) in enumerate(((1.6, 0.3, 2.4, 1.5), (2.2, -1.2, 1.4, 1.3), (1.2, 1.2, 0.8, 1.8))):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=rr, location=(dx_, NOSE + dy_, dz_)); d_ = bpy.context.object; d_.data.materials.append(dm); d_.scale = (1.0, 0.8, 0.6)
# --- flying debris: dark structural shards + glass
dark = grime_mat('debrisDark', (0.10, 0.09, 0.08), rough=0.6, amount=0.4)
skin = bpy.data.materials.get('coachSkin') or dark
glass = mat('debrisGlass', (0.7, 0.75, 0.72), rough=0.05, trans=0.9)
c0 = Vector((0, NOSE + 0.4, 2.6))
for i in range(90):
    d = Vector((rnd.gauss(0, 1), rnd.uniform(0.2, 1.5), rnd.uniform(0.1, 1.2))).normalized()
    r = rnd.uniform(0.6, 4.5)
    p = c0 + d * r
    if rnd.random() < 0.5: p.x = math.copysign(abs(p.x) + 1.4, p.x)
    gl = rnd.random() < 0.45
    sz = rnd.uniform(0.02, 0.08) if gl else rnd.uniform(0.04, 0.22)
    b = ico(f'deb{i}', sz, tuple(p), glass if gl else (skin if rnd.random() < 0.4 else dark))
    b.scale = (1, rnd.uniform(0.3, 1.6), rnd.uniform(0.08, 0.5))
    b.rotation_euler = (rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3))
if VIEW == 's14':
    stone = grime_mat('stoneFly', (0.30, 0.28, 0.25), rough=0.8, amount=0.4, streak=False)
    for i in range(160):
        p = Vector((rnd.uniform(-2.2, 2.2), rnd.uniform(-6.5, -1.0), abs(rnd.gauss(0, 0.6)) - 0.35))
        ico(f'bal{i}', rnd.uniform(0.02, 0.05), tuple(p), stone)
    cam = camera((2.7, -19.0, 0.30), (-0.2, -3.0, 0.9), lens=40)
elif VIEW == 's12':
    cam = camera((24.0, 1.5, 4.2), (0.0, -4.4, 2.6), lens=85)
else:   # s13 top-down
    cam = camera((6.0, 14.0, 34.0), (0.0, -6.0, 1.0), lens=50)
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = (Vector(cam.location) - c0).length; cam.data.dof.aperture_fstop = 2.8 if VIEW == 's14' else 5.6
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 40 if PREV else 128
sc.render.filepath = f'/home/claude/ep03/out/{VIEW}' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath=f'/home/claude/ep03/{VIEW}.blend')
bpy.ops.render.render(write_still=True)
