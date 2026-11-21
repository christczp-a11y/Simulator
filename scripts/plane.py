"""Learjet 60 as a structured particle lattice. numpy/scipy only.
Axes: +x forward (nose), +y left wing, +z up. Origin near CG. Units: metres.
"""
import numpy as np
from scipy.interpolate import PchipInterpolator

H = 0.03          # surface lattice spacing
X0 = 7.9          # x of nose tip (s = distance aft of nose, x = X0 - s)

PARTS = ["nose", "cockpit", "cabin_fwd", "cabin_mid", "aft_fuse", "tailcone",
         "windshield", "windows", "wing_L", "wing_R", "winglet_L", "winglet_R",
         "engine_L", "engine_R", "pylon_L", "pylon_R", "fin", "stab_L", "stab_R",
         "deltafin_L", "deltafin_R", "floor", "seats", "bulkhead", "fuel_L", "fuel_R",
         "core_L", "core_R", "fan_L", "fan_R", "navlight_L", "navlight_R", "beacon"]
PID = {n: i for i, n in enumerate(PARTS)}

_S = np.array([0, 0.25, 0.7, 1.4, 2.2, 3.1, 4.0, 4.8, 11.0, 12.4, 13.8, 15.2, 16.2, 16.75, 16.9])
_R = np.array([0.0, 0.13, 0.30, 0.50, 0.68, 0.84, 0.94, 0.98, 0.98, 0.92, 0.76, 0.50, 0.27, 0.10, 0.0])
_Z = np.array([-0.34, -0.32, -0.29, -0.24, -0.17, -0.09, -0.03, 0, 0, 0.04, 0.12, 0.24, 0.35, 0.42, 0.44])
fus_r = PchipInterpolator(_S, _R)
fus_z = PchipInterpolator(_S, _Z)
fus_dr = fus_r.derivative()

rng = np.random.default_rng(7)


def _meridian_stations(rfun, drfun, s0, s1, h):
    out = []; s = s0 + 1e-4
    while s < s1:
        out.append(s)
        s += h / np.sqrt(1.0 + float(drfun(s)) ** 2)
    return np.array(out)


def revolve(rfun, drfun, s0, s1, h, axis_x0, cy=0.0, czfun=None):
    """Surface of revolution about the x axis. returns pos, nrm, s, theta."""
    P = []; N = []; SS = []; TH = []
    for j, s in enumerate(_meridian_stations(rfun, drfun, s0, s1, h)):
        r = float(rfun(s)); dr = float(drfun(s))
        if r < h * 0.3:
            continue
        n = max(3, int(round(2 * np.pi * r / h)))
        th = (np.arange(n) + (0.5 if j % 2 else 0.0)) / n * 2 * np.pi
        cz = float(czfun(s)) if czfun is not None else 0.0
        P.append(np.stack([np.full(n, axis_x0 - s), cy + r * np.sin(th), cz + r * np.cos(th)], 1))
        nn = np.stack([np.full(n, dr), np.sin(th), np.cos(th)], 1)
        N.append(nn / np.linalg.norm(nn, axis=1, keepdims=True))
        SS.append(np.full(n, s)); TH.append(th)
    return np.concatenate(P), np.concatenate(N), np.concatenate(SS), np.concatenate(TH)


