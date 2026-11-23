"""EP03 Egypt train - scene building library (bpy 5.2)."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix

A = '/home/claude/ep03/assets/'

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    sc.cycles.use_adaptive_sampling = True
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Base Contrast'
    sc.render.film_transparent = False
    return sc

# ---------------- materials ----------------
def mat(name, color=(0.8,0.8,0.8), rough=0.5, metal=0.0, emit=None, estr=0.0, coat=0.0, alpha=1.0, trans=0.0):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Alpha'].default_value = alpha
    b.inputs['Transmission Weight'].default_value = trans
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = estr
    return m

def grime_mat(name, color, rough=0.45, metal=0.0, dirt=(0.18,0.14,0.10), amount=0.35, scale=3.0, coat=0.0, streak=True):
    """Principled with noise-driven dirt + roughness variation + bump."""
    m = bpy.data.materials.get(name)
    if m: return m
    m = mat(name, color, rough, metal, coat=coat)
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = 8
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    # vertical streaks: object z gradient
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    wv = N.new('ShaderNodeTexWave'); wv.wave_type='BANDS'; wv.bands_direction='X'; wv.inputs['Scale'].default_value=6; wv.inputs['Distortion'].default_value=12; wv.inputs['Detail'].default_value=4
    L.new(tc.outputs['Object'], wv.inputs['Vector'])
    mixf = N.new('ShaderNodeMath'); mixf.operation='MULTIPLY'
    L.new(nz.outputs['Fac'], mixf.inputs[0]); L.new(wv.outputs['Fac'], mixf.inputs[1])
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = 0.15; ramp.color_ramp.elements[1].position = 0.55
    L.new((mixf.outputs[0] if streak else nz.outputs['Fac']), ramp.inputs[0])
    am = N.new('ShaderNodeMath'); am.operation='MULTIPLY'; am.inputs[1].default_value = amount
    L.new(ramp.outputs['Color'], am.inputs[0])
    mix = N.new('ShaderNodeMix'); mix.data_type='RGBA'
    mix.inputs['A'].default_value = (*color,1); mix.inputs['B'].default_value = (*dirt,1)
    L.new(am.outputs[0], mix.inputs['Factor']); L.new(mix.outputs['Result'], b.inputs['Base Color'])
    rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = rough; rr.inputs['To Max'].default_value = min(1, rough+0.4)
    L.new(am.outputs[0], rr.inputs['Value']); L.new(rr.outputs['Result'], b.inputs['Roughness'])
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 40
    L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08
    L.new(nz2.outputs['Fac'], bump.inputs['Height']); L.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

# ---------------- geometry helpers ----------------
def link(o, coll=None):
    (coll or bpy.context.scene.collection).objects.link(o); return o

def box(name, size, loc, m=None, bevel=0.02, segs=2, coll=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x*size[0], v.co.y*size[1], v.co.z*size[2]))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); o.location = loc
    if bevel > 0:
        md = o.modifiers.new('bev','BEVEL'); md.width = bevel; md.segments = segs; md.limit_method='ANGLE'
        o.modifiers.new('wn','WEIGHTED_NORMAL').keep_sharp = True
    if m: me.materials.append(m)
    return link(o, coll)

def cyl(name, r, depth, loc, rot=(0,0,0), m=None, verts=24, coll=None, bevel=0.0):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=depth)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); o.location = loc; o.rotation_euler = rot
    for p in me.polygons: p.use_smooth = True
    if bevel:
        md = o.modifiers.new('bev','BEVEL'); md.width=bevel; md.segments=2; md.limit_method='ANGLE'
    if m: me.materials.append(m)
    return link(o, coll)

def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join(); objs[0].name = name
    return objs[0]

def coll(name):
    c = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); return c

# ---------------- world / light ----------------
def world(hdr='spruit_sunrise_1k.hdr', strength=0.6, rot=0.0):
    w = bpy.data.worlds.new('W'); bpy.context.scene.world = w; w.use_nodes = True
    N = w.node_tree.nodes; L = w.node_tree.links
    bg = N['Background']; bg.inputs['Strength'].default_value = strength
    env = N.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(A+hdr)
    mp = N.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value[2] = rot
    tc = N.new('ShaderNodeTexCoord')
    L.new(tc.outputs['Generated'], mp.inputs['Vector']); L.new(mp.outputs['Vector'], env.inputs['Vector'])
    L.new(env.outputs['Color'], bg.inputs['Color'])
    return w

def sun(elev_deg, azim_deg, strength=4.0, color=(1.0,0.86,0.7), angle=1.0):
    d = bpy.data.lights.new('Sun','SUN'); d.energy = strength; d.color = color; d.angle = math.radians(angle)
    o = bpy.data.objects.new('Sun', d)
    # azimuth measured from +Y (north) clockwise toward +X (east); light points along -dir
    el, az = math.radians(elev_deg), math.radians(azim_deg)
    dirv = Vector((math.sin(az)*math.cos(el), math.cos(az)*math.cos(el), math.sin(el)))
    o.rotation_euler = (-dirv).to_track_quat('-Z','Y').to_euler()
    return link(o)

def camera(loc, target, lens=85, name='Cam'):
    c = bpy.data.cameras.new(name); c.lens = lens; c.sensor_width = 36; c.clip_end = 6000
    o = bpy.data.objects.new(name, c); o.location = loc
    o.rotation_euler = (Vector(target)-Vector(loc)).to_track_quat('-Z','Y').to_euler()
    link(o); bpy.context.scene.camera = o
    return o

def depth_haze(color=(0.80,0.74,0.64), start=40.0, end=900.0, max_fac=0.75):
    """Compositor aerial perspective using Z pass (cheap, CPU friendly)."""
    sc = bpy.context.scene; sc.view_layers[0].use_pass_z = True
    sc.use_nodes = True
    nt = sc.compositing_node_group if hasattr(sc,'compositing_node_group') and sc.compositing_node_group else None
    if nt is None:
        nt = bpy.data.node_groups.new('Comp','CompositorNodeTree')
        sc.compositing_node_group = nt
    N = nt.nodes; L = nt.links
    for n in list(N): N.remove(n)
    rl = N.new('CompositorNodeRLayers')
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = start; mr.inputs['From Max'].default_value = end
    mr.inputs['To Max'].default_value = max_fac; mr.clamp = True
    L.new(rl.outputs['Depth'], mr.inputs['Value'])
    pw = N.new('ShaderNodeMath'); pw.operation='POWER'; pw.inputs[1].default_value = 0.7
    L.new(mr.outputs['Result'], pw.inputs[0])
    mix = N.new('ShaderNodeMix'); mix.data_type='RGBA'
    L.new(pw.outputs[0], mix.inputs['Factor']); L.new(rl.outputs['Image'], mix.inputs['A'])
    mix.inputs['B'].default_value = (*color,1)
    out = N.new('NodeGroupOutput') if False else None
    try:
        nt.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        go = N.new('NodeGroupOutput'); L.new(mix.outputs['Result'], go.inputs[0])
    except Exception as e:
        comp = N.new('CompositorNodeComposite'); L.new(mix.outputs['Result'], comp.inputs['Image'])
    return nt

def sky_world(elev_deg, azim_deg, strength=0.25, aerosol=2.0, air=1.0):
    w = bpy.data.worlds.new('Sky'); bpy.context.scene.world = w; w.use_nodes = True
    N = w.node_tree.nodes; L = w.node_tree.links
    s = N.new('ShaderNodeTexSky'); s.sky_type = 'MULTIPLE_SCATTERING'
    s.sun_elevation = math.radians(elev_deg)
    # Blender sun_rotation: 0 = +Y? use azimuth measured from north clockwise -> rotation about Z
    s.sun_rotation = math.radians(azim_deg)
    s.aerosol_density = aerosol; s.air_density = air; s.sun_disc = True
    bg = N['Background']; bg.inputs['Strength'].default_value = strength
    L.new(s.outputs['Color'], bg.inputs['Color'])
    return w

def gn_scatter(target, inst_obj, density, seed=0, scale=(0.8,1.25), name='scatter'):
    """Geometry-nodes scatter of inst_obj on target faces (density per m^2)."""
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    dp = N.new('GeometryNodeDistributePointsOnFaces'); dp.inputs['Density'].default_value = density; dp.inputs['Seed'].default_value = seed
    oi = N.new('GeometryNodeObjectInfo'); oi.inputs['Object'].default_value = inst_obj; oi.transform_space='ORIGINAL'
    ip = N.new('GeometryNodeInstanceOnPoints')
    rv = N.new('FunctionNodeRandomValue'); rv.data_type='FLOAT_VECTOR'
    vv=[i for i in rv.inputs if i.type=='VECTOR']; vv[0].default_value = (0,0,0); vv[1].default_value = (0.08,0.08,6.283); rv.inputs['Seed'].default_value = seed+1
    rs = N.new('FunctionNodeRandomValue'); rs.data_type='FLOAT'
    fl = [i for i in rs.inputs if i.type=='VALUE' and i.name in ('Min','Max')]
    fl[0].default_value = scale[0]; fl[1].default_value = scale[1]; rs.inputs['Seed'].default_value = seed+2
    L.new(gi.outputs[0], dp.inputs['Mesh'])
    L.new(dp.outputs['Points'], ip.inputs['Points'])
    L.new(oi.outputs['Geometry'], ip.inputs['Instance'])
    L.new([o for o in rv.outputs if o.type=='VECTOR'][0], ip.inputs['Rotation'])
    L.new([o for o in rs.outputs if o.type=='VALUE'][0], ip.inputs['Scale'])
    L.new(ip.outputs['Instances'], go.inputs[0])
    md = target.modifiers.new(name, 'NODES'); md.node_group = ng
    return md

def window_glass(name, tint=(0.85, 0.88, 0.86), rough=0.03):
    """Architectural glass: reflective/transmissive for camera rays, transparent for shadow & diffuse rays
    (so sun and bounce light enter interiors without caustics noise)."""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links
    b = N['Principled BSDF']; b.inputs['Base Color'].default_value = (*tint, 1)
    b.inputs['Roughness'].default_value = rough; b.inputs['Transmission Weight'].default_value = 1.0
    tr = N.new('ShaderNodeBsdfTransparent'); tr.inputs['Color'].default_value = (*tint, 1)
    lp = N.new('ShaderNodeLightPath')
    mx = N.new('ShaderNodeMath'); mx.operation = 'MAXIMUM'
    L.new(lp.outputs['Is Shadow Ray'], mx.inputs[0]); L.new(lp.outputs['Is Diffuse Ray'], mx.inputs[1])
    sh = N.new('ShaderNodeMixShader')
    L.new(mx.outputs[0], sh.inputs['Fac']); L.new(b.outputs[0], sh.inputs[1]); L.new(tr.outputs[0], sh.inputs[2])
    L.new(sh.outputs[0], N['Material Output'].inputs['Surface'])
    return m

def screen(name, w, h, loc, rot, img, strength=2.5, flip=False):
    """Emissive display face (plane, UV-mapped, normal = local +Z, image 'up' = local +Y)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w/2, -h/2, 0), (w/2, -h/2, 0), (w/2, h/2, 0), (-w/2, h/2, 0)], [], [(0, 1, 2, 3)])
    me.uv_layers.new(); uv = me.uv_layers[0].data
    for i, c in enumerate(((1, 1), (0, 1), (0, 0), (1, 0)) if flip else ((0, 0), (1, 0), (1, 1), (0, 1))): uv[i].uv = c
    m = bpy.data.materials.get('scr_' + img)
    if not m:
        m = bpy.data.materials.new('scr_' + img); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
        tx = N.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load('/home/claude/ep03/assets/tex/' + img)
        uvn = N.new('ShaderNodeUVMap'); uvn.uv_map = 'UVMap'; L.new(uvn.outputs['UV'], tx.inputs['Vector'])
        b = N['Principled BSDF']; b.inputs['Base Color'].default_value = (0.01, 0.01, 0.01, 1); b.inputs['Roughness'].default_value = 0.32
        L.new(tx.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = strength
    me.materials.append(m)
    o = bpy.data.objects.new(name, me); link(o); o.location = loc; o.rotation_euler = rot
    return o

def decal(name, w, h, loc, rot, img, rough=0.5, flip=False):
    """Non-emissive printed face (plane, UV-mapped) - signs, gauge dials, labels."""
    o = screen(name, w, h, loc, rot, img, strength=0.0, flip=flip)
    m = bpy.data.materials.get('dcl_' + img)
    if not m:
        m = bpy.data.materials.new('dcl_' + img); m.use_nodes = True; N = m.node_tree.nodes
        tx = N.new('ShaderNodeTexImage'); tx.image = bpy.data.images.get(img) or bpy.data.images.load('/home/claude/ep03/assets/tex/' + img)
        uvn = N.new('ShaderNodeUVMap'); uvn.uv_map = 'UVMap'; m.node_tree.links.new(uvn.outputs['UV'], tx.inputs['Vector'])
        bs = N['Principled BSDF']; bs.inputs['Roughness'].default_value = rough
        m.node_tree.links.new(tx.outputs['Color'], bs.inputs['Base Color'])
    o.data.materials[0] = m
    return o
