# Setup input tests: Start confirms Continue (except the OSK, where Start still means Join).
# usage: SDL_VIDEODRIVER=offscreen python3 tools_setup_input_test.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SDUI_MOCK'] = '1'
os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
from sdui import main as M, device
from sdui.gfx import Gfx
from sdui.app import App
from sdui import look as LK

def check(cond, msg):
    if not cond:
        raise SystemExit('FAIL: ' + msg)

def fresh(ren, W, H):
    app = App(Gfx(ren, W, H), device.make(), shot=True)
    app.set_look(LK.theme_look('teal'))
    return app

def main():
    win, ren, W, H = M.setup_sdl(640, 480, False, software=True)

    app = fresh(ren, W, H)
    app.jump_to('lang')
    check(app.screen == 'lang' and app.ctx == 'setup', 'lang is a setup screen')
    app.key('menu')  # Start
    check(app.screen == 'wifi', 'Start on Language confirms and advances to Wi-Fi, got %s' % app.screen)

    app = fresh(ren, W, H)
    app.jump_to('tz')
    app.sel['tz'] = app.tz_index()
    app.key('menu')
    check(app.screen == 'time', 'Start on Time zone confirms and advances, got %s' % app.screen)

    app = fresh(ren, W, H)
    app.jump_to('time')
    it = app.time_items()
    app.sel['time'] = next(i for i, r in enumerate(it) if r.get('k') == 'go')
    app.key('menu')
    check(app.screen == 'card', 'Start on Time Continue advances to Games location, got %s' % app.screen)

    app = fresh(ren, W, H)
    app.jump_to('time')
    app.sel['time'] = next(i for i, r in enumerate(it) if r.get('k') == 'go')
    app.key('a')
    check(app.screen == 'card', 'A on Time Continue still advances')

    app = fresh(ren, W, H)
    app.jump_to('card')
    app.key('menu')
    check(app.screen == 'copy', 'Start on Games location confirms, got %s' % app.screen)

    app = fresh(ren, W, H)
    app.jump_to('copy')
    app.key('menu')
    check(app.setup_done and app.screen == 'home', 'Start on setup Continue/Done finishes setup, got %s done=%s' % (app.screen, app.setup_done))

    # Already-connected wifi.txt state: Continue focused, Start/A breeze through
    app = fresh(ren, W, H)
    app.jump_to('wifi')
    app.dev.wifi_status = 'Home Network'
    app.sel['wifi'] = 0
    check(app.wifi_items()[0].get('k') == 'go', 'first row is Continue when already connected')
    app.key('menu')
    check(app.screen == 'tz', 'Start on Connected Continue advances to Time zone, got %s' % app.screen)

    app = fresh(ren, W, H)
    app.jump_to('wifi')
    app.dev.wifi_status = 'Home Network'
    app.sel['wifi'] = 0
    app.key('a')
    check(app.screen == 'tz', 'A on Connected Continue advances to Time zone')

    # Unconnected wifi: Start on Skip for now should also advance (same as A)
    app = fresh(ren, W, H)
    app.jump_to('wifi')
    it = app.wifi_items()
    skip = next(i for i, r in enumerate(it) if r['label'] == 'Skip for now')
    app.sel['wifi'] = skip
    app.key('menu')
    check(app.screen == 'tz', 'Start on Skip for now advances, got %s' % app.screen)

    # OSK: Start must Join, not type the highlighted key
    app = fresh(ren, W, H)
    app.jump_to('kb')
    app.pw = ''
    app.pw_cur = 0
    before = list(app.kb)
    app.key('menu')
    check(app.screen == 'kb', 'Start on empty OSK stays on the keyboard (Join with no password), got %s' % app.screen)
    check(app.pw == '', 'Start on OSK did not type a character')
    check(app.kb == before, 'Start on OSK did not move the key cursor')

    app = fresh(ren, W, H)
    app.jump_to('kb')
    app.pw = 'short'
    app.pw_cur = len(app.pw)
    app.key('menu')
    check(app.screen == 'kb', 'Start on a short password stays (Join still validates length)')
    check(app.pw == 'short', 'Start on OSK did not alter the password')

    app = fresh(ren, W, H)
    app.jump_to('kb')
    # password already set by jump_to; Start = Join should connect and leave the keyboard
    app._wifi_user_connect = True
    app.key('menu')
    app.tick()  # wifi_ok is posted by the mock backend, then applied
    check(app.screen == 'tz', 'Start/Join on a valid password submits and advances, got %s' % app.screen)

    # After setup, Start/menu on Settings must not be remapped to A (menu still goes back / opens settings elsewhere)
    app = fresh(ren, W, H)
    app.jump_to('settings')
    check(app.setup_done and app.ctx == 'home', 'settings is post-setup')
    check(not app.setup_start_confirms(), 'Start is not remapped after setup')
    app.key('menu')
    check(app.screen == 'home' or app.screen == 'settings', 'menu on Settings is not treated as a confirm typo, got %s' % app.screen)

    M.sdl.DestroyWindow(win)
    M.sdl.Quit()
    print('ok all setup input tests')

if __name__ == '__main__':
    main()
