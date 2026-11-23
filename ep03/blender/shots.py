"""Animated render driver for EP02 (El-Ayyat). Runs the still scripts in build-only mode, adds animation, renders a
frame sequence (resumable: existing frames are skipped).
usage: blender -b --factory-startup -P shots.py -- <shot> <outdir> [--spp 64] [--scale 1.0] [--frames a-b] [--device OPTIX|CUDA|CPU]"""
import sys, os, math, random, re
sys.path.insert(0, '/home/claude/ep03')
import bpy
from mathutils import Vector, Matrix, Quaternion, Euler
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
SHOT, OUT = argv[0], argv[1]
def opt(k, d):
    return type(d)(argv[argv.index(k) + 1]) if k in argv else d
SPP, SCALE, DEVICE = opt('--spp', 64), opt('--scale', 1.0), opt('--device', 'OPTIX')
FR = opt('--frames', '')
FPS = 30
ROOT = '/home/claude/ep03'
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'

# ---------------------------------------------------------------- helpers
def movers134():
    return [o for o in bpy.data.objects if (o.name == 'l134' or o.name.startswith('t134_')) and o.parent is None]

def key_track(objs, fn, n, axis=1):
    """fn(frame) -> offset along axis (m), relative to current location."""
    for o in objs:
        base = o.location.copy()
        for f in range(1, n + 1):
            o.location = base; o.location[axis] += fn(f); o.keyframe_insert('location', frame=f)
        o.location = base

def smooth_noise(seed, n, freqs=(0.7, 1.9, 4.3, 9.1)):
    rnd = random.Random(seed); ph = [(rnd.uniform(0, 6.28), rnd.uniform(0.5, 1.0)) for _ in freqs]
    return lambda t: sum(a * math.sin(2 * math.pi * fq * t + p) for fq, (p, a) in zip(freqs, ph)) / len(freqs)

def shake(cam, n, amp_deg, seed=1, env=lambda f: 1.0, freqs=(0.7, 1.9, 4.3, 9.1), pos=0.0):
    nx, ny, nz = (smooth_noise(seed + k, n, freqs) for k in range(3))
    px, py, pz = (smooth_noise(seed + 10 + k, n, freqs) for k in range(3))
    for f in range(1, n + 1):
        t = f / FPS; a = math.radians(amp_deg) * env(f)
        cam.delta_rotation_euler = (a * nx(t), a * 0.6 * nz(t), a * 0.5 * ny(t)); cam.keyframe_insert('delta_rotation_euler', frame=f)
        if pos:
            cam.delta_location = (pos * env(f) * px(t), pos * env(f) * py(t), pos * env(f) * pz(t)); cam.keyframe_insert('delta_location', frame=f)

def impact_shake(cam, n, f_hit, amp_deg=1.2, freq=6.0, decay=3.0, slow=1.0, seed=3, base=0.0):
    """Spring-damper camera kick at f_hit; time scaled by 1/slow for slow motion."""
    rnd = random.Random(seed); ph = [rnd.uniform(0, 6.28) for _ in range(3)]
    hf = smooth_noise(seed + 7, n, (11.0, 17.0, 23.0))
    for f in range(1, n + 1):
        t = (f - f_hit) / FPS / slow
        a = math.radians(amp_deg) * (math.exp(-decay * t) * 1.0 if t >= 0 else 0.0)
        hi = math.radians(base)
        cam.delta_rotation_euler = tuple(a * math.sin(2 * math.pi * freq * t + ph[k]) * (1, 0.5, 0.7)[k] + hi * hf(f / FPS / slow) for k in range(3))
        cam.keyframe_insert('delta_rotation_euler', frame=f)

def lerp_key(o, path, a, b, f0, f1, ease=True):
    for f in range(f0, f1 + 1):
        u = (f - f0) / max(1, f1 - f0); u = u * u * (3 - 2 * u) if ease else u
        v = [x + (y - x) * u for x, y in zip(a, b)] if hasattr(a, '__len__') else a + (b - a) * u
        setattr(o, path, v) if not isinstance(path, tuple) else None
        o.keyframe_insert(path, frame=f)

def rigs():
    return [o for o in bpy.data.objects if o.type == 'ARMATURE']

def bone_snap(r, names):
    return {n: (r.pose.bones[n].location.copy(), r.pose.bones[n].rotation_quaternion.copy(), r.pose.bones[n].scale.copy()) for n in names if n in r.pose.bones}

