# Drawing helpers on top of SDL2 renderer: cached text, SVG shapes, gradients.
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
import os, ctypes as C
from . import sdl

HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK_FONTS = ['/usr/config/ppsspp/assets/NotoSansJP-Regular.ttf', os.path.join(HERE, 'fonts', 'NotoSansJP-Regular.ttf')]
if os.environ.get('SDUI_FALLBACK_FONT'):   # desktop testing: point at a local NotoSansJP-Regular.ttf
    FALLBACK_FONTS.append(os.environ['SDUI_FALLBACK_FONT'])

def hx(h):
    h = h.lstrip('#'); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

ICONS = {
    'wifi': '<path d="M2 8.5a15 15 0 0 1 20 0"/><path d="M5.5 12.2a10 10 0 0 1 13 0"/><path d="M9 15.8a5 5 0 0 1 6 0"/><circle cx="12" cy="19.3" r="1" fill="#fff"/>',
    'lock': '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    'chev': '<path d="M9 6l6 6-6 6"/>',
    'check': '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    'menu': '<path d="M5 7h14M5 12h14M5 17h14"/>',
    'lr': '<path d="M9 7l-5 5 5 5M15 7l5 5-5 5"/>',
    'ud': '<path d="M7 9l5-5 5 5M7 15l5 5 5-5"/>',
}
STAR = '<path fill="#fff" d="M12 2.5l2.9 6.1 6.6.8-4.9 4.5 1.3 6.6L12 17.2l-5.9 3.3 1.3-6.6L2.5 9.4l6.6-.8z"/>'
MARK = ('<path d="M200.00 0.0L200.00 0.0A160 160 0 0 1 351.31 108.0L48.69 108.0A160 160 0 0 1 200.00 0.0Z"/>'
        '<path d="M5.08 120.0L314.92 120.0A160 160 0 0 1 319.80 168.0L0.20 168.0A160 160 0 0 1 5.08 120.0Z"/>'
        '<path d="M21.25 180.0L338.75 180.0A160 160 0 0 1 180.00 320.0L180.00 320.0A160 160 0 0 1 21.25 180.0Z"/>')
MARK_PARTS = MARK.split('/>')[:3]


