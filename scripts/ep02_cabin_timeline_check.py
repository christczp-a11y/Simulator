"""Reopen the baked project in Blender and check playback against its PC2 and solver samples."""
import argparse
import json
from pathlib import Path
import struct
import sys

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0,str(Path(__file__).resolve().parent))
from ep02_cabin_motion import points
from ep02_landmarks import landmarks


def pc2_frame(path, frame, count, samples):
    with path.open("rb") as f:
        tag,version,size,start,rate,n = struct.unpack("<12s i i f f i", f.read(32))
        if (tag,version,size,start,rate,n)!=(b"POINTCACHE2\0",1,count,1.,1.,samples):
            raise ValueError(f"Unexpected PC2 header in {path}")
        f.seek(32+(frame-1)*count*12)
        return np.frombuffer(f.read(count*12),dtype="<f4").reshape(-1,3)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("cache",type=Path)
    p.add_argument("binding_report",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:])
    scene=bpy.context.scene
    report=json.loads(args.binding_report.read_text())
    times=np.load(args.cache/"times.npy")
    with np.load(args.cache/"frame-0000.npz") as f:
        base=f["xyz"].astype(float)*.001
    with np.load(args.cache/"mesh.npz") as top:
        rim,*_=landmarks(dict(top),base*1000)
    if scene.frame_start!=1 or scene.frame_end!=len(times):
        raise ValueError("Timeline bounds disagree with cached solver samples")
    glass=next(o for o in scene.objects if o.get("CCSA_part_id")==2000023)
    grip=next(o for o in scene.objects if o.name.startswith("Padded grip"))
    pointer=bpy.data.objects["Speedometer | pointer"]
    instrument=bpy.data.objects["Recessed instrument carrier"]
    speeds=np.genfromtxt(bpy.data.texts["Solver sample times.csv"].as_string().splitlines(),
                         names=True,delimiter=",")["cg_kmh"]
    cameras=[ob for ob in scene.objects if ob.type=="CAMERA"]
    with np.load(args.cache/"mesh.npz") as data:
        indices=[np.flatnonzero(data["node_id"]==n).item() for n in (5000514,5000513,5000511)]
    def seat_basis(xyz):
        origin,forward,left=xyz[indices]
        x=forward-origin
        x/=np.linalg.norm(x)
        z=np.cross(x,left-origin)
        z/=np.linalg.norm(z)
        return origin,np.column_stack((x,np.cross(z,x),z))
    rest_origin,rest_axes=seat_basis(base)
    center=points(grip.data).astype(float).mean(axis=0)
    objects=[o for o in scene.objects if o.get("CCSA_part_id") in (2000023,2000917,2000928,2000938,2000880)]
    results=[]
    for row in report["measured_frames"]:
        frame=int(np.argmin(abs(times-row["solver_ms"]*.001)))+1
        scene.frame_set(frame)
        dg=bpy.context.evaluated_depsgraph_get()
        visible=len(glass.evaluated_get(dg).data.polygons)
        if visible!=row["visible_detailed_windscreen_faces"]:
            raise ValueError(f"Windscreen erosion mismatch at frame {frame}")
        error=0.
        for ob in objects:
            mod=ob.modifiers[0]
            if mod.type!="MESH_CACHE":
                raise ValueError(f"Missing leading point cache on {ob.name}")
            expected=pc2_frame(Path(bpy.path.abspath(mod.filepath)),frame,len(ob.data.vertices),len(times))
            # Read source vertices before the evaluated erosion modifier
            # changes numbering. Its separate topology test above stays active.
            erosion=ob.modifiers["Solver shell erosion"]
            erosion.show_viewport=False
            try:
                bpy.context.view_layer.update()
                actual=points(ob.evaluated_get(dg).data)
                error=max(error,float(1000*np.max(np.linalg.norm(actual-expected,axis=1))))
            finally:
                erosion.show_viewport=True
                bpy.context.view_layer.update()
        matrix=np.asarray(grip.evaluated_get(dg).matrix_world)
        pos=matrix[:3,:3]@center+matrix[:3,3]
        if frame==1:
            origin=pos
        with np.load(args.cache/f"frame-{frame-1:04d}.npz") as f:
            xyz=f["xyz"].astype(float)*.001
            shift=(xyz[rim]-base[rim]).mean(axis=0)
        wheel_error=1000*np.linalg.norm(pos-origin-shift)
        dial=instrument.matrix_world.inverted() @ pointer.matrix_world
        if frame==1:
            initial_eyes=np.array([tuple(cam.matrix_world.translation) for cam in cameras])
            initial_dial=dial.to_3x3().copy()
        current_origin,current_axes=seat_basis(xyz)
        expected_eyes=(initial_eyes-rest_origin) @ rest_axes @ current_axes.T+current_origin
        camera_error=float(1000*max(np.linalg.norm(expected_eyes-np.array([tuple(cam.matrix_world.translation) for cam in cameras]),axis=1)))
        angle=np.deg2rad(-234*(speeds[frame-1]-speeds[0])/1.609344/140)
        expected_dial=Matrix.Rotation(angle,3,(-1.,0.,.13)) @ initial_dial
        dial_error=float(np.max(np.abs(np.asarray(dial.to_3x3())-np.asarray(expected_dial))))
        if error>.002 or camera_error>.01 or dial_error>1e-4 or abs(wheel_error-row["wheel_center_displacement_difference_mm"])>.02:
            raise ValueError(f"Playback mismatch at frame {frame}: point {error} mm, rim {wheel_error} mm")
        results.append(dict(frame=frame,solver_ms=1000*times[frame-1],max_pc2_playback_error_mm=error,
                            max_camera_position_error_mm=camera_error,max_dial_rotation_matrix_error=dial_error,
                            visible_windscreen_faces=visible))
    missing=[path for path in bpy.utils.blend_paths(absolute=True,packed=False) if path and not Path(path).exists()]
    if missing:
        raise ValueError(f"Missing external assets: {missing[:3]}")
    args.output.write_text(json.dumps(dict(samples=scene.frame_end,missing_external_files=missing,
                                          timeline_checks=results),indent=2,allow_nan=False)+"\n")


if __name__=="__main__":
    main()