def key_snap(r, snap, f):
    for n, (l, q, s) in snap.items():
        pb = r.pose.bones[n]; pb.rotation_mode = 'QUATERNION'
        pb.location, pb.rotation_quaternion, pb.scale = l, q, s
        pb.keyframe_insert('location', frame=f); pb.keyframe_insert('rotation_quaternion', frame=f); pb.keyframe_insert('scale', frame=f)

FACE = ['eye.L', 'eye.R', 'brow.L', 'brow.R', 'jaw', 'mouth', 'lip.T', 'lip.B', 'lips.L', 'lips.R']
def face_bones(r):
    return [b.name for b in r.pose.bones if b.name in FACE or b.name.startswith(('lip', 'mouth', 'jaw', 'cheek'))]

def idle(r, n, seed, amp=1.0, every=6):
    """Breathing + small head drift added on top of the current pose (keyframed every few frames)."""
    rnd = random.Random(seed)
    names = [x for x in ('chest', 'head', 'neck') if x in r.pose.bones]
    base = {k: r.pose.bones[k].rotation_quaternion.copy() for k in names}
    hn = [smooth_noise(seed + i, n, (0.15, 0.37, 0.8)) for i in range(2)]
    br = rnd.uniform(0.22, 0.30); ph = rnd.uniform(0, 6.28)
    for f in list(range(1, n + 1, every)) + [n]:
        t = f / FPS
        for k in names:
            pb = r.pose.bones[k]; pb.rotation_mode = 'QUATERNION'
            if k == 'chest': d = Quaternion((1, 0, 0), math.radians(1.2 * amp * math.sin(2 * math.pi * br * t + ph)))
            elif k == 'head': d = Quaternion((0, 1, 0), math.radians(3.0 * amp * hn[0](t))) @ Quaternion((1, 0, 0), math.radians(2.0 * amp * hn[1](t)))
            else: d = Quaternion((0, 1, 0), math.radians(1.2 * amp * hn[0](t)))
            pb.rotation_quaternion = base[k] @ d; pb.keyframe_insert('rotation_quaternion', frame=f)
    for k in names: r.pose.bones[k].rotation_quaternion = base[k]

def blinks(r, n, seed):
    rnd = random.Random(seed); f = rnd.randint(8, 50)
    eyes = [x for x in ('eye.L', 'eye.R') if x in r.pose.bones]
    if not eyes: return
    base = {e: r.pose.bones[e].scale.copy() for e in eyes}
    for e in eyes: r.pose.bones[e].keyframe_insert('scale', frame=1)
    while f < n - 4:
        for df, s in ((-1, 1.0), (1, 0.08), (3, 1.0)):
            for e in eyes:
                b = base[e]; r.pose.bones[e].scale = (b[0], b[1], b[2] * s); r.pose.bones[e].keyframe_insert('scale', frame=f + df)
        f += rnd.randint(60, 140)
    for e in eyes: r.pose.bones[e].scale = base[e]

def world_patch(**kw):
    import world
    orig = world.build
    def b(*a, **k):
        k.update(kw); return orig(*a, **k)
    world.build = b

def run_script(path, args, subs=()):
    src = open(os.path.join(ROOT, path)).read()
    src = src.replace("bpy.ops.render.render(write_still=True)", "pass")
    src = re.sub(r"bpy\.ops\.wm\.save_as_mainfile\([^\n]*\)", "pass", src)
    for a, b in subs:
        assert a in src, (path, a); src = src.replace(a, b)
    sys.argv = [path, '--final'] + list(args)
    g = {'__name__': '__main__', '__file__': os.path.join(ROOT, path)}
    exec(compile(src, path, 'exec'), g)
    return g

# ---------------------------------------------------------------- shots
def s_trackside(gap, y_end, n, lens=None, shk=0.0, shk_end=None):
    g = run_script('shot01.py', ['--gap', str(gap)])
    v = (gap - y_end) / (n - 1)
    key_track(movers134(), lambda f: -v * (f - 1), n)
    cam = g['cam']
    if lens:
        for f in (1, n):
            cam.data.lens = lens[0] if f == 1 else lens[1]; cam.data.keyframe_insert('lens', frame=f)
    if shk:
        e = shk_end or shk
        shake(cam, n, 1.0, seed=gap, env=lambda f: shk + (e - shk) * f / n, freqs=(3.1, 7.7, 13.3, 19.9))
    return g

