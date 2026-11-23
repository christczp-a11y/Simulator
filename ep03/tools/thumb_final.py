"""EP03 final thumbnail (Chris picked A). No red circle - the impact is pushed into the lower third by the crop,
with a vignette and local contrast/sharpness on the impact.  python thumb_final.py"""
import os, sys, importlib.util
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

spec = importlib.util.spec_from_file_location('tv', r'C:\YouTubeNeuropolis\recon\vulcan\thumbnail.py')
g = {'__file__': spec.origin}; sys.argv = ['x', os.environ.get('TEMP', '.')]
exec(compile(open(spec.origin, encoding='utf-8').read().split('os.makedirs(OUT')[0], 'thumbnail.py', 'exec'), g)
words, text, grade, WHITE, YEL = g['words'], g['text'], g['grade'], g['WHITE'], g['YEL']
RED = (0xD7, 0x26, 0x1E)
OUT = r'C:\YouTubeNeuropolis\Out\ep03-egypt-train'

src = Image.open(r'C:\YouTubeNeuropolis\Out\ep03-egypt-train\work\frames\s14\s14_0020.png').convert('RGB')
S = 1.25                                         # push in so the crumpled coach + loco nose fill the lower-middle
x0, y0 = 216, 0
im = src.crop((x0, y0, x0 + int(1080 / S), y0 + int(1920 / S))).resize((1080, 1920), Image.LANCZOS)
ix, iy = int((740 - x0) * S), int((900 - y0) * S)   # impact point in the new frame (~655, 1125)

# punchier but natural grade
im = ImageEnhance.Color(im).enhance(1.12)
im = ImageEnhance.Contrast(im).enhance(1.10)
# local contrast + sharpness on the impact, feathered
mask = Image.new('L', im.size, 0)
ImageDraw.Draw(mask).ellipse((ix - 330, iy - 360, ix + 330, iy + 360), fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(120))
hot = ImageEnhance.Contrast(im.filter(ImageFilter.UnsharpMask(radius=3, percent=90, threshold=2))).enhance(1.12)
im = Image.composite(hot, im, mask)
# vignette (edges darker) + top darkening for the headline
vig = Image.radial_gradient('L').resize(im.size).point(lambda v: int(v * 0.6))
im.paste((0, 0, 0), (0, 0), vig)
im = grade(im, 0.7)

d = ImageDraw.Draw(im)
words(d, 540, 200, [('HOW TRAIN 134', WHITE)], 112)
words(d, 540, 340, [('HIT', RED), (' A STOPPED', WHITE)], 112)
words(d, 540, 480, [('TRAIN', WHITE)], 112)
text(d, (540, 1640), 'EGYPT TRAIN CRASH', 52, YEL, stroke=6)
im.save(os.path.join(OUT, 'thumb_final.png'))
im.resize((270, 480), Image.LANCZOS).save(os.path.join(os.environ['TEMP'], 'ep03chk', 'thumb_final_25.png'))
print('impact at', ix, iy)
