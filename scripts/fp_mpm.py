"""fp_mpm.py — crash simulation of the forward fuselage and cockpit for the first-person shot.
Same method and kernels as mpm.py (MLS-MPM, Hu et al. 2018, on the free Taichi runtime; J2 elastic-plastic metal with
ductile failure, failed material becomes frictional debris), but at close-up resolution and high-speed-camera rate:
every vertex of the cockpit mesh (fp_geo.py) is a material point, grid 2 cm, real aluminium wave speed, thousands of frames a second.
The fuselage aft of the cockpit is not simulated: its cut edge is driven on at the aircraft's speed (10 tonnes behind it).

  python fp_mpm.py nose.npz out_dir '{"arch":"cuda"}'
Output: x.npy (T,N,3) float32 world positions, ep.npy (T,N) uint8 plastic strain x100, fail.npy (N,) frame of failure (inf never),
meta.json with fps and t0 (time of frame 0 in seconds; 0 = first contact with the ground)."""
import sys, json, time, os
import numpy as np
import taichi as ti
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fp_pose

CFG = dict(dx=0.02, fps=5000, t0=-0.001, t1=0.040, cfl=0.35, c0=5000.0, nu=0.30, gravity=9.81, mu_ground=0.6, debris_friction=0.9,
           seed=5, threads=4, arch="cpu", gpu_gb=3.0, strength=0.25, ductility=1.0, zrel=0.15, seam=1.0, seam_width=0.02, kin_mass=300.0)
# part -> (kg per m2 of surface, yield MPa for a 2 cm cell, hardening MPa, failure strain, wave speed as a fraction of c0, spall = tension limit / yield)
MAT = dict(
    radome=(4, 9, 0, 0.04, 0.5, 0.8),            # glass-fibre shell: weak, brittle
    skin=(8, 30, 40, 0.18, 1.0, 2.5),            # 2024 aluminium skin + stringers, ~3 mm equivalent
    glass=(30, 80, 0, 0.03, 0.35, 0.3),          # 25 mm stretched acrylic: ~75 MPa tensile, a few % strain at break (spall 0.3 = 72 MPa uniaxial)
    floor=(10, 30, 40, 0.18, 1.0, 2.5), bulkhead=(12, 45, 40, 0.18, 1.0, 2.5), frame=(20, 60, 60, 0.20, 1.0, 2.5),
    panel=(25, 30, 30, 0.20, 1.0, 2.5), glareshield=(6, 9, 10, 0.30, 0.5, 2.5), pedestal=(20, 30, 30, 0.20, 1.0, 2.5),
    yoke=(40, 90, 60, 0.25, 1.0, 2.5), seat=(15, 15, 15, 0.50, 0.6, 2.5), avionics=(40, 30, 30, 0.25, 1.0, 2.5),
    gear=(150, 150, 100, 0.60, 1.0, 2.5),
)