def s_hook(n):
    # v2 opening hook: train 134 closes from 180 m to 30 m; camera slides right and pushes in so the loco is revealed past the coach
    g = s_trackside(180, 30, n, lens=(85, 130), shk=0.01, shk_end=0.12)
    cam = g['cam']; x0 = cam.location.x
    for f in (1, n):
        cam.location.x = x0 if f == 1 else x0 + 1.6; cam.keyframe_insert('location', index=0, frame=f)
    return g

def s_map(view, n):
    import mapscene as M
    sys.argv = ['mapscene.py', '--final']
    sc = M.scene(view, y134=(8.0 if view == 's3' else -4.0))
    grp = [o for o in bpy.data.objects if o.name.startswith(('t134', 'L134'))]
    if view == 's3':
        key_track(grp, lambda f: -1.3 * (f - 1) / (n - 1), n)
        cam = sc.camera; a = cam.location.copy()
        for f in range(1, n + 1):
            u = (f - 1) / (n - 1); cam.location = a + Vector((0.8 * u, -3.0 * u, -1.0 * u)); cam.keyframe_insert('location', frame=f)
    else:
        D = 3.2
        g0 = M.CRASH_Y + 0.25; g1 = -4.0 - 0.25
        ticks = [o for o in bpy.data.objects if o.name.startswith('gapT')]
        bpy.context.view_layer.update()
        wy = lambda o: sum((o.matrix_world @ v.co).y for v in o.data.vertices) / len(o.data.vertices)
        north = max(ticks, key=wy)                       # g1 end, next to train 134
        print('GAPTICKS', [(o.name, round(wy(o), 2)) for o in ticks], 'north', north.name)
        grp.append(north)
        # trains run ALONG the curved rail: each object keeps its offset from the rail and turns with the tangent
        slope = lambda y: (M.rail_x(y + 0.05) - M.rail_x(y - 0.05)) / 0.1
        for o in grp:
            p0 = o.location.copy(); r0 = o.rotation_euler.z; yc = o.matrix_world.translation.y
            for f in range(1, n + 1):
                dy = -D * ((f - 1) / (n - 1)) ** 1.3
                o.location = p0 + Vector((M.rail_x(yc + dy) - M.rail_x(yc), dy, 0))
                o.rotation_euler.z = r0 - (math.atan(slope(yc + dy)) - math.atan(slope(yc)))
                o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_euler', index=2, frame=f)
            o.location = p0; o.rotation_euler.z = r0
        gap = bpy.data.objects.get('gap')
        if gap:   # the curved ribbon is trimmed (not scaled) so it keeps hugging the rail
            ng = bpy.data.node_groups.new('gapCut', 'GeometryNodeTree')
            ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
            ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
            Nn = ng.nodes; gi = Nn.new('NodeGroupInput'); go = Nn.new('NodeGroupOutput')
            pos = Nn.new('GeometryNodeInputPosition'); sep = Nn.new('ShaderNodeSeparateXYZ')
            cmp = Nn.new('FunctionNodeCompare'); cmp.data_type = 'FLOAT'; cmp.operation = 'GREATER_THAN'
            val = Nn.new('ShaderNodeValue'); val.name = 'cut'
            dl = Nn.new('GeometryNodeDeleteGeometry'); dl.domain = 'POINT'
            L = ng.links.new
            L(pos.outputs[0], sep.inputs[0]); L(sep.outputs[1], cmp.inputs[0]); L(val.outputs[0], cmp.inputs[1])
            L(gi.outputs[0], dl.inputs[0]); L(cmp.outputs[0], dl.inputs['Selection']); L(dl.outputs[0], go.inputs[0])
            md = gap.modifiers.new('cut', 'NODES'); md.node_group = ng
            ym = gap.matrix_world.translation.y
            for f in range(1, n + 1):
                u = ((f - 1) / (n - 1)) ** 1.3
                val.outputs[0].default_value = g1 - D * u - ym; val.outputs[0].keyframe_insert('default_value', frame=f)
    return {'cam': sc.camera}

