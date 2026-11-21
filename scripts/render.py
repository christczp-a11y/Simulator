"""Headless Blender renderer. blender -b --factory-startup -P render.py -- [options]
Runs the particle FX sequentially along the slow-motion timeline and renders the requested frames."""
import bpy, sys, os, time, argparse
import numpy as np
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fx, cam

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=os.path.join(HERE, "..", "data"))
ap.add_argument("--out", default=os.path.join(HERE, "..", "renders", "test"))
ap.add_argument("--frames", default="all")          # "all", "a-b" or "1,5,9"
ap.add_argument("--n", type=int, default=450)
ap.add_argument("--res", default="1920x1080")
ap.add_argument("--samples", type=int, default=64)
ap.add_argument("--quality", type=float, default=1.0)
ap.add_argument("--device", default="OPTIX")
ap.add_argument("--fstop", type=float, default=0.45)
ap.add_argument("--exposure", type=float, default=0.0)
ap.add_argument("--bloom", type=float, default=0.35)
ap.add_argument("--compdev", default="GPU")
ap.add_argument("--skip_existing", type=int, default=1)
ap.add_argument("--scheme", default="design")       # design | livery | v1  (see palette.py)
ap.add_argument("--grid_h", type=float, default=0.5)
ap.add_argument("--firelight", type=float, default=1.0)
ap.add_argument("--tag", default="frame")
ap.add_argument("--view", default="Filmic")
ap.add_argument("--look", default="Medium High Contrast")
ap.add_argument("--fire", type=int, default=1)       # 0: airframe only, no fuel fire
ap.add_argument("--mfire", default="")              # folder of an mfire.py run (Mantaflow fire); empty = built-in coarse gas
ap.add_argument("--vol", type=float, default=0.0)    # >0: also render the Mantaflow flame as a real volume, this is its emission gain
ap.add_argument("--volsmoke", type=float, default=2.0)   # smoke density multiplier of that volume
ap.add_argument("--voldens", type=float, default=1.5)    # optical density of the flame itself (per m): makes the fireball read as a surface, not a glow
ap.add_argument("--pfire", type=float, default=1.0)  # brightness multiplier of the fire particles
ap.add_argument("--mfdens", type=float, default=800.0)   # fire particles per m3 of flame (at quality 1)
ap.add_argument("--mpm", default="")                # folder of an mpm.py run; empty = rigid-fragment sim
ap.add_argument("--exr", type=int, default=0)        # 1: also keep a linear EXR next to each PNG
A = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
W, H = [int(x) for x in A.res.split("x")]
os.makedirs(A.out, exist_ok=True)
if A.frames == "all": WANT = list(range(A.n))
elif "-" in A.frames: a, b = A.frames.split("-"); WANT = list(range(int(a), int(b) + 1))
else: WANT = [int(x) for x in A.frames.split(",")]


