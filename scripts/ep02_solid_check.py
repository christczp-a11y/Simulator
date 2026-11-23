"""Check the interior-contact part set in Starter and in its measured 56 km/h brick states."""
import argparse
import itertools
import json
from pathlib import Path
import re

import numpy as np

from vtk_seq import cell_offsets


def distortion_flags(report):
    parts = {}
    for block in report.read_text().split("STANDARD SOLID PROPERTY SET")[1:]:
        pid = re.search(r"PROPERTY SET NUMBER [ .]*=\s*(\d+)",block)
        flag = re.search(r"^\s*SOLID DISTORTION CONTROL FLAG [ .]*=\s*(\d+)",block,re.M)
        if not pid or not flag:
            raise ValueError("Missing property number or solid-distortion setting")
        key = int(pid[1])
        if key in parts and parts[key] != int(flag[1]):
            raise ValueError(f"Conflicting records for property {key}")
        parts[key] = int(flag[1])
    return parts


def check(case, audit_dir, cache):
    deck = (case/"combine.key").read_text()
    stanza = "*CONTACT_INTERIOR\n$#    psid\n   1000001\n"
    if deck.count(stanza)!=1:
        raise ValueError("Unexpected interior-contact card")
    runs = [audit_dir/k for k in ("original","no-interior","repeat")]
    flags = []
    for i,folder in enumerate(runs):
        expected = deck.replace(stanza,"") if i==1 else deck
        if (folder/"combine.key").read_text()!=expected:
            raise ValueError("Additional changes in Starter comparison deck")
        flags.append(distortion_flags(folder/"combine_0000.out"))
    if flags[0]!=flags[2] or flags[0].keys()!=flags[1].keys():
        raise ValueError("Inconsistent Starter property sets")
    members = (case/"set-yaris-coarse-v1l.key").read_text().split("solids interior contact\n",1)[1].split("*",1)[0]
    ids = [int(v) for line in members.splitlines() if line.lstrip().startswith("200") for v in line.split()]
    changed = {pid for pid,flag in flags[0].items() if flag!=flags[1][pid]}
    if changed!=set(ids) or any((flags[0][pid],flags[1][pid])!=(1,0) for pid in ids):
        raise ValueError("Imported flags do not match the v1l interior-contact set")
    with np.load(cache/"mesh.npz") as mesh:
        selected=np.flatnonzero(np.isin(mesh["part_id"],ids)&(mesh["cell_types"]==12))
        flat=mesh["cells_flat"]
        first=cell_offsets(flat,mesh["cell_types"])[selected]
        nodes=flat[first[:,None]+np.arange(1,9)]
        part=mesh["part_id"][selected]
        eid=mesh["elem_id"][selected]
    # Trilinear VTK_HEXAHEDRON geometry, evaluated at all eight Gauss points.
    # This diagnostic is independent of the element's stress integration rule.
    corners=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])
    gradients=[]
    for point in itertools.product((-1/np.sqrt(3),1/np.sqrt(3)),repeat=3):
        x,y,z=(1+corners*point).T
        gradients.append(corners*np.column_stack((y*z,x*z,x*y))/8)
    times=np.load(cache/"times.npy")
    smallest=np.full(len(nodes),np.inf)
    when=np.zeros(len(nodes))
    for i,t in enumerate(times):
        with np.load(cache/f"frame-{i:04d}.npz") as f:
            if f["time_s"]!=t:
                raise ValueError("Cache timestamp mismatch")
            active=f["active"][selected]
            points=f["xyz"][nodes].astype(float)
        jac=np.einsum("enc,gnl->egcl",points-points[:,:1],gradients,optimize=True)
        det=np.linalg.det(jac)
        if i==0:
            if not np.all(active) or np.any(det<=1e-7):
                raise ValueError("Invalid or inactive starting brick in the contact set")
            rest=det
        ratio=(det[active]/rest[active]).min(axis=1)
        update=ratio<smallest[active]
        indices=np.flatnonzero(active)[update]
        smallest[indices]=ratio[update]
        when[indices]=t
    rows=[]
    for pid in ids:
        group=np.flatnonzero(part==pid)
        index=group[np.argmin(smallest[group])]
        rows.append(dict(part_id=pid,bricks=len(group),min_detJ_ratio=smallest[index],
                         solver_ms=1000*when[index],element_id=int(eid[index])))
    return dict(confirmed_property_ids=sorted(changed), frames=len(times), bricks=len(nodes),
                minimum_active_detJ_ratio=smallest.min(),ever_nonpositive_bricks=int((smallest<=0).sum()),parts=rows)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ("case","audit_dir","cache","output"):
        parser.add_argument(arg,type=Path)
    args=parser.parse_args()
    args.output.write_text(json.dumps(check(args.case,args.audit_dir,args.cache),indent=2,allow_nan=False)+"\n")
