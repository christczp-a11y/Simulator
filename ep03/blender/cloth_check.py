"""Automated clothing-penetration test: every preset x several mocap clips.
Counts triangle-triangle intersections between layers that must never touch
(skin/shoes/top/bottom/belt). Prints a table; exit summary line 'TOTAL n'."""
import sys, json
sys.path.insert(0, '/home/claude/ep03')
import bpy
from mathutils.bvhtree import BVHTree
from lib import reset
import charsys as C, retarget as RT
exec(open('/home/claude/ep03/presets.py').read())   # PEOPLE
CLIPS = [('02_01', 0, 12)] if 'rest' in sys.argv else [('02_01', 0, 300), ('09_01', 0, 140), ('113_15', 0, 960)]
PAIRS = [(0, 2), (0, 4), (0, 5), (2, 4), (2, 5), (4, 5), (1, 4)]
STEP = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 12
NAMES = {0: 'skin', 1: 'shoe', 2: 'top', 4: 'bottom', 5: 'belt'}
only = [a for a in sys.argv if a.startswith('only=')]
people = PEOPLE if not only else [p for p in PEOPLE if p['name'] in only[0][5:].split(',')]
res = {}
BADS = []
import bmesh
def count_exposed(o, m, scale, look=0.03):
    """Visible poke-through test. From every skin point cast a ray outward along the skin normal and
    list the layers it crosses within `look`. Layers must be met in order skin<shoe<top<bottom<belt;
    if the OUTERMOST surface hit is a lower layer than one already crossed, an inner layer is
    showing through an outer one -> visible clipping. Hidden overlaps under a covering layer are ignored."""
    look *= scale
    lay = [d.value for d in o.data.attributes['layer'].data]
    reg = [d.value for d in o.data.attributes['region'].data]
    def related(a, b):            # same body part, or torso<->leg (waistband / belt over trouser legs)
        return a == b or {a, b} in ({0, 3}, {0, 4})
    bm = bmesh.new(); bm.from_mesh(m)
    bm.verts.ensure_lookup_table()
    mw = o.matrix_world; bm.transform(mw)
    trees = {}
    freg = {}
    for L in (0, 1, 2, 4, 5):
        tb = bm.copy(); tb.verts.ensure_lookup_table()
        rl_ = tb.verts.layers.int['region']
        bmesh.ops.delete(tb, geom=[v for v, l in zip(tb.verts, lay) if l != L], context='VERTS')
        if tb.faces:
            trees[L] = BVHTree.FromBMesh(tb); tb.faces.ensure_lookup_table()
            freg[L] = [f.verts[0][rl_] for f in tb.faces]
        tb.free()
    sk = bm.copy(); sk.verts.ensure_lookup_table()
    bmesh.ops.delete(sk, geom=[v for v, l in zip(sk.verts, lay) if l != 0], context='VERTS')
    bmesh.ops.recalc_face_normals(sk, faces=sk.faces); sk.normal_update()
    trees[0] = BVHTree.FromBMesh(sk)     # skin with outward normals: lets us tell 'entering another limb'
    srl = sk.verts.layers.int['region']
    origins = [(f.calc_center_median(), f.normal.copy(), f.verts[0][srl]) for f in sk.faces] + [(v.co.copy(), v.normal.copy(), v[srl]) for v in sk.verts]
    bad = 0
    for p0, n0, r0 in origins:
        seq = []
        for L, t in trees.items():
            o_ = p0 + n0*1e-4; t0 = 0.0
            for _ in range(4):
                loc, nrm, fi, d = t.ray_cast(o_ + n0*t0, n0, (look + 0.06*scale if L == 0 else look) - t0)
                if loc is None: break
                dd = (loc - o_).dot(n0); t0 = dd + 1e-4
                if L != 0 and not related(r0, freg[L][fi]): continue
                if L == 0 and nrm.dot(n0) < 0: seq.append((dd, -1)); break   # entering another body part
                seq.append((dd, -2 if L == 0 else L))                         # -2: leaving a skin shell
        seq.sort()
        ex = [i for i, (_, L) in enumerate(seq) if L == -2]
        if ex: seq = seq[ex[-1]+1:]            # anything before we leave the body is hidden inside it
        if any(L == -1 for _, L in seq):
            de = seq[[L for _, L in seq].index(-1)][0]
            # surfaces just in front of another limb belong to that limb (e.g. a sleeve passing the hip)
            seq = [(d, L) for d, L in seq if d < de - 0.035*scale]
        if len(seq) < 2: continue
        out = seq[-1][1]
        if out < max(L for _, L in seq):
            bad += 1; BADS.append((round(p0.x,1), round(p0.z,1), tuple(L for _, L in seq)))
    sk.free(); bm.free()
    return bad
for p in people:
    for clip, a, b in CLIPS:
        sc = reset(); import addon_utils; addon_utils.enable('rigify', default_set=True)
        r, body = C.make_character(loc=(0, 0, 0), **p)
        bpy.context.view_layer.update()
        last = RT.retarget(r, f'/home/claude/ep03/mocap/{clip}.bvh', start=a, end=b, step=STEP)
        ms = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == r and 'layer' in o.data.attributes]
        worst = {}
        for f in range(1, last + 1):
            sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
            for o in ms:
                e = o.evaluated_get(dg); m = e.to_mesh()
                n = count_exposed(o, m, scale=p['height']/1.98)
                if n > worst.get('exposed', (0, 0))[0]: worst['exposed'] = (n, f)
                e.to_mesh_clear()
        res[f"{p['name']} {clip}"] = worst
        print('ROW', p['name'], clip, json.dumps(worst), flush=True)
tot = sum(v[0] for w in res.values() for v in w.values())
print('TOTAL', tot)
from collections import Counter
print('WHERE', Counter(BADS).most_common(15))
