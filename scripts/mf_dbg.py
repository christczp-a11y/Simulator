"""Debug variants of the Mantaflow stepping set-up. blender -b --factory-startup -P mf_dbg.py -- <out_dir>"""
import bpy, sys, os, json
import numpy as np
out = sys.argv[sys.argv.index("--") + 1]; os.makedirs(out, exist_ok=True)
res = {}
T4 = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], np.float32) / np.sqrt(3.0) * 0.5
for name, f0, emitter, ftype, vgroup, pre in (("a_start1_sphere", 1, "sphere", "SMOKE", False, False), ("b_start158_sphere", 158, "sphere", "SMOKE", False, False),
                                             ("c_start158_tets_smoke", 158, "tets", "SMOKE", False, False), ("d_tets_fire", 158, "tets", "FIRE", False, False),
                                             ("e_tets_fire_vg", 158, "tets", "FIRE", True, False), ("f_start158_sphere_preroll", 158, "sphere", "SMOKE", False, True)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.fps = 30; sc.frame_start = f0; sc.frame_end = f0 + 9
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 10)); dom = bpy.context.object; dom.scale = (60, 20, 20)
    m = dom.modifiers.new("fluid", 'FLUID'); m.fluid_type = 'DOMAIN'; ds = m.domain_settings
    ds.domain_type = 'GAS'; ds.resolution_max = 96; ds.time_scale = 0.1
    ds.cache_type = 'REPLAY'; ds.cache_data_format = 'OPENVDB'; cdir = os.path.join(out, name); ds.cache_directory = cdir
    ds.cache_frame_start = f0; ds.cache_frame_end = f0 + 9
    if emitter == "sphere":
        bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=2, location=(-20, 0, 10)); em = bpy.context.object
    else:
        cen = np.random.default_rng(1).uniform(-1, 1, (200, 3)) * [3, 3, 3] + [-20, 0, 10]
        base = (np.arange(200) * 4)[:, None]
        faces = np.concatenate([base + np.array(t)[None] for t in ((1, 3, 2), (0, 2, 3), (0, 3, 1), (0, 1, 2))]).tolist()
        me = bpy.data.meshes.new("fuel"); me.from_pydata((cen[:, None] + T4[None]).reshape(-1, 3).tolist(), [], faces); me.update()
        em = bpy.data.objects.new("fuel", me); sc.collection.objects.link(em)
    if vgroup:
        vg = em.vertex_groups.new(name="burn"); vg.add(list(range(len(em.data.vertices))), 1.0, 'REPLACE')
    fm = em.modifiers.new("fluid", 'FLUID'); fm.fluid_type = 'FLOW'; fs = fm.flow_settings
    fs.flow_type = ftype; fs.flow_behavior = 'INFLOW'; fs.use_initial_velocity = True
    if emitter == "tets": fs.volume_density = 1.0; fs.surface_distance = 1.0
    if vgroup: fs.density_vertex_group = "burn"
    r = {}
    if pre: sc.frame_set(f0 - 1)
    for f in range(f0, f0 + 10):
        if emitter == "sphere": em.location = (-20 + (f - f0), 0, 10)
        else:
            me.vertices.foreach_set("co", ((cen + [f - f0, 0, 0])[:, None] + T4[None]).reshape(-1).astype(np.float32)); me.update()
        sc.frame_set(f)
        dse = dom.evaluated_get(bpy.context.evaluated_depsgraph_get()).modifiers["fluid"].domain_settings
        try:
            r[f] = [round(float(np.array(dse.density_grid, np.float32).sum()), 2), round(float(np.array(dse.flame_grid, np.float32).sum()), 2), round(float(np.abs(np.array(dse.velocity_grid, np.float32)).max()), 2)]
        except Exception as e: r[f] = repr(e)
    nfiles = sum(len(fl) for _, _, fl in os.walk(cdir))
    res[name] = dict(grids=r, files=nfiles)
    print("DBG", name, json.dumps(res[name]), flush=True)
json.dump(res, open(os.path.join(out, "dbg.json"), "w"), indent=1)
