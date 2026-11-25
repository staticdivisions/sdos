# Entry point: window, input (keyboard + handheld gamepad via ROCKNIX's es_input.cfg), main loop, screenshot mode.
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
import os, sys, time, ctypes as C
import xml.etree.ElementTree as ET
from . import sdl
from .gfx import Gfx
from .app import App
from . import device
from . import btnswap

KEYS = {1073741906: 'up', 1073741905: 'down', 1073741904: 'left', 1073741903: 'right', 13: 'a', ord('z'): 'a',
        ord('x'): 'b', 8: 'b', ord('y'): 'y', ord('s'): 'x', ord('q'): 'l1', ord('w'): 'r1', 27: 'menu', ord('m'): 'menu'}
# H700 Gamepad defaults (evdev order: B/A/X/Y = btn 0/1/2/3). Used if no es_input map is found.
H700 = {1: 'a', 0: 'b', 2: 'x', 3: 'y', 13: 'up', 14: 'down', 15: 'left', 16: 'right', 9: 'start', 8: 'select', 10: 'hotkey', 4: 'l1', 5: 'r1'}


def es_mapping(name, guid):
    for p in ('/storage/.config/emulationstation/es_input.cfg', '/usr/config/emulationstation/es_input.cfg'):
        if not os.path.exists(p):
            continue
        try:
            root = ET.parse(p).getroot()
        except Exception:
            continue
        best = None
        for ic in root.findall('inputConfig'):
            if ic.get('type') != 'joystick':
                continue
            if ic.get('deviceGUID') == guid or (best is None and ic.get('deviceName') == name):
                best = ic
                if ic.get('deviceGUID') == guid:
                    break
        if best is None:
            continue
        btn, hat, axis = {}, {}, {}
        ren = {'hotkeyenable': 'hotkey', 'leftshoulder': 'l1', 'rightshoulder': 'r1'}
        for inp in best.findall('input'):
            nm = ren.get(inp.get('name'), inp.get('name')); t = inp.get('type'); i = int(inp.get('id')); v = int(inp.get('value'))
            if t == 'button': btn[i] = nm
            elif t == 'hat': hat[(i, v)] = nm
            elif t == 'axis' and nm.startswith('leftanalog'): axis[(i, 1 if v > 0 else -1)] = nm.replace('leftanalog', '')
        return btn, hat, axis
    return None



def controller_flags(pads):
    """ES/runemu --controllers flags for up to 5 pads (player 1 is the first, usually the built-in pad)."""
    parts = []
    for i, d in enumerate(pads[:5], 1):
        name = (d.get('name') or 'Pad').replace(' ', '_')
        parts.append('-p%dindex %d -p%dguid %s -p%dname %s -p%dnbbuttons %d -p%dnbhats %d -p%dnbaxes %d' % (
            i, d['idx'], i, d['guid'], i, name, i, d['nbbuttons'], i, d['nbhats'], i, d['nbaxes']))
    return ' '.join(parts)


