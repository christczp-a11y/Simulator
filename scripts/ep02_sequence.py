"""Batch Cycles renders of measured EP02 poses with a physical-time shutter."""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ep02_still import load_car, materials, set_scene


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path)
    p.add_argument("cache",type=Path)
    p.add_argument("shots",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--mode",choices=["head","fixed"],required=True)
    p.add_argument("--sequence",choices=["main","real","stills"],required=True)
    p.add_argument("--width",type=int,default=360)
    p.add_argument("--samples",type=int,default=12)
    p.add_argument("--frames",type=int,nargs="+")
    p.add_argument("--save-scene",type=Path,help="Save the first measured pose as a local Blender scene")
    p.add_argument("--save-index",type=int,help="Save this shot index instead of the first requested shot")
    p.add_argument("--cabin",type=Path,help="Editable v2j cabin built with build_ep02_cabin.sh")
    p.add_argument("--gpu",action="store_true",help="Use a supported Cycles GPU, if available")
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:])
    shots=json.loads(args.shots.read_text())[args.mode][args.sequence]
    args.output.mkdir(parents=True,exist_ok=True)
    if args.cabin:
        bpy.ops.wm.open_mainfile(filepath=str(args.cabin.resolve()))
        cam=next(ob for ob in bpy.context.scene.objects if ob.type=="CAMERA" and ob.name.startswith("01 |"))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        set_scene()
        bpy.ops.object.camera_add()
        cam=bpy.context.object
    cam.data.sensor_fit,cam.data.sensor_height,cam.data.lens="VERTICAL",32,19
    cam.data.clip_start=.015
    cam.rotation_mode="QUATERNION"
    scene=bpy.context.scene
    scene.camera=cam
    scene.render.engine="CYCLES"
    if args.gpu:
        preferences=bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX","HIP","METAL","ONEAPI","CUDA"):
            try:
                preferences.compute_device_type=backend
                preferences.refresh_devices()
            except (TypeError,RuntimeError):
                continue
            if any(d.type==backend for d in preferences.devices):
                for device in preferences.devices:
                    device.use=device.type==backend
                scene.cycles.device="GPU"
                break
        else:
            raise RuntimeError("No supported Cycles GPU was found.")
    scene.cycles.samples=args.samples
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=6
    scene.render.resolution_x,scene.render.resolution_y=args.width,round(args.width*16/9)
    scene.render.resolution_percentage=100
    scene.render.use_persistent_data=True
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGB"
    with np.load(args.source) as s, np.load(args.cache/"mesh.npz") as z:
        source,top=dict(s),dict(z)
    times=np.load(args.cache/"times.npy")
    @lru_cache(maxsize=4)
    def frame(i):
        with np.load(args.cache/f"frame-{i:04d}.npz") as f:return dict(f)
    objects={}
    cabin=None
    if args.cabin:
        from ep02_cabin_motion import CabinMotion
        rigid=set(source["part_id"][source["part_mat"]=="RIGID"])
        cabin=CabinMotion(scene,top,frame(0),rigid)
        print("CABIN BINDING",json.dumps(cabin.report),flush=True)
        scene["source"]="CCSA v2j cabin with v1l shell motion transferred by part ID; trim motion is reconstructed."
        notes=bpy.data.texts.get("About this cabin")
        if notes:
            notes.clear()
            notes.write("Detailed v2j shell surfaces follow measured v1l solver nodes. Fittings use their local support.\n"
                        "The stored pose is a diagnostic snapshot. Use ep02_render.py to reproduce the time series.\n")
    palette=materials()
    previous_active=None
    def update(pose):
        nonlocal previous_active
        t=max(0.,pose["t_s"])
        i=max(0,np.searchsorted(times,t,side="right")-1)
        f=frame(i)
        xyz=f["xyz"]*.001
        if i+1<len(times) and t>times[i]:
            u=(t-times[i])/(times[i+1]-times[i])
            xyz=(1-u)*xyz + u*.001*frame(i+1)["xyz"]
        xyz[:,0]-=pose["approach_m"]
        changed=set(source["part_id"]) if previous_active is None else set(top["part_id"][f["active"]!=previous_active])
        if cabin:
            changed-=cabin.parts
            # The studio scene uses a reconstructed manual console over the
            # tunnel. Do not insert its bare alternative assembly through it.
            changed.difference_update(range(2000951,2000963))
            cabin.update(xyz,f["active"],pose["speed_kmh"])
            scene["solver_time_s"]=float(t)
            scene["approach_m"]=float(pose["approach_m"])
            scene["display_speed_kmh"]=float(pose["speed_kmh"])
        if changed:
            for part in changed.intersection(objects):
                ob,_=objects.pop(part); mesh=ob.data
                bpy.data.objects.remove(ob,do_unlink=True)
                bpy.data.meshes.remove(mesh)
            load_car(top,f,source,0,objects=objects,palette=palette,only=changed)
        for ob,idx in objects.values():
            ob.data.vertices.foreach_set("co",np.ascontiguousarray(xyz[idx],dtype=np.float32).ravel())
            ob.data.update()
        previous_active=f["active"]
        cam.location=pose["eye_m"]
        cam.rotation_quaternion=pose["quaternion_wxyz"]
    save_scene=args.save_scene
    for index in (args.frames if args.frames is not None else range(len(shots))):
        shot=shots[index]
        output=args.output/f"{index:04d}.png"
        rendering=output.with_suffix(".partial.png")
        scene.render.filepath=str(rendering.resolve())
        if save_scene and (args.save_index is None or index==args.save_index):
            update(shot)
            if cabin:
                bpy.context.preferences.filepaths.save_version=0
            bpy.ops.wm.save_as_mainfile(filepath=str(save_scene.resolve()),compress=bool(cabin))
            save_scene=None
        exposures=shot.get("shutter")
        if not exposures:
            update(shot)
            bpy.ops.render.render(write_still=True)
            rendering.replace(output)
            continue
        # EXRs hold scene-linear radiance. Accumulate it before display
        # rendering so glass reflections and highlights blur at the correct intensity.
        acc=None
        import tempfile
        with tempfile.TemporaryDirectory(dir=args.output) as temp:
            path=Path(temp)/"exposure.exr"
            scene.render.image_settings.file_format="OPEN_EXR"
            scene.render.filepath=str(path.resolve())
            for exposure in exposures:
                update(exposure)
                bpy.ops.render.render(write_still=True)
                img=bpy.data.images.load(str(path.resolve()),check_existing=False)
                pixels=np.empty(len(img.pixels),dtype=np.float32)
                img.pixels.foreach_get(pixels)
                acc=pixels if acc is None else acc+pixels
                bpy.data.images.remove(img)
            w,h=scene.render.resolution_x,scene.render.resolution_y
            merged=bpy.data.images.new("Integrated shutter",w,h,alpha=True,float_buffer=True)
            merged.pixels.foreach_set(acc/len(exposures))
            scene.render.image_settings.file_format="PNG"
            merged.save_render(str(rendering.resolve()),scene=scene)
            bpy.data.images.remove(merged)
            rendering.replace(output)


if __name__=="__main__":
    main()
