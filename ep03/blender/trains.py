"""EP03 detailed rolling stock: ENR red GE-style diesel loco + ribbed AC coach (exterior + interior).
Convention: rail top z=0, track centre x=0 (pass x offset), train runs along Y.
Loco front at y0 facing -Y, body extends toward +Y."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
from lib import *

# ---------------- geometry helpers ----------------
def prism(name, prof, x0, x1, m, bevel=0.0, segs=2, angle=35):
    """Closed polygon prof [(y,z),...] (CCW seen from +X) extruded from x0 to x1."""
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    a = [bm.verts.new((x0, y, z)) for y, z in prof]
    b = [bm.verts.new((x1, y, z)) for y, z in prof]
    n = len(prof)
    bm.faces.new(list(reversed(a))); bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); link(o)
    if m: me.materials.append(m)
    if bevel > 0: bevel_mod(o, bevel, segs, angle)
    return o

def prism_z(name, prof, z0, z1, m, bevel=0.0, segs=2):
    """Polygon prof [(x,y),...] extruded along Z."""
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    a = [bm.verts.new((x, y, z0)) for x, y in prof]
    b = [bm.verts.new((x, y, z1)) for x, y in prof]
    n = len(prof)
    bm.faces.new(list(reversed(a))); bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n; bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); link(o)
    if m: me.materials.append(m)
    if bevel > 0: bevel_mod(o, bevel, segs)
    return o

def bevel_mod(o, w, segs=2, angle=35):
    md = o.modifiers.new('bev', 'BEVEL'); md.width = w; md.segments = segs
    md.limit_method = 'ANGLE'; md.angle_limit = math.radians(angle); md.use_clamp_overlap = True
    md.harden_normals = True; md.miter_outer = 'MITER_ARC'
    for p in o.data.polygons: p.use_smooth = True
    wn = o.modifiers.new('wn', 'WEIGHTED_NORMAL'); wn.keep_sharp = True; wn.weight = 50
    return md

def tube(name, pts, r, m, verts=8):
    """Polyline pipe through pts (handrails, hoses)."""
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts): p.co = (*c, 1)
    cu.bevel_depth = r; cu.bevel_resolution = max(1, verts // 4); cu.use_fill_caps = True
    o = bpy.data.objects.new(name, cu); link(o)
    if m: cu.materials.append(m)
    return o

def to_mesh_join(objs, name):
    """Convert curves/apply modifiers, join into one mesh object."""
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in objs:
        e = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(e, preserve_all_data_layers=True, depsgraph=dg)
        n = bpy.data.objects.new(o.name + '_m', me); n.matrix_world = o.matrix_world.copy(); link(n)
        out.append(n)
    for o in objs: bpy.data.objects.remove(o, do_unlink=True)
    return join(out, name)

# ---------------- materials ----------------
def livery(name, base, band, under=(0.025, 0.025, 0.025), band_z=(2.30, 2.62), under_z=1.62, dirt=0.45, metal=0.0):
    """Paint keyed by world-ish Z (objects built at z origin 0): black underbody, base colour, white band.
    Includes grime streaks (darker toward bottom), roughness breakup and fine bump."""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    def step(edge):
        s = N.new('ShaderNodeMath'); s.operation = 'GREATER_THAN'; s.inputs[1].default_value = edge
        L.new(sep.outputs['Z'], s.inputs[0]); return s
    s_under, s_b0, s_b1 = step(under_z), step(band_z[0]), step(band_z[1])
    inband = N.new('ShaderNodeMath'); inband.operation = 'SUBTRACT'
    L.new(s_b0.outputs[0], inband.inputs[0]); L.new(s_b1.outputs[0], inband.inputs[1])
    c1 = N.new('ShaderNodeMix'); c1.data_type = 'RGBA'; c1.inputs['A'].default_value = (*under, 1); c1.inputs['B'].default_value = (*base, 1)
    L.new(s_under.outputs[0], c1.inputs['Factor'])
    c2 = N.new('ShaderNodeMix'); c2.data_type = 'RGBA'; c2.inputs['B'].default_value = (*band, 1)
    L.new(c1.outputs['Result'], c2.inputs['A']); L.new(inband.outputs[0], c2.inputs['Factor'])
    # grime: noise * vertical streak waves, stronger low
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.6; nz.inputs['Detail'].default_value = 8
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'Y'
    wv.inputs['Scale'].default_value = 5.5; wv.inputs['Distortion'].default_value = 2.2; wv.inputs['Detail'].default_value = 3
    L.new(tc.outputs['Object'], wv.inputs['Vector'])
    low = N.new('ShaderNodeMapRange'); low.inputs['From Min'].default_value = 4.2; low.inputs['From Max'].default_value = 1.4
    L.new(sep.outputs['Z'], low.inputs['Value'])
    g1 = N.new('ShaderNodeMath'); g1.operation = 'MULTIPLY'; L.new(nz.outputs['Fac'], g1.inputs[0]); L.new(wv.outputs['Fac'], g1.inputs[1])
    g2 = N.new('ShaderNodeMath'); g2.operation = 'ADD'; L.new(g1.outputs[0], g2.inputs[0]); L.new(low.outputs['Result'], g2.inputs[1])
    g3 = N.new('ShaderNodeMapRange'); g3.inputs['From Min'].default_value = 0.35; g3.inputs['From Max'].default_value = 1.5
    g3.inputs['To Max'].default_value = dirt; L.new(g2.outputs[0], g3.inputs['Value'])
    c3 = N.new('ShaderNodeMix'); c3.data_type = 'RGBA'; c3.inputs['B'].default_value = (0.16, 0.12, 0.085, 1)
    L.new(c2.outputs['Result'], c3.inputs['A']); L.new(g3.outputs['Result'], c3.inputs['Factor'])
    L.new(c3.outputs['Result'], b.inputs['Base Color'])
    r = N.new('ShaderNodeMapRange'); r.inputs['To Min'].default_value = 0.16; r.inputs['To Max'].default_value = 0.55
    L.new(g3.outputs['Result'], r.inputs['Value']); r.inputs['From Max'].default_value = dirt
    L.new(r.outputs['Result'], b.inputs['Roughness'])
    b.inputs['Metallic'].default_value = metal
    b.inputs['Coat Weight'].default_value = 0.55; b.inputs['Coat Roughness'].default_value = 0.06
    # dirt kills the clear coat locally (weathered paint is matte where grime collects)
    cw = N.new('ShaderNodeMapRange'); cw.inputs['From Max'].default_value = dirt; cw.inputs['To Min'].default_value = 0.6; cw.inputs['To Max'].default_value = 0.1
    L.new(g3.outputs['Result'], cw.inputs['Value']); L.new(cw.outputs['Result'], b.inputs['Coat Weight'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.08
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 40; L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    L.new(nz2.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

def chevron_mat():
    m = bpy.data.materials.get('chevron')
    if m: return m
    m = bpy.data.materials.new('chevron'); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    ax = N.new('ShaderNodeMath'); ax.operation = 'ABSOLUTE'; L.new(sep.outputs['X'], ax.inputs[0])
    ad = N.new('ShaderNodeMath'); ad.operation = 'ADD'; L.new(ax.outputs[0], ad.inputs[0]); L.new(sep.outputs['Z'], ad.inputs[1])
    mu = N.new('ShaderNodeMath'); mu.operation = 'MULTIPLY'; mu.inputs[1].default_value = 1 / 0.22; L.new(ad.outputs[0], mu.inputs[0])
    fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(mu.outputs[0], fr.inputs[0])
    st = N.new('ShaderNodeMath'); st.operation = 'GREATER_THAN'; st.inputs[1].default_value = 0.5; L.new(fr.outputs[0], st.inputs[0])
    mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs['A'].default_value = (0.02, 0.02, 0.02, 1); mx.inputs['B'].default_value = (0.75, 0.55, 0.04, 1)
    L.new(st.outputs[0], mx.inputs['Factor']); L.new(mx.outputs['Result'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.55
    return m

def mats():
    return dict(
        red=livery('locoRed', (0.22, 0.009, 0.007), (0.72, 0.71, 0.68)),
        black=grime_mat('frameBlack', (0.025, 0.024, 0.022), rough=0.6, metal=0.3, amount=0.25, dirt=(0.06, 0.05, 0.04), scale=6, streak=False),
        steel=grime_mat('bareSteel', (0.32, 0.31, 0.30), rough=0.45, metal=1.0, amount=0.5, dirt=(0.16, 0.12, 0.08)),
        wheel=grime_mat('wheelSteel', (0.20, 0.16, 0.13), rough=0.6, metal=0.8, amount=0.6, dirt=(0.25, 0.13, 0.06)),
        glass=window_glass('cabGlass'),
        rubber=mat('rubberK', (0.012, 0.012, 0.012), rough=0.85),
        yellow=mat('grabYellow', (0.80, 0.58, 0.04), rough=0.45),
        lamp=mat('lampOn', (1, 1, 0.92), rough=0.1, emit=(1, 0.93, 0.78), estr=40),
        lampoff=mat('lampOff', (0.6, 0.6, 0.55), rough=0.1, coat=1.0),
        grille=grime_mat('grille', (0.025, 0.025, 0.025), rough=0.7, metal=0.4, amount=0.25, dirt=(0.06,0.05,0.04)),
        chev=chevron_mat(),
        white=mat('numWhite', (0.85, 0.85, 0.82), rough=0.4),
    )

# ---------------- locomotive ----------------
def locomotive(name, y0=0.0, x=0.0, lights=True, length=21.0, interior=False, atc_on=True):
    X0, Y0 = x, y0; x = 0.0; y0 = 0.0
    m = mats(); P = []
    W = 3.05; hw = W / 2; L_ = length
    deck0, deck1 = 1.30, 1.55
    # deck / underframe with sill
    P.append(prism(name + '_deck', [(0.25, deck0), (L_ - 0.25, deck0), (L_ - 0.25, deck1), (0.25, deck1)], -hw, hw, m['black'], 0.02))
    # sill skirt band slightly proud
    for s in (-1, 1):
        P.append(box(name + f'_sill{s}', (0.04, L_ - 0.6, 0.18), (x + s * (hw + 0.01), y0 + L_ / 2, 1.42), m['black'], bevel=0.008))
    # pilot / plow with chevrons
    P.append(prism(name + '_pilot', [(-0.12, 0.25), (0.25, 0.25), (0.25, deck1), (0.0, deck1), (-0.12, 1.1)], -hw + 0.05, hw - 0.05, m['black'], 0.02))
    P.append(prism(name + '_chevs', [(-0.135, 1.12), (-0.125, 1.12), (0.005, deck1 - 0.02), (-0.005, deck1 - 0.02)], -hw + 0.1, hw - 0.1, m['chev'], 0.0))
    P.append(prism(name + '_plow', [(-0.35, 0.10), (0.15, 0.10), (0.15, 0.35), (-0.18, 0.55)], -1.2, 1.2, m['black'], 0.02))
    # cab (profile in y,z)
    cab = [(0.25, deck1), (2.9, deck1), (4.15, deck1), (4.15, 4.32), (1.95, 4.32), (1.72, 4.25),
           (0.98, 2.88), (0.90, 2.82), (0.33, 2.74), (0.25, 2.64)]
    cabo = prism(name + '_cab', cab, -hw + 0.02, hw - 0.02, m['red'], 0.06, 3)
    P.append(cabo)
    if interior:
        cabo.data.materials.append(cab_mats()['wall'])
        sol = cabo.modifiers.new('sol', 'SOLIDIFY'); sol.thickness = 0.06; sol.offset = -1; sol.material_offset = 1
        cc = bpy.data.collections.new(name + '_cabcut'); bpy.context.scene.collection.children.link(cc)
        p0_, p1_ = Vector((0.93, 2.85)), Vector((1.70, 4.22)); mid_ = (p0_ + p1_) / 2; d_ = p1_ - p0_
        for s_ in (-1, 1):
            c_ = box(name + f'_wcut{s_}', (1.12, d_.length * 0.78, 0.5), (s_ * 0.66, mid_.x, mid_.y), None, bevel=0.04, coll=cc)
            c_.rotation_euler = (math.atan2(d_.y, d_.x), 0, 0)
            box(name + f'_scut{s_}', (0.5, 0.9, 0.7), (s_ * hw, 2.45, 3.55), None, bevel=0.04, coll=cc)
        bo_ = cabo.modifiers.new('cut', 'BOOLEAN'); bo_.operation = 'DIFFERENCE'; bo_.operand_type = 'COLLECTION'; bo_.collection = cc; bo_.solver = 'EXACT'
        P += cab_interior(name, hw, deck1, atc_on)
    # nose tumble-home side chamfer: small corner boxes give the wide-nose look
    # windshields (two panes on raked face), set slightly proud with black gasket
    p0, p1 = Vector((0.93, 2.85)), Vector((1.70, 4.22))
    d = (p1 - p0); ln = d.length; ang = math.atan2(d.y, d.x)
    for s in (-1, 1):
        cx = s * 0.66
        mid = (p0 + p1) / 2
        g = box(name + f'_ws{s}', (1.18, ln * 0.80, 0.02), (x + cx, y0 + mid.x - 0.012, mid.y + 0.012), m['glass'], bevel=0.05, segs=3)
        g.rotation_euler = (ang, 0, 0); P.append(g)
        for (fw_, fh_, ox_, oy_) in ((1.28, 0.05, 0, ln * 0.42), (1.28, 0.05, 0, -ln * 0.42), (0.05, ln * 0.88, 0.615, 0), (0.05, ln * 0.88, -0.615, 0)):
            f = box(name + f'_wsf{s}{ox_:.2f}{oy_:.2f}', (fw_, fh_, 0.03), (0, 0, 0), m['rubber'], bevel=0.0)
            f.rotation_euler = (ang, 0, 0)
            off_ = Vector((ox_, oy_, 0)); off_.rotate(f.rotation_euler)
            f.location = Vector((x + cx, y0 + mid.x - 0.004, mid.y + 0.004)) + off_; P.append(f)
        # wiper
        wp = box(name + f'_wip{s}', (0.03, 0.70, 0.015), (x + cx + 0.25, y0 + mid.x - 0.04, mid.y - 0.05), m['black'], bevel=0.0)
        wp.rotation_euler = (ang, 0, math.radians(12 * s)); P.append(wp)
    # centre pillar
    pl = box(name + '_pillar', (0.12, ln * 0.92, 0.03), (x, y0 + (p0.x + p1.x) / 2 - 0.01, (p0.y + p1.y) / 2 + 0.01), m['red'], bevel=0.01)
    pl.rotation_euler = (ang, 0, 0); P.append(pl)
    # side cab windows + door
    for s in (-1, 1):
        sx = x + s * (hw - 0.005)
        P.append(box(name + f'_sw{s}', (0.02, 0.95, 0.75), (sx, y0 + 2.45, 3.55), m['glass'], bevel=0.05, segs=3))
        for (dy_, dz_, ly_, lz_) in ((0, 0.42, 1.05, 0.05), (0, -0.42, 1.05, 0.05), (0.50, 0, 0.05, 0.85), (-0.50, 0, 0.05, 0.85)):
            P.append(box(name + f'_swf{s}{dy_}{dz_}', (0.03, ly_, lz_), (sx + s * 0.004, y0 + 2.45 + dy_, 3.55 + dz_), m['rubber'], bevel=0.0))
        P.append(box(name + f'_door{s}', (0.012, 0.75, 1.9), (sx + s * 0.002, y0 + 3.55, 2.55), m['red'], bevel=0.01))
        P.append(box(name + f'_doorwin{s}', (0.02, 0.45, 0.5), (sx + s * 0.004, y0 + 3.55, 3.6), m['glass'], bevel=0.04))
        P.append(tube(name + f'_gh{s}', [(sx + s * 0.06, y0 + 3.15, 1.9), (sx + s * 0.06, y0 + 3.15, 3.2)], 0.018, m['yellow']))
        P.append(tube(name + f'_gh2{s}', [(sx + s * 0.06, y0 + 3.95, 1.9), (sx + s * 0.06, y0 + 3.95, 3.2)], 0.018, m['yellow']))
        # mirror arm
        P.append(box(name + f'_mir{s}', (0.06, 0.18, 0.28), (sx + s * 0.16, y0 + 1.95, 3.6), m['black'], bevel=0.02))
    # headlights: two in nose (recessed bezels), one in roof cap; marker lamps
    for s in (-1, 1):
        P.append(cyl(name + f'_hlb{s}', 0.13, 0.08, (x + s * 0.95, y0 + 0.24, 2.45), rot=(math.pi / 2, 0, 0), m=m['black'], verts=24))
        P.append(cyl(name + f'_hl{s}', 0.10, 0.04, (x + s * 0.95, y0 + 0.19, 2.45), rot=(math.pi / 2, 0, 0), m=m['lamp'] if lights else m['lampoff'], verts=24))
        P.append(cyl(name + f'_mk{s}', 0.06, 0.05, (x + s * 1.25, y0 + 0.24, 2.05), rot=(math.pi / 2, 0, 0), m=m['lampoff'], verts=16))
    P.append(box(name + '_hltb', (0.55, 0.10, 0.22), (x, y0 + 1.86, 4.34), m['black'], bevel=0.03))
    for s in (-1, 1):
        P.append(cyl(name + f'_hlt{s}', 0.075, 0.03, (x + s * 0.13, y0 + 1.80, 4.34), rot=(math.pi / 2, 0, 0), m=m['lamp'] if lights else m['lampoff'], verts=20))
    # number board
    P.append(box(name + '_num', (0.7, 0.03, 0.18), (x, y0 + 0.31, 2.50), m['white'], bevel=0.01))
    # nose handrail + steps
    P.append(tube(name + '_nrail', [(x - 1.3, y0 + 0.05, deck1), (x - 1.3, y0 + 0.05, 2.5), (x - 0.4, y0 + 0.05, 2.5)], 0.02, m['yellow']))
    P.append(tube(name + '_nrail2', [(x + 1.3, y0 + 0.05, deck1), (x + 1.3, y0 + 0.05, 2.5), (x + 0.4, y0 + 0.05, 2.5)], 0.02, m['yellow']))
    # ---- long hood ----
    hw2 = 1.20; h0, h1 = 4.15, L_ - 4.6
    hood = [(h0, deck1), (h1, deck1), (h1, 4.05), (h0, 4.05)]
    P.append(prism(name + '_hood', hood, -hw2, hw2, m['red'], 0.09, 3))
    # door panel seams (proud thin strips) + louvre grilles
    rnd = random.Random(3)
    y = h0 + 0.6
    while y < h1 - 0.5:
        for s in (-1, 1):
            P.append(box(name + f'_seam{s}{y:.1f}', (0.012, 0.025, 2.35), (x + s * (hw2 + 0.003), y0 + y, 2.78), m['black'], bevel=0.0))
        y += 1.15
    for i, (yy, hh) in enumerate([(h0 + 1.7, 0.6), (h0 + 3.0, 0.6), (h0 + 6.5, 0.8), (h0 + 7.7, 0.8), (h1 - 1.2, 0.9)]):
        for s in (-1, 1):
            gx = x + s * (hw2 + 0.006)
            P.append(box(name + f'_gr{i}{s}', (0.015, 0.95, hh), (gx, y0 + yy, 3.35), m['grille'], bevel=0.01))
            for k in range(int(hh / 0.06)):
                P.append(box(name + f'_lv{i}{s}{k}', (0.03, 0.9, 0.012), (gx + s * 0.008, y0 + yy, 3.35 - hh / 2 + 0.04 + k * 0.06), m['black'], bevel=0.0))
    # ---- radiator section (wider, with angled wings) ----
    r0, r1 = h1, L_ - 0.35
    rad = [(-1.52, deck1), (1.52, deck1), (1.52, 3.55), (1.30, 4.30), (-1.30, 4.30), (-1.52, 3.55)]
    P.append(prism_z(name + '_radtmp', [(a, r0) for a, _ in [(0, 0)]] * 0 + [(-1.52, r0), (1.52, r0), (1.52, r1), (-1.52, r1)], deck1, 3.55, m['red'], 0.05))
    # wings: prism along Y
    wing = [(r0, 3.55), (r1, 3.55), (r1, 4.30), (r0, 4.30)]
    wg = prism(name + '_radtop', wing, -1.30, 1.30, m['red'], 0.05)
    P.append(wg)
    for s in (-1, 1):
        # angled radiator cores on each side (dark mesh)
        c = box(name + f'_core{s}', (0.03, r1 - r0 - 0.6, 0.72), (x + s * 1.43, y0 + (r0 + r1) / 2, 3.93), m['grille'], bevel=0.0)
        c.rotation_euler = (0, s * math.radians(-17), 0); P.append(c)
    for i in range(3):  # roof fans
        fy = r0 + 0.8 + i * 1.25
        P.append(cyl(name + f'_fan{i}', 0.52, 0.08, (x, y0 + fy, 4.33), m=m['grille'], verts=32))
        P.append(cyl(name + f'_fanr{i}', 0.56, 0.05, (x, y0 + fy, 4.32), m=m['black'], verts=32))
        for k in range(6):
            bl = box(name + f'_bl{i}{k}', (0.95, 0.06, 0.01), (x, y0 + fy, 4.38), m['black'], bevel=0.0)
            bl.rotation_euler = (0, 0, k * math.pi / 6); P.append(bl)
    # exhaust stack, horn, dynamic brake hatch
    P.append(box(name + '_stack', (0.35, 0.55, 0.18), (x, y0 + h0 + 5.0, 4.13), m['black'], bevel=0.03))
    P.append(box(name + '_db', (1.9, 2.4, 0.22), (x, y0 + h0 + 1.6, 4.13), m['grille'], bevel=0.04))
    for k in range(3):
        P.append(cyl(name + f'_horn{k}', 0.05, 0.28 + 0.06 * k, (x + 0.35, y0 + 2.6 + k * 0.12, 4.45), rot=(math.pi / 2, 0, 0), m=m['steel'], verts=12))
    # rear end
    P.append(box(name + '_rearplate', (W - 0.1, 0.05, 1.0), (x, y0 + L_ - 0.25, 2.0), m['red'], bevel=0.02))
    P.append(prism(name + '_rpilot', [(L_ - 0.25, 0.25), (L_ + 0.12, 1.1), (L_, deck1), (L_ - 0.25, deck1)], -hw + 0.05, hw - 0.05, m['chev'], 0.02))
    # walkway handrails along hood
    for s in (-1, 1):
        hx = x + s * (hw - 0.06)
        posts = [h0 + 0.2 + i * 2.25 for i in range(int((h1 - h0) / 2.25) + 1)]
        for py in posts:
            P.append(tube(name + f'_post{s}{py:.1f}', [(hx, y0 + py, deck1), (hx, y0 + py, deck1 + 1.0)], 0.018, m['black']))
        P.append(tube(name + f'_rail{s}', [(hx, y0 + posts[0], deck1 + 1.0), (hx, y0 + posts[-1], deck1 + 1.0)], 0.02, m['black']))
        P.append(tube(name + f'_rail2{s}', [(hx, y0 + posts[0], deck1 + 0.5), (hx, y0 + posts[-1], deck1 + 0.5)], 0.015, m['black']))
        # steps at four corners
        for sy in (0.55, L_ - 0.55):
            for k in range(3):
                P.append(box(name + f'_stp{s}{sy:.0f}{k}', (0.38, 0.5, 0.03), (x + s * (hw - 0.22), y0 + sy, 0.55 + k * 0.32), m['grille'], bevel=0.0))
            P.append(box(name + f'_stps{s}{sy:.0f}', (0.03, 0.55, 1.05), (x + s * (hw - 0.02), y0 + sy, 0.88), m['black'], bevel=0.0))
    # fuel tank (between trucks)
    P.append(prism(name + '_tank', [(6.6, 0.55), (14.4, 0.55), (14.7, 0.85), (14.7, deck0), (6.3, deck0), (6.3, 0.85)], -1.25, 1.25, m['black'], 0.12, 3))
    for s in (-1, 1):
        P.append(cyl(name + f'_fill{s}', 0.07, 0.06, (x + s * 1.27, y0 + 10.5, 1.0), rot=(0, math.pi / 2, 0), m=m['steel'], verts=12))
        P.append(box(name + f'_air{s}', (0.5, 4.0, 0.42), (x + s * 0.9, y0 + 16.1, 1.05), m['black'], bevel=0.12, segs=3))
    # trucks (C-C)
    for ty in (3.9, L_ - 4.4):
        P += truck(name + f'_tr{ty:.0f}', x, y0 + ty, m)
    # couplers
    for e, cy_ in ((-1, -0.05), (1, L_ + 0.05)):
        P.append(box(name + f'_cpl{e}', (0.30, 0.6, 0.28), (x, y0 + cy_, 0.95), m['steel'], bevel=0.03))
        for s in (-1, 1):
            P.append(tube(name + f'_hose{e}{s}', [(x + s * 0.5, y0 + cy_, 1.25), (x + s * 0.55, y0 + cy_ + e * 0.15, 0.95), (x + s * 0.5, y0 + cy_ + e * 0.2, 0.75)], 0.03, m['rubber']))
    P = [p for p in P if p.name != name + '_radtmp'] + [p for p in P if p.name == name + '_radtmp']
    o = to_mesh_join(P, name)
    if interior:
        cc_ = bpy.data.collections.get(name + '_cabcut')
        if cc_:
            for ob_ in list(cc_.objects): bpy.data.objects.remove(ob_, do_unlink=True)
            bpy.data.collections.remove(cc_)
    if lights:
        for s in (-1, 1):
            lt = bpy.data.lights.new(name + f'L{s}', 'SPOT'); lt.energy = 2500; lt.spot_size = math.radians(28); lt.color = (1, 0.92, 0.78)
            lt.shadow_soft_size = 0.08
            lo = bpy.data.objects.new(name + f'L{s}', lt); lo.location = (x + s * 0.95, y0 + 0.1, 2.45)
            lo.rotation_euler = (math.radians(92), 0, math.radians(180)); link(lo); lo.parent = o
    o.location = (X0, Y0, 0)
    return o

def truck(name, x, cy, m, axles=3, r=0.53, pitch=1.9):
    P = []
    n = axles
    for s in (-1, 1):
        sx = x + s * 1.02
        P.append(prism(name + f'_side{s}', [(cy - 2.55, 0.55), (cy + 2.55, 0.55), (cy + 2.35, 1.05), (cy - 2.35, 1.05)], sx - 0.06, sx + 0.06, m['black'], 0.03))
        for i in range(n):
            wy = cy + (i - (n - 1) / 2) * pitch
            P.append(cyl(name + f'_wh{s}{i}', r, 0.13, (x + s * 0.72, wy, r), rot=(0, math.pi / 2, 0), m=m['wheel'], verts=32, bevel=0.01))
            P.append(cyl(name + f'_hub{s}{i}', 0.17, 0.10, (sx + s * 0.08, wy, r), rot=(0, math.pi / 2, 0), m=m['steel'], verts=16))
            P.append(box(name + f'_jb{s}{i}', (0.16, 0.36, 0.42), (sx + s * 0.04, wy, r + 0.05), m['black'], bevel=0.02))
            # coil springs
            for k in (-1, 1):
                P.append(cyl(name + f'_sp{s}{i}{k}', 0.09, 0.32, (sx, wy + k * 0.32, 0.98), m=m['steel'], verts=12))
        # brake cylinders
        for i in range(n - 1):
            by = cy + (i - (n - 2) / 2) * pitch
            P.append(cyl(name + f'_bc{s}{i}', 0.10, 0.28, (sx + s * 0.1, by, 0.80), rot=(0, math.pi / 2, 0), m=m['black'], verts=12))
        P.append(box(name + f'_sand{s}', (0.28, 0.35, 0.5), (sx + s * 0.02, cy - 2.75, 1.0), m['black'], bevel=0.03))
    P.append(box(name + '_bolster', (2.0, 0.6, 0.3), (x, cy, 1.10), m['black'], bevel=0.03))
    return P

# ---------------- coach ----------------
def coach_mats():
    return dict(
        skin=livery('coachSkin', (0.34, 0.24, 0.13), (0.46, 0.36, 0.22), under=(0.03, 0.03, 0.03), band_z=(9, 9.1), under_z=1.12, dirt=0.5, metal=0.0),
        letter=livery('coachLetter', (0.38, 0.28, 0.16), (0.38, 0.28, 0.16), under_z=0.0, band_z=(9, 9.1), dirt=0.35, metal=0.0),
        roof=grime_mat('coachRoof', (0.30, 0.28, 0.25), rough=0.6, metal=0.5, amount=0.6, dirt=(0.14, 0.11, 0.08)),
        inner=grime_mat('innerWall', (0.72, 0.70, 0.64), rough=0.6, amount=0.12, dirt=(0.4, 0.36, 0.3), scale=2),
        floor=grime_mat('floorVinyl', (0.18, 0.17, 0.16), rough=0.55, amount=0.3),
        seat=grime_mat('seatBlue', (0.04, 0.08, 0.24), rough=0.85, amount=0.15, dirt=(0.05, 0.05, 0.08), scale=6),
        seatcover=mat('headCover', (0.75, 0.74, 0.70), rough=0.9),
        curtain=grime_mat('curtain', (0.32, 0.18, 0.10), rough=0.95, amount=0.2, scale=8),
        light=mat('ceilLight', (1, 1, 1), rough=0.3, emit=(1, 0.97, 0.9), estr=6),
        **{k: v for k, v in mats().items() if k in ('black', 'steel', 'wheel', 'glass', 'rubber', 'grille', 'lampoff', 'yellow')},
        tail=mat('tailRed', (0.4, 0.0, 0.0), rough=0.2, emit=(1, 0.04, 0.02), estr=25),
    )

def coach(name, y0=0.0, x=0.0, length=24.0, interior=True, tail=False, seed=0):
    """Ribbed AC coach. Front end at y0, body toward +Y. Floor top z=1.25."""
    X0, Y0 = x, y0
    m = coach_mats(); P = []; L_ = length; hw = 1.45; t = 0.05
    fz, wz0, wz1, sz, rz = 1.20, 2.15, 3.05, 3.30, 4.00
    # cross-section outer (x,z) right half, mirrored
    outer = [(hw, fz - 0.15), (hw, sz), (hw - 0.12, sz + 0.35), (hw - 0.55, rz - 0.06), (0.0, rz)]
    def ring(off):
        pts = []
        for (px, pz) in outer:
            nx = px - off if px > 0.01 else 0.0
            pts.append((nx, pz - (off if pz >= rz - 0.07 else 0)))
        return pts
    o_r = ring(0.0); i_r = ring(t)
    o_full = [(-px, pz) for px, pz in reversed(o_r[1:])] + o_r  # left..right over the top? build ordered loop
    right = o_r; left = [(-px, pz) for px, pz in o_r]
    outer_loop = right[:-1] + [(0.0, rz)] + list(reversed(left[:-1]))
    ir = i_r; il = [(-px, pz) for px, pz in i_r]
    inner_loop = ir[:-1] + [(0.0, rz - t)] + list(reversed(il[:-1]))
    shell_prof = outer_loop + list(reversed(inner_loop))
    me = bpy.data.meshes.new(name + '_shell'); bm = bmesh.new()
    a = [bm.verts.new((px, 0.0, pz)) for px, pz in shell_prof]
    b = [bm.verts.new((px, L_, pz)) for px, pz in shell_prof]
    n = len(shell_prof)
    bm.faces.new(a); bm.faces.new(list(reversed(b)))
    for i in range(n):
        j = (i + 1) % n; bm.faces.new((a[i], b[i], b[j], a[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    shell = bpy.data.objects.new(name + '_shell', me); link(shell)
    me.materials.append(m['skin']); me.materials.append(m['inner'])
    for p in me.polygons:
        c = p.center; r = Vector((c.x, 0, c.z - 2.4))
        if p.normal.dot(r) < -0.2 and abs(p.normal.y) < 0.5: p.material_index = 1
    # window cutters
    cut_c = bpy.data.collections.new(name + '_cut'); bpy.context.scene.collection.children.link(cut_c)
    nwin = 10; pitch = (L_ - 4.4) / nwin
    win_y = [2.2 + pitch * (i + 0.5) for i in range(nwin)]
    for s in (-1, 1):
        for wy in win_y:
            c = box(name + f'_wc{s}{wy:.1f}', (0.4, pitch - 0.32, wz1 - wz0), (s * hw, wy, (wz0 + wz1) / 2), None, bevel=0.07, segs=3, coll=cut_c)
        for dy in (0.95, L_ - 0.95):
            box(name + f'_dc{s}{dy:.0f}', (0.4, 0.86, 2.0), (s * hw, dy, fz + 1.0), None, bevel=0.03, coll=cut_c)
    for e in (0.0, L_):  # end gangway door openings
        box(name + f'_ec{e:.0f}', (0.9, 0.4, 2.0), (0, e, fz + 1.0), None, bevel=0.03, coll=cut_c)
    bo = shell.modifiers.new('cut', 'BOOLEAN'); bo.operation = 'DIFFERENCE'; bo.operand_type = 'COLLECTION'; bo.collection = cut_c; bo.solver = 'EXACT'
    P.append(shell)
    # flutes on lower body and letterboard (array of thin ribs)
    for s in (-1, 1):
        for (z0, z1) in ((fz - 0.12, wz0 - 0.12), (wz1 + 0.10, sz - 0.02)):
            rib = box(name + f'_rib{s}{z0:.1f}', (0.012, 0.022, z1 - z0), (s * (hw + 0.006), 1.75 if z0 < 2 else 0.3, (z0 + z1) / 2), m['skin'], bevel=0.0)
            ar = rib.modifiers.new('arr', 'ARRAY'); ar.use_relative_offset = False; ar.use_constant_offset = True
            ar.constant_offset_displace = (0, 0.075, 0); ar.count = int(((L_ - 3.5) if z0 < 2 else (L_ - 0.6)) / 0.075)
            P.append(rib)
        # window band: dark recessed frame + glass + pillars
        for wy in win_y:
            P.append(box(name + f'_g{s}{wy:.1f}', (0.012, pitch - 0.34, wz1 - wz0 - 0.02), (s * (hw - 0.03), wy, (wz0 + wz1) / 2), m['glass'], bevel=0.06, segs=3))
            gw, gh = pitch - 0.30, wz1 - wz0 + 0.02
            for dz in (-1, 1):
                P.append(box(name + f'_gkh{s}{wy:.1f}{dz}', (0.03, gw, 0.04), (s * (hw - 0.015), wy, (wz0 + wz1) / 2 + dz * gh / 2), m['rubber'], bevel=0.01))
            for dy in (-1, 1):
                P.append(box(name + f'_gkv{s}{wy:.1f}{dy}', (0.03, 0.04, gh), (s * (hw - 0.015), wy + dy * gw / 2, (wz0 + wz1) / 2), m['rubber'], bevel=0.01))
        # doors (closed, recessed)
        for dy in (0.95, L_ - 0.95):
            P.append(box(name + f'_door{s}{dy:.0f}', (0.03, 0.84, 1.98), (s * (hw - 0.04), dy, fz + 1.0), m['letter'], bevel=0.01))
            P.append(box(name + f'_dw{s}{dy:.0f}', (0.035, 0.45, 0.6), (s * (hw - 0.035), dy, fz + 1.55), m['glass'], bevel=0.05))
            P.append(tube(name + f'_dh{s}{dy:.0f}', [(s * (hw + 0.05), dy - 0.5, fz + 0.2), (s * (hw + 0.05), dy - 0.5, fz + 1.3)], 0.016, m['steel']))
            for k in range(2):
                P.append(box(name + f'_st{s}{dy:.0f}{k}', (0.32, 0.6, 0.03), (s * (hw - 0.05), dy, fz - 0.45 - k * 0.32), m['grille'], bevel=0.0))
        # rain gutter
        P.append(tube(name + f'_gut{s}', [(s * (hw + 0.01), 0.05, sz + 0.02), (s * (hw + 0.01), L_ - 0.05, sz + 0.02)], 0.018, m['skin']))
    # roof: AC units, vents
    for i, ay in enumerate((3.6, L_ - 3.6)):
        P.append(box(name + f'_ac{i}', (1.75, 2.8, 0.32), (0, ay, rz + 0.12), m['roof'], bevel=0.1, segs=3))
        for k in range(2):
            P.append(cyl(name + f'_acf{i}{k}', 0.32, 0.05, (0, ay - 0.65 + k * 1.3, rz + 0.29), m=m['grille'], verts=24))
    for k in range(6):
        P.append(box(name + f'_vent{k}', (0.35, 0.5, 0.12), (0.35 * (1 if k % 2 else -1), 6 + k * 2.4, rz + 0.01), m['roof'], bevel=0.04))
    # ends: gangway bellows, buffers, coupler, end door with window
    for e, ey in ((-1, 0.0), (1, L_)):
        P.append(box(name + f'_bel{e}', (1.25, 0.30, 2.3), (0, ey + e * 0.12, fz + 1.15), m['rubber'], bevel=0.08, segs=3))
        for s in (-1, 1):
            P.append(cyl(name + f'_buf{e}{s}', 0.19, 0.45, (s * 0.88, ey + e * 0.22, 1.05), rot=(math.pi / 2, 0, 0), m=m['steel'], verts=20))
            P.append(cyl(name + f'_bufp{e}{s}', 0.22, 0.04, (s * 0.88, ey + e * 0.45, 1.05), rot=(math.pi / 2, 0, 0), m=m['black'], verts=20))
        P.append(box(name + f'_cpl{e}', (0.25, 0.5, 0.22), (0, ey + e * 0.25, 1.0), m['steel'], bevel=0.02))
        # end wall around the gangway door (door 0.9 wide x 2.0 high)
        ez = ey - e * 0.025
        for s in (-1, 1):
            P.append(box(name + f'_ew{e}{s}', (hw - 0.47, 0.05, sz - fz + 0.15), (s * (0.45 + (hw - 0.47) / 2), ez, (fz - 0.15 + sz) / 2), m['skin'], bevel=0.01))
        P.append(box(name + f'_ewt{e}', (0.92, 0.05, sz - fz - 2.0), (0, ez, (fz + 2.0 + sz) / 2), m['skin'], bevel=0.0))
        rp = [(px, pz) for px, pz in outer if pz >= sz - 0.001]
        rp = rp + [(-px, pz) for px, pz in reversed(rp)]
        cp = bpy.data.meshes.new(name + f'_cap{e}'); bmc = bmesh.new()
        vv = [bmc.verts.new((px, ez, pz)) for px, pz in rp]
        bmc.faces.new(vv); bmesh.ops.solidify(bmc, geom=bmc.faces[:], thickness=0.05); bmc.to_mesh(cp); bmc.free()
        co = bpy.data.objects.new(name + f'_cap{e}', cp); link(co); cp.materials.append(m['roof']); P.append(co)
        P.append(box(name + f'_ed{e}', (0.86, 0.03, 1.98), (0, ey - e * 0.03, fz + 1.0), m['letter'], bevel=0.01))
        P.append(box(name + f'_edw{e}', (0.5, 0.035, 0.7), (0, ey - e * 0.03, fz + 1.5), m['glass'], bevel=0.05))
    if tail:
        for s in (-1, 1):
            P.append(cyl(name + f'_tl{s}', 0.10, 0.06, (s * 1.05, L_ + 0.04, fz + 0.45), rot=(math.pi / 2, 0, 0), m=m['tail'], verts=20))
            P.append(cyl(name + f'_tlb{s}', 0.13, 0.05, (s * 1.05, L_ + 0.02, fz + 0.45), rot=(math.pi / 2, 0, 0), m=m['black'], verts=20))
    # underframe
    P.append(box(name + '_uf', (2.5, L_ - 0.4, 0.3), (0, L_ / 2, fz - 0.28), m['black'], bevel=0.03))
    rnd = random.Random(seed)
    for i in range(7):
        P.append(box(name + f'_eq{i}', (rnd.uniform(1.0, 2.1), rnd.uniform(0.7, 1.7), rnd.uniform(0.35, 0.55)), (rnd.uniform(-0.3, 0.3), 5.5 + i * 2.1, fz - 0.62), m['black'], bevel=0.03))
    for by in (2.6, L_ - 2.6):
        P += coach_bogie(name + f'_bg{by:.0f}', by, m)
    if interior:
        P += coach_interior(name, L_, fz, hw - t, win_y, pitch, m, rnd)
    for p in list(P):
        pass
    o = to_mesh_join(P, name)
    bpy.data.collections.remove(cut_c)
    o.location = (X0, Y0, 0)
    o['win_y'] = win_y; o['floor_z'] = fz
    return o

def coach_bogie(name, cy, m):
    P = []
    for s in (-1, 1):
        sx = s * 1.0
        P.append(prism(name + f'_side{s}', [(cy - 1.5, 0.45), (cy + 1.5, 0.45), (cy + 1.3, 0.95), (cy - 1.3, 0.95)], sx - 0.05, sx + 0.05, m['black'], 0.03))
        for k in (-1, 1):
            wy = cy + k * 1.25
            P.append(cyl(name + f'_wh{s}{k}', 0.46, 0.13, (s * 0.72, wy, 0.46), rot=(0, math.pi / 2, 0), m=m['wheel'], verts=32, bevel=0.01))
            P.append(cyl(name + f'_hub{s}{k}', 0.15, 0.12, (sx + s * 0.06, wy, 0.46), rot=(0, math.pi / 2, 0), m=m['steel'], verts=16))
        P.append(cyl(name + f'_air{s}', 0.24, 0.28, (sx, cy, 0.95), m=m['rubber'], verts=20))
        P.append(cyl(name + f'_dmp{s}', 0.05, 0.5, (sx + s * 0.12, cy + 0.6, 0.75), rot=(0.5, 0, 0), m=m['steel'], verts=10))
    P.append(box(name + '_bol', (2.1, 0.5, 0.25), (0, cy, 0.78), m['black'], bevel=0.03))
    return P

def coach_interior(name, L_, fz, iw, win_y, pitch, m, rnd):
    P = []
    P.append(box(name + '_floor', (2 * iw, L_ - 0.1, 0.06), (0, L_ / 2, fz + 0.02), m['floor'], bevel=0.0))
    # inner wall lining is the shell's inside (skin material) -> add lining panels below/above windows
    for s in (-1, 1):
        P.append(box(name + f'_lin{s}', (0.02, L_ - 0.4, 0.92), (s * (iw - 0.012), L_ / 2, fz + 0.5), m['inner'], bevel=0.0))
        P.append(box(name + f'_sill{s}', (0.14, L_ - 0.4, 0.04), (s * (iw - 0.07), L_ / 2, 2.12), m['inner'], bevel=0.01))
        P.append(box(name + f'_lup{s}', (0.02, L_ - 0.4, 0.40), (s * (iw - 0.012), L_ / 2, 3.25), m['inner'], bevel=0.0))
        # luggage rack
        P.append(box(name + f'_rack{s}', (0.42, L_ - 2.4, 0.03), (s * (iw - 0.25), L_ / 2, 3.12), m['grille'], bevel=0.0))
        P.append(tube(name + f'_rackr{s}', [(s * (iw - 0.46), 1.2, 3.14), (s * (iw - 0.46), L_ - 1.2, 3.14)], 0.012, m['steel']))
        # curtains tied at window pillars
        for wy in win_y:
            P.append(box(name + f'_cur{s}{wy:.1f}', (0.05, 0.16, 0.85), (s * (iw - 0.06), wy + pitch / 2 - 0.08, 2.62), m['curtain'], bevel=0.02))
    # ceiling panel with light strip
    P.append(box(name + '_ceil', (2 * iw - 0.4, L_ - 0.4, 0.03), (0, L_ / 2, 3.62), m['inner'], bevel=0.0))
    for s in (-1, 1):
        P.append(box(name + f'_cl{s}', (0.10, L_ - 1.6, 0.02), (s * 0.55, L_ / 2, 3.60), m['light'], bevel=0.0))
    # vestibule partitions at both ends with door
    for e, py in ((0, 1.55), (1, L_ - 1.55)):
        for s in (-1, 1):
            P.append(box(name + f'_part{e}{s}', (iw - 0.45, 0.05, 2.35), (s * (iw / 2 + 0.22), py, fz + 1.18), m['inner'], bevel=0.0))
        P.append(box(name + f'_pgl{e}', (0.86, 0.02, 0.9), (0, py, fz + 1.5), m['glass'], bevel=0.0))
    # seats 2+2
    rows = int((L_ - 3.6) / 1.02)
    for r in range(rows):
        sy = 1.95 + r * 1.02
        for s in (-1, 1):
            for k in range(2):
                sx = s * (0.52 + k * 0.50)
                P += seat(name + f'_s{r}{s}{k}', sx, sy, fz, m)
    return P

def seat(name, sx, sy, fz, m):
    """Airline seat facing -Y (toward y0 / front). Cushion top at fz+0.46."""
    P = []
    P.append(box(name + 'c', (0.48, 0.48, 0.13), (sx, sy, fz + 0.40), m['seat'], bevel=0.05, segs=3))
    bk = box(name + 'b', (0.48, 0.12, 0.72), (sx, sy + 0.27, fz + 0.82), m['seat'], bevel=0.05, segs=3)
    bk.rotation_euler = (math.radians(-9), 0, 0); P.append(bk)
    hc = box(name + 'h', (0.40, 0.03, 0.22), (sx, sy + 0.20, fz + 1.07), m['seatcover'], bevel=0.01)
    hc.rotation_euler = (math.radians(-9), 0, 0); P.append(hc)
    P.append(box(name + 'f', (0.06, 0.40, 0.33), (sx, sy, fz + 0.18), m['steel'], bevel=0.01))
    P.append(box(name + 'a', (0.05, 0.42, 0.04), (sx + 0.25, sy + 0.02, fz + 0.62), m['black'], bevel=0.015))
    return P


# ---------------- loco cab interior ----------------
def cab_mats():
    return dict(
        wall=grime_mat('cabWall', (0.36, 0.42, 0.40), rough=0.7, amount=0.35, dirt=(0.25, 0.23, 0.2), scale=3, streak=False),
        desk=grime_mat('cabDesk', (0.16, 0.18, 0.19), rough=0.6, amount=0.3, dirt=(0.1, 0.1, 0.1), streak=False),
        floor=grime_mat('cabFloor', (0.10, 0.10, 0.10), rough=0.8, amount=0.5, streak=False),
        seat=grime_mat('cabSeat', (0.08, 0.08, 0.09), rough=0.85, amount=0.2, streak=False),
        screen=mat('dmiOff', (0.01, 0.012, 0.015), rough=0.15),
        screenOn=mat('dmiOn', (0.02, 0.05, 0.08), rough=0.15, emit=(0.25, 0.6, 1.0), estr=1.2),
        amber=mat('cabAmber', (0.6, 0.4, 0.0), rough=0.2, emit=(1, 0.65, 0.1), estr=10),
        green=mat('cabGreen', (0.0, 0.5, 0.1), rough=0.2, emit=(0.1, 1, 0.3), estr=8),
        red=mat('cabRed', (0.5, 0.0, 0.0), rough=0.2, emit=(1, 0.05, 0.02), estr=10),
        dark=mat('cabLampOff', (0.05, 0.05, 0.05), rough=0.3),
        metal=grime_mat('cabMetal', (0.45, 0.45, 0.44), rough=0.35, metal=1.0, amount=0.3),
        yellow=mat('guardYellow', (0.8, 0.55, 0.02), rough=0.4),
        label=mat('cabLabel', (0.85, 0.85, 0.8), rough=0.5),
    )

def cab_interior(name, hw, deck1, atc_on=True):
    """Driver's desk on the right (-X? ENR drives on left side: driver at +X side looking -Y)."""
    cm = cab_mats(); P = []
    fz = deck1 + 0.05
    P.append(box(name + '_cfloor', (2 * hw - 0.2, 3.6, 0.04), (0, 2.25, fz), cm['floor'], bevel=0.0))
    # desk across the front under the windshield
    # nose block + overhanging desk with knee recess underneath
    P.append(prism(name + '_cdesk', [(0.45, fz), (0.95, fz), (0.95, fz + 0.62), (1.55, fz + 0.62), (1.55, fz + 0.95), (1.05, fz + 1.08), (0.45, fz + 1.02)], -hw + 0.12, hw - 0.12, cm['desk'], 0.02))
    P.append(box(name + '_kick', (2 * hw - 0.3, 0.02, 0.5), (0, 0.96, fz + 0.30), cm['dark'], bevel=0.0))
    # driver console (right side, +X): sloped panel with DMI screen, gauges, ATC section
    dx = 0.72
    sp = box(name + '_cslope', (1.28, 0.58, 0.04), (dx - 0.08, 1.30, fz + 1.12), cm['desk'], bevel=0.01)
    sp.rotation_euler = (math.radians(-32), 0, 0); P.append(sp)
    def onslope(u, v, h=0.025):   # u across (x), v from far (high) edge 0 toward the driver 0.5; panel faces the driver
        a = math.radians(32)
        tt = Vector((0, math.cos(a), -math.sin(a))); nn = Vector((0, math.sin(a), math.cos(a)))
        return Vector((dx + u, 1.30, fz + 1.12)) + tt * (v - 0.25) + nn * h
    rot = (math.radians(-32), 0, 0)
    # two displays in bezels: speed / ATC state, and traction diagnostics
    for k, (u, w_, h_, img) in enumerate(((-0.40, 0.34, 0.255, 'dmi.png'), (0.00, 0.30, 0.225, 'dmi2.png'))):
        bz = box(name + f'_bez{k}', (w_ + 0.05, h_ + 0.05, 0.03), onslope(u, 0.20, 0.025), cm['dark'], bevel=0.05); bz.rotation_euler = rot; P.append(bz)
        P.append(screen(name + f'_scr{k}', w_, h_, onslope(u, 0.20, 0.041), rot, img, strength=5.0, flip=True))
    for i in range(4):   # air gauges: brake pipe, main reservoir, brake cylinder, equalising
        u, v = 0.27 + (i % 2) * 0.13, 0.12 + (i // 2) * 0.15
        g = cyl(name + f'_gauge{i}', 0.055, 0.02, onslope(u, v), rot=rot, m=cm['label'], verts=24); P.append(g)
        P.append(decal(name + f'_gdial{i}', 0.077, 0.077, onslope(u, v, 0.0355), rot, 'gauge.png', rough=0.3, flip=True))
        rim = cyl(name + f'_grim{i}', 0.062, 0.016, onslope(u, v, 0.018), rot=rot, m=cm['metal'], verts=24); P.append(rim)
        import mathutils
        Rn = mathutils.Matrix.Rotation(math.radians(-32), 3, 'X') @ mathutils.Matrix.Rotation(math.radians(40 - 55 * i), 3, 'Z')
        dn = Rn @ Vector((0, 1, 0))
        nd = box(name + f'_needle{i}', (0.004, 0.040, 0.003), onslope(u, v, 0.038) + dn * 0.016, cm['red'], bevel=0.0)
        nd.rotation_euler = Rn.to_euler(); P.append(nd)
        P.append(cyl(name + f'_gcap{i}', 0.006, 0.006, onslope(u, v, 0.039), rot=rot, m=cm['dark'], verts=10))
    for i in range(7):   # row of toggle switches with labels
        u = -0.56 + i * 0.06
        P.append(box(name + f'_tgb{i}', (0.03, 0.04, 0.012), onslope(u, 0.42, 0.03), cm['metal'], bevel=0.1))
        tg = box(name + f'_tg{i}', (0.008, 0.008, 0.035), onslope(u, 0.42, 0.05), cm['dark'], bevel=0.2); tg.rotation_euler = (math.radians(-32 + (20 if i % 3 else -20)), 0, 0); P.append(tg)
        lb = box(name + f'_tgl{i}', (0.04, 0.015, 0.002), onslope(u, 0.46, 0.026), cm['label'], bevel=0.0); lb.rotation_euler = rot; P.append(lb)
    # ATC block: labelled strip with three lamps and a guarded isolation switch
    P.append(box(name + '_atcplate', (0.34, 0.12, 0.006), onslope(0.06, 0.42, 0.006), cm['label'], bevel=0.0))
    P[-1].rotation_euler = (math.radians(-32), 0, 0)
    lamps = [('green' if atc_on else 'dark'), ('dark' if atc_on else 'amber'), ('dark' if atc_on else 'red')]
    for i, lm in enumerate(lamps):
        P.append(cyl(name + f'_atcl{i}', 0.014, 0.015, onslope(-0.05 + i * 0.07, 0.42, 0.012), rot=(math.radians(-32), 0, 0), m=cm[lm], verts=14))
    sw_base = onslope(0.19, 0.42, 0.03)
    P.append(box(name + '_atcsw', (0.035, 0.05, 0.02), sw_base, cm['metal'], bevel=0.1))
    lever = box(name + '_atclev', (0.012, 0.012, 0.06), sw_base + Vector((0, 0, 0.03)), cm['metal'], bevel=0.2)
    lever.rotation_euler = (math.radians(-32 + (-25 if atc_on else 25)), 0, 0); P.append(lever)
    guard = box(name + '_atcgrd', (0.05, 0.07, 0.004), sw_base + Vector((0, -0.03, 0.065)), cm['yellow'], bevel=0.1)
    guard.rotation_euler = (math.radians(40 if not atc_on else -32), 0, 0); P.append(guard)
    # control stand on the desk top to the driver's left: throttle quadrant, then automatic + independent brake valves
    def stand(nm, x, w_, col, lever_ang, knob_m):
        P.append(box(name + f'_{nm}b', (w_, 0.30, 0.10), (x, 1.38, fz + 1.02), cm['dark'], bevel=0.08))
        P.append(box(name + f'_{nm}q', (w_ * 0.6, 0.22, 0.012), (x, 1.38, fz + 1.075), cm['metal'], bevel=0.0))
        lv = box(name + f'_{nm}l', (0.025, 0.20, 0.02), (x, 1.45, fz + 1.11), col, bevel=0.2); lv.rotation_euler = (math.radians(lever_ang), 0, 0); P.append(lv)
        P.append(cyl(name + f'_{nm}k', 0.022, 0.07, (x, 1.54, fz + 1.13), rot=(0, math.pi / 2, 0), m=knob_m, verts=12))
    stand('thr', dx - 0.78, 0.12, cm['metal'], 12, cm['dark'])
    stand('abv', dx - 1.00, 0.14, cm['metal'], 18, cm['red'])
    stand('ibv', dx - 1.18, 0.10, cm['metal'], 10, cm['dark'])
    # left (assistant) side: radio handset + small panel
    P.append(box(name + '_radio', (0.30, 0.18, 0.12), (-0.75, 1.35, fz + 1.18), cm['dark'], bevel=0.1))
    # seats
    for sx, nm in ((dx, 'drv'), (-0.75, 'ast')):
        P.append(box(name + f'_{nm}s', (0.50, 0.48, 0.10), (sx, 1.98, fz + 0.62), cm['seat'], bevel=0.1, segs=2))
        P.append(box(name + f'_{nm}b', (0.48, 0.10, 0.62), (sx, 2.25, fz + 0.98), cm['seat'], bevel=0.1, segs=2))
        P.append(cyl(name + f'_{nm}p', 0.04, 0.60, (sx, 2.03, fz + 0.30), m=cm['metal'], verts=12))
        P.append(cyl(name + f'_{nm}f', 0.25, 0.03, (sx, 2.03, fz + 0.03), m=cm['metal'], verts=20))
    # back wall with door, sun visors, cab light
    P.append(box(name + '_cbw', (2 * hw - 0.2, 0.06, 2.75), (0, 4.05, fz + 1.37), cm['wall'], bevel=0.0))
    for s in (-1, 1):
        v = box(name + f'_visor{s}', (0.9, 0.25, 0.01), (s * 0.66, 1.80, 4.05), cm['dark'], bevel=0.0)
        v.rotation_euler = (math.radians(-20), 0, 0); P.append(v)
    P.append(box(name + '_clight', (0.4, 0.15, 0.03), (0, 2.8, 4.24), mat('cabLight', (1, 1, 1), emit=(1, 0.95, 0.85), estr=3), bevel=0.0))
    return P
