"""fp_render.py — first-person view from the captain's seat. Solid surfaces (the mesh of fp_geo.py) + procedural sky and ground.
Runs in Blender (-b -P fp_render.py -- args) or with the bpy module (python3 fp_render.py args).

  --geo nose.npz --tex panel.png --out DIR --tag T --t "-1000,0,10"   (times in milliseconds, 0 = first contact)
  --sim DIR      crash simulation from fp_mpm.py (needed for t > 0; without it the aircraft is undeformed)
The camera is the pilot's eye carried on at the aircraft's speed (a head cannot be slowed down in 30 ms), looking along the nose.
"""
import bpy, sys, os, json, time, argparse
import numpy as np
from mathutils import Matrix, Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fp_pose

ap = argparse.ArgumentParser()
ap.add_argument("--geo"); ap.add_argument("--tex"); ap.add_argument("--sim", default=""); ap.add_argument("--out"); ap.add_argument("--tag", default="fp")
ap.add_argument("--t", default="0"); ap.add_argument("--tfile", default=""); ap.add_argument("--stride", default="0,1"); ap.add_argument("--persistent", type=int, default=0); ap.add_argument("--max_frames", type=int, default=0); ap.add_argument("--denoiser", default="OIDN"); ap.add_argument("--res", default="1280x720"); ap.add_argument("--samples", type=int, default=96)
ap.add_argument("--device", default="CPU"); ap.add_argument("--lens", type=float, default=15.0); ap.add_argument("--look_down", type=float, default=4.0)
ap.add_argument("--exposure", type=float, default=-0.35); ap.add_argument("--sun_el", type=float, default=9.0); ap.add_argument("--sun_az", type=float, default=50.0)
ap.add_argument("--fstop", type=float, default=0.0); ap.add_argument("--blur", type=float, default=0.0); ap.add_argument("--threads", type=int, default=0)
ap.add_argument("--eye", default=""); ap.add_argument("--tear", type=float, default=0.02); ap.add_argument("--tear_failed", type=float, default=0.008); ap.add_argument("--rivet", type=float, default=0.008); ap.add_argument("--rivet_failed", type=float, default=0.0025); ap.add_argument("--panel_gain", type=float, default=3.0)
ap.add_argument("--fold", type=float, default=1.0); ap.add_argument("--fold_dead", type=float, default=0.02); ap.add_argument("--fold_max", type=float, default=60.0); ap.add_argument("--curl_radius", type=float, default=0.12); ap.add_argument("--step", type=float, default=0.5)
ap.add_argument("--world", default=""); ap.add_argument("--grass", type=int, default=900000); ap.add_argument("--refl", type=float, default=0.2); ap.add_argument("--fill", type=float, default=6.0)
ap.add_argument("--dust", type=float, default=14.0); ap.add_argument("--leaves", type=int, default=1500); ap.add_argument("--view", default="AgX"); ap.add_argument("--crop", default=""); ap.add_argument("--noworld", type=int, default=0); ap.add_argument("--leaf_r", type=float, default=1000.0); ap.add_argument("--grass_gain", type=float, default=1.0); ap.add_argument("--grass_lod", default="45,85")
A = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
W, H = map(int, A.res.split("x"))
def log(*a): print("[fp]", *a, flush=True)


