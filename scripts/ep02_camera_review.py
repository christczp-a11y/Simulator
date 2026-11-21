"""Export orientation traces and timing comparisons for the two EP02 camera mounts."""
import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("shots",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--prefix",default="56kmh")
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


if __name__=="__main__":main()
