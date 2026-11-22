"""Render a solved EP02 speed case, including its camera proof or the film plates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
WORK = ROOT / "work"
OUT = ROOT / "out/ep02-car-speeds"
STILL_NAMES = ["approach", "contact", "20ms", "40ms", "60ms", "100ms"]


def script(name, *args):
    subprocess.run([sys.executable, SCRIPTS / name, *args], check=True)


def comparison(head, fixed, dest, width):
    # The two images are synchronised frame-for-frame. Repeat the complete
    # 0.6 s replay three times so a viewer can follow each camera.
    style = "fontcolor=white:fontsize=22:y=14"
    filters = (f"[0:v][1:v]hstack,pad=iw:ih+56:0:56:color=0x121212,"
               f"drawtext=text='Head response':x=16:{style},"
               f"drawtext=text='Body-mounted':x={width+16}:{style},"
               "loop=loop=2:size=18:start=0,setpts=N/(30*TB),format=yuv420p")
    font_cache=WORK/"font-cache"
    font_cache.mkdir(parents=True,exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-framerate", "30",
                    "-i", head/"%04d.png", "-framerate", "30", "-i", fixed/"%04d.png",
                    "-filter_complex", filters, "-c:v", "libx264", "-crf", "17",
                    "-movflags", "+faststart", dest], check=True,env=os.environ|{"XDG_CACHE_HOME":str(font_cache)})
    subprocess.run(["ffmpeg","-v","error","-xerror","-i",dest,"-f","null","-"],check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("target", choices=["stills","proof","film"])
    p.add_argument("speed", type=int)
    p.add_argument("history", type=Path, help="Merged, CFC-filtered solver history")
    p.add_argument("cache", type=Path)
    p.add_argument("--source", type=Path, default=WORK/"car.npz")
    p.add_argument("--cabin",type=Path,help="Transfer the solved shell motion to this editable v2j cabin")
    p.add_argument("--review-dir",type=Path,default=OUT/"stills",help="Destination of inspection views and measurements")
    p.add_argument("--picture-root",type=Path,default=WORK/"picture")
    p.add_argument("--blender", type=Path, default=WORK/"blender-4.5.16-linux-x64/blender")
    p.add_argument("--width", type=int)
    p.add_argument("--samples", type=int)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--gpu", action="store_true")
    args = p.parse_args()
    width = args.width or (1080 if args.target=="film" else 360)
    samples = args.samples or (32 if args.target=="film" else 8)
    if width <= 0 or round(width*16/9)%2 or samples < 1 or args.threads < 1:
        p.error("Specify a positive resolution with an even height, samples and thread count.")
    case = args.picture_root/str(args.speed)
    case.mkdir(parents=True, exist_ok=True)
    clearance = case/"landmarks.csv"
    shots = case/"shots.json"
    script("ep02_landmarks.py",args.cache,clearance)
    script("ep02_shots.py",args.history,clearance,shots)
    plan = json.loads(shots.read_text())
    measured = plan["head"]["main"][0]["speed_kmh"]
    if abs(measured-args.speed) > .2:
        raise ValueError(f"Requested case is {args.speed} km/h, history begins at {measured} km/h")
    proof = case/"proof"
    # Resume only a render whose inputs and quality settings match exactly.
    digest=hashlib.sha256(shots.read_bytes())
    inputs=[args.source,SCRIPTS/"ep02_still.py",SCRIPTS/"ep02_sequence.py"]
    if args.cabin:
        inputs.extend([args.cabin,SCRIPTS/"ep02_cabin_motion.py"])
    for path in inputs:
        with path.open("rb") as f:
            digest.update(hashlib.file_digest(f,"sha256").digest())
    for path in sorted(args.cache.glob("frame-*.npz")):
        with np.load(path) as frame:
            digest.update(str(frame["source_hash"]).encode())
    key=digest.hexdigest()
    dest = args.review_dir
    def render(mode, seq, folder, save_scene=False):
        folder.mkdir(parents=True, exist_ok=True)
        signature = dict(shots=key, width=width, samples=samples, mode=mode, sequence=seq)
        stamp = folder/"settings.json"
        if stamp.exists() and json.loads(stamp.read_text()) != signature:
            raise ValueError(f"Render settings changed. Use a fresh image directory for {folder}.")
        stamp.write_text(json.dumps(signature))
        indices = [str(i) for i in range(len(plan[mode][seq])) if not (folder/f"{i:04d}.png").is_file()]
        snapshot = case/("driver-60ms.blend" if args.cabin else "driver-seat.blend")
        if save_scene and not snapshot.exists():
            needed="4" if args.cabin else "0"
            if needed not in indices:
                indices.append(needed)
        if not indices:
            return
        cmd = [args.blender, "-b","-t",str(args.threads),"--python-exit-code","1","-P",
               SCRIPTS/"ep02_sequence.py","--",args.source,args.cache,shots,folder,
               "--mode",mode,"--sequence",seq,"--width",str(width),"--samples",str(samples),"--frames",*indices]
        if args.gpu:
            cmd.append("--gpu")
        if args.cabin:
            cmd.extend(["--cabin",args.cabin])
        if save_scene:
            cmd.extend(["--save-scene",snapshot,"--save-index","4" if args.cabin else "0"])
        with (folder/"blender.log").open("a") as log:
            subprocess.run(cmd, check=True, stdout=log,stderr=subprocess.STDOUT,
                           env=os.environ|{"BLENDER_USER_RESOURCES":str(WORK/"blender-user")})
    if args.target=="film":
        for seq in ("main","real"):
            render("head",seq,case/seq)
        return
    dest.mkdir(parents=True,exist_ok=True)
    prefix=f"{args.speed}kmh"
    script("ep02_camera_review.py",shots,dest,"--prefix",prefix,"--cache",args.cache)
    shutil.copyfile(clearance,dest/f"{prefix}-clearance.csv")
    for mode in ("head","fixed"):
        folder=proof/mode/"stills"
        render(mode,"stills",folder,save_scene=mode=="head")
        for i,name in enumerate(STILL_NAMES):
            shutil.copyfile(folder/f"{i:04d}.png",dest/f"{prefix}-{mode}-{name}.png")
        if args.target=="proof":
            render(mode,"real",proof/mode/"real")
    if args.target=="proof":
        comparison(proof/"head/real",proof/"fixed/real",dest/f"{prefix}-camera-comparison.mp4",width)


if __name__=="__main__":
    main()
