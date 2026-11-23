"""EP03 thumbnails in the EP01 (Vulcan) style: heavy white caps with black stroke, key word red, hand-drawn red circle,
yellow tagline at the bottom, top darkened.  python thumbnail_ep03.py"""
import os, sys
sys.path.insert(0, r'C:\YouTubeNeuropolis\recon\vulcan')
from PIL import Image, ImageDraw, ImageEnhance
import importlib.util

spec = importlib.util.spec_from_file_location('tv', r'C:\YouTubeNeuropolis\recon\vulcan\thumbnail.py')
src = open(spec.origin, encoding='utf-8').read().split('os.makedirs(OUT')[0]   # reuse helpers only
g = {'__file__': spec.origin}
sys.argv = ['x', os.environ.get('TEMP', '.')]
exec(compile(src, 'thumbnail.py', 'exec'), g)
words, text, circle, grade, WHITE, YEL = g['words'], g['text'], g['circle'], g['grade'], g['WHITE'], g['YEL']
RED = (0xD7, 0x26, 0x1E)
F = r'C:\YouTubeNeuropolis\Out\ep03-egypt-train\work\frames'
OUT = r'C:\YouTubeNeuropolis\Out\ep03-egypt-train'


def headline(im):
    d = ImageDraw.Draw(im)
    words(d, 540, 200, [('HOW TRAIN 134', WHITE)], 112)
    words(d, 540, 340, [('HIT', RED), (' A STOPPED', WHITE)], 112)
    words(d, 540, 480, [('TRAIN', WHITE)], 112)
    return d


# A: the impact from the side - train 134's locomotive folding the last coach of the stopped train 2010
im = Image.open(os.path.join(F, 's14', 's14_0020.png')).convert('RGB')
can = im
can = grade(can, 0.75)
headline(can)
can = Image.blend(can, ImageEnhance.Contrast(ImageEnhance.Color(can).enhance(1.15)).enhance(1.12), 1.0)   # no red circle (Chris 2026-11-23)
vig = Image.radial_gradient('L').resize((1080, 1920)).point(lambda v: int(v * 0.55)); can.paste((0, 0, 0), (0, 0), vig)
headline(can)
text(ImageDraw.Draw(can), (540, 1700), 'EGYPT TRAIN CRASH', 70, YEL, stroke=8)
can.save(os.path.join(OUT, 'thumb_a.png'))

# B: aerial - the stopped train 2010 with its coaches, train 134's red locomotive buried in its last coach
im = Image.open(os.path.join(F, 's16', 's16_0060.png')).convert('RGB')
im = grade(im, 0.7)
headline(im)
pass   # no red circle
text(ImageDraw.Draw(im), (540, 1700), 'EGYPT TRAIN CRASH', 70, YEL, stroke=8)
im.save(os.path.join(OUT, 'thumb_b.png'))
print('done')
