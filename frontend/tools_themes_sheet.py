# Contact sheet of every theme preset (Home screen at 640x480) + the accent presets.
# usage: SDL_VIDEODRIVER=offscreen python3 tools_themes_sheet.py <out.png>
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SDUI_MOCK'] = '1'; os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
from sdui import main as M, device, look as LK, sdl
from sdui.gfx import Gfx
from sdui.app import App
from PIL import Image, ImageDraw, ImageFont
out = sys.argv[1]
W, H = 640, 480
win, ren, W, H = M.setup_sdl(W, H, False, software=True)
tiles = []
for t in LK.THEMES:
    g = Gfx(ren, W, H); app = App(g, device.make(), shot=True); app.set_look(LK.theme_look(t['id']))
    app.jump_to('home'); sdl.SetRenderDrawColor(ren, 0, 0, 0, 255); sdl.RenderClear(ren); app.render(); app.render()
    p = '/tmp/_th_%s.png' % t['id']; M.save_png(ren, W, H, p); tiles.append((t, Image.open(p).convert('RGB')))
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sdui/fonts/Manrope-700.ttf')
f1, f2 = ImageFont.truetype(FONT, 26), ImageFont.truetype(FONT, 17)
cols, pad, lab = 4, 24, 52
rows = (len(tiles) + cols - 1) // cols
acc = [a for a in LK.ACCENTS if a[2]]
sheet = Image.new('RGB', (pad + cols * (W + pad), pad + 70 + rows * (H + lab + pad) + 150), '#0B1012')
d = ImageDraw.Draw(sheet)
d.text((pad, pad), 'sdOS 0.1.3 · theme presets (all Roomy) · 640x480', font=f1, fill='#E8F4F2')
for i, (t, im) in enumerate(tiles):
    x = pad + (i % cols) * (W + pad); y = pad + 70 + (i // cols) * (H + lab + pad)
    sheet.paste(im, (x, y))
    c = LK.colors(LK.theme_look(t['id']))
    d.text((x, y + H + 10), '%d. %s' % (i + 1, t['name']), font=f1, fill='#E8F4F2')
    tag = 'light' if c['light'] else 'dark'
    d.text((x + W - d.textlength(tag, font=f2), y + H + 16), tag, font=f2, fill='#8FA3A0')
y = pad + 70 + rows * (H + lab + pad) + 10
d.text((pad, y), 'Accent presets (shown on dark; light themes use a deeper shade of the same hue)', font=f2, fill='#8FA3A0')
for i, (aid, nm, hexc) in enumerate(acc):
    x = pad + i * 190; d.rounded_rectangle((x, y + 36, x + 40, y + 76), 10, fill=hexc)
    d.text((x + 50, y + 44), nm, font=f2, fill='#E8F4F2')
sheet.save(out)
print('saved', out, sheet.size)