def N(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items(): setattr(n, k, v)
    return n


def principled(nt, color, rough=0.5, metal=0.0):
    p = N(nt, "ShaderNodeBsdfPrincipled"); p.inputs["Base Color"].default_value = (*color, 1); p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal; return p


def mat_simple(name, color, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = N(nt, "ShaderNodeOutputMaterial"); p = principled(nt, color, rough, metal); nt.links.new(p.outputs[0], o.inputs["Surface"]); return m


def mat_two_sided(name, front, back, rf=0.6, rb=0.3):
    """front = the side the face normal points to (the cabin side of the skin), back = outside paint"""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = N(nt, "ShaderNodeOutputMaterial"); a = principled(nt, front, rf); b = principled(nt, back, rb); g = N(nt, "ShaderNodeNewGeometry"); mx = N(nt, "ShaderNodeMixShader")
    nt.links.new(g.outputs["Backfacing"], mx.inputs[0]); nt.links.new(a.outputs[0], mx.inputs[1]); nt.links.new(b.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], o.inputs["Surface"]); return m


def mat_glass(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = N(nt, "ShaderNodeOutputMaterial"); t = N(nt, "ShaderNodeBsdfTransparent"); t.inputs[0].default_value = (0.93, 0.96, 0.95, 1)
    gl = N(nt, "ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.03; fr = N(nt, "ShaderNodeFresnel"); fr.inputs["IOR"].default_value = 1.3
    mu = N(nt, "ShaderNodeMath", operation='MULTIPLY'); nt.links.new(fr.outputs[0], mu.inputs[0]); mu.inputs[1].default_value = A.refl
    mx = N(nt, "ShaderNodeMixShader"); nt.links.new(mu.outputs[0], mx.inputs[0]); nt.links.new(t.outputs[0], mx.inputs[1]); nt.links.new(gl.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], o.inputs["Surface"]); return m


def mat_paint(name, color, rough, x0):
    """painted aluminium skin: panel joints every 0.4 m along the fuselage and every 30 degrees around it, a row of rivets either side.
    Drawn from the REST position of the surface (attribute 'rest'), so the lines stay on the metal when it crumples."""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear(); L = nt.links.new
    o = N(nt, "ShaderNodeOutputMaterial"); p = principled(nt, color, rough); at = N(nt, "ShaderNodeAttribute"); at.attribute_name = "rest"; sp = N(nt, "ShaderNodeSeparateXYZ"); L(at.outputs["Vector"], sp.inputs[0])
    def math(op, a, b=None, c=None):
        q = N(nt, "ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b, c)):
            if v is None: continue
            if isinstance(v, (int, float)): q.inputs[i].default_value = v
            else: L(v, q.inputs[i])
        return q.outputs[0]
    sv = math('SUBTRACT', x0, sp.outputs[0]); ang = math('ARCTAN2', sp.outputs[1], sp.outputs[2]); rr = math('SQRT', math('ADD', math('MULTIPLY', sp.outputs[1], sp.outputs[1]), math('MULTIPLY', sp.outputs[2], sp.outputs[2])))
    def tri(x, period):                                           # distance to the nearest multiple of period
        f = math('FRACT', math('DIVIDE', x, period)); return math('MULTIPLY', math('ABSOLUTE', math('SUBTRACT', f, 0.5)), period), f
    ds_, _ = tri(math('ADD', math('SUBTRACT', sv, 0.55), 0.2), 0.4); ds = math('SUBTRACT', 0.2, ds_)                    # along the fuselage: joints at 0.55 + 0.4 k
    da_, _ = tri(math('ADD', ang, 0.2617994), 0.5235988); dt = math('MULTIPLY', math('SUBTRACT', 0.2617994, da_), rr)   # around it: every 30 degrees, as arc length
    line = math('MAXIMUM', math('LESS_THAN', ds, 0.0012), math('LESS_THAN', dt, 0.0012))
    def rivets(d, along):
        row = math('LESS_THAN', math('ABSOLUTE', math('SUBTRACT', d, 0.012)), 0.0028); _, f = tri(along, 0.022)
        return math('MULTIPLY', row, math('LESS_THAN', math('ABSOLUTE', math('SUBTRACT', f, 0.5)), 0.13))
    riv = math('MAXIMUM', rivets(ds, math('MULTIPLY', ang, rr)), rivets(dt, sv))
    nz = N(nt, "ShaderNodeTexNoise"); L(at.outputs["Vector"], nz.inputs["Vector"]); nz.inputs["Scale"].default_value = 3.0; nz.inputs["Detail"].default_value = 6.0
    dirt = N(nt, "ShaderNodeMapRange"); L(nz.outputs[0], dirt.inputs[0]); dirt.inputs[1].default_value = 0.35; dirt.inputs[2].default_value = 0.75; dirt.inputs[3].default_value = 1.0; dirt.inputs[4].default_value = 0.86
    k = math('MULTIPLY', math('SUBTRACT', 1.0, math('MULTIPLY', line, 0.75)), math('SUBTRACT', 1.0, math('MULTIPLY', riv, 0.30)))
    vm = N(nt, "ShaderNodeVectorMath", operation='SCALE'); vm.inputs[0].default_value = color; L(math('MULTIPLY', k, dirt.outputs[0]), vm.inputs["Scale"]); L(vm.outputs[0], p.inputs["Base Color"])
    bp = N(nt, "ShaderNodeBump"); L(math('ADD', line, math('MULTIPLY', riv, 0.5)), bp.inputs["Height"]); bp.inputs["Strength"].default_value = 0.6; bp.inputs["Distance"].default_value = -0.001; L(bp.outputs[0], p.inputs["Normal"])
    L(p.outputs[0], o.inputs["Surface"]); return m


def mat_edge(name, color, alpha=0.6, rough=0.35):
    """the broken edge of a transparency: frosted, lets some light through"""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = N(nt, "ShaderNodeOutputMaterial"); p = principled(nt, color, rough); t = N(nt, "ShaderNodeBsdfTransparent"); mx = N(nt, "ShaderNodeMixShader"); mx.inputs[0].default_value = alpha
    nt.links.new(t.outputs[0], mx.inputs[1]); nt.links.new(p.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], o.inputs["Surface"]); return m


def mat_panel(name, path, gain):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = N(nt, "ShaderNodeOutputMaterial"); p = principled(nt, (0.03, 0.03, 0.03), 0.55)
    uv = N(nt, "ShaderNodeUVMap"); mp = N(nt, "ShaderNodeMapping"); mp.inputs["Scale"].default_value = (-1, 1, 1); mp.inputs["Location"].default_value = (1, 0, 0)
    tx = N(nt, "ShaderNodeTexImage"); tx.image = bpy.data.images.load(path); tx.extension = 'EXTEND'
    nt.links.new(uv.outputs[0], mp.inputs[0]); nt.links.new(mp.outputs[0], tx.inputs[0])
    pw = N(nt, "ShaderNodeAttribute"); pw.attribute_name = "pow"; mg = N(nt, "ShaderNodeMath", operation='MULTIPLY'); nt.links.new(pw.outputs["Fac"], mg.inputs[0]); mg.inputs[1].default_value = gain
    dk = N(nt, "ShaderNodeMapRange"); nt.links.new(pw.outputs["Fac"], dk.inputs[0]); dk.inputs[3].default_value = 0.12; dk.inputs[4].default_value = 1.0
    bc = N(nt, "ShaderNodeVectorMath", operation='SCALE'); nt.links.new(tx.outputs["Color"], bc.inputs[0]); nt.links.new(dk.outputs[0], bc.inputs["Scale"])
    nt.links.new(bc.outputs[0], p.inputs["Base Color"]); nt.links.new(tx.outputs["Color"], p.inputs["Emission Color"])
    # the displays are drawn brighter against the daylight than real ones are, so that they can be read; their mirror image in the windshield must not get that boost (in daylight it is all but invisible)
    lp = N(nt, "ShaderNodeLightPath"); dm = N(nt, "ShaderNodeMapRange"); nt.links.new(lp.outputs["Is Glossy Ray"], dm.inputs[0]); dm.inputs[3].default_value = 1.0; dm.inputs[4].default_value = 0.08
    mg2 = N(nt, "ShaderNodeMath", operation='MULTIPLY'); nt.links.new(mg.outputs[0], mg2.inputs[0]); nt.links.new(dm.outputs[0], mg2.inputs[1]); nt.links.new(mg2.outputs[0], p.inputs["Emission Strength"])
    nt.links.new(p.outputs[0], o.inputs["Surface"]); return m


def haze(nt, shader_out):
    """distance haze: mixes a surface toward the sky colour near the horizon; returns the socket to plug into Surface"""
    cam = N(nt, "ShaderNodeCameraData"); k = N(nt, "ShaderNodeMath", operation='MULTIPLY'); nt.links.new(cam.outputs["View Distance"], k.inputs[0]); k.inputs[1].default_value = -1 / 5200.0
    hz = N(nt, "ShaderNodeMath", operation='POWER'); hz.inputs[0].default_value = 2.718281828; nt.links.new(k.outputs[0], hz.inputs[1])
    em = N(nt, "ShaderNodeEmission"); em.inputs[0].default_value = (0.62, 0.52, 0.46, 1); em.inputs[1].default_value = float(HAZE)
    mx = N(nt, "ShaderNodeMixShader"); nt.links.new(hz.outputs[0], mx.inputs[0]); nt.links.new(em.outputs[0], mx.inputs[1]); nt.links.new(shader_out, mx.inputs[2]); return mx.outputs[0]


def mat_vcol(name, rough=0.85, use_haze=True, leaf=1.6, trans=0.0, bump=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = N(nt, "ShaderNodeOutputMaterial"); p = N(nt, "ShaderNodeBsdfPrincipled"); p.inputs["Roughness"].default_value = rough
    at = N(nt, "ShaderNodeAttribute"); at.attribute_name = "Col"; g = N(nt, "ShaderNodeNewGeometry")
    nz = N(nt, "ShaderNodeTexNoise"); nt.links.new(g.outputs["Position"], nz.inputs["Vector"]); nz.inputs["Scale"].default_value = leaf; nz.inputs["Detail"].default_value = 5.0
    mr = N(nt, "ShaderNodeMapRange"); nt.links.new(nz.outputs[0], mr.inputs[0]); mr.inputs[1].default_value = 0.3; mr.inputs[2].default_value = 0.7; mr.inputs[3].default_value = 0.45; mr.inputs[4].default_value = 1.5
    vm = N(nt, "ShaderNodeVectorMath", operation='SCALE'); nt.links.new(at.outputs["Color"], vm.inputs[0]); nt.links.new(mr.outputs[0], vm.inputs["Scale"]); nt.links.new(vm.outputs[0], p.inputs["Base Color"])
    if bump > 0: bp = N(nt, "ShaderNodeBump"); nt.links.new(nz.outputs[0], bp.inputs["Height"]); bp.inputs["Strength"].default_value = bump; bp.inputs["Distance"].default_value = 0.4; nt.links.new(bp.outputs[0], p.inputs["Normal"])
    out = p.outputs[0]
    if trans > 0:                                                 # leaves and straw let light through: lit from behind they glow instead of going black
        tr = N(nt, "ShaderNodeBsdfTranslucent"); nt.links.new(vm.outputs[0], tr.inputs[0]); mx = N(nt, "ShaderNodeMixShader"); mx.inputs[0].default_value = trans
        nt.links.new(p.outputs[0], mx.inputs[1]); nt.links.new(tr.outputs[0], mx.inputs[2]); out = mx.outputs[0]
    nt.links.new(haze(nt, out) if use_haze else out, o.inputs["Surface"]); return m


def mat_points(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = N(nt, "ShaderNodeOutputMaterial"); p = N(nt, "ShaderNodeBsdfPrincipled"); p.inputs["Roughness"].default_value = 0.5
    ac = N(nt, "ShaderNodeAttribute"); ac.attribute_name = "col"; ae = N(nt, "ShaderNodeAttribute"); ae.attribute_name = "emit"
    nt.links.new(ac.outputs["Color"], p.inputs["Base Color"]); nt.links.new(ac.outputs["Color"], p.inputs["Emission Color"]); nt.links.new(ae.outputs["Fac"], p.inputs["Emission Strength"])
    nt.links.new(p.outputs[0], o.inputs["Surface"]); return m


def mat_ground(name, wdir, ext):
    """field colours, row directions, hedges and roads from the baked maps of fp_world.py; soil and stubble detail down to centimetres is procedural"""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear(); L = nt.links.new
    o = N(nt, "ShaderNodeOutputMaterial"); g = N(nt, "ShaderNodeNewGeometry")
    def math(op, a, b=None):
        q = N(nt, "ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b)):
            if v is None: continue
            if isinstance(v, (int, float)): q.inputs[i].default_value = v
            else: L(v, q.inputs[i])
        return q.outputs[0]
    def mixc(f, a, b):
        q = N(nt, "ShaderNodeMix", data_type='RGBA')
        for i, v in ((0, f), (6, a), (7, b)):
            if isinstance(v, (int, float)): q.inputs[i].default_value = v
            elif isinstance(v, tuple): q.inputs[i].default_value = v
            else: L(v, q.inputs[i])
        return q.outputs[2]
    def noise(scale, detail=6.0, rough=0.6):
        n = N(nt, "ShaderNodeTexNoise"); L(g.outputs["Position"], n.inputs["Vector"]); n.inputs["Scale"].default_value = scale; n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough; return n.outputs[0]
    mp = N(nt, "ShaderNodeMapping"); mp.inputs["Location"].default_value = (-ext[0] / ext[2], -ext[1] / ext[2], 0); mp.inputs["Scale"].default_value = (1 / ext[2], 1 / ext[2], 1)
    L(g.outputs["Position"], mp.inputs[0])
    t1 = N(nt, "ShaderNodeTexImage"); t1.image = bpy.data.images.load(os.path.join(wdir, "ground.png")); L(mp.outputs[0], t1.inputs[0])
    t2 = N(nt, "ShaderNodeTexImage"); t2.image = bpy.data.images.load(os.path.join(wdir, "ground2.png")); t2.image.colorspace_settings.name = 'Non-Color'; t2.interpolation = 'Closest'
    L(mp.outputs[0], t2.inputs[0]); sep = N(nt, "ShaderNodeSeparateColor"); L(t2.outputs["Color"], sep.inputs[0])
    rot = N(nt, "ShaderNodeVectorRotate", rotation_type='Z_AXIS'); L(g.outputs["Position"], rot.inputs["Vector"]); L(math('MULTIPLY', sep.outputs[0], -3.14159265), rot.inputs["Angle"])
    def rows(scale, dist):
        w = N(nt, "ShaderNodeTexWave"); L(rot.outputs[0], w.inputs["Vector"]); w.inputs["Scale"].default_value = scale; w.inputs["Distortion"].default_value = dist; w.bands_direction = 'Y'; return w.outputs[1]
    road = math('GREATER_THAN', sep.outputs[2], 0.75); f0 = math('MULTIPLY', math('GREATER_THAN', sep.outputs[2], 0.25), math('LESS_THAN', sep.outputs[2], 0.75))
    rowmask = math('MULTIPLY', math('GREATER_THAN', sep.outputs[0], 0.004), math('SUBTRACT', 1.0, math('MAXIMUM', sep.outputs[1], road)))
    big = noise(1 / 60.0, 5.0); mid = noise(1 / 3.0, 8.0); fine = noise(22.0, 9.0, 0.7)
    col = t1.outputs["Color"]
    col = mixc(math('MULTIPLY', big, 0.5), col, mixc(0.5, col, (0.10, 0.085, 0.05, 1)))
    col = mixc(math('MULTIPLY', math('MULTIPLY', rows(1.3, 0.8), rowmask), 0.55), col, mixc(0.62, col, (0.025, 0.02, 0.012, 1)))     # crop rows / stubble lines
    col = mixc(math('MULTIPLY', math('MULTIPLY', rows(0.045, 0.2), rowmask), 0.40), col, mixc(0.5, col, (0.05, 0.04, 0.025, 1)))    # tramlines
    col = mixc(math('MULTIPLY', mid, 0.55), col, mixc(0.6, col, (0.02, 0.022, 0.01, 1)))
    col = mixc(math('MULTIPLY', fine, 0.7), col, mixc(0.65, col, (0.30, 0.25, 0.15, 1)))
    # the field the aircraft comes down in carries real stubble (geometry) near the impact point; seen from the air that stubble shades itself,
    # so the bare ground of the same field is tinted to the measured colour of the stubble-covered part (otherwise the patch shows as a dark oval)
    tint = N(nt, "ShaderNodeMix", data_type='RGBA', blend_type='MULTIPLY'); L(f0, tint.inputs[0]); L(col, tint.inputs[6]); tint.inputs[7].default_value = (*FIELD_TINT, 1); col = tint.outputs[2]
    p = N(nt, "ShaderNodeBsdfPrincipled"); L(col, p.inputs["Base Color"]); p.inputs["Roughness"].default_value = 0.92
    try: p.inputs["Specular IOR Level"].default_value = 0.08      # bare soil has no sheen; with the default the low sky turns flat ground pale at grazing angles
    except Exception: pass
    bh = math('ADD', math('MULTIPLY', fine, 0.03), math('ADD', math('MULTIPLY', mid, 0.22), math('MULTIPLY', math('MULTIPLY', rows(1.3, 0.8), rowmask), 0.08)))
    bp = N(nt, "ShaderNodeBump"); L(bh, bp.inputs["Height"]); bp.inputs["Strength"].default_value = 0.7; L(bp.outputs[0], p.inputs["Normal"])
    L(haze(nt, p.outputs[0]), o.inputs["Surface"]); return m


def mesh_from(name, V, Q, C, sc, material, smooth=True):
    """V (n,3), Q (f,k) faces (k = 3 or 4), C (n,3) vertex colours"""
    k = Q.shape[1]; F = len(Q); me = bpy.data.meshes.new(name); me.vertices.add(len(V)); me.vertices.foreach_set("co", np.ascontiguousarray(V, np.float32).ravel())
    me.loops.add(k * F); me.polygons.add(F); me.loops.foreach_set("vertex_index", np.ascontiguousarray(Q, np.int32).ravel())
    me.polygons.foreach_set("loop_start", np.arange(F, dtype=np.int32) * k); me.polygons.foreach_set("loop_total", np.full(F, k, np.int32))
    ca = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT'); c4 = np.ones((len(V), 4), np.float32); c4[:, :3] = C; ca.data.foreach_set("color", c4.ravel())
    me.update(calc_edges=True); me.materials.append(material)
    if smooth:
        try: me.shade_smooth()
        except Exception: me.polygons.foreach_set("use_smooth", np.ones(F, bool))
    if sc is None: return me
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); return ob


GRASS = None


def build_world(wdir, sc):
    """trees, hedges, farm buildings (layout from fp_world.py) and the grass of the field the aircraft comes down in"""
    Wz = np.load(os.path.join(wdir, "world.npz")); T = Wz["trees"].astype(np.float64); Hd = Wz["hedges"].astype(np.float64); Bd = Wz["buildings"].astype(np.float64)
    rng = np.random.default_rng(4); mat = mat_vcol("world"); VV = []; QQ = []; CC = []; n = 0
    # trees: a lumpy ellipsoid crown on a trunk
    nl, nm = 8, 12; lat = np.linspace(0.10, np.pi - 0.30, nl + 1); lon = np.arange(nm) / nm * 2 * np.pi
    LA, LO = np.meshgrid(lat, lon, indexing="ij"); unit = np.stack([np.sin(LA) * np.cos(LO), np.sin(LA) * np.sin(LO), np.cos(LA)], -1)
    K = len(T); h = T[:, 2]; rc = h * T[:, 3]; rv = h * 0.36; ph = rng.uniform(0, 2 * np.pi, (K, 2))
    lump = 1 + 0.24 * np.sin(3 * LO[None] + ph[:, 0, None, None]) * np.sin(2.5 * LA[None] + ph[:, 1, None, None]) + rng.normal(0, 0.08, (K, nl + 1, nm))
    P = unit[None] * lump[..., None] * np.stack([rc, rc, rv], -1)[:, None, None, :]
    P[..., 0] += T[:, 0, None, None]; P[..., 1] += T[:, 1, None, None]; P[..., 2] += (h - rv)[:, None, None]
    u = rng.uniform(0, 1, (K, 1)); green = np.array([0.028, 0.060, 0.016]) * (1 - u) + np.array([0.075, 0.115, 0.030]) * u
    autumn = np.array([0.26, 0.16, 0.03]) * (1 - u) + np.array([0.30, 0.085, 0.02]) * u
    base = np.where(T[:, 4:5] > 0.74, autumn, green)
    shade = (0.50 + 0.85 * (np.cos(LA) + 1) / 2)[None, :, :, None] * rng.uniform(0.8, 1.2, (K, nl + 1, nm, 1))
    Cc = base[:, None, None, :] * shade
    # near trees get foliage: clumps of small leaf cards around the crown, so the outline is ragged instead of a smooth blob. The blob stays inside as the dark interior.
    near = np.flatnonzero((np.hypot(T[:, 0], T[:, 1]) < A.leaf_r) & (T[:, 0] > -400.0)); nlf = int(A.leaves)
    if len(near) and nlf:
        Kn = len(near); ncl = 46; cd_ = rng.normal(size=(Kn, ncl, 3)); cd_[..., 2] = np.abs(cd_[..., 2]) * 1.1 - 0.35; cd_ /= np.linalg.norm(cd_, axis=2, keepdims=True)
        crf = rng.uniform(0.80, 1.22, (Kn, ncl)); ci = rng.integers(0, ncl, (Kn, nlf)); ar = np.arange(Kn)[:, None]
        d_ = cd_[ar, ci] + rng.normal(0, 0.27, (Kn, nlf, 3)); d_ /= np.linalg.norm(d_, axis=2, keepdims=True)
        rr_ = crf[ar, ci] * rng.uniform(0.82, 1.10, (Kn, nlf)); rad3 = np.stack([rc, rc, rv], -1)[near][:, None, :]
        ctr = np.stack([T[near, 0], T[near, 1], (h - rv)[near]], -1)[:, None, :]; Pc = ctr + d_ * rr_[..., None] * rad3
        sz = (h[near] * 0.5 * (T[near, 3] / 0.35))[:, None, None] * rng.uniform(0.045, 0.085, (Kn, nlf, 1))
        e1 = rng.normal(size=(Kn, nlf, 3)); e1 /= np.linalg.norm(e1, axis=2, keepdims=True); e2 = rng.normal(size=(Kn, nlf, 3)); e2 /= np.linalg.norm(e2, axis=2, keepdims=True)
        L3 = np.stack([Pc - e1 * sz, Pc + e1 * sz, Pc + e2 * sz * 1.6], 2)                                # (Kn, nlf, 3 corners, 3)
        lc = base[near][:, None, :] * (0.50 + 0.95 * (d_[..., 2:3] + 1) / 2) * rng.uniform(0.6, 1.45, (Kn, nlf, 1)) * rng.uniform(0.92, 1.08, (Kn, nlf, 3))
        lm = mat_vcol("leaves", 0.6, use_haze=True, leaf=3.0, trans=0.35, bump=0.0)
        mesh_from("leaves", L3.reshape(-1, 3), np.arange(Kn * nlf * 3).reshape(-1, 3), np.repeat(lc.reshape(-1, 3), 3, axis=0), sc, lm, smooth=False)
        P[near] = ctr[:, None] + (P[near] - ctr[:, None]) * 0.84; Cc[near] *= 0.42
    idx = np.arange((nl + 1) * nm).reshape(nl + 1, nm); a = idx[:-1]; b = idx[1:]; q = np.stack([a, b, np.roll(b, -1, 1), np.roll(a, -1, 1)], -1).reshape(-1, 4)
    QQ.append((q[None] + (np.arange(K) * (nl + 1) * nm)[:, None, None]).reshape(-1, 4) + n); VV.append(P.reshape(-1, 3)); CC.append(Cc.reshape(-1, 3)); n += K * (nl + 1) * nm
    tr = h * 0.022; ang = np.arange(4) / 4 * 2 * np.pi; ring = np.stack([np.cos(ang), np.sin(ang)], -1)
    Pt = np.zeros((K, 2, 4, 3)); Pt[..., :2] = T[:, None, None, :2] + ring[None, None] * tr[:, None, None, None]; Pt[:, 1, :, 2] = (h - rv * 0.8)[:, None]
    idx = np.arange(8).reshape(2, 4); q = np.stack([idx[0], np.roll(idx[0], -1), np.roll(idx[1], -1), idx[1]], -1)
    QQ.append((q[None] + (np.arange(K) * 8)[:, None, None]).reshape(-1, 4) + n); VV.append(Pt.reshape(-1, 3)); CC.append(np.tile([0.045, 0.035, 0.025], (K * 8, 1))); n += K * 8
    # hedges: an irregular dark green wall along the field boundary
    for (ax, ay, bx, by, hh) in Hd:
        A0 = np.array([ax, ay]); B0 = np.array([bx, by]); ln = np.linalg.norm(B0 - A0); m = max(2, int(ln / 4.0) + 1)
        f = np.linspace(0, 1, m)[:, None]; c = A0 + (B0 - A0) * f; d = (B0 - A0) / ln; nr = np.array([-d[1], d[0]])
        w = rng.uniform(0.8, 1.4, (m, 1)); z = hh * rng.uniform(0.7, 1.25, m)
        S = np.zeros((m, 4, 3)); S[:, 0, :2] = c - nr * w; S[:, 1, :2] = c - nr * w * 0.8; S[:, 2, :2] = c + nr * w * 0.8; S[:, 3, :2] = c + nr * w; S[:, 1, 2] = z; S[:, 2, 2] = z
        idx = np.arange(m * 4).reshape(m, 4); q = np.concatenate([np.stack([idx[:-1, j], idx[1:, j], idx[1:, j + 1], idx[:-1, j + 1]], -1) for j in range(3)])
        cc = np.array([0.030, 0.058, 0.018]) * rng.uniform(0.7, 1.3, (m, 1, 1)) * np.array([0.6, 1.1, 1.1, 0.6])[None, :, None]
        QQ.append(q + n); VV.append(S.reshape(-1, 3)); CC.append(cc.reshape(-1, 3)); n += m * 4
    Vw = np.concatenate(VV); Qw = np.concatenate(QQ); Cw = np.concatenate(CC)
    mesh_from("trees", Vw, Qw, Cw, sc, mat, smooth=True)
    # buildings: walls + gable roof, flat shaded (vertices are not shared between faces)
    VV = []; CC = []
    walls = [(0.62, 0.58, 0.50), (0.30, 0.065, 0.045), (0.38, 0.39, 0.40)]; roofs = [(0.13, 0.065, 0.05), (0.27, 0.28, 0.30), (0.48, 0.49, 0.50)]
    for (bx, by, yaw, ln, wd, hw, hr, kd) in Bd:
        c, s_ = np.cos(yaw), np.sin(yaw); R = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]]); o = np.array([bx, by, 0]); x, y = ln / 2, wd / 2
        p = lambda px, py, pz: R @ np.array([px, py, pz]) + o
        c00, c10, c11, c01 = (-x, -y), (x, -y), (x, y), (-x, y); kd = int(kd); wc = walls[kd]; rcol = roofs[kd]
        for (a_, b_) in ((c00, c10), (c10, c11), (c11, c01), (c01, c00)):
            VV.append([p(*a_, 0), p(*b_, 0), p(*b_, hw), p(*a_, hw)]); CC.append([wc] * 4)
        VV.append([p(-x - 0.4, -y - 0.4, hw), p(x + 0.4, -y - 0.4, hw), p(x + 0.4, 0, hw + hr), p(-x - 0.4, 0, hw + hr)]); CC.append([rcol] * 4)
        VV.append([p(-x - 0.4, y + 0.4, hw), p(x + 0.4, y + 0.4, hw), p(x + 0.4, 0, hw + hr), p(-x - 0.4, 0, hw + hr)]); CC.append([rcol] * 4)
        for sx in (-x, x):
            VV.append([p(sx, -y, hw), p(sx, y, hw), p(sx, 0, hw + hr), p(sx, 0, hw + hr)]); CC.append([wc] * 4)
    Vb = np.array(VV).reshape(-1, 3); mesh_from("buildings", Vb, np.arange(len(Vb)).reshape(-1, 4), np.array(CC).reshape(-1, 3), sc, mat, smooth=False)
    # grass / stubble where the aircraft comes down: single-triangle blades, dense near the impact point, thinning out with distance
    ng = int(A.grass)
    if ng > 0:
        p = rng.uniform([-70, -55], [130, 55], (ng * 14, 2)); d = np.hypot((p[:, 0] - 14) / 110, p[:, 1] / 55)
        k = rng.uniform(0, 1, len(p)) < np.clip(0.02 / (d * d + 0.02), 0, 1) * np.clip(1 - d, 0, 1) ** 0.7; p = p[k][:ng]; d = d[k][:ng]; m = len(p)
        far = np.clip(d / 0.25, 0, 1)                                    # far from the impact point: fewer, bigger tufts
        hh = rng.uniform(0.10, 0.36, m) * (1 + 0.6 * far); an = rng.uniform(0, np.pi, m); w = rng.uniform(0.006, 0.013, m) * (1 + 4 * far)
        lean = rng.normal(0, 0.28, (m, 2)) * hh[:, None] + np.array([0.10, 0.03]) * hh[:, None]; e = np.stack([np.cos(an), np.sin(an)], 1) * w[:, None]
        G3 = np.zeros((m, 3, 3)); G3[:, 0, :2] = p - e; G3[:, 1, :2] = p + e; G3[:, 2, :2] = p + lean; G3[:, 2, 2] = hh
        straw = np.array([0.50, 0.40, 0.17]) * rng.uniform(0.55, 1.25, (m, 1)); gr = rng.uniform(0, 1, (m, 1)) < 0.18; straw = np.where(gr, np.array([0.10, 0.16, 0.04]) * rng.uniform(0.7, 1.2, (m, 1)), straw)
        cg = straw[:, None, :] * np.array([0.50, 0.50, 1.15])[None, :, None]
        cg = cg * A.grass_gain                                           # 1 except in the calibration runs for FIELD_TINT
        gm = mat_vcol("grass", 0.7, use_haze=False, leaf=40.0, trans=0.35, bump=0.0); gob = mesh_from("grass", G3.reshape(-1, 3), np.arange(m * 3).reshape(-1, 3), cg.reshape(-1, 3), sc, gm, smooth=False)
        global GRASS; GRASS = dict(ob=gob, G3=G3, cg=cg, mat=gm, gone=np.zeros(m, bool), tlast=0.0, u=np.random.default_rng(5).uniform(0, 1, m), keep=np.ones(m, bool))
    log("world: trees", K, "with leaves", len(near), "hedges", len(Hd), "buildings", len(Bd), "grass blades", ng)


def make_points(name, sc, material):
    """an object whose mesh vertices render as spheres (radius from the 'rad' attribute)"""
    me = bpy.data.meshes.new(name); ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry'); ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nin = ng.nodes.new("NodeGroupInput"); nout = ng.nodes.new("NodeGroupOutput"); m2p = ng.nodes.new("GeometryNodeMeshToPoints"); na = ng.nodes.new("GeometryNodeInputNamedAttribute")
    na.data_type = 'FLOAT'; na.inputs["Name"].default_value = "rad"; sm = ng.nodes.new("GeometryNodeSetMaterial"); sm.inputs["Material"].default_value = material
    ng.links.new(nin.outputs[0], m2p.inputs["Mesh"]); ng.links.new(na.outputs[0], m2p.inputs["Radius"]); ng.links.new(m2p.outputs["Points"], sm.inputs["Geometry"]); ng.links.new(sm.outputs["Geometry"], nout.inputs[0])
    md = ob.modifiers.new("pts", 'NODES'); md.node_group = ng; return ob


def set_points(ob, pos, rgb, emit, rad):
    n = len(pos); me = bpy.data.meshes.new("pts"); me.vertices.add(n)
    if n:
        me.vertices.foreach_set("co", np.ascontiguousarray(pos, np.float32).ravel())
        a = me.attributes.new("col", 'FLOAT_COLOR', 'POINT'); c = np.ones((n, 4), np.float32); c[:, :3] = rgb; a.data.foreach_set("color", c.ravel())
        a = me.attributes.new("emit", 'FLOAT', 'POINT'); a.data.foreach_set("value", np.ascontiguousarray(emit, np.float32))
        a = me.attributes.new("rad", 'FLOAT', 'POINT'); a.data.foreach_set("value", np.ascontiguousarray(rad, np.float32))
    old = ob.data; ob.data = me; bpy.data.meshes.remove(old)


def make_instancer(name, sc, shape):
    """an object whose mesh vertices each carry a copy of the object 'shape', turned by the 'rot' attribute and scaled by 'scl'"""
    me = bpy.data.meshes.new(name); ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry'); ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nin = ng.nodes.new("NodeGroupInput"); nout = ng.nodes.new("NodeGroupOutput"); m2p = ng.nodes.new("GeometryNodeMeshToPoints"); oi = ng.nodes.new("GeometryNodeObjectInfo"); oi.inputs[0].default_value = shape
    iop = ng.nodes.new("GeometryNodeInstanceOnPoints"); ar = ng.nodes.new("GeometryNodeInputNamedAttribute"); ar.data_type = 'FLOAT_VECTOR'; ar.inputs["Name"].default_value = "rot"
    asc = ng.nodes.new("GeometryNodeInputNamedAttribute"); asc.data_type = 'FLOAT_VECTOR'; asc.inputs["Name"].default_value = "scl"; e2r = ng.nodes.new("FunctionNodeEulerToRotation")
    ng.links.new(nin.outputs[0], m2p.inputs["Mesh"]); ng.links.new(m2p.outputs["Points"], iop.inputs["Points"]); ng.links.new(oi.outputs["Geometry"], iop.inputs["Instance"])
    ng.links.new(ar.outputs[0], e2r.inputs[0]); ng.links.new(e2r.outputs[0], iop.inputs["Rotation"]); ng.links.new(asc.outputs[0], iop.inputs["Scale"]); ng.links.new(iop.outputs["Instances"], nout.inputs[0])
    md = ob.modifiers.new("inst", 'NODES'); md.node_group = ng; return ob


def set_instances(ob, pos, rgb, rot, scl):
    n = len(pos); me = bpy.data.meshes.new("inst"); me.vertices.add(n)
    if n:
        me.vertices.foreach_set("co", np.ascontiguousarray(pos, np.float32).ravel())
        a = me.attributes.new("col", 'FLOAT_COLOR', 'POINT'); c = np.ones((n, 4), np.float32); c[:, :3] = rgb; a.data.foreach_set("color", c.ravel())
        a = me.attributes.new("rot", 'FLOAT_VECTOR', 'POINT'); a.data.foreach_set("vector", np.ascontiguousarray(rot, np.float32).ravel())
        a = me.attributes.new("scl", 'FLOAT_VECTOR', 'POINT'); a.data.foreach_set("vector", np.ascontiguousarray(scl, np.float32).ravel())
    old = ob.data; ob.data = me; bpy.data.meshes.remove(old)


def mat_instance(name, rough=0.9):
    """colour from the 'col' attribute of the point that carries the instance"""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = N(nt, "ShaderNodeOutputMaterial"); p = N(nt, "ShaderNodeBsdfPrincipled"); p.inputs["Roughness"].default_value = rough
    ac = N(nt, "ShaderNodeAttribute"); ac.attribute_name = "col"; ac.attribute_type = 'INSTANCER'; nt.links.new(ac.outputs["Color"], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], o.inputs["Surface"]); return m


