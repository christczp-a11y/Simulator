"""Build 30 fps physical-time shot lists after the full history and mesh cache exist."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from ep02_camera import Camera

FPS = 30


def sample_plan(history, landmarks):
    cam = Camera.from_history(history)
    mt = landmarks["time_s"]
    t = history["time_s"]
    contact = cam.contact
    if abs(mt[-1] - t[-1]) > .0006:
        raise ValueError("Mesh cache and measured time history cover different intervals.")
    def landmark(field, at):
        return np.interp(at, mt, landmarks[field])
    def point(prefix, at):
        return np.column_stack([landmark(f"{prefix}_{axis}_mm", at) for axis in "xyz"])*.001
    def at_times(at,mode):
        origin = point("mount", at)
        x = point("mount_x", at)-origin
        x /= np.linalg.norm(x,axis=1)[:,None]
        side = point("mount_y", at)-origin
        z = np.cross(x,side); z /= np.linalg.norm(z,axis=1)[:,None]
        y = np.cross(z,x)
        basis=np.stack([x,y,z],axis=2)
        delta=cam.offsets(at,mode)
        eye=origin+np.einsum("nij,nj->ni",basis,np.array([-.035,-.048,.920])+delta[:,:3])
        approach=np.maximum(-at,0)*cam.speed/3.6
        eye[:,0]-=approach
        base_forward = np.array([1.,-.09,-.10]); base_forward/=np.linalg.norm(base_forward)
        base_right = np.cross(base_forward,[0,0,1]);base_right/=np.linalg.norm(base_right)
        base_up=np.cross(base_right,base_forward)
        base=np.stack([base_right,base_up,-base_forward],axis=1)
        rot=basis @ Rotation.from_euler("XYZ",delta[:,3:],degrees=True).as_matrix() @ base
        quat=Rotation.from_matrix(rot).as_quat()[:,[3,0,1,2]]
        vel=np.zeros(len(at))
        if len(at)>1:
            # Differentiate per shot, never across cuts or between camera modes.
            vel[1:]=np.rad2deg(Rotation.from_matrix(rot[:-1].transpose(0,2,1)@rot[1:]).magnitude())*FPS
        out=[]
        for i,s in enumerate(at):
            sample_time = max(0.,float(s))
            if sample_time > mt[-1]+1e-9:
                raise ValueError("Requested time exceeds the solved animation.")
            out.append(dict(t_s=float(s), since_contact_s=float(s-contact),
                            eye_m=eye[i].tolist(), quaternion_wxyz=quat[i].tolist(),
                            angular_deg_s=float(vel[i]), approach_m=float(approach[i]),
                            speed_kmh=float(np.interp(s,t,history["cg_resultant_kmh"])),
                            seat_g=float(np.interp(s,t,history["seat_decel_cfc60_g"])) if s>=0 else None,
                            cabin_lost_cm=float(landmark("cabin_lost_cm",s))))
        return out
    # Nine film frames transition from real time to 30x. Integral of the
    # cubic ease keeps film and physical time continuous at both joins.
    ramp=.3
    contact_film=1+ramp
    pre=1+ramp*(1+1/30)/2
    trim_end=min(t[-1],mt[-1])
    main_end=contact_film+(trim_end-contact)*30
    ft=np.arange(int(np.floor(main_end*FPS))+1)/FPS
    u=np.clip((ft-1)/ramp,0,1)
    along=ramp*(u-(1-1/30)*(u**3-.5*u**4))
    at=np.where(ft<1,contact-pre+ft,
                np.where(ft<contact_film,contact-pre+1+along,contact+(ft-contact_film)/30))
    replay=trim_end + np.arange(-17,1)/FPS
    still=np.array([-.45,contact,*[contact+ms/1000 for ms in (20,40,60,100)]])
    shots = {}
    for mode in ("head", "fixed"):
        shots[mode] = {}
        for name, physical in [("main",at),("real",replay),("stills",still)]:
            poses = at_times(physical,mode)
            for i,pose in enumerate(poses):
                real_time = name == "real" or (name == "main" and ft[i] < 1)
                if real_time:
                    # Five midpoint samples across a 180-degree shutter,
                    # evaluated on the physical-time trajectory before rendering.
                    offsets=((np.arange(5)+.5)/5-.5)/(2*FPS)
                    shutter=at_times(np.minimum(physical[i]+offsets,trim_end),mode)
                    pose["shutter"]=[{k:s[k] for k in ("t_s","eye_m","quaternion_wxyz","approach_m")} for s in shutter]
                if name == "main" and 1 <= ft[i] < contact_film:
                    pose["slow"]=float(1/(1-(1-1/30)*(3*u[i]**2-2*u[i]**3)))
                else:
                    pose["slow"]=30 if name == "main" and ft[i] >= contact_film else 1
            shots[mode][name]=poses
    return shots


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("history",type=Path);p.add_argument("landmarks",type=Path);p.add_argument("output",type=Path)
    args=p.parse_args()
    read=lambda path: np.genfromtxt(path,delimiter=",",names=True)
    result=sample_plan(read(args.history),read(args.landmarks))
    args.output.write_text(json.dumps(result,allow_nan=False))
