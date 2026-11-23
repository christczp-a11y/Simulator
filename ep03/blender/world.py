"""EP03 shared world: Nile-valley farmland corridor around the crash site.
Track runs along Y (north = +Y). Main line x=0, second line x=-4.6. 2010 last coach rear end at y=0
(train 2010 extends south, -Y). Train 134 comes from the north heading south (-Y)."""
import bpy, bmesh, math, random
from mathutils import Vector
from lib import *
import props
from trains import locomotive, coach, mats as tmats

SUN = dict(elev=24, azim=118)   # morning sun, east-south-east (fits aftermath photos' low warm light)

def add_clouds(w, cover=0.42, seed=3.0):
    """Fair-weather cumulus + thin cirrus painted on a sky plane in the world shader (clouds shrink and
    fade toward the horizon the way a real cloud deck does)."""
    N = w.node_tree.nodes; L = w.node_tree.links; bg = N['Background']
    sky = bg.inputs['Color'].links[0].from_socket
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], sep.inputs[0])
    mz = N.new('ShaderNodeMath'); mz.operation = 'MAXIMUM'; mz.inputs[1].default_value = 0.03; L.new(sep.outputs['Z'], mz.inputs[0])
    def div(sock):
        d = N.new('ShaderNodeMath'); d.operation = 'DIVIDE'; L.new(sock, d.inputs[0]); L.new(mz.outputs[0], d.inputs[1]); return d
    dx, dy = div(sep.outputs['X']), div(sep.outputs['Y'])
    cv = N.new('ShaderNodeCombineXYZ'); L.new(dx.outputs[0], cv.inputs['X']); L.new(dy.outputs[0], cv.inputs['Y']); cv.inputs['Z'].default_value = seed
    def layer(scale, detail, rough, lo, hi, stretch=(1, 1, 1)):
        mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = stretch; L.new(cv.outputs[0], mp.inputs['Vector'])
        nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = detail
        nz.inputs['Roughness'].default_value = rough; L.new(mp.outputs[0], nz.inputs['Vector'])
        r = N.new('ShaderNodeMapRange'); r.inputs['From Min'].default_value = lo; r.inputs['From Max'].default_value = hi
        L.new(nz.outputs['Fac'], r.inputs['Value']); return r, nz
    cu, nzc = layer(1.1, 12, 0.62, 0.72 - cover * 0.5, 0.72 - cover * 0.5 + 0.16)
    ci, _ = layer(0.5, 6, 0.5, 0.58, 0.85, stretch=(0.25, 1.0, 1.0))
    ciw = N.new('ShaderNodeMath'); ciw.operation = 'MULTIPLY'; ciw.inputs[1].default_value = 0.35; L.new(ci.outputs[0], ciw.inputs[0])
    tot = N.new('ShaderNodeMath'); tot.operation = 'MAXIMUM'; L.new(cu.outputs[0], tot.inputs[0]); L.new(ciw.outputs[0], tot.inputs[1])
    fade = N.new('ShaderNodeMapRange'); fade.inputs['From Min'].default_value = 0.02; fade.inputs['From Max'].default_value = 0.16
    L.new(sep.outputs['Z'], fade.inputs['Value'])
    fac = N.new('ShaderNodeMath'); fac.operation = 'MULTIPLY'; L.new(tot.outputs[0], fac.inputs[0]); L.new(fade.outputs[0], fac.inputs[1])
    # cloud brightness follows the sky's own luminance (so exposure stays consistent), shaded underneath
    bw = N.new('ShaderNodeRGBToBW'); L.new(sky, bw.inputs[0])
    sh = N.new('ShaderNodeMapRange'); sh.inputs['From Min'].default_value = 0.3; sh.inputs['From Max'].default_value = 0.8
    sh.inputs['To Min'].default_value = 2.6; sh.inputs['To Max'].default_value = 1.5; L.new(nzc.outputs['Fac'], sh.inputs['Value'])
    lum = N.new('ShaderNodeMath'); lum.operation = 'MULTIPLY'; L.new(bw.outputs[0], lum.inputs[0]); L.new(sh.outputs[0], lum.inputs[1])
    cc = N.new('ShaderNodeMix'); cc.data_type = 'RGBA'; cc.inputs['Factor'].default_value = 1.0
    tint = N.new('ShaderNodeMix'); tint.data_type = 'RGBA'; tint.blend_type = 'MULTIPLY'; tint.inputs['Factor'].default_value = 1.0
    tint.inputs['B'].default_value = (1.0, 0.97, 0.93, 1)
    cmb = N.new('ShaderNodeCombineColor'); L.new(lum.outputs[0], cmb.inputs[0]); L.new(lum.outputs[0], cmb.inputs[1]); L.new(lum.outputs[0], cmb.inputs[2])
    L.new(cmb.outputs[0], tint.inputs['A'])
    mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; L.new(fac.outputs[0], mx.inputs['Factor']); L.new(sky, mx.inputs['A']); L.new(tint.outputs['Result'], mx.inputs['B'])
    L.new(mx.outputs['Result'], bg.inputs['Color'])

