"""fp_night.py — the overnight run for the Short on this PC. Standard library only.

  python fp_night.py <blender.exe> <ffmpeg.exe> <samples> [sim folder under fp\\]

1. renders the real-speed frames for the replay at the end (fp\\short\\film_times_rt.json -> frames\\s_00600.png ...),
2. then hands over to fp_short_run.py, which renders the frames still missing from the main film (second pass).
Blender is started again every 60 frames. To stop: create fp\\short\\STOP, then end blender.exe. Progress: fp\\short\\run.log, render.log.
"""
import subprocess, os, sys, json, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); J = lambda *a: os.path.join(ROOT, *a)
BL, FF, SAMPLES = sys.argv[1], sys.argv[2], sys.argv[3]; SIM = sys.argv[4] if len(sys.argv) > 4 else "sim_g1"
SH = J("fp", "short"); FR = J("fp", "short", "frames"); TIMES = J("fp", "short", "film_times_rt.json"); LOW = 0x00004000 | 0x08000000
frame = lambda i: os.path.join(FR, f"s_{i:05d}.png")

def log(*a):
    with open(os.path.join(SH, "run.log"), "a", encoding="utf-8") as f: f.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")

def missing():
    out = []
    for i, _ in json.load(open(TIMES)):
        p = frame(int(i))
        if os.path.exists(p) and os.path.getsize(p) < 300_000: os.remove(p); log("removed empty frame", i)
        if not os.path.exists(p): out.append(int(i))
    return out

log("night run start")
fails = 0
while fails < 4:
    m = missing()
    if not m: break
    if os.path.exists(os.path.join(SH, "STOP")): log("STOP file found, ending"); sys.exit(0)
    args = [BL, "-b", "-P", J("scripts", "fp_render.py"), "--", "--geo", J("data", "fp", "nose.npz"), "--tex", J("data", "fp", "panel.png"), "--world", J("data", "fp"), "--sim", J("fp", SIM),
            "--out", FR, "--tag", "s", "--tfile", TIMES, "--persistent", "1", "--res", "1080x1920", "--samples", SAMPLES, "--device", "OPTIX", "--max_frames", "60"]
    log("real-speed frames, failures", fails, "to render", len(m))
    with open(os.path.join(SH, "render.log"), "a") as lf: rc = subprocess.call(args, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, creationflags=LOW)
    left = len(missing()); log("blender exit", rc, "rendered", len(m) - left)
    if rc != 0 or left >= len(m): fails += 1
if missing(): log("real-speed frames: gave up, still missing", len(missing()))
rc = subprocess.call([sys.executable, J("scripts", "fp_short_run.py"), BL, FF, SAMPLES, SIM], cwd=ROOT, creationflags=LOW); log("fp_short_run exit", rc)
log("night run done")
