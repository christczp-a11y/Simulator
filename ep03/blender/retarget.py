"""Retarget CMU BVH (cgspeed conversion) onto a charsys Rigify rig, baked to FK controls.
retarget(rig, bvh_path, start=0, end=None, step=4, frame_offset=1, yaw=0) -> last frame
Rotation transfer per bone: T(f) = S(f) @ S_rest^-1 @ Q @ T_rest, where Q swings the target rest
bone direction onto the source rest bone direction (handles T-pose vs A-pose)."""
import bpy, math
from mathutils import Matrix, Vector, Quaternion

MAP = [  # (source, target control, kind)
    ('Hips', 'torso', 'root'),
    ('Hips', 'hips', 'spine'),
    ('Spine1', 'chest', 'spine'),
    ('Head', 'neck', 'nh'),   # CMU neck/head markers are noisy: drive neck+head from head-vs-chest delta,
    ('Head', 'head', 'nh'),   # split, clamped and smoothed
]
for s, t in (('Left', 'L'), ('Right', 'R')):
    MAP += [(f'{s}Arm', f'upper_arm_fk.{t}', 'limb'), (f'{s}ForeArm', f'forearm_fk.{t}', 'limb'),
            (f'{s}UpLeg', f'thigh_fk.{t}', 'limb'), (f'{s}Leg', f'shin_fk.{t}', 'limb'),
            (f'{s}Foot', f'foot_fk.{t}', 'limb'), (f'{s}ToeBase', f'toe_fk.{t}', 'limb')]

def swing(a, b):
    a = a.normalized(); b = b.normalized()
    return a.rotation_difference(b).to_matrix()

def load_bvh(path, scale):
    before = set(bpy.data.objects)
    bpy.ops.import_anim.bvh(filepath=path, global_scale=scale, rotate_mode='NATIVE', axis_forward='-Z', axis_up='Y',
                            update_scene_fps=False, update_scene_duration=False, use_fps_scale=False)
    src = [o for o in bpy.data.objects if o not in before][0]
    return src

def retarget(rig, path, start=0, end=None, step=4, frame_offset=1, yaw=0.0, scale=0.056, hold_root_xy=False, widen=4.0):
    sc = bpy.context.scene
    src = load_bvh(path, scale)
    act = src.animation_data.action
    n = int(act.frame_range[1])
    end = n if end is None else min(end, n)
    for n_ in ('thigh_parent.L', 'thigh_parent.R', 'upper_arm_parent.L', 'upper_arm_parent.R'):
        rig.pose.bones[n_]['IK_FK'] = 1.0
    Ys = Matrix.Rotation(math.radians(yaw), 3, 'Z')
    # rest data
    SW = src.matrix_world.to_3x3(); TW = rig.matrix_world.to_3x3()
    srest = {b.name: (SW @ b.matrix_local.to_3x3(), src.matrix_world @ b.head_local, src.matrix_world @ b.tail_local) for b in src.data.bones}
    trest = {}
    for s, t, k in MAP:
        b = rig.data.bones[t]
        trest[t] = (TW @ b.matrix_local.to_3x3(), rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local)
    # direction references (use deform chain directions for limbs)
    Q = {}
    for s, t, k in MAP:
        if k == 'limb':
            sdir = srest[s][2] - srest[s][1]; tdir = trest[t][2] - trest[t][1]
            Q[t] = swing(tdir, sdir)
        else:
            Q[t] = Matrix.Identity(3)
    # leg length ratio
    sleg = (srest['LeftUpLeg'][1] - srest['LeftFoot'][1]).length
    tleg = (rig.matrix_world @ rig.data.bones['DEF-thigh.L'].head_local - rig.matrix_world @ rig.data.bones['DEF-foot.L'].head_local).length
    k = tleg / sleg
    sc.frame_set(start + 1)
    hip0 = (src.matrix_world @ src.pose.bones['Hips'].head).copy()
    shr = srest['Hips'][1]
    t_torso0 = trest['torso'][1]
    s_hiph = srest['Hips'][1].z - min(srest['LeftToeBase'][2].z, srest['LeftFoot'][1].z)
    t_floor = rig.matrix_world.translation.z
    # source rest facing: assume source faces -Y after import (checked by caller via yaw)
    out_f = frame_offset
    NH = {}
    for f in range(start + 1, end + 1, step):
        sc.frame_set(f)
        for s, t, kind in MAP:
            spb = src.pose.bones[s]
            Sf = SW @ spb.matrix.to_3x3()
            Sr = srest[s][0]
            Tr = trest[t][0]
            if kind == 'nh':
                C = SW @ src.pose.bones['Spine1'].matrix.to_3x3(); Cr = srest['Spine1'][0]
                Dc = C @ Cr.inverted()
                q = (Dc.inverted() @ Sf @ Sr.inverted()).to_quaternion()
                ax_, ang = q.to_axis_angle(); ang = max(-math.radians(28), min(math.radians(28), ang))
                prev = NH.get(t)
                cur = Quaternion(ax_, ang * (0.45 if t == 'neck' else 1.0))
                if prev is not None: cur = prev.slerp(cur, 0.5)
                NH[t] = cur
                R = Ys @ Dc @ cur.to_matrix() @ Ys.inverted() @ Tr
            else:
                R = Ys @ Sf @ Sr.inverted() @ Ys.inverted() @ Q[t] @ Tr
            if t.split('_')[0] in ('thigh', 'shin', 'foot', 'toe'):
                # CMU walkers place feet almost on one line; our hips are wider, so the feet crossed.
                # Rotate the whole leg outward about the forward axis by `widen` degrees.
                R = Matrix.Rotation(math.radians(-widen if t.endswith('.L') else widen), 3, 'Y') @ R
            pb = rig.pose.bones[t]
            M = pb.matrix.copy()
            loc = M.translation.copy()
            if kind == 'root':
                hp = src.matrix_world @ spb.head
                d = Ys @ (hp - hip0)
                if hold_root_xy: d.x = d.y = 0
                loc = rig.matrix_world.inverted() @ Vector((t_torso0.x + d.x*k, t_torso0.y + d.y*k, t_floor + (t_torso0.z - t_floor) * (hp.z / s_hiph)))
            Mn = (TW.inverted() @ R).to_4x4(); Mn.translation = loc
            pb.matrix = Mn
            bpy.context.view_layer.update()
        for s, t, kind in MAP:
            pb = rig.pose.bones[t]
            if pb.rotation_mode == 'QUATERNION': pb.keyframe_insert('rotation_quaternion', frame=out_f)
            else: pb.keyframe_insert('rotation_euler', frame=out_f)
            if kind == 'root': pb.keyframe_insert('location', frame=out_f)
        out_f += 1
    bpy.data.objects.remove(src, do_unlink=True)
    return out_f - 1

