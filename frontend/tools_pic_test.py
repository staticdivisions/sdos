# 0.1.14 local tests: shaders/overlays, .m3u disc swap, RetroArch menu toggle.
# usage: python3 tools_pic_test.py
import os, sys, json, zlib, struct, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SDUI_MOCK'] = '1'
os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
from sdui import picture as P, device
from sdui.app import App

ok = 0
def check(c, msg):
    global ok
    if not c: raise SystemExit('FAIL: ' + msg)
    ok += 1

# fake RetroArch disc control (saturating next/prev, index change only with the tray open)
def ra_sim(start, count, cmds):
    idx, ejected = start, False
    for c in cmds:
        if c == 'DISK_EJECT_TOGGLE': ejected = not ejected
        elif c == 'DISK_NEXT' and ejected: idx = min(idx + 1, count - 1)
        elif c == 'DISK_PREV' and ejected: idx = max(idx - 1, 0)
    return idx, ejected
for n in range(2, 6):
    for start in range(n):
        for t in range(n):
            idx, ej = ra_sim(start, n, P.disc_commands(t, n))
            check(idx == t and not ej, 'disc %d->%d of %d' % (start, t, n))

d = tempfile.mkdtemp()
m = os.path.join(d, 'FF (USA).m3u')
open(m, 'w').write('\ufeff# comment\nFF (USA) (Disc 1).chd\n\nFF (USA) (Disc 2).chd|Second\nFF3.cue\n')
ds = P.m3u_discs(m)
check([x[1] for x in ds] == ['Disc 1', 'Second', 'Disc 3'], 'm3u labels %r' % ds)
check(P.m3u_discs(os.path.join(d, 'x.cue')) == [], 'non-m3u')
os.makedirs(os.path.join(d, 'saves', os.path.basename(d)))
json.dump({'image_index': 2, 'image_path': 'x'}, open(os.path.join(d, 'saves', os.path.basename(d), 'FF (USA).ldci'), 'w'))
check(P.last_disc(m, saves=os.path.join(d, 'saves')) == 2, 'ldci')
check(P.last_disc(os.path.join(d, 'none.m3u'), saves=os.path.join(d, 'saves')) == 0, 'no ldci')

cfg = os.path.join(d, 'ra.cfg')
open(cfg, 'w').write('video_driver = "glcore"\n'); check(P.shader_kind(cfg) == 'slang', 'glcore')
open(cfg, 'w').write('video_driver = "gl"\n'); check(P.shader_kind(cfg) == 'glsl', 'gl')
check(P.shader_kind(os.path.join(d, 'nope')) == 'slang', 'default kind')
check(P.shader_rel('off', 'slang') is None, 'off rel')
check(P.shader_live_path('off', 'glsl', '/s') == '/s/nearest.glslp', 'off live')
check(P.step(P.SHADERS, 'crt', 1) == 'off' and P.step(P.SHADERS, 'off', -1) == 'crt', 'step wraps')

# presets exist in the ROCKNIX 20261101 rootfs (if unpacked on this box)
ROOT = os.environ.get('SDOS_ROOTFS_SHARE', '')   # optional: an unpacked base image's /usr/share
if ROOT and os.path.isdir(ROOT):
    for sid, _, sl, gl in P.SHADERS:
        if sl: check(os.path.exists(os.path.join(ROOT, 'slang-shaders', sl)), 'slang ' + sl)
        if gl: check(os.path.exists(os.path.join(ROOT, 'glsl-shaders', gl)), 'glsl ' + gl)
    for k, rel in P.PASSTHRU.items():
        check(os.path.exists(os.path.join(ROOT, k + '-shaders', rel)), 'passthru ' + rel)

def png_rows(data):
    check(data[:8] == b'\x89PNG\r\n\x1a\n', 'png sig')
    w, h = struct.unpack('>II', data[16:24])
    i, idat = 8, b''
    while i < len(data):
        L = struct.unpack('>I', data[i:i + 4])[0]; t = data[i + 4:i + 8]
        if t == b'IDAT': idat += data[i + 8:i + 8 + L]
        i += 12 + L
    raw = zlib.decompress(idat); st = w * 4 + 1
    return w, h, [raw[y * st + 1:(y + 1) * st] for y in range(h)]
for key in ('lines', 'grid'):
    w, h, rows = png_rows(P.overlay_png(key, 720, 480))
    check((w, h) == (720, 480) and len(rows) == 480, key + ' size')
    check(all(len(r) == 2880 for r in rows), key + ' row len')
w, h, rows = png_rows(P.overlay_png('lines', 640, 480))
check(rows[0][3] == 0 and rows[1][3] == 120, 'scanline alpha')
check(P.overlay_png('off', 640, 480) is None, 'off png')
live, store = os.path.join(d, 'live'), os.path.join(d, 'store')
check(P.write_overlay('off', 640, 480, live, store) == 'none', 'off overlay value')
v = P.write_overlay('grid', 640, 480, live, store)
check(v == 'sdos/grid.cfg', 'overlay value')
txt = open(os.path.join(store, v)).read()
check('overlay0_overlay = "%s/sdos/grid-640x480.png"' % store in txt and 'overlay0_full_screen = true' in txt, 'overlay cfg')
check(os.path.exists(os.path.join(store, 'sdos', 'grid-640x480.png')), 'overlay png written')

# Device.swap_disc sends the commands in order, spaced out
class FakeDev:
    def __init__(self): self.sent = []
    def ra(self, c, want=False): self.sent.append((c, time.time()))
fd = FakeDev()
device.Device.swap_disc(fd, 1, 3)
time.sleep(0.5 + 0.3 * 6 + 0.4)
check([c for c, _ in fd.sent] == P.disc_commands(1, 3), 'swap_disc order %r' % fd.sent)
gaps = [b[1] - a[1] for a, b in zip(fd.sent, fd.sent[1:])]
check(min(gaps) >= 0.25, 'commands spaced (RetroArch edge-detects them)')