def a_s04(n):
    g = run_script('shot04.py', [], subs=[("(4.4, 278.5), 180, 3)", "(4.4, 278.5), 180, 3)"),
                                          ("(3.3, 289.0), 0, 11)", "(3.3, 289.0), 0, 1)"),
                                          ("(5.3, 295.0), 175, 19)", "(5.3, 295.0), 175, 5)")])
    key_track(movers134(), lambda f: -0.5 * 0.55 * ((f - 1) / FPS) ** 2, n)
    for i, r in enumerate(rigs()):
        if r.name.startswith(('s1', 'st')): idle(r, n, 40 + i); blinks(r, n, 50 + i)
    return g

def a_s05(view, n):
    g = run_script('shot05.py', ['--view', view])
    R = g['R']
    for i, (nm, (r, act, side)) in enumerate(R.items()):
        if view == 'b' and nm == 'p6': continue
        idle(r, n, 10 + i, amp=0.8); blinks(r, n, 20 + i)
    if view == 'a':   # p2 talks: mouth cycles, small hand beat
        r = R['p2'][0]; import people as PP, charsys as C
        fb = face_bones(r); seq = ['talk', 'talkA', 'talk', 'neutral', 'talkA', 'talk', 'neutral', 'neutral']
        for k, f in enumerate(range(1, n + 1, 4)):
            PP.expr(r, seq[k % len(seq)]); key_snap(r, bone_snap(r, fb), f)
        shake(g['cam'], n, 0.12, seed=5, freqs=(0.4, 0.9, 1.7, 3.1), pos=0.004)
    else:             # 5a: p6 turns to the rear window, puzzled -> alert
        r = R['p6'][0]; import people as PP
        names = ['chest', 'neck', 'head'] + face_bones(r)
        B = bone_snap(r, names)
        PP.head_turn(r, pitch=-4); PP.head_turn(r, yaw=68); PP.chest_turn(r, 42); PP.expr(r, 'neutral')
        A = bone_snap(r, names)
        key_snap(r, A, 1); key_snap(r, A, 18)
        for k in B: pass
        key_snap(r, B, 50)
        PP.expr(r, 'alarm', 0.7); C_ = bone_snap(r, face_bones(r)); key_snap(r, C_, 72); key_snap(r, C_, n)
        shake(g['cam'], n, 0.10, seed=6, freqs=(0.4, 0.9, 1.7, 3.1), pos=0.003)
    return g

def a_s06(n):
    world_patch(y_min=60, y_max=520)
    g = run_script('shot06.py', [])
    cam = bpy.context.scene.camera
    for o in movers134() + [cam]:
        o.animation_data_clear()
    for o in movers134() + [cam]:
        o.location.y += 0   # back to frame-1 location already (keyframes cleared)
    V = 100 / 3.6 / FPS
    key_track(movers134() + [cam], lambda f: -V * (f - 1), n)
    shake(cam, n, 0.10, seed=7, freqs=(2.3, 5.1, 9.7, 14.9), pos=0.01)
    return g

def a_s07(view, n):
    g = run_script('shot07.py', ['--view', view])
    cam = g['cam']; a = cam.location.copy()
    d = Vector((0.0, 0.55, 0.0)) if view == 'in' else Vector((2.0, 2.6, 0.0))
    for f in range(1, n + 1):
        u = (f - 1) / (n - 1); cam.location = a + d * u; cam.keyframe_insert('location', frame=f)
    for i, r in enumerate(rigs()): idle(r, n, 70 + i, amp=0.7, every=8); blinks(r, n, 80 + i)
    return g

def a_s08(view, n):
    g = run_script('shot08.py', ['--view', view])
    cam = g['cam']; lo = g['lo']
    mv = [lo, cam] + rigs() + [o for o in bpy.data.objects if o.type == 'LIGHT' and o.name.startswith('Area')]
    if view == 's08':
        r = rigs()[0]; pb = r.pose.bones['hand_ik.L']
        Mt = pb.matrix.copy()
        Mr = Mt.copy(); Mr.translation = Mt.translation + Vector((0.10, 0.30, -0.30))   # rest: hand back on the thigh
        for f, M_ in ((1, Mr), (55, Mr), (92, Mt)):
            pb.matrix = M_; bpy.context.view_layer.update(); pb.keyframe_insert('location', frame=f); pb.keyframe_insert('rotation_quaternion', frame=f)
        Mp = Mt.copy(); Mp.translation = Mt.translation + Vector((0, 0.012, -0.018))
        for f, M_ in ((100, Mp), (108, Mt), (n, Mt)):
            pb.matrix = M_; bpy.context.view_layer.update(); pb.keyframe_insert('location', frame=f); pb.keyframe_insert('rotation_quaternion', frame=f)
        idle(r, n, 90, amp=0.6, every=8)
        key_track(mv, lambda f: -100 / 3.6 / FPS * (f - 1), n)
        shake(cam, n, 0.12, seed=8, freqs=(3.3, 6.1, 11.7, 17.3), pos=0.004)
    elif view == 's11':
        v0, dec = 36.0, 4.5
        key_track(mv, lambda f: -(v0 * ((f - 1) / FPS) - 0.5 * dec * ((f - 1) / FPS) ** 2), n)
        shake(cam, n, 1.0, seed=9, env=lambda f: 0.12 + 0.35 * (f / n) ** 3, freqs=(3.3, 6.1, 11.7, 21.3), pos=0.006)
    else:
        a = cam.location.copy()
        for f in range(1, n + 1):
            u = (f - 1) / (n - 1); cam.location = a + Vector((0.05, -0.12, 0.0)) * u; cam.keyframe_insert('location', frame=f)
    return g