def shape_clod(sc, mat):
    """an angular lump of soil, radius about 1"""
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0); rng = np.random.default_rng(21)
    for v in bm.verts: v.co *= float(rng.uniform(0.62, 1.30))
    me = bpy.data.meshes.new("clod"); bm.to_mesh(me); bm.free(); me.materials.append(mat)
    ob = bpy.data.objects.new("clod", me); sc.collection.objects.link(ob); ob.location = (0, 0, -900.0); return ob


def shape_straw(sc, mat):
    """a bit of stalk: a thin bent strip one unit long"""
    x = np.linspace(-0.5, 0.5, 4); V = np.array([[xi, w, 0.06 * np.cos(xi * 3)] for xi in x for w in (-0.035, 0.035)]); Q = [(2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1) for i in range(3)]
    me = bpy.data.meshes.new("straw"); me.from_pydata(V.tolist(), [], Q); me.update(); me.materials.append(mat)
    ob = bpy.data.objects.new("straw", me); sc.collection.objects.link(ob); ob.location = (0, 0, -900.0); return ob


class Soil:
    """Soil thrown up where the airframe meets the ground. NOT part of the solver (self-written, tuned by eye): aircraft particles that
    reach the ground at the RIM of the contact patch kick soil out sideways and up, those at its leading edge squirt it forward
    (the jet of an oblique impact); nothing comes up through the middle, the fuselage is in the way.
    Three kinds: clods (angular lumps, ballistic), bits of straw (ballistic), and fine dust that the air slows down within milliseconds.
    Every source throws its grains along one ray with a spread of speeds, so the spray has streaks like a real ejecta curtain."""
    def __init__(self, X, meta, vel, per):
        T, n, _ = X.shape; tc = np.full(n, np.inf, np.float32); p0 = np.zeros((n, 2), np.float32); stp = max(1, int(round(meta["fps"] / 5000.0)))
        for f in range(0, T, stp):
            z = np.asarray(X[f, :, 2]); new = (z < 0.03) & ~np.isfinite(tc)
            if new.any(): tc[new] = meta["t0"] + f / meta["fps"]; p0[new] = np.asarray(X[f, :, :2])[new]
        hit = np.flatnonzero(np.isfinite(tc)); rng = np.random.default_rng(9); kind = np.zeros(len(hit), np.int8); side = np.zeros(len(hit), np.float32)
        tb = np.floor((tc[hit] - tc[hit].min()) / 1e-3).astype(int) if len(hit) else np.zeros(0, int)
        for b in np.unique(tb):
            m = np.flatnonzero(tb == b); y = p0[hit[m], 1]; x = p0[hit[m], 0]; cy = np.median(y); hw = np.percentile(np.abs(y - cy), 90) + 0.02
            rim = np.abs(y - cy) > 0.72 * hw; bow = x > np.percentile(x, 88); kind[m] = np.where(bow, 2, np.where(rim, 1, 0)); side[m] = np.sign(y - cy)
        sel = np.flatnonzero(kind > 0); ns = len(sel); u = rng.uniform(0, 1, ns)                    # one ray per source
        v_rim = np.stack([vel[0] * rng.uniform(0.25, 0.95, ns), side[sel] * rng.uniform(15, 70, ns), u ** 2.2 * 40.0 + 2.0], 1)
        v_bow = np.stack([vel[0] * rng.uniform(1.05, 1.70, ns), rng.normal(0, 12, ns), u ** 1.4 * 130.0 + 2.0], 1)
        vs = np.where((kind[sel] == 2)[:, None], v_bow, v_rim); ts = tc[hit[sel]]; ps = p0[hit[sel]]
        def spawn(k, jit, lo, hi, turb):
            rep = np.repeat(np.arange(ns), k) if k >= 1 else np.flatnonzero(rng.uniform(size=ns) < k); m = len(rep)
            return (ts[rep] + rng.uniform(0, 5e-4, m), np.c_[ps[rep] + rng.normal(0, jit, (m, 2)), np.zeros(m)], vs[rep] * rng.uniform(lo, hi, (m, 1)) + rng.normal(0, turb, (m, 3)), m)
        k = max(1, int(per))
        # clods: mostly crumbs of a few millimetres, now and then a lump of a centimetre or two
        self.ct, self.cp, self.cv, m = spawn(k, 0.02, 0.55, 1.05, 1.5)
        r = np.clip(rng.lognormal(np.log(0.0018), 0.75, m), 0.0006, 0.018); self.cs = (r[:, None] * rng.uniform(0.55, 1.35, (m, 3))).astype(np.float32)
        self.cr = rng.uniform(0, 6.283, (m, 3)).astype(np.float32); self.cw = rng.normal(0, 400.0, (m, 3)).astype(np.float32)        # tumbling, rad/s
        self.cc = (np.array([0.10, 0.068, 0.040]) * rng.uniform(0.5, 1.4, (m, 1)) * rng.uniform(0.9, 1.1, (m, 3))).astype(np.float32)
        # straw
        self.st, self.sp, self.sv, m2 = spawn(k / 10.0, 0.03, 0.45, 1.0, 3.0)
        self.ss = (rng.uniform(0.02, 0.09, (m2, 1)) * np.array([1.0, 1.0, 1.0])).astype(np.float32); self.sr = rng.uniform(0, 6.283, (m2, 3)).astype(np.float32); self.sw = rng.normal(0, 250.0, (m2, 3)).astype(np.float32)
        self.scol = (np.array([0.40, 0.31, 0.13]) * rng.uniform(0.6, 1.25, (m2, 1))).astype(np.float32)
        # dust: each grain is stopped by the air with its own time constant (finer = sooner)
        self.dt_, self.dp, self.dv, m3 = spawn(k * 5, 0.03, 0.30, 1.10, 2.5)
        self.dtau = rng.uniform(0.004, 0.022, m3); self.drad = np.clip(rng.lognormal(np.log(0.00028), 0.5, m3), 0.0001, 0.0009).astype(np.float32)
        self.dcol = (np.array([0.27, 0.20, 0.125]) * rng.uniform(0.6, 1.3, (m3, 1))).astype(np.float32)
        log("soil: sources", ns, "of", len(hit), "ground hits; clods", m, "straw", m2, "dust", m3)

    def clods(self, t):
        a = np.flatnonzero(self.ct <= t); dt = (t - self.ct[a])[:, None]; p = self.cp[a] + self.cv[a] * dt; p[:, 2] -= 4.9 * dt[:, 0] ** 2; p[:, 2] = np.maximum(p[:, 2], 0.0)
        return p, self.cc[a], self.cr[a] + self.cw[a] * dt, self.cs[a]

    def straw(self, t):
        a = np.flatnonzero(self.st <= t); dt = (t - self.st[a])[:, None]; p = self.sp[a] + self.sv[a] * dt; p[:, 2] = np.maximum(p[:, 2] - 4.9 * dt[:, 0] ** 2, 0.0)
        return p, self.scol[a], self.sr[a] + self.sw[a] * dt, self.ss[a]

    def dust(self, t):
        a = np.flatnonzero(self.dt_ <= t); dt = t - self.dt_[a]; tau = self.dtau[a]; p = self.dp[a] + self.dv[a] * (tau * (1 - np.exp(-dt / tau)))[:, None]
        return p, self.dcol[a], np.zeros(len(a), np.float32), self.drad[a]


