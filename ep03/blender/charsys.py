import os
"""LastSecond channel universal character system.
One skeleton (Blender's bundled Rigify human metarig, face bones replaced by a compact
block-face set) + parametric faceted block body + offset clothing shells that share the
body's skinning, so clothes stand proud of the body and follow it without clipping.

make_character(name, **params) -> (rig, body_obj)
"""
import bpy, bmesh, math, addon_utils
from mathutils import Vector, Matrix

addon_utils.enable('rigify', default_set=True)

Z0 = [0.0, 0.085, 0.537, 1.01, 1.466, 1.658, 1.72, 1.98]   # metarig knots
FR = {  # target knot fractions of total height
    'adult': [0, .042, .262, .500, .694, .820, .834, 1.0],
    'old':   [0, .043, .260, .494, .686, .813, .828, 1.0],
    'teen':  [0, .044, .265, .498, .680, .800, .814, 1.0],
    'child': [0, .050, .250, .455, .618, .752, .765, 1.0],
}

def _lerpmap(z, xs, ys):
    if z <= xs[0]: return ys[0] + (z - xs[0]) * (ys[1]-ys[0])/(xs[1]-xs[0])
    for i in range(len(xs)-1):
        if z <= xs[i+1]:
            t = (z-xs[i])/(xs[i+1]-xs[i]); return ys[i] + t*(ys[i+1]-ys[i])
    return ys[-1] + (z-xs[-1])

def _mat(name, col, rough=0.72, spec=0.3):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1); b.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in b.inputs: b.inputs['Specular IOR Level'].default_value = spec
    return m

# ---------------------------------------------------------------- mesh builder
class Builder:
    def __init__(self):
        self.bm = bmesh.new(); self.dl = self.bm.verts.layers.deform.verify()
        self.groups = []; self.mats = []
        # layer: 0 skin, 1 footwear, 2 top, 3 top details, 4 bottom, 5 belt, 6 belt details
        self.layer = 0; self.ll = self.bm.verts.layers.int.new('layer')
    def gi(self, name):
        if name not in self.groups: self.groups.append(name)
        return self.groups.index(name)
    def mi(self, m):
        if m not in self.mats: self.mats.append(m)
        return self.mats.index(m)
    def _add(self, verts, faces, weights, mat):
        mi = self.mi(mat); vs = []
        for co, w in zip(verts, weights):
            v = self.bm.verts.new(co)
            for g, val in w.items(): v[self.dl][self.gi(g)] = val
            v[self.ll] = self.layer
            vs.append(v)
        for f in faces:
            try:
                ff = self.bm.faces.new([vs[i] for i in f]); ff.material_index = mi; ff.smooth = False
            except ValueError: pass
        return vs
    def box(self, center, size, frame, group, mat, bevel=0.18, taper=None):
        """chamfered box. frame: 3x3 Matrix columns = local x,y,z. size along local axes.
        taper=(sx,sz) scales the +y end cross-section."""
        tb = bmesh.new(); bmesh.ops.create_cube(tb, size=1.0)
        for v in tb.verts:
            x, y, z = v.co
            if taper and y > 0: x *= taper[0]; z *= taper[1]
            v.co = Vector((x*size[0], y*size[1], z*size[2]))
        if bevel > 0:
            off = bevel*min(size)
            bmesh.ops.bevel(tb, geom=list(tb.edges), offset=off, segments=1, profile=0.5, affect='EDGES')
        verts = [Vector(center) + frame @ v.co for v in tb.verts]
        faces = [[v.index for v in f.verts] for f in tb.faces]
        tb.free()
        w = group if isinstance(group, dict) else {group: 1.0}
        return self._add(verts, faces, [w]*len(verts), mat)
    def tube(self, rings, mat, cap0=None, cap1=None):
        """rings: list of (center, frame, w, d, chamfer, weights). chamfered-rect cross-section (8 verts)."""
        allv = []; ws = []
        for c, F, w, d, ch, wt in rings:
            hw, hd = w/2, d/2; cx, cz = min(ch, .45)*hw*2, min(ch, .45)*hd*2
            pts = [(hw-cx, hd), (hw, hd-cz), (hw, -hd+cz), (hw-cx, -hd), (-hw+cx, -hd), (-hw, -hd+cz), (-hw, hd-cz), (-hw+cx, hd)]
            for px, pz in pts:
                allv.append(Vector(c) + F @ Vector((px, 0, pz))); ws.append(wt)
        n = 8; faces = []
        for r in range(len(rings)-1):
            for i in range(n):
                a, b = r*n+i, r*n+(i+1) % n
                faces.append([a, b, b+n, a+n])
        # garment tubes are open sleeves (a cap would cut through the body underneath)
        if cap0 is None: cap0 = self.layer in (0, 1)
        if cap1 is None: cap1 = self.layer in (0, 1)
        if cap0: faces.append(list(range(n))[::-1])
        if cap1: faces.append([ (len(rings)-1)*n + i for i in range(n)])
        return self._add(allv, faces, ws, mat)
    def to_object(self, name):
        me = bpy.data.meshes.new(name); self.bm.normal_update(); self.bm.to_mesh(me); self.bm.free()
        ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
        for g in self.groups: ob.vertex_groups.new(name=g)
        for m in self.mats: me.materials.append(m)
        for p in me.polygons: p.use_smooth = False
        return ob

def frame_from(d, up=None):
    d = Vector(d).normalized()
    if up is None:
        up = Vector((0, 0, 1)) if abs(d.z) < 0.7 else Vector((0, -1, 0))
    z = (up - up.dot(d)*d).normalized(); x = d.cross(z).normalized(); z = x.cross(d).normalized()
    return Matrix((x, d, z)).transposed()

def world_frame():
    return Matrix(((1, 0, 0), (0, 1, 0), (0, 0, 1)))