def a_s11a(n):
    """Inside 134 just before impact: emergency braking (~0.15 g). Loose items keep their speed (inertia) and move
    forward (-Y) relative to the decelerating coach; passengers pitch forward and brace. Nothing flies."""
    g = run_script('shot11a.py', [], subs=[('knees=0.36, lean=24)', 'knees=0.36, lean=12)')])
    cam = g['cam']; FZ = g['FZ']; row_y = g['row_y']
    for o in list(bpy.data.objects):     # the coaches ahead would be in the way of a moving train
        if o.name.startswith(('t2010_1', 't2010_2', 't2010_3')): bpy.data.objects.remove(o, do_unlink=True)
    A_ = 0.15 * 9.81; V0 = 25.0; G_ = 9.81; f_b = 4      # braking starts at frame 4
    def rel(f):            # forward displacement of a free object relative to the coach (m)
        t = max(0.0, (f - f_b) / FPS); return 0.5 * A_ * t * t
    # passengers: pitch forward with braking onset (lean ramps in over ~0.35 s, small overshoot)
    for i, r in enumerate(rigs()):
        pb = r.pose.bones['chest']; pb.rotation_mode = 'QUATERNION'; q0 = pb.rotation_quaternion.copy()
        ph = random.Random(i).uniform(-0.05, 0.05)
        for f in range(1, n + 1, 2):
            t = max(0.0, (f - f_b) / FPS - ph)
            on = 1 - math.exp(-t / 0.12); over = 0.12 * math.exp(-t / 0.25) * math.sin(2 * math.pi * 1.6 * t)
            ang = -16.0 * (1 - on - over)       # starts 16 deg more upright than the braced pose
            pb.rotation_quaternion = q0 @ Quaternion((1, 0, 0), math.radians(ang)); pb.keyframe_insert('rotation_quaternion', frame=f)
        pb.rotation_quaternion = q0
        blinks(r, n, 100 + i)
    # bottle slides off the luggage rack, falls under gravity, lands and rolls forward
    bot = bpy.data.objects.get('bottle')
    if bot:
        p0 = Vector((-1.02, row_y(9) - 0.25, FZ + 1.93)); vx = 0.55; t_off = 0.30
        for f in range(1, n + 1):
            t = max(0.0, (f - f_b) / FPS); y = p0.y - rel(f)
            if t < t_off: p = Vector((p0.x + 0.15 * t / t_off, y, p0.z))
            else:
                tf = t - t_off; z = p0.z - 0.5 * G_ * tf * tf
                p = Vector((p0.x + 0.15 + vx * tf, y, max(FZ + 0.035, z)))
            bot.location = p; bot.rotation_euler = Euler((math.radians(90), 0, 0)) if t < t_off else Euler((math.radians(90) + 6 * (t - t_off), 0, 0.3))
            bot.keyframe_insert('location', frame=f); bot.keyframe_insert('rotation_euler', frame=f)
    ph_ = bpy.data.objects.get('phone')
    if ph_:   # phone slides off a seat cushion edge onto the floor
        p0 = Vector((-0.30, row_y(10) - 0.30, FZ + 0.47)); r0 = Euler((0, 0, 0.4))
        for f in range(1, n + 1):
            d = rel(f) * 1.0; p = Vector((p0.x, p0.y - d, p0.z))
            if d > 0.22:
                tf = math.sqrt(2 * (d - 0.22) / A_) if A_ else 0; p.z = max(FZ + 0.006, p0.z - 0.5 * G_ * tf * tf)
            ph_.location = p; ph_.rotation_euler = r0; ph_.keyframe_insert('location', frame=f); ph_.keyframe_insert('rotation_euler', frame=f)
    bag = bpy.data.objects.get('bag')
    if bag:   # bag on the floor in the aisle slides forward (floor friction mu~0.1 -> net 0.05 g)
        p0 = Vector((0.05, row_y(11) - 0.20, FZ + 0.17)); r0 = Euler((0, 0, -0.3))
        for f in range(1, n + 1):
            t = max(0.0, (f - f_b) / FPS); d = 0.5 * 0.05 * 9.81 * t * t
            bag.location = p0 - Vector((0, d, 0)); bag.rotation_euler = r0; bag.keyframe_insert('location', frame=f); bag.keyframe_insert('rotation_euler', frame=f)
    # the whole coach (and everything in it) runs south while braking; windows show the motion
    car = bpy.data.objects.new('carrier', None); bpy.context.scene.collection.objects.link(car)
    inside = [o for o in bpy.data.objects if o.parent is None and o is not car and (o.type in ('ARMATURE', 'CAMERA') or o.name.startswith('t2010_0') or o.name in ('bottle', 'phone', 'bag'))]
    for o in inside:
        o.parent = car
    for f in range(1, n + 1):
        t = (f - 1) / FPS; tb = max(0.0, (f - f_b) / FPS)
        car.location = (0, -(V0 * t - 0.5 * A_ * tb * tb), 0); car.keyframe_insert('location', frame=f)
    shake(cam, n, 0.22, seed=11, freqs=(5.3, 9.1, 14.7, 21.3), pos=0.004)
    bpy.context.scene.render.use_motion_blur = True; bpy.context.scene.render.motion_blur_shutter = 0.5
    return g

