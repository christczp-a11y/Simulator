"""fp_geo.py — forward fuselage and cockpit of the Learjet 60 as SURFACES (quad grids), for the first-person shot.
Same outer shape as plane.py (same axes: +x nose, +y left, +z up; s = distance aft of the nose tip, x = X0 - s).
Every mesh vertex is also a material point of the crash simulation, so the mesh crumples and tears with the physics.

  python3 fp_geo.py out.npz [h]
Writes verts (N,3), quads (F,4), fmat (F,) render material, vpart (N,) part id, varea (N,) m2 per vertex, uv (N,2),
kin (N,) bool = driven by the rest of the aircraft, part_names, mat_names, eye (3,) pilot eye point, X0.
"""
import numpy as np, sys
from plane import fus_r, fus_z, X0

PARTS = ["radome", "skin", "glass", "floor", "bulkhead", "frame", "panel", "glareshield", "pedestal", "yoke", "seat", "avionics", "gear"]
MATS = ["skin", "glass", "floor", "bulkhead", "frame", "panel", "glareshield", "pedestal", "yoke", "seat", "avionics", "gear", "radome"]
PI = {n: i for i, n in enumerate(PARTS)}; MI = {n: i for i, n in enumerate(MATS)}
S_END = 4.6; S_KIN = 4.25
EYE_S, EYE_Y, EYE_Z = 2.95, 0.36, 0.52
# Hard things break as pieces. Every vertex belongs to one PIECE; the renderer keeps each piece rigid and lets the model fold, crack and
# tear only between pieces. Facet size in metres per part (0 = each patch of that part is one rigid piece):
PIECE = dict(radome=0.07, skin=0.085, glass=0.20, floor=0.13, bulkhead=0.11, frame=0.12, panel=0.09, glareshield=0.10, pedestal=0.09,
             yoke=0.0, seat=0.0, avionics=0.12, gear=0.0)
# thickness the renderer gives each piece (m), + = along the face normal (skin normals point into the cabin), - = against it
THICK = dict(radome=0.008, skin=0.0025, glass=0.025, floor=-0.010, bulkhead=-0.006, frame=-0.003, panel=-0.003, glareshield=-0.012,
             pedestal=-0.003, yoke=0.0, seat=-0.003, avionics=-0.002, gear=0.0)
# how weak the line between two pieces is in the simulation: distance-to-joint value written into 'seam' (0 = a full joint, 0.01 = half, None = no weakening)
SEAMV = dict(radome=0.01, skin=0.01, glass=None, floor=0.01, bulkhead=0.01, frame=0.01, panel=0.0, glareshield=0.01, pedestal=0.01, avionics=0.01)
PW, PH = 1.34, 0.50                                              # instrument panel plate (m); fp_tex.py draws the same layout


def panel_rects():
    """the instruments of fp_tex.py as rectangles (x0, x1, y0, y1, depth) in metres from the top-left corner of the panel image"""
    R = []; yc = 0.185
    for xm in (0.195, 0.387, 0.953, 1.145): R.append((xm - 0.092, xm + 0.092, yc - 0.092, yc + 0.104, 0.10))          # four displays with their key rows
    R.append((0.67 - 0.083, 0.67 + 0.083, 0.093, 0.227, 0.10))                                                         # engine display
    for i in range(3): R.append((0.67 + (i - 1) * 0.058 - 0.029, 0.67 + (i - 1) * 0.058 + 0.029, 0.271 - 0.029, 0.271 + 0.029, 0.11))   # standby instruments
    R.append((0.550, 0.787, 0.006, 0.056, 0.04))                                                                       # annunciator block
    for xm in (0.31, 1.03): R.append((xm - 0.027, xm + 0.080, 0.009, 0.043, 0.03))                                     # master warning / caution
    for x0 in (0.070, 0.750):                                                                                          # switch panels, three a side
        for j in range(3): R.append((x0 + j * 0.173, x0 + (j + 1) * 0.173 - 0.004, 0.342, 0.448, 0.03))
    return R


