"""Coarse 3-D gas solver for the fire (numpy only, so it also runs inside Blender's Python).
Stable-fluids style: semi-Lagrangian advection, buoyancy from temperature, vorticity confinement,
FFT pressure projection with a divergence source (combustion expansion). Ground is a free-slip wall
(even extension in z); x/y are periodic, so keep the domain padded.
The grid only carries velocity + temperature; the visible fire is particles advected through it."""
import numpy as np


class Fluid:
    def __init__(self, origin, size, h=0.5, buoy=38.0, cool=0.8, vort=3.0, damp=0.25):
        self.o = np.asarray(origin, np.float32); self.h = float(h)
        self.n = nx, ny, nz = tuple(int(round(s / h)) for s in size)
        self.u = np.zeros((3, nx, ny, nz), np.float32); self.T = np.zeros((nx, ny, nz), np.float32)
        self.S = np.zeros((nx, ny, nz), np.float32)          # divergence source (1/s), cleared every step
        self.buoy, self.cool, self.vort, self.damp = buoy, cool, vort, damp
        kx = np.fft.fftfreq(nx) * 2 * np.pi; ky = np.fft.fftfreq(ny) * 2 * np.pi; kz = np.fft.rfftfreq(2 * nz) * 2 * np.pi
        lam = -(4.0 / h ** 2) * (np.sin(kx / 2)[:, None, None] ** 2 + np.sin(ky / 2)[None, :, None] ** 2 + np.sin(kz / 2)[None, None, :] ** 2)
        lam[0, 0, 0] = 1.0; self.ilam = (1.0 / lam).astype(np.float32); self.ilam[0, 0, 0] = 0.0
        I = np.indices((nx, ny, nz), dtype=np.float32); self.I = I
        self.N = nx * ny * nz; self.active = False; self.time = 0.0

    # ---- sampling
    def _setup(self, x, y, z):
        nx, ny, nz = self.n
        x = np.clip(x, 0, nx - 1.001); y = np.clip(y, 0, ny - 1.001); z = np.clip(z, 0, nz - 1.001)
        i = x.astype(np.int32); j = y.astype(np.int32); k = z.astype(np.int32)
        return (i * ny + j) * nz + k, (x - i).astype(np.float32), (y - j).astype(np.float32), (z - k).astype(np.float32)

    def _gather(self, f, b, wx, wy, wz):
        nx, ny, nz = self.n; f = f.reshape(-1); sy = nz; sx = ny * nz
        c00 = f[b] + (f[b + 1] - f[b]) * wz; c01 = f[b + sy] + (f[b + sy + 1] - f[b + sy]) * wz
        c10 = f[b + sx] + (f[b + sx + 1] - f[b + sx]) * wz; c11 = f[b + sx + sy] + (f[b + sx + sy + 1] - f[b + sx + sy]) * wz
        c0 = c00 + (c01 - c00) * wy; c1 = c10 + (c11 - c10) * wy
        return c0 + (c1 - c0) * wx

    def sample(self, pos):
        """world positions (N,3) -> velocity (N,3), temperature (N,)"""
        g = (pos - self.o) / self.h - 0.5
        b, wx, wy, wz = self._setup(g[:, 0], g[:, 1], g[:, 2])
        v = np.stack([self._gather(self.u[c], b, wx, wy, wz) for c in range(3)], 1)
        return v, self._gather(self.T, b, wx, wy, wz)

    # ---- sources
    def cells(self, pos):
        nx, ny, nz = self.n
        g = np.floor((pos - self.o) / self.h).astype(np.int64)
        ok = (g[:, 0] >= 1) & (g[:, 0] < nx - 1) & (g[:, 1] >= 1) & (g[:, 1] < ny - 1) & (g[:, 2] >= 0) & (g[:, 2] < nz - 1)
        return (g[:, 0] * ny + g[:, 1]) * nz + g[:, 2], ok

    def burn(self, pos, heat, tmax, div, divmax):
        """add heat and gas expansion at emitter positions (rates already multiplied by dt for heat)"""
        c, ok = self.cells(pos); c = c[ok]
        if len(c) == 0: return
        cnt = np.bincount(c, minlength=self.N).astype(np.float32).reshape(self.n)
        np.minimum(self.T + cnt * heat, np.maximum(self.T, tmax), out=self.T)
        np.maximum(self.S, np.minimum(cnt * div, divmax), out=self.S)
        self.active = True

    def drag(self, pos, vel, alpha, vmul=1.0):
        """pull the gas toward the velocity of objects/emitters occupying the cells"""
        c, ok = self.cells(pos); c = c[ok]
        if len(c) == 0: return
        cnt = np.bincount(c, minlength=self.N).astype(np.float32)
        m = cnt > 0; a = np.minimum(1.0, alpha * cnt[m])
        for k in range(3):
            vs = np.bincount(c, weights=vel[ok, k], minlength=self.N)[m] / cnt[m] * vmul
            uk = self.u[k].reshape(-1); uk[m] += (vs.astype(np.float32) - uk[m]) * a

    # ---- one step
    def step(self, dt):
        u, T, h = self.u, self.T, self.h; nx, ny, nz = self.n
        d = lambda f, ax: (np.roll(f, -1, ax) - np.roll(f, 1, ax)) * (0.5 / h)
        u[2] += (dt * self.buoy) * T
        if self.vort > 0:
            wx = d(u[2], 1) - d(u[1], 2); wy = d(u[0], 2) - d(u[2], 0); wz = d(u[1], 0) - d(u[0], 1)
            mag = np.sqrt(wx * wx + wy * wy + wz * wz)
            gx, gy, gz = d(mag, 0), d(mag, 1), d(mag, 2)
            inv = 1.0 / (np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-3); gx *= inv; gy *= inv; gz *= inv
            e = self.vort * h * dt
            fx = e * (gy * wz - gz * wy); fy = e * (gz * wx - gx * wz); fz = e * (gx * wy - gy * wx)
            for f in (fx, fy, fz): f[:, :, :1] = 0; f[:, :, -1:] = 0
            u[0] += fx; u[1] += fy; u[2] += fz
        # semi-Lagrangian advection
        s = dt / h; I = self.I
        b, wx, wy, wz = self._setup((I[0] - u[0] * s).reshape(-1), (I[1] - u[1] * s).reshape(-1), (I[2] - u[2] * s).reshape(-1))
        new = [self._gather(u[c], b, wx, wy, wz).reshape(self.n) for c in range(3)]
        Tn = self._gather(T, b, wx, wy, wz).reshape(self.n)
        for c in range(3): u[c] = new[c]
        T[:] = Tn * np.exp(-dt / self.cool)
        u *= np.exp(-dt * self.damp)
        # pressure projection with expansion source; w mirrored odd at floor and ceiling
        wp = np.concatenate([-u[2][:, :, :1], u[2], -u[2][:, :, -1:]], 2)
        div = d(u[0], 0) + d(u[1], 1) + (wp[:, :, 2:] - wp[:, :, :-2]) * (0.5 / h) - self.S
        ext = np.concatenate([div, div[:, :, ::-1]], 2)
        p = np.fft.irfftn(np.fft.rfftn(ext) * self.ilam, s=ext.shape)[:, :, :nz].astype(np.float32)
        u[0] -= d(p, 0); u[1] -= d(p, 1)
        pp = np.concatenate([p[:, :, :1], p, p[:, :, -1:]], 2)
        u[2] -= (pp[:, :, 2:] - pp[:, :, :-2]) * (0.5 / h)
        self.S[:] = 0; self.time += dt
