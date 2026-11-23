"""Props: coach, locomotive, track, vegetation, buildings, poles."""
import bpy, bmesh, math, random
from mathutils import Vector
from lib import *

def corrugated_steel(name='VIPsteel'):
    m = bpy.data.materials.get(name)
    if m: return m
    m = grime_mat(name, (0.74,0.75,0.76), rough=0.22, metal=1.0, dirt=(0.32,0.26,0.20), amount=0.35, scale=2.5)
    nt = m.node_tree; N = nt.nodes; L = nt.links; b = N['Principled BSDF']
    tc = [n for n in N if n.type=='TEX_COORD'][0]
    wv = N.new('ShaderNodeTexWave'); wv.wave_type='BANDS'; wv.bands_direction='Y'; wv.wave_profile='SIN'
    wv.inputs['Scale'].default_value = 0.0  # set via mapping
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1,1,1)
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    # ribs along length (object Y) every 6 cm -> sin of y
    mul = N.new('ShaderNodeMath'); mul.operation='MULTIPLY'; mul.inputs[1].default_value = 2*math.pi/0.06
    L.new(sep.outputs['Y'], mul.inputs[0])
    s = N.new('ShaderNodeMath'); s.operation='SINE'; L.new(mul.outputs[0], s.inputs[0])
    # only on lower body (z<0.9 local) -> mask
    gt = N.new('ShaderNodeMath'); gt.operation='LESS_THAN'; gt.inputs[1].default_value = -0.35
    L.new(sep.outputs['Z'], gt.inputs[0])
    mk = N.new('ShaderNodeMath'); mk.operation='MULTIPLY'; L.new(s.outputs[0], mk.inputs[0]); L.new(gt.outputs[0], mk.inputs[1])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.35; bump.inputs['Distance'].default_value=0.01
    L.new(mk.outputs[0], bump.inputs['Height'])
    old = b.inputs['Normal'].links[0].from_node if b.inputs['Normal'].links else None
    if old: L.new(old.outputs['Normal'], bump.inputs['Normal'])
    L.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def M():
    return dict(
        steel=corrugated_steel(),
        band=grime_mat('band', (0.55,0.06,0.05), rough=0.35, coat=0.3, amount=0.3),
        glass=mat('glass', (0.005,0.007,0.008), rough=0.03, metal=0.0, coat=1.0),
        dark=grime_mat('darkmetal', (0.05,0.05,0.05), rough=0.6, metal=0.6, amount=0.5),
        rubber=mat('rubber', (0.02,0.02,0.02), rough=0.8),
        roof=grime_mat('roof', (0.45,0.46,0.47), rough=0.55, metal=0.6, amount=0.7, dirt=(0.22,0.18,0.13)),
        tail=mat('taillamp', (0.4,0.0,0.0), rough=0.2, emit=(1,0.05,0.02), estr=0.0),
        head=mat('headlamp', (1,1,0.9), rough=0.2, emit=(1,0.95,0.8), estr=60.0),
        white=grime_mat('white134', (0.80,0.80,0.78), rough=0.4, coat=0.2, amount=0.35),
        red=grime_mat('red134', (0.50,0.05,0.04), rough=0.35, coat=0.2, amount=0.3),
        blue=grime_mat('locoblue', (0.05,0.12,0.30), rough=0.45, coat=0.2, amount=0.5),
        yellow=grime_mat('locoyellow', (0.75,0.55,0.05), rough=0.45, amount=0.5),
    )

