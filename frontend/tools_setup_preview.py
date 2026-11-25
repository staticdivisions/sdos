# Render real 640x480 first-boot setup screens with the sdui software renderer.
# usage: SDL_VIDEODRIVER=offscreen python3 tools_setup_preview.py [outdir]
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SDUI_MOCK'] = '1'
os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
os.environ['SDUI_FIXED_TIME'] = '1795491000'  # 2026-11-23 7:30 PM America/Los_Angeles
from sdui import main as M, device
from sdui.gfx import Gfx
from sdui.app import App
from sdui import look as LK

OUT = sys.argv[1] if len(sys.argv) > 1 else 'preview-out'
THEME = 'teal'
W, H = 640, 480

def shoot(ren, W, H, name, setup):
    app = App(Gfx(ren, W, H), device.make(), shot=True)
    app.set_look(LK.theme_look(THEME))
    setup(app)
    M.sdl.SetRenderDrawColor(ren, 0, 0, 0, 255)
    M.sdl.RenderClear(ren)
    app.render(); app.render()
    path = os.path.join(OUT, name)
    M.save_png(ren, W, H, path)
    print('wrote', path)
    return path

def lang(app):
    app.jump_to('lang')
    app.sel['lang'] = 0

def devpick(app):
    app.jump_to('devpick')

def wifi_searching(app):
    app.jump_to('wifi')
    app.dev.wifi_status = None
    app.dev.nets = []
    app.dev.busy['scan'] = True
    app.sel['wifi'] = 0

def wifi_unconnected(app):
    app.jump_to('wifi')
    app.dev.wifi_status = None
    app.sel['wifi'] = 0

def wifi_connected(app):
    app.jump_to('wifi')
    app.dev.wifi_status = 'Home Network'
    app.sel['wifi'] = 0  # Continue

def tz(app):
    app.jump_to('tz')
    app.sel['tz'] = app.tz_index()

def time_continue(app):
    app.jump_to('time')
    it = app.time_items()
    app.sel['time'] = next(i for i, r in enumerate(it) if r.get('k') == 'go')

def card(app):
    app.jump_to('card')
    app.sel['card'] = 0

def ready(app):
    app.jump_to('copy')
    app.copy_top = 0

def kb(app):
    app.jump_to('kb')

def main():
    os.makedirs(OUT, exist_ok=True)
    win, ren, W, H = M.setup_sdl(640, 480, False, software=True)
    shots = [
        ('01_device_pick.png', devpick),
        ('02_welcome_language.png', lang),
        ('03_wifi_searching.png', wifi_searching),
        ('04_wifi_unconnected.png', wifi_unconnected),
        ('05_wifi_connected.png', wifi_connected),
        ('06_timezone.png', tz),
        ('07_time_continue.png', time_continue),
        ('08_games_location.png', card),
        ('09_ready_copy.png', ready),
        ('10_wifi_password_keyboard.png', kb),
    ]
    paths = [shoot(ren, W, H, name, fn) for name, fn in shots]
    M.sdl.DestroyWindow(win)
    M.sdl.Quit()
    print('done', len(paths), 'screens in', OUT)
    return paths

if __name__ == '__main__':
    main()