def rodrigues(axis, th):
    """rotation matrices (K,3,3) about unit axes (K,3) by angles (K,)"""
    K = len(th); x, y, z = axis[:, 0], axis[:, 1], axis[:, 2]; Z = np.zeros(K)
    Kx = np.stack([np.stack([Z, -z, y], 1), np.stack([z, Z, -x], 1), np.stack([-y, x, Z], 1)], 1)
    return np.eye(3)[None] + np.sin(th)[:, None, None] * Kx + (1 - np.cos(th))[:, None, None] * (Kx @ Kx)


class Pieces:
    """Hard things break as pieces. Every vertex belongs to a piece (fp_geo.py). The simulation moves the material points; each piece is then
    laid over its points as a RIGID body (best-fit rotation + translation), so a display stays a flat box and a skin facet a flat plate.
    Between pieces: ductile sheet (skin, floor, ...) keeps a 1 cm strip that folds and finally tears; brittle parts (acrylic, radome,
    the instrument panel) have a hairline joint that opens as a crack. Every piece has thickness, so a torn edge shows metal.
    Where the solver compressed a sheet in its plane the facets are tilted so the sheet keeps its length (it cannot shrink, it has to fold):
    that fold pattern below the solver's 2 cm cell is a geometric reconstruction, not solved."""
    BRITTLE = ("radome", "glass"); SHEET = ("skin", "floor", "bulkhead", "glareshield", "pedestal", "avionics", "frame")
    GAP = dict(radome=0.002, glass=0.004)

    def __init__(self, G, Wd, R0, T0, pn):
        V0 = G["verts"].astype(np.float64); Q = G["quads"].astype(np.int64); N = len(V0); F = len(Q); self.N = N; self.Q = Q
        piece = G["piece"].astype(np.int64); K = int(piece.max()) + 1; self.piece = piece; self.K = K; vpart = G["vpart"]; thick = G["thick"].astype(np.float64); uv = G["uv"].astype(np.float64)
        mixed = (vpart[Q] != vpart[Q][:, :1]).any(1); ta = np.abs(thick); tm = ta.copy(); np.minimum.at(tm, Q[mixed].ravel(), np.repeat(ta[Q[mixed]].min(1), 4)); thick = np.sign(thick) * tm
        self.fnose = (float(G["X0"]) - V0[Q[:, 0], 0]) < 1.52          # ahead of the cockpit's front bulkhead the skin is bare primer inside, behind it there is lining
        fn = np.cross(V0[Q[:, 1]] - V0[Q[:, 0]], V0[Q[:, 3]] - V0[Q[:, 0]]); vn = np.zeros((N, 3))
        for k in range(4): np.add.at(vn, Q[:, k], fn)
        vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
        pq = piece[Q]; bridge = (pq != pq[:, :1]).any(1); self.bridge = bridge; bi = np.flatnonzero(bridge); self.bi = bi; bq = Q[bi]; self.bq = bq
        brit_v = np.isin(vpart, [pn.index(k) for k in self.BRITTLE]); self.bbrit = brit_v[bq].all(1)
        # joints are hairlines: both sides of the 1 cm strip between two pieces are pulled together. Between two cells of the same Voronoi
        # tiling they go onto the plane halfway between the two seeds (the true cell wall: a straight line instead of a staircase of grid
        # squares); elsewhere (riveted joints, instrument cut-outs: already straight along the grid) onto the middle of the strip.
        seed = G["pseed"].astype(np.float64); pvor = G["pvor"]; Vr = V0.copy(); IA = []; IB = []
        for a in range(4):
            for b in range(4):
                if a == b: continue
                m = piece[bq[:, a]] != piece[bq[:, b]]; IA.append(bq[m, a]); IB.append(bq[m, b])
        IA = np.concatenate(IA); IB = np.concatenate(IB); PB = piece[IB]
        dn = np.linalg.norm(V0[IA] - V0[IB], axis=1); o = np.argsort(-dn, kind="stable"); opp = np.full(N, -1, np.int64); opp[IA[o]] = IB[o]       # the vertex straight across the strip
        m = np.flatnonzero(opp >= 0); Vr[m] = 0.52 * V0[m] + 0.48 * V0[opp[m]]
        dd = np.linalg.norm(V0[IA] - seed[PB], axis=1); dd[(pvor[piece[IA]] < 0) | (pvor[piece[IA]] != pvor[PB])] = np.inf
        o = np.argsort(-dd, kind="stable"); bp = np.full(N, -1, np.int64); bd = np.full(N, np.inf); bp[IA[o]] = PB[o]; bd[IA[o]] = dd[o]      # the nearest neighbouring cell wins
        v = np.flatnonzero(np.isfinite(bd)); sa = seed[piece[v]]; sb = seed[bp[v]]; nn = sb - sa; nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
        # slide along the surface (not through it) until the vertex is on that plane; where the wall cuts the surface too obliquely keep the mid-strip position
        td = nn - (nn * vn[v]).sum(1, keepdims=True) * vn[v]; den = (td * nn).sum(1); stp = 0.96 * (((sa + sb) / 2 - V0[v]) * nn).sum(1) / np.maximum(den, 1e-6)
        okp = (den > 0.3) & (np.abs(stp) * np.linalg.norm(td, axis=1) < 1.3 * float(G["h"])); v = v[okp]; Vr[v] = V0[v] + stp[okp, None] * td[okp]
        uvr = uv.copy(); pv = np.flatnonzero(vpart == pn.index("panel"))                       # the panel texture follows its vertices (uv is affine in position there)
        if len(pv): M_, *_ = np.linalg.lstsq(np.c_[V0[pv], np.ones(len(pv))], uv[pv], rcond=None); uvr[pv] = np.c_[Vr[pv], np.ones(len(pv))] @ M_
        self.uv = uvr.astype(np.float32); self.rest = Vr.astype(np.float32)
        Wr = Vr @ R0.T + T0; Wb = (Vr + vn * thick[:, None]) @ R0.T + T0
        cnt = np.bincount(piece, minlength=K).astype(np.float64); self.cnt = cnt
        c0 = np.stack([np.bincount(piece, Wd[:, j], K) for j in range(3)], 1) / cnt[:, None]; self.c0 = c0
        self.q0 = Wd - c0[piece]; self.qr = Wr - c0[piece]; self.qb = Wb - c0[piece]
        ev, evec = np.linalg.eigh(self.outer(self.q0, self.q0)); self.T = evec[:, :, 1:3]; self.ev = ev[:, 1:3]
        ppart = np.zeros(K, np.int64); ppart[piece] = vpart; pth = np.zeros(K); pth[piece] = thick; self.ppart = ppart
        self.sheet = (ev[:, 0] < 0.03 * ev[:, 1]) & (ev[:, 1] > 0.04 * ev[:, 2]) & (cnt >= 10) & np.isin(ppart, [pn.index(k) for k in self.SHEET]) & (pth != 0)
        # folding: facets in the same band across the direction of compression tilt the same way, the next band the other way (an accordion).
        # The band a facet is in follows from where its centre lies along that direction; the choice is made once, when the facet starts to fold.
        pnm = np.stack([np.bincount(piece, (vn @ R0.T)[:, j], K) for j in range(3)], 1); self.pnm = pnm / np.maximum(np.linalg.norm(pnm, axis=1, keepdims=True), 1e-12)
        psz = np.sqrt(cnt) * float(G["h"]); self.pitch = np.ones(K) * 0.09
        for ip in np.unique(ppart): self.pitch[ppart == ip] = max(0.04, float(np.median(psz[ppart == ip])))
        self.fsgn = np.zeros(K)
        # curl: a facet of sheet metal whose material has failed does not stay a flat tile, it ends up bent. Each folding facet gets a fixed bend
        # axis and sense; how far it curls follows the share of its material points that have failed (set in advance()). An isometric bend
        # (cylinder), so the sheet keeps its size. NOT solved: added so that torn skin reads as metal rather than as broken tiles.
        rc_ = np.random.default_rng(17); ph_ = rc_.uniform(0, np.pi, K); self.bdir = np.einsum('kij,kj->ki', self.T, np.stack([np.cos(ph_), np.sin(ph_)], 1))
        self.kmax = rc_.uniform(0.3, 1.0, K) * rc_.choice([-1.0, 1.0], K) * self.sheet / A.curl_radius if A.curl_radius > 0 else np.zeros(K); self.kap = np.zeros(K)
        # joints
        E = lambda X: np.linalg.norm(X[bq] - X[np.roll(bq, -1, 1)], axis=2)
        self.E = E; self.L0 = E(Wr); gap = np.zeros(len(pn)); 
        for k, v in self.GAP.items(): gap[pn.index(k)] = v
        pvq = pvor[piece[bq]]; self.bsame = (pvq >= 0).all(1) & (pvq == pvq[:, :1]).all(1)             # joint between two facets of one tiling (not a riveted joint)
        self.bgap = gap[vpart[bq[:, 0]]]; self.torn = np.zeros(len(bi), bool); self.dead = np.zeros(K, bool); self.tlast = 0.0
        bpos = np.full(F, -1, np.int64); bpos[bi] = np.arange(len(bi)); self.nbr = np.bincount(np.concatenate([pq[bi][:, k] for k in range(4)]), minlength=K).astype(np.float64)
        self.bpq = pq[bi]
        # thickness: a back face behind every face, and a rim along every piece outline, shown once the joint beside it has torn
        self.hasth = (thick[Q] != 0).all(1)
        ev_ = np.stack([Q, np.roll(Q, -1, 1)], -1).reshape(-1, 2); ef = np.repeat(np.arange(F), 4); key = ev_.min(1) * N + ev_.max(1)
        o = np.argsort(key, kind="stable"); ks = key[o]; fs = ef[o]; st = np.flatnonzero(np.r_[True, ks[1:] != ks[:-1]]); ct = np.diff(np.r_[st, len(ks)])
        fa = fs[st]; fb = np.where(ct >= 2, fs[np.minimum(st + 1, len(fs) - 1)], -1); e2 = ev_[o][st]
        ia = ~bridge[fa]; ib = np.where(fb >= 0, ~bridge[np.maximum(fb, 0)], False)
        rim = (piece[e2[:, 0]] == piece[e2[:, 1]]) & (ia ^ ib) & (thick[e2[:, 0]] != 0) & (thick[e2[:, 1]] != 0)
        other = np.where(ia, fb, fa)[rim]; mine = np.where(ia, fa, fb)[rim]; e2 = e2[rim]
        # rims have their own vertices (so that they can carry their own normals): front copies at 2N.., back copies after them
        rv = np.unique(e2); nr = len(rv); rpos = np.full(N, -1, np.int64); rpos[rv] = np.arange(nr); self.rv = rv; self.nr = nr
        ne = np.cross(Wr[e2[:, 1]] - Wr[e2[:, 0]], Wb[e2[:, 0]] - Wr[e2[:, 0]]); ne /= np.maximum(np.linalg.norm(ne, axis=1, keepdims=True), 1e-12)
        flip = (ne * ((Wr[e2[:, 0]] + Wr[e2[:, 1]]) / 2 - c0[piece[e2[:, 0]]])).sum(1) < 0; ne[flip] *= -1; e2[flip] = e2[flip][:, ::-1]      # outward, and wound to match
        rn = np.zeros((nr, 3)); np.add.at(rn, rpos[e2[:, 0]], ne); np.add.at(rn, rpos[e2[:, 1]], ne); self.rn = rn / np.maximum(np.linalg.norm(rn, axis=1, keepdims=True), 1e-12)
        a_ = 2 * N + rpos[e2[:, 0]]; b_ = 2 * N + rpos[e2[:, 1]]; self.rimq = np.stack([a_, b_, b_ + nr, a_ + nr], 1)
        self.rimb = np.where(other >= 0, bpos[np.maximum(other, 0)], -1); self.rimf = mine
        self.vnw = vn @ R0.T; self.base = np.concatenate([np.arange(N), np.arange(N), rv, rv]); self.NV = 2 * N + 2 * nr
        self.screen = np.zeros(K, bool)                              # pieces that are lit displays (deep panel pieces)
        self.screen[np.unique(piece[(vpart == pn.index("panel")) & (thick < -0.05)])] = True
        log("pieces", K, "joint faces", len(bi), "of", F, "hairline", int(self.bbrit.sum()), "rim edges", len(e2), "folding sheet pieces", int(self.sheet.sum()))

    def outer(self, a, b):
        M = np.zeros((self.K, 3, 3))
        for i in range(3):
            for j in range(3): M[:, i, j] = np.bincount(self.piece, a[:, i] * b[:, j], self.K)
        return M

    def pose(self, P):
        """front and back vertex positions for simulated positions P"""
        K = self.K; pc = self.piece; c = np.stack([np.bincount(pc, P[:, j], K) for j in range(3)], 1) / self.cnt[:, None]
        A_ = self.outer(P - c[pc], self.q0)
        # a piece that is nearly a line (a strip two vertices wide) has no defined roll about its own axis: a small pull toward "not turned" settles it
        U, S, Vt = np.linalg.svd(A_ + (0.02 * self.ev[:, 1])[:, None, None] * np.eye(3)[None]); d = np.sign(np.linalg.det(U @ Vt)); U[:, :, 2] *= d[:, None]; R = U @ Vt; R[self.cnt < 4] = np.eye(3)
        self.Pk = c[pc] + np.einsum('nij,nj->ni', R[pc], self.qr)          # plain rigid fit, before any folding or curling: what the joints are judged on
        if A.fold > 0:
            F2 = (A_ @ self.T) / np.maximum(self.ev[:, None, :], 1e-12); _, s2, v2 = np.linalg.svd(F2, full_matrices=False)
            th = np.arccos(np.clip(s2[:, 1] + A.fold_dead, np.cos(np.radians(A.fold_max)), 1.0)) * A.fold * self.sheet
            d1 = np.einsum('kij,kj->ki', self.T, v2[:, 1, :]); d1 *= np.where(d1 @ np.array([1.0, 0.31, 0.17]) < 0, -1.0, 1.0)[:, None]      # direction of compression (rest frame), one sense for all
            new = (th > 0) & (self.fsgn == 0); self.fsgn[new] = np.where(np.floor((self.c0[new] * d1[new]).sum(1) / self.pitch[new]) % 2 == 0, 1.0, -1.0)
            ax = np.cross(self.pnm, d1); ax /= np.maximum(np.linalg.norm(ax, axis=1, keepdims=True), 1e-12); R = R @ rodrigues(ax, th * self.fsgn)
        Rv = R[pc]; self.cur = self.bend(); qr, qb = self.cur[0], self.cur[1]
        return c[pc] + np.einsum('nij,nj->ni', Rv, qr), c[pc] + np.einsum('nij,nj->ni', Rv, qb), R

    def bend(self):
        """rest-frame offsets of the front and back vertices and the rest normals, with each piece curled by its present curvature"""
        act = np.flatnonzero(np.abs(self.kap[self.piece]) > 1e-4)
        if not len(act): return self.qr, self.qb, self.vnw, self.rn
        pc = self.piece[act]; k = self.kap[pc]; bd = self.bdir[pc]; nm = self.pnm[pc]; out = []
        for q in (self.qr, self.qb):
            q = q.copy(); qa = q[act]; u = (qa * bd).sum(1); w = (qa * nm).sum(1); ph = k * u; rho = 1.0 / k - w
            q[act] = qa + (rho * np.sin(ph) - u)[:, None] * bd + (1.0 / k - rho * np.cos(ph) - w)[:, None] * nm; out.append(q)
        def turn(n, idx, pcs):
            n = n.copy(); na = n[idx]; bd_ = self.bdir[pcs]; nm_ = self.pnm[pcs]; nu = (na * bd_).sum(1); nw = (na * nm_).sum(1)
            ph = self.kap[pcs] * (self.qr[self.rv[idx]] * bd_).sum(1) if n is not None and len(n) == self.nr else self.kap[pcs] * (self.qr[idx] * bd_).sum(1)
            n[idx] = na + ((nu * np.cos(ph) - nw * np.sin(ph)) - nu)[:, None] * bd_ + ((nu * np.sin(ph) + nw * np.cos(ph)) - nw)[:, None] * nm_; return n
        ra = np.flatnonzero(np.abs(self.kap[self.piece[self.rv]]) > 1e-4)
        return out[0], out[1], turn(self.vnw, act, pc), turn(self.rn, ra, self.piece[self.rv[ra]])

    def verts(self, Pf, Pb, R):
        """all vertices (front, back, rim copies) and their normals: every piece carries the smooth normals it had at rest, turned with it"""
        nf = np.einsum('nij,nj->ni', R[self.piece], self.cur[2]); nrm = np.einsum('nij,nj->ni', R[self.piece[self.rv]], self.cur[3])
        return np.concatenate([Pf, Pb, Pf[self.rv], Pb[self.rv]]), np.concatenate([nf, -nf, nrm, nrm])

    def advance(self, X, meta, tfail, t):
        """joints tear and screens die for good: step through the simulation up to time t and remember what has broken"""
        times = list(np.arange(self.tlast + A.step * 1e-3, t - 1e-9, A.step * 1e-3)) + [t]; out = None
        for tk in times:
            f = (tk - meta["t0"]) * meta["fps"]
            if f <= 0: continue
            f = min(f, len(X) - 1.001); i = int(f); a = f - i; P = np.asarray(X[i], np.float64) * (1 - a) + np.asarray(X[i + 1], np.float64) * a
            failed = tfail <= f; ff = np.bincount(self.piece, failed, self.K) / self.cnt; self.kap = self.kmax * np.clip((ff - 0.15) / 0.6, 0.0, 1.0)
            Pf, Pb, R = self.pose(P); g = (self.E(self.Pk) - self.L0).max(1)   # how far the joint has opened (m), from the solved motion alone
            # acrylic and the radome crack as soon as a joint opens a few millimetres. Metal is ductile: between two facets of the same skin panel
            # it stays in one piece (the joint just bends) until they are really pulled apart; along riveted joints and cut-outs it lets go early.
            fj = failed[self.bq].any(1)
            self.torn |= np.where(self.bbrit, g > self.bgap, np.where(self.bsame, (g > A.tear) | (fj & (g > A.tear_failed)), (g > A.rivet) | (fj & (g > A.rivet_failed))))
            tf = np.bincount(self.bpq.ravel(), np.repeat(self.torn, 4), self.K) / np.maximum(self.nbr, 1)
            self.dead |= self.screen & ((ff > 0.10) | (tf > 0.5)); out = (P, Pf, Pb, R, failed)
        self.tlast = t; return out

    def faces(self, fmat, backm, rimm, skin_i, primer_i):
        """quads and material slots of everything that is still there"""
        keep = np.ones(len(self.Q), bool); keep[self.bi] = ~self.torn; q = self.Q[keep]; fm = fmat[keep]; kb = keep & self.hasth
        rs = (self.rimb < 0) | self.torn[np.maximum(self.rimb, 0)]
        bm = np.where((fmat[kb] == skin_i) & self.fnose[kb], primer_i, backm[fmat[kb]])
        return (np.concatenate([q, self.Q[kb][:, ::-1] + self.N, self.rimq[rs]]), np.concatenate([fm, bm, rimm[fmat[self.rimf[rs]]]]), int(keep.sum()))


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene; sc.render.engine = 'CYCLES'
    if A.device != "CPU":
        try:
            pr = bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type = A.device; pr.refresh_devices()
            for d in pr.devices: d.use = (d.type != 'CPU')
            sc.cycles.device = 'GPU'
        except Exception as e: log("GPU setup failed", e)
    if A.threads: sc.render.threads_mode = 'FIXED'; sc.render.threads = A.threads
    cy = sc.cycles; cy.samples = A.samples; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.03; cy.use_denoising = True
    try: cy.denoiser = 'OPTIX' if A.denoiser == "OPTIX" else 'OPENIMAGEDENOISE'      # OIDN by default also on the GPU: the stills that were approved used it
    except Exception as e: log("denoiser", e)
    cy.max_bounces = 6; cy.diffuse_bounces = 3; cy.glossy_bounces = 3; cy.transmission_bounces = 2; cy.transparent_max_bounces = 12
    cy.caustics_reflective = False; cy.caustics_refractive = False; cy.sample_clamp_indirect = 8.0
    sc.render.resolution_x = W; sc.render.resolution_y = H; sc.render.resolution_percentage = 100
    if A.persistent: sc.render.use_persistent_data = True          # film: keep the static world (trees, buildings) in the renderer between frames
    if A.crop:                                                    # x0,x1,y0,y1 as fractions of the frame (y from the bottom): render only that window, for a close look
        cx0, cx1, cy0, cy1 = [float(v) for v in A.crop.split(",")]; sc.render.use_border = True; sc.render.use_crop_to_border = True
        sc.render.border_min_x = cx0; sc.render.border_max_x = cx1; sc.render.border_min_y = cy0; sc.render.border_max_y = cy1
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    try:
        sc.view_settings.view_transform = A.view
        if A.view == 'AgX': sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception as e:
        log("view", e)
        try: sc.view_settings.look = 'Medium High Contrast'
        except Exception as e2: log("look", e2)
    sc.view_settings.exposure = A.exposure
    # sky: low sun ahead and to the left
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
    o = N(nt, "ShaderNodeOutputWorld"); bg = N(nt, "ShaderNodeBackground"); sky = N(nt, "ShaderNodeTexSky")
    for st in ('MULTIPLE_SCATTERING', 'NISHITA', 'HOSEK_WILKIE'):
        try: sky.sky_type = st; break
        except Exception: pass
    log("sky", sky.sky_type)
    try:
        sky.sun_elevation = np.radians(A.sun_el); sky.sun_rotation = np.radians(90.0 - A.sun_az - 4.0)   # sun_rotation 0 = +Y in Blender; we want az degrees left of +x
        sky.sun_disc = True; sky.sun_size = np.radians(0.55); sky.sun_intensity = 1.0
    except Exception as e: log("sky params", e)
    for k, v in (("air_density", 1.0), ("aerosol_density", 2.2), ("dust_density", 2.2), ("ozone_density", 1.0)):
        try: setattr(sky, k, v)
        except Exception: pass
    bg.inputs[1].default_value = float(SKY); nt.links.new(sky.outputs[0], bg.inputs[0]); nt.links.new(bg.outputs[0], o.inputs[0])
    # ground
    me = bpy.data.meshes.new("ground"); s = 30000.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)]); me.update()
    go = bpy.data.objects.new("ground", me); sc.collection.objects.link(go)
    wdir = A.world or os.path.dirname(os.path.abspath(A.geo)); ext = [float(v) for v in np.load(os.path.join(wdir, "world.npz"))["extent"]]
    me.materials.append(mat_ground("ground", wdir, ext)); build_world(wdir, sc)
    cd = bpy.data.cameras.new("cam"); co = bpy.data.objects.new("cam", cd); sc.collection.objects.link(co); sc.camera = co
    cd.sensor_width = 36; cd.lens = A.lens; cd.clip_start = 0.02; cd.clip_end = 60000
    if A.fstop > 0: cd.dof.use_dof = True; cd.dof.aperture_fstop = A.fstop; cd.dof.focus_distance = 6.0
    ld = bpy.data.lights.new("fill", 'POINT'); ld.energy = A.fill; ld.color = (1.0, 0.93, 0.85); ld.shadow_soft_size = 0.25; lo = bpy.data.objects.new("fill", ld); sc.collection.objects.link(lo)
    return sc, co, lo


