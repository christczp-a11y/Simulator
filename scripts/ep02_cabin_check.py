"""Check the editable cabin transfer against a rigid patch and measured crash frames."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0,str(Path(__file__).resolve().parent))
from ep02_cabin_motion import CabinMotion, points
from ep02_landmarks import landmarks


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path)
    p.add_argument("cache",type=Path)
    p.add_argument("output",type=Path)
    args = p.parse_args(sys.argv[sys.argv.index("--")+1:])
    with np.load(args.cache/"mesh.npz") as z:
        top = dict(z)
    with np.load(args.cache/"frame-0000.npz") as z:
        first = dict(z)
    with np.load(args.source) as z:
        rigid = set(z["part_id"][z["part_mat"]=="RIGID"])
    # Include text local axes as well as mesh coordinates in the patch test.
    shells = list(bpy.data.collections["Model | CCSA v2j shells"].objects)
    trim = list(bpy.data.collections["Production trim"].all_objects)
    def world_points(ob):
        matrix = np.asarray(ob.matrix_world)
        if ob.type=="MESH":
            pts=points(ob.data)
        else:
            pts=np.asarray(ob.bound_box)
        return pts @ matrix[:3,:3].T + matrix[:3,3]
    before = {ob.name:world_points(ob) for ob in shells+trim}
    scene = bpy.context.scene
    binding = CabinMotion(scene,top,first,rigid)
    rot = np.asarray(Matrix.Rotation(.41,4,"Z") @ Matrix.Rotation(-.24,4,"Y"))[:3,:3]
    shift = np.array([.34,-.19,.12])
    errors = {}
    for label,r,b in (("rest",np.eye(3),np.zeros(3)),("rigid_patch",rot,shift)):
        binding.update(binding.rest @ r.T+b,first["active"],binding.initial_speed)
        bpy.context.view_layer.update()
        errors[label] = float(max(np.linalg.norm(world_points(o)-(before[o.name]@r.T+b),axis=1).max()
                                  for o in shells+trim)*1000)
        if errors[label] > .01:
            raise ValueError(f"{label} failed rigid motion reproduction: {errors[label]} mm")
    # Measure the change of the visual wheel centre against the four solver
    # rim extrema, allowing for their distinct centre definitions at rest.
    rim, *_ = landmarks(top,first["xyz"].astype(float))
    grip = next(o for o in trim if o.name.startswith("Padded grip"))
    glass = next(o for o in shells if o["CCSA_part_id"]==2000023)
    index = np.load(args.cache/"times.npy")
    initial_center = before[grip.name].mean(axis=0)
    initial_rim = binding.rest[rim].mean(axis=0)
    records = []
    for ms in (0,20,40,60,100,140):
        i = np.argmin(abs(index-ms/1000))
        if abs(index[i]-ms/1000) > .00051:
            raise ValueError("Missing required solver time")
        with np.load(args.cache/f"frame-{i:04d}.npz") as f:
            xyz = f["xyz"].astype(float)*.001
            active = f["active"]
        binding.update(xyz,active,binding.initial_speed)
        bpy.context.view_layer.update()
        delta = world_points(grip).mean(axis=0)-initial_center-(xyz[rim].mean(axis=0)-initial_rim)
        attr = glass.data.attributes["ep02_eroded"]
        flags = np.empty(len(attr.data),bool)
        attr.data.foreach_get("value",flags)
        visible_faces=len(glass.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.polygons)
        if visible_faces != len(flags)-int(flags.sum()):
            raise ValueError("Viewport windscreen still contains eroded faces")
        records.append(dict(solver_ms=float(1000*index[i]),wheel_center_displacement_difference_mm=float(1000*np.linalg.norm(delta)),
                            solver_windscreen_eroded_cells=int(np.sum((top["part_id"]==2000023)&first["active"]&~active)),
                            hidden_detailed_windscreen_faces=int(flags.sum()),visible_detailed_windscreen_faces=visible_faces))
    args.output.write_text(json.dumps(dict(**binding.report, max_error_mm=errors, measured_frames=records),
                                      indent=2,allow_nan=False)+"\n")


if __name__=="__main__":
    main()