def run(geo, outdir, cfg):
    G = np.load(geo); PARTS = [str(n) for n in G["part_names"]]; part = G["vpart"]; area = G["varea"].astype(np.float32)
    W0, R0, T0, vel = fp_pose.place(G["verts"]); t0 = float(cfg["t0"]); t1 = float(cfg["t1"])
    x0 = (W0 + vel * t0).astype(np.float32); N = len(x0); vel0 = vel.astype(np.float32)
    dx = float(cfg["dx"]); inv_dx = 1.0 / dx; c0 = float(cfg["c0"]); nu = float(cfg["nu"]); rng = np.random.default_rng(cfg["seed"])
    areal = np.zeros(N, np.float32); yld = np.zeros(N, np.float32); hard = np.zeros(N, np.float32); epf = np.zeros(N, np.float32)
    cw = np.ones(N, np.float32); spl = np.full(N, 2.5, np.float32)
    k = 0.02 / dx * float(cfg["strength"])
    for i, nme in enumerate(PARTS):
        # 'strength' stands for thin-wall collapse: a 3 mm skin smeared over a 2 cm cell would otherwise carry its full squash load.
        # Thick solid parts (acrylic, gear leg, control columns) do not buckle like that and keep their full strength.
        kk = 0.02 / dx if nme in ("glass", "gear", "yoke") else k
        m = part == i; a = MAT[nme]; areal[m] = a[0]; yld[m] = a[1] * 1e6 * kk; hard[m] = a[2] * 1e6 * kk; epf[m] = a[3]; cw[m] = a[4]; spl[m] = a[5]
    if float(cfg["seam"]) > 0 and "seam" in G.files:
        w = np.clip(1.0 - G["seam"] / float(cfg["seam_width"]), 0, 1) * float(cfg["seam"]); epf *= 1 - 0.6 * w; yld *= 1 - 0.3 * w
    epf *= rng.uniform(0.6, 1.4, N).astype(np.float32) * float(cfg["ductility"]); yld *= rng.uniform(0.85, 1.15, N).astype(np.float32)
    pmass = areal * area; pvol = area * dx; rho = areal / dx
    M = rho * (c0 * cw) ** 2
    Kp = (M * (1 + nu) / (3 * (1 - nu))).astype(np.float32); Gp = (M * (1 - 2 * nu) / (2 * (1 - nu))).astype(np.float32)
    dt = cfg["cfl"] * dx / (c0 + 1.2 * np.linalg.norm(vel0)); fps = float(cfg["fps"])
    sub = int(np.ceil((1.0 / fps) / dt)); dt = (1.0 / fps) / sub; T = int(round((t1 - t0) * fps)) + 1
    travel = vel * (t1 - t0); lo = x0.min(0); hi = x0.max(0)
    origin = np.array([lo[0] - 1.0, lo[1] - 3.5, -4 * dx], np.float32)
    size = np.array([hi[0] + travel[0] + 3.0, hi[1] + 3.5, hi[2] + 0.6]) - origin
    B = 8; nb = [int(np.ceil(s / dx / B)) + 1 for s in size]
    print(f"N={N} dx={dx} dt={dt:.2e} substeps/frame={sub} frames={T} blocks={nb} mass={pmass.sum():.0f} kg  yield strain skin={30e6 * k / (400 * c0 * c0 * 0.743 * 0.02 / dx):.4f}", flush=True)

    if cfg.get("arch", "cpu") == "cuda": ti.init(arch=ti.cuda, device_memory_GB=float(cfg["gpu_gb"]), default_fp=ti.f32, verbose=False)
    else: ti.init(arch=ti.cpu, cpu_max_num_threads=int(cfg["threads"]), default_fp=ti.f32, verbose=False)
    x = ti.Vector.field(3, ti.f32, N); v = ti.Vector.field(3, ti.f32, N); C = ti.Matrix.field(3, 3, ti.f32, N)
    sig = ti.Matrix.field(3, 3, ti.f32, N); Jf = ti.field(ti.f32, N); ep = ti.field(ti.f32, N); failed = ti.field(ti.i32, N)
    mass = ti.field(ti.f32, N); vol = ti.field(ti.f32, N); Kf = ti.field(ti.f32, N); Gf = ti.field(ti.f32, N); yf = ti.field(ti.f32, N); hf = ti.field(ti.f32, N)
    ef = ti.field(ti.f32, N); sf = ti.field(ti.f32, N); kin = ti.field(ti.i32, N); alive = ti.field(ti.i32, N)
    grid_v = ti.Vector.field(3, ti.f32); grid_m = ti.field(ti.f32)
    top = ti.root.pointer(ti.ijk, nb); top.dense(ti.ijk, B).place(grid_v, grid_m)
    x.from_numpy(x0); v.from_numpy(np.tile(vel0, (N, 1))); mass.from_numpy(pmass); vol.from_numpy(pvol); Kf.from_numpy(Kp); Gf.from_numpy(Gp)
    yf.from_numpy(yld); hf.from_numpy(hard); ef.from_numpy(epf); sf.from_numpy(spl); kin.from_numpy(G["kin"].astype(np.int32)); Jf.fill(1.0); alive.fill(1)
    org = ti.Vector(list(map(float, origin))); gmax = ti.Vector([float(n * B - 4) for n in nb]); V0 = ti.Vector(list(map(float, vel0)))
    grav = float(cfg["gravity"]); mug = float(cfg["mu_ground"]); dfr = float(cfg["debris_friction"]); zrel = float(cfg["zrel"]); kmass = float(cfg["kin_mass"])
    kground = int(round(-origin[2] / dx))
    I3 = ti.Matrix([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    @ti.kernel
    def p2g():
        for p in x:
            if alive[p] == 0: continue
            L = C[p]; D = 0.5 * (L + L.transpose()); W = 0.5 * (L - L.transpose())
            trD = D.trace()
            Jn = Jf[p] * (1.0 + dt * trD)
            s = sig[p]
            if failed[p] == 1:
                Jn = ti.min(Jn, 1.0)
                pr = Kf[p] * (1.0 - Jn)
                s_dev = ti.Matrix.zero(ti.f32, 3, 3)
                if pr > 0:
                    tr = s + dt * (2.0 * Gf[p] * (D - trD / 3.0 * I3) + W @ s - s @ W)
                    sd = tr - tr.trace() / 3.0 * I3
                    q = ti.sqrt(1.5 * (sd * sd).sum()) + 1e-9
                    s_dev = sd * ti.min(1.0, dfr * pr / q)
                s = s_dev - pr * I3
            else:
                tr = s + dt * (2.0 * Gf[p] * (D - trD / 3.0 * I3) + Kf[p] * trD * I3 + W @ s - s @ W)
                pm = tr.trace() / 3.0
                sd = tr - pm * I3
                q = ti.sqrt(1.5 * (sd * sd).sum()) + 1e-9
                ys = yf[p] + hf[p] * ep[p]
                if q > ys:
                    ep[p] += (q - ys) / (3.0 * Gf[p] + hf[p])
                    sd *= (yf[p] + hf[p] * ep[p]) / q
                s = sd + pm * I3
                if ep[p] > ef[p] or pm > sf[p] * yf[p]:
                    failed[p] = 1; s = ti.Matrix.zero(ti.f32, 3, 3); Jn = 1.0
            sig[p] = s; Jf[p] = Jn
            mp = mass[p]
            if kin[p] == 1: mp *= kmass                     # the driven edge outweighs whatever pushes on it
            Xp = (x[p] - org) * inv_dx
            base = int(Xp - 0.5); fx = Xp - base
            w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1.0) ** 2, 0.5 * (fx - 0.5) ** 2]
            affine = (-dt * 4.0 * inv_dx * inv_dx * vol[p] * Jn) * s + mp * C[p]
            for i, j, k in ti.static(ti.ndrange(3, 3, 3)):
                off = ti.Vector([i, j, k]); dpos = (off.cast(ti.f32) - fx) * dx
                wt = w[i][0] * w[j][1] * w[k][2]
                grid_v[base + off] += wt * (mp * v[p] + affine @ dpos)
                grid_m[base + off] += wt * mp

    @ti.kernel
    def clear():
        for I in ti.grouped(grid_m):
            grid_m[I] = 0.0; grid_v[I] = ti.Vector.zero(ti.f32, 3)

    @ti.kernel
    def grid_op():
        for I in ti.grouped(grid_m):
            m = grid_m[I]
            if m > 1e-12:
                u = grid_v[I] / m
                u.z -= dt * grav
                if I.z <= kground - 1 and u.z < 0:      # the node plane one below z = 0: a particle feels the ground about half a cell early
                    vn = -u.z; u.z = 0.0
                    vt = ti.sqrt(u.x * u.x + u.y * u.y) + 1e-9
                    f = ti.max(0.0, 1.0 - mug * vn / vt)
                    u.x *= f; u.y *= f
                grid_v[I] = u

    @ti.kernel
    def g2p():
        for p in x:
            if alive[p] == 0: continue
            if kin[p] == 1:
                if x[p].z < zrel: kin[p] = 0                # about to reach the ground: let it crush like the rest
                else:
                    v[p] = V0; C[p] = ti.Matrix.zero(ti.f32, 3, 3); x[p] += dt * V0
                    continue
            Xp = (x[p] - org) * inv_dx
            base = int(Xp - 0.5); fx = Xp - base
            w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1.0) ** 2, 0.5 * (fx - 0.5) ** 2]
            nv = ti.Vector.zero(ti.f32, 3); nC = ti.Matrix.zero(ti.f32, 3, 3)
            for i, j, k in ti.static(ti.ndrange(3, 3, 3)):
                off = ti.Vector([i, j, k]); dpos = off.cast(ti.f32) - fx
                wt = w[i][0] * w[j][1] * w[k][2]
                g = grid_v[base + off]
                nv += wt * g; nC += 4.0 * inv_dx * wt * g.outer_product(dpos)
            v[p] = nv; C[p] = nC; x[p] += dt * nv
            Xn = (x[p] - org) * inv_dx
            if Xn.x < 3 or Xn.y < 3 or Xn.z < 2 or Xn.x > gmax.x or Xn.y > gmax.y or Xn.z > gmax.z:
                alive[p] = 0

    os.makedirs(outdir, exist_ok=True)
    X = np.lib.format.open_memmap(os.path.join(outdir, "x.npy"), mode="w+", dtype=np.float32, shape=(T, N, 3))
    EP = np.lib.format.open_memmap(os.path.join(outdir, "ep.npy"), mode="w+", dtype=np.uint8, shape=(T, N))
    tfail = np.full(N, np.inf, np.float32); X[0] = x0; tw = time.time(); done = T
    for f in range(1, T):
        top.deactivate_all()
        for _ in range(sub):
            clear(); p2g(); grid_op(); g2p()
        xn = x.to_numpy(); X[f] = xn; e = ep.to_numpy(); EP[f] = np.clip(e * 100, 0, 250).astype(np.uint8)
        fl = failed.to_numpy() == 1; tfail[fl & ~np.isfinite(tfail)] = f
        if f % 10 == 0 or f < 3:
            sp = np.linalg.norm(v.to_numpy(), axis=1)
            print(f"frame {f}/{T} t={(t0 + f / fps) * 1e3:.1f} ms wall={time.time() - tw:.0f}s mean|v|={sp.mean():.1f} max|v|={sp.max():.0f} failed={fl.mean() * 100:.1f}% "
                  f"ep>0.02={np.mean(e > 0.02) * 100:.1f}% kin={int(kin.to_numpy().sum())} alive={alive.to_numpy().mean() * 100:.2f}%", flush=True)
            if not np.isfinite(sp).all() or sp.max() > 5000: print("UNSTABLE", flush=True); done = f; break
    X.flush(); EP.flush(); np.save(os.path.join(outdir, "fail.npy"), tfail)
    json.dump(dict(cfg, dt=dt, sub=sub, N=N, frames=done, vel=vel0.tolist(), R0=R0.tolist(), T0=T0.tolist(), pose=fp_pose.POSE), open(os.path.join(outdir, "meta.json"), "w"))
    print("saved", outdir, flush=True)


if __name__ == "__main__":
    cfg = dict(CFG)
    if len(sys.argv) > 3: cfg.update(json.loads(sys.argv[3]))
    run(sys.argv[1], sys.argv[2], cfg)