# Device.set_shader / set_overlay with a fake shader folder and system.cfg
class FakeRA(FakeDev):
    def __init__(self): super().__init__(); self.cfg = {}
    def set_setting(self, k, v): self.cfg[k] = v
    def is_ra(self): return True
    def game_running(self): return True
sd = os.path.join(d, 'shaders'); P.SHADER_DIR = sd
for rel in ('scanlines/scanline.slangp', 'nearest.slangp'):
    os.makedirs(os.path.dirname(os.path.join(sd, rel)), exist_ok=True); open(os.path.join(sd, rel), 'w').write('shaders = 1\n')
P.RA_CFG = os.path.join(d, 'nope.cfg')
_kind = P.shader_kind; P.shader_kind = lambda cfg=None: _kind(os.path.join(d, 'nope.cfg'))
f = FakeRA(); check(device.Device.set_shader(f, 'lines') == '', 'set_shader ok')
check(f.cfg == {'global.shaderset': 'scanlines/scanline.slangp'} and f.sent[-1][0] == 'SET_SHADER ' + sd + '/scanlines/scanline.slangp', 'shader live %r' % f.sent)
f = FakeRA(); device.Device.set_shader(f, 'off')
check(f.cfg['global.shaderset'] == 'none' and f.sent[-1][0] == 'SET_SHADER ' + sd + '/nearest.slangp', 'shader off')
f = FakeRA(); check(device.Device.set_shader(f, 'crt') != '' and f.cfg == {} and f.sent == [], 'missing preset is refused')
P.OVL_LIVE, P.OVL_STORE = live, store
_wo = P.write_overlay; P.write_overlay = lambda k, w, h: _wo(k, w, h, live, store)
f = FakeRA(); check(device.Device.set_overlay(f, 'lines', 720, 480) and f.cfg['global.overlayset'] == 'sdos/lines.cfg', 'set_overlay')
f = FakeRA(); device.Device.set_overlay(f, 'off', 720, 480); check(f.cfg['global.overlayset'] == 'none', 'overlay off')

# App: game menu rows, RetroArch menu toggle, persistence
class G:
    W, H = 640, 480
def mkapp(st=None):
    dev = device.make(); dev.load_state = lambda: dict(st or {}); dev.state = {}; dev.save_state = lambda: None
    return App.__new__(App), dev
from sdui.gfx import Gfx
from sdui import main as M
win, ren, w, h = M.setup_sdl(640, 480, False, software=True)
dev = device.make(); dev.save_state = lambda: None
app = App(Gfx(ren, w, h), dev)
app.game = {'title': 'FF', 'sys': 'psx', 'path': m}; app._disc_for = None
OV = app.ovl_list()
check(OV == ['Resume', 'Save state', 'Load state', 'Disc', 'Shader', 'Overlay', 'Emulator settings', 'Settings', 'Quit game'], 'menu %r' % OV)
app.ra_menu = False
check('Emulator settings' not in app.ovl_list(), 'RetroArch menu hidden')
app.game = {'title': 'G', 'sys': 'gba', 'path': '/x/g.gba'}
check('Disc' not in app.ovl_list() and 'Shader' in app.ovl_list(), 'no disc row for one-disc games')
app.game = {'title': 'T', 'sys': 'tool', 'path': '/x'}
check(app.ovl_list() == ['Resume', 'Quit'], 'tool menu unchanged')
app.ra_menu = True
app.game = {'title': 'FF', 'sys': 'psx', 'path': m}; app._disc_for = None
app.screen = 'game'; app.ovl = True; app.sel['ovl'] = app.ovl_list().index('Disc')
app.key_game('right'); check(app.disc_pick == 1, 'pick next disc')
app.key_game('left'); app.key_game('left'); check(app.disc_pick == 2, 'pick wraps')
app.key_game('a'); check(app.disc == 2 and not app.ovl and dev._disc == 2, 'disc swap')
app.ovl = True; app.sel['ovl'] = app.ovl_list().index('Shader')
app.key_game('right'); check(app.shader == 'sharp' and dev._shader == 'sharp', 'shader right')
app.sel['ovl'] = app.ovl_list().index('Overlay')
app.key_game('left'); check(app.overlay == 'grid' and dev._overlay == 'grid', 'overlay left')
app.persist()
check(dev.state.get('shader') == 'sharp' and dev.state.get('overlay') == 'grid' and dev.state.get('ra_menu') is True, 'persist %r' % dev.state)
# settings rows
app.screen = 'settings'; app.ctx = 'home'
keys = [r['k'] for r in app.set_items()]
check(all(k in keys for k in ('shader', 'overlay', 'ra_menu')), 'settings rows')
app.sel['settings'] = keys.index('ra_menu'); app.key_settings('a'); check(app.ra_menu is False and dev.state['ra_menu'] is False, 'settings toggle')
app.key_settings('right'); check(app.ra_menu is True, 'settings toggle back')
# reload from saved state
dev2 = device.make(); dev2.load_state = lambda: dict(shader='crt', overlay='lines', ra_menu=False)
app2 = App(Gfx(ren, w, h), dev2)
check(app2.shader == 'crt' and app2.overlay == 'lines' and app2.ra_menu is False, 'state restore')
dev3 = device.make(); dev3.load_state = lambda: dict(shader='bogus', overlay=None)
app3 = App(Gfx(ren, w, h), dev3)
check(app3.shader == 'off' and app3.overlay == 'off' and app3.ra_menu is True, 'defaults')
app.render()
print('ok: %d checks' % ok)
