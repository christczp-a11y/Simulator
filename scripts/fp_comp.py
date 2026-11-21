"""fp_comp.py — puts the rendered frames of the first-person Short together: clock read-out, playback rate, end card, optional sound.

  python3 fp_comp.py frames_dir tag film_times.json out.mp4 [--audio a.wav] [--size 1080x1920] [--tail 1.8] [--probe 120,300]

frames_dir holds {tag}_{frame:05d}.png as written by fp_render.py --tfile. Frames not rendered yet are filled in by blending the
nearest rendered frames before and after (so a pass that rendered every second frame already plays at 30 fps); the log says how many.
--probe writes those composited frames as jpg next to the mp4 instead of encoding, for a look at the overlay.
Needs PIL, numpy, ffmpeg. Fonts: JetBrains Mono for the clock, WenQuanYi Zen Hei for Chinese (paths below; change them on another machine).
"""
import numpy as np, json, os, sys, subprocess, argparse
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser(); ap.add_argument("frames"); ap.add_argument("tag"); ap.add_argument("times"); ap.add_argument("out")
ap.add_argument("--audio", default=""); ap.add_argument("--size", default="1080x1920"); ap.add_argument("--tail", type=float, default=1.8); ap.add_argument("--probe", default=""); ap.add_argument("--overlay_only", type=int, default=0)
ap.add_argument("--mono", default="/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf"); ap.add_argument("--cjk", default="/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
A = ap.parse_args(); W, H = map(int, A.size.split("x")); FPS = 30
T = json.load(open(A.times)); N = len(T); tms = np.array([t for _, t in T])
path = lambda i: os.path.join(A.frames, f"{A.tag}_{i:05d}.png")
have = np.array([os.path.exists(path(i)) for i in range(N)]); idx = np.flatnonzero(have)
if len(idx) == 0 and not A.overlay_only: sys.exit("no frames")
print("frames", N, "rendered", int(have.sum()), "filled in by blending", int((~have).sum()), flush=True)
rate = np.gradient(tms * 1e-3) * FPS                                # real seconds per film second
s = W / 1080.0; F1 = ImageFont.truetype(A.mono, int(70 * s)); F2 = ImageFont.truetype(A.cjk, int(38 * s)); F3 = ImageFont.truetype(A.mono, int(150 * s)); F4 = ImageFont.truetype(A.cjk, int(46 * s))
AMBER = (255, 178, 36); RED = (255, 90, 71); INK = (235, 231, 223); MUTE = (150, 155, 165)

cache = {}
def load(i):
    if i not in cache:
        if len(cache) > 6: cache.pop(next(iter(cache)))
        im = Image.open(path(i)).convert("RGB")
        if im.size != (W, H): im = im.resize((W, H), Image.LANCZOS)
        cache[i] = np.asarray(im, np.float32)
    return cache[i]

def picture(i):
    if have[i]: return load(i)
    k = np.searchsorted(idx, i); a = idx[max(k - 1, 0)]; b = idx[min(k, len(idx) - 1)]
    if a == b or b < i or a > i: return load(a if abs(a - i) <= abs(b - i) else b)
    w = (i - a) / float(b - a); return load(a) * (1 - w) + load(b) * w

def clock(t):
    if t < -1000: return "T-%.1f s" % (-t / 1000.0), AMBER
    if t < 0: return "T-%d ms" % round(-t), AMBER
    return "T+%.1f ms" % t, RED

def speed(r):
    if r > 0.97: return "真实速度"
    x = 1.0 / r; return "慢放 %d 倍" % (round(x / 10) * 10 if x >= 100 else round(x))

def overlay(arr, i):
    im = None if arr is None else Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)); ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    txt, col = clock(tms[i]); sp = speed(rate[i]); x0 = int(64 * s); y0 = int(250 * s)            # below the app's top bar, clear of the buttons on the right
    w1 = d.textlength("T+00.0 ms", font=F1); w2 = d.textlength(sp, font=F2); bw = int(max(w1, w2) + 56 * s); bh = int(178 * s)
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=int(14 * s), fill=(8, 10, 14, 150))
    d.rectangle([x0, y0 + int(14 * s), x0 + int(6 * s), y0 + bh - int(14 * s)], fill=col + (255,))
    d.text((x0 + int(28 * s), y0 + int(18 * s)), txt, font=F1, fill=col + (255,)); d.text((x0 + int(30 * s), y0 + int(112 * s)), sp, font=F2, fill=INK + (235,))
    return ov if im is None else Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")

def endcard(k):
    im = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(im); a = float(np.clip((k - 10) / 8.0, 0, 1))         # black for a third of a second, then the line comes up
    if a > 0:
        c = lambda col: tuple(int(v * a) for v in col)
        for txt, f, col, y in (("从机头触地到这里", F4, MUTE, 0.40), ("0.032", F3, RED, 0.445), ("秒", F4, INK, 0.545)):
            w = d.textlength(txt, font=f); d.text(((W - w) / 2, int(H * y)), txt, font=f, fill=c(col))
    return im

if A.overlay_only:
    # only the read-out and the end card, as a video with transparency: for putting the film together where the frames are (ffmpeg alone, no PIL needed there):
    #   ffmpeg -framerate 30 -i frames\\s_%05d.png -i overlay.mov -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=1.8[b];[b][1:v]overlay=eof_action=pass" -c:v libx264 -crf 16 -pix_fmt yuv420p out.mp4
    nt = int(round(A.tail * FPS)); p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "png", "-pix_fmt", "rgba", A.out], stdin=subprocess.PIPE)
    for i in range(N): p.stdin.write(overlay(None, i).tobytes())
    for k in range(nt): p.stdin.write(endcard(k).convert("RGBA").tobytes())
    p.stdin.close(); p.wait(); print("wrote", A.out, N + nt, "frames", os.path.getsize(A.out) // 1024, "KB"); sys.exit(0)
if A.probe:
    for i in [int(x) for x in A.probe.split(",")]:
        (endcard(i - N) if i >= N else overlay(picture(i), i)).save(os.path.splitext(A.out)[0] + f"_probe{i:05d}.jpg", quality=90)
    sys.exit(0)
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
if A.audio: cmd += ["-i", A.audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", A.out]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE); nt = int(round(A.tail * FPS))
for i in range(N):
    p.stdin.write(overlay(picture(i), i).tobytes())
    if i % 60 == 0: print("frame", i, flush=True)
for k in range(nt): p.stdin.write(endcard(k).tobytes())
p.stdin.close(); p.wait(); print("wrote", A.out, "%.1f s" % ((N + nt) / FPS), flush=True)
