"""Secondary particle systems + per-frame assembly. numpy only (runs in cloud and in Blender's Python).
All dynamics are integrated in real time along a retimed (slow-motion) output timeline."""
import numpy as np
import recon, fluid, palette

FPS_SIM = 240.0
PT_R = 0.012
FIRE_GAIN = 0.065
G = np.array([0, 0, -9.81], np.float32)


# ---------------------------------------------------------------- timeline
def timeline(n_out=450, fps=30.0, contact_frame=11.0, keys=((0, 0.16), (2.2, 0.16), (3.0, 0.03), (6.5, 0.035), (9.5, 0.11), (15.0, 0.30)), contact_tau=3.0):
    """returns sim-frame position (float, may be negative) for every output frame"""
    tau = np.arange(n_out + 1) / fps
    kt = np.array([k[0] for k in keys]); ks = np.array([k[1] for k in keys])
    fine = np.linspace(0, tau[-1], 20001)
    sp = np.interp(fine, kt, ks)
    # smooth the speed curve a little
    k = np.ones(401) / 401; sp = np.convolve(np.pad(sp, 200, mode="edge"), k, mode="valid")
    t = np.concatenate([[0], np.cumsum(0.5 * (sp[1:] + sp[:-1]) * np.diff(fine))])
    t_out = np.interp(tau, fine, t); t_c = np.interp(contact_tau, fine, t)
    return (t_out - t_c) * FPS_SIM + contact_frame


# ---------------------------------------------------------------- helpers
def ramp(x, xs, cols):
    cols = np.asarray(cols, np.float32)
    return np.stack([np.interp(x, xs, cols[:, i]) for i in range(cols.shape[1])], -1).astype(np.float32)


class Pool:
    """growable particle pool"""
    F = ("pos", "vel", "age", "life", "seed", "aux")
    def __init__(self):
        self.pos = np.zeros((0, 3), np.float32); self.vel = np.zeros((0, 3), np.float32)
        self.age = np.zeros(0, np.float32); self.life = np.zeros(0, np.float32)
        self.seed = np.zeros(0, np.float32); self.aux = np.zeros((0, 3), np.float32)
    def add(self, pos, vel, life, seed, aux=None):
        n = len(pos)
        if n == 0: return
        self.pos = np.concatenate([self.pos, pos.astype(np.float32)]); self.vel = np.concatenate([self.vel, vel.astype(np.float32)])
        self.age = np.concatenate([self.age, np.zeros(n, np.float32)]); self.life = np.concatenate([self.life, life.astype(np.float32)])
        self.seed = np.concatenate([self.seed, seed.astype(np.float32)])
        self.aux = np.concatenate([self.aux, (np.zeros((n, 3), np.float32) if aux is None else aux.astype(np.float32))])
    def cull(self, keep):
        for f in self.F: setattr(self, f, getattr(self, f)[keep])
    def __len__(self): return len(self.pos)


def ground_bounce(p, rest=0.3, fric=0.4, r=0.01):
    m = p.pos[:, 2] < r
    if m.any():
        p.pos[m, 2] = r
        vz = p.vel[m, 2]; p.vel[m, 2] = np.where(vz < 0, -rest * vz, vz)
        p.vel[m, :2] *= (1 - fric)


def abc_flow(x, t, k, amp):
    a = x * k
    ph = t * 2.0
    return amp * np.stack([np.sin(a[:, 2] + ph) + np.cos(a[:, 1] - ph * 0.7),
                           np.sin(a[:, 0] + ph * 1.3) + np.cos(a[:, 2] + ph * 0.4),
                           np.sin(a[:, 1] - ph) + np.cos(a[:, 0] + ph * 0.9)], 1).astype(np.float32)