def _airfoil_table(t):
    x = np.linspace(0, 1, 600) ** 1.6
    y = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    arc = np.concatenate([[0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    return x, y, arc


def lifting_surface(P0, P1, c0, c1, t0, t1, tdir, h=H, chord_dir=(-1, 0, 0)):
    """Tapered wing-like surface from root LE P0 to tip LE P1."""
    P0 = np.asarray(P0, float); P1 = np.asarray(P1, float)
    cd = np.asarray(chord_dir, float); td = np.asarray(tdir, float); td /= np.linalg.norm(td)
    span = np.linalg.norm(P1 - P0)
    # true spacing between stations measured perpendicular to chord
    sd = (P1 - P0) / span
    perp = np.linalg.norm(sd - cd * sd.dot(cd))
    nst = max(2, int(round(span * perp / h)))
    P = []; N = []; U = []; XC = []
    for i in range(nst + 1):
        u = i / nst
        le = P0 + (P1 - P0) * u; c = c0 + (c1 - c0) * u; t = t0 + (t1 - t0) * u
        x, y, arc = _airfoil_table(t)
        L = arc[-1] * c
        m = max(2, int(round(L / h)))
        a = (np.arange(m) + (0.5 if i % 2 else 0.25)) / m * arc[-1]
        xs = np.interp(a, arc, x); ys = np.interp(a, arc, y)
        dydx = np.gradient(y, x, edge_order=1); dy = np.interp(a, arc, dydx)
        for sgn in (1.0, -1.0):
            P.append(le + np.outer(xs * c, cd) + np.outer(sgn * ys * c, td))
            nn = np.outer(np.ones(m), sgn * td) - np.outer(np.clip(dy, -8, 8), cd)
            N.append(nn / np.linalg.norm(nn, axis=1, keepdims=True))
            U.append(np.full(m, u)); XC.append(xs)
    return np.concatenate(P), np.concatenate(N), np.concatenate(U), np.concatenate(XC)


def mirror(P, N):
    P2 = P.copy(); N2 = N.copy(); P2[:, 1] *= -1; N2[:, 1] *= -1
    return P2, N2


def build():
    pos = []; nrm = []; part = []

    def add(P, N, pid):
        pos.append(P); nrm.append(N)
        part.append(np.full(len(P), pid, np.int32) if np.isscalar(pid) else pid)

    # ---------------- fuselage shell
    P, N, S, TH = revolve(fus_r, fus_dr, 0.0, 16.9, H, X0, czfun=fus_z)
    pid = np.select([S < 1.3, S < 3.4, S < 7.0, S < 10.6, S < 13.6],
                    [PID["nose"], PID["cockpit"], PID["cabin_fwd"], PID["cabin_mid"], PID["aft_fuse"]],
                    PID["tailcone"]).astype(np.int32)
    elev = np.degrees(np.arcsin(np.clip(np.cos(TH), -1, 1)))      # 90 = top, 0 = side
    side = np.abs(np.degrees(np.arctan2(np.sin(TH), np.cos(TH))))  # 0 = top .. 180 bottom
    ws = (S > 2.05) & (S < 3.38) & (side > 5) & (side < 78 - (S - 2.05) * 9) & (side > 5 + (2.6 - S).clip(0) * 60)
    pid[ws] = PID["windshield"]
    # cabin windows: 6 per side
    zc = fus_z(S); rr = fus_r(S)
    zloc = rr * np.cos(TH)
    for i in range(6):
        sc = 4.75 + i * 1.02
        du = np.abs(S - sc) / 0.19; dv = np.abs(zloc - 0.30) / 0.24
        w = (du ** 4 + dv ** 4 < 1.0) & (np.abs(np.sin(TH)) > 0.5)
        pid[w] = PID["windows"]
    add(P, N, pid)

    # ---------------- wings
    sweep = np.tan(np.radians(13.0)); dih = np.tan(np.radians(2.5))
    c_root, c_tip, ytip = 2.75, 1.05, 6.30
    x_rle = X0 - 6.45
    x_qc = lambda y: x_rle - 0.25 * c_root - sweep * y
    P0 = np.array([x_rle, 0.0, -0.66]); P1 = np.array([x_qc(ytip) + 0.25 * c_tip, ytip, -0.66 + dih * ytip])
    Pw, Nw, U, XC = lifting_surface(P0, P1, c_root, c_tip, 0.105, 0.09, (0, -dih, 1))
    add(Pw, Nw, PID["wing_L"]); a, b = mirror(Pw, Nw); add(a, b, PID["wing_R"])
    # fuel: interior lattice in the wing box
    hf = 0.07
    F = []
    for y in np.arange(1.05, 5.4, hf):
        u = y / ytip; le = P0 + (P1 - P0) * u; c = c_root + (c_tip - c_root) * u; t = 0.105 - 0.015 * u
        for xc in np.arange(0.15, 0.62, hf / c):
            yt = 5 * t * (0.2969 * np.sqrt(xc) - 0.1260 * xc - 0.3516 * xc ** 2 + 0.2843 * xc ** 3 - 0.1036 * xc ** 4) * c
            for z in np.arange(-yt + 0.035, yt - 0.03, hf):
                F.append(le + np.array([-xc * c, 0, z]))
    F = np.array(F) + rng.normal(0, 0.006, (len(F), 3))
    Fn = np.tile([0, 0, 1.0], (len(F), 1))
    add(F, Fn, PID["fuel_L"]); a, b = mirror(F, Fn); add(a, b, PID["fuel_R"])
    # winglets
    cant = np.radians(14.0); hw = 1.12
    up = np.array([-np.tan(np.radians(38.0)), np.sin(cant), np.cos(cant)])
    W0 = P1 + np.array([0.0, 0.0, 0.0]); W1 = W0 + up * hw
    Pg, Ng, _, _ = lifting_surface(W0, W1, c_tip, 0.42, 0.085, 0.08, (np.cos(cant), -np.sin(cant) * 0 + 0, -np.sin(cant)))
    add(Pg, Ng, PID["winglet_L"]); a, b = mirror(Pg, Ng); add(a, b, PID["winglet_R"])
    # nav lights at wing tips
    tipc = P1 + np.array([-0.15, 0.03, 0.02])
    L = tipc + rng.normal(0, 0.035, (60, 3)); Ln = np.tile([0, 1.0, 0], (60, 1))
    add(L, Ln, PID["navlight_L"]); a, b = mirror(L, Ln); add(a, b, PID["navlight_R"])

    # ---------------- engines
    ey, ez, es0, eL = 1.60, 0.42, 11.75, 3.0
    nt = np.array([0, 0.03, 0.10, 0.32, 0.70, 0.93, 1.0]) * eL
    nr = np.array([0.40, 0.47, 0.52, 0.58, 0.52, 0.38, 0.33])
    nfun = PchipInterpolator(nt, nr); ndr = nfun.derivative()
    Pn, Nn, Sn, _ = revolve(nfun, ndr, 0.0, eL, H, X0 - es0, cy=ey, czfun=lambda s: ez)
    add(Pn, Nn, PID["engine_L"]); a, b = mirror(Pn, Nn); add(a, b, PID["engine_R"])
    # fan disc + spinner
    D = []; Dn = []
    for r in np.arange(0.03, 0.40, H):
        n = max(3, int(round(2 * np.pi * r / H))); th = np.arange(n) / n * 2 * np.pi + r * 9.0
        xoff = 0.22 * max(0.0, 1 - r / 0.14)        # spinner cone
        D.append(np.stack([np.full(n, X0 - es0 - 0.22 + xoff), ey + r * np.sin(th), ez + r * np.cos(th)], 1))
        Dn.append(np.tile([1.0, 0, 0], (n, 1)))
    D = np.concatenate(D); Dn = np.concatenate(Dn)
    add(D, Dn, PID["fan_L"]); a, b = mirror(D, Dn); add(a, b, PID["fan_R"])
    # core: dense cylinder (heavy)
    C = []; Cn = []
    for s in np.arange(0.45, eL - 0.1, 0.05):
        for r in (0.10, 0.19, 0.28):
            n = int(round(2 * np.pi * r / 0.05)); th = np.arange(n) / n * 2 * np.pi + s * 3
            C.append(np.stack([np.full(n, X0 - es0 - s), ey + r * np.sin(th), ez + r * np.cos(th)], 1))
            Cn.append(np.stack([np.zeros(n), np.sin(th), np.cos(th)], 1))
    C = np.concatenate(C); Cn = np.concatenate(Cn)
    add(C, Cn, PID["core_L"]); a, b = mirror(C, Cn); add(a, b, PID["core_R"])
    # pylons
    Pp, Np, _, _ = lifting_surface((X0 - 12.25, 0.70, 0.36), (X0 - 12.25, 1.16, 0.42), 2.0, 1.9, 0.09, 0.09, (0, 0, 1))
    add(Pp, Np, PID["pylon_L"]); a, b = mirror(Pp, Np); add(a, b, PID["pylon_R"])

    # ---------------- tail
    Pf, Nf, _, _ = lifting_surface((X0 - 13.55, 0, 0.70), (X0 - 15.25, 0, 2.80), 3.05, 1.65, 0.09, 0.085, (0, 1, 0))
    add(Pf, Nf, PID["fin"])
    Ps, Ns, _, _ = lifting_surface((X0 - 15.85, 0, 2.80), (X0 - 17.05, 2.235, 2.80), 1.42, 0.66, 0.085, 0.08, (0, 0, 1))
    add(Ps, Ns, PID["stab_L"]); a, b = mirror(Ps, Ns); add(a, b, PID["stab_R"])
    a35 = np.radians(35.0)
    d0 = np.array([X0 - 13.75, 0.52, -0.22]); dd = np.array([-np.tan(np.radians(50.0)), np.cos(a35), -np.sin(a35)])
    Pd, Nd, _, _ = lifting_surface(d0, d0 + dd * 1.0, 1.9, 0.45, 0.06, 0.06, (0, np.sin(a35), np.cos(a35)))
    add(Pd, Nd, PID["deltafin_L"]); a, b = mirror(Pd, Nd); add(a, b, PID["deltafin_R"])
    B = np.array([X0 - 15.3, 0, 2.90]) + rng.normal(0, 0.04, (50, 3))
    add(B, np.tile([0, 0, 1.0], (50, 1)), PID["beacon"])

    # ---------------- interior
    hi = 0.05
    FL = []
    for s in np.arange(3.45, 10.8, hi):
        r = float(fus_r(s)); zf = -0.50
        half = np.sqrt(max(r * r - zf * zf, 0)) - 0.03
        ys = np.arange(-half, half, hi) + (0.5 * hi if int(s / hi) % 2 else 0)
        FL.append(np.stack([np.full(len(ys), X0 - s), ys, np.full(len(ys), zf)], 1))
    FL = np.concatenate(FL); add(FL, np.tile([0, 0, 1.0], (len(FL), 1)), PID["floor"])
    BK = []
    for s in (3.42, 10.85):
        r0 = float(fus_r(s)) - 0.035
        for r in np.append(np.arange(hi, r0 - hi * 0.6, hi), r0):
            n = int(round(2 * np.pi * r / hi)); th = np.arange(n) / n * 2 * np.pi
            BK.append(np.stack([np.full(n, X0 - s), r * np.sin(th), float(fus_z(s)) + r * np.cos(th)], 1))
    BK = np.concatenate(BK); add(BK, np.tile([1.0, 0, 0], (len(BK), 1)), PID["bulkhead"])
    # seats: 2 crew + 7 cabin
    ST = []; STn = []
    def seat(sx, y):
        g = 0.045
        for a in np.arange(-0.24, 0.24, g):
            for b in np.arange(-0.22, 0.22, g):
                ST.append([X0 - sx - b, y + a, -0.10]); STn.append([0, 0, 1.0])       # cushion
            for c in np.arange(-0.10, 0.62, g):
                ST.append([X0 - sx - 0.24 - c * 0.18, y + a, c]); STn.append([1.0, 0, 0.2])  # back
        for a in (-0.24, 0.24):
            for b in np.arange(-0.22, 0.22, g):
                for c in np.arange(-0.48, -0.10, g):
                    ST.append([X0 - sx - b, y + a, c]); STn.append([0, np.sign(a), 0])
    for sx, y in [(2.75, 0.36), (2.75, -0.36), (4.9, 0.48), (4.9, -0.48), (6.1, 0.48), (6.1, -0.48),
                  (8.1, 0.48), (8.1, -0.48), (9.4, 0.48)]:
        seat(sx, y)
    add(np.array(ST), np.array(STn), PID["seats"])

    pos = np.concatenate(pos).astype(np.float32); nrm = np.concatenate(nrm).astype(np.float32)
    part = np.concatenate(part)
    pos += rng.normal(0, H * 0.06, pos.shape).astype(np.float32)   # break up moire
    return pos, nrm, part


# linear RGB base colours per part (port = red family, starboard = green family)
COLORS = {
    "nose": (0.90, 0.95, 1.00), "cockpit": (0.30, 0.78, 1.00), "cabin_fwd": (0.10, 0.48, 1.00),
    "cabin_mid": (0.06, 0.24, 1.00), "aft_fuse": (0.20, 0.10, 1.00), "tailcone": (0.48, 0.08, 1.00),
    "windshield": (0.55, 1.00, 0.95), "windows": (0.75, 1.00, 1.00),
    "wing_L": (1.00, 0.05, 0.20), "wing_R": (0.02, 1.00, 0.32),
    "winglet_L": (1.00, 0.45, 0.60), "winglet_R": (0.55, 1.00, 0.70),
    "engine_L": (1.00, 0.42, 0.02), "engine_R": (1.00, 0.42, 0.02),
    "pylon_L": (0.80, 0.40, 0.25), "pylon_R": (0.80, 0.40, 0.25),
    "fin": (1.00, 0.06, 0.70), "stab_L": (0.72, 0.16, 1.00), "stab_R": (0.72, 0.16, 1.00),
    "deltafin_L": (0.95, 0.55, 1.00), "deltafin_R": (0.95, 0.55, 1.00),
    "floor": (0.35, 0.40, 0.55), "seats": (1.00, 0.80, 0.35), "bulkhead": (0.45, 0.55, 0.75),
    "fuel_L": (1.00, 0.62, 0.05), "fuel_R": (1.00, 0.62, 0.05),
    "core_L": (1.00, 0.30, 0.05), "core_R": (1.00, 0.30, 0.05),
    "fan_L": (1.00, 0.85, 0.55), "fan_R": (1.00, 0.85, 0.55),
    "navlight_L": (1.00, 0.02, 0.02), "navlight_R": (0.02, 1.00, 0.10), "beacon": (1.00, 0.05, 0.05),
}
PART_RGB = np.array([COLORS[n] for n in PARTS], np.float32)

if __name__ == "__main__":
    import sys
    pos, nrm, part = build()
    print(len(pos), "points")
    for i, n in enumerate(PARTS):
        print(f"{n:12s} {np.sum(part == i):7d}")
    print("bbox", pos.min(0), pos.max(0))
    np.savez_compressed(sys.argv[1] if len(sys.argv) > 1 else "plane.npz", pos=pos, nrm=nrm, part=part)
