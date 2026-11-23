"""Master EP02, then check the encoded soundtrack, all decoded frames and cuts."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import numpy as np
from ep02_sound import SR,phone_db,read_audio


def run(args):
    result=subprocess.run(args,capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors="replace")[-4000:])
    return result.stderr.decode(errors="replace")


def measure(path):
    log=run(["ffmpeg","-nostdin","-hide_banner","-i",str(path),"-vn","-af",
             "loudnorm=I=-13:TP=-1.9:LRA=11:print_format=json","-f","null","-"])
    return json.loads(re.findall(r'\{\s*"input_i".*?\}',log,re.S)[-1])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","silent","mix","output","qa"):p.add_argument(name,type=Path)
    a=p.parse_args()
    frames=json.loads(a.manifest.read_text())["frames"]
    first=measure(a.mix)
    fields={"measured_I":"input_i","measured_LRA":"input_lra","measured_TP":"input_tp",
            "measured_thresh":"input_thresh","offset":"target_offset"}
    options=":".join(f"{key}={first[src]}" for key,src in fields.items())
    base=f"loudnorm=I=-13:TP=-1.9:LRA=11:{options}:linear=true"
    gain=0.0
    ceiling=-1.9
    # Check the delivered AAC. Sparse impacts can cause loudnorm to hit its
    # peak ceiling before reaching integrated loudness. Always re-encode
    # from the original float mix when adjusting gain and the limiter.
    for _ in range(4):
        limiter=f"alimiter=limit={10**(ceiling/20):.6f}:attack=5:release=60:level=0:latency=1"
        af=f"{base},volume={gain:.3f}dB,aresample=192000,{limiter},aresample=48000"
        run(["ffmpeg","-nostdin","-hide_banner","-y","-i",str(a.silent),"-i",str(a.mix),
             "-map","0:v:0","-map","1:a:0","-c:v","copy","-af",af,
             "-c:a","aac","-b:a","256k","-ar","48000","-movflags","+faststart",str(a.output)])
        after=measure(a.output)
        error=-13-float(after["input_i"])
        overshoot=float(after["input_tp"])+1.5
        if abs(error)<=.4 and overshoot<=0:
            break
        gain+=error
        if overshoot>0:
            ceiling-=overshoot+.15
    run(["ffmpeg","-nostdin","-v","error","-xerror","-i",str(a.output),"-f","null","-"])
    facts=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-of","json",str(a.output)]))
    video=next(s for s in facts["streams"] if s["codec_type"]=="video")
    if (video["width"],video["height"],video["r_frame_rate"],int(video["nb_frames"]))!=(1080,1920,"30/1",len(frames)):
        raise ValueError("Unexpected video format, frame count or frame rate")
    pcm=read_audio(a.output)
    checks=[]
    for i in range(1,len(frames)):
        d=frames[i]
        if d["phase"] not in ("drive","real") or d["local"]!=d["contactFrame"]:continue
        sec=i/30
        # Equal windows immediately before and after this picture contact.
        start=round(sec*SR); w=round(.12*SR)
        before=phone_db(pcm[max(0,start-w):start])
        hit=phone_db(pcm[start:start+w])
        checks.append({"frame":i,"phase":d["phase"],"pre_dbfs":before if np.isfinite(before) else None,
                       "impact_dbfs":hit,"delta_db":hit-before if np.isfinite(before) else None,
                       "delta_at_least_6db":bool(np.isfinite(hit) and hit>=before+6)})
    # Disk-light frame scan. Repeated held footage and the eight black frames
    # are separately labelled by the timeline.
    cmd=["ffmpeg","-v","error","-i",str(a.output),"-map","0:v:0","-f","framemd5","-"]
    hashes=[s.split(",")[-1].strip() for s in subprocess.check_output(cmd,text=True).splitlines() if not s.startswith("#")]
    repeats=[i for i in range(1,len(hashes)) if hashes[i]==hashes[i-1] and frames[i]["phase"] in ("drive","real")]
    report=dict(frame_count=len(hashes),encoded_bytes=a.output.stat().st_size,measured_lufs=float(after["input_i"]),
                true_peak_dbtp=float(after["input_tp"]),phone_band=checks,unexpected_exact_repeats=repeats)
    a.qa.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    expected_contacts=len({f["initial"] for f in frames if f["phase"]=="drive"})+1
    if report["encoded_bytes"]>=90_000_000 or report["true_peak_dbtp"]>-1.5 or abs(report["measured_lufs"]+13)>1 or repeats or len(checks)!=expected_contacts or not all(c["delta_at_least_6db"] for c in checks):
        raise ValueError(f"Inspect failed release measurements in {a.qa}")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