def coach(name, y0, x=0.0, style='vip', mats=None, tail_lamps=False, length=24.0):
    """Coach centred on track x, spanning y0-length .. y0 (front end at y0). Floor at z=1.15 above rail top (0)."""
    m = mats or M(); parts = []
    W, H, z0 = 2.95, 2.9, 1.15
    cy = y0 - length/2
    body_m = m['steel'] if style=='vip' else m['white']
    parts.append(box(name+'_body', (W, length, H), (x, cy, z0+H/2), body_m, bevel=0.10, segs=3))
    # roof (rounded) - flattened cylinder
    r = cyl(name+'_roof', W/2, length-0.2, (x, cy, z0+H-0.05), rot=(math.pi/2,0,0), m=m['roof'], verts=32)
    r.scale = (1, 0.18, 1); parts.append(r)
    # window band + windows on both sides
    band_m = m['band']
    for s in (-1, 1):
        parts.append(box(name+f'_band{s}', (0.02, length-0.6, 0.12), (x+s*(W/2+0.005), cy, z0+0.85), band_m, bevel=0.005))
        n = 9 if style=='vip' else 10
        for i in range(n):
            wy = y0 - 2.0 - i*(length-4.0)/(n-1)
            parts.append(box(name+f'_w{s}{i}', (0.03, 1.45, 0.82), (x+s*(W/2+0.004), wy, z0+1.55), m['glass'], bevel=0.06, segs=3))
            parts.append(box(name+f'_wf{s}{i}', (0.025, 1.52, 0.89), (x+s*(W/2-0.003), wy, z0+1.55), m['dark'], bevel=0.05, segs=2))
        # doors near ends
        for dy in (y0-0.9, y0-length+0.9):
            parts.append(box(name+f'_door{s}{dy:.0f}', (0.03, 0.9, 2.1), (x+s*(W/2+0.006), dy, z0+1.1), m['dark'] if style=='vip' else m['red'], bevel=0.02))
        if style != 'vip':
            parts.append(box(name+f'_stripe{s}', (0.02, length-0.4, 0.22), (x+s*(W/2+0.004), cy, z0+0.55), m['red'], bevel=0.005))
    # underframe + equipment boxes
    parts.append(box(name+'_frame', (W-0.3, length-0.4, 0.35), (x, cy, z0-0.1), m['dark'], bevel=0.03))
    rnd = random.Random(hash(name) & 0xffff)
    for i in range(6):
        ey = y0 - 6 - i*2.2
        parts.append(box(name+f'_eq{i}', (rnd.uniform(1.0,2.0), rnd.uniform(0.8,1.6), rnd.uniform(0.35,0.55)), (x+rnd.uniform(-0.3,0.3), ey, z0-0.5), m['dark'], bevel=0.02))
    # bogies + wheels
    for by in (y0-3.2, y0-length+3.2):
        parts.append(box(name+f'_bog{by:.0f}', (2.3, 2.8, 0.45), (x, by, 0.62), m['dark'], bevel=0.04))
        for wy in (-1.25, 1.25):
            for s in (-1,1):
                parts.append(cyl(name+f'_wh{by:.0f}{wy}{s}', 0.46, 0.14, (x+s*0.72, by+wy, 0.46), rot=(0,math.pi/2,0), m=m['dark'], verts=28))
        for s in (-1,1):
            parts.append(box(name+f'_spr{by:.0f}{s}', (0.25,0.6,0.5),(x+s*1.05, by, 0.8), m['rubber'], bevel=0.05))
    # AC units on roof
    for i, ay in enumerate((y0-4, y0-length+4)):
        parts.append(box(name+f'_ac{i}', (1.8, 2.6, 0.35), (x, ay, z0+H+0.36), m['roof'], bevel=0.08, segs=3))
    # ends: gangway, buffers, coupler, tail lamps
    for e, ey in ((1, y0), (-1, y0-length)):
        parts.append(box(name+f'_gw{e}', (1.2, 0.25, 2.2), (x, ey+e*0.12, z0+1.2), m['rubber'], bevel=0.06, segs=3))
        for s in (-1,1):
            parts.append(cyl(name+f'_buf{e}{s}', 0.2, 0.5, (x+s*0.88, ey+e*0.25, 1.06), rot=(math.pi/2,0,0), m=m['dark'], verts=20))
            if tail_lamps and e==1:
                parts.append(cyl(name+f'_tl{s}', 0.11, 0.06, (x+s*1.1, ey+0.03, z0+0.55), rot=(math.pi/2,0,0), m=m['tail'], verts=20))
        parts.append(box(name+f'_cpl{e}', (0.25, 0.5, 0.2), (x, ey+e*0.25, 1.0), m['dark'], bevel=0.02))
    o = join(parts, name)
    return o