# ---------------------------------------------------------------- skeleton
def build_rig(name, H, age, sex, build):
    bpy.ops.object.armature_human_metarig_add(); meta = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT'); eb = meta.data.edit_bones
    for b in list(eb['face'].children_recursive) + [eb['face']]: eb.remove(b)
    zs = [f*H for f in FR[age]]
    s = H/1.98
    sw = {'m': 1.25, 'f': 1.12}[sex] * (0.92 if age == 'child' else 1.0) * build**0.35
    hw = {'m': 1.0, 'f': 1.06}[sex] * build**0.4
    dep = build**0.45
    zm = lambda z: _lerpmap(z, Z0, zs)
    S0 = Vector((0.195, 0.027, 1.585)); S1 = Vector((S0.x*s*sw, S0.y*s, zm(S0.z)))
    armk = 1.05 if age == 'child' else 1.12
    def arm_chain(b):
        n = b.name
        return any(n.startswith(k) for k in ('upper_arm', 'forearm', 'hand', 'palm', 'f_', 'thumb'))
    def leg_chain(b):
        return any(b.name.startswith(k) for k in ('thigh', 'shin', 'foot', 'toe', 'heel'))
    orig = {b.name: (b.head.copy(), b.tail.copy()) for b in eb}
    newp = {}
    for b in eb:
        for ai, attr in enumerate(('head', 'tail')):
            p = orig[b.name][ai].copy()
            sx = 1 if p.x >= 0 else -1
            if arm_chain(b):
                S0s = Vector((S0.x*sx, S0.y, S0.z)); S1s = Vector((S1.x*sx, S1.y, S1.z))
                q = S1s + (p - S0s)*s*armk
            elif leg_chain(b):
                q = Vector((p.x*s*hw, p.y*s, zm(p.z)))
                if b.name.startswith(('foot', 'toe', 'heel')) and p.z < 0.1:
                    q.z = p.z*s
            elif b.name.startswith(('shoulder', 'breast')):
                q = Vector((p.x*s*sw, p.y*s*dep, zm(p.z)))
            elif b.name.startswith('pelvis'):
                q = Vector((p.x*s*hw, p.y*s*dep, zm(p.z)))
            else:
                q = Vector((p.x*s, p.y*s*dep, zm(p.z)))
            newp[(b.name, attr)] = q
    for b in eb:
        b.head = newp[(b.name, 'head')]; b.tail = newp[(b.name, 'tail')]
    # compact face bones
    head = eb['spine.006']; hb, top = zm(1.72), head.tail.z; hh = top - hb
    meta['hbase'] = hb
    hy = head.head.y; front = hy - hh*0.44
    def fb(n, h, t):
        e = eb.new(n); e.head = h; e.tail = t; e.parent = head; e.roll = 0; return e
    fb('jaw', (0, front+hh*0.08, hb+hh*0.245), (0, front+hh*0.08, hb+hh*0.245-hh*0.12))
    for sx, sd in ((1, 'L'), (-1, 'R')):
        fb('eye.'+sd, (sx*hh*0.17, front+hh*0.05, hb+hh*0.47), (sx*hh*0.17, front-hh*0.05, hb+hh*0.47))
        fb('brow.'+sd, (sx*hh*0.17, front+hh*0.05, hb+hh*0.575), (sx*hh*0.17, front-hh*0.05, hb+hh*0.575))
    bpy.ops.object.mode_set(mode='POSE')
    for n in ('jaw', 'eye.L', 'eye.R', 'brow.L', 'brow.R'):
        meta.pose.bones[n].rigify_type = 'basic.super_copy'
        meta.pose.bones[n].rigify_parameters.make_widget = True
    bpy.ops.object.mode_set(mode='OBJECT')
    meta.data.rigify_rig_basename = name + '_rig'
    bpy.ops.pose.rigify_generate()
    rig = bpy.data.objects[name + '_rig']
    rig['hbase'] = meta['hbase']
    bpy.data.objects.remove(meta, do_unlink=True)
    return rig

# ---------------------------------------------------------------- body
SKINS = {'light': (0.62, 0.43, 0.32), 'tan': (0.47, 0.30, 0.20), 'brown': (0.34, 0.21, 0.13), 'dark': (0.22, 0.13, 0.08)}

def _bl(rig, n):
    b = rig.data.bones[n]; return b.head_local.copy(), b.tail_local.copy()

def limb_rings(rig, chain, radii, side, mode='body', off=0.0, t_end=None, t_start=0.0, ch=0.32, root=None, ups=None):
    """continuous blended tube along DEF chain. radii: list of (w,d) at each chain joint (len = len(chain)+1).
    Blend zone at each internal joint. t_end: stop at this chain-param (0..len) for sleeves."""
    pts = [_bl(rig, c)[0] for c in chain] + [_bl(rig, chain[-1])[1]]
    if ups is None:
        frames = [frame_from(pts[i+1]-pts[i]) for i in range(len(chain))]
    else:
        frames = [frame_from(pts[i+1]-pts[i], up=ups[i]) for i in range(len(chain))]
    L = len(chain); t_end = L if t_end is None else t_end
    samples = []
    # sample params: start, around each joint, end
    ts = [t_start]
    if t_start < 0:
        # long, eased blend from the pelvis into the limb (hip/shoulder): avoids the square
        # corner of the limb's top ring swinging out behind the pelvis
        for tt in ((-0.2, -0.05, 0.1, 0.25, 0.42) if root else (-0.22, 0.0, 0.22)):
            if t_start < tt < t_end: ts.append(tt)
    for j in range(1, L):
        for dt in (-0.22, 0.0, 0.22):
            if t_start < j+dt < t_end: ts.append(j+dt)
    ts.append(t_end)
    rings = []
    for t in ts:
        i = min(max(int(math.floor(t)), 0), L-1); f = t - i
        c = pts[i].lerp(pts[i+1], f)
        fr = max(f, 0.0)
        w = radii[i][0] + (radii[i+1][0]-radii[i][0])*fr
        d = radii[i][1] + (radii[i+1][1]-radii[i][1])*fr
        if root and t < 0:          # limb top tucks inside the pelvis/shoulder so it can't poke out when flexed
            k = 1 + 0.9*t; w *= k; d *= k
        # weights
        j = round(t)
        if root and t < 0.5:
            a = max(0, min(1, (t+0.25)/0.72)); a = a*a*(3-2*a)
            wt = {root: 1-a, chain[0]: a} if 0 < a < 1 else ({root: 1.0} if a <= 0 else {chain[0]: 1.0})
            F = frames[0]
        elif 0 < j < L and abs(t-j) < 0.23:
            a = (t-j+0.22)/0.44; a = max(0, min(1, a))
            wt = {chain[j-1]: 1-a, chain[j]: a}
            F = frames[j-1].lerp(frames[j], a) if hasattr(Matrix, 'lerp') else frames[j-1]
            F = frame_from((frames[j-1].col[1]*(1-a) + frames[j].col[1]*a), up=(frames[j-1].col[2]*(1-a) + frames[j].col[2]*a))
        else:
            wt = {chain[i]: 1.0}; F = frames[i]
        rings.append((c, F, w+2*off, d+2*off, ch, wt))
    return rings

