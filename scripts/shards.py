"""shards.py — turn an MPM run into rigid shards.

MPM treats metal as a continuum on a 6 cm grid, so a thin airframe flows like clay and pieces that touch stick together.
Real aluminium structure tears along joints and comes apart as pieces that keep their shape. This post-process keeps the
MPM motion but removes the flow: the airframe is cut into shards, and every shard keeps its rest shape and follows the
best-fit rigid motion (Kabsch) of its own MPM particles. Where the MPM material stayed rigid, neighbouring shards agree and
the surface is seamless; where it flowed, the shards stay stiff and separate, overlap or tumble instead.

Shard size is not chosen by hand: a piece is split again while its MPM motion is not rigid (fit residual above --tol),
down to --small. So the crush zone becomes many small pieces and undamaged structure stays in large sections.
Fuel (liquid) is left untouched.

Particles the MPM scattered more than --loose metres away from their piece are loose debris and keep the MPM motion.

Release (default on). Following the MPM alone still looks like a lump, because in MPM broken material sticks together and
slides as one mass. So a shard leaves the MPM at the moment the MPM starts to deform or fail it: from then on it is a free
rigid body (mass and inertia from its particles) with gravity, air drag by its own mass/area, and impulse contact with the
ground (restitution, Coulomb friction, so it bounces, skids and tumbles). Shards do not collide with each other.
Pieces the MPM never deformed (tail section, engine cores ...) keep the MPM motion to the end.

  python shards.py sim.npz mpm_dir out_dir '{"big":1.6,"small":0.35,"tol":0.09}'
Writes out_dir/x.npy (same layout as mpm.py), shard.npy (N,) shard id (-1 = not rigidified), shard_rel.npy (K,) release frame,
loose_t.npy (N,) frame at which a loose particle left its piece, plus copies of ep/fail/meta/post.
"""
import numpy as np, os, sys, json, shutil, time


def kabsch(q0, q):
    """rotation M such that q ~= q0 @ M (rows), both centred"""
    U, _, Vt = np.linalg.svd(q0.T @ q)
    D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt)) or 1.0
    return U @ D @ Vt


def cut(x0, XS, parts, liquid, big, small, tol, minn, rng):
    """recursive bisection of every part; XS (F,N,3) = sample frames used to measure how non-rigid a piece moved"""
    out = []; stack = [np.flatnonzero(parts == p) for p in np.unique(parts) if p not in liquid]
    while stack:
        ix = stack.pop()
        if len(ix) == 0: continue
        p = x0[ix]; q = p - p.mean(0)
        w, v = np.linalg.eigh(q.T @ q / len(ix))
        L = 3.46 * np.sqrt(max(w[2], 0.0))                       # length of a uniform bar with this variance
        if len(ix) < 2 * minn or L <= small: out.append(ix); continue
        need = L > big
        if not need:
            for F in XS:
                y = F[ix]; y = y - y.mean(0)
                r = y - q @ kabsch(q, y)
                if np.sqrt((r * r).sum(1).mean()) > tol: need = True; break
        if not need: out.append(ix); continue
        d = v[:, 2] + rng.normal(0, 0.30, 3); d /= np.linalg.norm(d)   # tilted cuts: no regular grid of pieces
        s = q @ d; c = np.quantile(s, rng.uniform(0.35, 0.65))
        a = ix[s <= c]; b = ix[s > c]
        if len(a) < minn or len(b) < minn: out.append(ix); continue
        stack += [a, b]
    return out


