"""Read the wall-force traces in the verified CCSA coarse-model report, page 18."""
import argparse
import csv
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from PIL import Image
from scipy.signal import butter, sosfiltfilt


def reference(pdf):
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != "577cef33ad4344926cea9d94fba08727743691d7a6f7b1ad3a3d24dc3b86598e":
        raise ValueError("The graph calibration is specific to CCSA coarse validation v1")
    with tempfile.TemporaryDirectory() as temp:
        subprocess.run(["pdfimages","-f","18","-l","18","-j",pdf,Path(temp)/"wall"],check=True)
        rgb = np.asarray(Image.open(Path(temp)/"wall-004.jpg").convert("RGB"), dtype=int)
    if rgb.shape != (788,1312,3):
        raise ValueError("Unexpected CCSA figure raster")
    # Plot boundary in the original JPEG: x=59..1296 spans 0..150 ms,
    # y=741..35 spans 0..800 kN. Use only the loaded interval to avoid
    # axes/legend and keep graph values explicitly approximate.
    times = np.arange(5,66,dtype=float)
    curves = np.full((len(times),2),np.nan)
    for i,ms in enumerate(times):
        x = round(59+ms*(1296-59)/150)
        pix = rgb[100:732,x-2:x+3]
        r,g,b = pix.transpose(2,0,1)
        masks = [(r-b>16)&(r-g>6), (pix.mean(axis=2)<120)&(np.ptp(pix,axis=2)<18)]
        for j,mask in enumerate(masks):
            rows = np.nonzero(mask)[0]
            if len(rows):
                curves[i,j]=(741-100-np.median(rows))*800/(741-35)
    return times,curves


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report",type=Path)
    p.add_argument("history",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args()
    times,curves=reference(args.report)
    data=np.genfromtxt(args.history,names=True,delimiter=",")
    grid=np.arange(0,data["time_s"][-1],.0001)
    raw=np.interp(grid,data["time_s"],(data["wall1_FNX"]+data["wall2_FNX"])/1000)
    filt=sosfiltfilt(butter(2,2.0775*60,fs=10000,output="sos"),raw,padtype="constant",padlen=500)
    model_ms=1000*(grid+data["contact_time_s"][0])
    case=np.interp(times,model_ms,filt)
    args.output.mkdir(parents=True,exist_ok=True)
    with (args.output/"56kmh-wall-reference.csv").open("w",newline="") as f:
        w=csv.writer(f,lineterminator="\n")
        w.writerow(["ms","test_5677_approx_kN","ccsa_fe_approx_kN","opencourant_cfc60_kN"])
        for t,(test,fe),our in zip(times,curves,case):
            w.writerow([int(t),round(test) if np.isfinite(test) else "",round(fe) if np.isfinite(fe) else "",round(our,2)])
    os.environ.setdefault("MPLCONFIGDIR",str(args.report.resolve().parent/"mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7.6,4.2),layout="constrained")
    ax.plot(model_ms,filt,color="#244e61",lw=2,label="OpenCourant · CFC 60")
    for col,label,color in [(0,"Test 5677 · graph reading","#b55939"),(1,"CCSA LS-DYNA · graph reading","#66625c")]:
        ax.plot(times,curves[:,col],color=color,lw=1.3,marker=".",ms=3,label=label)
    ax.set(xlim=(0,85),ylim=(0,700),xlabel="Time (ms)",ylabel="Total frontal barrier force (kN)",
           title="56 km/h full-width impact")
    ax.grid(alpha=.18);ax.spines[["right","top"]].set_visible(False);ax.legend(frameon=False)
    fig.savefig(args.output/"56kmh-wall-reference.png",dpi=155)
    print("CFC60 peak (ms, kN)",model_ms[np.argmax(filt)],filt.max())
    print("1 ms graph peaks",[(times[np.nanargmax(y)],np.nanmax(y)) for y in curves.T])


if __name__=="__main__":
    main()
