"""Bake each measured cabin state into a scrubbable Blender project with native PC2 caches."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0,str(Path(__file__).resolve().parent))
from ep02_cabin_motion import CabinMotion, points


def key_pose(ob, matrix, frame):
    location, quat, _ = matrix.decompose()
    if frame > 1:
        quat.make_compatible(ob.rotation_quaternion)
    ob.rotation_mode = "QUATERNION"
    ob.location, ob.rotation_quaternion = location, quat
    ob.keyframe_insert(data_path="location",frame=frame,group="Solver motion")
    ob.keyframe_insert(data_path="rotation_quaternion",frame=frame,group="Solver motion")


def animate_erosion(ob, changes):
    # Each boolean field is a measured state. The switches keep face
    # deletions discrete even when viewing the cache at a subframe.
    mod = ob.modifiers["Solver shell erosion"]
    graph = mod.node_group.copy()
    mod.node_group = graph
    delete = next(n for n in graph.nodes if n.bl_idname=="GeometryNodeDeleteGeometry")
    previous = delete.inputs["Selection"].links[0].from_socket
    for frame, flags in changes:
        name = f"ep02_eroded_{frame:04d}"
        field = ob.data.attributes.new(name,"BOOLEAN","FACE")
        field.data.foreach_set("value",flags)
        named = graph.nodes.new("GeometryNodeInputNamedAttribute")
        named.data_type = "BOOLEAN"
        named.inputs["Name"].default_value = name
        switch = graph.nodes.new("GeometryNodeSwitch")
        switch.input_type = "BOOLEAN"
        graph.links.new(previous,switch.inputs["False"])
        graph.links.new(named.outputs["Attribute"],switch.inputs["True"])
        trigger = switch.inputs["Switch"]
        trigger.default_value = False
        trigger.keyframe_insert(data_path="default_value",frame=1)
        trigger.default_value = True
        trigger.keyframe_insert(data_path="default_value",frame=frame)
        previous = switch.outputs["Output"]
    graph.links.new(previous,delete.inputs["Selection"])


def bake(folder, source, cache, history):
    with np.load(source) as z:
        rigid = set(z["part_id"][z["part_mat"]=="RIGID"])
    with np.load(cache/"mesh.npz") as z:
        top = dict(z)
    with np.load(cache/"frame-0000.npz") as z:
        first = dict(z)
    times = np.load(cache/"times.npy")
    curve = np.genfromtxt(history,names=True,delimiter=",")
    if (len(times)<2 or times[0]!=0 or np.any(np.diff(times)<=0) or
        abs(times[-1]-curve["time_s"][-1])>.0006):
        raise ValueError("Solver cache and speed history differ in time coverage")
    scene = bpy.context.scene
    # Establish the staging project's base for Blender's //cache paths.
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/"ep02-cabin-motion.blend"),compress=True)
    motion = CabinMotion(scene,top,first,rigid)
    if abs(motion.initial_speed-curve["cg_resultant_kmh"][0])>.2:
        raise ValueError("Rebuild the static dial for the requested speed first")
    speeds = np.interp(times,curve["time_s"],curve["cg_resultant_kmh"])
    out = folder/"cache"
    out.mkdir()
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    scene.frame_start, scene.frame_end = 1,len(times)
    scene.render.fps = 30
    # Mesh cache headers are little-endian PC2. Frame 1 is solver t=0.
    skins = [(mesh,cells,pid) for pid,batch in motion.skins.items() for mesh,_,cells,_ in batch]
    mesh_objects = {o.data:o for o in scene.objects if o.type=="MESH"}
    meshes = [mesh for mesh,_,_ in skins] + [mesh for mesh,*_ in motion.linings]
    assemblies = bpy.data.collections.new("Solved trim mounts")
    scene.collection.children.link(assemblies)
    mounts = []
    for pid,*_,pieces in motion.fittings:
        root = bpy.data.objects.new(f"Mount {pid} | {pieces[0][0].users_collection[0].name}",None)
        root.empty_display_size=.025
        assemblies.objects.link(root)
        mounts.append(root)
    visibility = {}
    changes = {}
    previous_active = first["active"]
    with ExitStack() as stack:
        writers = []
        for i,mesh in enumerate(meshes):
            f=stack.enter_context((out/f"{i:04d}.pc2").open("wb"))
            f.write(struct.pack("<12s i i f f i",b"POINTCACHE2\0",1,len(mesh.vertices),1.,1.,len(times)))
            writers.append(f)
        for i,t in enumerate(times):
            with np.load(cache/f"frame-{i:04d}.npz") as f:
                if f["time_s"] != t:
                    raise ValueError(f"Cache timestamp mismatch at frame {i}")
                active,xyz=f["active"],f["xyz"].astype(float)*.001
            motion.update(xyz,active,speeds[i])
            frame=i+1
            for mesh,stream in zip(meshes,writers):
                stream.write(points(mesh).astype("<f4",copy=False).tobytes())
            if np.any(active!=previous_active):
                for mesh,cells,pid in skins:
                    if pid not in rigid and np.any(active[cells]!=previous_active[cells]):
                        changes.setdefault(mesh,[]).append((frame,~active[cells]))
            for root,(_,_,_,_,_,pieces) in zip(mounts,motion.fittings):
                ob,basis,_=next(item for item in pieces if item[0]!=motion.pointer)
                transform = ob.matrix_world @ basis.inverted()
                key_pose(root,transform,frame)
                for child,_,initial_hidden in pieces:
                    hidden = child.hide_render
                    if visibility.get(child,initial_hidden)!=hidden:
                        if child not in visibility:
                            child.hide_render = initial_hidden
                            child.keyframe_insert(data_path="hide_render",frame=1)
                        child.hide_render = hidden
                        child.keyframe_insert(data_path="hide_render",frame=frame)
                        visibility[child]=hidden
                    if child==motion.pointer:
                        key_pose(child,transform.inverted() @ child.matrix_world,frame)
            for ob,_ in motion.rig:
                key_pose(ob,ob.matrix_world,frame)
            previous_active=active
            if i%25==0:
                print(f"Baked solver sample {i+1}/{len(times)}",flush=True)
    motion.update(motion.rest,first["active"],speeds[0])
    for i,mesh in enumerate(meshes):
        ob=mesh_objects[mesh]
        mod=ob.modifiers.new("Solver positions at 0.5 ms intervals","MESH_CACHE")
        mod.cache_format="PC2"
        mod.filepath=f"//cache/{i:04d}.pc2"
        mod.forward_axis="POS_Y"
        mod.up_axis="POS_Z"
        mod.time_mode="FRAME"
        # In FRAME mode Blender indexes the PC2 samples from zero.
        mod.frame_start=1.
        ob.modifiers.move(len(ob.modifiers)-1,0)
    for mesh,states in changes.items():
        animate_erosion(mesh_objects[mesh],states)
    for root,(_,_,_,_,_,pieces) in zip(mounts,motion.fittings):
        for child,basis,_ in pieces:
            child.parent=root
            child.matrix_parent_inverse=Matrix.Identity(4)
            child.matrix_basis=basis
    scene.timeline_markers.clear()
    for ms in (0,20,40,60,100,140):
        if .001*ms<=times[-1]+1e-7:
            at=int(np.argmin(abs(times-.001*ms)))
            scene.timeline_markers.new(f"{times[at]*1000:.2f} ms",frame=at+1)
    scene.camera=next(ob for ob,_ in motion.rig if ob.name.startswith("05 |"))
    scene.frame_set(1)
    scene.render.resolution_x,scene.render.resolution_y=1200,816
    scene.render.filepath="//inspection.jpg"
    scene["source"]="CCSA v2j interior driven by v1l solver samples. Diagnostic model."
    note=bpy.data.texts["About this cabin"]
    note.clear()
    note.write("EP02 | Cabin motion inspection\nCCSA / FHWA. Each Blender frame is one solver sample.\n"
               "Door, dash, wheel, carpet and other fitted-trim motion is transferred from measured shell nodes.\n"
               "The 56 km/h validation case exceeds its 5% energy limit. Use this scene for model inspection.\n"
               "Keep the cache subfolder next to this file. The speedometer follows solver CG speed.\n")
    note=bpy.data.texts.new("Solver sample times.csv")
    note.write("frame,solver_ms,cg_kmh\n"+"".join(f"{i+1},{t*1000:.7f},{v:.6f}\n" for i,(t,v) in enumerate(zip(times,speeds))))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/"ep02-cabin-motion.blend"),compress=True,relative_remap=False)
    print("BAKED",json.dumps(dict(**motion.report,frames=len(times),mesh_caches=len(meshes),
                                  cache_bytes=sum(p.stat().st_size for p in out.glob("*.pc2")))),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path)
    p.add_argument("cache",type=Path)
    p.add_argument("history",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:])
    dest=args.output.resolve()
    if dest.exists():
        p.error("Choose a new output directory to keep existing inspection projects intact.")
    dest.parent.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(dir=dest.parent) as staging:
        folder=Path(staging)/dest.name
        folder.mkdir()
        bake(folder,args.source,args.cache,args.history)
        folder.rename(dest)