SKY = 0.25; HAZE = 0.9; FIELD_TINT = (0.585, 0.494, 0.0885)         # fitted by eye and by the radial colour profile around the impact point (stills at T-1 s, T-0.6 s; --grass_gain is the knob for that): the match depends on the viewing angle, this is the compromise for the 100 to 40 m range in which the blades fade in
LOD = tuple(float(v) for v in A.grass_lod.split(","))


def main():
    t0 = time.time(); G = np.load(A.geo); V0 = G["verts"].astype(np.float64); Q = G["quads"]; fmat = G["fmat"]; uv = G["uv"]; mats = [str(x) for x in G["mat_names"]]
    Wd, R0, T0, vel = fp_pose.place(V0)
    eye_m = np.array([float(x) for x in A.eye.split(",")]) if A.eye else G["eye"].astype(np.float64)
    eye0 = R0 @ eye_m + T0
    sc, co, lo = setup(); pm = mat_points("pts"); dust = make_points("dust", sc, pm); ej = None
    mi = mat_instance("soil"); clods = make_instancer("clods", sc, shape_clod(sc, mi)); straw = make_instancer("straw", sc, shape_straw(sc, mat_instance("stalk", 0.7)))
    x0m = float(G["X0"])
    lib = dict(skin=mat_paint("skin", (0.82, 0.83, 0.85), 0.28, x0m), radome=mat_paint("radome", (0.80, 0.81, 0.83), 0.35, -100.0),
               glass=mat_glass("glass"), floor=mat_simple("floor", (0.035, 0.036, 0.042), 0.95), bulkhead=mat_simple("bulkhead", (0.30, 0.29, 0.27), 0.7),
               frame=mat_simple("frame", (0.30, 0.38, 0.10), 0.55, 0.2), panel=mat_panel("panel", A.tex, A.panel_gain), glareshield=mat_simple("glareshield", (0.020, 0.020, 0.022), 0.8),
               pedestal=mat_simple("pedestal", (0.035, 0.035, 0.038), 0.6), yoke=mat_simple("yoke", (0.015, 0.015, 0.016), 0.38), seat=mat_simple("seat", (0.20, 0.15, 0.10), 0.62),
               avionics=mat_simple("avionics", (0.03, 0.03, 0.035), 0.5, 0.3), gear=mat_simple("gear", (0.35, 0.35, 0.37), 0.35, 0.9),
               # the other side of a piece and its broken edge
               liner=mat_simple("liner", (0.30, 0.29, 0.27), 0.75), primer=mat_simple("primer", (0.30, 0.38, 0.10), 0.6, 0.1), bare=mat_simple("bare", (0.78, 0.78, 0.80), 0.32, 1.0),
               composite=mat_simple("composite", (0.42, 0.36, 0.24), 0.85), core=mat_simple("core", (0.55, 0.50, 0.38), 0.9), box=mat_simple("box", (0.10, 0.10, 0.11), 0.45, 0.6),
               foam=mat_simple("foam", (0.07, 0.065, 0.06), 0.95), glass_in=mat_edge("glass_in", (1, 1, 1), 0.0), glass_edge=mat_edge("glass_edge", (0.80, 0.93, 0.88), 0.55, 0.3))
    slots = mats + [k for k in lib if k not in mats]; si = {k: i for i, k in enumerate(slots)}
    back = dict(skin="liner", radome="composite", glass="glass_in", floor="bare", bulkhead="primer", frame="primer", panel="box", glareshield="foam", pedestal="box", yoke="yoke", seat="seat", avionics="box", gear="gear")
    rimn = dict(skin="bare", radome="core", glass="glass_edge", floor="core", bulkhead="bare", frame="bare", panel="box", glareshield="foam", pedestal="bare", yoke="yoke", seat="foam", avionics="bare", gear="gear")
    backm = np.array([si[back[k]] for k in mats]); rimm = np.array([si[rimn[k]] for k in mats])
    PC = Pieces(G, Wd, R0, T0, [str(x) for x in G["part_names"]])
    sim = None
    if A.sim:
        meta = json.load(open(os.path.join(A.sim, "meta.json"))); X = np.load(os.path.join(A.sim, "x.npy"), mmap_mode="r"); tfail = np.load(os.path.join(A.sim, "fail.npy"))
        sim = (meta, X, tfail); log("sim", X.shape, "fps", meta["fps"], "t0 ms", meta["t0"] * 1e3)
        if A.dust > 0: ej = Soil(X, meta, vel, A.dust)
    vpart = G["vpart"]; pn = [str(x) for x in G["part_names"]]; prgb = np.array([dict(radome=(0.75, 0.72, 0.62), skin=(0.80, 0.81, 0.83), glass=(0.75, 0.90, 0.95), floor=(0.05, 0.05, 0.06), bulkhead=(0.3, 0.29, 0.27),
        frame=(0.30, 0.38, 0.10), panel=(0.04, 0.04, 0.04), glareshield=(0.02, 0.02, 0.02), pedestal=(0.04, 0.04, 0.04), yoke=(0.02, 0.02, 0.02), seat=(0.2, 0.15, 0.1), avionics=(0.05, 0.05, 0.06), gear=(0.35, 0.35, 0.37))[k] for k in pn], np.float32)
    sk = vpart <= pn.index("glass"); ssk = float(G["X0"]) - V0[sk, 0]; bins = np.arange(0.0, ssk.max() + 0.05, 0.05); bi = np.digitize(ssk, bins)
    prof = np.array([[bins[b - 1] + 0.025, (V0[sk, 2][bi == b].max() + V0[sk, 2][bi == b].min()) / 2, (V0[sk, 2][bi == b].max() - V0[sk, 2][bi == b].min()) / 2] for b in np.unique(bi)])
    def outside(p, t, lag):
        """True for world points that are not inside the forward fuselage (carried at flight speed, shifted by how far the cockpit has lagged)"""
        q = (p - T0 - vel * t - lag) @ R0; sq = float(G["X0"]) - q[:, 0]
        r = np.interp(sq, prof[:, 0], prof[:, 2], left=0.0, right=prof[-1, 2]); zc = np.interp(sq, prof[:, 0], prof[:, 1])
        return (sq < -0.05) | (sq > prof[-1, 0] + 3.0) | (np.hypot(q[:, 1], q[:, 2] - zc) > r + 0.06)
    ob = None; uv2 = PC.uv[PC.base]; rest2 = np.ascontiguousarray(PC.rest[PC.base]); NV = PC.NV
    os.makedirs(A.out, exist_ok=True)
    # stills: --t=ms,ms,... (ascending). film: --tfile = json list of [frame number, ms] (ascending), files are named by frame number, frames already on disk are skipped
    # (what has torn so far is rebuilt from the simulation, so a run can be stopped and resumed); --stride a,b renders only frames with number % b == a, for several processes side by side
    if A.tfile:
        sa, sb = map(int, A.stride.split(",")); jobs = [(int(i), float(tm), os.path.join(A.out, f"{A.tag}_{int(i):05d}.png")) for i, tm in json.load(open(A.tfile)) if int(i) % sb == sa]
        jobs = [j for j in jobs if not os.path.exists(j[2])]
        if A.max_frames > 0: jobs = jobs[:A.max_frames]              # leave after this many frames: graphics memory creeps up over ~100 frames in one process; the launcher starts the next batch
    else: jobs = [(-1, float(x), os.path.join(A.out, f"{A.tag}_{'m' if float(x) < 0 else 'p'}{abs(float(x)):07.2f}.png")) for x in A.t.split(",")]
    for fno, tms, fpath in jobs:
        t = tms * 1e-3; P = Wd + vel * t; lag = np.zeros(3); Pf, Pb, Rk = PC.pose(P); dv = np.zeros(PC.N, bool)
        if sim is not None and t > 0:
            meta, X, tfail = sim; r = PC.advance(X, meta, tfail, t)
            if r is not None:
                P, Pf, Pb, Rk, failed = r
                cock = np.isin(vpart, [pn.index(k) for k in ("glass", "panel", "seat")]); lag = (P[cock] - (Wd[cock] + vel * t)).mean(0); dv = PC.dead[PC.piece]
        if ob is not None: bpy.data.objects.remove(ob, do_unlink=True)
        VV_, NN_ = PC.verts(Pf, Pb, Rk); pw = np.where(dv, 0.0, 1.0).astype(np.float32)[PC.base]
        q, qm, F = PC.faces(fmat, backm, rimm, si["skin"], si["primer"]); nf = len(q); me = bpy.data.meshes.new("air"); me.vertices.add(NV)
        me.vertices.foreach_set("co", np.ascontiguousarray(VV_, np.float32).ravel())
        me.loops.add(4 * nf); me.polygons.add(nf); me.loops.foreach_set("vertex_index", np.ascontiguousarray(q, np.int32).ravel())
        me.polygons.foreach_set("loop_start", np.arange(nf, dtype=np.int32) * 4); me.polygons.foreach_set("loop_total", np.full(nf, 4, np.int32))
        for n in slots: me.materials.append(lib[n])
        me.polygons.foreach_set("material_index", np.ascontiguousarray(qm, np.int32))
        ul = me.uv_layers.new(name="UVMap"); ul.data.foreach_set("uv", np.ascontiguousarray(uv2[q.ravel()], np.float32).ravel())
        at = me.attributes.new("pow", 'FLOAT', 'POINT'); at.data.foreach_set("value", pw)
        at = me.attributes.new("rest", 'FLOAT_VECTOR', 'POINT'); at.data.foreach_set("vector", rest2.ravel())
        me.update(calc_edges=True)
        try: me.shade_smooth()
        except Exception: me.polygons.foreach_set("use_smooth", np.ones(nf, bool))
        try: me.normals_split_custom_set_from_vertices(np.ascontiguousarray(NN_, np.float32))
        except Exception as e: log("normals", e)
        ob = bpy.data.objects.new("air", me); sc.collection.objects.link(ob)
        eye = eye0 + vel * t
        if ej is not None:
            vis = lambda p: outside(p, t, lag) & (np.linalg.norm(p - eye, axis=1) > 0.5)
            p_, c_, r_, s_ = ej.clods(t); k = vis(p_); set_instances(clods, p_[k], c_[k], r_[k], s_[k])
            p_, c_, r_, s_ = ej.straw(t); k = vis(p_); set_instances(straw, p_[k], c_[k], r_[k], s_[k])
            p_, c_, e_, r_ = ej.dust(t); k = vis(p_); set_points(dust, p_[k], c_[k], e_[k], r_[k])
        if GRASS is not None:
            gone = GRASS["gone"]; base = GRASS["G3"][:, :2, :].mean(1)
            if sim is not None and t > 0:
                # grass the fuselage has passed through is gone (pressed under it): test blade tips and bases against the hull every millisecond up to now
                tip = GRASS["G3"][:, 2, :]; b3 = base + np.array([0, 0, 0.03])
                for tk in np.arange(GRASS["tlast"], t + 1e-9, 0.001):
                    lg = lag * (tk / t); gone |= ~outside(tip, tk, lg) | ~outside(b3, tk, lg)
                GRASS["tlast"] = t
            kb = ~gone
            if LOD[1] > 0:                                                # blades are drawn only near the eye (each has its own cut-off distance, so they thin out); beyond that they are far below a pixel wide and the tinted ground stands in
                kb &= np.linalg.norm(base - eye, axis=1) < LOD[0] + GRASS["u"] * (LOD[1] - LOD[0])
            if not np.array_equal(kb, GRASS["keep"]):
                nb_ = int(kb.sum()); GRASS["keep"] = kb
                me2 = mesh_from("grass", GRASS["G3"][kb].reshape(-1, 3), np.arange(nb_ * 3).reshape(-1, 3), GRASS["cg"][kb].reshape(-1, 3), None, GRASS["mat"], smooth=False)
                oldm = GRASS["ob"].data; GRASS["ob"].data = me2; bpy.data.meshes.remove(oldm)
        # camera: eye point carried at the aircraft's velocity, looking along the nose, tilted a little toward the flight path
        fwd = R0 @ np.array([1.0, 0, 0]); up = R0 @ np.array([0, 0, 1.0]); left = R0 @ np.array([0, 1.0, 0])
        ld = np.radians(A.look_down); f2 = fwd * np.cos(ld) - up * np.sin(ld); u2 = up * np.cos(ld) + fwd * np.sin(ld)
        M = Matrix.Identity(4)
        for r in range(3): M[r][0] = -left[r]; M[r][1] = u2[r]; M[r][2] = -f2[r]; M[r][3] = eye[r]
        co.matrix_world = M
        lo.location = Vector((eye + R0 @ np.array([-0.25, -0.36, 0.14])).tolist())
        sc.render.filepath = fpath
        t1 = time.time(); bpy.ops.render.render(write_still=True)
        log(f"t {tms} ms faces {F}/{len(Q)} torn joints {int(PC.torn.sum())}/{len(PC.torn)} dead screens {int(PC.dead.sum())} eye {eye.round(2)} render {time.time() - t1:.0f}s total {time.time() - t0:.0f}s -> {sc.render.filepath}")
    log("done")


main()