class Input:
    REPEAT_DELAY, REPEAT_RATE = .32, .07
    def __init__(self):
        self.joys = {}; self.held = {}; self.menu_down = None; self.other_during_menu = False
        self.controllers = ''

    def open_all(self):
        for i in range(sdl.NumJoysticks()):
            self.open(i)

    def open(self, idx):
        j = sdl.JoystickOpen(idx)
        if not j:
            return
        iid = sdl.JoystickInstanceID(j)
        if iid in self.joys:
            return
        name = (sdl.JoystickName(j) or b'').decode(errors='ignore')
        buf = C.create_string_buffer(64)
        sdl.JoystickGetGUIDString(sdl.JoystickGetGUID(j), buf, 64)
        guid = buf.value.decode()
        m = es_mapping(name, guid)
        if m is None and 'H700' in name:
            m = (H700, {}, {})
        if m is None:
            m = ({0: 'b', 1: 'a', 2: 'y', 3: 'x', 6: 'select', 7: 'start', 8: 'hotkey'}, {}, {})
        self.joys[iid] = {
            'j': j, 'map': m, 'name': name, 'idx': idx, 'guid': guid,
            'nbbuttons': sdl.JoystickNumButtons(j), 'nbhats': sdl.JoystickNumHats(j),
            'nbaxes': sdl.JoystickNumAxes(j),
        }
        self._rebuild_controllers()

    def close(self, iid):
        jd = self.joys.pop(iid, None)
        if jd and jd.get('j'):
            try:
                sdl.JoystickClose(jd['j'])
            except Exception:
                pass
        self._rebuild_controllers()

    def _rebuild_controllers(self):
        pads = sorted(self.joys.values(), key=lambda d: d.get('idx', 0))
        self.controllers = controller_flags(pads)

    def press(self, name, out):
        """name = logical button. Emits UI keys into out."""
        if name == 'hotkey':
            self.menu_down = time.time(); self.other_during_menu = False; return
        if self.menu_down is not None:
            self.other_during_menu = True
        k = {'a': 'a', 'b': 'b', 'y': 'y', 'x': 'x', 'l1': 'l1', 'r1': 'r1', 'select': 'select', 'start': 'menu',
             'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right'}.get(name)
        if k:
            out.append(k)
            if k in ('up', 'down', 'left', 'right'):
                self.held[k] = time.time() + self.REPEAT_DELAY

    def release(self, name, out):
        if name == 'hotkey':
            if self.menu_down is not None and not self.other_during_menu and time.time() - self.menu_down < .9:
                out.append('menu_tap')
            self.menu_down = None; return
        k = {'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right'}.get(name)
        if k:
            self.held.pop(k, None)

    def repeats(self, out):
        now = time.time()
        for k, t in list(self.held.items()):
            if now >= t:
                out.append(k); self.held[k] = now + self.REPEAT_RATE

    def handle(self, ev, out):
        t = ev.type
        if t == sdl.KEYDOWN:
            if ev.key.repeat:
                return
            k = KEYS.get(ev.key.keysym.sym)
            if k == 'menu': out.append('menu_tap')
            elif k: out.append(k)
            if k in ('up', 'down', 'left', 'right'): self.held[k] = time.time() + self.REPEAT_DELAY
        elif t == sdl.KEYUP:
            k = KEYS.get(ev.key.keysym.sym)
            if k: self.held.pop(k, None)
        elif t in (sdl.JOYBUTTONDOWN, sdl.JOYBUTTONUP):
            jd = self.joys.get(ev.jbutton.which)
            if not jd: return
            nm = jd['map'][0].get(ev.jbutton.button)
            if nm:
                nm = btnswap.remap_logical(nm, builtin=btnswap.is_builtin_pad(jd.get('name')))
                (self.press if t == sdl.JOYBUTTONDOWN else self.release)(nm, out)
        elif t == sdl.JOYHATMOTION:
            v = ev.jhat.value
            for bit, nm in ((1, 'up'), (4, 'down'), (8, 'left'), (2, 'right')):
                if v & bit and nm not in self.held: self.press(nm, out)
                elif not v & bit and nm in self.held: self.release(nm, out)
        elif t == sdl.JOYAXISMOTION:
            jd = self.joys.get(ev.jaxis.which)
            if not jd: return
            axm = jd['map'][2]
            for sgn in (1, -1):
                nm = axm.get((ev.jaxis.axis, sgn))
                if not nm: continue
                on = ev.jaxis.value * sgn > 20000
                key = 'ax_' + nm
                if on and key not in self.held:
                    self.held[key] = 1; self.press(nm, out)
                elif not on and key in self.held:
                    self.held.pop(key, None); self.release(nm, out)
        elif t == sdl.JOYDEVICEADDED:
            self.open(ev.jdevice.which)
        elif t == sdl.JOYDEVICEREMOVED:
            self.close(ev.jdevice.which)


def logical_size(W, H):
    """Dense panels (X55 1280x720, RGB20 Pro 1024x768) and HDMI: lay out at about 640x480 / 854x480 and let the
    renderer scale up, so text is as big as on a 3.5" 640x480 screen. Up to 1.4x (720x720, 960x544) stays 1:1."""
    s = float(os.environ.get('SDUI_SCALE') or 0) or min(W / 640.0, H / 480.0)
    if s < 1.4:
        return W, H
    return int(round(W / s)), int(round(H / s))


def setup_sdl(W, H, fullscreen, software=False):
    # SDL 2.32 on ROCKNIX takes the Wayland app_id from this variable (the hints alone left it as 'python3.14'),
    # and the in-game menu focuses the UI by app_id="sdui" through swaymsg.
    os.environ['SDL_VIDEO_WAYLAND_WMCLASS'] = 'sdui'
    sdl.SetHint(b'SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS', b'1')
    sdl.SetHint(b'SDL_APP_ID', b'sdui')
    sdl.SetHint(b'SDL_VIDEO_WAYLAND_WMCLASS', b'sdui')
    sdl.SetHint(b'SDL_RENDER_SCALE_QUALITY', b'1')
    if sdl.Init(sdl.INIT_VIDEO | sdl.INIT_JOYSTICK | sdl.INIT_EVENTS | sdl.INIT_TIMER) != 0:
        raise SystemExit('SDL_Init: ' + sdl.GetError().decode())
    sdl.TTF_Init(); sdl.IMG_Init(2)
    flags = sdl.WINDOW_SHOWN | (sdl.WINDOW_FULLSCREEN_DESKTOP if fullscreen else 0)
    win = sdl.CreateWindow(b'Static Divisions', 0x2FFF0000, 0x2FFF0000, W, H, flags)
    if not win:
        raise SystemExit('SDL_CreateWindow: ' + sdl.GetError().decode())
    ren = None
    if not software:
        ren = sdl.CreateRenderer(win, -1, sdl.RENDERER_ACCELERATED | sdl.RENDERER_PRESENTVSYNC)
    if not ren:
        ren = sdl.CreateRenderer(win, -1, sdl.RENDERER_SOFTWARE)
    if fullscreen:
        w, h = C.c_int(), C.c_int()
        sdl.GetRendererOutputSize(ren, C.byref(w), C.byref(h))
        if w.value > 0 and h.value > 0:
            W, H = logical_size(w.value, h.value)
    sdl.RenderSetLogicalSize(ren, W, H)
    sdl.ShowCursor(0)
    return win, ren, W, H