def lighting(exposure=-0.9, look='AgX - Medium High Contrast', haze=0.00016, clouds=0.42):
    sc = bpy.context.scene
    w = sky_world(SUN['elev'], SUN['azim'], strength=0.30, aerosol=1.6, air=1.0)
    if clouds: add_clouds(w, cover=clouds)
    sun(elev_deg=SUN['elev'], azim_deg=SUN['azim'], strength=4.2, color=(1.0, 0.86, 0.68), angle=0.7)
    sc.view_settings.exposure = exposure; sc.view_settings.look = look
    if haze:
        vol = box('haze', (3000, 3000, 160), (0, 0, 79), None, bevel=0)
        vm = bpy.data.materials.new('hazev'); vm.use_nodes = True; nt = vm.node_tree
        nt.nodes.remove(nt.nodes['Principled BSDF']); pv = nt.nodes.new('ShaderNodeVolumePrincipled')
        pv.inputs['Density'].default_value = haze; pv.inputs['Anisotropy'].default_value = 0.55
        pv.inputs['Color'].default_value = (0.92, 0.86, 0.76, 1)
        nt.links.new(pv.outputs[0], nt.nodes['Material Output'].inputs['Volume']); vol.data.materials.append(vm)
        vol.visible_shadow = False

def soil_mat(name='soil', c1=(0.065, 0.045, 0.03), c2=(0.045, 0.06, 0.022)):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links; b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.05; nz.inputs['Detail'].default_value = 6
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    rp = N.new('ShaderNodeValToRGB'); e = rp.color_ramp.elements
    e[0].position = 0.35; e[0].color = (*c1, 1); e[1].position = 0.65; e[1].color = (*c2, 1)
    L.new(nz.outputs['Fac'], rp.inputs[0])
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 3; L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs['Factor'].default_value = 0.2
    L.new(rp.outputs['Color'], mx.inputs['A']); L.new(nz2.outputs['Color'], mx.inputs['B'])
    L.new(mx.outputs['Result'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.95
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.4
    nz3 = N.new('ShaderNodeTexNoise'); nz3.inputs['Scale'].default_value = 25; L.new(tc.outputs['Object'], nz3.inputs['Vector'])
    L.new(nz3.outputs['Fac'], bump.inputs['Height']); L.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def water_mat():
    m = bpy.data.materials.get('canal')
    if m: return m
    m = mat('canal', (0.06, 0.07, 0.045), rough=0.06, coat=0.0)
    N = m.node_tree.nodes; L = m.node_tree.links; b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.2
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.05
    L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

def sugarcane():
    """Taller cane clump (2.6-3.2 m) - dominant crop of Upper Egypt fields near El-Ayyat."""
    m_leaf = grime_mat('caneleaf', (0.10, 0.21, 0.04), rough=0.55, amount=0.45, dirt=(0.42, 0.36, 0.16), scale=1.5)
    m_st = grime_mat('canestalk', (0.30, 0.30, 0.12), rough=0.6, amount=0.4)
    rnd = random.Random(5); parts = []
    for s in range(5):
        ox, oy = rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15); H = rnd.uniform(2.4, 3.1)
        parts.append(cyl('st', 0.022, H, (ox, oy, H / 2), m=m_st, verts=6))
        for i in range(9):
            z = H * 0.35 + i * H * 0.07
            me = bpy.data.meshes.new('lf'); bm = bmesh.new(); vs = []
            Lf = rnd.uniform(1.0, 1.5); ang = rnd.uniform(0, 6.283)
            for k in range(7):
                t = k / 6; w = 0.035 * math.sin(math.pi * min(1, t * 1.2 + 0.1))
                px = t * Lf; pz = z + 0.45 * Lf * t - 0.75 * Lf * t * t
                for sg in (-1, 1):
                    v = Vector((px, sg * w, pz)); v.rotate(__import__('mathutils').Euler((0, 0, ang))); vs.append(bm.verts.new(v + Vector((ox, oy, 0))))
            for k in range(6): bm.faces.new((vs[2 * k], vs[2 * k + 1], vs[2 * k + 3], vs[2 * k + 2]))
            bm.to_mesh(me); bm.free(); o = bpy.data.objects.new('lf', me); me.materials.append(m_leaf); link(o); parts.append(o)
    p = join(parts, 'cane')
    for poly in p.data.polygons: poly.use_smooth = True
    return p

def clover_tuft():
    """Low dense berseem (Egyptian clover) clump."""
    gm = grime_mat('clover', (0.07, 0.19, 0.04), rough=0.7, amount=0.3, dirt=(0.25, 0.30, 0.10), scale=4)
    rnd = random.Random(2); parts = []
    for i in range(10):
        me = bpy.data.meshes.new('cl'); bm = bmesh.new()
        r = rnd.uniform(0.04, 0.07); cx, cy = rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12); z = rnd.uniform(0.15, 0.35)
        vs = [bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z + 0.02 * math.sin(3 * a))) for a in [k * 2 * math.pi / 6 for k in range(6)]]
        bm.faces.new(vs); bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new('cl', me); me.materials.append(gm); link(o); parts.append(o)
        parts.append(cyl('cs', 0.004, z, (cx, cy, z / 2), m=gm, verts=4))
    return join(parts, 'clover')

