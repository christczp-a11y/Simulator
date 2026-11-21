"""Track cabin clearance and the seat frame on stable, solver-numbered landmarks."""
import argparse
import csv
from pathlib import Path

import numpy as np

WHEEL = 2000938
SEAT_BACK = 2000928


def landmarks(mesh, xyz):
    part = mesh["part_id"]
    wheel_verts, seat_tris, seat_cells = [], [], []
    for kind, cell_key in [("quad", "quad_cell"), ("tri", "tri_cell")]:
        faces, cell = mesh[kind], mesh[cell_key]
        wheel_verts.extend(faces[part[cell] == WHEEL].ravel())
        selected = part[cell] == SEAT_BACK
        for cols in ([(0,1,2), (0,2,3)] if kind == "quad" else [(0,1,2)]):
            seat_tris.extend(faces[selected][:, cols]);seat_cells.extend(cell[selected])
    wheel = np.unique(wheel_verts)
    rim = xyz[wheel]
    # Four opposite rim extrema define a reproducible wheel centre.
    rim_idx = wheel[[rim[:,1].argmin(),rim[:,1].argmax(),rim[:,2].argmin(),rim[:,2].argmax()]]
    center = xyz[rim_idx].mean(axis=0)
    tri = np.asarray(seat_tris)
    a, b, c = xyz[tri].transpose((1,0,2))
    # Intersect the rearward longitudinal ray through the wheel centre with
    # the initial driver's seatback. Follow that material point in every frame.
    ab, ac, ar = (b-a)[:,1:], (c-a)[:,1:], (center-a)[:,1:]
    det = ab[:,0]*ac[:,1]-ac[:,0]*ab[:,1]
    ok = abs(det) > 1e-8
    u = np.divide(ar[:,0]*ac[:,1]-ac[:,0]*ar[:,1],det,where=ok,out=np.zeros_like(det))
    v = np.divide(ab[:,0]*ar[:,1]-ar[:,0]*ab[:,1],det,where=ok,out=np.zeros_like(det))
    x = a[:,0]+u*(b[:,0]-a[:,0])+v*(c[:,0]-a[:,0])
    ok &= (u>=0)&(v>=0)&(u+v<=1)&(x<center[0])
    if not ok.any():
        raise ValueError("Wheel-centre ray misses the driver's seatback")
    j = np.flatnonzero(ok)[np.argmax(x[ok])]
    nids=mesh["node_id"]
    mount=[np.flatnonzero(nids==n).item() for n in (5000514,5000513,5000511)]
    return rim_idx,tri[j],np.array([1-u[j]-v[j],u[j],v[j]]),seat_cells[j],mount


def measure(cache, output):
    times=np.load(cache/"times.npy")
    with np.load(cache/"mesh.npz") as z: mesh=dict(z)
    with np.load(cache/"frame-0000.npz") as z:
        rim, tri, weights, seat_cell, mount = landmarks(mesh,z["xyz"].astype(float))
    rows=[]
    for i,t in enumerate(times):
        with np.load(cache/f"frame-{i:04d}.npz") as z:
            if z["time_s"]!=t or not z["active"][seat_cell]:
                raise ValueError("Seatback landmark unavailable")
            pts=z["xyz"];w=pts[rim].mean(0);s=weights@pts[tri]
            dist=np.linalg.norm(w-s)
            if i==0: reference=dist
            rows.append([t,dist,(reference-dist)/10,*w,*s,*pts[mount].ravel()])
    cols=["time_s","clearance_mm","cabin_lost_cm"]+[f"{loc}_{axis}_mm" for loc in ("wheel","back","mount","mount_x","mount_y") for axis in "xyz"]
    with output.open("w",newline="") as f:
        writer=csv.writer(f,lineterminator="\n"); writer.writerow(cols);writer.writerows(rows)
    print("Steering rim node IDs",mesh["node_id"][rim],"seatback element",mesh["elem_id"][seat_cell],
          "seatback node IDs",mesh["node_id"][tri],"weights",weights,"initial clearance (mm)",reference)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("cache",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args();measure(args.cache,args.output)
