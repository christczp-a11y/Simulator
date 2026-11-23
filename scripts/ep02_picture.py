"""Assemble a manifest from the solved shot lists and actual render directories."""
import argparse
import json
from pathlib import Path


def manifest(root,cases):
    frames=[]
    def append(phase,local,data,image,contact):
        frames.append(dict(phase=phase,local=local,image=str(image.relative_to(root)) if image else None,
                           kmh=data["speed_kmh"],initial=speed,g=data["seat_g"],slow=data["slow"],
                           since=data["since_contact_s"],cabinCm=data["cabin_lost_cm"],contactFrame=contact))
    for speed in cases:
        case=root/str(speed)
        poses=json.loads((case/"shots.json").read_text())["head"]
        main=poses["main"]
        contact=next(i for i,d in enumerate(main) if d["since_contact_s"]>=0)
        for i,d in enumerate(main):
            image=case/"main"/f"{i:04d}.png"
            if not image.is_file():raise FileNotFoundError(image)
            append("drive",i,d,image,contact)
        for i in range(8):append("hold",i,d,image,contact)
    replay=poses["real"]
    contact=next(i for i,d in enumerate(replay) if d["since_contact_s"]>=0)
    for i,d in enumerate(replay):
        image=case/"real"/f"{i:04d}.png"
        if not image.is_file():raise FileNotFoundError(image)
        append("real",i,d,image,contact)
    for i in range(8):append("black",i,d,None,contact)
    for i in range(84):append("end",i,d,None,contact)
    return dict(maxSpeed=max(cases),frames=frames)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("root",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("speeds",type=int,nargs="+")
    a=p.parse_args()
    if a.speeds!=sorted(set(a.speeds)):p.error("Specify rendered speeds in increasing order.")
    a.output.write_text(json.dumps(manifest(a.root,a.speeds),allow_nan=False))
