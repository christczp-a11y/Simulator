"""Run a batch of mpm.py configurations one after another and make a quick-look sheet for each.
  python mrun.py <base_dir> '{"name": {cfg...}, ...}' [frames_to_view]"""
import sys, os, json, subprocess, time
base = sys.argv[1]; jobs = json.loads(sys.argv[2]); view = sys.argv[3] if len(sys.argv) > 3 else "20,45,80,130,200,290"
py = sys.executable; sc = os.path.join(base, "scripts"); data = os.path.join(base, "data"); out = os.path.join(base, "mpm")
os.makedirs(out, exist_ok=True)
for name, cfg in jobs.items():
    cfg = dict({"arch": "cuda", "fracture": os.path.join(data, "fracture.npz")}, **cfg)
    t = time.time()
    with open(os.path.join(out, name + ".log"), "w") as log:
        subprocess.run([py, os.path.join(sc, "mpm.py"), os.path.join(data, "sim.npz"), os.path.join(out, name), json.dumps(cfg)], stdout=log, stderr=subprocess.STDOUT)
        log.write(f"\nSIM_SECONDS {time.time()-t:.0f}\n"); log.flush()
        subprocess.run([py, os.path.join(sc, "mview.py"), data, os.path.join(out, name), view, os.path.join(out, name + "_mv.png")], stdout=log, stderr=subprocess.STDOUT)
    open(os.path.join(out, name + ".done"), "w").write("ok")
