import numpy as np

def smooth(x, k):
    ker = np.hanning(2 * k + 1); ker /= ker.sum()
    return np.stack([np.convolve(np.pad(x[:, i], k, mode="edge"), ker, mode="valid") for i in range(x.shape[1])], 1)

def camera_path(focus, fps=30.0, trail=9.0):
    """focus: (N,3) tracked point per output frame -> eye, target, fov(deg), focus distance"""
    n = len(focus); tau = np.arange(n) / fps
    tgt = smooth(focus, 20).copy()
    w = np.interp(tau, [0, 2.2, 3, 6, 15], [1.0, 1.0, 0.75, 0.45, 0.35])      # keep the aircraft centred on the approach, however steep
    tgt[:, 2] = np.maximum(tgt[:, 2] * w, np.interp(tau, [0, 3, 6, 15], [0.0, 0.8, 1.2, 1.8]))
    kt = [0, 2.6, 5.0, 8.0, 11.0, 15.0]
    off = np.stack([np.interp(tau, kt, v) for v in ([26, 17, 7, -1, -6, -10], [-24, -27, -30, -33, -35, -36], [-1.5, 0.6, 1.6, 2.6, 3.0, 3.2])], 1)
    eye = smooth(tgt + off, 15); eye[:, 2] = np.maximum(eye[:, 2], 0.7)
    # trail slightly behind the action late in the shot so the debris field stays in frame
    tgt[:, 0] -= np.interp(tau, [0, 6, 15], [0, 0, trail])
    fov = np.interp(tau, [0, 2.2, 3.5, 5, 8, 11, 15], [42, 40, 37, 33, 33, 33, 30])
    dist = np.linalg.norm(tgt - eye, axis=1)
    return eye, tgt, fov, dist