def locomotive(name, y0, x=0.0, mats=None):
    """Front at y0 facing -Y (heading south)."""
    m = mats or M(); parts=[]
    L_, W = 20.0, 3.0
    cy = y0 + L_/2
    parts.append(box(name+'_hood', (W-0.3, L_-4, 2.7), (x, cy+1, 2.9), m['blue'], bevel=0.12, segs=3))
    parts.append(box(name+'_cab', (W, 3.6, 3.2), (x, y0+2.0, 3.15), m['blue'], bevel=0.25, segs=4))
    parts.append(box(name+'_nose', (W, 0.6, 1.3), (x, y0+0.3, 2.0), m['yellow'], bevel=0.15, segs=3))
    for s in (-1,1):
        parts.append(box(name+f'_ws{s}', (1.15, 0.05, 1.0), (x+s*0.65, y0+0.18, 3.9), m['glass'], bevel=0.05))
        parts.append(cyl(name+f'_hl{s}', 0.14, 0.08, (x+s*0.9, y0+0.0, 2.2), rot=(math.pi/2,0,0), m=m['head'], verts=20))
    parts.append(cyl(name+'_hlt', 0.16, 0.08, (x, y0+0.18, 4.65), rot=(math.pi/2,0,0), m=m['head'], verts=20))
    parts.append(box(name+'_frame', (W, L_, 0.5), (x, cy, 1.3), m['dark'], bevel=0.03))
    for by in (y0+4, y0+L_-4):
        parts.append(box(name+f'_bog{by:.0f}', (2.6, 4.0, 0.8), (x, by, 0.7), m['dark'], bevel=0.05))
    o = join(parts, name)
    # actual light so headlight glows
    for s in (-1,1):
        lt = bpy.data.lights.new(name+f'L{s}', 'SPOT'); lt.energy = 4000; lt.spot_size = math.radians(30); lt.color=(1,0.92,0.75)
        lo = bpy.data.objects.new(name+f'L{s}', lt); lo.location = (x+s*0.9, y0-0.2, 2.2); lo.rotation_euler = (math.radians(90),0,math.radians(180))
        link(lo)
    return o

def track(x, y_from, y_to, mats=None):
    m = mats or M()
    rail_m = mat('rail', (0.20,0.12,0.08), rough=0.6, metal=0.6)
    rust_m = grime_mat('railrust', (0.25,0.12,0.06), rough=0.8, amount=0.4)
    sleeper_m = grime_mat('sleeper', (0.30,0.29,0.27), rough=0.85, amount=0.5, dirt=(0.2,0.15,0.1))
    ballast_m = bpy.data.materials.get('ballastV') or stones_mat()
    L_ = y_to - y_from; cy = (y_from+y_to)/2
    objs = []
    # ballast prism
    me = bpy.data.meshes.new('ballast'); bm = bmesh.new()
    prof = [(-2.6,-0.05),(-1.6,0.35),(1.6,0.35),(2.6,-0.05)]
    vs0 = [bm.verts.new((x+p[0], y_from, p[1]-0.55)) for p in prof]
    vs1 = [bm.verts.new((x+p[0], y_to, p[1]-0.55)) for p in prof]
    for i in range(3): bm.faces.new((vs0[i], vs0[i+1], vs1[i+1], vs1[i]))
    bm.to_mesh(me); bm.free()
    bo = bpy.data.objects.new('ballast', me); me.materials.append(ballast_m); link(bo)
    sub = bo.modifiers.new('sub','SUBSURF'); sub.levels = 0; sub.render_levels = 0
    # stone displacement via texture
    tx = bpy.data.textures.new('stones','VORONOI'); tx.noise_scale = 0.06
    objs.append(bo)
    for s in (-1,1):
        r = box(f'rail{x}{s}', (0.07, L_, 0.16), (x+s*0.7175, cy, -0.08+0.0), rail_m, bevel=0.01)
        rt = box(f'railtop{x}{s}', (0.072, L_, 0.03), (x+s*0.7175, cy, -0.005), mat('railtop',(0.75,0.75,0.75),0.12,1.0), bevel=0.008)
        r2 = box(f'railweb{x}{s}', (0.15, L_, 0.03), (x+s*0.7175, cy, -0.15), rust_m, bevel=0.0)
    sl = box(f'sleeper{x}', (2.6, 0.24, 0.18), (x, y_from, -0.25), sleeper_m, bevel=0.02)
    ar = sl.modifiers.new('arr','ARRAY'); ar.count = int(L_/0.6); ar.relative_offset_displace = (0, 0.6/0.24, 0)
    return objs

