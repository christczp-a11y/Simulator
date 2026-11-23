"""Procedural telescoping-collision damage for the El-Ayyat stills.
The striking loco rides over the tail coach floor and drives ~pen metres into it: the coach end is
split open, side walls peel outward like a banana skin, the roof is torn up and back over the cab,
the floor folds down, and the section ahead of the hinge crumples into an accordion."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, noise

def _apply_mods(o):
    for mo in list(o.modifiers):
        try:
            with bpy.context.temp_override(object=o, active_object=o):
                bpy.ops.object.modifier_apply(modifier=mo.name)
        except Exception:
            o.modifiers.remove(mo)

def _densify(bm, M, y0, y1, step_y=0.22, zs=(1.35, 1.7, 2.1, 2.5, 2.9, 3.2, 3.6), xs=(-1.2, -0.6, 0.0, 0.6, 1.2)):
    """Bisect the zone so big flat panels can bend."""
    Mi = M.inverted(); R = M.to_3x3().inverted()
    def zone():
        return [g for g in bm.faces if y0 - 0.5 < (M @ g.calc_center_median()).y < y1 + 0.5] + \
               [e for e in bm.edges] + [v for v in bm.verts]
    y = y0
    while y <= y1:
        co = Mi @ Vector((0, y, 0)); no = (R @ Vector((0, 1, 0))).normalized()
        g = [f for f in bm.faces if abs((M @ f.calc_center_median()).y - y) < 1.6]
        if g:
            ge = set(g); ed = {e for f in g for e in f.edges}; vs = {v for f in g for v in f.verts}
            bmesh.ops.bisect_plane(bm, geom=list(ge) + list(ed) + list(vs), plane_co=co, plane_no=no)
        y += step_y
    for z in zs:
        g = [f for f in bm.faces if y0 - 0.3 < (M @ f.calc_center_median()).y < y1 + 0.3]
        ed = {e for f in g for e in f.edges}; vs = {v for f in g for v in f.verts}
        bmesh.ops.bisect_plane(bm, geom=g + list(ed) + list(vs), plane_co=Mi @ Vector((0, 0, z)), plane_no=(R @ Vector((0, 0, 1))).normalized())
    for x in xs:
        g = [f for f in bm.faces if y0 - 0.3 < (M @ f.calc_center_median()).y < y1 + 0.3]
        ed = {e for f in g for e in f.edges}; vs = {v for f in g for v in f.verts}
        bmesh.ops.bisect_plane(bm, geom=g + list(ed) + list(vs), plane_co=Mi @ Vector((x, 0, 0)), plane_no=(R @ Vector((1, 0, 0))).normalized())

def telescope(o, rear_y=0.0, pen=6.0, crumple=5.0, seed=1, side_peel=(70, 35), roof_lift=55, keep_interior=False):
    """o: coach whose rear end is at world y=rear_y, body toward -Y... (coach front at lower y).
    pen: how far the striker has entered (m). crumple: accordion length ahead of the entry hinge."""
    rnd = random.Random(seed)
    _apply_mods(o)
    M = o.matrix_world.copy(); Mi = M.inverted()
    hinge = rear_y - pen                     # where peeling starts
    y0 = hinge - crumple
    bm = bmesh.new(); bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    # interior fittings inside the entry zone are smashed: remove them, debris is added separately
    if not keep_interior:
        kill = [f for f in bm.faces if (lambda c: c.y > hinge - 0.4 and abs(c.x) < 1.30 and 1.30 < c.z < 3.05)(M @ f.calc_center_median())]
        bmesh.ops.delete(bm, geom=kill, context='FACES')
    _densify(bm, M, y0, rear_y)
    # tear lines: split edges along the roof/side seam, the floor line, the window band and random verticals
    cuts = []
    vys = [hinge + rnd.uniform(0.3, pen - 0.3) for _ in range(5)] + [hinge + 0.05]
    for e in bm.edges:
        a, b = M @ e.verts[0].co, M @ e.verts[1].co
        if min(a.y, b.y) < hinge - 0.05: continue
        mz = (a.z + b.z) / 2; my = (a.y + b.y) / 2
        horiz = abs(a.z - b.z) < 0.02; vert = abs(a.y - b.y) < 0.02
        if horiz and (abs(mz - 3.2) < 0.06 or abs(mz - 1.35) < 0.06 or (abs(mz - 2.5) < 0.06 and rnd.random() < 0.6)):
            cuts.append(e)
        elif vert and any(abs(my - vy) < 0.12 for vy in vys) and rnd.random() < 0.85:
            cuts.append(e)
    bmesh.ops.split_edges(bm, edges=cuts)
    # connected pieces -> each gets its own peel angle jitter (opens the tears)
    bm.verts.ensure_lookup_table(); seen = set(); pieces = []
    for v in bm.verts:
        if v.index in seen: continue
        st = [v]; comp = []; seen.add(v.index)
        while st:
            u = st.pop(); comp.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in seen: seen.add(w.index); st.append(w)
        pieces.append(comp)
    for comp in pieces:
        jit = (rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))
        for v in comp:
            w = M @ v.co
            if w.y < y0:
                continue
            if w.y < hinge:                                   # accordion crumple ahead of the hinge
                s = (w.y - y0) / crumple                        # 0..1
                w.y = y0 + (w.y - y0) * 0.62
                fold = math.sin(s * math.pi * 6.0)
                amp = 0.05 + 0.22 * s
                if abs(w.x) > 1.0:  w.x += math.copysign(amp * abs(fold), w.x)
                if w.z > 2.9:       w.z += 0.16 * s * fold
                if w.z < 1.45:      w.z -= 0.10 * s * abs(fold)
                w += Vector((noise.noise(w * 2.1), noise.noise(w * 2.1 + Vector((5, 1, 2)))*0.5, noise.noise(w * 2.1 + Vector((9, 3, 7))))) * 0.06 * s
                v.co = Mi @ w; continue
            # entry zone: shift the whole zone back so the crumpled part stays attached
            w.y = hinge - crumple * 0.38 + (w.y - hinge) + crumple * 0.0
            t = min(1.0, (w.y - (hinge - crumple * 0.38)) / max(pen, 0.1))       # 0 at hinge .. 1 at old rear end
            hy = hinge - crumple * 0.38
            if w.z > 3.05:                                   # roof: torn up and back over the striker
                ang = math.radians(roof_lift * (0.35 + 0.65 * t) + 12 * jit[0])
                p = Vector((0, w.y - hy, w.z - 3.05)); R = Matrix.Rotation(-ang, 3, 'X'); p = R @ p
                w.y, w.z = hy + p.y, 3.05 + p.z + 0.4 * t
                w.x *= 1 + 0.25 * t
            elif w.z < 1.45:                                 # floor: folded down and buckled
                w.z -= (0.15 + 0.55 * t) * (1 + 0.3 * jit[1])
                w.y -= 0.35 * t * t
                w.x *= 1 + 0.10 * t
            else:                                            # side walls peel outward about a vertical hinge
                sgn = 1 if w.x >= 0 else -1
                peel = side_peel[0] if sgn > 0 else side_peel[1]
                ang = math.radians(peel * (0.25 + 0.75 * t) + 14 * jit[2])
                p = Vector((w.x - sgn * 1.0, w.y - hy, 0)); R = Matrix.Rotation(-sgn * ang, 3, 'Z'); p = R @ p
                w.x, w.y = sgn * 1.0 + p.x + sgn * 0.25 * t, hy + p.y
                w.z += 0.25 * t * jit[0]
            w += Vector((noise.noise(w * 3.0), noise.noise(w * 3.0 + Vector((4, 2, 8)))*0.4, noise.noise(w * 3.0 + Vector((1, 7, 3))))) * (0.05 + 0.10 * t)
            v.co = Mi @ w
    bm.normal_update(); bm.to_mesh(o.data); bm.free()
    return hinge - crumple * 0.38          # new position of the entry hinge

def nose_damage(loco, depth=0.6, seed=2):
    """Crush the loco's front (local y < 1.4) by `depth` with crumples; loco faces -Y, front at local y~0."""
    _apply_mods(loco)
    bm = bmesh.new(); bm.from_mesh(loco.data)
    for v in bm.verts:
        c = v.co
        if c.y < 1.6 and c.z > 0.5:
            s = (1.6 - c.y) / 1.6
            c.y += depth * s
            c += Vector((noise.noise(c * 3.3), noise.noise(c * 3.3 + Vector((3, 3, 3)))*0.3, noise.noise(c * 3.3 + Vector((7, 1, 5))))) * 0.07 * s
    bm.to_mesh(loco.data); bm.free()

