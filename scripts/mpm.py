"""Material Point Method crash simulation (MLS-MPM, Hu et al. 2018) on the Taichi runtime (free, open source).
Every lattice particle of the aircraft is a material point: the airframe is an elastic-plastic metal that
dents, buckles and tears (J2 plasticity with a ductile failure strain), failed material becomes loose
frictional debris, fuel is a liquid. No pre-cut fragments: where it breaks is decided by the stress.

  python3 mpm.py sim.npz out_dir '{"dx":0.06}'       (sim.npz only supplies the start pose, parts and velocity)

Output: out_dir/x.npy (T,N,3) float32 positions per 240 fps frame, ep.npy (T,N) uint8 plastic strain (0..250 = 0..2.5),
fail.npy (N,) frame at which a particle failed (inf = never), meta.json."""
import sys, json, time, os
import numpy as np
import taichi as ti

CFG = dict(
    dx=0.06, fps=240, frames=480, cfl=0.35,
    c0=1000.0,                 # P-wave speed used for every solid (m/s); stiffness scales with particle density
    nu=0.30, spacing=0.028,    # lattice spacing: particle volume = spacing^2 * dx (a shell one cell thick)
    gravity=9.81, mu_ground=0.6, debris_friction=0.9,
    origin=(-16.0, -30.0), size=(170.0, 60.0, 26.0),
    seed=3, threads=4,
)
# part -> (yield MPa, hardening MPa, failure strain, kind)   kind 0 metal, 1 liquid fuel
MAT = dict(
    default=(9.0, 12.0, 0.32, 0),
    wing_L=(16.0, 20.0, 0.30, 0), wing_R=(16.0, 20.0, 0.30, 0),
    winglet_L=(8.0, 10.0, 0.30, 0), winglet_R=(8.0, 10.0, 0.30, 0),
    windshield=(6.0, 0.0, 0.05, 0), windows=(6.0, 0.0, 0.05, 0),
    engine_L=(10.0, 12.0, 0.35, 0), engine_R=(10.0, 12.0, 0.35, 0),
    pylon_L=(22.0, 20.0, 0.22, 0), pylon_R=(22.0, 20.0, 0.22, 0),
    core_L=(90.0, 60.0, 0.9, 0), core_R=(90.0, 60.0, 0.9, 0), fan_L=(30.0, 20.0, 0.25, 0), fan_R=(30.0, 20.0, 0.25, 0),
    floor=(10.0, 10.0, 0.25, 0), seats=(7.0, 8.0, 0.35, 0), bulkhead=(12.0, 10.0, 0.25, 0),
    fuel_L=(0, 0, 0, 1), fuel_R=(0, 0, 0, 1),
)


