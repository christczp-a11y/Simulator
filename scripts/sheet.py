import sys; sys.path.insert(0, '/mnt/project-files/particle-sim/scripts')
import numpy as np, plane, preview, recon

def sheet(simpath, out, frames, cam_off=(6, -34, 7), fov=30, W=960, H=400, cols=2, track=True, tint_frag=True):
    S = recon.Sim(simpath)
    rgb0 = plane.PART_RGB[S.part]
    if tint_frag:
        rng = np.random.default_rng(5); k = 0.55 + 0.9 * rng.random(S.nf)
        rgb0 = rgb0 * k[S.frag][:, None]
    L = np.array([0.3, -0.6, 0.75]); L /= np.linalg.norm(L)
    tiles = []
    for f in frames:
        p, n = S.frame(f, normals=True)
        sh = 0.2 + 0.8 * np.clip(n @ L, 0, 1)
        c = np.median(S.loc[int(f)], axis=0) if track else np.zeros(3)
        tgt = np.array([c[0], c[1], 1.5])
        img = preview.splat(p, rgb0 * sh[:, None] * 0.5, tgt + np.array(cam_off), tgt, fov=fov, W=W, Hh=H)
        # ground line marks every 5 m
        gx = np.arange(np.floor(c[0] / 5) * 5 - 60, c[0] + 60, 5.0)
        g = np.stack(np.meshgrid(gx, np.arange(-30, 31, 5.0), [0.0]), -1).reshape(-1, 3)
        img = preview.splat(g, np.full((len(g), 3), 0.25), tgt + np.array(cam_off), tgt, fov=fov, W=W, Hh=H, occlude=False, img=img)
        tiles.append(img)
    rows = [np.concatenate(tiles[i:i + cols], 1) for i in range(0, len(tiles), cols)]
    preview.save(np.concatenate(rows, 0), out, 1.6)

if __name__ == "__main__":
    simpath, out = sys.argv[1], sys.argv[2]
    frames = [int(x) for x in sys.argv[3].split(",")]
    sheet(simpath, out, frames)
