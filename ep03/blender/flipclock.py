"""End card (shot 20): mechanical flip clock 00:03 -> 00:00, transparent background, composited in Remotion
over the channel's halftone backdrop.  usage: python flipclock.py -- <outdir> [--spp 96] [--scale 1] [--device OPTIX] [--pick 1,40]"""
import sys, os, math, random
import bpy, bmesh
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = argv[0] if argv else '/tmp/claude-0/fc'
def opt(k, d): return type(d)(argv[argv.index(k) + 1]) if k in argv else d
SPP, SCALE, DEVICE, PICK = opt('--spp', 96), opt('--scale', 1.0), opt('--device', 'OPTIX'), opt('--pick', '')
TEX = '/home/claude/ep03/assets/tex/flip'
FPS, N = 30, 150
FLIPS = [(15, 3, 2), (45, 2, 1), (75, 1, 0)]        # (start frame, from, to) on the last digit
FLIP_DUR = 7                                        # frames for the leaf to fall (~0.23 s)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, N

# ------------------------------------------------------------------ materials
def img_mat(name, path, flipv=False):
    m = bpy.data.materials.new(name); m.use_nodes = True; T = m.node_tree; Nd = T.nodes
    b = Nd['Principled BSDF']; b.inputs['Roughness'].default_value = 0.42
    b.inputs['Specular IOR Level'].default_value = 0.35
    t = Nd.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path); t.extension = 'EXTEND'
    uv = Nd.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'
    if flipv:
        mp = Nd.new('ShaderNodeMapping'); mp.inputs['Location'].default_value[1] = 1; mp.inputs['Scale'].default_value[1] = -1
        T.links.new(uv.outputs[0], mp.inputs[0]); T.links.new(mp.outputs[0], t.inputs[0])
    else:
        T.links.new(uv.outputs[0], t.inputs[0])
    T.links.new(t.outputs[0], b.inputs['Base Color'])
    return m

def flat_mat(name, col, rough=0.35, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1); b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal; b.inputs['Coat Weight'].default_value = coat
    return m

M = {}
for d in range(10):
    for h in ('top', 'bot'):
        M[f'{d}{h}'] = img_mat(f'd{d}{h}', f'{TEX}/{d}_{h}.png')
        M[f'{d}{h}v'] = img_mat(f'd{d}{h}v', f'{TEX}/{d}_{h}.png', flipv=True)
body = flat_mat('body', (0.012, 0.012, 0.013), 0.28, coat=0.6)
edge = flat_mat('edge', (0.03, 0.03, 0.032), 0.5)
metal = flat_mat('metal', (0.55, 0.55, 0.56), 0.3, metal=1.0)
slot = flat_mat('slot', (0.002, 0.002, 0.002), 0.8)

# ------------------------------------------------------------------ geometry
CW, HH, GAP = 0.38, 0.36, 0.004          # card width, half height, hinge gap (each side)
R = 0.025                                # card corner radius