class Geo:
    def __init__(self): self.V = []; self.Q = []; self.FM = []; self.VP = []; self.VA = []; self.UV = []; self.PA = []; self.TH = []; self.TU = []; self.n = 0

    def patch(self, P, part, mat, closed_v=False, keep=None, vpart=None, fmat=None, uv=None, thick=None):
        """P (nu,nv,3) grid of points. keep (nu,nv) bool drops vertices (and their faces)."""
        nu, nv, _ = P.shape
        du = np.gradient(P, axis=0); dv = np.gradient(P, axis=1)
        if closed_v: dv = (np.roll(P, -1, 1) - np.roll(P, 1, 1)) / 2
        area = np.linalg.norm(np.cross(du, dv), axis=2)
        idx = self.n + np.arange(nu * nv).reshape(nu, nv)
        jn = nv if closed_v else nv - 1
        a = idx[:-1, :jn]; b = idx[1:, :jn]
        c = np.roll(idx, -1, 1)[1:, :jn]; d = np.roll(idx, -1, 1)[:-1, :jn]
        q = np.stack([a, b, c, d], -1).reshape(-1, 4)
        fm = np.full(len(q), MI[mat], np.int32) if fmat is None else fmat[:-1, :jn].reshape(-1)
        if keep is not None:
            k = keep.reshape(-1); ok = k[q - self.n].all(1); q = q[ok]; fm = fm[ok]
        U = np.stack(np.meshgrid(np.linspace(0, 1, nu), np.linspace(0, 1, nv), indexing="ij"), -1) if uv is None else uv
        self.V.append(P.reshape(-1, 3)); self.Q.append(q); self.FM.append(fm); self.UV.append(U.reshape(-1, 2))
        self.VP.append(np.full(nu * nv, PI[part], np.int32) if vpart is None else vpart.reshape(-1)); self.VA.append(area.reshape(-1))
        self.PA.append(np.full(nu * nv, len(self.PA), np.int32)); self.TU.append(np.full(nu * nv, -1.0, np.float32))
        self.TH.append(np.full(nu * nv, THICK[part] if thick is None else thick, np.float32) if vpart is None else np.array([THICK[n] for n in PARTS], np.float32)[vpart.reshape(-1)])
        self.n += nu * nv

    def plane(self, o, eu, ev, lu, lv, h, part, mat, keepfn=None, uv=None, thick=None):
        nu = max(2, int(round(lu / h)) + 1); nv = max(2, int(round(lv / h)) + 1)
        u = np.linspace(0, lu, nu); v = np.linspace(0, lv, nv)
        P = np.asarray(o, float) + u[:, None, None] * np.asarray(eu, float) + v[None, :, None] * np.asarray(ev, float)
        self.patch(P, part, mat, keep=None if keepfn is None else keepfn(P), uv=uv, thick=thick)

    def box(self, lo, hi, h, part, mat, faces="xXyYzZ"):
        lo = np.asarray(lo, float); hi = np.asarray(hi, float); d = hi - lo; ex, ey, ez = np.eye(3)
        if "x" in faces: self.plane(lo, ey, ez, d[1], d[2], h, part, mat)
        if "X" in faces: self.plane(lo + ex * d[0], ey, ez, d[1], d[2], h, part, mat)
        if "y" in faces: self.plane(lo, ex, ez, d[0], d[2], h, part, mat)
        if "Y" in faces: self.plane(lo + ey * d[1], ex, ez, d[0], d[2], h, part, mat)
        if "z" in faces: self.plane(lo, ex, ey, d[0], d[1], h, part, mat)
        if "Z" in faces: self.plane(lo + ez * d[2], ex, ey, d[0], d[1], h, part, mat)

    def tube(self, pts, rad, h, part, mat, nc=8):
        pts = np.asarray(pts, float); seg = np.linalg.norm(np.diff(pts, axis=0), axis=1); L = np.r_[0, np.cumsum(seg)]
        n = max(2, int(round(L[-1] / h)) + 1); t = np.linspace(0, L[-1], n)
        c = np.stack([np.interp(t, L, pts[:, k]) for k in range(3)], 1)
        tg = np.gradient(c, axis=0); tg /= np.linalg.norm(tg, axis=1, keepdims=True)
        ref = np.array([0.0, 0.0, 1.0]); a = np.cross(tg, ref)
        bad = np.linalg.norm(a, axis=1) < 0.2; a[bad] = np.cross(tg[bad], [0.0, 1.0, 0.0]); a /= np.linalg.norm(a, axis=1, keepdims=True)
        b = np.cross(tg, a); th = np.arange(nc) / nc * 2 * np.pi
        P = c[:, None] + rad * (np.cos(th)[None, :, None] * a[:, None] + np.sin(th)[None, :, None] * b[:, None])
        self.patch(P, part, mat, closed_v=True, thick=0.0); self.TU[-1] = np.repeat(t, nc).astype(np.float32)        # distance along the tube