def ground_patch(xmin, xmax, ymin, ymax, z, m, name='patch'):
    bpy.ops.mesh.primitive_plane_add(size=1); f = bpy.context.object; f.name = name
    f.scale = ((xmax - xmin), (ymax - ymin), 1); f.location = ((xmin + xmax) / 2, (ymin + ymax) / 2, z)
    bpy.ops.object.transform_apply(scale=True); f.data.materials.append(m)
    return f

def field(xmin, xmax, ymin, ymax, density, obj, seed, z=-0.55, m=None):
    f = ground_patch(xmin, xmax, ymin, ymax, z, m or soil_mat(), 'field')
    gn_scatter(f, obj, density, seed)
    return f

def build(y_min=-400, y_max=900, quality=1.0, trains=True, gap134=None, crops=True, hole=None):
    """Shared world. gap134: distance (m) between 2010 tail (y=0) and 134 nose; None = no 134."""
    random.seed(7)
    # base ground and embankment
    g = ground_patch(-1500, 1500, -1500, 2500, -0.62, soil_mat(), 'ground')
    emb = box('emb', (14, y_max - y_min + 400, 0.6), (-2.3, (y_min + y_max) / 2, -0.9), grime_mat('embsoil', (0.085, 0.068, 0.052), 0.95, amount=0.6, scale=1, dirt=(0.05,0.045,0.035)), bevel=0.3, segs=3)
    tuft = props.grass_tuft(1); tuft.location = (0, 0, -500)
    for (x0, x1, dens, sd) in ((3.2, 6.4, 22.0, 5), (-11.5, -6.2, 12.0, 6)):
        gp = ground_patch(x0, x1, y_min - 200, y_max + 200, -0.59, bpy.data.materials['embsoil'], 'verge')
        gn_scatter(gp, tuft, dens * quality, sd, (0.35, 1.1), 'tufts')
    tm = props.M()
    props.track(0.0, y_min - 200, y_max + 400, tm)
    props.track(-4.6, y_min - 200, y_max + 400, tm)
    # irrigation canal east of the line (Ibrahimiya-style feeder, ~8 m wide)
    ground_patch(14, 22, y_min - 300, y_max + 600, -1.35, water_mat(), 'canal')
    for s, x in ((-1, 13.5), (1, 22.5)):
        b = box(f'bank{s}', (1.6, y_max - y_min + 900, 1.0), (x, (y_min + y_max) / 2 + 150, -1.05), bpy.data.materials['embsoil'], bevel=0.4, segs=3)
        b.rotation_euler = (0, s * 0.5, 0)
    # dirt road west
    ground_patch(-17, -12.5, y_min - 300, y_max + 600, -0.58, grime_mat('road', (0.30, 0.24, 0.17), 0.95, amount=0.5, scale=0.5), 'road')
    # power poles along road with sagging wires
    poles = []
    for y in range(int(y_min), int(y_max) + 300, 45):
        poles.append(props.pole((-12.0, y, -0.58), h=8.0))
    wire_m = mat('wire', (0.02, 0.02, 0.02), rough=0.6)
    for k in (-0.45, 0.45):
        pts = []
        for y in range(int(y_min), int(y_max) + 300 - 45, 45):
            for t in range(9):
                tt = t / 8; pts.append((-12.0 + k, y + 45 * tt, 7.0 - 0.9 * 4 * tt * (1 - tt)))
        from trains import tube
        tube('wire', pts, 0.008, wire_m)
    if crops:
        cane = sugarcane(); cane.location = (0, 0, -500)
        clov = clover_tuft(); clov.location = (0, 0, -500)
        maize = props.maize_plant(); maize.location = (0, 0, -500)
        q = quality
        if hole:
            field(6.5, 13.0, y_min, hole[0], 1.4 * q, cane, 1); field(6.5, 13.0, hole[1], y_max, 1.4 * q, cane, 1)
        else:
            field(6.5, 13.0, y_min, y_max, 1.4 * q, cane, 1)
        field(23.5, 70, y_min, y_max * 0.6, 1.2 * q, cane, 2)
        field(23.5, 70, y_max * 0.6, y_max, 6.0 * q, clov, 3, m=soil_mat('soil2', (0.10, 0.08, 0.04), (0.06, 0.09, 0.03)))
        field(-60, -18, y_min, 200, 1.0 * q, maize, 4)
        field(-60, -18, 200, y_max, 6.0 * q, clov, 5)
        field(70, 260, y_min, y_max + 400, 0.25 * q, cane, 6)
        field(-260, -60, y_min, y_max + 400, 0.22 * q, maize, 7)
    # palms in clusters + village
    pal = [props.palm(s) for s in range(6)]
    for p in pal: p.location = (0, 0, -500)
    rnd = random.Random(11)
    for cl in [(-25, 180), (30, 260), (-40, 520), (26, 640), (-70, 900), (90, 1100), (-120, 760), (140, 500), (-160, 1300), (45, 1350),
               (-30, -120), (35, -260), (-55, 40), (60, 60), (-90, -330), (80, -180)]:
        for k in range(rnd.randint(3, 8)):
            src = rnd.choice(pal)
            inst = bpy.data.objects.new('palm_i', src.data); link(inst)
            inst.location = (cl[0] + rnd.uniform(-10, 10), cl[1] + rnd.uniform(-10, 10), -0.6)
            inst.rotation_euler = (0, 0, rnd.uniform(0, 6.28)); s = rnd.uniform(0.8, 1.25); inst.scale = (s, s, s)
    for i, (x, y, w, d, h) in enumerate([(-55, 820, 10, 9, 9), (-68, 835, 8, 12, 6), (-48, 860, 12, 8, 12), (70, 980, 9, 9, 9),
                                         (84, 1000, 11, 8, 6), (-90, 1150, 14, 10, 12), (110, 1250, 10, 10, 9), (-75, -260, 10, 9, 9), (95, -320, 12, 9, 6)]):
        props.house(f'h{i}', (x, y, -0.6), (w, d, h), rot=rnd.uniform(-0.2, 0.2))
    out = {}
    if trains:
        # 2010: last coach rear end at y=0 -> coach front end y0=-24.6 .. rear y=0 ; train extends south
        out['tail'] = coach('t2010_0', y0=-24.0, interior=True, tail=True, seed=1)
        for i in range(1, 4):
            coach(f't2010_{i}', y0=-24.0 - i * 24.6, interior=False, seed=i + 1)
        if gap134 is not None:
            # 134 heads south: loco nose faces -Y; our loco is built facing -Y already
            out['loco'] = locomotive('l134', y0=gap134, lights=True)
            for i in range(3):
                coach(f't134_{i}', y0=gap134 + 21.6 + i * 24.6, interior=False, seed=10 + i)
    return out