class Gfx:
    def __init__(self, ren, W, H):
        self.r = ren; self.W = W; self.H = H
        self.fonts = {}; self.tcache = {}; self.scache = {}; self.fb = None
        self.alpha = 1.0     # global multiplier (view fade)
        self.ox = 0          # global x offset (view slide)
        for p in FALLBACK_FONTS:
            if os.path.exists(p):
                self.fb = p; break

    # ---------- fonts / text ----------
    def font(self, weight, size, fb=False):
        key = (weight, size, fb)
        f = self.fonts.get(key)
        if f is None:
            path = self.fb if fb else os.path.join(HERE, 'fonts', 'Manrope-%d.ttf' % weight)
            f = sdl.TTF_OpenFont(path.encode(), size)
            sdl.TTF_SetFontHinting(f, sdl.TTF_HINTING_LIGHT_SUBPIXEL)
            self.fonts[key] = f
        return f

    def _needs_fb(self, s):
        if not self.fb:
            return False
        f = self.font(700, 12)
        return any(not sdl.TTF_GlyphIsProvided32(f, ord(ch)) for ch in s if ord(ch) > 127)

    def text_tex(self, s, weight, size):
        size = max(6, int(round(size)))
        key = (s, weight, size)
        t = self.tcache.get(key)
        if t is None:
            f = self.font(weight, size, self._needs_fb(s))
            surf = sdl.TTF_RenderUTF8_Blended(f, s.encode('utf-8') or b' ', sdl.Color(255, 255, 255, 255))
            if not surf:
                return None
            tex = sdl.CreateTextureFromSurface(self.r, surf)
            w, h = surf.contents.w, surf.contents.h
            sdl.FreeSurface(surf)
            sdl.SetTextureBlendMode(tex, sdl.BLENDMODE_BLEND)
            t = (tex, w, h, sdl.TTF_FontHeight(f))
            self.tcache[key] = t
            if len(self.tcache) > 1500:
                for k in list(self.tcache)[:500]:
                    sdl.DestroyTexture(self.tcache.pop(k)[0])
        return t

    def lh(self, size):
        return size * 1.366

    def measure(self, s, weight, size, track=0.0):
        if not s:
            return 0
        if track:
            return sum(self.measure(ch, weight, size) for ch in s) + track * size * (len(s))
        t = self.text_tex(s, weight, size)
        return t[1] if t else 0

    def text(self, s, x, y, weight, size, color, alpha=1.0, track=0.0, maxw=None, lineh=None):
        """Draw text with its line box top at y (line box = 1.366em, like CSS 'normal')."""
        if not s:
            return 0
        if maxw is not None and self.measure(s, weight, size, track) > maxw:
            while s and self.measure(s + '…', weight, size, track) > maxw:
                s = s[:-1]
            s = s.rstrip() + '…'
        if track:
            cx = x
            for ch in s:
                cx += self.text(ch, cx, y, weight, size, color, alpha, lineh=lineh) + track * size
            return cx - x
        t = self.text_tex(s, weight, size)
        if not t:
            return 0
        tex, w, h, fh = t
        box = lineh if lineh is not None else self.lh(size)
        ty = y + (box - h) / 2.0
        r, g, b = hx(color)
        sdl.SetTextureColorMod(tex, r, g, b)
        sdl.SetTextureAlphaMod(tex, int(255 * max(0, min(1, alpha * self.alpha))))
        sdl.RenderCopyF(self.r, tex, None, C.byref(sdl.FRect(x + self.ox, ty, w, h)))
        return w

    def wrap(self, s, weight, size, maxw):
        lines = []
        for para in s.split('\n'):
            words, cur = para.split(' '), ''
            for wd in words:
                t = (cur + ' ' + wd).strip()
                if cur and self.measure(t, weight, size) > maxw:
                    lines.append(cur); cur = wd
                else:
                    cur = t
            lines.append(cur)
        return lines

    # ---------- SVG-backed shapes ----------
    def svg_tex(self, key, svg, w, h):
        k = (key, w, h)
        t = self.scache.get(k)
        if t is None:
            data = svg.encode()
            buf = C.create_string_buffer(data, len(data))
            rw = sdl.RWFromConstMem(buf, len(data))
            surf = sdl.IMG_LoadSizedSVG_RW(rw, max(1, w), max(1, h))
            if not surf:
                return None
            t = sdl.CreateTextureFromSurface(self.r, surf)
            sdl.FreeSurface(surf)
            sdl.SetTextureBlendMode(t, sdl.BLENDMODE_BLEND)
            self.scache[k] = t
            if len(self.scache) > 600:
                for kk in list(self.scache)[:200]:
                    sdl.DestroyTexture(self.scache.pop(kk))
        return t

    def _blit(self, tex, x, y, w, h, color, alpha):
        if not tex:
            return
        r, g, b = hx(color)
        sdl.SetTextureColorMod(tex, r, g, b)
        sdl.SetTextureAlphaMod(tex, int(255 * max(0, min(1, alpha * self.alpha))))
        sdl.RenderCopyF(self.r, tex, None, C.byref(sdl.FRect(x + self.ox, y, w, h)))

    def rrect(self, x, y, w, h, r, color, alpha=1.0, radii=None):
        w, h = int(round(w)), int(round(h))
        if w <= 0 or h <= 0:
            return
        if not r and not radii:
            return self.fill(x, y, w, h, color, alpha)
        if radii:
            tl, tr, br, bl = radii
            d = ('M%g 0H%gA%g %g 0 0 1 %g %gV%gA%g %g 0 0 1 %g %gH%gA%g %g 0 0 1 0 %gV%gA%g %g 0 0 1 %g 0Z' %
                 (tl, w - tr, tr, tr, w, tr, h - br, br, br, w - br, h, bl, bl, bl, h - bl, tl, tl, tl, tl))
            svg = '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><path fill="#fff" d="%s"/></svg>' % (w, h, d)
            key = ('rr4', radii)
        else:
            r = min(r, w / 2.0, h / 2.0)
            svg = '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><rect width="%d" height="%d" rx="%g" ry="%g" fill="#fff"/></svg>' % (w, h, w, h, r, r)
            key = ('rr', r)
        self._blit(self.svg_tex(key, svg, w, h), x, y, w, h, color, alpha)

    def ring(self, x, y, w, h, r, color, alpha=1.0, sw=2):
        w, h = int(round(w)), int(round(h))
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><rect x="%g" y="%g" width="%g" height="%g" rx="%g" fill="none" stroke="#fff" stroke-width="%g"/></svg>'
               % (w, h, sw / 2.0, sw / 2.0, w - sw, h - sw, max(0, r - sw / 2.0), sw))
        self._blit(self.svg_tex(('ring', r, sw), svg, w, h), x, y, w, h, color, alpha)

    def circle(self, cx, cy, rad, color, alpha=1.0):
        self.rrect(cx - rad, cy - rad, rad * 2, rad * 2, rad, color, alpha)

    def abxy_diamond_width(self, size, letter='A', letter_fs=12):
        size = float(size)
        r_lit = size * 0.155 * 1.22
        d = size * 0.36
        gap = size * 0.26
        # cx is at size/2; letter starts at cx + d + r_lit + gap
        return size * 0.5 + d + r_lit + gap + self.measure(letter, 800, letter_fs)

    def abxy_diamond(self, x, y, size, lit, dim, letter, letter_fs=12):
        """Minimal 4-button ABXY diamond (top/left/bottom/right). The right (A) dot is
        filled with `lit`; the others stay quiet. A letter is drawn to the right of the
        cluster. Returns the total width including the letter."""
        size = float(size)
        r = size * 0.155
        r_lit = r * 1.22
        d = size * 0.36
        cx = x + size * 0.5
        cy = y + size * 0.5
        # unlit: top (X), left (Y), bottom (B) — quiet, but clearly four buttons
        for px, py in ((cx, cy - d), (cx - d, cy), (cx, cy + d)):
            self.circle(px, py, r, dim, 0.9)
        # lit right (A): soft halo then solid fill
        self.circle(cx + d, cy, r_lit * 1.75, lit, 0.28)
        self.circle(cx + d, cy, r_lit, lit, 1.0)
        gap = size * 0.26
        lx = cx + d + r_lit + gap
        # letter_fs is already in px; draw vertically centered on the cluster
        tw = self.measure(letter, 800, letter_fs)
        self.text(letter, lx, cy - letter_fs * 0.55, 800, letter_fs, lit, lineh=letter_fs * 1.1)
        return self.abxy_diamond_width(size, letter, letter_fs)

    def icon(self, name, x, y, size, color, alpha=1.0, sw=2):
        s = int(round(size))
        body = STAR if name == 'star' else ICONS[name]
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="%g" '
               'stroke-linecap="round" stroke-linejoin="round">%s</svg>' % (s, s, sw, body))
        self._blit(self.svg_tex(('ico', name, sw), svg, s, s), x, y, s, s, color, alpha)

    def mark(self, x, y, w, h, color, alpha=1.0, parts=None):
        w, h = int(round(w)), int(round(h))
        if parts is None:
            svg = '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 360 320" fill="#fff">%s</svg>' % (w, h, MARK)
            self._blit(self.svg_tex('mark', svg, w, h), x, y, w, h, color, alpha)
        else:  # draw each slab separately: parts = [(dx, alpha), ...]
            for i, (dx, a) in enumerate(parts):
                svg = '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 360 320" fill="#fff">%s/></svg>' % (w, h, MARK_PARTS[i])
                self._blit(self.svg_tex(('mark', i), svg, w, h), x + dx, y, w, h, color, alpha * a)

    def bars(self, x, y, n, color):
        # 18x14 signal bars
        for i in range(3):
            self.rrect(x + i * 6, y + 10 - i * 5, 4, 4 + i * 5, 1, color, 1 if i < n else .25)

    def hue_bar(self, x, y, w, h, alpha=1.0):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><defs><linearGradient id="g">'
               '<stop offset="0" stop-color="#ff3d3d"/><stop offset=".1667" stop-color="#ffff3d"/><stop offset=".3333" stop-color="#3dff3d"/>'
               '<stop offset=".5" stop-color="#3dffff"/><stop offset=".6667" stop-color="#6666ff"/><stop offset=".8333" stop-color="#ff3dff"/>'
               '<stop offset="1" stop-color="#ff3d42"/></linearGradient></defs><rect width="%d" height="%d" rx="%g" fill="url(#g)"/></svg>' % (w, h, w, h, h / 2.0))
        t = self.svg_tex('hue', svg, int(w), int(h))
        if t:
            sdl.SetTextureColorMod(t, 255, 255, 255)
            sdl.SetTextureAlphaMod(t, int(255 * alpha * self.alpha))
            sdl.RenderCopyF(self.r, t, None, C.byref(sdl.FRect(x + self.ox, y, w, h)))

    # ---------- plain fills / gradients ----------
    def fill(self, x, y, w, h, color, alpha=1.0):
        r, g, b = hx(color)
        sdl.SetRenderDrawBlendMode(self.r, sdl.BLENDMODE_BLEND)
        sdl.SetRenderDrawColor(self.r, r, g, b, int(255 * max(0, min(1, alpha * self.alpha))))
        sdl.RenderFillRectF(self.r, C.byref(sdl.FRect(x + self.ox, y, w, h)))

    def vgrad(self, x, y, w, h, color, a0, a1, horiz=False):
        r, g, b = hx(color)
        A0, A1 = int(255 * a0 * self.alpha), int(255 * a1 * self.alpha)
        x += self.ox
        V = sdl.Vertex * 4
        c0, c1 = sdl.Color(r, g, b, A0), sdl.Color(r, g, b, A1)
        if horiz:
            v = V(sdl.Vertex(sdl.FPoint(x, y), c0, sdl.FPoint(0, 0)), sdl.Vertex(sdl.FPoint(x + w, y), c1, sdl.FPoint(0, 0)),
                  sdl.Vertex(sdl.FPoint(x + w, y + h), c1, sdl.FPoint(0, 0)), sdl.Vertex(sdl.FPoint(x, y + h), c0, sdl.FPoint(0, 0)))
        else:
            v = V(sdl.Vertex(sdl.FPoint(x, y), c0, sdl.FPoint(0, 0)), sdl.Vertex(sdl.FPoint(x + w, y), c0, sdl.FPoint(0, 0)),
                  sdl.Vertex(sdl.FPoint(x + w, y + h), c1, sdl.FPoint(0, 0)), sdl.Vertex(sdl.FPoint(x, y + h), c1, sdl.FPoint(0, 0)))
        idx = (C.c_int * 6)(0, 1, 2, 0, 2, 3)
        sdl.RenderGeometry(self.r, None, v, 4, idx, 6)

    def glow(self, alpha=0.035):
        """CSS radial-gradient(120% 90% at 50% 0%, rgba(255,255,255,.035), transparent 60%)."""
        W, H = self.W, self.H
        rx, ry, cx, cy, n = 0.72 * W, 0.54 * H, W / 2.0, 0.0, 40
        import math
        verts = (sdl.Vertex * (n + 2))()
        verts[0] = sdl.Vertex(sdl.FPoint(cx, cy), sdl.Color(255, 255, 255, int(255 * alpha)), sdl.FPoint(0, 0))
        for k in range(n + 1):
            a = math.pi * k / n
            verts[k + 1] = sdl.Vertex(sdl.FPoint(cx + rx * math.cos(a), cy + ry * math.sin(a)), sdl.Color(255, 255, 255, 0), sdl.FPoint(0, 0))
        idx = (C.c_int * (n * 3))(*[v for k in range(n) for v in (0, k + 1, k + 2)])
        sdl.RenderGeometry(self.r, None, verts, n + 2, idx, n * 3)

    def clip(self, x=None, y=None, w=None, h=None):
        if x is None:
            sdl.RenderSetClipRect(self.r, None)
        else:
            sdl.RenderSetClipRect(self.r, C.byref(sdl.Rect(int(x + self.ox), int(y), int(w), int(h))))

    def image(self, path):
        k = ('img', path, os.path.getmtime(path) if os.path.exists(path) else 0)
        t = self.scache.get(k)
        if t is None:
            s = sdl.IMG_Load(path.encode())
            if not s:
                return None
            t = sdl.CreateTextureFromSurface(self.r, s); sdl.FreeSurface(s)
            self.scache[k] = t
        return t

    def blit_image(self, tex, x, y, w, h):
        sdl.SetTextureAlphaMod(tex, int(255 * self.alpha))
        sdl.RenderCopyF(self.r, tex, None, C.byref(sdl.FRect(x, y, w, h)))