def a_fe(view, n, T0, T1):
    """12/13/14/16 from the FE result (shot12fe build) with an animated FE coach."""
    import fe_anim as FA, fe_import as FE
    DT = (T1 - T0) / max(1, n - 1)
    src = open(os.path.join(ROOT, 'shot12fe.py')).read()
    a = src.index('objs, nkeep, ndel = FE.coach_mesh(MS, mats)'); b = src.index('\n', a)
    src = src[:a] + "objs = [FA.build(mats, T0_, DT_, N_)[0]]; nkeep = ndel = 0" + src[b:]
    src = src.replace("NOSE = FE.loco_front(MS)", "NOSE = FE.loco_front(0)")
    src = src.replace("bpy.ops.render.render(write_still=True)", "pass")
    src = re.sub(r"bpy\.ops\.wm\.save_as_mainfile\([^\n]*\)", "pass", src)
    sys.argv = ['shot12fe.py', '--final', '--view', view, '--ms', str(T1)]
    g = {'__name__': '__main__', 'FA': FA, 'T0_': T0, 'DT_': DT, 'N_': n}
    exec(compile(src, 'shot12fe.py', 'exec'), g)
    tr = FA.loco_track(T0, DT, n)
    key_track(movers134(), lambda f: tr[f - 1], n)
    # bogies + inner box follow the coach end approximately: bogies stay (sim keeps them on track)
    # debris: launched from the contact as the crush progresses (ballistic, slow-motion time)
    deb = [o for o in bpy.data.objects if re.match(r'^(deb|bal)\d+$', o.name)]
    rnd = random.Random(31)
    nose = Vector((0, FE.loco_front(0) + tr[-1], 0))
    for o in deb:
        p1 = o.location.copy(); src_p = Vector((math.copysign(1.4, p1.x) if o.name.startswith('deb') else p1.x * 0.3, FE.loco_front(0) + 0.3, 2.2 if o.name.startswith('deb') else 0.0))
        t_launch = rnd.uniform(T0 + 0.1 * (T1 - T0), T0 + 0.6 * (T1 - T0))
        r0 = o.rotation_euler.copy(); spin = Vector((rnd.uniform(-8, 8), rnd.uniform(-8, 8), rnd.uniform(-8, 8)))
        dur = max(0.05, (T1 - t_launch) / 1000.0); grav = Vector((0, 0, -9.81))
        v = (p1 - src_p) / dur - 0.5 * grav * dur           # ballistic: lands on its still position at T1
        for f in range(1, n + 1):
            tm = T0 + (f - 1) * DT
            o.hide_render = tm < t_launch; o.keyframe_insert('hide_render', frame=f)
            if tm < t_launch: continue
            s_ = (tm - t_launch) / 1000.0
            o.location = src_p + v * s_ + 0.5 * grav * s_ * s_; o.keyframe_insert('location', frame=f)
            o.rotation_euler = Euler((r0.x + spin.x * s_, r0.y + spin.y * s_, r0.z + spin.z * s_)); o.keyframe_insert('rotation_euler', frame=f)
    for o in bpy.data.objects:   # dust puffs grow
        if o.type == 'MESH' and o.data.materials and o.data.materials[0] and o.data.materials[0].name.startswith('dust') and view != 's16':
            s1 = o.scale.copy()
            for f in (1, n):
                u = 0.25 if f == 1 else 1.0
                o.scale = s1 * u; o.keyframe_insert('scale', frame=f)
    cam = bpy.context.scene.camera
    if view == 's12':
        key_track([cam], lambda f: 0.75 * tr[f - 1], n)
        impact_shake(cam, n, 6, amp_deg=0.9, freq=5.0, decay=2.0, slow=(T1 - T0) / 1000.0 * FPS / n * 1.0, base=0.12)
    elif view == 's13':
        shake(cam, n, 0.25, seed=13, freqs=(6.1, 11.3, 17.9, 23.1))
    elif view == 's14':
        impact_shake(cam, n, 3, amp_deg=1.4, freq=7.0, decay=2.5, base=0.3)
        bpy.context.scene.render.use_motion_blur = True; bpy.context.scene.render.motion_blur_shutter = 0.5
    elif view == 's16':
        a = cam.location.copy(); tgt = Vector((0.0, -14.0, 0.0))
        for f in range(1, n + 1):
            u = (f - 1) / (n - 1); u = u * u * (3 - 2 * u)
            cam.location = a + Vector((0, 0, 10.0)) * (1 - u) + Vector((-3, 4, 0)) * (1 - u)
            cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler(); cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    return g

