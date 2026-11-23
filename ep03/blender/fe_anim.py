"""Animated FE tail coach: one mesh (frame-0 topology), one shape key per FE output frame, Geometry Nodes deletes
faces whose erosion time has passed. Scene frame -> sim time is linear: t_ms = T0 + (frame - 1) * DT."""
import numpy as np, bpy
from lib import link
import fe_import as FE

def gone_times(max_edge=0.35):
    d = FE.load(); t = d['t']; q = d['quads']; pid = d['part_id']
    X0 = d['xyz'][0][q] / 1000.0
    e0 = np.linalg.norm(X0 - np.roll(X0, 1, axis=1), axis=2).max(1)
    gone = np.full(len(q), 1e9, dtype=np.float32)
    for f in range(len(t)):
        P = d['xyz'][f][q] / 1000.0
        e = np.linalg.norm(P - np.roll(P, 1, axis=1), axis=2).max(1)
        bad = d['deleted'][f] | (e > np.maximum(max_edge, e0 * 3.0)) | (np.abs(P[:, :, 0]).max(1) > 6.0) | (P[:, :, 2].min(1) < -0.5) | (P[:, :, 2].max(1) > 8.0)
        newly = bad & (gone > 1e8)
        gone[newly] = t[max(f - 1, 0)] + 0.5 * (t[f] - t[max(f - 1, 0)]) if f > 0 else -1.0
    gone[pid == 20] = -1.0            # rigid loco boxes are never shown (real loco model is used)
    return gone

def build(mats, T0, DT, nframes, name='feCoach', thick=0.004):
    d = FE.load(); t = d['t']; q = d['quads']; pid = d['part_id']
    gone = gone_times()
    keep = gone > T0 - 1e-3                      # faces already gone before the shot starts are dropped outright
    keep &= pid != 20
    qq = q[keep]; used, inv = np.unique(qq, return_inverse=True); inv = inv.reshape(qq.shape)
    X = d['xyz'][:, used, :].astype(np.float64) / 1000.0
    me = bpy.data.meshes.new(name)
    faces = [tuple(r) if r[2] != r[3] else tuple(r[:3]) for r in inv]
    me.from_pydata(X[0].tolist(), [], faces)
    slots = []
    for p_ in pid[keep]:
        m = mats.get(int(p_), mats['default'])
        if m.name not in slots: slots.append(m.name); me.materials.append(m)
    mi = np.array([slots.index(mats.get(int(p_), mats['default']).name) for p_ in pid[keep]], dtype=np.int32)
    me.polygons.foreach_set('material_index', mi)
    at = me.attributes.new('gone_t', 'FLOAT', 'FACE'); at.data.foreach_set('value', gone[keep])
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name, me); link(o)
    # shape keys for every FE frame inside [T0, T_end]
    T1 = T0 + DT * (nframes - 1)
    idx = [i for i in range(len(t)) if T0 - 10.5 <= t[i] <= T1 + 10.5]
    o.shape_key_add(name='Basis')
    keys = []
    for i in idx:
        k = o.shape_key_add(name=f't{int(round(t[i]))}'); k.data.foreach_set('co', X[i].ravel()); keys.append((i, k))
    for f in range(1, nframes + 1):
        tm = T0 + (f - 1) * DT
        for j, (i, k) in enumerate(keys):
            ti = t[i]; tp = t[keys[j - 1][0]] if j > 0 else ti - 1e9; tn = t[keys[j + 1][0]] if j + 1 < len(keys) else ti + 1e9
            if tm <= ti: w = (tm - tp) / (ti - tp) if tm > tp else 0.0
            else: w = (tn - tm) / (tn - ti) if tm < tn else 0.0
            if j == 0 and tm <= ti: w = 1.0
            if j == len(keys) - 1 and tm >= ti: w = 1.0
            k.value = max(0.0, min(1.0, w)); k.keyframe_insert('value', frame=f)
    # geometry nodes: delete faces whose gone_t < current sim time
    ng = bpy.data.node_groups.new('feErode', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    st = N.new('GeometryNodeInputSceneTime')
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY_ADD'; mul.inputs[1].default_value = DT; mul.inputs[2].default_value = T0 - DT
    L.new(st.outputs['Frame'], mul.inputs[0])
    na = N.new('GeometryNodeInputNamedAttribute'); na.data_type = 'FLOAT'; na.inputs['Name'].default_value = 'gone_t'
    cmp = N.new('FunctionNodeCompare'); cmp.data_type = 'FLOAT'; cmp.operation = 'LESS_THAN'
    L.new(na.outputs['Attribute'], cmp.inputs['A']); L.new(mul.outputs[0], cmp.inputs['B'])
    dl = N.new('GeometryNodeDeleteGeometry'); dl.domain = 'FACE'
    L.new(gi.outputs[0], dl.inputs['Geometry']); L.new(cmp.outputs['Result'], dl.inputs['Selection']); L.new(dl.outputs[0], go.inputs[0])
    gm = o.modifiers.new('erode', 'NODES'); gm.node_group = ng
    sm = o.modifiers.new('sol', 'SOLIDIFY'); sm.thickness = thick; sm.offset = 0
    return o, d, idx

def loco_track(T0, DT, nframes):
    """Per scene frame: loco front displacement (m) relative to its front at t=0."""
    d = FE.load(); t = d['t']; q = d['quads'][d['part_id'] == 20]; n = np.unique(q)
    fy = d['xyz'][:, n, 1].min(1) / 1000.0
    return [float(np.interp(T0 + (f - 1) * DT, t, fy) - fy[0]) for f in range(1, nframes + 1)]
