# Build labeled contact sheets from frontend screenshots.
import sys, os, glob
from PIL import Image, ImageDraw, ImageFont
src, out, pattern, cols, scale = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), float(sys.argv[5])
files = sorted(glob.glob(os.path.join(src, pattern)))
order = ['boot','lang','wifi','kb','tz','time','card','copy','home','games','ingame','settings','look','about']
def key(f):
    b = os.path.basename(f)[:-4].split('_')
    return (b[0], b[1], order.index(b[2]) if b[2] in order else 99)
files.sort(key=key)
ims = [Image.open(f).convert('RGB') for f in files]
tw = int(max(i.width for i in ims) * scale); th = int(max(i.height for i in ims) * scale)
rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (tw + 12) + 12, rows * (th + 30) + 12), (24, 26, 27))
d = ImageDraw.Draw(sheet)
try: font = ImageFont.truetype(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sdui', 'fonts', 'Manrope-600.ttf'), 13)
except Exception: font = None
for n, (f, im) in enumerate(zip(files, ims)):
    r, c = divmod(n, cols)
    x, y = 12 + c * (tw + 12), 12 + r * (th + 30)
    t = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    sheet.paste(t, (x, y + 18))
    d.text((x, y), os.path.basename(f)[:-4], fill=(160, 175, 172), font=font)
sheet.save(out)
print(out, sheet.size, len(ims))
