"""Calibration for Mantaflow slow motion: how far does gas emitted from a moving object travel per frame, relative to the
emitter's own displacement per frame, at different domain time scales?  blender -b --factory-startup -P mf_calib.py -- <out_dir>"""
import bpy, sys, os, json, time
import numpy as np
out = sys.argv[sys.argv.index("--") + 1]; os.makedirs(out, exist_ok=True)
res = {}
for ts in (1.0, 0.1):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.fps = 30; sc.frame_start = 1; sc.frame_end = 14
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 10)); dom = bpy.context.object; dom.scale = (60, 20, 20)
    m = dom.modifiers.new("fluid", 'FLUID'); m.fluid_type = 'DOMAIN'; ds = m.domain_settings
    ds.domain_type = 'GAS'; ds.resolution_max = 96; ds.time_scale = ts; ds.alpha = 0.0; ds.beta = 0.0; ds.vorticity = 0.0
    ds.cache_type = 'REPLAY'; ds.cache_data_format = 'OPENVDB'; cdir = os.path.join(out, f"ts{ts}"); ds.cache_directory = cdir
    ds.cache_frame_start = 1; ds.cache_frame_end = 14; ds.use_adaptive_timesteps = True
    bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=2, location=(-20, 0, 10)); em = bpy.context.object
    fm = em.modifiers.new("fluid", 'FLUID'); fm.fluid_type = 'FLOW'; fs = fm.flow_settings
    fs.flow_type = 'SMOKE'; fs.flow_behavior = 'INFLOW'; fs.use_initial_velocity = True; fs.velocity_factor = 1.0; fs.subframes = 0
    step = 1.0                                             # emitter moves 1 m per frame
    for f in range(1, 15):
        em.location = (-20 + step * (f - 1), 0, 10); em.keyframe_insert("location", frame=f)
        fs.use_inflow = f <= 4; fs.keyframe_insert("use_inflow", frame=f)
    for fc in em.animation_data.action.fcurves if hasattr(em.animation_data.action, "fcurves") else []:
        for k in fc.keyframe_points: k.interpolation = 'LINEAR'
    cx = {}
    t0 = time.time()
    for f in range(1, 15):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get(); dom_e = dom.evaluated_get(dg)
        dse = dom_e.modifiers["fluid"].domain_settings
        try:
            g = np.array(dse.density_grid, dtype=np.float32); r = tuple(dse.domain_resolution)
            if len(g) == r[0] * r[1] * r[2] and g.sum() > 0:
                g = g.reshape(r[2], r[1], r[0]); w = g.sum((0, 1)); xs = (np.arange(r[0]) + 0.5) / r[0] * 60 - 30
                cx[f] = float((w * xs).sum() / w.sum())
        except Exception as e:
            cx[f] = "err " + str(e)
    files = []
    for root, _, fl in os.walk(cdir): files += [os.path.join(os.path.relpath(root, cdir), x) for x in fl][:6]
    res[str(ts)] = dict(centroid_x=cx, seconds=time.time() - t0, files=files[:8])
    print("CALIB", ts, json.dumps(res[str(ts)]), flush=True)
json.dump(res, open(os.path.join(out, "calib.json"), "w"), indent=1)