def run(simpath, outdir, cfg):
    d = np.load(simpath)
    PARTS = [str(n) for n in np.load(os.path.join(os.path.dirname(os.path.abspath(simpath)), "pre.npz"))["part_names"]]
    x0 = (d["cen0"][d["frag"]] + d["local"]).astype(np.float32); part = d["part"]; N = len(x0)
    frag = d["frag"]; fmass = d["fmass"]; cnt = np.bincount(frag, minlength=len(fmass))
    vel0 = d["vel"].astype(np.float32); R0 = None
    if cfg.get("pose"):
        # different impact conditions: rebuild the start pose from the model frame (nose +x, up +z), same convention as sim.py
        po = cfg["pose"]; Pz = np.load(os.path.join(os.path.dirname(os.path.abspath(simpath)), "pre.npz"))
        model = (x0 - Pz["model_t"]) @ Pz["model_R"]
        r, pt, yw = (np.radians(po.get(k, v)) for k, v in (("roll_deg", 11.0), ("pitch_deg", -10.0), ("yaw_deg", 3.0)))
        Rx = np.array([[1, 0, 0], [0, np.cos(r), -np.sin(r)], [0, np.sin(r), np.cos(r)]])
        Ry = np.array([[np.cos(-pt), 0, np.sin(-pt)], [0, 1, 0], [-np.sin(-pt), 0, np.cos(-pt)]])
        Rz = np.array([[np.cos(yw), -np.sin(yw), 0], [np.sin(yw), np.cos(yw), 0], [0, 0, 1]])
        R0 = Rz @ Ry @ Rx
        g = np.radians(po.get("path_deg", -18.0)); sp = float(po.get("speed", 70.0))
        vel0 = (np.array([np.cos(g), 0.0, np.sin(g)]) * sp).astype(np.float32)
        w = model @ R0.T
        w[:, 2] += 11.0 * abs(vel0[2]) / cfg["fps"] - w[:, 2].min()          # first contact lands on frame 11, as the edit timeline expects
        w[:, :2] += x0[:, :2].mean(0) - w[:, :2].mean(0)
        x0 = w.astype(np.float32)
    # particle mass: recover from the fragment masses of the rigid version (uniform inside a part)
    try:
        F = np.load(cfg["fracture"]); pmass = F["pmass"].astype(np.float32)
    except Exception:
        pmass = (fmass / np.maximum(cnt, 1))[frag].astype(np.float32)
    rng = np.random.default_rng(cfg["seed"])
    yld = np.zeros(N, np.float32); hard = np.zeros(N, np.float32); epf = np.zeros(N, np.float32); kind = np.zeros(N, np.int32)
    for i, nme in enumerate(PARTS):
        m = part == i; a = MAT.get(nme, MAT["default"])
        k = 0.06 / float(cfg["dx"]) * float(cfg.get("strength", 1.0))     # MAT values are for a 0.06 m thick equivalent shell
        yld[m] = a[0] * 1e6 * k; hard[m] = a[1] * 1e6 * k; epf[m] = a[2]; kind[m] = a[3]
    # panels and seams: the airframe is strong inside a skin panel and weak along the joints between panels (rivet lines),
    # so it tears along seams and comes apart as bent panels rather than as powder. seam.npy = distance to the nearest joint.
    sp = os.path.join(os.path.dirname(os.path.abspath(simpath)), "seam.npy")
    if float(cfg.get("seam", 1.0)) > 0 and os.path.exists(sp):
        w = np.clip(1.0 - np.load(sp) / float(cfg.get("seam_width", 0.05)), 0, 1) * (kind == 0)
        k = float(cfg.get("seam", 1.0))
        epf *= (1 + k * 1.2) * (1 - w) + (1 - k * 0.65) * w; yld *= (1 + k * 0.25) * (1 - w) + (1 - k * 0.3) * w
    # material scatter so tears wander instead of following the lattice
    epf *= rng.uniform(0.6, 1.4, N).astype(np.float32) * float(cfg.get("ductility", 1.0)); yld *= rng.uniform(0.85, 1.15, N).astype(np.float32)

    dx = float(cfg["dx"]); inv_dx = 1.0 / dx; vol0 = float(cfg["spacing"]) ** 2 * dx
    rho = pmass / vol0
    c0 = float(cfg["c0"]); nu = float(cfg["nu"])
    M = rho * c0 * c0
    Kp = (M * (1 + nu) / (3 * (1 - nu))).astype(np.float32); Gp = (M * (1 - 2 * nu) / (2 * (1 - nu))).astype(np.float32)
    liq = kind == 1
    Kp[liq] = rho[liq] * 350.0 ** 2; Gp[liq] = 0.0
    dt = cfg["cfl"] * dx / (c0 + 1.2 * np.linalg.norm(vel0))
    sub = int(np.ceil((1.0 / cfg["fps"]) / dt)); dt = (1.0 / cfg["fps"]) / sub
    ox, oy = cfg["origin"]; oz = -4 * dx; origin = np.array([ox, oy, oz], np.float32)
    B = 8; nb = [int(np.ceil(s / dx / B)) + 1 for s in cfg["size"]]
    print(f"N={N} dx={dx} dt={dt:.2e} substeps/frame={sub} blocks={nb} vol0={vol0:.2e} rho skin={np.median(rho):.0f}", flush=True)

    if cfg.get("arch", "cpu") == "cuda":
        ti.init(arch=ti.cuda, device_memory_GB=float(cfg.get("gpu_gb", 2.5)), default_fp=ti.f32, verbose=False)
    else:
        ti.init(arch=ti.cpu, cpu_max_num_threads=int(cfg["threads"]), default_fp=ti.f32, verbose=False)
    x = ti.Vector.field(3, ti.f32, N); v = ti.Vector.field(3, ti.f32, N); C = ti.Matrix.field(3, 3, ti.f32, N)
    sig = ti.Matrix.field(3, 3, ti.f32, N); Jf = ti.field(ti.f32, N); ep = ti.field(ti.f32, N); failed = ti.field(ti.i32, N)
    mass = ti.field(ti.f32, N); Kf = ti.field(ti.f32, N); Gf = ti.field(ti.f32, N); yf = ti.field(ti.f32, N); hf = ti.field(ti.f32, N)
    ef = ti.field(ti.f32, N); kf = ti.field(ti.i32, N); alive = ti.field(ti.i32, N)
    grid_v = ti.Vector.field(3, ti.f32); grid_m = ti.field(ti.f32)
    top = ti.root.pointer(ti.ijk, nb); top.dense(ti.ijk, B).place(grid_v, grid_m)
    x.from_numpy(x0); v.from_numpy(np.tile(vel0, (N, 1))); mass.from_numpy(pmass); Kf.from_numpy(Kp); Gf.from_numpy(Gp)
    yf.from_numpy(yld); hf.from_numpy(hard); ef.from_numpy(epf); kf.from_numpy(kind); Jf.fill(1.0); alive.fill(1)
    org = ti.Vector(list(map(float, origin))); gmax = ti.Vector([float(n * B - 4) for n in nb])
    grav = float(cfg["gravity"]); mug = float(cfg["mu_ground"]); dfr = float(cfg["debris_friction"])
    kground = int(round(-oz / dx))               # grid layer of the ground plane z = 0
    I3 = ti.Matrix([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    @ti.kernel
    def p2g():
        for p in x:
            if alive[p] == 0: continue
            L = C[p]; D = 0.5 * (L + L.transpose()); W = 0.5 * (L - L.transpose())
            trD = D.trace()
            Jn = Jf[p] * (1.0 + dt * trD)
            s = sig[p]
            if kf[p] == 1 or failed[p] == 1:
                # liquid fuel / loose debris: pressure only when squeezed, never tension
                Jn = ti.min(Jn, 1.0)
                pr = Kf[p] * (1.0 - Jn)
                s_dev = ti.Matrix.zero(ti.f32, 3, 3)
                if kf[p] == 0 and pr > 0:
                    # frictional debris: shear strength proportional to pressure (Drucker-Prager, no cohesion)
                    tr = s + dt * (2.0 * Gf[p] * (D - trD / 3.0 * I3) + W @ s - s @ W)
                    sd = tr - tr.trace() / 3.0 * I3
                    q = ti.sqrt(1.5 * (sd * sd).sum()) + 1e-9
                    s_dev = sd * ti.min(1.0, dfr * pr / q)
                s = s_dev - pr * I3
            else:
                # metal: hypoelastic update (Jaumann rate) + J2 radial return with linear hardening
                tr = s + dt * (2.0 * Gf[p] * (D - trD / 3.0 * I3) + Kf[p] * trD * I3 + W @ s - s @ W)
                pm = tr.trace() / 3.0
                sd = tr - pm * I3
                q = ti.sqrt(1.5 * (sd * sd).sum()) + 1e-9
                ys = yf[p] + hf[p] * ep[p]
                if q > ys:
                    ep[p] += (q - ys) / (3.0 * Gf[p] + hf[p])
                    sd *= (yf[p] + hf[p] * ep[p]) / q
                s = sd + pm * I3
                # ductile failure by plastic strain, spall by hydrostatic tension
                if ep[p] > ef[p] or pm > 2.5 * yf[p]:
                    failed[p] = 1; s = ti.Matrix.zero(ti.f32, 3, 3); Jn = 1.0
            sig[p] = s; Jf[p] = Jn
            Xp = (x[p] - org) * inv_dx
            base = int(Xp - 0.5); fx = Xp - base
            w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1.0) ** 2, 0.5 * (fx - 0.5) ** 2]
            affine = (-dt * 4.0 * inv_dx * inv_dx * vol0 * Jn) * s + mass[p] * C[p]
            for i, j, k in ti.static(ti.ndrange(3, 3, 3)):
                off = ti.Vector([i, j, k]); dpos = (off.cast(ti.f32) - fx) * dx
                wt = w[i][0] * w[j][1] * w[k][2]
                grid_v[base + off] += wt * (mass[p] * v[p] + affine @ dpos)
                grid_m[base + off] += wt * mass[p]

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
                if I.z <= kground and u.z < 0:
                    vn = -u.z; u.z = 0.0
                    vt = ti.sqrt(u.x * u.x + u.y * u.y) + 1e-9
                    f = ti.max(0.0, 1.0 - mug * vn / vt)
                    u.x *= f; u.y *= f
                grid_v[I] = u

    @ti.kernel
    def g2p():
        for p in x:
            if alive[p] == 0: continue
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

    T = int(cfg["frames"])
    os.makedirs(outdir, exist_ok=True)
    X = np.lib.format.open_memmap(os.path.join(outdir, "x.npy"), mode="w+", dtype=np.float32, shape=(T, N, 3))
    EP = np.lib.format.open_memmap(os.path.join(outdir, "ep.npy"), mode="w+", dtype=np.uint8, shape=(T, N))
    tfail = np.full(N, np.inf, np.float32)
    X[0] = x0; t0 = time.time()
    for f in range(1, T):
        top.deactivate_all()                      # drop grid blocks the wreck has left; within a frame just zero the active ones
        for _ in range(sub):
            clear(); p2g(); grid_op(); g2p()
        xn = x.to_numpy(); X[f] = xn; e = ep.to_numpy(); EP[f] = np.clip(e * 100, 0, 250).astype(np.uint8)
        fl = failed.to_numpy() == 1; tfail[fl & ~np.isfinite(tfail)] = f
        if f % 5 == 0 or f < 4:
            vv = v.to_numpy(); sp = np.linalg.norm(vv, axis=1)
            print(f"frame {f} t={time.time()-t0:.0f}s  mean|v|={sp.mean():.1f} max|v|={sp.max():.0f} failed={fl.mean()*100:.1f}% "
                  f"ep>0.02={np.mean(e>0.02)*100:.1f}% zmin={xn[:,2].min():.2f} xmax={xn[:,0].max():.1f} alive={alive.to_numpy().mean()*100:.2f}%", flush=True)
            if not np.isfinite(sp).all() or sp.max() > 3000: print("UNSTABLE", flush=True); break
    X.flush(); EP.flush(); np.save(os.path.join(outdir, "fail.npy"), tfail)
    json.dump(dict(cfg, dt=dt, sub=sub, N=N, vel=vel0.tolist(), R0=(None if R0 is None else R0.tolist())), open(os.path.join(outdir, "meta.json"), "w"))
    print("saved", outdir, flush=True)


if __name__ == "__main__":
    cfg = dict(CFG)
    if len(sys.argv) > 3: cfg.update(json.loads(sys.argv[3]))
    run(sys.argv[1], sys.argv[2], cfg)
