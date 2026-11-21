"""make_data.py — per-output-frame data for the Remotion composition (src/data.json) and the halftone textures (public/).
Numbers shown on screen come from the simulation: seat speed and g are the captain's seat (mass-weighted mean of its material points,
1 ms moving average), see seatstats.py. Countdown = time left until the yoke reaches the eye (T+32.01 ms, where the film cuts)."""
import numpy as np, json, sys, os
from PIL import Image
FPS = 30; END = 32.01
T = [t for _, t in json.load(open('/mnt/project-files/particle-sim/out/fp-short/film_times.json'))]; N = len(T)
S = np.load('/tmp/claude-0/-home-claude/e6cfe8fd-2802-5115-938c-f08d9b34dfba/scratchpad/seatstats.npz'); st, sv, sg = S['t'], S['speed'] * 3.6, S['g']
def speed(t): return 342.0 if t < st[0] else min(342.0, float(np.interp(t, st, sv)))
def gpeak(t0, t1):                                     # largest g between two film frames (a real-speed frame spans 33 ms, the peak must not fall between frames)
    if t1 < st[0]: return 1.0
    m = (st > min(t0, t1)) & (st <= max(t0, t1)); a = float(np.interp(t1, st, sg))
    return max(a, float(sg[m].max()) if m.any() else a, 1.0)
rate = np.gradient(np.array(T)) / (1000.0 / FPS)       # real time per film time
F = []
def add(phase, src, t, slow, tprev=None, extra=None):
    d = dict(phase=phase, src=src, t=round(t, 4), slow=slow, left=round(max(END - t, 0) / 1000.0, 5), kmh=round(speed(t), 1), g=round(gpeak(t if tprev is None else tprev, t), 1))
    if extra: d.update(extra)
    F.append(d)
for i in range(N): add('main', i, T[i], float(1.0 / max(rate[i], 1e-9)) if rate[i] < 0.97 else 1.0, T[i - 1] if i else None)
for k in range(30): add("freeze", N - 1, T[-1], 0.0)
RW = 42; LAND = 77
for k in range(RW):
    p = k / (RW - 1.0); e = p * p * (3 - 2 * p); sf = (N - 1) - e * (N - 1 - LAND); add('rewind', int(round(sf)), float(np.interp(sf, np.arange(N), T)), -1.0, extra=dict(srcf=round(sf, 3), p=round(p, 4)))
for k in range(10): add('hold', LAND, T[LAND], 1.0)
tp = T[LAND]
for k in range(14):
    t = -400 + k * 1000.0 / FPS; add('real', 600 + k, t, 1.0, tp); tp = t
for k in range(8): add('black', -1, 99, 0.0)
for k in range(84): add('end', -1, 99, 0.0)
have = sorted(int(f[2:7]) for f in os.listdir(sys.argv[1]) if f.endswith('.png')) if len(sys.argv) > 1 else []
json.dump(dict(fps=FPS, frames=F, have=have, peak_g=round(float(sg.max()), 0)), open('src/data.json', 'w'))
print('frames', len(F), '%.2f s' % (len(F) / FPS), 'have', len(have), 'peak g', sg.max())
for i in (0, 77, 100, 138, 200, 300, 400, 521, 560, 600, 603): print(i, F[i])

def halftone(w, h, fn, col, pitch=13.0, ss=3):
    """dots on a 45-degree grid whose size follows fn(x, y) in 0..1 (1 = solid); returns RGBA"""
    W, H = w * ss, h * ss; y, x = np.mgrid[0:H, 0:W].astype(np.float32); p = pitch * ss
    u = (x + y) / np.sqrt(2); v = (x - y) / np.sqrt(2); du = (u / p - np.round(u / p)) * p; dv = (v / p - np.round(v / p)) * p
    cx = x - (du + dv) / np.sqrt(2); cy = y - (du - dv) / np.sqrt(2)                 # centre of the cell this pixel is in
    a = np.clip(np.nan_to_num(fn(cx / ss, cy / ss)), 0, 1); r = np.sqrt(a) * p * 0.76                # radius so that covered area ~ a, overlapping to solid near 1
    d = np.sqrt(du * du + dv * dv); m = np.clip((r - d) / ss + 0.5, 0, 1) * (a > 0.004)
    m = Image.fromarray((m * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
    im = Image.new('RGBA', (w, h), col + (0,)); im.putalpha(m); return im
halftone(1080, 900, lambda x, y: 0.9 * np.clip(1 - np.hypot((x + 60) / 1250.0, (y + 40) / 760.0), 0, 1) ** 1.25, (8, 8, 8)).save('public/ht_top.png')
halftone(1080, 760, lambda x, y: 0.6 * np.clip((y - 60) / 190.0, 0, 1) ** 1.2, (8, 8, 8)).save('public/ht_bottom.png')
halftone(1080, 1920, lambda x, y: 1.15 - np.hypot(x - 540, y - 960) / 440.0, (242, 240, 235), pitch=22.0, ss=2).save('public/ht_burst.png')
halftone(1080, 1920, lambda x, y: 0.5 + 0.0 * x, (255, 255, 255), pitch=7.0, ss=3).save('public/ht_screen.png')
halftone(1080, 1920, lambda x, y: 0.96 * np.clip((np.abs((x - 540) * 0.8 + (y - 960) * 0.6) / 900.0 - 0.52) / 0.4, 0, 1), (242, 240, 235), pitch=18.0, ss=2).save('public/ht_end.png')
print('textures ok')