def refit(ren, g, app):
    """Sway makes the window fullscreen after it is created, so the first output size can be the requested
    640x480 (the UI then sat pillarboxed on 720x720 / 1280x720 panels). Re-check on every window event."""
    w, h = C.c_int(), C.c_int()
    sdl.GetRendererOutputSize(ren, C.byref(w), C.byref(h))
    if w.value <= 0 or h.value <= 0:
        return
    W, H = logical_size(w.value, h.value)
    if (W, H) != (g.W, g.H):
        sdl.RenderSetLogicalSize(ren, W, H)
        g.W, g.H = W, H
        app.W, app.H = W, H
        app.dirty = True
        device.log('sdui resized: output %dx%d, layout %dx%d' % (w.value, h.value, W, H))


def save_png(ren, W, H, path):
    surf = sdl.CreateRGBSurfaceWithFormat(0, W, H, 32, sdl.PIXELFORMAT_RGBA32)
    sdl.RenderReadPixels(ren, None, sdl.PIXELFORMAT_RGBA32, surf.contents.pixels, surf.contents.pitch)
    sdl.IMG_SavePNG(surf, path.encode())
    sdl.FreeSurface(surf)


SHOT_SCREENS = ['boot', 'devpick', 'lang', 'wifi', 'kb', 'tz', 'time', 'card', 'copy', 'hask', 'home', 'games', 'ingame', 'settings', 'bt', 'btoff', 'btscan', 'look', 'about', 'tools', 'music', 'model', 'mtrial', 'mtrialkeep', 'color', 'confirm']


def shots(outdir, res_list, themes):
    from . import look as LK
    os.makedirs(outdir, exist_ok=True)
    os.environ['SDUI_MOCK'] = '1'
    for res in res_list:
        W, H = map(int, res.split('x'))
        win, ren, W, H = setup_sdl(W, H, False, software=True)
        for th in themes:
            dev = device.make()
            g = Gfx(ren, W, H)
            app = App(g, dev, shot=True)
            app.set_look(LK.theme_look(th))
            for name in SHOT_SCREENS:
                app.jump_to(name)
                sdl.SetRenderDrawColor(ren, 0, 0, 0, 255); sdl.RenderClear(ren)
                app.render(); app.render()
                save_png(ren, W, H, os.path.join(outdir, '%s_%s_%s.png' % (res, th, name)))
            # extra states
            for nm, fn in (('home_dense_size_l', lambda: app.set_look(dict(app.look, size='l'))),):
                pass
        sdl.DestroyWindow(win)
        sdl.Quit()
    return True


def main():
    args = sys.argv[1:]
    if args and args[0] == '--shots':
        outdir = args[1]
        res = args[2].split(',') if len(args) > 2 else ['640x480']
        themes = args[3].split(',') if len(args) > 3 else ['teal']
        shots(outdir, res, themes)
        return
    mock = os.environ.get('SDUI_MOCK') == '1'
    W, H = 640, 480
    if os.environ.get('SDUI_RES'):
        W, H = map(int, os.environ['SDUI_RES'].split('x'))
    win, ren, W, H = setup_sdl(W, H, not mock)
    dev = device.make()
    inp = Input(); inp.open_all()
    dev.controllers = inp.controllers
    g = Gfx(ren, W, H)
    app = App(g, dev)
    device.log('sdui %s up: %dx%d, driver %s, %d joystick(s), screen %s' % (device.VERSION, W, H, os.environ.get('SDL_VIDEODRIVER', '?'), sdl.NumJoysticks(), app.screen))
    ev = sdl.Event()
    t_up = time.time()
    running = True
    while running:
        out = []
        busy = app.dirty
        got = sdl.WaitEventTimeout(C.byref(ev), 16 if busy else 120)
        while got:
            if ev.type == sdl.QUIT:
                running = False
            elif ev.type == sdl.WINDOWEVENT:
                app.dirty = True
                if not mock:
                    refit(ren, g, app)
            else:
                inp.handle(ev, out)
            got = sdl.PollEvent(C.byref(ev))
        inp.repeats(out)
        dev.controllers = inp.controllers
        if not mock and time.time() - t_up < 5:
            refit(ren, g, app)      # until Sway's fullscreen size has arrived
        hidden = app.in_game_hidden()
        for k in out:
            if hidden:
                if k == 'menu_tap':
                    app.key('menu')
                continue
            app.key('menu' if k == 'menu_tap' else k)
        app.tick()
        if app.in_game_hidden():
            continue
        if app.dirty:
            app.dirty = False
            app.render()
            sdl.RenderPresent(ren)
    sdl.Quit()