# ---------------------------------------------------------------- layered-clothing resolver
def _region(name):
    """body region of a deform bone, so garments are only fitted against their own limb."""
    n = name.replace('DEF-', '')
    side = n.split('.')[1][0] if '.' in n and n.split('.')[1][:1] in 'LR' else ''
    for key, reg in (('upper_arm', 'arm'), ('forearm', 'arm'), ('hand', 'arm'), ('f_', 'arm'), ('thumb', 'arm'),
                     ('palm', 'arm'), ('shoulder', 'arm'), ('thigh', 'leg'), ('shin', 'leg'), ('foot', 'leg'), ('toe', 'leg')):
        if n.startswith(key): return reg + side
    return 'torso'

SOLID = (0, 1, 2, 4, 5)          # layers that are surfaces; 3/6 are small details riding on 2/5

def resolve_layers(B, s, margin=0.0045, look=0.035):
    """Make every garment layer lie at least `margin`*s outside every layer beneath it
    (skin < shoes < top < bottom < belt), measured along the skin normal, then give each garment
    vertex the skin weights under it so all layers bend identically. Works for any preset."""
    from mathutils.bvhtree import BVHTree
    bm = B.bm; ll, dl = B.ll, B.dl
    margin *= s; look *= s
    bm.verts.ensure_lookup_table()
    groups = B.groups
    def reg_of(v):
        w = v[dl]
        if not w: return 'torso'
        g = max(w.items(), key=lambda kv: kv[1])[0]
        return _region(groups[g])
    vreg = [reg_of(v) for v in bm.verts]
    def tree(layers, reg):
        tb = bm.copy(); tl = tb.verts.layers.int['layer']
        tb.verts.ensure_lookup_table()
        kill = [tv for tv, r in zip(tb.verts, vreg) if tv[tl] not in layers or r != reg]
        bmesh.ops.delete(tb, geom=kill, context='VERTS')
        if not tb.faces: tb.free(); return None, None
        bmesh.ops.recalc_face_normals(tb, faces=tb.faces)
        tb.faces.ensure_lookup_table()
        return tb, BVHTree.FromBMesh(tb)
    regions = sorted(set(vreg))
    skin = {r: tree((0,), r) for r in regions}
    def hits(tr, o, d, maxd):
        out = []; t0 = 0.0
        for _ in range(6):
            loc, nrm, fi, dist = tr.ray_cast(o + d*t0, d, maxd - t0)
            if loc is None: break
            t0 = (loc - o).dot(d) + 1e-5; out.append(t0)
        return out
    garment_layers = [L for L in (1, 2, 3, 4, 5, 6) if any(v[ll] == L for v in bm.verts)]
    for L in garment_layers:
        base = L - 1 if L in (3, 6) else None      # details only need to clear their own base layer
        below = (base,) if base is not None else tuple(x for x in SOLID if x < L)
        for r in regions:
            sb, st = skin[r]
            if st is None: continue
            ib, it = tree(below, r)
            gb = tuple(x for x in below if x >= 1)       # lower GARMENTS of any region (e.g. trouser leg under belt)
            xb, xt = (None, None)
            if gb:
                xb = bm.copy(); xl = xb.verts.layers.int['layer']; xb.verts.ensure_lookup_table()
                bmesh.ops.delete(xb, geom=[tv for tv in xb.verts if tv[xl] not in gb], context='VERTS')
                xt = BVHTree.FromBMesh(xb) if xb.faces else None
            for v, vr in zip(bm.verts, vreg):
                if v[ll] != L or vr != r: continue
                p0, n0, fi, d0 = st.find_nearest(v.co)
                if p0 is None: continue
                if n0.dot(v.co - p0) < -0.02*s: continue   # deep inside another shell: leave alone
                h = n0.dot(v.co - p0)
                need = margin if 0 in below else -1
                for tr_ in (it, xt):
                    if tr_ is None: continue
                    hs = [t for t in hits(tr_, p0 - n0*0.002*s, n0, h + look) if t < h + look]
                    if hs: need = max(need, max(hs) - 0.002*s + margin)
                if h < need:
                    v.co = p0 + n0*need + (v.co - p0 - n0*h)
            if ib: ib.free()
            if xb: xb.free()
    # weight transfer for small details only (buttons, pockets, buckle, epaulettes): they ride on the
    # surface under them. Tubes keep their own ring weights, which already mirror the skin rings
    # exactly; per-vertex transfer there makes rings uneven and the flat shading looks crumpled.
    for v, vr in zip(bm.verts, vreg):
        if v[ll] not in (3, 6): continue
        sb, st = skin.get(vr, (None, None))
        if st is None: continue
        loc, nrm, fi, d = st.find_nearest(v.co)
        if loc is None: continue
        sdl = sb.verts.layers.deform.active
        ws = {}; tot = 0.0
        for fv in sb.faces[fi].verts:
            k = 1.0/((fv.co - loc).length + 1e-4); tot += k
            for g, val in fv[sdl].items(): ws[g] = ws.get(g, 0.0) + k*val
        dv = v[dl]; dv.clear()
        for g, val in ws.items():
            if val/tot > 1e-3: dv[g] = val/tot
    for sb, st in skin.values():
        if sb: sb.free()

