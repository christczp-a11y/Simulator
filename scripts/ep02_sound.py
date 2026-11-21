"""Measure the supplied ElevenLabs assets and mix them to measured EP02 picture cues."""
import argparse
import csv
import json
import math
from pathlib import Path
import subprocess

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, resample_poly, sosfilt

ROOT=Path(__file__).resolve().parents[1]
SR=48000
PHONE=butter(4,300,btype="highpass",fs=SR,output="sos")


def read_audio(path):
    run=subprocess.run(["ffmpeg","-v","error","-i",str(path),"-f","f32le","-ac","2","-ar",str(SR),"-"],
                       stdout=subprocess.PIPE,check=True)
    return np.frombuffer(run.stdout,dtype="<f4").reshape(-1,2).copy()


def rms_db(x):
    rms=float(np.sqrt(np.mean(x.astype(float)**2))) if x.size else 0.0
    return 20*math.log10(rms) if rms>0 else -math.inf


def phone_db(x):
    return rms_db(sosfilt(PHONE,x,axis=0))


def impact_onset(x):
    # Some generated clips have a long quiet lead. Trim in source time,
    # before stretching, so the first audible transient lands on contact.
    block=round(.005*SR)
    length=len(x)//block*block
    filtered=sosfilt(PHONE,x[:length],axis=0)
    rms=np.sqrt(np.mean(filtered.reshape(-1,block,2)**2,axis=(1,2)))
    if not len(rms) or rms.max()<=1e-12:
        raise ValueError("Impact clip has no measurable phone-band signal")
    first=np.flatnonzero(rms>=rms.max()*10**(-15/20))[0]
    return int(max(0,first-1)*block)


def measure_assets(dest):
    with dest.open("w",newline="") as f:
        w=csv.writer(f,lineterminator="\n")
        w.writerow(["asset","seconds","full_rms_dbfs","above_300hz_rms_dbfs"])
        for path in sorted((ROOT/"audio").glob("*.mp3")):
            x=read_audio(path)
            w.writerow([path.stem,f"{len(x)/SR:.4f}",f"{rms_db(x):.2f}",f"{phone_db(x):.2f}"])


def ir_tail():
    ir=read_audio(ROOT/"audio/ir_field_a.mp3")
    # Follow EP01's direct-shot removal and use the remaining open-field decay.
    peak=int(np.argmax(np.abs(ir).max(axis=1)))
    tail=ir[peak+round(.07*SR):peak+round(1.35*SR)].copy()
    tail*=np.linspace(1,0,len(tail))[:,None]
    norm=np.sqrt((tail**2).sum(axis=0))
    if np.min(norm)==0:raise ValueError("Empty outdoor IR")
    return tail/norm


def mix(manifest,output,cue_file):
    frames=json.loads(manifest.read_text())["frames"]
    total=round(len(frames)*SR/30)
    track=np.zeros((total,2),np.float32)
    ir=ir_tail();cues=[]
    sample=lambda s:round(s*SR)
    def cue(n,sec,duration,gain,rate=1.0,space=False):
        remaining=min(sample(duration),total-sample(sec))
        if remaining<2:
            return
        path=ROOT/"audio"/(n+".mp3")
        x=read_audio(path)
        trim=impact_onset(x) if n in ("ep02_crush","n2_metal_tear","ep02_glass","n_glass") else 0
        x=x[trim:]
        if rate!=1:
            # Lower sample playback rate stretches the clip and drops its pitch.
            x=resample_poly(x,100,round(100*rate),axis=0)
        x=x[:remaining].copy()
        if len(x)<2:return
        attack=min(sample(.004),len(x)//3); release=min(sample(.035),len(x)//3)
        if attack:x[:attack]*=np.linspace(0,1,attack)[:,None]
        if release:x[-release:]*=np.linspace(1,0,release)[:,None]
        if space:
            wet=np.column_stack([fftconvolve(x[:,j],ir[:,j])[:len(x)] for j in range(2)])
            wet*=10**((rms_db(x)-rms_db(wet)-7)/20)
            x+=wet
        scale=10**((gain-rms_db(x))/20)
        track[sample(sec):sample(sec)+len(x)]+=x*scale
        cues.append((sec,sec+len(x)/SR,n,rate,gain,space,trim/SR))
    speeds=sorted(set(f["initial"] for f in frames if f["phase"]=="drive"))
    have=lambda n:(ROOT/"audio"/(n+".mp3")).is_file()
    for speed in speeds:
        idx=[i for i,f in enumerate(frames) if f["phase"]=="drive" and f["initial"]==speed]
        impact=next(i for i in idx if frames[i]["since"]>=0)
        start=idx[0]/30; hit=impact/30
        cue("n_flap",start,.18,-28)
        if have("ep02_drive"):cue("ep02_drive",start,hit-start-.14,-28,space=True)
        cue("n_slowdown",start+.93,min(.22,hit-start-1.02),-26)
        end=(idx[-1]+1)/30
        cue("ep02_crush" if have("ep02_crush") else "n2_metal_tear",hit,min(1.4,end-hit),-13,.33,True)
        at_peak=max((i for i in idx if i>=impact), key=lambda i:abs(frames[i]["g"] or 0))/30
        cue("ep02_glass" if have("ep02_glass") else "n_glass",max(hit+.3,at_peak),min(1.1,end-max(hit+.3,at_peak)),-18,.36,True)
        cue("n_stop",end,.18,-21)
    real=[i for i,f in enumerate(frames) if f["phase"]=="real"]
    hit=next(i for i in real if frames[i]["since"]>=0)/30
    replay_end=(real[-1]+1)/30
    if have("ep02_drive"):cue("ep02_drive",real[0]/30,max(0,hit-real[0]/30-.08),-27,space=True)
    cue("ep02_crush" if have("ep02_crush") else "n2_metal_tear",hit,min(.31,replay_end-hit),-10,space=True)
    if have("ep02_settle"):cue("ep02_settle",replay_end-.065,.065,-23,space=True)
    end=next(i for i,f in enumerate(frames) if f["phase"]=="end")/30
    cue("n_pop",end,.34,-18)
    wavfile.write(output,SR,track)
    with cue_file.open("w",newline="") as f:
        w=csv.writer(f,lineterminator="\n"); w.writerow(["start_s","end_s","clip","playback_rate","target_rms_dbfs","outdoor_ir","source_trim_s"])
        w.writerows([(f"{a:.3f}",f"{b:.3f}",n,r,g,sp,f"{trim:.3f}") for a,b,n,r,g,sp,trim in sorted(cues)])


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="action",required=True)
    m=sub.add_parser("assets");m.add_argument("output",type=Path)
    m=sub.add_parser("mix");m.add_argument("manifest",type=Path);m.add_argument("output",type=Path);m.add_argument("cues",type=Path)
    a=p.parse_args()
    if a.action=="assets":measure_assets(a.output)
    else:mix(a.manifest,a.output,a.cues)
