"""Import OpenCourant FE result (fe/frames.npz, mm, Y along track, coach rear end at Y=0) as Blender meshes.
Coach shells -> one mesh per material group; deleted (eroded) elements removed; stretched/outlier elements dropped."""
import numpy as np, bpy, bmesh
from lib import link
D = None
def load():
    global D
    if D is None:
        d = np.load('/home/claude/ep03/fe/frames.npz'); D = {k: d[k] for k in d.files}
    return D

def frame_at(ms):
    d = load(); return int(np.argmin(np.abs(d['t'] - ms)))

def loco_front(ms):
    d = load(); f = frame_at(ms); q = d['quads'][d['part_id'] == 20]
    return float(d['xyz'][f, np.unique(q), 1].min()) / 1000.0

def coach_mesh(ms, mats, name='feCoach', max_edge=0.35, thick=0.004):
    """mats: dict part_id -> material (missing parts use mats['default'])."""
    d = load(); f = frame_at(ms)
    xyz = d['xyz'][f].astype(np.float64) / 1000.0
    q = d['quads']; pid = d['part_id']; dele = d['deleted'][f]
    keep = (pid != 20) & ~dele
    P = xyz[q]                                   # (E,4,3)
    e = np.linalg.norm(P - np.roll(P, 1, axis=1), axis=2).max(1)
    e0 = np.linalg.norm((d['xyz'][0][q] - np.roll(d['xyz'][0][q], 1, axis=1)) / 1000.0, axis=2).max(1)
    keep &= (e < np.maximum(max_edge, e0 * 3.0))
    keep &= np.abs(P[:, :, 0]).max(1) < 6.0
    keep &= (P[:, :, 2].min(1) > -0.5) & (P[:, :, 2].max(1) < 8.0)
    out = []
    groups = {}
    for p_ in np.unique(pid[keep]):
        m = mats.get(int(p_), mats['default']); groups.setdefault(m.name, (m, []))[1].append(p_)
    for mname, (m, plist) in groups.items():
        sel = keep & np.isin(pid, plist)
        qq = q[sel]; used, inv = np.unique(qq, return_inverse=True); inv = inv.reshape(qq.shape)
        me = bpy.data.meshes.new(name + '_' + mname)
        faces = [tuple(r) if r[2] != r[3] else tuple(r[:3]) for r in inv]
        me.from_pydata(xyz[used].tolist(), [], faces)
        me.validate(); me.update()
        o = bpy.data.objects.new(name + '_' + mname, me); link(o); me.materials.append(m)
        for poly in me.polygons: poly.use_smooth = True
        sm = o.modifiers.new('sol', 'SOLIDIFY'); sm.thickness = thick; sm.offset = 0
        o.modifiers.new('wn', 'WEIGHTED_NORMAL')
        out.append(o)
    return out, int(keep.sum()), int((dele & (pid != 20)).sum())
