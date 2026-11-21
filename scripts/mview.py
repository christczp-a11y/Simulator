"""Quick look at an mpm.py run without Blender or matplotlib (numpy only): side / top / three-quarter views of chosen frames.
  python mview.py <data_dir> <mpm_dir> 20,60,120 out.png"""
import sys, os, zlib, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import palette


def png(path, a):
    h, w, _ = a.shape; raw = b"".join(b"\x00" + a[y].tobytes() for y in range(h))
    def ch(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))


def splat(img, u, v, depth, col, x0, y0, sc):
    H, W, _ = img.shape
    px = ((u - x0) * sc).astype(int); py = (H - 1 - (v - y0) * sc).astype(int)
    ok = (px >= 0) & (px < W - 1) & (py >= 0) & (py < H - 1); o = np.argsort(-depth[ok])      # far first, near overwrites
    px, py, c = px[ok][o], py[ok][o], col[ok][o]
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)): img[py + dy, px + dx] = c


def main(data, mdir, frames, out, span=34.0):
    S = np.load(os.path.join(data, "sim.npz")); P = np.load(os.path.join(data, "pre.npz"))
    X = np.load(os.path.join(mdir, "x.npy"), mmap_mode="r"); EP = np.load(os.path.join(mdir, "ep.npy"), mmap_mode="r"); tf = np.load(os.path.join(mdir, "fail.npy"))
    rest = (S["cen0"][S["frag"]] + S["local"] - P["model_t"]) @ P["model_R"]
    pid = {str(n): i for i, n in enumerate(P["part_names"])}
    rgb = palette.colors(rest, S["part"], pid, "design", P["part_rgb"])[0]
    rgb = np.clip(rgb, 0, 1) ** 0.45
    W, Hs, Ht = 640, 200, 360; sc = W / span
    rows = []
    for f in frames:
        f = min(f, len(X) - 1); x = np.asarray(X[f]); e = np.asarray(EP[f]) * 0.01
        c = rgb.copy(); st = np.clip(e / 0.3, 0, 1)[:, None]; c = c * (1 - 0.5 * st) + 0.5 * st
        dead = tf <= f; c[dead] = c[dead] * 0.55 + np.array([1.0, 0.75, 0.4]) * 0.45
        c8 = (np.clip(c, 0, 1) * 255).astype(np.uint8); cx = np.median(x[:, 0])
        a = np.full((Hs, W, 3), 10, np.uint8); splat(a, x[:, 0], x[:, 2], -x[:, 1], c8, cx - span / 2, -1.0, sc)
        b = np.full((Ht, W, 3), 10, np.uint8); splat(b, x[:, 0], x[:, 1], -x[:, 2], c8, cx - span / 2, -Ht / sc / 2, sc)
        an, bn = np.radians(38), np.radians(20)
        u = (x[:, 0] - cx) * np.cos(an) + x[:, 1] * np.sin(an); dep = -(x[:, 0] - cx) * np.sin(an) + x[:, 1] * np.cos(an)
        w = x[:, 2] * np.cos(bn) + dep * np.sin(bn)
        q = np.full((Ht, W, 3), 10, np.uint8); splat(q, u, w, dep, c8, -span / 2, -7.0, sc)
        col = np.concatenate([a, np.full((4, W, 3), 60, np.uint8), b], 0); col2 = np.concatenate([np.full((Hs + 4 - 0, W, 3), 10, np.uint8), q], 0)
        col2[:Hs] = 10
        row = np.concatenate([col, np.full((col.shape[0], 4, 3), 60, np.uint8), col2], 1)
        # frame tick marks: one white pixel block per 10 frames in the top-left corner
        row[4:12, 4:4 + max(1, f // 2)] = 255
        rows.append(row); rows.append(np.full((6, row.shape[1], 3), 90, np.uint8))
        print(f"frame {f}: failed {dead.mean()*100:.1f}%  ep>0.05 {np.mean(e>0.05)*100:.1f}%  x-median {cx:.1f}  speed-ish", flush=True)
    png(out, np.concatenate(rows, 0))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], [int(v) for v in sys.argv[3].split(",")], sys.argv[4])