def P_s(s, y, z): return np.stack(np.broadcast_arrays(X0 - np.asarray(s, float), y, z), -1)
def rad(s): return float(fus_r(s))
def zc(s): return float(fus_z(s))
def inside(P, margin):
    s = X0 - P[..., 0]; return np.hypot(P[..., 1], P[..., 2] - fus_z(s)) < fus_r(s) - margin


def glass_region(s, side):
    """windshield + side windows as one wrap-around transparency per side (side = degrees from the top centreline).
    Front edge is furthest forward on the centreline and sweeps aft toward the sides; the top edge leaves a strip of roof ahead of the pilot."""
    front = 2.02 + 0.55 * np.clip(side / 80.0, 0, None) ** 1.3
    top = 2.62 + 0.75 * np.clip((side - 10.0) / 55.0, 0, 1)
    return (side > 3.0) & (s > front) & (s < top) & (side < 82 - (s - 2.05) * 8)


def build(h=0.010):
    g = Geo()
    # ---- fuselage skin, one closed grid; the radome and the transparencies are regions of it
    ns = int(round((S_END - 0.03) / h)); nt = int(round(2 * np.pi * 0.98 / h))
    s = np.linspace(0.03, S_END, ns); th = np.arange(nt) / nt * 2 * np.pi
    S, TH = np.meshgrid(s, th, indexing="ij"); R = fus_r(S); Z = fus_z(S)
    P = np.stack([X0 - S, R * np.sin(TH), Z + R * np.cos(TH)], -1)
    side = np.abs(np.degrees(np.arctan2(np.sin(TH), np.cos(TH))))
    gl = glass_region(S, side); rd = S < 0.55
    vp = np.where(gl, PI["glass"], np.where(rd, PI["radome"], PI["skin"])).astype(np.int32)
    fm = np.where(gl, MI["glass"], np.where(rd, MI["radome"], MI["skin"])).astype(np.int32)
    g.patch(P, "skin", "skin", closed_v=True, vpart=vp, fmat=fm)
    # ---- window surrounds: a rubber-black tube along every edge of the transparencies, and the centre post
    def on_skin(sv, sd, sgn, lift=0.0):
        sv = np.asarray(sv, float); a = np.radians(np.asarray(sd, float)); r = fus_r(sv) + lift
        return np.stack([X0 - sv, sgn * r * np.sin(a), fus_z(sv) + r * np.cos(a)], -1)
    sd = np.linspace(3.0, 78.0, 90); g.tube(on_skin(np.linspace(2.0, 2.64, 40), 0.0, 1.0), 0.040, h, "frame", "glareshield", nc=10)
    for sgn in (-1.0, 1.0):
        g.tube(on_skin(2.02 + 0.55 * (sd / 80.0) ** 1.3, sd, sgn), 0.016, h, "frame", "glareshield", nc=6)
        sd2 = np.linspace(3.0, 71.4, 90); g.tube(on_skin(2.62 + 0.75 * np.clip((sd2 - 10.0) / 55.0, 0, 1), sd2, sgn), 0.016, h, "frame", "glareshield", nc=6)
        ss2 = np.linspace(2.55, 3.37, 60); g.tube(on_skin(ss2, 82 - (ss2 - 2.05) * 8, sgn), 0.016, h, "frame", "glareshield", nc=6)
    # ---- floor, bulkheads, frames
    zf = -0.60
    g.plane(P_s(S_END, -1.0, zf), (1, 0, 0), (0, 1, 0), S_END - 1.55, 2.0, h, "floor", "floor", keepfn=lambda Q: inside(Q, 0.025))
    g.plane(P_s(1.50, -0.7, zc(1.5) - 0.7), (0, 1, 0), (0, 0, 1), 1.4, 1.4, h, "bulkhead", "bulkhead", keepfn=lambda Q: inside(Q, 0.02))
    def door(Q): return inside(Q, 0.02) & ~((np.abs(Q[..., 1]) < 0.30) & (Q[..., 2] < 0.45) & (Q[..., 2] > zf))
    g.plane(P_s(3.42, -1.0, zc(3.42) - 1.0), (0, 1, 0), (0, 0, 1), 2.0, 2.0, h, "bulkhead", "bulkhead", keepfn=door)
    for sf in np.arange(1.9, S_END, 0.4):
        r0 = rad(sf) - 0.012; nr = 6; rr = r0 - np.arange(nr) * h
        A = np.stack([np.full((nr, nt), X0 - sf), rr[:, None] * np.sin(th)[None], zc(sf) + rr[:, None] * np.cos(th)[None]], -1)
        sd = np.abs(np.degrees(np.arctan2(np.sin(th), np.cos(th))))
        g.patch(A, "frame", "frame", closed_v=True, keep=np.broadcast_to(~((sf > 1.95) & (sf < 3.45) & (sd < 80))[None], (nr, nt)))
    # ---- instrument panel (leans 8 deg, top forward), glareshield with a lip, centre pedestal
    lean = np.radians(8); ez = np.array([np.sin(lean), 0, np.cos(lean)])
    def halfwidth(c, lim, margin):                              # how far a row across the cabin can reach before it meets the skin
        s_ = X0 - c[:, 0]; rr = np.clip(fus_r(s_) - margin, 0.01, None); dz = c[:, 2] - fus_z(s_)
        return np.minimum(lim, np.sqrt(np.clip(rr ** 2 - dz ** 2, 1e-4, None)))
    def strip(centers, halfw, part, mat, uvw=0.0, thick=None):
        """rows of points across the cabin, each as wide as the fuselage allows there, so the edge follows the skin smoothly"""
        nv = max(2, int(round(2 * halfw.max() / h)) + 1); f = np.linspace(-1, 1, nv); P = np.repeat(centers[:, None, :], nv, 1).astype(float)
        P[..., 1] += halfw[:, None] * f[None]; uv = None
        if uvw: uv = np.stack([(P[..., 1] + uvw / 2) / uvw, np.broadcast_to(np.linspace(0, 1, len(centers))[:, None], P.shape[:2])], -1)
        g.patch(P, part, mat, uv=uv, thick=thick)
    pw, ph = 1.34, 0.50; oc = P_s(2.22, 0.0, -0.15); o = P_s(2.22, -pw / 2, -0.15)
    cen = oc + np.linspace(0, ph, int(round(ph / h)) + 1)[:, None] * ez
    strip(cen, halfwidth(cen, pw / 2, 0.03), "panel", "panel", uvw=pw)
    top = o + ez * ph                                           # panel top edge
    sg0, sg1 = X0 - top[0] - 0.02, 2.02                         # glareshield from just aft of the panel top to the windshield base
    sr = np.linspace(sg0 + 0.24, sg1, int(round((sg0 + 0.24 - sg1) / h)) + 1); cen = P_s(sr, 0.0, top[2] + 0.035)
    strip(cen, halfwidth(cen, 0.72, 0.03), "glareshield", "glareshield")
    zr = np.linspace(top[2] - 0.02, top[2] + 0.035, 7); cen = P_s(np.full(7, sg0 + 0.24), 0.0, zr)
    strip(cen, halfwidth(cen, 0.72, 0.03), "glareshield", "glareshield", thick=0.0)       # the lip: a single surface, the padded top slab ends behind it
    n1 = int(round(0.85 / h)); n2 = int(round(0.28 / h)); ss = np.linspace(2.22, 3.07, n1); yy = np.linspace(-0.14, 0.14, n2)
    zt = np.interp(ss, [2.22, 2.5, 3.07], [-0.15, -0.26, -0.33])
    g.patch(np.stack([np.broadcast_to((X0 - ss)[:, None], (n1, n2)), np.broadcast_to(yy[None], (n1, n2)), np.broadcast_to(zt[:, None], (n1, n2))], -1), "pedestal", "pedestal")
    for y0 in (-0.14, 0.14):
        n3 = int(round(0.45 / h)); f = np.linspace(0, 1, n3)
        g.patch(np.stack([np.broadcast_to((X0 - ss)[:, None], (n1, n3)), np.full((n1, n3), y0), zf + (zt[:, None] - zf) * f[None]], -1), "pedestal", "pedestal")
    for y0 in (-0.05, 0.05):                                    # thrust levers
        g.tube([P_s(2.62, y0, -0.28), P_s(2.56, y0, -0.12)], 0.012, h, "yoke", "yoke", nc=6)
        g.tube([P_s(2.56, y0 - 0.035, -0.12), P_s(2.56, y0 + 0.035, -0.12)], 0.017, h, "yoke", "yoke", nc=8)
    # ---- control columns with ram's-horn wheels
    for y0 in (-EYE_Y, EYE_Y):
        g.tube([P_s(2.40, y0, zf), P_s(2.44, y0, -0.30), P_s(2.52, y0, -0.06)], 0.020, h, "yoke", "yoke")
        a = np.radians(np.linspace(200, 340, 24)); w = 0.15
        arc = [P_s(2.53, y0 + w * np.cos(t), -0.06 + 0.02 + w * 0.55 * (1 + np.sin(t))) for t in a]
        horn = [P_s(2.55, y0 - w * 0.94, 0.16)] + arc + [P_s(2.55, y0 + w * 0.94, 0.16)]
        g.tube(horn, 0.016, h, "yoke", "yoke")
    # ---- crew seats
    for y0 in (-EYE_Y, EYE_Y):
        g.plane(P_s(3.16, y0 - 0.23, -0.27), (1, 0, 0), (0, 1, 0), 0.46, 0.46, h, "seat", "seat", thick=-0.06)
        bk = np.array([-0.2, 0, 1.0]); bk /= np.linalg.norm(bk)
        g.plane(P_s(3.16, y0 - 0.23, -0.27), (0, 1, 0), bk, 0.46, 0.80, h, "seat", "seat", thick=-0.06)
        g.box(P_s(3.12, y0 - 0.20, zf + 0.005), P_s(2.76, y0 + 0.20, -0.275), h, "seat", "seat", faces="xXyY")
    # ---- what is inside the nose: radar antenna, avionics boxes, nose gear in its well
    g.plane(P_s(0.42, -0.14, zc(0.42) - 0.14), (0, 1, 0), (0, 0, 1), 0.28, 0.28, h, "avionics", "avionics", keepfn=lambda Q: inside(Q, 0.02))
    for (sa, sb, ya, yb, za, zb) in ((0.80, 1.15, -0.22, -0.02, -0.38, -0.12), (0.80, 1.20, 0.02, 0.24, -0.40, -0.14), (1.18, 1.44, -0.20, 0.18, -0.20, 0.04)):
        g.box(P_s(sb, ya, za), P_s(sa, yb, zb), h, "avionics", "avionics")
    g.box(P_s(2.30, -0.10, zf - 0.24), P_s(1.62, 0.10, zf - 0.02), h, "gear", "gear")

    V = np.concatenate(g.V).astype(np.float32); Q = np.concatenate(g.Q).astype(np.int32)
    used = np.zeros(len(V), bool); used[Q.ravel()] = True; remap = np.cumsum(used) - 1          # drop vertices no face uses
    V = V[used]; Q = remap[Q].astype(np.int32)
    for k in ("VP", "VA", "UV", "PA", "TH", "TU"): setattr(g, k, [np.concatenate(getattr(g, k))[used]])
    # riveted joints of the skin: along the ring frames (every 0.4 m) and along stringers (every 30 deg). seam = distance to the nearest joint (m)
    vp_all = g.VP[0]; sv = X0 - V[:, 0].astype(np.float64); rr = np.hypot(V[:, 1], V[:, 2] - fus_z(sv)); tt = np.degrees(np.arctan2(V[:, 1], V[:, 2] - fus_z(sv)))
    ds = np.abs((sv - 0.55 + 0.2) % 0.4 - 0.2); dt_ = np.radians(np.abs((tt + 15.0) % 30.0 - 15.0)) * rr
    seam = np.where(vp_all == PI["skin"], np.minimum(ds, dt_), 9.0).astype(np.float32)
    # ---- pieces. Skin facets never cross a riveted joint (they are cut per bay); the panel is cut along its instruments
    from scipy.spatial import cKDTree
    rng = np.random.default_rng(3); N = len(V); va = g.VA[0]; uv = g.UV[0]; thick = g.TH[0].copy(); piece = np.full(N, -1, np.int64); nid = 0
    bay = np.where(vp_all == PI["skin"], (np.floor((sv - 0.55) / 0.4).astype(np.int64) + 3) * 100 + np.floor((tt + 180.0) / 30.0).astype(np.int64), 0)
    key = g.PA[0].astype(np.int64) * 100000 + vp_all.astype(np.int64) * 5000 + bay
    def voronoi(X, area, size):
        k = max(1, int(round(area / size ** 2)))
        if k == 1 or len(X) < 12: return np.zeros(len(X), np.int64), X.mean(0)[None]
        seeds = X[rng.choice(len(X), min(k, len(X) // 6), replace=False)]
        for _ in range(2):
            _, lab = cKDTree(seeds).query(X); cnt = np.bincount(lab, minlength=len(seeds))
            seeds = (np.stack([np.bincount(lab, X[:, j], len(seeds)) for j in range(3)], 1) / np.maximum(cnt, 1)[:, None])[cnt > 0]
        _, lab = cKDTree(seeds).query(X); us, inv = np.unique(lab, return_inverse=True); return inv, seeds[us]
    pseed = []; pvor = []                                           # per piece: its Voronoi seed, and the id of the Voronoi tiling it belongs to (-1 = not a Voronoi cell)
    for gi, kq in enumerate(np.unique(key)):
        m = np.flatnonzero(key == kq); part = PARTS[vp_all[m[0]]]; size = PIECE[part]; lab = np.zeros(len(m), np.int64); sd = None; nfix = 0
        if part == "panel":
            xi = (1.0 - uv[m, 0]) * PW; yi = (1.0 - uv[m, 1]) * PH; lab[:] = -1; nr = 0
            for (x0, x1, y0, y1, dep) in panel_rects():
                r = (xi >= x0) & (xi <= x1) & (yi >= y0) & (yi <= y1) & (lab < 0)
                if r.any(): lab[r] = nr; nr += 1; thick[m[r]] = -dep
            rest = lab < 0; nfix = nr
            if rest.any(): l2, sd = voronoi(V[m[rest]].astype(np.float64), float(va[m[rest]].sum()), size); lab[rest] = nr + l2
        elif size > 0: lab, sd = voronoi(V[m].astype(np.float64), float(va[m].sum()), size)
        nl = int(lab.max()) + 1
        for j in range(nl):
            if sd is not None and j >= nfix: pseed.append(sd[j - nfix]); pvor.append(gi)
            else: pseed.append(V[m[lab == j]].mean(0)); pvor.append(-1)
        piece[m] = nid + lab; nid += nl
    # tubes (window surrounds, centre post) break into lengths, not into shell fragments: re-cut them across the axis (done after the loop above
    # so that the random tilings of everything else stay exactly as they were)
    tu = g.TU[0]; tm = np.flatnonzero((tu >= 0) & (vp_all == PI["frame"]))
    if len(tm):
        seg = np.floor(tu[tm] / 0.14).astype(np.int64); k2 = g.PA[0][tm].astype(np.int64) * 1000 + seg; piece[tm] = nid + np.unique(k2, return_inverse=True)[1]
        us, piece = np.unique(piece, return_inverse=True); old = us < nid; ps2 = np.zeros((len(us), 3)); pv2 = np.full(len(us), -1)
        ps2[old] = np.array(pseed)[us[old]]; pv2[old] = np.array(pvor)[us[old]]
        for j in np.flatnonzero(~old): ps2[j] = V[piece == j].mean(0)
        pseed = list(ps2); pvor = list(pv2)
    thick = np.where((vp_all <= PI["glass"]), np.minimum(thick, 0.3 * fus_r(sv)), thick).astype(np.float32)      # the nose tip is too tight for a full-thickness shell
    pq = piece[Q]; bridge = (pq != pq[:, :1]).any(1); bv = np.unique(Q[bridge])
    sval = np.array([9.0 if SEAMV.get(n) is None else SEAMV[n] for n in PARTS], np.float32)[vp_all[bv]]; seam[bv] = np.minimum(seam[bv], sval)
    out = dict(verts=V, quads=Q, fmat=np.concatenate(g.FM).astype(np.int32), vpart=np.concatenate(g.VP).astype(np.int32),
               varea=np.concatenate(g.VA).astype(np.float32), uv=np.concatenate(g.UV).astype(np.float32),
               kin=(X0 - V[:, 0]) > S_KIN, seam=seam, piece=piece.astype(np.int32), thick=thick, pseed=np.array(pseed, np.float32), pvor=np.array(pvor, np.int32), part_names=np.array(PARTS), mat_names=np.array(MATS),
               eye=np.array([X0 - EYE_S, EYE_Y, EYE_Z], np.float32), X0=np.float32(X0), h=np.float32(h))
    return out


if __name__ == "__main__":
    o = build(float(sys.argv[2]) if len(sys.argv) > 2 else 0.010)
    np.savez_compressed(sys.argv[1], **o)
    V = o["verts"]; print(len(V), "vertices", len(o["quads"]), "quads", "bbox", V.min(0).round(2), V.max(0).round(2))
    for i, n in enumerate(PARTS):
        m = o["vpart"] == i; print(f"{n:12s} {int(m.sum()):7d} verts  area {float(o['varea'][m].sum()):6.2f} m2  pieces {len(np.unique(o['piece'][m]))}")
    cnt = np.bincount(o["piece"]); print("pieces", len(cnt), "verts per piece min/median/max", cnt.min(), int(np.median(cnt)), cnt.max())
