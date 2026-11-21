"""fp_world.py — the countryside the aircraft comes down into (run once, in the cloud: needs scipy).
Fields are Voronoi cells; hedgerows with trees follow the field boundaries; a paved road, farm tracks, two farmsteads, woods.
World axes as in the simulation: the aircraft flies toward +x, first contact at the origin, ground z = 0.

  python3 fp_world.py out_dir
Writes ground.png (field colours, sRGB), ground2.png (R row direction / pi, G hedge, B road = 1 / impact field = 0.5; data), world.npz (trees, hedges, buildings, extent).
"""
import numpy as np, sys, os
from scipy.spatial import Voronoi, cKDTree
from PIL import Image

L = 5200.0; X0W, Y0W = -1100.0, -2600.0; NPX = 4096          # texture covers [X0W, X0W+L] x [Y0W, Y0W+L]
rng = np.random.default_rng(11)


def main(out):
    os.makedirs(out, exist_ok=True)
    # ---- field sites: jittered anisotropic grid, rotated; one big field around the impact point
    ang = np.radians(24.0); c, s = np.cos(ang), np.sin(ang); R = np.array([[c, -s], [s, c]])
    gx, gy = np.meshgrid(np.arange(-14, 15), np.arange(-22, 23), indexing="ij")
    P = np.stack([gx.ravel() * 330.0, gy.ravel() * 190.0], 1) + rng.uniform(-90, 90, (gx.size, 2))
    P = P @ R.T + np.array([1500.0, 0.0])
    P = P[np.linalg.norm(P - np.array([60.0, 0.0]), axis=1) > 260.0]; P = np.vstack([[60.0, 0.0], P])
    n = len(P)
    kind = rng.choice(5, n, p=[0.30, 0.20, 0.22, 0.16, 0.12])           # 0 pasture 1 green crop 2 stubble 3 plough 4 woodland
    kind[0] = 2
    far = np.linalg.norm(P - P[0], axis=1); kind[(kind == 4) & (far < 420)] = 0
    pal = np.array([[0.105, 0.160, 0.045], [0.050, 0.115, 0.030], [0.330, 0.270, 0.120], [0.150, 0.105, 0.065], [0.030, 0.060, 0.020]])
    col = pal[kind] * rng.uniform(0.78, 1.25, (n, 1)) * rng.uniform(0.93, 1.07, (n, 3)); col[0] = [0.150, 0.125, 0.055]      # the field of the impact: darker, it has to match the self-shadowed grass geometry laid over it
    rowang = (ang + rng.choice([0.0, np.pi / 2], n) + rng.normal(0, 0.05, n)) % np.pi
    # ---- rasterise: nearest and second nearest site per pixel
    u = (np.arange(NPX) + 0.5) / NPX * L
    XX, YY = np.meshgrid(X0W + u, Y0W + u, indexing="xy")            # image row = y, column = x
    tree = cKDTree(P); d, idx = tree.query(np.stack([XX.ravel(), YY.ravel()], 1), k=2)
    i1 = idx[:, 0].reshape(NPX, NPX); i2 = idx[:, 1].reshape(NPX, NPX)
    p1 = P[i1]; p2 = P[i2]; q = np.stack([XX, YY], -1)
    edge = np.abs(((q - (p1 + p2) / 2) * (p2 - p1)).sum(-1) / np.linalg.norm(p2 - p1, axis=-1))     # distance to the cell boundary
    # which boundaries carry a hedge, which a farm track
    key = np.minimum(i1, i2).astype(np.int64) * 100003 + np.maximum(i1, i2)
    hsh = (key * 2654435761 % 1000) / 1000.0
    hedge = (edge < 2.2) & (hsh < 0.62); track = (edge < 1.6) & (hsh >= 0.62) & (hsh < 0.80)
    # paved road: a gentle S across the area
    xr = np.linspace(X0W, X0W + L, 400); yr = 520.0 - 0.33 * (xr - 300) + 140 * np.sin(xr / 700.0)
    rt = cKDTree(np.stack([xr, yr], 1)); dr, _ = rt.query(np.stack([XX.ravel(), YY.ravel()], 1)); dr = dr.reshape(NPX, NPX)
    road = dr < 4.0; verge = (dr >= 4.0) & (dr < 7.5)
    img = col[i1]
    img[track] = [0.22, 0.19, 0.14]; img[hedge] = [0.030, 0.060, 0.020]; img[verge] = [0.13, 0.17, 0.06]; img[road] = [0.085, 0.085, 0.09]
    line = road & (dr < 0.6) & ((XX // 9.0) % 2 == 0); img[line] = [0.55, 0.55, 0.5]
    srgb = np.where(img <= 0.0031308, img * 12.92, 1.055 * np.clip(img, 0, 1) ** (1 / 2.4) - 0.055)
    Image.fromarray((np.clip(srgb, 0, 1)[::-1] * 255).astype(np.uint8)).save(os.path.join(out, "ground.png"))
    d2 = np.stack([rowang[i1] / np.pi, hedge.astype(float), np.where(road | track, 1.0, np.where(i1 == 0, 0.5, 0.0))], -1)       # B: 1 = road or track, 0.5 = the field of the impact
    d2[..., 0][(kind[i1] == 0) | (kind[i1] == 4)] = -1.0 / 255      # pasture and woodland have no rows -> 0
    Image.fromarray((np.clip(d2, 0, 1)[::-1] * 255).astype(np.uint8)).save(os.path.join(out, "ground2.png"))
    # ---- trees: along hedged boundaries (from the Voronoi ridges), in woodland cells, around the farms
    vor = Voronoi(P); T = []; H = []
    def clear(p):                                                       # keep the flight path and the impact area open
        return (np.abs(p[:, 1]) < 30) & (p[:, 0] > -160) & (p[:, 0] < 110)
    for (a, b), (va, vb) in zip(vor.ridge_points, vor.ridge_vertices):
        if va < 0 or vb < 0: continue
        k = (int(min(a, b)) * 100003 + int(max(a, b))) * 2654435761 % 1000 / 1000.0
        if k >= 0.62: continue
        A = vor.vertices[va]; B = vor.vertices[vb]; ln = np.linalg.norm(B - A)
        if ln < 12 or ln > 2500 or max(np.abs(A - [1500, 0]).max(), np.abs(B - [1500, 0]).max()) > 2700: continue
        H.append([*A, *B, rng.uniform(1.3, 2.4)])
        dens = rng.choice([0.0, 0.035, 0.07, 0.12], p=[0.15, 0.3, 0.35, 0.2])      # trees per metre of hedge
        m = rng.poisson(ln * dens)
        if m:
            f = rng.uniform(0, 1, m)[:, None]; p = A + (B - A) * f + rng.normal(0, 1.2, (m, 2))
            p = p[~clear(p)]
            T += [[x, y, rng.uniform(7, 17), rng.uniform(0.28, 0.42), rng.uniform()] for x, y in p]
    for i in np.flatnonzero(kind == 4):
        if abs(P[i, 0] - 1500) > 2400 or abs(P[i, 1]) > 2400: continue
        m = 900; p = P[i] + rng.uniform(-260, 260, (m, 2)); _, j = tree.query(p); p = p[j == i]
        T += [[x, y, rng.uniform(12, 22), rng.uniform(0.25, 0.36), rng.uniform()] for x, y in p]
    B = []                                                              # buildings: x, y, yaw, length, width, wall height, roof rise, kind
    for (fx, fy, yaw) in ((410.0, 215.0, 0.5), (980.0, -330.0, -0.3), (1750.0, 420.0, 1.1), (250.0, -420.0, 0.2)):
        cy, sy = np.cos(yaw), np.sin(yaw); Rf = np.array([[cy, -sy], [sy, cy]])
        for (ox, oy, ln, wd, hw, hr, kd) in ((0, 0, 14, 9, 5.5, 3.0, 0), (26, 8, 30, 14, 6.5, 4.0, 1), (22, -22, 22, 11, 5.0, 3.2, 2), (-18, 14, 9, 7, 3.2, 2.0, 0)):
            o = Rf @ np.array([ox, oy]); B.append([fx + o[0], fy + o[1], yaw + (np.pi / 2 if kd == 2 else 0), ln, wd, hw, hr, kd])
        for _ in range(14):
            o = rng.normal(0, 28, 2); T.append([fx + o[0], fy + o[1], rng.uniform(8, 16), rng.uniform(0.3, 0.42), rng.uniform()])
    T = np.array(T, np.float32); B = np.array(B, np.float32); H = np.array(H, np.float32)
    # drop trees standing on buildings or on the road
    dr2, _ = rt.query(T[:, :2]); ok = dr2 > 9.0
    for b in B: ok &= np.linalg.norm(T[:, :2] - b[:2], axis=1) > max(b[3], b[4]) * 0.75
    T = T[ok]
    np.savez_compressed(os.path.join(out, "world.npz"), trees=T, hedges=H, buildings=B, extent=np.array([X0W, Y0W, L], np.float32))
    print("sites", n, "trees", len(T), "hedges", len(H), "buildings", len(B))


if __name__ == "__main__":
    main(sys.argv[1])