def make_character(name, sex='m', age='adult', height=1.74, build=1.0, skin='tan',
                   hair='short', hair_col=(0.03, 0.025, 0.02), facial=None,
                   top='shirt', top_col=(0.55, 0.57, 0.60), sleeve='short',
                   bottom='trousers', bottom_col=(0.16, 0.17, 0.19), shoe_col=(0.06, 0.05, 0.045),
                   hijab=None, glasses=False, robe_col=None, cap=None, loc=(0, 0, 0)):
    rig = build_rig(name, height, age, sex, build)
    s = height/1.98
    B = Builder()
    SK = _mat(f'skin_{skin}', SKINS.get(skin, skin) if isinstance(skin, str) else skin, rough=0.6)
    HR = _mat(f'hair_{name}', hair_col, rough=0.8)
    TOP = _mat(f'top_{name}', top_col); BOT = _mat(f'bot_{name}', bottom_col)
    SHO = _mat(f'shoe_{name}', shoe_col, rough=0.5)
    EYE = _mat('eye_dark', (0.025, 0.02, 0.02), rough=0.35, spec=0.6)
    MOU = _mat('mouth_dark', (0.09, 0.03, 0.03), rough=0.6)
    W = {'m': 1.0, 'f': 0.92}[sex]*build**0.5
    kid = age == 'child'
    # ---- torso tube (body)
    def bz(n, end=0): return _bl(rig, n)[end].z
    zc = bz('DEF-thigh.L') - 0.085*s      # crotch
    zh = bz('DEF-spine'); z1 = bz('DEF-spine.001'); z2 = bz('DEF-spine.002'); z3 = bz('DEF-spine.003')
    zn = bz('DEF-spine.004'); zhd = bz('DEF-spine.006')
    hipx = abs(_bl(rig, 'DEF-thigh.L')[0].x)
    shx = abs(_bl(rig, 'DEF-upper_arm.L')[0].x)
    yb = lambda z: _lerpmap(z, [zh, zn], [_bl(rig, 'DEF-spine')[0].y*0.6, _bl(rig, 'DEF-spine.004')[0].y])
    fw = world_frame(); up = frame_from((0, 0, 1), up=Vector((0, -1, 0)))
    female = sex == 'f'
    torso_prof = [  # z, width, depth, weights
        # pelvis tapers under the crotch so there is no flat "box ledge" at the seat
        (zc-0.035*s, (2*hipx+0.13*s*W)*0.50, 0.19*s*W*0.55, {'DEF-spine': 1}),
        (zc, (2*hipx+0.13*s*W*(1.08 if female else 1))*0.90, 0.19*s*W*0.86, {'DEF-spine': 1}),
        (zh+0.02*s, 2*hipx+0.15*s*W*(1.1 if female else 1), 0.205*s*W, {'DEF-spine': 1}),
        (z1, (0.34 if not female else 0.30)*s*W, 0.21*s*W, {'DEF-spine': .5, 'DEF-spine.001': .5}),
        (z2, (0.37 if not female else 0.33)*s*W, 0.22*s*W, {'DEF-spine.001': .5, 'DEF-spine.002': .5}),
        (z3, (0.43 if not female else 0.39)*s*W, (0.235 if not female else 0.25)*s*W, {'DEF-spine.002': .4, 'DEF-spine.003': .6}),
        (zn-0.012*s, 2*shx+0.02*s, 0.21*s*W, {'DEF-spine.003': 1}),
        (zn+0.012*s, 0.22*s, 0.16*s, {'DEF-spine.003': .5, 'DEF-spine.004': .5}),
    ]
    def torso_rings(prof, off=0.0, ch=0.30):
        return [((0, yb(z), z), up, w+2*off, d+2*off, ch, wt) for z, w, d, wt in prof]
    B.tube(torso_rings(torso_prof), SK)
    # neck
    hbz = rig['hbase']
    neck = [((0, _bl(rig, 'DEF-spine.004')[0].y, zn-0.01*s), up, 0.13*s, 0.13*s, 0.3, {'DEF-spine.004': 1}),
            ((0, _bl(rig, 'DEF-spine.005')[0].y, hbz+0.03*s), up, 0.12*s, 0.12*s, 0.3, {'DEF-spine.005': .5, 'DEF-spine.006': .5})]
    B.tube(neck, SK)
    bust = female and not kid
    pass
    # ---- arms & legs (body)
    for sd, sx in (('L', 1), ('R', -1)):
        arm = [f'DEF-upper_arm.{sd}', f'DEF-upper_arm.{sd}.001', f'DEF-forearm.{sd}', f'DEF-forearm.{sd}.001']
        ar = [(0.115*s*W, 0.12*s*W), (0.105*s*W, 0.11*s*W), (0.092*s*W, 0.095*s*W), (0.082*s*W, 0.085*s*W), (0.07*s, 0.06*s)]
        # arm + mitten hand as ONE tube: rings oriented by bone roll (z = palm-width axis),
        # so the wrist flattens smoothly into the palm instead of a box stuck on a tube.
        hz = rig.data.bones[f'DEF-hand.{sd}'].matrix_local.col[2].to_3d()
        mchain = arm + [f'DEF-hand.{sd}', f'DEF-f_middle.01.{sd}', f'DEF-f_middle.02.{sd}']
        mups = [rig.data.bones[b].matrix_local.col[2].to_3d() for b in arm] + [hz, hz, hz]
        mr = ar[:4] + [(0.054*s, 0.068*s), (0.050*s, 0.098*s), (0.046*s, 0.094*s), (0.036*s, 0.084*s)]
        B.tube(limb_rings(rig, mchain, mr, sd, ups=mups, ch=0.36), SK)
        # thumb: a slim block lying against the index side of the palm, rigid to the hand
        hh0 = _bl(rig, f'DEF-hand.{sd}')[0]; kn = _bl(rig, f'DEF-f_middle.01.{sd}')[0]
        hd = (kn - hh0); plen = hd.length; hd = hd.normalized()
        side = (_bl(rig, f'DEF-palm.01.{sd}')[0] - _bl(rig, f'DEF-palm.04.{sd}')[0]); side = (side - side.dot(hd)*hd).normalized()
        nrm = hd.cross(side).normalized()
        tip = _bl(rig, f'DEF-thumb.02.{sd}')[1]
        if (tip - hh0).dot(nrm) < 0: nrm = -nrm
        tc = hh0 + hd*plen*0.62 + side*0.040*s + nrm*0.018*s
        TF = frame_from(hd, up=nrm)
        B.box(tc, (0.026*s, plen*0.70, 0.030*s), TF, f'DEF-hand.{sd}', SK, bevel=0.4)
        # shoulder cap
        a0 = _bl(rig, arm[0])[0]
        B.box((a0.x - sx*0.01*s, a0.y, a0.z+0.005*s), (0.12*s*W, 0.12*s*W, 0.10*s*W), fw, {f'DEF-shoulder.{sd}': .5, arm[0]: .5}, SK, bevel=0.3)
        leg = [f'DEF-thigh.{sd}', f'DEF-thigh.{sd}.001', f'DEF-shin.{sd}', f'DEF-shin.{sd}.001']
        lr = [(0.19*s*W*(1.06 if female else 1), 0.195*s*W), (0.16*s*W, 0.165*s*W), (0.13*s*W, 0.135*s*W), (0.12*s*W, 0.125*s*W), (0.085*s, 0.09*s)]
        B.tube(limb_rings(rig, leg, lr, sd, t_start=-0.2, root='DEF-spine', ch=0.42), SK)
        # shoes
        f0, f1 = _bl(rig, f'DEF-foot.{sd}'); t0, t1 = _bl(rig, f'DEF-toe.{sd}')
        # one continuous shoe (heel->ball weighted to foot, blended across the ball, toe cap on toe)
        # so it bends at the ball like a real shoe; collar rises over the ankle to hide the gap.
        SF = frame_from(Vector((0, -1, 0)), up=Vector((0, 0, 1)))
        fb, tb_ = f'DEF-foot.{sd}', f'DEF-toe.{sd}'
        hy = f0.y + 0.06*s; ty = t1.y - 0.015*s; by = t0.y
        ank = f0.z + 0.025*s
        prof = [  # (y, width, height, weights)
            (hy,                  0.078, 0.070, {fb: 1}),
            (hy - 0.025*s,        0.090, ank/s, {fb: 1}),
            (f0.y - 0.02*s,       0.094, ank/s, {fb: 1}),
            ((f0.y + by)/2,       0.100, 0.082, {fb: 1}),
            (by + 0.015*s,        0.104, 0.068, {fb: .7, tb_: .3}),
            (by - 0.015*s,        0.104, 0.062, {fb: .3, tb_: .7}),
            ((by + ty)/2,         0.098, 0.054, {tb_: 1}),
            (ty,                  0.074, 0.040, {tb_: 1}),
        ]
        cx = (f0.x + t0.x)/2
        B.layer = 1
        rings = [((cx, y, h*s/2 + 0.014*s), SF, w*s, h*s, 0.32, wt) for y, w, h, wt in prof]
        B.tube(rings, SHO)
        SOLE = _mat('sole', (0.20, 0.19, 0.18) if shoe_col[0] < 0.2 else (0.06, 0.06, 0.06), rough=0.7)
        srings = [((cx, y, 0.008*s), SF, w*s*1.03, 0.016*s, 0.3, wt) for y, w, h, wt in prof]
        B.tube(srings, SOLE)
        B.layer = 0
    # ---- clothing shells (share skinning, offset outward)
    o = 0.010*s
    B.layer = 2
    if top in ('shirt', 'tee', 'polo', 'uniform', 'jacket'):
        prof = [p for p in torso_prof if p[0] >= z1 - 0.06*s]
        prof[0] = (zh+0.035*s, prof[0][1], prof[0][2], prof[0][3]) if False else prof[0]
        tprof = [(z1+0.004*s, torso_prof[3][1]*1.02, torso_prof[3][2]*1.02, torso_prof[3][3])] + torso_prof[3:]
        B.tube(torso_rings(tprof, off=o), TOP)

        # hem band
        pass
        for sd, sx in (('L', 1), ('R', -1)):
            arm = [f'DEF-upper_arm.{sd}', f'DEF-upper_arm.{sd}.001', f'DEF-forearm.{sd}', f'DEF-forearm.{sd}.001']
            ar = [(0.115*s*W, 0.12*s*W), (0.105*s*W, 0.11*s*W), (0.092*s*W, 0.095*s*W), (0.082*s*W, 0.085*s*W), (0.07*s, 0.06*s)]
            te = {'short': 1.35, 'long': 3.85, 'rolled': 2.7}[sleeve]
            B.tube(limb_rings(rig, arm, ar, sd, off=o*1.3, t_end=te), TOP)
            B.tube(limb_rings(rig, arm, ar, sd, off=o*2.3, t_start=te-0.12, t_end=te), TOP)   # cuff
            a0 = _bl(rig, arm[0])[0]
            B.box((a0.x - sx*0.01*s, a0.y, a0.z+0.008*s), (0.12*s*W+2*o*1.3, 0.12*s*W+2*o*1.3, 0.10*s*W+2*o*1.3), fw, {f'DEF-shoulder.{sd}': .5, arm[0]: .5}, TOP, bevel=0.3)
        if top in ('shirt', 'polo', 'uniform'):
            # collar: stand around neck + two flaps lying on the shirt front
            yn = _bl(rig, 'DEF-spine.004')[0].y
            B.tube([((0, yn, zn-0.005*s), up, 0.15*s, 0.155*s, 0.35, {'DEF-spine.003': .6, 'DEF-spine.004': .4}),
                    ((0, yn, zn+0.04*s), up, 0.135*s, 0.14*s, 0.35, {'DEF-spine.004': 1})], TOP, cap0=False, cap1=False)
            B.layer = 3
            for sx in (1, -1):
                cf = frame_from(Vector((sx*0.45, 0, -1)), up=Vector((0, -1, 0)))
                B.box((sx*0.04*s, yb(zn-0.03*s) - torso_prof[6][2]/2 - o - 0.004*s, zn-0.015*s), (0.055*s, 0.075*s, 0.01*s), cf, 'DEF-spine.003', TOP, bevel=0.2)
            # placket + buttons
            yf = lambda z: yb(z) - _lerpmap(z, [z1, z2, z3], [prof[0][2], torso_prof[4][2], torso_prof[5][2]])/2 - o
            for z in [z1+0.04*s + k*(zn-0.10*s-z1)/4 for k in range(5)]:
                B.box((0, yf(z)-0.003*s, z), (0.012*s, 0.006*s, 0.012*s), fw, 'DEF-spine.002' if z > z2 else 'DEF-spine.001', _mat('button', (0.85, 0.84, 0.8), rough=0.4), bevel=0.3)
            if top in ('shirt', 'uniform'):
                pz = z3 - 0.01*s
                B.box((0.075*s*W, yf(pz)-0.004*s, pz), (0.075*s, 0.008*s, 0.08*s), fw, 'DEF-spine.003', TOP, bevel=0.2)
        if top == 'uniform':
            B.layer = 3
            for sd, sx in (('L', 1), ('R', -1)):
                a0 = _bl(rig, f'DEF-upper_arm.{sd}')[0]
                B.box((a0.x - sx*0.03*s, a0.y, a0.z+0.07*s), (0.10*s, 0.05*s, 0.012*s), fw, f'DEF-shoulder.{sd}', _mat('epaulette', (0.08, 0.09, 0.12)), bevel=0.2)
    if top == 'galabeya':
        # Egyptian galabeya: one long loose robe, neck to ankle. Upper body = loose shell, lower = skirt
        # skinned per vertex across both legs (side weight by x, thigh->shin by height) so it follows walking/sitting.
        B.layer = 2
        go = o*2.2
        gprof = [(zh+0.02*s, torso_prof[2][1]*1.06, torso_prof[2][2]*1.10, torso_prof[2][3])] + torso_prof[3:]
        B.tube(torso_rings(gprof, off=go), TOP)
        for sd, sx in (('L', 1), ('R', -1)):
            arm = [f'DEF-upper_arm.{sd}', f'DEF-upper_arm.{sd}.001', f'DEF-forearm.{sd}', f'DEF-forearm.{sd}.001']
            ar = [(0.125*s*W, 0.13*s*W), (0.12*s*W, 0.125*s*W), (0.115*s*W, 0.12*s*W), (0.11*s*W, 0.115*s*W), (0.105*s, 0.10*s)]
            B.tube(limb_rings(rig, arm, ar, sd, off=go, t_end=3.55), TOP)
            a0 = _bl(rig, arm[0])[0]
            B.box((a0.x - sx*0.01*s, a0.y, a0.z+0.008*s), (0.12*s*W+2*go, 0.12*s*W+2*go, 0.10*s*W+2*go), fw, {f'DEF-shoulder.{sd}': .5, arm[0]: .5}, TOP, bevel=0.3)
        yn = _bl(rig, 'DEF-spine.004')[0].y
        B.tube([((0, yn, zn-0.005*s), up, 0.16*s, 0.16*s, 0.35, {'DEF-spine.003': .6, 'DEF-spine.004': .4}),
                ((0, yn, zn+0.025*s), up, 0.145*s, 0.15*s, 0.35, {'DEF-spine.004': 1})], TOP, cap0=False, cap1=False)
        B.layer = 3
        yfr = yb(z3) - torso_prof[5][2]/2 - go - 0.004*s
        B.box((0, yfr, zn-0.07*s), (0.018*s, 0.008*s, 0.12*s), fw, 'DEF-spine.003', _mat('slit', (0.04, 0.035, 0.03), rough=0.8), bevel=0.2)
        # skirt
        B.layer = 2
        zk = _bl(rig, 'DEF-shin.L')[0].z; za = _bl(rig, 'DEF-foot.L')[0].z
        z_top = zh + 0.02*s; z_hem = za + 0.05*s
        nr, nv = 9, 16
        legw = 0.20*s*W
        verts, wts = [], []
        for k in range(nr):
            t = k/(nr-1); z = z_top + (z_hem - z_top)*t
            w = (torso_prof[2][1]*1.06 + 2*go) + (2*legw*0.55)*t
            d = (torso_prof[2][2]*1.10 + 2*go) + (0.16*s)*t
            yc = _lerpmap(z, [z_hem, zk, z_top], [_bl(rig, 'DEF-shin.L')[0].y, _bl(rig, 'DEF-shin.L')[0].y, yb(z_top)])
            for i in range(nv):
                a = 2*math.pi*i/nv
                x = (w/2)*math.cos(a); y = yc + (d/2)*math.sin(a)
                verts.append(Vector((x, y, z)))
                side = max(0.0, min(1.0, 0.5 + x/(w*0.55)))   # 1 = left leg (+x)
                zk_t = (z - z_top)/(zk - z_top) if z > zk else 1 + (zk - z)/(zk - z_hem)
                wt = {}
                if zk_t < 0.35:
                    sp = 1 - zk_t/0.35; wt['DEF-spine'] = sp*0.8
                    rest = 1 - wt['DEF-spine']
                else:
                    rest = 1.0
                th = max(0.0, min(1.0, 1.6 - zk_t)) if zk_t > 0.6 else 1.0
                sh = 1 - th
                for sd, f in (('L', side), ('R', 1 - side)):
                    if f <= 0: continue
                    wt[f'DEF-thigh.{sd}'] = wt.get(f'DEF-thigh.{sd}', 0) + rest*f*th*0.5
                    wt[f'DEF-thigh.{sd}.001'] = wt.get(f'DEF-thigh.{sd}.001', 0) + rest*f*th*0.5
                    if sh > 0: wt[f'DEF-shin.{sd}'] = rest*f*sh
                wts.append(wt)
        faces = []
        for k in range(nr-1):
            for i in range(nv):
                a_, b_ = k*nv+i, k*nv+(i+1) % nv
                faces.append([a_, b_, b_+nv, a_+nv])
        B._add(verts, faces, wts, TOP)
    if bottom in ('trousers', 'shorts'):
        B.layer = 4
        bprof = [torso_prof[0], torso_prof[1], torso_prof[2],
                 (z1+0.02*s, torso_prof[3][1]*1.03, torso_prof[3][2]*1.03, torso_prof[3][3])]
        B.tube(torso_rings(bprof, off=o*0.8), BOT)
        BELT = _mat('belt', (0.05, 0.04, 0.035), rough=0.45)
        B.layer = 5
        B.tube(torso_rings([(z1-0.012*s, bprof[3][1], bprof[3][2], bprof[3][3]), (z1+0.022*s, bprof[3][1], bprof[3][2], bprof[3][3])], off=o*(0.2 if os.environ.get('BREAK') else 2.0)), BELT, cap0=False, cap1=False)
        B.layer = 6
        B.box((0, yb(z1)-bprof[3][2]/2-o*2.4, z1+0.005*s), (0.045*s, 0.008*s, 0.03*s), fw, {'DEF-spine': .5, 'DEF-spine.001': .5}, _mat('buckle', (0.55, 0.52, 0.45), rough=0.3), bevel=0.2)
        B.layer = 4
        for sd in ('L', 'R'):
            leg = [f'DEF-thigh.{sd}', f'DEF-thigh.{sd}.001', f'DEF-shin.{sd}', f'DEF-shin.{sd}.001']
            lr = [(0.19*s*W*(1.06 if female else 1), 0.195*s*W), (0.16*s*W, 0.165*s*W), (0.14*s*W, 0.145*s*W), (0.13*s*W, 0.135*s*W), (0.125*s, 0.13*s)]
            te = 3.86 if bottom == 'trousers' else 1.7
            B.tube(limb_rings(rig, leg, lr, sd, off=o*1.2, t_end=te, t_start=-0.2, root='DEF-spine', ch=0.42), BOT)
            if bottom == 'trousers':
                B.tube(limb_rings(rig, leg, lr, sd, off=o*1.9, t_start=te-0.08, t_end=te), BOT)
    B.layer = 0
    if not os.environ.get('NORESOLVE'): resolve_layers(B, s)
    # store body region per vertex (used by the clipping checker)
    rl = B.bm.verts.layers.int.new('region'); RID = {'torso': 0, 'armL': 1, 'armR': 2, 'legL': 3, 'legR': 4}
    for v in B.bm.verts:
        w = v[B.dl]
        v[rl] = RID.get(_region(B.groups[max(w.items(), key=lambda kv: kv[1])[0]]) if w else 'torso', 0)
    body = B.to_object(name)
    # ---- head (separate builder for clarity, merged after)
    H_ = Builder()
    hb_, ht_ = _bl(rig, 'DEF-spine.006'); hb_.z = rig['hbase']; hh = ht_.z - hb_.z
    hw_, hd_ = hh*0.84, hh*0.90
    fs = hh/0.281
    hc = Vector((0, hb_.y, hb_.z + hh*0.47))
    front = hc.y - hd_/2
    H_.box(hc, (hw_, hd_, hh*0.94), fw, 'DEF-spine.006', SK, bevel=0.16)
    # jaw/cheek taper block (lower face)
    H_.box((0, hc.y - hd_*0.06, hb_.z + hh*0.10), (hw_*0.82, hd_*0.78, hh*0.2), fw, 'DEF-spine.006', SK, bevel=0.3)
    # ears
    for sx in (1, -1):
        H_.box((sx*(hw_/2+0.006*fs), hc.y+hd_*0.05, hb_.z+hh*0.45), (0.018*fs, 0.05*fs, 0.075*fs), fw, 'DEF-spine.006', SK, bevel=0.3)
    # nose
    H_.box((0, front - 0.012*fs, hb_.z+hh*0.37), (0.034*fs, 0.026*fs, 0.058*fs), fw, 'DEF-spine.006', SK, bevel=0.25, taper=(1.0, 0.7))
    # eyes (white + pupil block), on eye bones for blink
    WH = _mat('eye_white', (0.80, 0.78, 0.74), rough=0.4)
    for sd, sx in (('L', 1), ('R', -1)):
        ex = sx*hh*0.17; ez = hb_.z+hh*0.47
        H_.box((ex, front-0.002*fs, ez), (0.05*fs, 0.006*fs, 0.022*fs), fw, f'DEF-eye.{sd}', WH, bevel=0.2)
        H_.box((ex - sx*0.004*fs, front-0.0055*fs, ez), (0.022*fs, 0.006*fs, 0.024*fs), fw, f'DEF-eye.{sd}', EYE, bevel=0.2)
        bw = 0.062*fs if sex == 'm' else 0.055*fs
        H_.box((ex+sx*0.004*fs, front-0.004*fs, hb_.z+hh*0.575), (bw, 0.012*fs, (0.016 if sex == 'm' else 0.011)*fs), fw, f'DEF-brow.{sd}', HR, bevel=0.15)
    # mouth (on jaw: scale y opens)
    jb = rig.data.bones['DEF-jaw']; jz = jb.head_local.z
    H_.box((0, front-0.001*fs, jz - 0.006*fs), (0.07*fs, 0.006*fs, 0.012*fs), fw, 'DEF-jaw', MOU, bevel=0.2)
    LIP = _mat(f'lip_{skin}', tuple(c*0.82 for c in (SKINS.get(skin) if isinstance(skin, str) else skin)), rough=0.5)
    H_.box((0, front-0.003*fs, jz + 0.002*fs), (0.074*fs, 0.006*fs, 0.006*fs), fw, 'DEF-spine.006', LIP, bevel=0.3)
    # facial hair
    if facial in ('moustache', 'full'):
        H_.box((0, front-0.012*fs, jz+0.012*fs), (0.085*fs, 0.016*fs, 0.02*fs), fw, 'DEF-spine.006', HR, bevel=0.2)
    if facial in ('full', 'stubble'):
        BE = HR if facial == 'full' else _mat(f'stub_{name}', tuple(min(1, c*0.6+0.25*k) for c, k in zip(hair_col, SKINS.get(skin, (0.4, 0.3, 0.2)))), rough=0.9)
        H_.box((0, hc.y - hd_*0.08, hb_.z + hh*0.12), (hw_*0.86, hd_*0.82, hh*0.2), fw, {'DEF-jaw': .5, 'DEF-spine.006': .5}, BE, bevel=0.3)
    # hair
    top_z = ht_.z; hcol = HR
    if cap and hair in ('short', 'side', 'curly'): hair = 'capped'
    if hair == 'capped':
        H_.box((0, hc.y + hd_*0.30, hb_.z+hh*0.62), (hw_+0.024*fs, hd_*0.42, hh*0.40), fw, 'DEF-spine.006', hcol, bevel=0.2)
    if hair in ('short', 'side', 'long', 'bun', 'receding', 'curly'):
        H_.box((0, hc.y+0.004*fs, top_z - hh*0.06 + 0.012*fs), (hw_+0.022*fs, hd_+0.02*fs, hh*0.16), fw, 'DEF-spine.006', hcol, bevel=0.22)
        H_.box((0, hc.y + hd_*0.30, hb_.z+hh*0.62), (hw_+0.024*fs, hd_*0.42, hh*0.52), fw, 'DEF-spine.006', hcol, bevel=0.2)
        for sx in (1, -1):
            H_.box((sx*(hw_/2+0.007*fs), hc.y + hd_*0.30, hb_.z+hh*0.74), (0.016*fs, hd_*0.42, hh*0.24), fw, 'DEF-spine.006', hcol, bevel=0.2)
        if hair != 'receding':
            # stepped fringe blocks
            n = 4
            for k in range(n):
                x = -hw_/2 + (k+0.5)*hw_/n
                dz = (0.035 if (k + (hair == 'side')) % 2 else 0.018)*fs
                if hair == 'side': dz = (0.05 - 0.01*k)*fs
                H_.box((x, front-0.004*fs, top_z - hh*0.13 - dz/2), (hw_/n+0.004*fs, 0.03*fs, hh*0.10+dz), fw, 'DEF-spine.006', hcol, bevel=0.15)
        if hair == 'curly':
            for k in range(7):
                a = k/6*math.pi
                H_.box((math.cos(a)*hw_*0.45, hc.y + math.sin(a)*hd_*0.2 - 0.01*fs, top_z+0.01*fs), (0.07*fs, 0.07*fs, 0.05*fs), fw, 'DEF-spine.006', hcol, bevel=0.35)
        if hair == 'long':
            H_.box((0, hc.y + hd_*0.38, hb_.z+hh*0.2), (hw_+0.03*fs, hd_*0.3, hh*0.75), fw, 'DEF-spine.006', hcol, bevel=0.2)
        if hair == 'bun':
            H_.box((0, hc.y + hd_*0.55, hb_.z+hh*0.78), (0.09*fs, 0.08*fs, 0.08*fs), fw, 'DEF-spine.006', hcol, bevel=0.35)
    if hijab:
        HJ = _mat(f'hijab_{name}', hijab, rough=0.85)
        t = 0.022*fs; topz = ht_.z
        hood_front = front + 0.03*fs
        hood_back = hc.y + hd_/2 + t
        H_.box((0, (hood_front+hood_back)/2, hb_.z + hh*0.5 + t*0.5), (hw_+2*t, hood_back-hood_front, hh*1.0+t), fw, 'DEF-spine.006', HJ, bevel=0.2)
        # face frame bands
        H_.box((0, front - 0.002*fs + 0.017*fs, topz - hh*0.09), (hw_+2*t, 0.04*fs, hh*0.2), fw, 'DEF-spine.006', HJ, bevel=0.25)
        for sx in (1, -1):
            H_.box((sx*(hw_/2 - 0.008*fs + t/2), front + 0.016*fs, hb_.z + hh*0.48), (t+0.016*fs, 0.04*fs, hh*0.9), fw, 'DEF-spine.006', HJ, bevel=0.25)
        H_.box((0, front + 0.03*fs + (hd_*0.55)/2, hb_.z + hh*0.02), (hw_+2*t, hd_*0.55 + 0.02*fs, hh*0.16), fw, 'DEF-spine.006', HJ, bevel=0.3)
        # cowl over neck and shoulders
        yh = hb_.y; ynk = _bl(rig, 'DEF-spine.004')[0].y
        H_.tube([((0, yh+0.01*fs, hb_.z + hh*0.06), up, hw_+2*t, hd_*0.9, 0.35, {'DEF-spine.006': 1}),
                 ((0, (yh+ynk)/2, hb_.z - 0.035*fs), up, hw_+2*t+0.02*fs, hd_*0.95, 0.35, {'DEF-spine.005': .5, 'DEF-spine.006': .5}),
                 ((0, ynk, zn - 0.035*fs), up, 2*shx*0.86, 0.25*fs*W, 0.38, {'DEF-spine.003': 1}),
                 ((0, ynk, zn - 0.075*fs), up, 2*shx*0.90, 0.255*fs*W, 0.38, {'DEF-spine.003': 1})], HJ, cap0=False, cap1=True)
    if glasses:
        GL = _mat('glasses', (0.02, 0.02, 0.02), rough=0.3)
        gz = hb_.z+hh*0.47; gy = front-0.014*fs; gw, gh, bt = 0.068*fs, 0.048*fs, 0.007*fs
        for sx in (1, -1):
            gx = sx*hh*0.17
            for dz in (gh/2, -gh/2):
                H_.box((gx, gy, gz+dz), (gw, bt, bt), fw, 'DEF-spine.006', GL, bevel=0.1)
            for dx in (gw/2, -gw/2):
                H_.box((gx+dx, gy, gz), (bt, bt, gh), fw, 'DEF-spine.006', GL, bevel=0.1)
            H_.box((sx*(hw_/2+0.004*fs), front+hd_*0.25, gz+gh/2), (bt, hd_*0.5, bt), fw, 'DEF-spine.006', GL, bevel=0.1)
        H_.box((0, gy, gz+0.008*fs), (hh*0.34-gw, bt, bt), fw, 'DEF-spine.006', GL, bevel=0.1)
    if cap:
        CP = _mat(f'cap_{name}', cap, rough=0.6)
        H_.box((0, hc.y+0.004*fs, top_z - hh*0.05), (hw_+0.03*fs, hd_+0.03*fs, hh*0.2), fw, 'DEF-spine.006', CP, bevel=0.2)
        H_.box((0, hc.y+0.004*fs, top_z + hh*0.02), (hw_+0.06*fs, hd_+0.06*fs, hh*0.07), fw, 'DEF-spine.006', CP, bevel=0.25)
        H_.box((0, front-0.035*fs, top_z - hh*0.13), (hw_*0.86, 0.08*fs, 0.012*fs), fw, 'DEF-spine.006', _mat('visor', (0.03, 0.03, 0.03), rough=0.3), bevel=0.2)
        H_.box((0, front-0.004*fs, top_z - hh*0.10), (hw_*0.5, 0.008*fs, 0.03*fs), fw, 'DEF-spine.006', _mat('badge', (0.62, 0.55, 0.32), rough=0.35), bevel=0.2)
    head = H_.to_object(name+'_head')
    # merge head into body
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True); head.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    am = body.modifiers.new('arm', 'ARMATURE'); am.object = rig; am.use_deform_preserve_volume = False
    body.parent = rig
    rig.location = loc
    rig.show_in_front = False; rig.hide_render = True
    for o_ in rig.children:
        if o_.name.startswith('WGT') : o_.hide_render = True
    return rig, body

