"""Tiny numpy point rasteriser for fast look checks (not the final renderer)."""
import numpy as np
from PIL import Image


def look_at(eye, target, up=(0, 0, 1)):
    eye = np.asarray(eye, float); f = np.asarray(target, float) - eye; f /= np.linalg.norm(f)
    r = np.cross(f, up); r /= np.linalg.norm(r); u = np.cross(r, f)
    return eye, np.stack([r, u, f])


def splat(pos, rgb, eye, target, fov=35.0, W=1280, Hh=720, size=None, occlude=True, zeps=0.12, img=None, gain=1.0):
    eye, R = look_at(eye, target)
    c = (pos - eye) @ R.T
    z = c[:, 2]; ok = z > 0.1
    f = 0.5 * W / np.tan(np.radians(fov) / 2)
    px = (W / 2 + f * c[:, 0] / np.maximum(z, 1e-3)); py = (Hh / 2 - f * c[:, 1] / np.maximum(z, 1e-3))
    ok &= (px >= 1) & (px < W - 2) & (py >= 1) & (py < Hh - 2)
    ix = px[ok].astype(np.int64); iy = py[ok].astype(np.int64); zz = z[ok]; col = rgb[ok] * gain
    if img is None:
        img = np.zeros((Hh, W, 3), np.float32)
    if occlude:
        zb = np.full((Hh, W), 1e9, np.float32)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                np.minimum.at(zb, (iy + dy, ix + dx), zz)
        keep = zz <= zb[iy, ix] + zeps
        ix, iy, col = ix[keep], iy[keep], col[keep]
    for dx, dy, w in ((0, 0, 1.0), (1, 0, 0.5), (0, 1, 0.5), (-1, 0, 0.5), (0, -1, 0.5)):
        np.add.at(img, (iy + dy, ix + dx), col * w)
    return img


def save(img, path, exposure=1.0):
    x = 1 - np.exp(-img * exposure)
    Image.fromarray((np.clip(x, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)).save(path)
