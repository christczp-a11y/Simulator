"""fp_short_run.py — renders the vertical Short on this PC and puts it together. Standard library only.

  python fp_short_run.py <blender.exe> <ffmpeg.exe> <samples> [sim folder under fp\\]

Pass A renders every second frame (when it is through, a 15 fps version is written), pass B the rest, then the 30 fps film.
Frames already on disk are never rendered twice, so the run can be stopped and started again. Blender is started again every
60 frames (graphics memory creeps up in one process and runs out after about 100). A pass gives up after 4 runs that crashed or
added no frame. To stop: create an empty file fp\\short\\STOP, then end blender.exe in the task manager.
Progress: fp\\short\\run.log (this script), fp\\short\\render.log (Blender).
"""
import subprocess, os, sys, json, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); J = lambda *a: os.path.join(ROOT, *a)
BL, FF, SAMPLES = sys.argv[1], sys.argv[2], sys.argv[3]; SIM = sys.argv[4] if len(sys.argv) > 4 else "sim_g1"
SH = J("fp", "short"); FR = J("fp", "short", "frames"); OUT = J("out", "fp-short"); TAG = "s"; TIMES = J("fp", "short", "film_times.json")
os.makedirs(FR, exist_ok=True); os.makedirs(OUT, exist_ok=True)
N = len(json.load(open(TIMES))); frame = lambda i: os.path.join(FR, f"{TAG}_{i:05d}.png")
LOW = 0x00004000 | 0x08000000                                      # below normal priority, no console window

def log(*a):
    with open(os.path.join(SH, "run.log"), "a", encoding="utf-8") as f: f.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")

def missing(a, b):
    out = []
    for i in range(N):
        if i % b != a: continue
        p = frame(i)
        if os.path.exists(p) and os.path.getsize(p) < 300_000: os.remove(p); log("removed empty frame", i)      # a real frame is 2 to 3 MB
        if not os.path.exists(p): out.append(i)
    return out

def render(a, b):
    args = [BL, "-b", "-P", J("scripts", "fp_render.py"), "--", "--geo", J("data", "fp", "nose.npz"), "--tex", J("data", "fp", "panel.png"), "--world", J("data", "fp"), "--sim", J("fp", SIM),
            "--out", FR, "--tag", TAG, "--tfile", TIMES, "--stride", f"{a},{b}", "--persistent", "1", "--res", "1080x1920", "--samples", SAMPLES, "--device", "OPTIX", "--max_frames", "60"]
    with open(os.path.join(SH, "render.log"), "a") as lf: return subprocess.call(args, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, creationflags=LOW)

def film(name, step):
    """step 1: all frames at 30 fps; step 2: every second frame held for two (15 fps look), for a first viewing"""
    lst = os.path.join(SH, "list.txt")
    with open(lst, "w") as f:
        for i in range(0, N, step): f.write("file '%s'\nduration %.6f\n" % (frame(i).replace("\\", "/"), step / 30.0))
    out = os.path.join(OUT, name)
    if os.path.exists(out) and os.path.getsize(out) > 1_000_000 and os.path.getmtime(out) > max(os.path.getmtime(frame(i)) for i in range(0, N, step)): log("film", name, "is up to date"); return
    cmd = [FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", os.path.join(SH, "overlay.mov"), "-filter_complex",
           "[0:v]fps=30,tpad=stop_mode=clone:stop_duration=1.8[b];[b][1:v]overlay=eof_action=pass[v]", "-map", "[v]", "-r", "30", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, creationflags=LOW); log("film", name, "exit", r.returncode, (r.stderr or "")[-300:], os.path.getsize(out) if os.path.exists(out) else 0)

log("start", "frames", N, "samples", SAMPLES, "sim", SIM)
for a, b, name, step in ((0, 2, "learjet-cockpit-short-15fps-first-look.mp4", 2), (0, 1, "learjet-cockpit-short-1080x1920.mp4", 1)):
    fails = 0
    while fails < 4:                                               # Blender renders 60 frames and leaves (exit 0); only a run that added no frame, or crashed, counts as a failure
        m = missing(a, b)
        if not m: break
        if os.path.exists(os.path.join(SH, "STOP")): log("STOP file found, ending"); sys.exit(0)
        log("pass", f"{a},{b}", "failures", fails, "frames to render", len(m)); rc = render(a, b); left = len(missing(a, b)); log("blender exit", rc, "rendered", len(m) - left)
        if rc != 0 or left >= len(m): fails += 1
    m = missing(a, b)
    if m: log("gave up, still missing", len(m), "frames, first", m[:5]); sys.exit(1)
    film(name, step)
log("done")
