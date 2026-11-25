# Drive the UI with random button presses in every layout and size; fail on any exception.
import os, sys, random, time, traceback
os.environ['SDUI_MOCK'] = '1'
from sdui import main as M, device
from sdui.gfx import Gfx
from sdui.app import App
from sdui import look as LK
import ctypes as C
random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
keys = ['up', 'down', 'left', 'right', 'a', 'b', 'y', 'menu']
n = 0
for res in ('640x480', '720x480', '720x720'):
    W, H = map(int, res.split('x'))
    win, ren, W, H = M.setup_sdl(W, H, False, software=True)
    for th in ('teal', 'amber', 'magenta', 'mono'):
        app = App(Gfx(ren, W, H), device.make(), shot=True)
        app.set_look(LK.theme_look(th))
        for start in M.SHOT_SCREENS:
            app.jump_to(start)
            for i in range(120):
                k = random.choice(keys)
                try:
                    app.key(k); app.tick(); app.render(); n += 1
                except Exception:
                    print('FAIL', res, th, start, 'screen=', app.screen, 'key=', k); traceback.print_exc(); sys.exit(1)
    M.sdl.DestroyWindow(win); M.sdl.Quit()
print('ok', n, 'steps')