def a_s17(n):
    g = run_script('shot17.py', [])
    cam = g['cam']; foc = g['focus']; a = cam.location.copy(); d = (foc - a) * 0.12
    for f in range(1, n + 1):
        u = (f - 1) / (n - 1); cam.location = a + d * u; cam.keyframe_insert('location', frame=f)
        cam.data.dof.focus_distance = (cam.location - foc).length; cam.data.dof.keyframe_insert('focus_distance', frame=f)
    return g

SHOTS = {
    's01': (150, lambda n: s_trackside(760, 640, n)),
    's01h': (150, s_hook),   # v2 hook: train 134 closing from 180 m to 40 m at ~28 m/s
    's02': (120, lambda n: s_trackside(640, 540, n, lens=(85, 102), shk=0.01, shk_end=0.05)),
    's03': (300, lambda n: s_map('s3', n)),
    's04': (105, a_s04),
    's05': (90, lambda n: a_s05('a', n)),
    's05a': (90, lambda n: a_s05('b', n)),
    's06': (195, a_s06),
    's07': (210, lambda n: a_s07('in', n)),
    's08': (195, lambda n: a_s08('s08', n)),
    's09': (120, lambda n: s_trackside(300, 190, n, shk=0.05, shk_end=0.16)),
    's10': (90, lambda n: s_map('s10', n)),
    's11': (90, lambda n: a_s08('s11', n)),
    's11a': (45, a_s11a),
    's12': (120, lambda n: a_fe('s12', n, 0.0, 450.0)),
    's13': (60, lambda n: a_fe('s13', n, 150.0, 450.0)),
    's14': (60, lambda n: a_fe('s14', n, 0.0, 450.0)),
    's16': (180, lambda n: a_fe('s16', n, 450.0, 450.0)),
    's17': (150, a_s17),
    's18': (150, lambda n: a_s07('ext', n)),
    's19': (210, lambda n: a_s08('s19', n)),
}