def debris(center, n, mats, spread=(3.0, 4.0, 2.5), seed=3, size=(0.03, 0.35), fly=True):
    rnd = random.Random(seed); out = []
    for i in range(n):
        me = bpy.data.meshes.new('dbr'); bm = bmesh.new()
        kind = rnd.random()
        if kind < 0.55:   # bent sheet fragment
            sx, sy = rnd.uniform(*size), rnd.uniform(*size)
            vs = [bm.verts.new((x * sx, y * sy, rnd.uniform(-0.03, 0.03) + 0.15 * x * y * sx)) for x in (-1, 0, 1) for y in (-1, 1)]
            bm.faces.new((vs[0], vs[2], vs[3], vs[1])); bm.faces.new((vs[2], vs[4], vs[5], vs[3]))
            bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.006)
        else:             # chunk
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rnd.uniform(size[0], size[1] * 0.4))
            for v in bm.verts: v.co *= rnd.uniform(0.5, 1.4)
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new('dbr', me); bpy.context.scene.collection.objects.link(ob)
        me.materials.append(rnd.choice(mats))
        d = Vector((rnd.gauss(0, spread[0]), rnd.gauss(0, spread[1]), abs(rnd.gauss(0, spread[2])) if fly else 0))
        ob.location = Vector(center) + d
        if not fly: ob.location.z = -0.55 + rnd.uniform(0, 0.08)
        ob.rotation_euler = (rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3))
        out.append(ob)
    return out
