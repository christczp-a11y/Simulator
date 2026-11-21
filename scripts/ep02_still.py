"""Render a driver-seat framing study directly from one cached FE state (Blender -b -P)."""
import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_seq import cell_offsets


def material(name, color, metallic=0.0, roughness=0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def surface(name, color1, color2, scale, roughness):
    mat = material(name, color1, roughness=roughness)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tex = nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = 5
    coords = nodes.new("ShaderNodeTexCoord")
    links.new(coords.outputs["Object"], tex.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    for el, col in zip(ramp.color_ramp.elements, (color1, color2)):
        el.color = (*col, 1)
    links.new(tex.outputs["Fac"], ramp.inputs[0])
    bsdf = nodes.get("Principled BSDF")
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.0009
    links.new(tex.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def glass():
    mat = material("Laminated safety glass", (.84, .91, .91), roughness=.06)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Metallic"].default_value = 1
    tr = nodes.new("ShaderNodeBsdfTransparent")
    # A shell has no second interface. Use the air/glass Schlick
    # reflectance from either side; a solid's exiting-ray Fresnel would
    # turn the interior view into a mirror at the windshield rake angle.
    geom = nodes.new("ShaderNodeNewGeometry")
    dot = nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    links.new(geom.outputs["Normal"], dot.inputs[0])
    links.new(geom.outputs["Incoming"], dot.inputs[1])
    cosine = nodes.new("ShaderNodeMath")
    cosine.operation = "ABSOLUTE"
    links.new(dot.outputs["Value"], cosine.inputs[0])
    complement = nodes.new("ShaderNodeMath")
    complement.operation = "SUBTRACT"
    complement.inputs[0].default_value = 1
    links.new(cosine.outputs[0], complement.inputs[1])
    fifth = nodes.new("ShaderNodeMath")
    fifth.operation = "POWER"
    fifth.inputs[1].default_value = 5
    links.new(complement.outputs[0], fifth.inputs[0])
    fr = nodes.new("ShaderNodeMath")
    fr.operation = "MULTIPLY_ADD"
    fr.inputs[1].default_value = .9625
    fr.inputs[2].default_value = .0375
    links.new(fifth.outputs[0], fr.inputs[0])
    mix = nodes.new("ShaderNodeMixShader")
    links.new(fr.outputs[0], mix.inputs[0])
    links.new(tr.outputs[0], mix.inputs[1])
    links.new(shader.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], nodes.get("Material Output").inputs["Surface"])
    return mat


def materials():
    return dict(paint=material("Painted steel", (.105, .125, .137), .62, .30),
                roof=surface("Roof lining", (.026, .026, .027), (.065, .059, .054), 320, .91),
                plastic=surface("Moulded charcoal", (.032, .036, .037), (.064, .069, .070), 280, .52),
                seat=surface("Seat textile", (.030, .033, .034), (.088, .091, .093), 600, .9),
                rubber=material("Rubber", (.018, .019, .019), roughness=.78), glass=glass())


def finish(pid, name):
    if pid in (2000023, 2000062, 2000011, 2000325, 2000347, 2000349, 2000407, 2000452):
        return "glass"
    if "roof" in name and not any(k in name for k in ("rail", "brkt")):
        return "roof"
    if any(k in name for k in ("dash", "instrument", "trim", "panelplastic", "steeringcolm", "console")):
        return "plastic"
    if "seat" in name and any(k in name for k in ("cover", "foam", "cushion")):
        return "seat"
    if any(k in name for k in ("rubber", "tread", "tirewall", "tirebead", "seal")):
        return "rubber"
    return "paint"


def mesh_obj(name, xyz, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(xyz.tolist(), [], faces)
    mesh.update()
    if mat.name in {"Moulded charcoal", "Rubber", "Seat textile"}:
        mesh.polygons.foreach_set("use_smooth", np.ones(len(mesh.polygons), dtype=bool))
        mesh.set_sharp_from_angle(angle=np.deg2rad(40))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(mat)
    return obj


def load_car(top, frame, source, shift):
    mats = materials()
    xyz = frame["xyz"] * .001
    xyz[:, 0] += shift
    names = dict(zip(source["part_id"], source["part_name"]))
    # Rigid parts can have status=0 even at t=0 because the solver uses their
    # rigid-body master. Initial geometry is retained only for those parts.
    rigid = set(source["part_id"][source["part_mat"] == "RIGID"])
    pid = top["part_id"]
    nodes = top["cells_flat"]
    types = top["cell_types"]
    start = cell_offsets(nodes, types)
    widths = nodes[start]
    if not (np.all(widths[types == 3] == 2) and np.all(np.isin(widths[types == 5], [3, 4]))
            and np.all(widths[types == 9] == 4) and np.all(widths[types == 12] == 8)):
        raise ValueError("Unexpected topology")
    # Build shells plus the faces of active brick cells. Coincident internal
    # faces within one part are removed; an eroded neighbour exposes the face.
    brick_faces = [(0,3,2,1), (4,5,6,7), (0,1,5,4), (1,2,6,5), (2,3,7,6), (3,0,4,7)]
    skip = {2000523, 2000524}  # draw one optical skin of the three co-located windshield plies
    for part, name in names.items():
        if part in skip:
            continue
        sel = (pid == part) & (frame["active"] | (part in rigid))
        poly = []
        for ty, width in [(5, 3), (9, 4)]:
            at = start[sel & (types == ty)]
            if len(at):
                poly.extend(nodes[at[:, None] + np.arange(1, width + 1)].tolist())
        at = start[sel & (types == 12)]
        if len(at):
            bricks = nodes[at[:, None] + np.arange(1, 9)]
            surface_faces = {}
            for cols in brick_faces:
                for face in bricks[:, cols]:
                    face = tuple(dict.fromkeys(face))
                    if len(face) < 3:
                        continue
                    key = tuple(sorted(face))
                    if key in surface_faces:
                        surface_faces.pop(key)
                    else:
                        surface_faces[key] = face
            poly.extend(surface_faces.values())
        if not poly:
            continue
        idx = np.unique(np.fromiter((n for face in poly for n in face), dtype=np.int32))
        local = dict(zip(idx, range(len(idx))))
        mesh_obj(str(part) + "_" + name, xyz[idx], [tuple(local[n] for n in f) for f in poly],
                 mats[finish(part, name.lower())])
    return xyz


def box(name, center, size, mat, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(mat)
    if bevel:
        mod = ob.modifiers.new("Edge radius", "BEVEL")
        mod.width, mod.segments = bevel, 3


def set_scene():
    road = surface("Asphalt", (.035,.038,.041), (.10,.107,.11), 210, .94)
    concrete = surface("Cast concrete", (.22,.228,.222), (.44,.438,.404), 4.5, .84)
    verge = surface("Verge", (.060,.068,.041), (.18,.17,.10), 9, .97)
    line = material("Weathered road marking", (.59,.59,.53), roughness=.89)
    box("Ground", (-30,0,-.07), (250,180,.11), verge)
    box("Test approach", (-65,0,-.031), (170,6.8,.06), road)
    for y in (-2.95,2.95):
        box("Edge stripe", (-42,y,.0004), (85,.082,.001), line)
    # Concrete cladding extends sideways for the image. Its face shares the
    # FE barrier's x-coordinate. The loading surface covers the vehicle width.
    for j in range(-4,5):
        box("Concrete wall panel", (.25,1.9*j,.88), (.4,1.896,1.76), concrete, .003)
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Cloudy sky")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation, sky.sun_rotation = .46, 2.35
    sky.sun_disc = False
    nt.links.new(sky.outputs[0], nt.nodes.get("Background").inputs[0])
    nt.nodes.get("Background").inputs["Strength"].default_value = .24
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.rotation_euler = (.65, -.40, -.7)
    sun.data.energy, sun.data.angle = 1.1, .30


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("cache", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--index", type=int, default=0)
    p.add_argument("--approach-m", type=float, default=0)
    p.add_argument("--width", type=int, default=360)
    p.add_argument("--samples", type=int, default=8)
    args = p.parse_args(sys.argv[sys.argv.index("--")+1:])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    set_scene()
    with np.load(args.cache / "mesh.npz") as a, np.load(args.source) as s, np.load(args.cache / f"frame-{args.index:04d}.npz") as f:
        xyz = load_car(dict(a), dict(f), dict(s), -args.approach_m)
        ix = {int(n): j for j,n in enumerate(a["node_id"]) if 5000511 <= n <= 5000518}
    # The original crossmember sensor has local +x forward and +y left.
    origin = Vector(xyz[ix[5000514]])
    x = (Vector(xyz[ix[5000513]]) - origin).normalized()
    y_ref = (Vector(xyz[ix[5000511]]) - origin).normalized()
    z = x.cross(y_ref).normalized()
    y = z.cross(x).normalized()
    eye = origin + x * -.035 + y * -.048 + z * .920
    bpy.ops.object.camera_add(location=eye)
    cam = bpy.context.object
    cam.rotation_euler = (x - .09*y - .10*z).to_track_quat("-Z","Y").to_euler()
    cam.data.sensor_fit, cam.data.sensor_height, cam.data.lens = "VERTICAL", 32, 19
    cam.data.clip_start = .015
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.engine = "CYCLES"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.resolution_x, scene.render.resolution_y = args.width, round(args.width*16/9)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(args.output.resolve())
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