def run(simpath, mdir, outdir, cfg):
    t0 = time.time(); os.makedirs(outdir, exist_ok=True)
    d = np.load(simpath); part = d["part"]
    names = [str(n) for n in np.load(os.path.join(os.path.dirname(os.path.abspath(simpath)), "pre.npz"))["part_names"]]
    liquid = [i for i, n in enumerate(names) if n.startswith("fuel")]
    X = np.load(os.path.join(mdir, "x.npy"), mmap_mode="r"); T, N, _ = X.shape
    x0 = np.array(X[0], np.float64)
    fs = np.unique(np.linspace(int(cfg["f0"]), T - 1, int(cfg["nsample"])).round().astype(int))
    XS = [np.array(X[f], np.float64) for f in fs]
    rng = np.random.default_rng(int(cfg["seed"]))
    cells = cut(x0, XS, part, liquid, cfg["big"], cfg["small"], cfg["tol"], int(cfg["minn"]), rng)
    # particles that the MPM threw far away from the rest of their piece are loose debris: they keep the MPM motion and
    # are taken out of the fit (otherwise a piece would sit at the centre of a scattered cloud)
    def layout(cells):
        cnt = np.array([len(c) for c in cells]); order = np.concatenate(cells); starts = np.r_[0, np.cumsum(cnt)[:-1]]; rep = np.repeat(np.arange(len(cells)), cnt)
        c0 = np.add.reduceat(x0[order], starts) / cnt[:, None]
        return cnt, order, starts, rep, x0[order] - c0[rep]
    def pose(P, cnt, starts, rep, Q0):
        """centroid c and rotation M per shard, so that points ~= Q0 @ M + c (rows)"""
        c = np.add.reduceat(P, starts) / cnt[:, None]; Q = P - c[rep]
        U, _, Vt = np.linalg.svd(np.add.reduceat(Q0[:, :, None] * Q[:, None, :], starts, axis=0))
        sgn = np.sign(np.linalg.det(U @ Vt)); sgn[sgn == 0] = 1.0; U[:, :, 2] *= sgn[:, None]
        return c, U @ Vt
    def fit(P, cnt, starts, rep, Q0):
        c, M = pose(P, cnt, starts, rep, Q0)
        return np.einsum("ni,nij->nj", Q0, M[rep]) + c[rep]
    n_in = sum(len(c) for c in cells); tloose = np.full(N, np.inf, np.float32)
    for it in range(int(cfg["passes"])):
        cnt, order, starts, rep, Q0 = layout(cells); worst = np.zeros(len(order))
        for t in range(int(cfg["f0"]), T, 3):
            P = np.array(X[t], np.float64)[order]; res = np.sqrt(((fit(P, cnt, starts, rep, Q0) - P) ** 2).sum(1)); worst = np.maximum(worst, res)
            first = (res > 0.4 * float(cfg["loose"])) & ~np.isfinite(tloose[order]); tloose[order[first]] = t          # when it started to drift off
        keep = worst <= float(cfg["loose"]); cells = [c[keep[s:s + n]] for c, s, n in zip(cells, starts, cnt)]
        cells = [c for c in cells if len(c) >= max(4, int(cfg["minn"]) // 2)]
        print(f"[shards] pass {it}: {int((~keep).sum())} particles left their piece (> {cfg['loose']} m)", flush=True)
    lab = np.full(N, -1, np.int32)
    for k, ix in enumerate(cells): lab[ix] = k
    K = len(cells); cnt, order, starts, rep, Q0 = layout(cells)
    ext = np.array([3.46 * np.sqrt(np.linalg.eigvalsh(np.cov(x0[c].T))[-1]) for c in cells])
    print(f"[shards] {K} shards holding {len(order)} of {n_in} solid particles in {time.time() - t0:.0f}s; "
          f"size m p10/50/90 {np.percentile(ext, 10):.2f}/{np.median(ext):.2f}/{np.percentile(ext, 90):.2f}; particles per shard median {int(np.median(cnt))}; "
          f"shards longer than 1 m: {int((ext > 1).sum())}", flush=True)
    zg = float(np.clip(np.percentile(np.asarray(X[-1])[:, 2], 0.5), 0.0, 0.2))      # where the MPM ground holds material
    fps = float(json.load(open(os.path.join(mdir, "meta.json")))["fps"])
    # ---- pass A: rigid pose of every shard in every frame, and how badly the MPM deformed it
    C = np.zeros((T, K, 3)); MM = np.zeros((T, K, 3, 3), np.float32); RMS = np.zeros((T, K), np.float32); ZL = np.zeros((T, K), np.float32)
    for t in range(T):
        P = np.array(X[t], np.float64)[order]; c, M = pose(P, cnt, starts, rep, Q0)
        Y = np.einsum("ni,nij->nj", Q0, M[rep]) + c[rep]
        C[t] = c; MM[t] = M; RMS[t] = np.sqrt(np.add.reduceat(((Y - P) ** 2).sum(1), starts) / cnt); ZL[t] = np.minimum.reduceat(Y[:, 2], starts)
    print(f"[shards] poses fitted {time.time() - t0:.0f}s", flush=True)
    rel = np.full(K, T + 5)
    if cfg.get("release", 1):
        bad = RMS > np.maximum(cfg["rtol"], cfg["rrel"] * ext)[None]; bad[:int(cfg["f0"]) - 3] = False
        rel = np.where(bad.any(0), bad.argmax(0), T + 5)
        tfail = np.load(os.path.join(mdir, "fail.npy"))
        med = np.array([np.sort(tfail[c])[int(len(c) * float(cfg["failfrac"]))] for c in cells])      # frame when that share of the piece has failed
        rel = np.minimum(rel, np.where(np.isfinite(med), np.ceil(med), T + 5)).astype(int)
        # a piece that reaches the ground at speed takes that impact itself (as a rigid body) instead of being pressed flat by the MPM
        vz = np.zeros((T, K)); vz[2:] = (C[2:, :, 2] - C[:-2, :, 2]) * fps / 2
        gb = (np.r_[ZL[1:], ZL[-1:]] < zg + float(cfg["gmargin"])) & (vz < -float(cfg["vcrit"])); gb[:2] = False
        relg = np.where(gb.any(0), gb.argmax(0) + 1, T + 5); ng = int((relg < rel).sum())
        rel = np.maximum(np.minimum(rel, relg), 3)
        print(f"[shards] {ng} shards are released by their own ground impact", flush=True)
        print(f"[shards] released during the run: {int((rel < T).sum())} of {K} shards, {int(cnt[rel < T].sum())} particles; "
              f"release frame p10/50/90 {np.percentile(rel[rel < T], [10, 50, 90]).round() if (rel < T).any() else None}", flush=True)
    # ---- rigid body data (rest frame)
    try: pm = np.load(json.load(open(os.path.join(mdir, "meta.json")))["fracture"])["pmass"].astype(np.float64)
    except Exception:
        fr = d["frag"]; pm = (d["fmass"] / np.maximum(np.bincount(fr, minlength=len(d["fmass"])), 1))[fr].astype(np.float64)
    mo = pm[order]; mass = np.add.reduceat(mo, starts)
    cm0 = np.add.reduceat(Q0 * mo[:, None], starts) / mass[:, None]; Qm = Q0 - cm0[rep]          # about the centre of mass
    I0 = np.add.reduceat(mo[:, None, None] * ((Qm ** 2).sum(1)[:, None, None] * np.eye(3) - Qm[:, :, None] * Qm[:, None, :]), starts, axis=0)
    I0 += (mass * 0.03 ** 2)[:, None, None] * np.eye(3); I0i = np.linalg.inv(I0)
    ev = np.array([np.sort(np.linalg.eigvalsh(np.cov(x0[c].T)))[::-1] for c in cells]).clip(1e-5)
    area = 0.5 * 12.0 * np.sqrt(ev[:, 0] * ev[:, 1])                                             # tumbling plate: half of length x width
    kd = 0.5 * 1.2 * float(cfg["cd"]) * area / mass
    print(f"[shards] mass kg p10/50/90 {np.percentile(mass, [10, 50, 90]).round(2)}, drag length m (1/kd) p10/50/90 {np.percentile(1 / kd, [10, 50, 90]).round(0)}", flush=True)
    cc = np.zeros((K, 3)); A = np.tile(np.eye(3), (K, 1, 1)); v = np.zeros((K, 3)); w = np.zeros((K, 3)); act = np.zeros(K, bool); calm = np.zeros(K)
    nsub = int(cfg["nsub"]); dt = 1.0 / fps / nsub; g = np.array([0, 0, -9.81]); e_r = float(cfg["restitution"]); mu = float(cfg["mu"]); wmax = float(cfg["wmax"])
    cross = np.cross
    def Iinv(x): return np.einsum("kij,kj->ki", A, np.einsum("kij,kj->ki", I0i, np.einsum("kji,kj->ki", A, x)))
    O = np.lib.format.open_memmap(os.path.join(outdir, "x.npy"), mode="w+", dtype=np.float32, shape=(T, N, 3))
    lift_prev = np.zeros(K)
    for t in range(T):
        new = (rel - 1 == t)
        if new.any():
            a = max(t - 2, 0); h = max(t - a, 1) / fps
            At = np.swapaxes(MM[t][new].astype(np.float64), 1, 2); Aa = np.swapaxes(MM[a][new].astype(np.float64), 1, 2)
            com_t = C[t][new] + np.einsum("kij,kj->ki", At, cm0[new]); com_a = C[a][new] + np.einsum("kij,kj->ki", Aa, cm0[new])
            dA = At @ np.swapaxes(Aa, 1, 2)
            ax = 0.5 * np.stack([dA[:, 2, 1] - dA[:, 1, 2], dA[:, 0, 2] - dA[:, 2, 0], dA[:, 1, 0] - dA[:, 0, 1]], 1)
            sn = np.linalg.norm(ax, axis=1); ang = np.arcsin(np.clip(sn, 0, 1)); wv = ax / np.maximum(sn, 1e-9)[:, None] * (ang / h)[:, None]
            vv = (com_t - com_a) / h; sp = np.linalg.norm(vv, axis=1); n = int(new.sum())
            u = rng.normal(0, 1, (n, 3)); u[:, 2] = np.abs(u[:, 2]) * 0.6                             # uneven break-up: sideways and upwards, never into the ground
            vv = vv + u * (sp * float(cfg["scatter"]))[:, None]
            wv = wv + rng.normal(0, 1, (n, 3)) * (sp / np.maximum(ext[new], 0.3) * float(cfg["spin"]))[:, None]
            cc[new] = com_t; A[new] = At; v[new] = vv; w[new] = wv; act |= new
        # --- this frame
        Ause = np.where(act[:, None, None], A, np.swapaxes(MM[t].astype(np.float64), 1, 2))
        cuse = np.where(act[:, None], cc, C[t] + np.einsum("kij,kj->ki", Ause, cm0))
        Y = np.einsum("kij,kj->ki", Ause[rep], Qm) + cuse[rep]
        # an attached stiff piece cannot be pressed into the ground the way the clay was: rest it on the ground instead
        lift = np.clip(zg - np.minimum.reduceat(Y[:, 2], starts), 0.0, None) * ~act
        lift = np.maximum(lift, lift_prev * 0.9 * ~act) if t else lift; lift_prev = lift; Y[:, 2] += lift[rep]
        x = np.array(X[t], np.float32); x[order] = Y; O[t] = x
        if t % 40 == 0 or t == T - 1:
            sa = np.linalg.norm(v[act], axis=1) if act.any() else np.zeros(1)
            print(f"[shards] frame {t}/{T} free {int(act.sum())} speed p50/p90 {np.median(sa):.0f}/{np.percentile(sa, 90):.0f} m/s  {time.time() - t0:.0f}s", flush=True)
        if not act.any(): continue
        # --- advance the free shards to the next frame
        for _ in range(nsub):
            sp = np.linalg.norm(v, axis=1)
            v = (v + g * dt) / (1.0 + kd * sp * dt)[:, None]; w = w * (1.0 - float(cfg["wdamp"]) * dt)
            cc = cc + v * dt * act[:, None]
            th = np.linalg.norm(w, axis=1); k = w / np.maximum(th, 1e-9)[:, None]; th = th * dt
            Kx = np.zeros((K, 3, 3)); Kx[:, 0, 1] = -k[:, 2]; Kx[:, 0, 2] = k[:, 1]; Kx[:, 1, 0] = k[:, 2]; Kx[:, 1, 2] = -k[:, 0]; Kx[:, 2, 0] = -k[:, 1]; Kx[:, 2, 1] = k[:, 0]
            Rinc = np.eye(3) + np.sin(th)[:, None, None] * Kx + (1 - np.cos(th))[:, None, None] * (Kx @ Kx)
            A = np.where(act[:, None, None], Rinc @ A, A)
            Y = np.einsum("kij,kj->ki", A[rep], Qm) + cc[rep]
            zmin = np.minimum.reduceat(Y[:, 2], starts); hit = act & (zmin < zg)
            if hit.any():
                near = (Y[:, 2] < zmin[rep] + 0.02).astype(np.float64)                                # contact patch: a flat piece lying flat gets no torque
                pc = np.add.reduceat(Y * near[:, None], starts) / np.add.reduceat(near, starts)[:, None]
                r = pc - cc; r[:, 2] = zmin - cc[:, 2]
                nz = np.zeros((K, 3)); nz[:, 2] = 1.0
                uu = v + cross(w, r); un = uu[:, 2]
                kn = 1.0 / mass + (cross(Iinv(cross(r, nz)), r))[:, 2]
                jn = np.where(hit & (un < 0), -(1.0 + np.where(un < -1.5, e_r, 0.0)) * un / kn, 0.0)
                v = v + nz * (jn / mass)[:, None]; w = w + Iinv(cross(r, nz * jn[:, None]))
                uu = v + cross(w, r); ut = uu.copy(); ut[:, 2] = 0; su = np.linalg.norm(ut, axis=1); tdir = ut / np.maximum(su, 1e-9)[:, None]
                kt = 1.0 / mass + (cross(Iinv(cross(r, tdir)), r) * tdir).sum(1)
                jt = np.where(hit, np.minimum(mu * jn, su / np.maximum(kt, 1e-12)), 0.0)
                v = v - tdir * (jt / mass)[:, None]; w = w - Iinv(cross(r, tdir * jt[:, None]))
                cc[:, 2] += np.where(hit, zg - zmin, 0.0)
                # pieces that are down and slow come to rest instead of jittering on one point
                slow = hit & (np.linalg.norm(v, axis=1) < 1.5); calm = np.where(slow, calm + dt, 0.0)
                f = np.where(slow, np.exp(-dt * 25.0), 1.0)[:, None]; v = v * f; w = w * np.where(hit, np.exp(-dt * np.where(slow, 40.0, 6.0)), 1.0)[:, None]
            wn = np.linalg.norm(w, axis=1); w = w * np.minimum(1.0, wmax / np.maximum(wn, 1e-9))[:, None]
        U, _, Vt = np.linalg.svd(A); A = U @ Vt                                                      # keep rotations orthonormal
    O.flush(); np.save(os.path.join(outdir, "shard.npy"), lab); np.save(os.path.join(outdir, "shard_rel.npy"), rel.astype(np.float32))
    tloose[lab >= 0] = np.inf; np.save(os.path.join(outdir, "loose_t.npy"), tloose)
    for f in ("ep.npy", "fail.npy", "post.npz"):
        if os.path.exists(os.path.join(mdir, f)): shutil.copyfile(os.path.join(mdir, f), os.path.join(outdir, f))
    meta = json.load(open(os.path.join(mdir, "meta.json"))); meta["shards"] = dict(cfg, K=K, source=os.path.basename(os.path.normpath(mdir)))
    json.dump(meta, open(os.path.join(outdir, "meta.json"), "w"))
    print("[shards] done", flush=True)


if __name__ == "__main__":
    cfg = dict(big=1.6, small=0.35, tol=0.09, minn=8, nsample=14, f0=14, seed=3, loose=0.4, passes=2,
               release=1, rtol=0.04, rrel=0.06, failfrac=0.5, gmargin=0.08, vcrit=15.0, nsub=4, restitution=0.35, mu=0.6, cd=1.2, scatter=0.22, spin=0.15, wdamp=0.3, wmax=60.0)
    if len(sys.argv) > 4: cfg.update(json.loads(sys.argv[4]))
    run(sys.argv[1], sys.argv[2], sys.argv[3], cfg)