if __name__ == '__main__':
    n, fn = SHOTS[SHOT]
    print('SHOT', SHOT, n, 'frames')
    fn(n)
    sc = bpy.context.scene
    sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = n
    if FR:
        a, b = FR.split('-'); sc.frame_start, sc.frame_end = int(a), int(b)
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    sc.render.resolution_percentage = int(100 * SCALE)
    sc.cycles.samples = SPP; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    if DEVICE != 'CPU':
        p = bpy.context.preferences.addons['cycles'].preferences; p.compute_device_type = DEVICE; p.get_devices()
        for d in p.devices: d.use = d.type == DEVICE
        sc.cycles.device = 'GPU'; sc.cycles.denoiser = 'OPENIMAGEDENOISE'; sc.cycles.denoising_use_gpu = True   # OptiX denoiser fails to initialise on Colab L4; OIDN runs on the GPU too
    sc.render.use_persistent_data = False
    if '--persist' in argv: sc.render.use_persistent_data = True
    if '--eevee' in argv: sc.render.engine = 'BLENDER_EEVEE'
    BENCH = opt('--bench', '')
    if BENCH:   # timing: frame start -> first sample message = scene sync; -> render_post = total
        import time as _t
        _st = {}
        def _pre(s, *a): _st['t0'] = _t.time(); _st['s'] = None
        def _stats(txt, *a):
            if _st.get('s') is None and ('Sample' in str(txt) or 'Rendering' in str(txt)): _st['s'] = _t.time()
        def _post(s, *a):
            t1 = _t.time(); sync = (_st['s'] or t1) - _st['t0']
            print(f"BENCH {BENCH} {SHOT} frame {s.frame_current} total {t1 - _st['t0']:.1f}s sync {sync:.1f}s", flush=True)
        bpy.app.handlers.render_pre.append(_pre); bpy.app.handlers.render_stats.append(_stats); bpy.app.handlers.render_post.append(_post)
    if BENCH == 'B':   # render method v3 candidate: low spp + OIDN + bounce limits + persistent data
        sc.cycles.samples = 24; sc.cycles.adaptive_threshold = 0.02
        sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2; sc.cycles.transparent_max_bounces = 8
        sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
        sc.render.use_persistent_data = True
    if BENCH == 'C':   # EEVEE configured to match the Cycles look
        sc.render.engine = 'BLENDER_EEVEE'
        ee = sc.eevee
        for k, v in dict(use_raytracing=True, ray_tracing_method='SCREEN', use_shadows=True, shadow_ray_count=2,
                         shadow_step_count=8, shadow_resolution_scale=1.0, taa_render_samples=32,
                         use_volumetric_shadows=True, fast_gi_method='GLOBAL_ILLUMINATION', use_fast_gi=True,
                         volumetric_end=3000.0).items():
            if hasattr(ee, k):
                try: setattr(ee, k, v)
                except Exception as e: print('EEVEE SET FAIL', k, e)
            else: print('EEVEE NO ATTR', k)
        for o in bpy.data.objects:
            if o.type == 'LIGHT':
                o.data.use_shadow = True
                if o.data.type == 'SUN' and hasattr(o.data, 'shadow_maximum_resolution'): o.data.shadow_maximum_resolution = 0.001
                print('LIGHT', o.name, o.data.type, getattr(o.data, 'angle', None), o.data.energy)
            if o.name == 'haze': o.hide_render = True          # the 3 km haze box fogs EEVEE grey and swallows the sun shadows
        if sc.world and hasattr(sc.world, 'use_sun_shadow'): sc.world.use_sun_shadow = True
        if '--probe' in argv:   # interiors: irradiance volume around the camera, baked
            cam = sc.camera
            bpy.ops.object.lightprobe_add(type='VOLUME', location=cam.matrix_world.translation)
            pr = bpy.context.object; pr.scale = (8, 30, 4)
            try: bpy.ops.object.lightprobe_cache_bake(subset='ALL')
            except Exception as e: print('PROBE BAKE FAILED', e)
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_depth = '8'
    os.makedirs(f'{OUT}/{SHOT}', exist_ok=True)
    sc.render.filepath = f'{OUT}/{SHOT}/{SHOT}_'
    sc.render.use_overwrite = False; sc.render.use_placeholder = False
    if '--save' in argv: bpy.ops.wm.save_as_mainfile(filepath=f'{OUT}/{SHOT}.blend')
    if '--norender' in argv: sys.exit(0)
    PICK = opt('--pick', '')
    if PICK:
        for f in [int(x) for x in PICK.split(',')]:
            sc.frame_set(f); sc.render.filepath = f'{OUT}/{SHOT}/{SHOT}_{f:04d}.png'; bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
    print('DONE', SHOT)