def stones_mat():
    m = bpy.data.materials.new('ballastV'); m.use_nodes=True
    nt=m.node_tree; N=nt.nodes; L=nt.links; b=N['Principled BSDF']
    tc=N.new('ShaderNodeTexCoord'); vo=N.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value=14
    L.new(tc.outputs['Object'], vo.inputs['Vector'])
    rp=N.new('ShaderNodeValToRGB'); e=rp.color_ramp.elements
    e[0].color=(0.06,0.055,0.05,1); e[1].color=(0.19,0.17,0.15,1)
    L.new(vo.outputs['Color'], rp.inputs[0]); L.new(rp.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value=0.9
    bump=N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=1.0; bump.inputs['Distance'].default_value=0.05
    L.new(vo.outputs['Distance'], bump.inputs['Height']); L.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def maize_plant():
    m_leaf = grime_mat('maizeleaf', (0.09,0.20,0.03), rough=0.6, amount=0.5, dirt=(0.35,0.30,0.12), scale=1.5)
    parts = [cyl('stalk', 0.018, 2.2, (0,0,1.1), m=m_leaf, verts=6)]
    rnd = random.Random(3)
    for i in range(13):
        z = 0.3 + i*0.14
        me = bpy.data.meshes.new('leaf'); bm = bmesh.new()
        segs=6; Lf = rnd.uniform(0.8,1.15); ang = rnd.uniform(0, 2*math.pi)
        verts=[]
        for k in range(segs+1):
            t=k/segs; w = 0.075*math.sin(math.pi*min(1,t*1.2+0.1))
            px = t*Lf; pz = z + 0.35*Lf*t - 0.6*Lf*t*t
            for s in (-1,1):
                v = Vector((px, s*w, pz)); v.rotate(__import__('mathutils').Euler((0,0,ang)))
                verts.append(bm.verts.new(v))
        for k in range(segs):
            bm.faces.new((verts[2*k], verts[2*k+1], verts[2*k+3], verts[2*k+2]))
        bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new('leaf', me); me.materials.append(m_leaf); link(o); parts.append(o)
    p = join(parts, 'maize')
    for poly in p.data.polygons: poly.use_smooth = True
    return p

def palm(seed=0):
    rnd = random.Random(seed)
    trunk_m = grime_mat('palmtrunk', (0.30,0.24,0.17), rough=0.9, amount=0.5)
    frond_m = grime_mat('palmfrond', (0.16,0.25,0.08), rough=0.55, amount=0.4, dirt=(0.35,0.32,0.15), scale=2)
    H = rnd.uniform(9, 16); lean = rnd.uniform(-0.08, 0.08)
    parts=[]
    t = cyl('trunk', 0.22, H, (0,0,H/2), m=trunk_m, verts=10); t.rotation_euler=(lean,0,0); parts.append(t)
    top = Vector((0, -math.sin(lean)*H, H))
    n = rnd.randint(16, 22)
    for i in range(n):
        az = i/n*2*math.pi + rnd.uniform(-0.1,0.1); el = rnd.uniform(-0.3, 0.7)
        Lf = rnd.uniform(3.0, 4.2)
        me = bpy.data.meshes.new('frond'); bm = bmesh.new(); vs=[]
        segs=8
        for k in range(segs+1):
            tt=k/segs; w = 0.55*math.sin(math.pi*tt)*(1-0.3*tt)
            d = tt*Lf; z = math.sin(el)*d - 0.35*d*d/Lf*2
            for s in (-1,1):
                vs.append(bm.verts.new((d, s*w, z - abs(s*w)*0.35)))
        for k in range(segs): bm.faces.new((vs[2*k],vs[2*k+1],vs[2*k+3],vs[2*k+2]))
        bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new('frond', me); me.materials.append(frond_m); link(o)
        o.location = top; o.rotation_euler = (0,0,az); parts.append(o)
    p = join(parts, f'palm{seed}')
    for poly in p.data.polygons: poly.use_smooth = True
    return p

def house(name, loc, size, rot=0.0):
    brick = grime_mat('brick', (0.42,0.17,0.10), rough=0.85, amount=0.4, scale=4)
    conc = grime_mat('concrete', (0.55,0.52,0.47), rough=0.9, amount=0.5)
    w,d,h = size; parts=[]
    parts.append(box(name+'_b', (w,d,h), (0,0,h/2), brick, bevel=0.03))
    floors = max(1,int(h/3))
    for f in range(floors+1):
        parts.append(box(name+f'_s{f}', (w+0.1,d+0.1,0.22), (0,0,f*3.0), conc, bevel=0.02))
    for cx in (-w/2, w/2):
        for cyy in (-d/2, d/2):
            parts.append(box(name+'_c', (0.3,0.3,h+0.8), (cx,cyy,(h+0.8)/2), conc, bevel=0.02))
    # rebar on roof
    for cx in (-w/2, w/2):
        for cyy in (-d/2, d/2):
            for k in range(4):
                parts.append(cyl(name+'_rb', 0.012, 1.0, (cx+0.08*(k%2-0.5), cyy+0.08*(k//2-0.5), h+1.3), m=mat('rebar',(0.2,0.1,0.06),0.8,0.5), verts=5))
    # windows
    for f in range(floors):
        for i in range(max(1,int(w/3))):
            parts.append(box(name+'_win', (1.0,0.05,1.1), (-w/2+1.5+i*3, -d/2-0.01, f*3+1.6), mat('winhole',(0.02,0.02,0.02),0.9), bevel=0.0))
    o = join(parts, name); o.location = loc; o.rotation_euler=(0,0,rot)
    return o

def pole(loc, h=7.0):
    conc = grime_mat('concrete', (0.55,0.52,0.47), rough=0.9, amount=0.5)
    p = box('pole', (0.22,0.22,h), (loc[0],loc[1],h/2), conc, bevel=0.02)
    a = box('arm', (1.2,0.1,0.1), (loc[0],loc[1],h-0.4), mat('rebar',(0.2,0.1,0.06),0.8,0.5), bevel=0.0)
    return join([p,a],'pole')


def grass_tuft(seed=0):
    rnd = random.Random(seed)
    gm = grime_mat('grass', (0.10,0.15,0.04), rough=0.7, amount=0.7, dirt=(0.30,0.25,0.12), scale=1)
    parts=[]
    for i in range(26):
        me = bpy.data.meshes.new('blade'); bm = bmesh.new(); vs=[]
        h = rnd.uniform(0.12,0.32); ang=rnd.uniform(0,6.28); lean=rnd.uniform(0.1,0.5)
        for k in range(5):
            t=k/4; w=0.012*(1-t)
            for sgn in (-1,1):
                v=Vector((lean*h*t*t, sgn*w, h*t)); v.rotate(__import__('mathutils').Euler((0,0,ang))); vs.append(bm.verts.new(v))
        for k in range(4): bm.faces.new((vs[2*k],vs[2*k+1],vs[2*k+3],vs[2*k+2]))
        bm.to_mesh(me); bm.free(); o=bpy.data.objects.new('blade',me); me.materials.append(gm); link(o); parts.append(o)
    return join(parts,'tuft')