def half_plane(name, mat, x, top=True, back=False):
    """Card half in XZ (faces -Y). Origin at hinge line (z=0) so leaves rotate about X."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    z0, z1 = (GAP, HH) if top else (-HH, -GAP)
    # rounded outer corners only
    pts = []
    zo = z1 if top else z0; zi = z0 if top else z1
    sgn = 1 if top else -1
    pts.append((-CW / 2, zi))
    for k in range(7):
        a = math.pi / 2 * k / 6
        cx, cz = -CW / 2 + R, zo - sgn * R
        pts.append((cx - R * math.cos(a), cz + sgn * R * math.sin(a)))
    for k in range(7):
        a = math.pi / 2 * k / 6
        cx, cz = CW / 2 - R, zo - sgn * R
        pts.append((cx + R * math.sin(a), cz + sgn * R * math.cos(a)))
    pts.append((CW / 2, zi))
    if not top: pts.reverse()
    yy = 0.0006 if back else 0.0
    vs = [bm.verts.new((x + px, yy, pz)) for px, pz in pts]
    f = bm.faces.new(vs if not back else list(reversed(vs)))
    for l in f.loops:
        px, pz = l.vert.co.x - x, l.vert.co.z
        u = (px + CW / 2) / CW
        v = (pz - (-HH if not top else 0)) / HH if top else (pz + HH) / HH
        if top: v = pz / HH
        l[uvl].uv = (u, v)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); me.materials.append(mat)
    return o

def rbox(name, size, loc, mat, bev=0.02, seg=4):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); o.location = loc
    me.materials.append(mat)
    b = o.modifiers.new('bev', 'BEVEL'); b.width = bev; b.segments = seg; b.limit_method = 'ANGLE'
    for p in me.polygons: p.use_smooth = True
    return o

PAIR_GAP, COLON = 0.03, 0.15
xs = []
x = -(4 * CW + 2 * PAIR_GAP + COLON) / 2 + CW / 2
for i in range(4):
    xs.append(x); x += CW + (PAIR_GAP if i in (0, 2) else COLON)

# housing: one slab per digit pair, rounded, with a recessed dark window; joined by a colon bridge
# one housing for all four cards (as on the channel banner); pins on both sides of every card
cx = (xs[0] + xs[3]) / 2; w = xs[3] - xs[0] + CW + 0.13
rbox('house', (w, 0.20, 2 * HH + 0.13), (cx, 0.125, 0.0), body, bev=0.07, seg=8)
rbox('axle', (w - 0.06, 0.006, 0.006), (cx, 0.006, 0), slot, bev=0.002, seg=2)
for i, x in enumerate(xs):
    for sx in (-1, 1):
        rbox(f'pin{i}{sx}', (0.022, 0.03, 0.05), (x + sx * (CW / 2 + 0.009), 0.0, 0), metal, bev=0.009)
# colon dots
cxc = (xs[1] + xs[2]) / 2
for k, zz in enumerate((0.13, -0.13)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.024, location=(cxc, 0.0, zz), segments=24, ring_count=12)
    o = bpy.context.object; o.name = f'colon{k}'; o.scale.y = 0.4
    o.data.materials.append(bpy.data.materials.get('dot') or flat_mat('dot', (0.92, 0.92, 0.90), 0.4))
    for p in o.data.polygons: p.use_smooth = True
COLON_OBJS = [bpy.data.objects['colon0'], bpy.data.objects['colon1']]

# cards: stacked leaves behind each card add mechanical depth
def leaf_stack(x):
    for j in range(1, 4):
        for top in (True, False):
            o = half_plane(f'stack{x:.2f}{j}{top}', edge, x, top)
            o.location.y = 0.004 * j; o.location.z += (-0.0025 if top else 0.0025) * j * 0

def static_card(x, d, key=''):
    t = half_plane(f'top{key}{d}', M[f'{d}top'], x, True); b = half_plane(f'bot{key}{d}', M[f'{d}bot'], x, False)
    return t, b

def vis(o, f_on, f_off):
    """visible on [f_on, f_off)"""
    for f, h in ((1, not (f_on <= 1 < f_off)), (f_on, False), (f_off, True)):
        if f < 1: continue
        o.hide_render = h; o.hide_viewport = h; o.keyframe_insert('hide_render', frame=f); o.keyframe_insert('hide_viewport', frame=f)

for i, x in enumerate(xs):
    leaf_stack(x)
    if i < 3:
        static_card(x, 0, key=f'c{i}')

# last digit: top halves switch to the next number as the leaf starts; bottom halves switch when it lands
x3 = xs[3]
times = [1] + [f for f, _, _ in FLIPS] + [N + 1]
digits = [FLIPS[0][1]] + [b for _, _, b in FLIPS]
for k, d in enumerate(digits):
    t = half_plane(f'top3_{d}', M[f'{d}top'], x3, True)
    vis(t, times[k], times[k + 1])
    b = half_plane(f'bot3_{d}', M[f'{d}bot'], x3, False)
    b_on = times[k] + (FLIP_DUR if k else 0); b_off = times[k + 1] + FLIP_DUR if k + 1 < len(times) - 1 else N + 1
    vis(b, b_on, b_off)

def leaf_angle(u):
    """Gravity-driven fall: angle ~ u^2 (constant angular accel from rest), then a small damped bounce on the stop."""
    if u <= 1.0: return math.pi * u * u
    t = (u - 1.0) * FLIP_DUR / FPS
    return math.pi - math.radians(9) * math.exp(-28 * t) * abs(math.sin(2 * math.pi * 9 * t))

for f0, a, b in FLIPS:
    piv = bpy.data.objects.new(f'leaf{a}', None); sc.collection.objects.link(piv); piv.location = (0, -0.0015, 0)
    fr = half_plane(f'leafF{a}', M[f'{a}top'], x3, True); fr.parent = piv
    bk = half_plane(f'leafB{a}', M[f'{b}botv'], x3, True, back=True); bk.parent = piv
    for f in range(1, N + 1):
        u = (f - f0) / FLIP_DUR
        piv.rotation_euler.x = 0 if u < 0 else leaf_angle(u)
        piv.keyframe_insert('rotation_euler', index=0, frame=f)
    for o in (fr, bk): vis(o, f0, f0 + FLIP_DUR + 8)

# the last flip lands the clock on 00:00: the colon turns red
red = flat_mat('red', (0.68, 0.016, 0.012), 0.38)
for o in COLON_OBJS:
    o.data.materials.clear(); o.data.materials.append(bpy.data.materials['dot']); o.data.materials.append(red)
    for p in o.data.polygons: p.material_index = 0
    # swap via hide: duplicate red dot
    r = o.copy(); r.data = o.data.copy(); sc.collection.objects.link(r)
    for p in r.data.polygons: p.material_index = 1
    r.name = o.name + 'R'
    land = FLIPS[-1][0] + FLIP_DUR
    vis(o, 1, land); vis(r, land, N + 1)

# ------------------------------------------------------------------ rig: the whole clock on a root so it can react
root = bpy.data.objects.new('clock', None); sc.collection.objects.link(root)
for o in list(sc.objects):
    if o.parent is None and o is not root and o.type in ('MESH', 'EMPTY'):
        o.parent = root
# the clock rests on a table we never see: each leaf landing gives the body a tiny reaction rock (stiff rubber feet)
for f in range(1, N + 1):
    rx = 0.0
    for f0, _, _ in FLIPS:
        t = (f - (f0 + FLIP_DUR)) / FPS
        if t >= 0: rx += math.radians(0.35 if f0 != FLIPS[-1][0] else 0.7) * math.exp(-16 * t) * math.sin(2 * math.pi * 7 * t)
    root.rotation_euler = (rx, 0, 0); root.keyframe_insert('rotation_euler', frame=f)
root.location = (0, 0, 0.25)

# ------------------------------------------------------------------ camera + light
cam_d = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam_d.lens = 85; cam_d.sensor_fit = 'HORIZONTAL'; cam_d.sensor_width = 36
cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = 8.0
tgt = bpy.data.objects.new('tgt', None); sc.collection.objects.link(tgt); tgt.location = (0, 0, 0.25)
cam_d.dof.focus_object = tgt
c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
# slow orbit + push-in over the card; a slight settle after the final flip
for f in range(1, N + 1):
    u = (f - 1) / (N - 1); e = u * u * (3 - 2 * u)
    ang = math.radians(-16 + 10 * e)
    dist = 7.4 - 0.7 * e
    cam.location = (dist * math.sin(ang), -dist * math.cos(ang), 0.25 + 0.95 - 0.25 * e)
    cam.keyframe_insert('location', frame=f)

def area(name, loc, size, energy, col=(1, 1, 1), rot=None):
    l = bpy.data.lights.new(name, 'AREA'); l.size = size; l.energy = energy; l.color = col
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
    tc = o.constraints.new('TRACK_TO'); tc.target = tgt; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
    return o
area('key', (-2.5, -3.5, 3.2), 3.0, 900)
area('fill', (3.5, -2.5, 0.6), 4.0, 220, (0.95, 0.97, 1.0))
area('top', (0.0, 0.5, 3.5), 2.5, 380)
area('rim', (2.0, 2.5, 1.5), 1.5, 500)
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.9, 0.9, 0.9, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.35

# ------------------------------------------------------------------ render
r = sc.render; r.engine = 'CYCLES'; r.film_transparent = True
r.resolution_x, r.resolution_y = 1080, 1920; r.resolution_percentage = int(100 * SCALE)
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGBA'
r.use_motion_blur = True; r.motion_blur_shutter = 0.5
sc.cycles.samples = SPP; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
if DEVICE != 'CPU':
    pr = bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type = DEVICE; pr.get_devices()
    for dv in pr.devices: dv.use = True
    sc.cycles.device = 'GPU'; sc.cycles.denoiser = 'OPENIMAGEDENOISE'; sc.cycles.denoising_use_gpu = True   # OptiX denoiser fails to initialise on Colab L4; OIDN runs on the GPU too
os.makedirs(f'{OUT}/s20', exist_ok=True)
frames = [int(v) for v in PICK.split(',')] if PICK else range(1, N + 1)
for f in frames:
    p = f'{OUT}/s20/s20_{f:04d}.png'
    if os.path.exists(p): continue
    sc.frame_set(f); r.filepath = p; bpy.ops.render.render(write_still=True)