# ---------------------------------------------------------------- main class
class FX:
    def __init__(self, simpath, prepath, seed=5, quality=1.0, scheme="design", grid_h=0.5, mpm=None, fire=True, mfire=None, tl=None, mf_density=800.0):
        self.mpm = mpm is not None
        self.S = S = recon.MSim(simpath, mpm) if self.mpm else recon.Sim(simpath); P = np.load(prepath)
        self.P = {k: P[k] for k in P.files}
        self.rng = np.random.default_rng(seed); self.q = quality
        self.part = S.part; self.frag = S.frag
        names = [str(x) for x in P["part_names"]]; self.pid = {n: i for i, n in enumerate(names)}
        self.scheme = scheme
        rest = (S.cen0[S.frag] + S.local - P["model_t"]) @ P["model_R"]        # back to the model frame (nose +x, up +z)
        self.part_rgb, self.base_emit, self.edge_rgb, self.edge_emit = palette.colors(rest, S.part, self.pid, scheme, P["part_rgb"])
        self.tint = (1 + (P["frag_tint"][S.frag].astype(np.float32) - 1) * (0.75 if scheme == "livery" else 0.85)).astype(np.float32)
        self.pt_fbreak = P["frag_break"][S.frag].astype(np.float32)
        self.base_rgb = (self.part_rgb * self.tint[:, None]).astype(np.float32)
        self.pt_break = P["pt_break"]; self.shed = P["shed"]; self.shed_idx = np.flatnonzero(self.shed)
        self.shed_done = np.zeros(len(self.shed_idx), bool)
        self.fuel = P["fuel"]; self.fuel_ign = P["frag_break"][S.frag[self.fuel]] + self.rng.uniform(0, 10, len(self.fuel))
        # most tanks flash off quickly (the fireball); about a third of the fuel fragments keep streaming flame as they tumble
        longb = (self.rng.random(int(S.frag.max()) + 1) < 0.14)[S.frag[self.fuel]]
        self.fuel_dur = np.where(longb, self.rng.uniform(150, 330, len(self.fuel)), self.rng.uniform(30, 90, len(self.fuel)))   # sim frames
        self.fuel_rate = np.where(longb, 0.9, 1.0)
        self.nozzle = P["nozzle"]; self.noz_off = P["frag_break"][S.frag[self.nozzle]]; self.noz_n = 160      # 160 rim particles per engine (pre.py)
        self.axis_aft = (np.array([-1.0, 0.0, 0.0]) @ P["model_R"].T).astype(np.float32)                    # thrust-line direction (aft) in the rest pose
        self.rings = P["rings"]
        self.noz_out = []
        if self.mpm: self._mpm_setup(S, P)
        if not fire: self.fuel_ign = np.full(len(self.fuel), np.inf, np.float32)      # airframe-only looks: nothing ever ignites
        for k in range(0 if self.mpm else len(self.nozzle) // self.noz_n):
            fr = np.unique(S.frag[self.nozzle[k * self.noz_n:(k + 1) * self.noz_n]])
            v = np.diff(S.loc[:, fr].mean(1), axis=0) * FPS_SIM
            hit = np.flatnonzero(np.linalg.norm(v - S.vel, axis=1) > 8.0)
            self.noz_out.append(float(hit[hit > 4][0]) if (hit > 4).any() else 1e9)
        self.cand = np.arange(0, len(S.part), 3)                           # ground-contact probe particles
        self.sparks = Pool(); self.dust = Pool(); self.fire = Pool(); self.exh = Pool(); self.debris = Pool()
        # gas solver that carries the fire (see fluid.py); fire pool aux = (heat, is_smoke, -)
        self.mf = mfire is not None; self.mf_density = mf_density
        if self.mf:                                                        # gas from Blender's Mantaflow (mfire.py) instead of fluid.py
            import mfield; self.fl = mfield.MField(mfire, timeline() if tl is None else tl)
        else: self.fl = fluid.Fluid((-12.0, -26.0, 0.0), (140.0, 52.0, 24.0), h=grid_h, buoy=42.0, vort=6.0, cool=0.35)
        self.fl_acc = 0.0
        self.wake = np.arange(0, len(S.part), 12)
        self.spill_pos = np.zeros((0, 3), np.float32); self.spill_t0 = np.zeros(0, np.float32); self.spill_dur = np.zeros(0, np.float32)
        self.t = None                                                      # current sim-frame time
        # ground lattice
        dx = 0.42; self.g_dx = dx; self.g_x0 = -45.0; self.g_y0 = -42.0
        nx = int(215 / dx); ny = int(90 / dx)
        gx, gy = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
        self.g_shape = (nx, ny)
        jit = self.rng.normal(0, 0.03, (nx, ny, 2))
        self.g_pos = np.stack([self.g_x0 + gx * dx + (gy % 2) * dx * 0.5 + jit[..., 0], self.g_y0 + gy * dx * 0.866 + jit[..., 1], np.zeros((nx, ny))], -1).reshape(-1, 3).astype(np.float32)
        self.g_heat = np.zeros(nx * ny, np.float32)
        # air motes
        n = int(16000 * quality)
        self.m_pos = np.stack([self.rng.uniform(-45, 165, n), self.rng.uniform(-40, 30, n), self.rng.uniform(0.15, 1, n) ** 2 * 14], 1).astype(np.float32)
        self.m_seed = self.rng.random(n).astype(np.float32)

    # ---- MPM run: everything the rigid version read from fragments is derived from particle tracks instead
    def _mpm_setup(self, S, P):
        import os
        rest = S.cen0[S.frag] + S.local; N = len(rest); pid = self.pid
        self.tint[:] = 1.0; self.pt_fbreak[:] = np.inf; self.base_rgb = self.part_rgb.copy()
        if S.meta.get("R0") is not None: self.axis_aft = (np.array([-1.0, 0.0, 0.0]) @ np.array(S.meta["R0"]).T).astype(np.float32)
        self.pt_break = S.tfail.astype(np.float32)
        # a share of the material that failed is thrown clear as loose bits (ballistic, keeps its colour); the rest stays in the MPM wreck
        heavy = np.isin(S.part, [pid[k] for k in ("fuel_L", "fuel_R", "core_L", "core_R")])
        self.shed = np.isfinite(self.pt_break) & (np.random.default_rng(7).random(N) < 0.30) & ~heavy
        sh = os.path.join(S.mdir, "shard.npy")
        if os.path.exists(sh):
            # rigid shards (shards.py): the pieces stay whole, only the loose material between them is thrown clear as bits.
            # Every piece gets its own brightness once it has broken away, so neighbouring pieces can be told apart.
            self.shards = True
            lab = np.load(sh); rel = np.load(os.path.join(S.mdir, "shard_rel.npy")); tl = np.load(os.path.join(S.mdir, "loose_t.npy"))
            loose = (lab < 0) & ~heavy
            self.pt_break = np.where(loose, np.minimum(self.pt_break, tl), self.pt_break).astype(np.float32)
            self.shed = loose & np.isfinite(self.pt_break) & (np.random.default_rng(7).random(N) < 0.85)
            tk = np.random.default_rng(11).uniform(0.62, 1.30, len(rel)).astype(np.float32)
            self.tint = np.where(lab >= 0, tk[np.maximum(lab, 0)], 1.0).astype(np.float32)
            self.pt_fbreak = np.where(lab >= 0, rel[np.maximum(lab, 0)], np.inf).astype(np.float32)
        self.shed_idx = np.flatnonzero(self.shed); self.shed_done = np.zeros(len(self.shed_idx), bool)
        self.noz_off = np.full(len(self.nozzle), np.inf)
        cache = os.path.join(S.mdir, "post.npz")
        if os.path.exists(cache):
            c = np.load(cache); self.fuel_ign = c["fuel_ign"]; self.rings = c["rings"]; self.noz_out = list(c["noz_out"]); self.focus_track = c["focus"]; return
        # fuel leaves its tank when it is far from the wing skin that surrounded it at rest
        skin = np.flatnonzero(np.isin(S.part, [pid["wing_L"], pid["wing_R"]])); nb = np.zeros((len(self.fuel), 4), int)
        for a in range(0, len(self.fuel), 100):
            d = np.linalg.norm(rest[self.fuel[a:a + 100], None] - rest[None, skin], axis=2); nb[a:a + 100] = skin[np.argpartition(d, 4, axis=1)[:, :4]]
        esc = np.full(len(self.fuel), np.inf)
        groups = {"fuselage": ("nose", "cockpit", "cabin_fwd", "cabin_mid", "aft_fuse", "tailcone"), "wing_R": ("wing_R",), "wing_L": ("wing_L",),
                  "core_R": ("core_R",), "core_L": ("core_L",), "fin": ("fin",)}
        amp = {"fuselage": 1.0, "wing_R": 0.7, "wing_L": 0.7, "core_R": 0.9, "core_L": 0.9, "fin": 0.5}
        gidx = {g: np.flatnonzero(np.isin(S.part, [pid[n] for n in names]))[::7] for g, names in groups.items()}
        rings = {}; nk = len(self.nozzle) // self.noz_n; ncen = np.zeros((S.T, nk, 3), np.float32); sub = np.arange(0, N, 23); foc = np.zeros((S.T, 3), np.float32)
        for f in range(S.T):
            x = S.fr(f)
            dmin = np.linalg.norm(x[self.fuel, None] - x[nb], axis=2).min(1)
            new = (dmin > 0.45) & ~np.isfinite(esc); esc[new] = f
            for g, ix in gidx.items():
                if g not in rings:
                    j = ix[np.argmin(x[ix, 2])]
                    if x[j, 2] < 0.15: rings[g] = [f, x[j, 0], x[j, 1], amp[g]]
            for k in range(nk): ncen[f, k] = x[self.nozzle[k * self.noz_n:(k + 1) * self.noz_n]].mean(0)
            foc[f] = np.median(x[sub], axis=0)
        self.fuel_ign = (esc + self.rng.uniform(2, 14, len(esc))).astype(np.float32)
        self.rings = np.array(list(rings.values()), np.float32).reshape(-1, 4)
        v = np.diff(ncen, axis=0) * FPS_SIM
        for k in range(nk):
            hit = np.flatnonzero(np.linalg.norm(v[:, k] - S.vel, axis=1) > 8.0); hit = hit[hit > 4]
            self.noz_out.append(float(hit[0]) if len(hit) else 1e9)
        self.focus_track = foc
        np.savez(cache, fuel_ign=self.fuel_ign, rings=self.rings, noz_out=np.array(self.noz_out), focus=foc)

    # ---- aircraft kinematics
    def pts(self, idx, f):
        """positions of selected aircraft particles at sim frame f (float, <0 extrapolates the approach)"""
        S = self.S
        if self.mpm: return S.pos(idx, f)
        if f < 0:
            return S.loc[0][S.frag[idx]] + S.local[idx] + (S.vel * (f / FPS_SIM)).astype(np.float32)
        f = min(f, S.T - 1.001); i = int(np.floor(f)); a = f - i
        fr = S.frag[idx]
        L = S.loc[i][fr] * (1 - a) + S.loc[i + 1][fr] * a
        q0 = S.quat[i][fr]; q1 = S.quat[i + 1][fr]
        q1 = np.where((q0 * q1).sum(1, keepdims=True) < 0, -q1, q1)
        Q = q0 * (1 - a) + q1 * a; Q /= np.linalg.norm(Q, axis=1, keepdims=True)
        return L + recon.qrot(Q, S.local[idx])

    def dirs(self, idx, f, d):
        """rest-pose direction d carried by the fragments of particles idx at sim frame f"""
        S = self.S
        if f < 0: return np.tile(d, (len(idx), 1))
        if self.mpm:
            # best-fit rotation of this particle set from its rest pose (Kabsch); the set is one engine's nozzle ring
            r = S.fr(0)[idx]; c = S.pos(idx, f); r = r - r.mean(0); c = c - c.mean(0)
            U, _, Vt = np.linalg.svd(r.T @ c); sg = np.sign(np.linalg.det(U @ Vt))
            R = (U * np.array([1, 1, sg])) @ Vt
            return np.tile((d @ R).astype(np.float32), (len(idx), 1))
        f = min(f, S.T - 1.001); i = int(np.floor(f)); a = f - i; fr = S.frag[idx]
        q0 = S.quat[i][fr]; q1 = S.quat[i + 1][fr]
        q1 = np.where((q0 * q1).sum(1, keepdims=True) < 0, -q1, q1)
        Q = q0 * (1 - a) + q1 * a; Q /= np.linalg.norm(Q, axis=1, keepdims=True)
        return recon.qrot(Q, np.tile(d, (len(idx), 1)))

    def pts_vel(self, idx, f):
        p0 = self.pts(idx, f); p1 = self.pts(idx, f + 0.5)
        return p0, (p1 - p0) * (FPS_SIM / 0.5)

    def aircraft(self, f):
        """full aircraft layer at sim frame f -> pos, rgb, emit, rad"""
        idx = np.arange(len(self.part))
        pos, vel = self.pts_vel(idx, f)
        heat = np.zeros(len(idx), np.float32)
        age = (f - self.pt_break) / FPS_SIM                      # seconds since the nearby crack opened
        m = age > 0
        heat[m] = np.exp(-age[m] / 0.06)
        spd = np.linalg.norm(vel, axis=1)
        scrape = (pos[:, 2] < 0.07) & (spd > 6) & (f >= 0)
        crack = heat.copy()
        heat = np.zeros_like(crack)
        heat[scrape] = np.clip(spd[scrape] / 60, 0.15, 0.6)
        w = np.clip(heat * 1.4, 0, 1)[:, None]
        tw = np.clip((f - self.pt_fbreak) / 12.0, 0, 1); tw = tw * tw * (3 - 2 * tw)
        base = self.part_rgb * (1 + (self.tint - 1) * tw)[:, None]
        rgb = base * (1 - w) + np.array([1.0, 0.35, 0.05], np.float32) * w
        cw = 0.35 * (0.45 if getattr(self, "shards", False) else 1.0)
        rgb = rgb * (1 - cw * crack[:, None]) + cw * crack[:, None]          # crack core leans white, hue survives
        kg = 0.45 if getattr(self, "shards", False) else 1.0      # rigid pieces: less white glow, so each piece keeps its part colour
        emit = self.base_emit + (crack * 3.0 + heat * 2.5) * kg
        if self.mpm:
            # bent metal: plastic strain lifts the colour toward the edge tint and adds a little glow, so dents and creases read
            st = np.clip(self.S.strain(f) / 0.30, 0, 1)[:, None]; e = np.ones(3, np.float32) if self.edge_rgb is None else self.edge_rgb
            rgb = rgb * (1 - 0.30 * st) + e * (0.30 * st); emit = emit + 0.5 * st[:, 0]
        if self.edge_rgb is not None:                              # torn edges keep a rim colour so every fragment stays outlined
            rim = ((0.25 if self.mpm else 0.7) * (age > 0) * np.clip(age / 0.05, 0, 1)).astype(np.float32)[:, None]
            rgb = rgb * (1 - rim) + self.edge_rgb * rim; emit = emit + self.edge_emit * rim[:, 0]
        rad = np.full(len(idx), PT_R, np.float32)
        gone = self.shed & (f >= self.pt_break)                   # handed over to the debris pool
        keep = ~gone
        return pos[keep], rgb[keep], emit[keep], rad[keep]

    # ---- emission + integration for one substep [f0, f1] (sim frames)
    def substep(self, f0, f1):
        rng = self.rng; dt = (f1 - f0) / FPS_SIM; S = self.S
        if self.mf: self.fl.seek(f1)
        # exhaust jets (as long as the nozzle is still attached). The jet leaves along the ENGINE AXIS as carried by the
        # engine's own rigid body (not along the flight path), from points filling the nozzle disc, so the plume is a
        # straight extension of the nacelle whatever the aircraft's attitude or sideslip.
        on = self.noz_off > f0
        for k in range(len(self.nozzle) // self.noz_n):
            sl = slice(k * self.noz_n, (k + 1) * self.noz_n); o = on[sl]
            if not o.any(): continue
            idx = self.nozzle[sl][o]
            # the engine flames out when its own body is hit (speed change), spooling down in ~0.05 s
            spool = 1.0 if f0 < self.noz_out[k] else float(np.exp(-(f0 - self.noz_out[k]) / 12.0))
            if spool < 0.03: continue
            n = rng.poisson(650.0 * self.q * dt * len(idx) * spool)
            if n == 0: continue
            p, v = self.pts_vel(idx, f0)
            ax = self.dirs(idx, f0, self.axis_aft).mean(0); ax /= np.linalg.norm(ax)
            c = p.mean(0); ve = v.mean(0)
            r = np.linalg.norm(np.cross(p - c, ax), axis=1).mean()               # nozzle radius
            e1 = np.cross(ax, [0.0, 0.0, 1.0]); e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
            rr = r * np.sqrt(rng.random(n)); th = rng.uniform(0, 2 * np.pi, n)
            off = np.outer(rr * np.cos(th), e1) + np.outer(rr * np.sin(th), e2)
            core = 1.0 - (rr / r) ** 2                                           # faster in the core (jet profile)
            U = (rng.uniform(150, 190, n) + 80.0 * core) * (0.35 + 0.65 * spool)
            jet = ve + np.outer(U, ax) + rng.normal(0, 1.6, (n, 3))
            self.exh.add(c + off + (jet - ve) * rng.uniform(0, dt, (n, 1)), jet, rng.uniform(0.018, 0.040, n), rng.random(n))
        if f1 > 0:
            fa = max(f0, 0.0)
            # ---- ground contact: sparks + dust + ground heat
            p, v = self.pts_vel(self.cand, fa)
            spd = np.linalg.norm(v, axis=1)
            c = np.flatnonzero((p[:, 2] < 0.08) & (spd > 5))
            if len(c):
                pc, vc, sc = p[c], v[c], spd[c]
                n = rng.poisson(np.clip(sc / 40, 0.1, 1.5) * 6.0 * self.q * dt); rep = np.repeat(np.arange(len(c)), n); k = len(rep)
                if k:
                    vv = vc[rep] * rng.uniform(0.15, 0.95, (k, 1)) + rng.normal(0, 3.5, (k, 3))
                    vv[:, 2] = np.abs(vv[:, 2]) + rng.uniform(0.5, 9, k)
                    self.sparks.add(pc[rep] + rng.normal(0, 0.03, (k, 3)), vv, rng.uniform(0.08, 0.5, k) ** 1.0, rng.random(k))
                n = rng.poisson(np.clip(sc / 40, 0.1, 1.5) * 4.0 * self.q * dt); rep = np.repeat(np.arange(len(c)), n); k = len(rep)
                if k:
                    vv = vc[rep] * rng.uniform(0.03, 0.45, (k, 1)) + rng.normal(0, 2.5, (k, 3))
                    vv[:, 2] = np.abs(vv[:, 2]) * 0.5 + rng.uniform(0.3, 8, k) * rng.random(k)
                    self.dust.add(pc[rep] + rng.normal(0, 0.06, (k, 3)) * [1, 1, 0.3], vv, rng.uniform(0.4, 1.8, k), rng.random(k))
                gi = np.round((pc[:, 1] - self.g_y0) / (self.g_dx * 0.866)).astype(int)
                gj = np.round((pc[:, 0] - self.g_x0 - (gi % 2) * self.g_dx * 0.5) / self.g_dx).astype(int)
                ok = (gi >= 0) & (gi < self.g_shape[1]) & (gj >= 0) & (gj < self.g_shape[0])
                np.add.at(self.g_heat, gj[ok] * self.g_shape[1] + gi[ok], 0.5)
            # ---- fuel -> fire: emitters heat the gas grid, push it and release flame particles
            fl = self.fl
            burning = (self.fuel_ign <= f1) & (self.fuel_ign + self.fuel_dur > fa)
            if burning.any():
                idx = self.fuel[burning]
                p, v = self.pts_vel(idx, fa)
                fl.burn(p, 60.0 * dt, 1.5, 8.0, 30.0); fl.drag(p, v, 0.6, 0.55)
                flash = (fa - self.fuel_ign[burning]) < 22                # first moments after a tank ruptures: violent expansion
                if flash.any(): fl.burn(p[flash], 0.0, 1.5, 30.0, 110.0)
                prog = np.clip((fa - self.fuel_ign[burning]) / self.fuel_dur[burning], 0, 1)
                n = rng.poisson((120.0 if self.mf else 480.0) * self.q * dt * (1.2 - prog) * self.fuel_rate[burning]); rep = np.repeat(np.arange(len(idx)), n); k = len(rep)
                if k:
                    d = rng.normal(0, 1, (k, 3)); d /= np.linalg.norm(d, axis=1, keepdims=True)
                    vv = v[rep] * rng.uniform(0.5, 0.9, (k, 1)) + d * rng.uniform(0.3, 2.5, (k, 1)); vv[:, 2] += rng.uniform(0, 4, k)
                    aux = np.zeros((k, 3), np.float32); aux[:, 0] = rng.uniform(1.2, 1.5, k); aux[:, 2] = rng.uniform(0.25, 0.7, k)
                    self.fire.add(p[rep] + d * rng.uniform(0, 0.25, (k, 1)), vv, rng.uniform(2.0, 3.5, k), rng.random(k), aux)
                m = rng.random(len(idx)) < 30.0 * dt                 # fuel spilled on the ground keeps burning along the scar
                if m.any():                                          # ... in separate pools, not as one carpet
                    cell = np.floor(p[m, :2] / 3.5); hsh = np.sin(cell[:, 0] * 12.9898 + cell[:, 1] * 78.233) * 43758.5453
                    m[np.flatnonzero(m)[(hsh - np.floor(hsh)) > 0.22]] = False
                if m.any():
                    sp = p[m] + rng.normal(0, 0.5, (int(m.sum()), 3)); sp[:, 2] = 0.05
                    self.spill_pos = np.concatenate([self.spill_pos, sp.astype(np.float32)])
                    self.spill_t0 = np.concatenate([self.spill_t0, np.full(len(sp), f1, np.float32)])
                    self.spill_dur = np.concatenate([self.spill_dur, rng.uniform(200, 520, len(sp)).astype(np.float32)])
            if len(self.spill_pos):
                on = (f1 - self.spill_t0) < self.spill_dur
                if on.any():
                    sp = self.spill_pos[on]
                    fl.burn(sp + np.array([0, 0, 0.2], np.float32), 25.0 * dt, 1.15, 2.0, 6.0)
                    n = rng.poisson(110.0 * self.q * dt, len(sp)); rep = np.repeat(np.arange(len(sp)), n); k = len(rep)
                    if k:
                        vv = rng.normal(0, 0.7, (k, 3)); vv[:, 2] = rng.uniform(0.5, 3.5, k)
                        aux = np.zeros((k, 3), np.float32); aux[:, 0] = rng.uniform(1.0, 1.3, k); aux[:, 2] = rng.uniform(0.1, 0.3, k)
                        self.fire.add(sp[rep] + rng.normal(0, 0.18, (k, 3)) * [1, 1, 0.3] + [0, 0, 0.08], vv, rng.uniform(2.0, 3.5, k), rng.random(k), aux)
            if self.mf and fl.active and fl.flame_m3 > 0:
                # Mantaflow run: the flame field itself is filled with short-lived tracer particles, so the particle fire has
                # the solver's shape; they ride its velocity and are coloured by its flame value
                k = rng.poisson(self.mf_density * self.q * fl.flame_m3 * dt / 0.11)
                if k:
                    p = fl.seed(k, rng); vv, T = fl.sample(p)
                    aux = np.zeros((k, 3), np.float32); aux[:, 0] = T * 0.6; aux[:, 2] = 0.0
                    self.fire.add(p, vv, rng.uniform(0.04, 0.18, k), rng.random(k), aux)
            if fl.active:
                if len(self.fire):                                   # fuel mist keeps burning where the gas carried it
                    young = (self.fire.age < self.fire.aux[:, 2]) & (self.fire.aux[:, 1] == 0)
                    if young.any(): fl.burn(self.fire.pos[young], 4.0 * dt / self.q, 0.72, 1.0 / self.q, 4.0)
                p, v = self.pts_vel(self.wake, fa); fl.drag(p, v, 0.10, 0.6)     # the wreck drags the air with it
                self.fl_acc += dt
                if self.fl_acc >= 0.6 / FPS_SIM: fl.step(self.fl_acc); self.fl_acc = 0.0
            # ---- shed debris: aircraft particles torn off at cracks keep their part colour
            due = ~self.shed_done & (self.pt_break[self.shed_idx] <= f1)
            if due.any():
                idx = self.shed_idx[due]; self.shed_done |= due
                p, v = self.pts_vel(idx, fa); k = len(idx)
                d = rng.normal(0, 1, (k, 3)); d /= np.linalg.norm(d, axis=1, keepdims=True)
                vv = v * rng.uniform(0.75, 1.02, (k, 1)) + d * rng.uniform(0.5, 9, (k, 1))
                self.debris.add(p, vv, rng.uniform(1.5, 6.0, k), rng.random(k), aux=self.base_rgb[idx])
        # ---- integrate
        tsec = f1 / FPS_SIM
        for pool, drag, grav, rest, fric in ((self.sparks, 1.2, 1.0, 0.35, 0.3), (self.debris, 0.5, 1.0, 0.3, 0.45)):
            if len(pool):
                pool.vel += (G * grav - drag * pool.vel) * dt
                pool.pos += pool.vel * dt; pool.age += dt; ground_bounce(pool, rest, fric)
        if len(self.exh):
            self.exh.vel -= 2.0 * self.exh.vel * dt; self.exh.pos += self.exh.vel * dt; self.exh.age += dt
        fl = self.fl
        if len(self.dust):
            d = self.dust
            ug = fl.sample(d.pos)[0] if fl.active else 0.0
            d.vel += (G * 0.35 - 2.6 * (d.vel - ug) + 2.6 * abc_flow(d.pos, tsec, 0.9, 0.8)) * dt
            d.pos += d.vel * dt; d.age += dt; ground_bounce(d, 0.0, 0.8, 0.02)
        if len(self.fire):
            fp = self.fire; h = fp.aux[:, 0]
            if fl.active: ug, Tg = fl.sample(fp.pos)
            else: ug = np.zeros_like(fp.vel); Tg = np.zeros(len(fp), np.float32)
            turb = abc_flow(fp.pos, tsec, 2.4, 1.0) + abc_flow(fp.pos + 7.1, tsec * 1.7, 6.5, 0.6)       # detail below grid scale
            turb *= (0.2 + 0.6 * np.clip(h, 0, 1))[:, None]
            fp.vel += 16.0 * (ug + turb - fp.vel) * dt
            fp.pos += fp.vel * dt; fp.age += dt
            np.maximum(fp.pos[:, 2], 0.03, out=fp.pos[:, 2])
            # heat: follows the gas temperature (stays hot inside the fireball), cools on its own at the edges
            k = np.where(Tg > h, 10.0, 1.5)
            h += (k * (Tg - h) - h / 0.20) * dt
            smoke = fp.aux[:, 1] > 0
            dead = (h < 0.2) & ~smoke
            if dead.any():
                turn = dead & (fp.seed > 0.78); fp.aux[turn, 1] = 1.0; fp.age[turn] = 0.0
                fp.cull(~(dead & ~turn))
        for pool, extra in ((self.sparks, 1.0), (self.exh, 1.0), (self.dust, 1.0), (self.debris, 1.0), (self.fire, 1.0)):
            if len(pool): pool.cull(pool.age < pool.life * extra)
        self.g_heat *= np.exp(-dt / 1.2)

    def advance(self, f_from, f_to):
        n = max(1, int(np.ceil((f_to - f_from) / 1.0)))
        e = np.linspace(f_from, f_to, n + 1)
        for a, b in zip(e[:-1], e[1:]): self.substep(a, b)

    # ---- layers for the renderer: each is (pos, rgb, emit, rad)
    def layers(self, f):
        out = {}
        out["aircraft"] = self.aircraft(f)
        p = self.debris
        if len(p):
            x = p.age / p.life
            hot = np.exp(-p.age / 0.12)[:, None]
            rgb = p.aux * (1 - hot) + np.array([1.0, 0.7, 0.3], np.float32) * hot
            out["debris"] = (p.pos, rgb, 0.35 + 1.5 * hot[:, 0], PT_R * np.clip((1 - x) * 4, 0, 1))
        p = self.sparks
        if len(p):
            x = p.age / p.life
            out["sparks"] = (p.pos, ramp(x, [0, 0.25, 0.6, 1], [(1, 0.8, 0.4), (1, 0.5, 0.1), (1, 0.22, 0.03), (0.5, 0.05, 0.01)]),
                             np.interp(x, [0, 0.3, 1], [5, 3, 0.5]).astype(np.float32), (0.013 - 0.006 * x).astype(np.float32))
        p = self.exh
        if len(p):
            x = p.age / p.life
            out["exhaust"] = (p.pos, ramp(x, [0, 0.4, 1], [(0.55, 0.8, 1.0), (0.2, 0.45, 1.0), (0.6, 0.2, 0.5)]),
                              np.interp(x, [0, 0.5, 1], [5, 2.2, 0.2]).astype(np.float32), (0.02 - 0.012 * x).astype(np.float32))
        p = self.fire
        if len(p):
            sm = p.aux[:, 1] > 0; fl_ = ~sm
            T = p.aux[fl_, 0] * (0.8 + 0.4 * p.seed[fl_]); age = p.age[fl_]
            rgb = ramp(T, [0.1, 0.3, 0.6, 1.0, 1.4], [(0.6, 0.02, 0.0), (1.0, 0.07, 0.0), (1.0, 0.22, 0.02), (1.0, 0.45, 0.08), (1.0, 0.70, 0.30)])
            emit = np.interp(T, [0.2, 0.35, 0.6, 1.0, 1.4], [0.03, 0.2, 0.7, 1.9, 3.6]).astype(np.float32) * (FIRE_GAIN * 0.5 / self.q)      # additive: keep total light independent of particle count
            # two populations: big soft "body" blobs make the flame read as a continuous gas, fine bright grains keep it particulate
            body = p.seed[fl_] < 0.22; grow = (1 + 0.8 * np.clip(age / 0.4, 0, 1)) * np.clip(age / 0.015, 0.2, 1)
            rad = np.where(body, 0.085 + 0.25 * p.seed[fl_], 0.016 + 0.022 * p.seed[fl_]) * grow
            emit = emit * np.where(body, 0.30, 1.0)
            out["fire"] = (p.pos[fl_], rgb, emit, rad.astype(np.float32))
            if sm.any():
                x = p.age[sm] / p.life[sm]
                k2 = (p.seed[sm] * 37.0) % 1.0                      # soot: fine dark particles, not blobs
                c = np.array([0.022, 0.02, 0.023], np.float32) * (0.5 + 1.5 * k2)[:, None]
                out["smoke"] = (p.pos[sm], c, np.zeros(int(sm.sum()), np.float32), ((0.016 + 0.03 * k2) * np.clip(x * 8, 0.3, 1)).astype(np.float32))
        p = self.dust
        if len(p):
            x = p.age / p.life
            c = np.array([0.12, 0.10, 0.09], np.float32) * (0.45 + 0.75 * p.seed)[:, None]
            out["dust"] = (p.pos, c, np.full(len(p), 0.02, np.float32), ((0.012 + 0.02 * p.seed) * np.clip(x * 8, 0.3, 1) * np.clip((1 - x) * 3, 0, 1)).astype(np.float32))
        # ground lattice with shock rings and a glowing scar
        g = self.g_pos.copy(); t = f / FPS_SIM
        ring = np.zeros(len(g), np.float32)
        for fr, x, y, amp in self.rings:
            dtm = t - fr / FPS_SIM
            if dtm > 0:
                r = np.hypot(g[:, 0] - x, g[:, 1] - y)
                ring += amp * np.exp(-((r - 3.0 - 55.0 * dtm) / 0.8) ** 2) * np.exp(-dtm / 0.55) * 1.0
        g[:, 2] += 0.25 * ring
        h = np.clip(self.g_heat, 0, 1.5)
        base = np.array([0.10, 0.16, 0.26], np.float32)
        rgb = base[None] * (1 - np.clip(h, 0, 1)[:, None]) + np.array([1.0, 0.32, 0.05], np.float32) * np.clip(h, 0, 1)[:, None]
        rgb = rgb + ring[:, None] * np.array([0.3, 0.8, 1.0], np.float32)
        glow = np.zeros(len(g), np.float32)
        if self.fl.active:                                         # ground lit from below the fire
            glow = np.clip(self.fl.sample(g + np.array([0, 0, 0.6], np.float32))[1], 0, 1.2)
            rgb = rgb * (1 - np.clip(glow, 0, 1)[:, None]) + np.array([1.0, 0.36, 0.06], np.float32) * np.clip(glow, 0, 1)[:, None]
        out["ground"] = (g, rgb, (0.10 + 2.0 * h + 1.0 * ring + 1.6 * glow).astype(np.float32), (0.02 + 0.012 * ring).astype(np.float32))
        tw = 0.6 + 0.4 * np.sin(self.m_seed * 50 + t * 9)
        out["motes"] = (self.m_pos, np.tile(np.array([0.45, 0.6, 0.9], np.float32), (len(self.m_pos), 1)), (0.5 * tw).astype(np.float32),
                        (0.008 + 0.012 * self.m_seed).astype(np.float32))
        return out

    def focus(self, f):
        """point the camera should track: mass-weighted centre of the wreck, biased to the big pieces"""
        S = self.S
        if self.mpm:
            return self.focus_track[0] + S.vel * (f / FPS_SIM) if f < 0 else self.focus_track[int(min(f, S.T - 1))]
        if f < 0: c = (S.loc[0] * S.fmass[:, None]).sum(0) / S.fmass.sum() + S.vel * (f / FPS_SIM)
        else:
            i = int(min(f, S.T - 1)); c = (S.loc[i] * S.fmass[:, None]).sum(0) / S.fmass.sum()
        return c


ADDITIVE = ("fire", "exhaust")      # rendered as pure light (emission + transparency), never occlude the aircraft


def pack(layers, additive=False):
    """-> pos, rgb, emit, rad, alb for the opaque set (additive=False) or the additive set"""
    L = {k: v for k, v in layers.items() if (k in ADDITIVE) == additive}
    if not L:
        z = np.zeros(0, np.float32); return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32), z, z, z
    alb = np.concatenate([(np.zeros(len(v[0]), np.float32) if k == "sparks" else np.ones(len(v[0]), np.float32)) for k, v in L.items()])
    pos = np.concatenate([v[0] for v in L.values()]).astype(np.float32)
    rgb = np.concatenate([v[1] for v in L.values()]).astype(np.float32)
    emit = np.concatenate([v[2] for v in L.values()]).astype(np.float32)
    rad = np.concatenate([v[3] for v in L.values()]).astype(np.float32)
    ok = rad > 1e-4
    return pos[ok], rgb[ok], emit[ok], rad[ok], alb[ok]