def log(*a):
    print("[render]", *a, flush=True)


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    if A.device != "CPU":
        try:
            pr = bpy.context.preferences.addons['cycles'].preferences
            pr.compute_device_type = A.device; pr.refresh_devices()
            for d in pr.devices: d.use = (d.type != 'CPU')
            sc.cycles.device = 'GPU'
            log("devices", [(d.name, d.type, d.use) for d in pr.devices])
        except Exception as e:
            log("GPU setup failed", e)
    cy = sc.cycles
    cy.samples = A.samples; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.04
    cy.use_denoising = True
    try: cy.denoiser = 'OPTIX' if A.device == "OPTIX" else 'OPENIMAGEDENOISE'
    except Exception as e: log("denoiser", e)
    cy.max_bounces = 2; cy.diffuse_bounces = 1; cy.glossy_bounces = 1; cy.transmission_bounces = 0; cy.volume_bounces = 0
    cy.transparent_max_bounces = 96                     # additive fire particles are emission + transparency
    cy.caustics_reflective = False; cy.caustics_refractive = False
    sc.render.resolution_x = W; sc.render.resolution_y = H; sc.render.resolution_percentage = 100; sc.render.fps = 30
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    sc.render.use_persistent_data = False
    sc.view_settings.view_transform = A.view
    try: sc.view_settings.look = A.look
    except Exception as e: log("look", e)
    sc.view_settings.exposure = A.exposure
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg: bg.inputs[0].default_value = (0.0025, 0.004, 0.009, 1); bg.inputs[1].default_value = 1.0
    # camera
    cd = bpy.data.cameras.new("cam"); co = bpy.data.objects.new("cam", cd); sc.collection.objects.link(co); sc.camera = co
    cd.sensor_width = 36; cd.clip_start = 0.1; cd.clip_end = 2000; cd.dof.use_dof = True; cd.dof.aperture_fstop = A.fstop; cd.dof.aperture_blades = 0
    # lights: cool key from the camera side, warm fire light driven per frame
    def sun(name, direction, energy, color):
        ld = bpy.data.lights.new(name, 'SUN'); ld.energy = energy; ld.color = color; ld.angle = 0.05
        lo = bpy.data.objects.new(name, ld); sc.collection.objects.link(lo)
        lo.rotation_mode = 'QUATERNION'; lo.rotation_quaternion = Vector(direction).normalized().to_track_quat('-Z', 'Y')
        return lo
    sun("key", (0.35, 0.75, -0.55), 1.3, (0.75, 0.86, 1.0))
    sun("rim", (-0.6, -0.5, -0.35), 0.9, (0.55, 0.7, 1.0))
    fd = bpy.data.lights.new("fire", 'POINT'); fd.color = (1.0, 0.45, 0.12); fd.shadow_soft_size = 2.5; fd.energy = 0
    fo = bpy.data.objects.new("fire", fd); sc.collection.objects.link(fo)
    # material: per-point colour drives both diffuse and emission
    m = bpy.data.materials.new("pts"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); pb = nt.nodes.new("ShaderNodeBsdfPrincipled")
    ac = nt.nodes.new("ShaderNodeAttribute"); ac.attribute_name = "col"
    ae = nt.nodes.new("ShaderNodeAttribute"); ae.attribute_name = "emit"
    aa = nt.nodes.new("ShaderNodeAttribute"); aa.attribute_name = "alb"
    vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = 'SCALE'
    nt.links.new(ac.outputs["Color"], vm.inputs[0]); nt.links.new(aa.outputs["Fac"], vm.inputs["Scale"])
    nt.links.new(vm.outputs["Vector"], pb.inputs["Base Color"]); nt.links.new(ac.outputs["Color"], pb.inputs["Emission Color"])
    nt.links.new(ae.outputs["Fac"], pb.inputs["Emission Strength"]); pb.inputs["Roughness"].default_value = 0.55
    nt.links.new(pb.outputs["BSDF"], out.inputs["Surface"])
    try: m.cycles.emission_sampling = 'NONE'
    except Exception as e: log("emission_sampling", e)
    # point object: mesh vertices -> point cloud via geometry nodes
    me = bpy.data.meshes.new("pts"); ob = bpy.data.objects.new("pts", me); sc.collection.objects.link(ob)
    ng = bpy.data.node_groups.new("pts", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nin = ng.nodes.new("NodeGroupInput"); nout = ng.nodes.new("NodeGroupOutput")
    m2p = ng.nodes.new("GeometryNodeMeshToPoints"); na = ng.nodes.new("GeometryNodeInputNamedAttribute")
    na.data_type = 'FLOAT'; na.inputs["Name"].default_value = "rad"
    sm = ng.nodes.new("GeometryNodeSetMaterial"); sm.inputs["Material"].default_value = m
    ng.links.new(nin.outputs[0], m2p.inputs["Mesh"]); ng.links.new(na.outputs[0], m2p.inputs["Radius"])
    ng.links.new(m2p.outputs["Points"], sm.inputs["Geometry"]); ng.links.new(sm.outputs["Geometry"], nout.inputs[0])
    md = ob.modifiers.new("pts", 'NODES'); md.node_group = ng
    # additive material for fire / exhaust: light only, soft-edged, never hides what is behind it
    m2 = bpy.data.materials.new("glow"); m2.use_nodes = True; nt = m2.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader"); ac = nt.nodes.new("ShaderNodeAttribute"); ac.attribute_name = "col"
    ae = nt.nodes.new("ShaderNodeAttribute"); ae.attribute_name = "emit"
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.5
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    sq = nt.nodes.new("ShaderNodeMath"); sq.operation = 'POWER'; sq.inputs[1].default_value = 1.5
    mu = nt.nodes.new("ShaderNodeMath"); mu.operation = 'MULTIPLY'
    nt.links.new(lw.outputs["Facing"], inv.inputs[1]); nt.links.new(inv.outputs[0], sq.inputs[0])
    nt.links.new(sq.outputs[0], mu.inputs[0]); nt.links.new(ae.outputs["Fac"], mu.inputs[1])
    nt.links.new(ac.outputs["Color"], em.inputs["Color"]); nt.links.new(mu.outputs[0], em.inputs["Strength"])
    nt.links.new(em.outputs[0], add.inputs[0]); nt.links.new(tr.outputs[0], add.inputs[1]); nt.links.new(add.outputs[0], out.inputs["Surface"])
    try: m2.cycles.emission_sampling = 'NONE'
    except Exception as e: log("emission_sampling", e)
    ng2 = ng.copy(); ng2.name = "glow"
    for nd in ng2.nodes:
        if nd.bl_idname == "GeometryNodeSetMaterial": nd.inputs["Material"].default_value = m2
    me2 = bpy.data.meshes.new("glow"); ob2 = bpy.data.objects.new("glow", me2); sc.collection.objects.link(ob2)
    md2 = ob2.modifiers.new("glow", 'NODES'); md2.node_group = ng2
    ob2.visible_shadow = False; ob2.visible_diffuse = False; ob2.visible_glossy = False
    # compositor bloom
    try:
        if A.bloom <= 0: raise RuntimeError("bloom off")
        sc.render.compositor_device = A.compdev
        ct = bpy.data.node_groups.new("comp", "CompositorNodeTree"); sc.compositing_node_group = ct
        ct.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        rl = ct.nodes.new("CompositorNodeRLayers"); gl = ct.nodes.new("CompositorNodeGlare"); go = ct.nodes.new("NodeGroupOutput")
        gl.inputs["Type"].default_value = 'Bloom'; gl.inputs["Quality"].default_value = 'High'
        gl.inputs["Threshold"].default_value = 1.0; gl.inputs["Strength"].default_value = A.bloom; gl.inputs["Size"].default_value = 0.5
        ct.links.new(rl.outputs["Image"], gl.inputs["Image"]); ct.links.new(gl.outputs["Image"], go.inputs[0])
    except Exception as e:
        log("compositor setup failed:", repr(e))
    return sc, co, ob, ob2, fo


def setup_volume(sc):
    """Mantaflow cache as a volume object: emission from the 'flame' grid, thin soot from 'density'"""
    import json
    M = json.load(open(os.path.join(A.mfire, "meta.json"))); h = M["cell"]
    vol = bpy.data.volumes.new("fire"); vob = bpy.data.objects.new("fire", vol); sc.collection.objects.link(vob)
    vob.location = tuple(np.array(M["lo"]) + 0.5 * h)
    m = bpy.data.materials.new("firevol"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    af = nt.nodes.new("ShaderNodeAttribute"); af.attribute_name = "flame"
    cr = nt.nodes.new("ShaderNodeValToRGB"); e = cr.color_ramp.elements
    e[0].position = 0.0; e[0].color = (0.0, 0.0, 0.0, 1); e[1].position = 1.0; e[1].color = (1.0, 0.62, 0.18, 1)
    for pos, col in ((0.08, (0.30, 0.015, 0.0, 1)), (0.35, (0.9, 0.10, 0.005, 1)), (0.7, (1.0, 0.30, 0.03, 1))):
        k = e.new(pos); k.color = col
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.6
    mu = nt.nodes.new("ShaderNodeMath"); mu.operation = 'MULTIPLY'; mu.inputs[1].default_value = A.vol
    nt.links.new(af.outputs["Fac"], cr.inputs["Fac"]); nt.links.new(af.outputs["Fac"], pw.inputs[0]); nt.links.new(pw.outputs[0], mu.inputs[0])
    nt.links.new(cr.outputs["Color"], pv.inputs["Emission Color"]); nt.links.new(mu.outputs[0], pv.inputs["Emission Strength"])
    # extinction = flame * voldens + smoke * volsmoke: an optically thick flame shows its surface structure instead of
    # adding up through its whole depth into a flat white disc
    ad = nt.nodes.new("ShaderNodeAttribute"); ad.attribute_name = "density"
    m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = 'MULTIPLY'; m1.inputs[1].default_value = A.voldens
    m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = 'MULTIPLY'; m2.inputs[1].default_value = A.volsmoke
    sm = nt.nodes.new("ShaderNodeMath"); sm.operation = 'ADD'
    nt.links.new(af.outputs["Fac"], m1.inputs[0]); nt.links.new(ad.outputs["Fac"], m2.inputs[0])
    nt.links.new(m1.outputs[0], sm.inputs[0]); nt.links.new(m2.outputs[0], sm.inputs[1]); nt.links.new(sm.outputs[0], pv.inputs["Density"])
    pv.inputs["Color"].default_value = (0.02, 0.018, 0.02, 1)
    try: pv.inputs["Density Attribute"].default_value = ""; pv.inputs["Blackbody Intensity"].default_value = 0.0
    except Exception as ex: log("volume inputs", ex)
    nt.links.new(pv.outputs["Volume"], out.inputs["Volume"]); vol.materials.append(m)
    return vob


def set_points(ob, pos, rgb, emit, rad, alb):
    n = len(pos); me = bpy.data.meshes.new("pts")
    me.vertices.add(n); me.vertices.foreach_set("co", np.ascontiguousarray(pos, np.float32).ravel())
    a = me.attributes.new("col", 'FLOAT_COLOR', 'POINT'); c = np.ones((n, 4), np.float32); c[:, :3] = rgb; a.data.foreach_set("color", c.ravel())
    a = me.attributes.new("emit", 'FLOAT', 'POINT'); a.data.foreach_set("value", np.ascontiguousarray(emit, np.float32))
    a = me.attributes.new("rad", 'FLOAT', 'POINT'); a.data.foreach_set("value", np.ascontiguousarray(rad, np.float32))
    a = me.attributes.new("alb", 'FLOAT', 'POINT'); a.data.foreach_set("value", np.ascontiguousarray(alb, np.float32))
    old = ob.data; ob.data = me; bpy.data.meshes.remove(old)


def main():
    t0 = time.time()
    sc, co, ob, ob2, fo = setup()
    tl = fx.timeline(A.n)
    X = fx.FX(os.path.join(A.data, "sim.npz"), os.path.join(A.data, "pre.npz"), quality=A.quality, scheme=A.scheme, grid_h=A.grid_h, mpm=(A.mpm or None), fire=bool(A.fire),
              mfire=(A.mfire or None), tl=tl, mf_density=A.mfdens)
    vob = setup_volume(sc) if (A.mfire and A.vol > 0) else None
    focus = np.stack([X.focus(f) for f in tl[:A.n]])
    eye, tgt, fov, dist = cam.camera_path(focus, trail=(1.5 if A.mpm else 9.0))     # the MPM wreck stays in one heap, keep it centred
    want = set(WANT); last = max(WANT)
    for i in range(A.n):
        if i > 0: X.advance(tl[i - 1], tl[i])
        if i in want:
            path = os.path.join(A.out, f"{A.tag}_{i:04d}.png")
            if A.skip_existing and os.path.exists(path):
                continue
            L = X.layers(tl[i]); pos, rgb, emit, rad, alb = fx.pack(L)
            set_points(ob, pos, rgb, emit, rad, alb)
            gp = list(fx.pack(L, True)); gp[2] = gp[2] * A.pfire; set_points(ob2, *gp)
            if vob is not None:
                vp, vh = X.fl.vol_path(int(np.clip(i, X.fl.i0, X.fl.i1))); vob.hide_render = not (i >= X.fl.i0 and os.path.exists(vp))
                if not vob.hide_render: vob.data.filepath = vp; vob.location = tuple(X.fl.lo + 0.5 * vh)
            co.location = eye[i]; co.rotation_mode = 'QUATERNION'
            co.rotation_quaternion = (Vector(tgt[i]) - Vector(eye[i])).to_track_quat('-Z', 'Y')
            co.data.lens = 18.0 / np.tan(np.radians(fov[i]) / 2); co.data.dof.focus_distance = float(dist[i])
            if "fire" in L:
                fp, _, fe, fr = L["fire"]; w = fe * fr * fr
                if w.sum() > 0:
                    c = (fp * w[:, None]).sum(0) / w.sum(); fo.location = (c[0], c[1], c[2] + 1.5)
                    fo.data.energy = float(min(2.5e3, w.sum() * 150.0) * A.firelight)
            sc.render.filepath = path
            t1 = time.time(); bpy.ops.render.render(write_still=True)
            if A.exr:
                im = bpy.data.images["Render Result"]; st = sc.render.image_settings
                st.file_format = 'OPEN_EXR'; st.color_depth = '16'; im.save_render(path[:-4] + ".exr", scene=sc); st.file_format = 'PNG'; st.color_depth = '8'
            log(f"frame {i} simf {tl[i]:.1f} points {len(pos)} render {time.time()-t1:.1f}s total {time.time()-t0:.0f}s")
        if i >= last: break
    log("done")

main()
