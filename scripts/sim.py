"""Rigid-fragment crash simulation with Blender's Bullet world. Runs with the bpy module
(cloud) or inside Blender. Output: per-frame fragment transforms + everything needed
to rebuild particle positions."""
import sys, json, time
import numpy as np
import bpy
from mathutils import Matrix, Vector, Quaternion
from scipy.spatial import ConvexHull

CFG = dict(
    fps=240, frames=600, substeps=8, iters=40,
    speed=62.0, path_deg=-13.0, pitch_deg=-5.0, roll_deg=11.0, yaw_deg=3.0,
    clearance=1.2,             # lowest point height above ground at frame 1
    link_impulse=1.6,          # breaking impulse per point-link (N*s per substep)
    friction=0.75, restitution=0.02, lin_damp=0.02, ang_damp=0.05,
    kin_frames=3, seed=1,
)


def rot_xyz(roll, pitch, yaw):
    # roll about x (right wing down positive), pitch about y (nose up positive), yaw about z
    return (Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(-pitch, 3, 'Y') @ Matrix.Rotation(roll, 3, 'X'))


def main(cfg, plane_npz, frac_npz, out_npz):
    P = np.load(plane_npz); F = np.load(frac_npz)
    pos = P["pos"].astype(np.float64); nrm = P["nrm"].astype(np.float64)
    frag = F["frag"]; nf = int(frag.max()) + 1; pmass = F["pmass"]
    rng = np.random.default_rng(cfg["seed"])

    R0 = np.array(rot_xyz(np.radians(cfg["roll_deg"]), np.radians(cfg["pitch_deg"]), np.radians(cfg["yaw_deg"])))
    wpos = pos @ R0.T; wnrm = nrm @ R0.T
    wpos[:, 2] += cfg["clearance"] - wpos[:, 2].min()
    g = np.radians(cfg["path_deg"])
    vel = np.array([np.cos(g), 0.0, np.sin(g)]) * cfg["speed"]
    anchor = F["link_anchor"] @ R0.T; anchor[:, 2] += wpos[:, 2].min() - cfg["clearance"] + 0  # placeholder, fixed below
    shift = wpos[0] - pos[0] @ R0.T
    anchor = F["link_anchor"] @ R0.T + shift

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = cfg["fps"]; sc.frame_start = 1; sc.frame_end = cfg["frames"]
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    rbw.collection = bpy.data.collections.new("RB"); rbw.constraints = bpy.data.collections.new("RBC")
    rbw.substeps_per_frame = cfg["substeps"]; rbw.solver_iterations = cfg["iters"]; rbw.time_scale = 1.0
    rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = cfg["frames"]
    sc.gravity = (0, 0, -9.81)

    # ground
    me = bpy.data.meshes.new("ground"); s = 1500.0
    me.from_pydata([(-s, -s, -3), (s, -s, -3), (s, s, -3), (-s, s, -3), (-s, -s, 3), (s, -s, 3), (s, s, 3), (-s, s, 3)], [],
                   [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])
    gr = bpy.data.objects.new("ground", me); gr.location = (0, 0, -3); sc.collection.objects.link(gr); rbw.collection.objects.link(gr)
    gr.rigid_body.type = 'PASSIVE'; gr.rigid_body.collision_shape = 'BOX'
    gr.rigid_body.friction = cfg["friction"]; gr.rigid_body.restitution = cfg["restitution"]
    gr.rigid_body.collision_margin = 0.0

    objs = []; cen = np.zeros((nf, 3)); fmass = np.bincount(frag, pmass, nf)
    order = np.argsort(frag, kind="stable"); starts = np.searchsorted(frag[order], np.arange(nf + 1))
    for i in range(nf):
        idx = order[starts[i]:starts[i + 1]]
        p = wpos[idx]; c = np.average(p, axis=0, weights=pmass[idx]); cen[i] = c
        q = p - c
        if len(q) > 90:
            q = q[rng.choice(len(q), 90, replace=False)]
        q = q * 0.94
        # thin sheets need a little thickness: offset along the smallest principal axis
        w, V = np.linalg.eigh(np.cov(q.T))
        if np.sqrt(max(w[0], 0)) < 0.012:
            thick = np.concatenate([q + V[:, 0] * 0.015, q - V[:, 0] * 0.015])
        else:
            thick = q
        try:
            h = ConvexHull(thick)
            vmap = {v: k for k, v in enumerate(h.vertices)}
            verts = thick[h.vertices]; faces = [[vmap[v] for v in s3] for s3 in h.simplices]
        except Exception:
            verts = thick; faces = []
        me = bpy.data.meshes.new(f"f{i}"); me.from_pydata([tuple(v) for v in verts], [], faces)
        ob = bpy.data.objects.new(f"f{i}", me); ob.location = c; ob.rotation_mode = 'QUATERNION'
        sc.collection.objects.link(ob); rbw.collection.objects.link(ob)
        rb = ob.rigid_body
        rb.type = 'ACTIVE'; rb.collision_shape = 'CONVEX_HULL'; rb.mass = float(max(fmass[i], 0.05))
        rb.friction = cfg["friction"]; rb.restitution = cfg["restitution"]; rb.collision_margin = 0.004
        rb.use_deactivation = False; rb.linear_damping = cfg["lin_damp"]; rb.angular_damping = cfg["ang_damp"]
        objs.append(ob)
    # initial velocity via kinematic lead-in
    kf = cfg["kin_frames"]
    for i, ob in enumerate(objs):
        for f in (1, kf):
            ob.location = cen[i] + vel * (f - 1) / cfg["fps"]
            ob.keyframe_insert("location", frame=f)
        ob.rigid_body.kinematic = True; ob.rigid_body.keyframe_insert("kinematic", frame=kf)
        ob.rigid_body.kinematic = False; ob.rigid_body.keyframe_insert("kinematic", frame=kf + 1)
    # glue
    la, lb, ln, ls, lcross = F["link_a"], F["link_b"], F["link_n"], F["link_s"], F["link_cross"]
    for k in range(len(la)):
        e = bpy.data.objects.new(f"c{k}", None); e.location = anchor[k]
        sc.collection.objects.link(e); rbw.constraints.objects.link(e)
        c = e.rigid_body_constraint
        c.type = 'FIXED'; c.object1 = objs[la[k]]; c.object2 = objs[lb[k]]
        c.use_breaking = True; c.breaking_threshold = float(cfg["link_impulse"] * ls[k] * ln[k])
        c.disable_collisions = bool(lcross[k])
        c.use_override_solver_iterations = False
        # constraints must follow the kinematic lead-in too
        for f in (1, kf):
            e.location = anchor[k] + vel * (f - 1) / cfg["fps"]; e.keyframe_insert("location", frame=f)
    for k in range(len(F["nc_a"])):
        e = bpy.data.objects.new(f"n{k}", None); e.location = cen[F["nc_a"][k]]
        sc.collection.objects.link(e); rbw.constraints.objects.link(e)
        c = e.rigid_body_constraint
        c.type = 'POINT'; c.object1 = objs[F["nc_a"][k]]; c.object2 = objs[F["nc_b"][k]]
        c.use_breaking = True; c.breaking_threshold = 1e-6; c.disable_collisions = True
    print("no-collide pairs", len(F["nc_a"]))
    print("built", nf, "bodies", len(la), "constraints", flush=True)

    T = cfg["frames"]
    loc = np.zeros((T, nf, 3), np.float32); quat = np.zeros((T, nf, 4), np.float32)
    t0 = time.time()
    for f in range(1, T + 1):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for i, ob in enumerate(objs):
            m = ob.evaluated_get(dg).matrix_world
            loc[f - 1, i] = m.translation; q = m.to_quaternion(); quat[f - 1, i] = (q.w, q.x, q.y, q.z)
        if f % 25 == 0:
            v = (loc[f - 1] - loc[f - 2]) * cfg["fps"]
            print(f"frame {f} t={time.time()-t0:.0f}s  mean|v|={np.linalg.norm(v,axis=1).mean():.1f}  zmin={loc[f-1,:,2].min():.2f} zmax={loc[f-1,:,2].max():.2f}", flush=True)
    # particle coordinates in fragment frames (rest pose)
    local = wpos - cen[frag]
    np.savez_compressed(out_npz, loc=loc, quat=quat, cen0=cen.astype(np.float32), local=local.astype(np.float32),
                        nrm0=wnrm.astype(np.float32), frag=frag.astype(np.int32), fmass=fmass.astype(np.float32),
                        part=P["part"], anchor=anchor.astype(np.float32), link_a=la, link_b=lb, link_n=ln,
                        vel=vel, cfg=json.dumps(cfg))
    print("saved", out_npz, flush=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    cfg = dict(CFG)
    if len(args) > 3:
        cfg.update(json.loads(args[3]))
    main(cfg, args[0], args[1], args[2])
