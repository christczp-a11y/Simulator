"""Reader for an mfire.py run (Blender Mantaflow cache, OpenVDB). Gives fx.py the gas of the real solver through the same
interface as fluid.Fluid, so the fire particles ride Mantaflow's velocity field and take their heat from its flame field.
If the run has wavelet noise (noise/fluid_noise_####.vdb) the flame and smoke come from that finer grid.
Needs the openvdb module that ships with Blender's Python."""
import os, json
import numpy as np


class Grid:
    """dense copy of the active box of one VDB grid; world position of voxel i is lo + (i + 0.5) * h"""
    def __init__(self, g, lo, ncomp=1):
        self.h = float(g.transform.voxelSize()[0]); self.lo = lo; self.ok = g.activeVoxelCount() > 0
        if not self.ok: return
        b0, b1 = g.evalActiveVoxelBoundingBox(); b0 = np.array(b0) - 1; b1 = np.array(b1) + 1
        self.sh = tuple(int(v) for v in (b1 - b0 + 1)); self.b0 = b0.astype(np.float32)
        self.a = np.zeros(self.sh + ((ncomp,) if ncomp > 1 else ()), np.float32); g.copyToArray(self.a, ijk=tuple(int(v) for v in b0))

    def sample(self, pos):
        n = len(pos)
        if not self.ok: return np.zeros((n,) + self.a.shape[3:] if hasattr(self, "a") else n, np.float32)
        g = (pos - self.lo) / self.h - 0.5 - self.b0; nx, ny, nz = self.sh
        ok = (g[:, 0] >= 0) & (g[:, 0] < nx - 1) & (g[:, 1] >= 0) & (g[:, 1] < ny - 1) & (g[:, 2] >= -0.5) & (g[:, 2] < nz - 1)
        g = np.clip(g, 0, np.array([nx, ny, nz], np.float32) - 1.001); i = g.astype(np.int32); f = (g - i).astype(np.float32)
        b = (i[:, 0] * ny + i[:, 1]) * nz + i[:, 2]; sy = nz; sx = ny * nz
        a = self.a.reshape(nx * ny * nz, -1); wx, wy, wz = f[:, 0:1], f[:, 1:2], f[:, 2:3]
        c00 = a[b] + (a[b + 1] - a[b]) * wz; c01 = a[b + sy] + (a[b + sy + 1] - a[b + sy]) * wz
        c10 = a[b + sx] + (a[b + sx + 1] - a[b + sx]) * wz; c11 = a[b + sx + sy] + (a[b + sx + sy + 1] - a[b + sx + sy]) * wz
        c0 = c00 + (c01 - c00) * wy; c1 = c10 + (c11 - c10) * wy
        r = (c0 + (c1 - c0) * wx) * ok[:, None]
        return r if self.a.ndim == 4 else r[:, 0]


class MField:
    def __init__(self, fdir, tl, tgain=2.0):
        import openvdb
        self.vdb = openvdb; self.dir = fdir; M = json.load(open(os.path.join(fdir, "meta.json")))
        self.h = float(M["cell"]); self.lo = np.array(M["lo"], np.float32); self.i0 = int(M["i0"]); self.i1 = int(M["i1"])
        self.tl = np.asarray(tl, np.float64); self.cur = None; self.active = False; self.tgain = tgain
        self.F = self.D = self.V = None; self.flame_m3 = 0.0; self.cdf = None

    # the solver already ran: sources and stepping are no-ops here
    def burn(self, *a, **k): pass
    def drag(self, *a, **k): pass
    def step(self, *a, **k): pass

    def path(self, i, noise=False):
        return os.path.join(self.dir, "noise" if noise else "data", "fluid_%s_%04d.vdb" % ("noise" if noise else "data", i + 1))

    def vol_path(self, i):
        """file to render as a volume (the fine one if there is one) and the cell size of its grids"""
        p = self.path(i, True)
        if os.path.exists(p):
            return p, float(self.vdb.readAll(p)[0][0].transform.voxelSize()[0])
        return self.path(i), self.h

    def seek(self, f):
        """make the field of the output frame that covers sim-frame time f current"""
        if f < self.tl[self.i0]: self.active = False; return
        i = int(np.clip(np.searchsorted(self.tl, f), self.i0, self.i1))
        if i != self.cur: self.load(i)

    def load(self, i):
        self.cur = i; p = self.path(i); self.active = False; self.F = self.D = self.V = None; self.cdf = None; self.flame_m3 = 0.0
        if not os.path.exists(p): return
        G = {g.name: g for g in self.vdb.readAll(p)[0]}; S = G; pn = self.path(i, True)
        if os.path.exists(pn): S = {g.name: g for g in self.vdb.readAll(pn)[0]}
        if "velocity" in G: self.V = Grid(G["velocity"], self.lo, 3)
        if "flame" in S: self.F = Grid(S["flame"], self.lo)
        if "density" in S: self.D = Grid(S["density"], self.lo)
        self.active = self.V is not None and self.V.ok
        if self.F is not None and self.F.ok:
            w = np.clip(self.F.a.ravel() - 0.03, 0, None).astype(np.float64); s = w.sum()
            self.flame_m3 = float((self.F.a > 0.05).sum() * self.F.h ** 3); self.cdf = np.cumsum(w) / s if s > 0 else None

    def sample(self, pos):
        """world positions (N,3) -> gas velocity (N,3) in m per simulated second, heat (N,) = tgain * flame"""
        n = len(pos); pos = np.asarray(pos, np.float32)
        v = self.V.sample(pos) if (self.active and n and self.V is not None and self.V.ok) else np.zeros((n, 3), np.float32)
        T = self.F.sample(pos) * self.tgain if (self.active and n and self.F is not None and self.F.ok) else np.zeros(n, np.float32)
        return v.astype(np.float32), T.astype(np.float32)

    def smoke(self, pos):
        n = len(pos)
        return self.D.sample(np.asarray(pos, np.float32)) if (self.active and n and self.D is not None and self.D.ok) else np.zeros(n, np.float32)

    def seed(self, n, rng):
        """n random points inside the flame, more where it is hotter -> positions (n,3)"""
        if n <= 0 or self.cdf is None: return np.zeros((0, 3), np.float32)
        F = self.F; c = np.searchsorted(self.cdf, rng.random(n)); nx, ny, nz = F.sh
        ijk = np.stack([c // (ny * nz), (c // nz) % ny, c % nz], 1).astype(np.float32)
        return ((ijk + F.b0 + rng.random((n, 3)).astype(np.float32)) * F.h + self.lo).astype(np.float32)
