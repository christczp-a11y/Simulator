"""Export orientation traces and timing comparisons for the two EP02 camera mounts."""
import argparse
import csv
from functools import lru_cache
import json
import os
from pathlib import Path

import numpy as np
from ep02_landmarks import WHEEL


def point_to_surface(p, tri):
    """Shortest distance from an eye position to the actual wheel triangles."""
    a,b,c=tri.transpose(1,0,2)
    ab,ac=b-a,c-a
    normal=np.cross(ab,ac)
    norm2=np.einsum("ij,ij->i",normal,normal)
    closest=np.inf
    # If the orthogonal projection is inside, distance to the plane is exact.
    within=norm2>1e-20
    for start,end in ((a,b),(b,c),(c,a)):
        step=end-start
        offset=p-start
        within &= np.einsum("ij,ij->i",np.cross(step,offset),normal)>=0
        length2=np.einsum("ij,ij->i",step,step)
        u=np.divide(np.einsum("ij,ij->i",offset,step),length2,
                    where=length2>0,out=np.zeros_like(length2)).clip(0,1)
        closest=min(closest,np.linalg.norm(offset-u[:,None]*step,axis=1).min())
    if within.any():
        height=np.einsum("ij,ij->i",p-a[within],normal[within])/np.sqrt(norm2[within])
        closest=min(closest,abs(height).min())
    return float(closest)


def wheel_clearance(cache,plans):
    times=np.load(cache/"times.npy")
    with np.load(cache/"mesh.npz") as top:
        tri_mask=top["part_id"][top["tri_cell"]]==WHEEL
        quad_mask=top["part_id"][top["quad_cell"]]==WHEEL
        triangles=top["tri"][tri_mask]
        quads=top["quad"][quad_mask]
        tri_cells,quad_cells=top["tri_cell"][tri_mask],top["quad_cell"][quad_mask]
        cells=np.concatenate([tri_cells,quad_cells,quad_cells])
        verts,faces=np.unique(np.concatenate([triangles,quads[:,[0,1,2]],quads[:,[0,2,3]]]),
                              return_inverse=True)
        faces=faces.reshape(-1,3)
    @lru_cache(maxsize=4)
    def wheel(i):
        with np.load(cache/f"frame-{i:04d}.npz") as frame:
            return frame["xyz"][verts].astype(float)*.001,frame["active"][cells]
    result={}
    for mode in ("head","fixed"):
        distances=[]
        for pose in plans[mode]["main"]:
            t=max(0,pose["t_s"])
            j=max(0,np.searchsorted(times,t,side="right")-1)
            xyz,active=wheel(j)
            if j+1<len(times):
                u=(t-times[j])/(times[j+1]-times[j])
                xyz=xyz*(1-u)+wheel(j+1)[0]*u
            p=np.array(pose["eye_m"])+[pose["approach_m"],0,0]
            if not active.any():
                raise ValueError("No active steering wheel surface remains at this physical time")
            distances.append(100*point_to_surface(p,xyz[faces[active]]))
        k=int(np.argmin(distances))
        result[mode]=dict(initial_eye_to_wheel_cm=distances[0],minimum_eye_to_wheel_cm=distances[k],
                          since_contact_ms=1000*plans[mode]["main"][k]["since_contact_s"])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("shots",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--prefix",default="56kmh")
    p.add_argument("--cache",type=Path)
    args=p.parse_args()
    plans=json.loads(args.shots.read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR",str(Path(__file__).resolve().parents[1]/"work/mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(8,5.7),layout="constrained")
    with (args.output/f"{args.prefix}-camera-orientation.csv").open("w",newline="") as f:
        w=csv.writer(f,lineterminator="\n")
        w.writerow(["mode","shot","film_frame","film_s","solver_s","since_contact_s","eye_x_m","eye_y_m","eye_z_m",
                    "quat_w","quat_x","quat_y","quat_z","angular_speed_deg_per_film_s"])
        for ax,seq in zip(axes,["main","real"]):
            for mode,color in [("head","#184e77"),("fixed","#b96c40")]:
                poses=plans[mode][seq]
                for i,s in enumerate(poses):
                    w.writerow([mode,seq,i,i/30,s["t_s"],s["since_contact_s"],*s["eye_m"],*s["quaternion_wxyz"],s["angular_deg_s"]])
                ft=np.arange(len(poses))/30
                ax.plot(ft,[s["angular_deg_s"] for s in poses],color=color,lw=1.5,label=mode)
                if mode=="head":
                    rel=np.array([s["since_contact_s"] for s in poses])
                    ax.axvline(np.interp(0,rel,ft),ls=":",color="#555555",label="first contact")
            ax.set(ylabel="Angular speed (deg/s)",title={"main":"Approach and 30× impact","real":"Real-time replay"}[seq])
            ax.set_xlabel("Elapsed film time (s)")
            ax.legend(frameon=False,fontsize=8)
    fig.savefig(args.output/f"{args.prefix}-camera-angular-speed.png",dpi=170)
    if args.cache:
        result=wheel_clearance(args.cache,plans)
        (args.output/f"{args.prefix}-eye-clearance.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":main()
