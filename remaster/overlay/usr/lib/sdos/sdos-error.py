#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# sdOS: a plain error screen shown when the menu fails to start 3 times in a row.
# Standalone on purpose (no sdui imports): SDL2 + SDL2_ttf via ctypes.
# Exit 0 = user pressed a button or 10 minutes passed (launcher then retries); non-zero = could not show it.
import ctypes as C, sys, os, time
LOG = sys.argv[1] if len(sys.argv) > 1 else '/var/log/sd-ui.log'
sdl = C.CDLL('libSDL2-2.0.so.0'); ttf = C.CDLL('libSDL2_ttf-2.0.so.0')
vp, i, u32, cs = C.c_void_p, C.c_int, C.c_uint32, C.c_char_p
def f(lib, n, r, *a):
    fn = getattr(lib, n); fn.restype = r; fn.argtypes = list(a); return fn
class Rect(C.Structure): _fields_ = [('x', i), ('y', i), ('w', i), ('h', i)]
class Color(C.Structure): _fields_ = [('r', C.c_uint8), ('g', C.c_uint8), ('b', C.c_uint8), ('a', C.c_uint8)]
class Surf(C.Structure): _fields_ = [('flags', u32), ('format', vp), ('w', i), ('h', i)]
Init = f(sdl, 'SDL_Init', i, u32); GetError = f(sdl, 'SDL_GetError', cs)
CreateWindow = f(sdl, 'SDL_CreateWindow', vp, cs, i, i, i, i, u32)
CreateRenderer = f(sdl, 'SDL_CreateRenderer', vp, vp, i, u32)
GetOut = f(sdl, 'SDL_GetRendererOutputSize', i, vp, C.POINTER(i), C.POINTER(i))
SetLogical = f(sdl, 'SDL_RenderSetLogicalSize', i, vp, i, i)
Color_ = f(sdl, 'SDL_SetRenderDrawColor', i, vp, C.c_uint8, C.c_uint8, C.c_uint8, C.c_uint8)
Clear = f(sdl, 'SDL_RenderClear', i, vp); Present = f(sdl, 'SDL_RenderPresent', None, vp)
FillRect = f(sdl, 'SDL_RenderFillRect', i, vp, C.POINTER(Rect))
TexFromSurf = f(sdl, 'SDL_CreateTextureFromSurface', vp, vp, vp)
Copy = f(sdl, 'SDL_RenderCopy', i, vp, vp, C.POINTER(Rect), C.POINTER(Rect))
FreeSurf = f(sdl, 'SDL_FreeSurface', None, vp); DestroyTex = f(sdl, 'SDL_DestroyTexture', None, vp)
WaitEv = f(sdl, 'SDL_WaitEventTimeout', i, vp, i)
NumJoy = f(sdl, 'SDL_NumJoysticks', i); JoyOpen = f(sdl, 'SDL_JoystickOpen', vp, i)
ShowCursor = f(sdl, 'SDL_ShowCursor', i, i); Quit = f(sdl, 'SDL_Quit', None)
TTF_Init = f(ttf, 'TTF_Init', i); OpenFont = f(ttf, 'TTF_OpenFont', vp, cs, i)
Render = f(ttf, 'TTF_RenderUTF8_Blended', C.POINTER(Surf), vp, cs, Color)

os.environ.setdefault('SDL_VIDEO_WAYLAND_WMCLASS', 'sdui-error')
if Init(0x20 | 0x200 | 0x4000) != 0:
    print('sdos-error: SDL_Init failed:', GetError()); sys.exit(2)
TTF_Init()
win = CreateWindow(b'sdOS', 0x2FFF0000, 0x2FFF0000, 640, 480, 0x4 | 0x1001)
if not win:
    print('sdos-error: window failed:', GetError()); sys.exit(3)
ren = CreateRenderer(win, -1, 0x2) or CreateRenderer(win, -1, 0x1)
if not ren:
    print('sdos-error: renderer failed:', GetError()); sys.exit(4)
W, H = C.c_int(), C.c_int(); GetOut(ren, C.byref(W), C.byref(H))
W, H = (W.value or 640), (H.value or 480)
SetLogical(ren, W, H); ShowCursor(0)
for j in range(NumJoy()): JoyOpen(j)
FONTS = ['/usr/share/sd-ui/sdui/fonts/Manrope-600.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf',
         '/usr/share/fonts/liberation/LiberationSans-Regular.ttf']
def font(sz):
    for p in FONTS:
        if os.path.exists(p):
            fo = OpenFont(p.encode(), sz)
            if fo: return fo
    return None
big, small = font(max(18, H // 18)), font(max(11, H // 40))
if not big or not small:
    print('sdos-error: no usable font'); sys.exit(5)
def text(fo, s, x, y, col):
    sf = Render(fo, s.encode('utf-8', 'replace') or b' ', Color(*col, 255))
    if not sf: return 0
    t = TexFromSurf(ren, sf); w, h = sf.contents.w, sf.contents.h; FreeSurf(sf)
    Copy(ren, t, None, C.byref(Rect(x, y, w, h))); DestroyTex(t); return h
try:
    NOISE = ('MESA', 'setlocale', 'import-environment', 'showing the error screen', 'strings:', 'system.cfg: No such')
    tail = [l.rstrip()[:110] for l in open(LOG, errors='replace').read().splitlines()
            if l.strip() and not any(n in l for n in NOISE)][-14:]
except Exception as e:
    tail = ['(could not read %s: %s)' % (LOG, e)]
def draw():
    Color_(ren, 12, 20, 22, 255); Clear(ren)
    Color_(ren, 255, 176, 32, 255); FillRect(ren, C.byref(Rect(0, 0, W, max(4, H // 120))))
    m = W // 22; y = H // 14
    y += text(big, 'sdOS could not start', m, y, (240, 240, 240)) + H // 40
    for s in ('The menu stopped 3 times in a row.',
              'Logs were copied to the SDOS drive, in the sdos-logs folder.',
              'Put the card in a PC and send that folder to Static Divisions.',
              'Press any button to try again.'):
        y += text(small, s, m, y, (190, 205, 205)) + 4
    y += H // 30
    for s in tail:
        if y > H - H // 20: break
        y += text(small, s, m, y, (120, 140, 140)) + 1
    Present(ren)
ev = (C.c_uint8 * 64)()
t0 = time.time(); last = 0
while time.time() - t0 < 600:
    if time.time() - last > 1: draw(); last = time.time()
    if WaitEv(ev, 250):
        typ = C.cast(ev, C.POINTER(C.c_uint32))[0]
        if typ in (0x300, 0x603) and time.time() - t0 > 2:   # key down / joystick button down (ignore the first 2 s)
            break
        if typ == 0x100: break
Quit(); sys.exit(0)