def fix_feet(rig, f0, f1):
    """CMU foot/toe rest roll & pitch differ from ours: feet stand tilted on their edge.
    Estimate a constant per-foot correction from stance frames (foot lowest) that makes the
    stance foot match our flat rest foot (keeping yaw), then blend toward fully flat while planted."""
    sc = bpy.context.scene; W = rig.matrix_world.to_3x3()
    rest = {}
    saved = {pb.name: pb.matrix_basis.copy() for pb in rig.pose.bones}
    for pb in rig.pose.bones: pb.matrix_basis.identity()
    bpy.context.view_layer.update()
    for sd in 'LR':
        for b in (f'DEF-foot.{sd}', f'DEF-toe.{sd}'):
            rest[b] = (W @ rig.pose.bones[b].matrix.to_3x3()).copy()
    for pb in rig.pose.bones: pb.matrix_basis = saved[pb.name]
    bpy.context.view_layer.update()
    def yaw_of(M):
        y = M.col[1]; return math.atan2(y.x, -y.y)
    def flat(b, M):
        return Matrix.Rotation(yaw_of(M), 3, 'Z') @ rest[b]
    for sd in 'LR':
        for part in ('foot', 'toe'):
            b = f'DEF-{part}.{sd}'; ctl = rig.pose.bones[f'{part}_fk.{sd}']
            rec = []
            for f in range(f0, f1 + 1):
                sc.frame_set(f)
                M = W @ rig.pose.bones[b].matrix.to_3x3()
                z = (rig.matrix_world @ rig.pose.bones[f'DEF-toe.{sd}'].head).z
                rec.append((f, M.copy(), z))
            zs = sorted(r_[2] for r_ in rec); zcut = zs[int(len(zs) * 0.35)]
            qs = [(M.inverted() @ flat(b, M)).to_quaternion() for f, M, z in rec if z <= zcut]
            q0 = qs[0]; acc = Quaternion((0, 0, 0, 0))
            for q in qs:
                if q.dot(q0) < 0: q = -q
                acc = Quaternion([a + c for a, c in zip(acc, q)])
            Cq = acc.normalized().to_matrix()
            zmin, zr = zs[0], max(zs[-1] - zs[0], 1e-4)
            for f, M, z in rec:
                sc.frame_set(f)
                Mc = M @ Cq
                # planted weight: 1 near the floor, 0 once lifted ~4 cm
                w = max(0.0, min(1.0, 1 - (z - zmin) / 0.04))
                if w > 0:
                    Mc = Mc.to_quaternion().slerp(flat(b, Mc).to_quaternion(), w * 0.85).to_matrix()
                cw = rig.matrix_world.to_3x3().inverted() @ Mc
                Cm = ctl.matrix.copy(); loc = Cm.translation.copy()
                # control and DEF bone share orientation in Rigify FK chains
                N = cw.to_4x4(); N.translation = loc; ctl.matrix = N
                bpy.context.view_layer.update()
                if ctl.rotation_mode == 'QUATERNION': ctl.keyframe_insert('rotation_quaternion', frame=f)
                else: ctl.keyframe_insert('rotation_euler', frame=f)

def ground(rig, f0, f1, smooth=2):
    """Shift torso so the lowest shoe-sole vertex sits on the floor each frame (removes float/sink)."""
    sc = bpy.context.scene
    ms = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == rig]
    idx = {o.name: [v.index for v in o.data.vertices if (o.matrix_world @ v.co).z < 0.03] for o in ms}
    ms = [o for o in ms if idx[o.name]]
    off = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get(); z = 9
        for o in ms:
            e = o.evaluated_get(dg); m = e.to_mesh(); mw = o.matrix_world
            z = min(z, min((mw @ m.vertices[i].co).z for i in idx[o.name])); e.to_mesh_clear()
        off.append(z)
    sm = [sum(off[max(0, i-smooth):i+smooth+1]) / len(off[max(0, i-smooth):i+smooth+1]) for i in range(len(off))]
    tb = rig.pose.bones['torso']
    for i, f in enumerate(range(f0, f1 + 1)):
        sc.frame_set(f)
        M = tb.matrix.copy(); M.translation.z -= sm[i]
        tb.matrix = M
        tb.keyframe_insert('location', frame=f)
    return off
