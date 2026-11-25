# Render Bluetooth settings screens at 640x480 and 720x480 in a few themes.
# usage: SDL_VIDEODRIVER=offscreen python3 tools_bt_preview.py [outdir]
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SDUI_MOCK'] = '1'
os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
os.environ['SDUI_FIXED_TIME'] = '1795491000'
from sdui import main as M, device
from sdui.gfx import Gfx
from sdui.app import App
from sdui import look as LK

OUT = sys.argv[1] if len(sys.argv) > 1 else 'preview-out'
THEMES = ['teal', 'amber', 'magenta']
SIZES = [(640, 480), (720, 480)]
SCREENS = [
    ('settings', 'settings'),
    ('bt_off', 'btoff'),
    ('bt_on', 'bt'),
    ('bt_searching', 'btscan'),
]

def shoot(ren, W, H, path, theme, name):
    app = App(Gfx(ren, W, H), device.make(), shot=True)
    app.set_look(LK.theme_look(theme))
    app.jump_to(name)
    M.sdl.SetRenderDrawColor(ren, 0, 0, 0, 255)
    M.sdl.RenderClear(ren)
    app.render(); app.render()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    M.save_png(ren, W, H, path)
    print('wrote', path)

def main():
    os.makedirs(OUT, exist_ok=True)
    for W, H in SIZES:
        win, ren, w, h = M.setup_sdl(W, H, False, software=True)
        for theme in THEMES:
            for label, name in SCREENS:
                shoot(ren, w, h, os.path.join(OUT, '%dx%d_%s_%s.png' % (w, h, theme, label)), theme, name)
        M.sdl.DestroyWindow(win)
        M.sdl.Quit()
    print('done', OUT)

if __name__ == '__main__':
    main()
