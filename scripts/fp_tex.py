"""Instrument panel image for the first-person shot (drawn, not a photo). Layout after the Learjet 60's Pro Line 4 panel:
two large displays in front of each pilot (PFD outboard, MFD inboard), engine displays and standby instruments in the middle.
The flight display shows the attitude of the shot: 24 deg nose down, 14 deg right bank, ground proximity warning.
  python3 fp_tex.py panel.png"""
import sys, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W, H = 2680, 1000                    # 1.34 m x 0.50 m at 2 px per mm
PX = 2000.0                          # px per metre


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()


def pfd(sz, pitch=-24.0, roll=14.0, spd=185, alt=40):
    im = Image.new("RGB", (sz, sz), (4, 6, 8)); d = ImageDraw.Draw(im)
    # attitude: draw a big sky/ground card, shift by pitch, rotate by roll
    a = int(sz * 0.62); k = a / 50.0                     # px per degree
    card = Image.new("RGB", (a * 3, a * 3), (110, 62, 22)); c = ImageDraw.Draw(card)
    hy = a * 1.5 + pitch * k
    c.rectangle([0, 0, a * 3, hy], fill=(30, 110, 235)); c.line([0, hy, a * 3, hy], fill=(255, 255, 255), width=4)
    f = font(int(sz * 0.035))
    for p in range(-60, 61, 10):
        if p == 0: continue
        y = hy - p * k; w = a * 0.16
        c.line([a * 1.5 - w, y, a * 1.5 + w, y], fill=(255, 255, 255), width=3)
        c.text((a * 1.5 + w + 6, y - sz * 0.02), str(abs(p)), fill=(255, 255, 255), font=f)
    for p in (-30, -40, -50):                              # red chevrons: recover upwards
        y = hy - p * k
        c.line([a * 1.5 - a * .22, y + a * .07, a * 1.5, y - a * .05, a * 1.5 + a * .22, y + a * .07], fill=(255, 30, 20), width=9)
    card = card.rotate(roll, resample=Image.BICUBIC, center=(a * 1.5, a * 1.5))
    x0, y0 = int(sz * 0.19), int(sz * 0.07)
    im.paste(card.crop((a, a, a * 2, a * 2)), (x0, y0))
    cx, cy = x0 + a / 2, y0 + a / 2
    d.line([cx - a * .22, cy, cx - a * .07, cy, cx - a * .07, cy + a * .04], fill=(255, 220, 0), width=7)
    d.line([cx + a * .22, cy, cx + a * .07, cy, cx + a * .07, cy + a * .04], fill=(255, 220, 0), width=7)
    d.rectangle([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 220, 0))
    fb = font(int(sz * 0.085)); t = "PULL UP"; tw = d.textlength(t, font=fb)
    d.rectangle([cx - tw / 2 - 10, y0 + a * .70, cx + tw / 2 + 10, y0 + a * .70 + sz * .10], fill=(215, 0, 0))
    d.text((cx - tw / 2, y0 + a * .70), t, fill=(255, 255, 255), font=fb)
    # speed and altitude tapes
    f2 = font(int(sz * 0.05)); f3 = font(int(sz * 0.038))
    for (xa, val, step, n) in ((int(sz * .02), spd, 10, 4), (x0 + a + int(sz * .02), alt, 100, 4)):
        d.rectangle([xa, y0, xa + sz * .15, y0 + a], fill=(38, 40, 44))
        for i in range(-n, n + 1):
            v = (val // step) * step + i * step; y = cy - (v - val) / step * a / (2 * n)
            if y0 < y < y0 + a and v >= 0:
                d.line([xa + sz * .12, y, xa + sz * .15, y], fill=(230, 230, 230), width=2); d.text((xa + 4, y - sz * .022), str(int(v)), fill=(210, 210, 210), font=f3)
        d.rectangle([xa - 2, cy - sz * .04, xa + sz * .15, cy + sz * .04], fill=(0, 0, 0), outline=(255, 255, 255), width=3)
        d.text((xa + 6, cy - sz * .032), str(int(val)), fill=(255, 60, 40) if step == 100 else (255, 255, 255), font=f2)
    # compass arc
    ry = y0 + a + sz * .33; r = sz * .30
    d.arc([cx - r, ry - r, cx + r, ry + r], 200, 340, fill=(230, 230, 230), width=4)
    for i in range(-6, 7):
        an = math.radians(-90 + i * 10); l = r * (.90 if i % 3 else .84)
        d.line([cx + r * math.cos(an), ry + r * math.sin(an), cx + l * math.cos(an), ry + l * math.sin(an)], fill=(230, 230, 230), width=3)
    d.polygon([cx, ry - r - 4, cx - 12, ry - r - 26, cx + 12, ry - r - 26], fill=(255, 255, 255))
    d.text((cx - sz * .06, y0 + a + sz * .10), "094", fill=(0, 255, 120), font=f2)
    return im


def mfd(sz):
    """terrain display: everything ahead is above the aircraft, so the whole sector is red"""
    im = Image.new("RGB", (sz, sz), (4, 6, 8)); d = ImageDraw.Draw(im); cx, cy = sz / 2, sz * .82
    import random; rnd = random.Random(4)
    for rr, col in ((sz * .70, (150, 0, 0)), (sz * .52, (200, 10, 0)), (sz * .30, (235, 20, 0))):
        d.pieslice([cx - rr, cy - rr, cx + rr, cy + rr], 205, 335, fill=col)
    for _ in range(260):
        an = math.radians(rnd.uniform(207, 333)); rr = rnd.uniform(sz * .06, sz * .68); q = rnd.uniform(6, 22)
        x, y = cx + rr * math.cos(an), cy + rr * math.sin(an); d.ellipse([x - q, y - q, x + q, y + q], fill=rnd.choice([(250, 40, 0), (170, 0, 0), (225, 200, 0)]))
    for rr in (sz * .35, sz * .70): d.arc([cx - rr, cy - rr, cx + rr, cy + rr], 205, 335, fill=(235, 235, 235), width=3)
    d.line([cx, cy, cx, cy - sz * .70], fill=(255, 0, 255), width=4)
    d.polygon([cx, cy - 18, cx - 16, cy + 14, cx + 16, cy + 14], outline=(255, 255, 255), width=4)
    f = font(int(sz * .055)); d.text((sz * .05, sz * .04), "TERRAIN", fill=(255, 40, 30), font=f); d.text((sz * .70, sz * .04), "2.5 NM", fill=(0, 230, 255), font=f)
    return im


def eis(w, h):
    im = Image.new("RGB", (w, h), (4, 6, 8)); d = ImageDraw.Draw(im); f = font(int(h * .11))
    for i, (nm, val, frac) in enumerate((("N1", "38.4", .38), ("N1", "38.1", .38), ("ITT", "512", .55), ("ITT", "509", .55))):
        cx = w * (.16 + .225 * i); cy = h * .36; r = h * .21
        d.arc([cx - r, cy - r, cx + r, cy + r], 150, 390, fill=(210, 210, 210), width=4)
        an = math.radians(150 + 240 * frac); d.line([cx, cy, cx + r * .9 * math.cos(an), cy + r * .9 * math.sin(an)], fill=(255, 255, 255), width=5)
        d.text((cx - r * .7, cy + r * .5), val, fill=(0, 255, 120), font=f)
    f2 = font(int(h * .085))
    for i, t in enumerate(("OIL PRESS 62 61", "OIL TEMP  88 87", "FUEL 3120 LB")):
        d.text((w * .06, h * (.68 + .10 * i)), t, fill=(0, 230, 255), font=f2)
    return im


def bezel(d, box, r=14):
    x0, y0, x1, y1 = box; d.rounded_rectangle([x0 - r, y0 - r, x1 + r, y1 + r], radius=r, fill=(13, 13, 14), outline=(34, 34, 36), width=3)


def build():
    im = Image.new("RGB", (W, H), (20, 21, 23)); d = ImageDraw.Draw(im)
    m = lambda metres: int(round(metres * PX))
    ds = m(0.168); yc = m(0.50 - 0.315)                    # display centres 31.5 cm above the panel bottom edge
    xs = {"pfdL": 0.67 - 0.475, "mfdL": 0.67 - 0.283, "mfdR": 0.67 + 0.283, "pfdR": 0.67 + 0.475}
    P = pfd(ds); M = mfd(ds)
    for k, xm in xs.items():
        x = m(xm) - ds // 2; y = yc - ds // 2; bezel(d, (x, y, x + ds, y + ds)); im.paste(P if "pfd" in k else M, (x, y))
        for i in range(6):                                # bezel keys
            d.rectangle([x + ds * (.06 + .155 * i), y + ds + 20, x + ds * (.06 + .155 * i) + 22, y + ds + 32], fill=(60, 60, 62))
    ew, eh = m(0.150), m(0.118); ex = m(0.67) - ew // 2; ey = yc - ds // 2
    bezel(d, (ex, ey, ex + ew, ey + eh)); im.paste(eis(ew, eh), (ex, ey))
    # standby attitude, altimeter, airspeed (round) under the engine display
    for i, col in enumerate(((30, 110, 235), (10, 10, 10), (10, 10, 10))):
        cx = m(0.67) + (i - 1) * m(0.058); cy = ey + eh + m(0.052); r = m(0.024)
        d.ellipse([cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8], fill=(10, 10, 11), outline=(40, 40, 42), width=3)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        if i == 0: d.chord([cx - r, cy - r, cx + r, cy + r], 200, 340 + 180 - 160, fill=(30, 110, 235)); d.pieslice([cx - r, cy - r, cx + r, cy + r], 14, 194, fill=(110, 62, 22))
        else:
            for a in range(0, 360, 30): d.line([cx + r * .78 * math.cos(math.radians(a)), cy + r * .78 * math.sin(math.radians(a)), cx + r * .96 * math.cos(math.radians(a)), cy + r * .96 * math.sin(math.radians(a))], fill=(230, 230, 230), width=3)
            d.line([cx, cy, cx + r * .8 * math.cos(1.1 + i), cy + r * .8 * math.sin(1.1 + i)], fill=(255, 255, 255), width=4)
    # warning lights on the top row: master warning lit both sides, annunciator block in the middle
    f = font(26)
    for xm in (0.67 - 0.36, 0.67 + 0.36):
        x = m(xm); d.rounded_rectangle([x - 46, 26, x + 46, 78], radius=6, fill=(255, 25, 15)); d.text((x - 40, 36), "MSTR", fill=(255, 235, 230), font=f)
        d.rounded_rectangle([x + 60, 26, x + 152, 78], radius=6, fill=(255, 170, 0)); d.text((x + 66, 36), "CAUT", fill=(40, 20, 0), font=f)
    fa = font(17)
    for i in range(3):
        for j in range(8):
            x = m(0.67) - 232 + j * 58; y = 20 + i * 30; lit = (i * 8 + j) in (1, 6, 10, 13, 19)
            d.rectangle([x, y, x + 52, y + 25], fill=(255, 40, 20) if lit and i < 2 else (255, 170, 0) if lit else (26, 26, 28), outline=(50, 50, 52))
    # lower panel: rows of lit switch legends and knobs
    import random; rnd = random.Random(2)
    for row in range(3):
        y = m(0.50 - 0.165) + row * 62 + 40
        for j in range(40):
            x = 150 + j * 60 + rnd.randint(-6, 6)
            if abs(x - W / 2) < 150: continue
            if rnd.random() < .75: d.rectangle([x, y, x + 34, y + 9], fill=(150, 170, 150))
            if rnd.random() < .5: d.ellipse([x + 6, y + 18, x + 30, y + 42], fill=(42, 42, 44), outline=(70, 70, 72), width=2)
            if rnd.random() < .12: d.rectangle([x, y + 16, x + 34, y + 40], fill=(0, 200, 90))
    glow = im.filter(ImageFilter.GaussianBlur(6))
    return Image.blend(im, glow, 0.25)


if __name__ == "__main__":
    build().save(sys.argv[1]); print("saved", sys.argv[1])
