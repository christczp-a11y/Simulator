import sys
from PIL import Image
fs=[int(x) for x in sys.argv[2].split(',')]; ims=[Image.open(f'out/st_{f:04d}.jpg').resize((432,768),Image.LANCZOS) for f in fs]
S=Image.new('RGB',(432*len(ims),768))
for i,im in enumerate(ims): S.paste(im,(i*432,0))
S.save(sys.argv[1],quality=88)