def rock_variants(n=5, size=0.032, name='rock'):
    rm = grime_mat('ballastRock', (0.15, 0.14, 0.125), rough=0.85, amount=0.5, dirt=(0.14, 0.11, 0.08), scale=30)
    out = []
    for i in range(n):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=size)
        o = bpy.context.object; o.name = f'{name}{i}'
        rnd = random.Random(i * 7 + 1)
        for v in o.data.vertices:
            v.co *= rnd.uniform(0.7, 1.3)
        o.scale = (rnd.uniform(0.8, 1.4), rnd.uniform(0.8, 1.4), rnd.uniform(0.5, 0.8)); bpy.ops.object.transform_apply(scale=True)
        o.data.materials.append(rm); o.location = (0, 0, -600)
        out.append(o)
    return out

def ballast_rocks(x, y0, y1, density=900, seed=0):
    """Real stone instances over the ballast shoulders and between sleepers, for close shots."""
    rocks = bpy.data.collections.get('rocks')
    if rocks is None:
        rocks = bpy.data.collections.new('rocks'); bpy.context.scene.collection.children.link(rocks)
        for o in rock_variants():
            for c in o.users_collection: c.objects.unlink(o)
            rocks.objects.link(o)
        rocks.hide_render = False
    me = bpy.data.meshes.new('ballastTop'); bm = bmesh.new()
    prof = [(-2.6, -0.60), (-1.6, -0.22), (1.6, -0.22), (2.6, -0.60)]
    a = [bm.verts.new((x + p[0], y0, p[1])) for p in prof]; b = [bm.verts.new((x + p[0], y1, p[1])) for p in prof]
    for i in range(3): bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new('ballastTop', me); link(o)
    o.data.materials.append(bpy.data.materials['ballastV'])
    ng = bpy.data.node_groups.new('rockscatter', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    dp = N.new('GeometryNodeDistributePointsOnFaces'); dp.inputs['Density'].default_value = density; dp.inputs['Seed'].default_value = seed
    ci = N.new('GeometryNodeCollectionInfo'); ci.inputs['Collection'].default_value = rocks
    ci.inputs['Separate Children'].default_value = True; ci.inputs['Reset Children'].default_value = True
    ip = N.new('GeometryNodeInstanceOnPoints'); ip.inputs['Pick Instance'].default_value = True
    rv = N.new('FunctionNodeRandomValue'); rv.data_type = 'FLOAT_VECTOR'
    vv = [i for i in rv.inputs if i.type == 'VECTOR']; vv[1].default_value = (6.283, 6.283, 6.283)
    rs = N.new('FunctionNodeRandomValue'); rs.data_type = 'FLOAT'
    fl = [i for i in rs.inputs if i.type == 'VALUE' and i.name in ('Min', 'Max')]; fl[0].default_value = 0.6; fl[1].default_value = 1.5
    ri = N.new('FunctionNodeRandomValue'); ri.data_type = 'INT'
    ii = [i for i in ri.inputs if i.type == 'INT']; ii[0].default_value = 0; ii[1].default_value = 4
    jg = N.new('GeometryNodeJoinGeometry')
    L.new(gi.outputs[0], dp.inputs['Mesh']); L.new(dp.outputs['Points'], ip.inputs['Points'])
    L.new(ci.outputs[0], ip.inputs['Instance'])
    L.new([q for q in rv.outputs if q.type == 'VECTOR'][0], ip.inputs['Rotation'])
    L.new([q for q in rs.outputs if q.type == 'VALUE'][0], ip.inputs['Scale'])
    L.new([q for q in ri.outputs if q.type == 'INT'][0], ip.inputs['Instance Index'])
    L.new(ip.outputs['Instances'], jg.inputs[0]); L.new(gi.outputs[0], jg.inputs[0])
    L.new(jg.outputs[0], go.inputs[0])
    md = o.modifiers.new('rocks', 'NODES'); md.node_group = ng
    return o