# ---------------------------------------------------------------- posing helpers
def pb(rig, n): return rig.pose.bones[n]

def set_ik_fk(rig, ik=True):
    for n in ('thigh_parent.L', 'thigh_parent.R', 'upper_arm_parent.L', 'upper_arm_parent.R'):
        rig.pose.bones[n]['IK_FK'] = 0.0 if ik else 1.0

def move(rig, n, world_delta):
    """translate a control by an armature-space delta"""
    p = rig.pose.bones[n]; M = p.matrix.copy(); M.translation += Vector(world_delta); p.matrix = M
    bpy.context.view_layer.update()

def rotate(rig, n, axis, deg):
    """rotate a control about an armature-space axis through its head"""
    p = rig.pose.bones[n]; M = p.matrix.copy(); t = M.translation.copy()
    R = Matrix.Rotation(math.radians(deg), 4, Vector(axis))
    M = Matrix.Translation(t) @ R @ Matrix.Translation(-t) @ M; p.matrix = M
    bpy.context.view_layer.update()

def place(rig, n, world_pos):
    p = rig.pose.bones[n]; M = p.matrix.copy(); M.translation = Vector(world_pos); p.matrix = M
    bpy.context.view_layer.update()

VISEME = {'rest': (1, 1), 'M': (1.05, 0.5), 'A': (1.0, 3.6), 'E': (1.25, 2.0), 'O': (0.72, 3.0), 'U': (0.6, 1.8), 'F': (1.1, 1.0)}
def mouth(rig, v):
    sx, sy = VISEME[v]; p = rig.pose.bones['jaw']; p.scale = (sx, sy, 1)

def blink(rig, amt):
    for sd in ('L', 'R'): rig.pose.bones['eye.'+sd].scale = (1, 1, 1)
    for sd in ('L', 'R'):
        p = rig.pose.bones['eye.'+sd]; p.scale = (1, 1, max(0.08, 1-amt))
