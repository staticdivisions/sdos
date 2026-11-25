# The Static Divisions handheld frontend: setup wizard, systems, games, in-game menu, settings, Look.
# Text only.
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
import os, time, math
from . import look as LK
from .device import TZS, SETUP_FOLDERS, VERSION, TOOLS, MODELS, MODEL_AUTO, FAMILY, model_of, model_name, SETUP_STEPS, setup_model_rows
from . import music as MU
from . import btnswap

LANGS = [('English', True), ('Español', False), ('Français', False), ('Deutsch', False), ('Italiano', False), ('Português', False), ('日本語', False)]
SLEEP = [('1 min', 60), ('3 min', 180), ('5 min', 300), ('10 min', 600), ('Never', 0)]
# On-screen keyboard: letters page and a symbols page; together every printable ASCII character.
KB_ABC = [list('1234567890'), list('qwertyuiop'), list('asdfghjkl'), list('zxcvbnm')]
KB_SYM = [list('!@#$%^&*()'), list('-_=+[]{};:'), list('\'",.<>/?\\|'), list('`~.@_-!?')]
KB_BOTTOM = ['Shift', '#+=', 'Space', 'Del', 'Join']
KB_W = {'Space': 2.4}
KB = KB_ABC + [KB_BOTTOM]
ROWH = {1: 56, 2: 42, 3: 46}
TOP_H = {1: 44, 2: 34, 3: 34}
HINT_H = {1: 40, 2: 30, 3: 34}
OVL = ['Resume', 'Save state', 'Load state', 'Emulator settings', 'Settings', 'Quit game']
OVL_TOOL = ['Resume', 'Quit']

def ease(t):  # cubic-bezier(.2,.7,.2,1)-ish
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3

def clamp(v, a, b): return max(a, min(b, v))


class App:
    def __init__(self, gfx, dev, shot=False):
        self.g = gfx; self.dev = dev; self.shot = shot
        self.t_boot = time.time()
        self.W, self.H = gfx.W, gfx.H
        st = dev.load_state() if not shot else {}
        if not isinstance(st, dict): st = {}
        self.look = LK.clean(st.get('look'))
        self.slots = [LK.clean(x) if x else None for x in (st.get('slots') or [None, None, None])][:3]
        while len(self.slots) < 3: self.slots.append(None)
        self.setup_done = bool(st.get('setupDone'))
        self.setup_model_done = bool(st.get('setupModelDone'))
        self.model_prompted = bool(st.get('modelPrompted'))
        self.mtrial_prefer_keep = bool(st.get('mtrialPreferKeep'))
        self.setup_resume = st.get('setupResume') or ''
        self.confirm_back = None
        self.favs = set(st.get('favs') or [])
        self.recents = list(st.get('recents') or [])
        self.h24 = bool(st.get('h24'))
        self.sleep = int(st.get('sleep', 2))
        self.swap_ab = bool(st.get('swap_ab'))
        self.swap_xy = bool(st.get('swap_xy'))
        self.tz = st.get('tz') or ('America/Los_Angeles' if dev.mock else None)
        self.screen = 'boot'; self.dir = ''; self.t_enter = 0
        self.sel = {}; self.ctx = 'setup' if not self.setup_done else 'home'
        self.sys = None; self.systems = []
        self.pw_for = None; self.pw = ''; self.kb = [1, 0]; self.shift = 0; self.pw_cur = 0; self.kb_sym = False; self.pw_show = False; self.pw_last = -1
        self.time_auto = True; self.man_off = 0
        self.card = 1; self.copy_path = ''
        self.ovl = False; self.game = None; self.saved = False; self._pending_launch = None; self._pending_until = 0
        self.upd = 'idle'; self.upd_msg = ''
        self.about_y = 0; self.jump = None; self.toast_ = None
        self.connecting = False; self.anim = {}; self.last_input = time.time()
        self.bright = dev.get_bright(); self.vol = dev.get_vol()
        self.dirty = True; self.ret = 'home'
        self.player = None; self.confirm = None; self.powering = None; self._wifi_auto = [0, 0.0]
        self._wifi_user_connect = False
        self.apply_look()
        self.apply_btn_swap(persist=False)
        if self.tz and not dev.mock:
            os.environ['TZ'] = self.tz; time.tzset()
        if dev.mock:
            os.environ['TZ'] = self.tz; time.tzset()
        self.rescan()
        if dev.mock and not st:   # demo favorites / recents for desktop screenshots
            sg = lambda sid: self.sys_by(sid)['games']
            self.favs = {sg('gba')[3]['path'], sg('psp')[1]['path']}
            self.recents = [sg('psp')[2], sg('gba')[5], sg('snes')[1]]

    # ---------- state ----------
    def persist(self):
        if self.shot: return
        self.dev.state.update(look=self.look, slots=self.slots, setupDone=self.setup_done, favs=sorted(self.favs),
                              recents=self.recents[:10], h24=self.h24, sleep=self.sleep, tz=self.tz,
                              swap_ab=self.swap_ab, swap_xy=self.swap_xy,
                              setupModelDone=self.setup_model_done, modelPrompted=self.model_prompted,
                              mtrialPreferKeep=self.mtrial_prefer_keep, setupResume=self.setup_resume)
        self.dev.save_state()

    def apply_look(self):
        self.c = LK.colors(self.look); self.opt = LK.opt_of(self.look['layout']); self.fz = LK.fz(self.look)
        self.dirty = True

    def apply_btn_swap(self, persist=True):
        """Push the two Settings toggles into the pad map, emulator configs, and state."""
        btnswap.set_flags(self.swap_ab, self.swap_xy)
        if persist:
            self.persist()
        if self.shot:
            return
        if self.dev.mock and not os.environ.get('SDUI_SWAP_ROOT'):
            return
        try:
            btnswap.apply(self.swap_ab, self.swap_xy)
        except Exception as e:
            try:
                from .device import log
                log('btn swap apply failed: %r' % (e,))
            except Exception:
                pass

    def set_btn_swap(self, which, on):
        if which == 'ab':
            self.swap_ab = bool(on)
        else:
            self.swap_xy = bool(on)
        self.apply_btn_swap()
        self.dirty = True

    def set_look(self, L):
        self.look = LK.clean(L); self.apply_look(); self.persist()

    def rescan(self):
        self.systems = self.dev.scan()
        paths = {g['path'] for s in self.systems for g in s['games']}
        self.recents = [r for r in self.recents if r.get('path') in paths] if not self.dev.mock else self.recents
        self.favs = {f for f in self.favs if f in paths} if not self.dev.mock else self.favs

    def sys_by(self, sid):
        return next((s for s in self.systems if s['id'] == sid), None)

    def toast(self, text):
        self.toast_ = (text, time.time()); self.dirty = True

    def go(self, name, back=False):
        self.screen = name; self.dir = 'back' if back else ''; self.t_enter = time.time(); self.jump = None
        self.anim = {}; self.dirty = True

    def now(self):
        return self.dev.now() + self.man_off * 60

    def fmt_time(self, t=None):
        lt = time.localtime(self.now() if t is None else t)
        if self.h24: return time.strftime('%H:%M', lt)
        return time.strftime('%I:%M %p', lt).lstrip('0')

    def time_parts(self):
        s = self.fmt_time(); p = s.split(' ')
        return (p[0], p[1] if len(p) > 1 else '')

    def fmt_date(self):
        return time.strftime('%A, %B ', time.localtime(self.now())) + str(time.localtime(self.now()).tm_mday)

    def s(self, key, n=None):
        v = self.sel.get(key, 0)
        return clamp(v, 0, max(0, n - 1)) if n else v

    def setup_cues(self):
        """Face-button diamond on first-boot setup screens (and the one-time H? / device pick)."""
        if self.screen == 'kb':
            return False
        return self.ctx == 'setup' or self.screen in ('devpick', 'hask')

    def setup_start_confirms(self):
        """Start should confirm the highlighted setup action. Leave the OSK alone: Start already means Join there."""
        return self.setup_cues()

    def cue_metrics(self):
        o = self.opt
        size = 28 if o == 1 else (20 if o == 2 else 24)
        fs = 14 if o == 1 else (11 if o == 2 else 13)
        return size, fs

    def cue_width(self):
        size, fs = self.cue_metrics()
        return self.g.abxy_diamond_width(size, 'A', fs)

    def draw_cue(self, x, y, h, letter='A'):
        """Diamond + letter, vertically centered in a row. x is the left of the cluster."""
        g, c = self.g, self.c
        size, fs = self.cue_metrics()
        yy = y + (h - size) / 2.0
        return g.abxy_diamond(x, yy, size, c['ac'], c['dim'], letter, letter_fs=fs)

    def draw_cta(self, x, y, w, h, label='Continue'):
        """Focused primary action pill with the lit A diamond inside it."""
        g, c, o, fz = self.g, self.c, self.opt, self.fz
        if o == 1:
            g.rrect(x, y, w, h, 14, c['ac'], c['acbg_a'])
            g.clip(x, y, 3, h)
            g.rrect(x, y, w, h, 14, c['ac'])
            g.clip()
            fs, wt = 24 * fz, 700
        elif o == 2:
            g.rrect(x, y, 4, h, 0, c['ac'], radii=(0, 2, 2, 0))
            fs, wt = 19 * fz, 700
        else:
            g.fill(x, y, 3, h, c['ac'])
            fs, wt = 30 * fz, 800
        pad = {1: 28, 2: 24, 3: 22}[o]
        g.text(label, x + pad, y, wt, fs, c['fg'] if o != 2 else c['ac'], lineh=h)
        cw = self.cue_width()
        self.draw_cue(x + w - pad - cw, y, h)

    # ---------- drawing primitives that depend on the look ----------
    @property
    def wifi(self):
        return self.dev.wifi_status

    def topbar(self, title, x0=0, w=None):
        g, c, o = self.g, self.c, self.opt
        w = self.W if w is None else w
        h = TOP_H[o]
        pad = 22 if o == 1 else 24
        fs = {1: 17, 2: 12, 3: 14}[o]
        # left: title
        x = x0 + pad
        lhb = h
        if o == 3:
            g.text((title or 'Static Divisions').upper(), x, 0, 700, 12, c['dim'], track=.24, lineh=lhb)
        else:
            mw, mh = (22, 20) if o == 1 else (16, 14)
            g.mark(x, (h - mh) / 2, mw, mh, c['ac'])
            x += mw + 10
            if title:
                if o == 2: g.text(title.upper(), x, 0, 800, fs, c['fg'], track=.16, lineh=lhb)
                else: g.text(title, x, 0, 700, fs, c['fg'], lineh=lhb)
        # right: wifi, battery, clock (drawn right to left)
        rx = x0 + w - pad
        wt = 700 if o == 2 else 600
        tr = .16 if o == 2 else 0
        if self.look['clock']:
            s = self.fmt_time(); tw = g.measure(s, wt, fs, tr); rx -= tw
            g.text(s, rx, 0, wt, fs, c['fg'], track=tr, lineh=lhb); rx -= 14
        if self.look['batt']:
            cap, chg = self.dev.battery()
            s = ('%d%%' % cap) if cap is not None else '–'
            tw = g.measure(s, wt, fs, tr); rx -= tw
            g.text(s, rx, 0, wt, fs, c['dim'], track=tr, lineh=lhb)
            if o != 2:
                rx -= 6 + 26 + 3
                by = (h - 13) / 2
                g.ring(rx, by, 26, 13, 3, c['dim'], sw=2)
                g.rrect(rx + 26 + 1, by + 4, 2, 5, 1, c['dim'])
                if cap is not None:
                    g.rrect(rx + 3, by + 3, max(1, 20 * cap / 100.0), 7, 1, c['fg'])
            rx -= 14
        if self.wifi:
            if o == 2:
                tw = g.measure('WI-FI', wt, fs, tr); rx -= tw
                g.text('WI-FI', rx, 0, wt, fs, c['dim'], track=tr, lineh=lhb); rx -= 6
            rx -= 20
            g.icon('wifi', rx, (h - 20) / 2, 20, c['dim'])
        if o == 2:
            g.fill(x0, h - 1, w, 1, c['faint'])
        return h

    def header_h(self, h1, sub, step):
        o, fz = self.opt, self.fz
        if o == 2:
            h = 14 + 12 * 1.1 + (6 + 22 * fz * 1.366 if sub else 0) + (12 if step else 0) + 8
        elif o == 3:
            h = 6 + 26 * fz * 1.1 + (4 + 16 * fz * 1.366 if sub else 0) + (14 if step else 0) + 6
        else:
            h = 6 + 30 * fz * 1.1 + (4 + 16 * fz * 1.366 if sub else 0) + (14 if step else 0) + 10
        return int(round(h))

    def header(self, h1, sub, step, y, x0=0, w=None):
        g, c, o, fz = self.g, self.c, self.opt, self.fz
        w = self.W if w is None else w
        if o == 2:
            px = 24; yy = y + 14
            g.text(h1.upper(), x0 + px, yy, 800, 12, c['ac'], track=.22, lineh=12 * 1.1); yy += 12 * 1.1
            if sub:
                yy += 6; g.text(sub, x0 + px, yy, 600, 22 * fz, c['fg'], maxw=w - 2 * px); yy += 22 * fz * 1.366
            if step:
                yy += 10; sw = (w - 2 * px - (SETUP_STEPS - 1) * 6) / float(SETUP_STEPS)
                for i in range(SETUP_STEPS):
                    g.fill(x0 + px + i * (sw + 6), yy, sw, 2, c['ac'] if i < step else c['faint'])
        else:
            px = 26 if o == 3 else 28; yy = y + 6
            hs = (26 if o == 3 else 30) * fz
            g.text(h1, x0 + px, yy, 800, hs, c['fg'], lineh=hs * 1.1, maxw=w - 2 * px); yy += hs * 1.1
            if sub:
                yy += 4; g.text(sub, x0 + px, yy, 500, 16 * fz, c['dim'], maxw=w - 2 * px); yy += 16 * fz * 1.366
            if step:
                yy += 10
                for i in range(SETUP_STEPS):
                    g.rrect(x0 + px + i * 28, yy, 22, 4, 2, c['ac'] if i < step else c['faint'])
        return self.header_h(h1, sub, step)

    def kbd(self, x, y, label, o):
        """Hint key cap. Returns width."""
        g, c = self.g, self.c
        hh = 18 if o == 2 else 22
        icon = {'☰': 'menu', '◂▸': 'lr', '▲▼': 'ud'}.get(label)
        fsz = 10 if o == 2 else 12
        cw = 12 if icon else g.measure(label, 800, fsz)
        w = max(hh, cw + 12)
        g.rrect(x, y, w, hh, 4 if o == 2 else hh / 2.0, c['faint'])
        if icon:
            g.icon(icon, x + (w - 12) / 2.0, y + (hh - 12) / 2.0, 12, c['fg'], sw=2.6)
        else:
            g.text(label, x + (w - cw) / 2.0, y, 800, fsz, c['fg'], lineh=hh)
        return w

    def hints(self, items, x0=0, w=None):
        g, c, o = self.g, self.c, self.opt
        w = self.W if w is None else w
        h = HINT_H[o]; y = self.H - h
        if o == 2: g.fill(x0, y, w, 1, c['faint'])
        fs = {1: 14, 2: 11, 3: 13}[o]; tr = .14 if o == 2 else 0
        kh = 18 if o == 2 else 22
        def width(it):
            lab = it[1].upper() if o == 2 else it[1]
            icon = it[0] in ('☰', '◂▸', '▲▼')
            cw = 12 if icon else g.measure(it[0], 800, 10 if o == 2 else 12)
            return max(kh, cw + 12) + 7 + g.measure(lab, 600, fs, tr)
        lx = x0 + 24; rx = x0 + w - 24
        for it in [i for i in items if len(i) > 2 and i[2] == 'l']:
            self._hint(it, lx, y, h, fs, tr, kh, o); lx += width(it) + 20
        for it in reversed([i for i in items if not (len(i) > 2 and i[2] == 'l')]):
            rx -= width(it); self._hint(it, rx, y, h, fs, tr, kh, o); rx -= 20
        return h

    def _hint(self, it, x, y, h, fs, tr, kh, o):
        kw = self.kbd(x, y + (h - kh) / 2.0, it[0], o)
        lab = it[1].upper() if o == 2 else it[1]
        self.g.text(lab, x + kw + 7, y, 600, fs, self.c['dim'], track=tr, lineh=h)

    # rt segments: ('t',s) ('ico',name) ('bars',n) ('bar',v,max) ('arrows',s) ('sw',hex) ('hue',deg,on) ('chev',)
    def seg_w(self, seg, fs, wt):
        g, k = self.g, seg[0]
        if k == 't': return g.measure(seg[1], wt, fs)
        if k == 'arrows': return g.measure('‹', wt, fs) + g.measure(seg[1], wt, fs) + g.measure('›', wt, fs) + 16
        if k in ('ico', 'chev'): return 16
        if k == 'bars': return 18
        if k == 'bar': return 120
        if k == 'sw': return 16
        if k == 'hue': return 120 + 8 + max(38, g.measure(seg[2] and ('%d°' % round(seg[1])) or 'Off', wt, fs))
        return 0

    def draw_rt(self, segs, rx, y, rh, fs, wt, col, selcol):
        g, c = self.g, self.c
        x = rx
        for seg in reversed(segs):
            sw = self.seg_w(seg, fs, wt); x -= sw
            k = seg[0]; cy = y + rh / 2.0
            if k == 't':
                g.text(seg[1], x, y, wt, fs, col, lineh=rh)
            elif k == 'arrows':
                ac = selcol if selcol else c['dim']
                a = g.measure('‹', wt, fs)
                g.text('‹', x + 4, y, wt, fs, ac, lineh=rh)
                g.text(seg[1], x + a + 8, y, wt, fs, col, lineh=rh)
                g.text('›', x + a + 8 + g.measure(seg[1], wt, fs) + 4, y, wt, fs, ac, lineh=rh)
            elif k == 'chev':
                g.icon('chev', x, cy - 8, 16, col)
            elif k == 'ico':
                g.icon(seg[1], x, cy - 8, 16, col)
            elif k == 'bars':
                g.bars(x, cy - 7, seg[1], col)
            elif k == 'bar':
                g.rrect(x, cy - 3, 120, 6, 3, c['faint'])
                g.rrect(x, cy - 3, 120 * seg[1] / float(seg[2]), 6, 3, c['ac'])
            elif k == 'sw':
                g.circle(x + 8, cy, 10, c['faint']); g.circle(x + 8, cy, 8, seg[1])
            elif k == 'hue':
                on = seg[2]
                g.hue_bar(x, cy - 5, 120, 10, 1 if on else .45)
                kx = x + 120 * seg[1] / 359.0
                g.circle(kx, cy, 11, c['bg'], 1 if on else .45); g.circle(kx, cy, 8, c['fg'], 1 if on else .45)
                t = ('%d°' % round(seg[1])) if on else 'Off'
                tw = g.measure(t, wt, fs)
                g.text(t, x + sw - tw, y, wt, fs, col, lineh=rh)
            x -= 8

    def _lerp(self, key, target):
        if self.shot or key not in self.anim:
            self.anim[key] = [target, time.time()]; return target
        cur, t0 = self.anim[key]; now = time.time(); dt = now - t0
        nv = target + (cur - target) * math.exp(-dt / 0.055)
        if abs(nv - target) < 0.5: nv = target
        else: self.dirty = True
        self.anim[key] = [nv, now]
        return nv

    def list_view(self, key, items, x, y, w, h, empty='Nothing here yet'):
        g, c, o, fz = self.g, self.c, self.opt, self.fz
        n = len(items)
        if not n:
            g.text(empty, x + (w - g.measure(empty, 500, 18)) / 2.0, y + h / 2.0 - 12, 500, 18, c['dim'])
            return
        s = self.s(key, n); rh = int(round(ROWH[o] * fz))
        hl_pad = 4 if o == 1 else 0
        off, vis = 0, n
        if o == 3:
            ty = round(h / 2.0 - rh / 2.0 - s * rh)
        else:
            vis = max(1, int((h - 4) // rh)); off = 0 if n <= vis else clamp(s - (vis - 1) // 2, 0, n - vis); ty = 2 - off * rh
        ty = self._lerp(key + ':ty', ty)
        hly = self._lerp(key + ':hl', s * rh + hl_pad)
        g.clip(x, y, w, h)
        # highlight
        if o == 1:
            hx0, hw, hh = x + 14, w - 28, rh - hl_pad * 2
            g.rrect(hx0, y + ty + hly, hw, hh, 14, c['ac'], c['acbg_a'])
            g.clip(x, y, w, h)
            g.clip(hx0, max(y, y + ty + hly), 3, hh)
            g.rrect(hx0, y + ty + hly, hw, hh, 14, c['ac'])
            g.clip(x, y, w, h)
        elif o == 2:
            g.rrect(x, y + ty + hly, 4, rh, 0, c['ac'], radii=(0, 2, 2, 0))
        else:
            g.fill(x, y + ty + hly, 3, rh, c['ac'])
        pad = {1: 28, 2: 24, 3: 22}[o]
        for i, it in enumerate(items):
            ry = y + ty + i * rh
            if ry > y + h or ry + rh < y: continue
            alpha = 1.0
            if o == 3:
                if abs(i - s) >= 3: alpha = .45
            elif i < off or i >= off + vis:
                continue
            sel = i == s
            if o == 1:
                fs, wt, col = 24 * fz, 700, c['fg']; rfs, rwt, rcol = 19 * fz, 600, (c['fg'] if sel else c['dim'])
            elif o == 2:
                fs, wt, col = 19 * fz, (700 if sel else 500), (c['ac'] if sel else c['fg']); rfs, rwt, rcol = 15 * fz, 600, (c['ac'] if sel else c['dim'])
                g.fill(x + 24, ry + rh - 1, w - 48, 1, c['faint'], alpha)
            else:
                fs, wt, col = (30 * fz, 800, c['fg']) if sel else (20 * fz, 600, c['dim']); rfs, rwt, rcol = (18 * fz if sel else 15 * fz), 600, (c['ac'] if sel else c['dim'])
            g.alpha = alpha
            lx = x + pad
            show_cue = self.setup_cues() and sel and not it.get('off') and not it.get('info')
            rt = list(it.get('rt') or [])
            if show_cue:
                rt = [sg for sg in rt if sg[0] != 'chev']
            rtw = sum(self.seg_w(sg, rfs, rwt) for sg in rt) + 8 * max(0, len(rt) - 1)
            cue_w = (self.cue_width() + 10) if self.setup_cues() else 0
            if 'lead' in it:
                if it['lead']: g.icon('star', lx + 1, ry + rh / 2.0 - 8, 16, c['ac'])
                lx += 18 + 12
            maxw = x + w - pad - lx - (rtw + 12 if rt else 0) - cue_w
            lcol = it.get('col', col)
            g.text(it['label'], lx, ry, wt, fs, c['dim'] if it.get('off') else lcol, lineh=rh, maxw=maxw)
            rx = x + w - pad - cue_w
            if rt:
                self.draw_rt(rt, rx, ry, rh, rfs, rwt, rcol, c['ac'] if sel else None)
            if show_cue:
                self.draw_cue(x + w - pad - self.cue_width(), ry, rh)
            if it.get('sep'):
                g.fill(x + 28, ry + rh - 1, w - 56, 1, c['faint'])
            g.alpha = 1.0
        if o == 3:  # soft fade at top and bottom
            fh = h * .22
            g.vgrad(x, y, w, fh, c['bg'], 1, 0); g.vgrad(x, y + h - fh, w, fh, c['bg'], 0, 1)
        g.clip()

    def aside(self, a, x, y, w, h):
        """o3 big-type column, content centered vertically."""
        g, c = self.g, self.c
        parts = []
        if a.get('cap'): parts.append(('cap', 12 * 1.366 + 6))
        bs = 46 if a.get('sm') else 96
        parts.append(('big', bs * (1.05 if a.get('sm') else .95)))
        if a.get('sub'): parts.append(('sub', 8 + 17 * 1.3))
        if a.get('step'): parts.append(('step', 14))
        if a.get('preview'): parts.append(('pv', 14 + self.lookpv_h()))
        tot = sum(p[1] for p in parts)
        yy = y + 6 + (h - 6 - tot) / 2.0
        px = x + 26
        g.clip(x, y, w, h)
        for k, ph in parts:
            if k == 'cap':
                g.text(a['cap'].upper(), px, yy, 700, 12, c['dim'], track=.24); yy += ph
            elif k == 'big':
                lh = bs * (1.05 if a.get('sm') else .95)
                big = str(a['big'])
                tr = -.02 if a.get('sm') else -.04
                cx = px
                for ch in big:  # negative tracking
                    cx += g.text(ch, cx, yy, 800, bs, c['ac'], lineh=lh) + tr * bs
                yy += ph
            elif k == 'sub':
                g.text(a['sub'], px, yy + 8, 600, 17, c['fg'], lineh=17 * 1.3, maxw=w - 26 - 12); yy += ph
            elif k == 'step':
                for i in range(SETUP_STEPS): g.rrect(px + i * 28, yy + 10, 22, 4, 2, c['ac'] if i < a['step'] else c['faint'])
                yy += ph
            elif k == 'pv':
                self.lookpv(px, yy + 14, w - 26 - 22); yy += ph
        g.clip()

    def frame(self, title, h1=None, sub=None, step=0, aside=None, body=None, hint=None, wide=False):
        """Standard layout. body(x, y, w, h) draws the list area."""
        g, c, o = self.g, self.c, self.opt
        th = self.topbar(title)
        hh = HINT_H[o] if hint else 0
        if o == 3 and aside and not wide:
            aw = round(self.W * .38)
            self.aside(aside, 0, th, aw, self.H - th - hh)
            g.fill(aw, th, 1, self.H - th - hh, c['faint'])
            body(aw + 1, th, self.W - aw - 1, self.H - th - hh)
        else:
            y = th
            if h1 is not None: y += self.header(h1, sub, step, th)
            body(0, y, self.W, self.H - y - hh)
        if hint: self.hints(hint)

    # ---------- look preview box ----------
    def lookpv_h(self):
        fz = self.fz
        return 6 + 10 * 1.366 + 4 + 3 * (12 * fz * 1.366 + 6) + 6

    def lookpv(self, x, y, w):
        g, c, o, fz = self.g, self.c, self.opt, self.fz
        h = self.lookpv_h()
        g.rrect(x, y, w, h, 3 if o == 2 else 10, c['fg'], .03)
        g.ring(x, y, w, h, 3 if o == 2 else 10, c['faint'], sw=1)
        g.mark(x + 10, y + 6 + (13.66 - 11) / 2, 12, 11, c['ac'])
        stt = ' · '.join([s for s in [self.fmt_time() if self.look['clock'] else '', (lambda b: ('%d%%' % b) if b is not None else '')(self.dev.battery()[0]) if self.look['batt'] else ''] if s])
        g.text(stt, x + w - 10 - g.measure(stt, 700, 10), y + 6, 700, 10, c['dim'])
        yy = y + 6 + 13.66 + 4
        rows = [('Game Boy', '9'), ('Game Boy Advance', '14'), ('NES', '12')]
        rh = 12 * fz * 1.366 + 6
        for i, (a, b) in enumerate(rows):
            on = i == 1
            fs, wt, col, bcol = 12 * fz, 600, c['fg'], c['dim']
            lx = x + 12
            if o == 1 and on:
                g.rrect(x + 4, yy, w - 8, rh, 6, c['ac'], c['acbg_a']); g.fill(x + 4, yy + 2, 2, rh - 4, c['ac']); lx = x + 12
            elif o == 2:
                wt = 700 if on else 500
                if on: col = bcol = c['ac']; g.fill(x, yy, 2, rh, c['ac'])
                g.fill(x, yy + rh - 1, w, 1, c['faint']); lx = x + 10
            elif o == 3:
                col = c['fg'] if on else c['dim']
                if on: fs, wt, bcol = 15 * fz, 800, c['ac']; g.fill(x, yy, 2, rh, c['ac'])
            g.text(a, lx, yy, wt, fs, col, lineh=rh)
            g.text(b, x + w - 10 - g.measure(b, 600, 12 * fz), yy, 600, 12 * fz, bcol, lineh=rh)
            yy += rh

    # ---------- render ----------
    def render(self):
        g, c = self.g, self.c
        g.alpha = 1.0; g.ox = 0
        g.fill(0, 0, self.W, self.H, c['bg'])
        dt = time.time() - self.t_enter
        if not self.shot and dt < .22 and self.screen != 'boot':
            e = ease(dt / .22); g.alpha = e; g.ox = (1 - e) * (-14 if self.dir == 'back' else 14); self.dirty = True
        getattr(self, 'draw_' + self.screen)()
        g.alpha = 1.0; g.ox = 0
        if (self.screen not in ('game',) or self.ovl) and c.get('glow'):
            g.glow(c['glow'])
        self.draw_toast()

    def draw_toast(self):
        if not self.toast_: return
        g, c = self.g, self.c
        text, t0 = self.toast_; dt = time.time() - t0
        if dt > 1.9: self.toast_ = None; return
        a = ease(dt / .2) if dt < .2 else (1 - ease((dt - 1.7) / .2) if dt > 1.7 else 1)
        if not self.shot: self.dirty = True
        else: a = 1
        tw = g.measure(text, 700, 19); w, h = tw + 36, 19 * 1.366 + 18
        x, y = (self.W - w) / 2.0, self.H - 56 - h + (1 - a) * 10
        g.rrect(x, y, w, h, 22, c['fg'], a)
        g.text(text, x + 18, y + 9, 700, 19, c['bg'], a)

    # ---------- screens ----------
    def draw_boot(self):
        g, c = self.g, self.c
        t = 9 if self.shot else time.time() - self.t_enter
        mw, mh = 180, 160          # mark viewBox 360x320; ~180px wide on 640x480
        nfs, sfs, ufs = 51, 19, 18 # sdOS 1.5x, wordmark 19, URL 18
        tot = mh + 22 + nfs * 1.15 + 12 + sfs * 1.366 + 10 + ufs * 1.366 + 22 + 2
        y0 = (self.H - tot) / 2.0
        parts = []
        for i, d in enumerate((.1, .2, .3)):
            k = clamp((t - d) / .9, 0, 1); sgn = 1 if i == 1 else -1   # slabs 1 and 3 enter from the left, 2 from the right
            if k < .6:
                e = ease(k / .6); dx = 40 * sgn * (1 - e) + (-6 * sgn) * e; a = e
            else:
                e = ease((k - .6) / .4); dx = -6 * sgn * (1 - e); a = 1
            parts.append((dx, a))
        g.mark((self.W - mw) / 2.0, y0, mw, mh, c['ac'], parts=parts)
        y = y0 + mh + 22
        a = clamp((t - .7) / .6, 0, 1)
        # product name: "sd" bold + "OS" light accent, then the maker small underneath
        w1 = g.measure('sd', 800, nfs, -.02); w2 = g.measure('OS', 300, nfs, -.02)
        x = (self.W - (w1 + w2)) / 2.0
        g.text('sd', x, y - nfs * .108, 800, nfs, c['fg'], a, track=-.02, lineh=nfs * 1.366)
        g.text('OS', x + w1, y - nfs * .108, 300, nfs, c['ac'], a, track=-.02, lineh=nfs * 1.366)
        y += nfs * 1.15 + 12
        tr = .16
        sw = g.measure('STATIC DIVISIONS', 600, sfs, tr)
        g.text('STATIC DIVISIONS', (self.W - sw) / 2.0 + sfs * tr / 2, y, 600, sfs, c['dim'], a, track=tr)
        y += sfs * 1.366 + 10
        url = 'staticdivisions.com/sdos/'
        utr = .04
        uw = g.measure(url, 600, ufs, utr)
        g.text(url, (self.W - uw) / 2.0 + ufs * utr / 2, y, 600, ufs, c['ac'], a, track=utr)
        y += ufs * 1.366 + 22
        a2 = clamp((t - .9) / .4, 0, 1)
        g.rrect((self.W - mw) / 2.0, y, mw, 2, 1, c['faint'], a2)
        f = clamp((t - 1.0) / 1.3, 0, 1); f = f * f * (3 - 2 * f)
        if f > 0: g.fill((self.W - mw) / 2.0, y, mw * f, 2, c['ac'], a2)
        if not self.shot:
            self.dirty = True
            if t > 2.5: self.after_boot()

    def after_boot(self):
        # A pending model trial always wins: the confirm screen must appear
        # before we resume setup or home, and before the first-boot picker.
        tr = None if self.shot else self.dev.model_trial()
        if tr:
            self._mtrial_checked = True
            self.mtrial = tr
            self.mtrial_back = self.setup_resume or ('lang' if not self.setup_done else 'home')
            self.mtrial_deadline = time.time() + self.MTRIAL_SECS
            # First-boot / "is this an H?" picks default the cursor to Keep.
            # Settings-driven switches still start on Go back (blind-press safety).
            self.sel['mtrial'] = 0 if self.mtrial_prefer_keep else 1
            self.ctx = 'setup' if not self.setup_done else 'home'
            self.go('mtrial')
            return
        if not self.setup_done:
            self.ctx = 'setup'
            if MODEL_AUTO or self.setup_model_done or not setup_model_rows():
                self.go(self.setup_resume or 'lang')
            else:
                self.sel['devpick'] = self.setup_model_index()
                self.go('devpick')
            return
        if (not MODEL_AUTO) and (not self.model_prompted) and setup_model_rows() and self.dev.is_default_h_tree():
            self.sel['hask'] = 0
            self.go('hask')
            return
        self.ctx = 'home'
        self.go('home')

    def key_boot(self, k):
        if k == 'a': self.after_boot()

    # First-boot device picker (and the one-time "is this an H?" follow-on)
    def setup_model_index(self):
        rows = setup_model_rows()
        cur = self.dev.current_model()
        for i, (nm, std, alt, _st) in enumerate(rows):
            if cur == std or (alt and cur == alt):
                return i
        return 0

    def devpick_items(self):
        cur = self.dev.current_model()
        it = []
        for nm, std, alt, sticks in setup_model_rows():
            hint = 'Has joysticks' if sticks else 'No joysticks'
            mark = [('ico', 'check')] if (cur == std or (alt and cur == alt)) else []
            it.append({'label': nm, 'rt': [('t', hint)] + mark, 'pick': (std, nm)})
        return it

    def draw_devpick(self):
        it = self.devpick_items()
        self.frame('Setup', 'Which device is this?', 'Check the label on the back.', 1,
                   {'cap': 'Setup · 1 of 6', 'big': '01', 'sub': 'Your handheld'},
                   lambda x, y, w, h: self.list_view('devpick', it, x, y, w, h),
                   [['▲▼', 'Move'], ['A', 'Choose']])

    def key_devpick(self, k):
        it = self.devpick_items(); n = len(it)
        if not n:
            return self.go('lang' if not self.setup_done else 'home')
        if k == 'a':
            d, m = it[self.s('devpick', n)]['pick']
            if d == self.dev.current_model():
                self.setup_model_done = True
                self.model_prompted = True
                self.mtrial_prefer_keep = False
                self.setup_resume = ''
                self.persist()
                if self.setup_done:
                    self.ctx = 'home'; return self.go('home')
                self.ctx = 'setup'; return self.go('lang')
            self.mtrial_prefer_keep = True
            self.setup_resume = 'lang' if not self.setup_done else 'home'
            self.confirm_back = 'devpick'
            self.confirm = ('model', d, m)
            self.sel['confirm'] = 0
            self.persist()
            return self.go('confirm')
        if k in ('b', 'menu') and self.setup_done:
            return self.go('hask', True)
        self.nav('devpick', n, k)

    def draw_hask(self):
        it = [{'label': 'No, choose a different model'},
              {'label': 'Yes, this is an RG35XX H'}]
        self.frame('Setup', 'Is this an RG35XX H?',
                   'Check the label on the back. The RG35XX H has joysticks. The Plus does not.', 0,
                   {'cap': 'Check your handheld', 'big': 'H?', 'sm': True,
                    'sub': 'Check the label on the back'},
                   lambda x, y, w, h: self.list_view('hask', it, x, y, w, h),
                   [['▲▼', 'Move'], ['A', 'Choose']])

    def key_hask(self, k):
        if k == 'a':
            if self.s('hask', 2) == 1:
                self.model_prompted = True
                self.setup_model_done = True
                self.persist()
                self.ctx = 'home'
                return self.go('home')
            self.sel['devpick'] = self.setup_model_index()
            return self.go('devpick')
        self.nav('hask', 2, k)

    # Language
    def lang_items(self):
        cur = self.dev.state.get('lang', 0) if not self.shot else 0
        return [{'label': l, 'rt': [('ico', 'check')] if i == cur else ([] if ok else [('t', 'Later')]), 'off': not ok} for i, (l, ok) in enumerate(LANGS)]

    def draw_lang(self):
        it = self.lang_items()
        self.frame('Setup', 'Language', 'Welcome to sdOS. Choose a language for menus.', 2, {'cap': 'Setup · 2 of 6', 'big': '02', 'sub': 'Language'},
                   lambda x, y, w, h: self.list_view('lang', it, x, y, w, h), [['A', 'Select']])

    def key_lang(self, k):
        n = len(LANGS)
        if k == 'a':
            i = self.s('lang', n)
            if not LANGS[i][1]: return self.toast('English only in this first version')
            self.dev.state['lang'] = i
            if self.dev.wifi_present():
                self._wifi_auto = [0, time.time()]
                self._wifi_user_connect = False
                if self.wifi:
                    self.sel['wifi'] = 0
                else:
                    self.dev.wifi_scan()
                self.go('wifi')
            else:
                self.go('tz')
        else: self.nav('lang', n, k)

    # Wi-Fi
    def wifi_items(self):
        nets = self.dev.wifi_list()
        it = []
        if self.ctx == 'setup' and self.wifi:
            it.append({'label': 'Continue', 'rt': [], 'k': 'go', 'cta': True})
        if not nets and self.dev.busy.get('scan'):
            it.append({'label': 'Searching for networks…', 'rt': [], 'off': True, 'info': True})
        it += [{'label': n['ssid'], 'rt': ([('t', 'Connected')] if self.wifi == n['ssid'] else []) + ([('ico', 'lock')] if n['lock'] else []) + [('bars', n['sig'])], 'net': n} for n in nets]
        if self.ctx == 'setup':
            if not self.wifi:
                it.append({'label': 'Skip for now', 'rt': []})
        else:
            it.append({'label': 'Turn Wi-Fi off' if self.wifi else 'Leave Wi-Fi off', 'rt': []})
        it.append({'label': 'Search again', 'rt': []})
        return it

    def draw_wifi(self):
        setup = self.ctx == 'setup'
        busy = self.dev.busy.get('scan')
        it = self.wifi_items()
        if it:
            s = self.s('wifi', len(it))
            if it[s].get('info') or it[s].get('off'):
                for i, row in enumerate(it):
                    if not row.get('info') and not row.get('off'):
                        self.sel['wifi'] = i
                        break
            it = self.wifi_items()
        nets = self.dev.wifi_list()
        connecting = self.dev.busy.get('connect')
        if connecting:
            sub = 'Connecting…'
        elif setup and self.wifi:
            sub = 'Connected to ' + self.wifi
        elif busy and not nets:
            sub = 'Searching…'
        elif setup:
            sub = 'For the clock and updates. Optional.'
        else:
            sub = 'Pick a network.'
        a = {'cap': 'Setup · 3 of 6' if setup else 'Settings', 'big': '03' if setup else 'Wi-Fi', 'sm': not setup,
             'sub': 'Connecting…' if connecting else (('Connected to ' + self.wifi) if (setup and self.wifi) else ('Wi-Fi' if setup else (self.wifi or 'Off')))}
        hint = [['B', 'Back'], ['A', 'Select']]
        self.frame('Setup' if setup else 'Wi-Fi', 'Wi-Fi', sub, 3 if setup else 0, a,
                   lambda x, y, w, h: self.list_view('wifi', it, x, y, w, h), hint)
        if connecting or busy: self.dirty = True

    def key_wifi(self, k):
        if self.dev.busy.get('connect'): return
        it = self.wifi_items()
        if it:
            s0 = self.s('wifi', len(it))
            if it[s0].get('info') or it[s0].get('off'):
                for i, r in enumerate(it):
                    if not r.get('info') and not r.get('off'):
                        self.sel['wifi'] = i
                        it = self.wifi_items()
                        break
        n = len(it); s = self.s('wifi', n); row = it[s]
        if k == 'a':
            if row.get('info'): return
            if row.get('k') == 'go':
                return self.go('tz') if self.ctx == 'setup' else self.go('settings', True)
            if row['label'] == 'Search again':
                self._wifi_auto = [0, time.time()]
                self.dev.wifi_scan(); self.dirty = True; return
            if 'net' not in row:
                if self.ctx == 'setup': self.go('tz')
                else:
                    self.dev.wifi_off(); self.toast('Wi-Fi off'); self.go('settings', True)
                return
            net = row['net']
            if self.wifi == net['ssid']:
                return self.go('tz') if self.ctx == 'setup' else self.go('settings', True)
            self._wifi_user_connect = True
            if net['lock']:
                self.pw_for = net['ssid']; self.pw = ''; self.pw_cur = 0; self.kb = [1, 0]; self.shift = 0; self.kb_sym = False; self.pw_show = False; self.pw_last = -1; self.go('kb')
            else:
                self.dev.wifi_connect(net['ssid'], ''); self.dirty = True
        elif k == 'b':
            self.go('lang' if self.ctx == 'setup' else 'settings', True)
        else: self.nav('wifi', n, k)

    def on_wifi(self, kind, ssid):
        if kind == 'wifi_ok':
            self.toast('Connected to ' + ssid)
            user = getattr(self, '_wifi_user_connect', False)
            if self.screen == 'kb' or (self.screen == 'wifi' and user):
                self._wifi_user_connect = False
                if self.ctx == 'setup': self.go('tz')
                else: self.go('settings', True)
            elif self.screen == 'wifi' and self.ctx == 'setup':
                # Connected in the background (wifi.txt): stay here, focus Continue.
                self.sel['wifi'] = 0
        elif kind == 'wifi_fail':
            self.toast("Couldn't connect to " + ssid)
            self._wifi_user_connect = False
            if self.screen == 'kb': self.go('wifi', True)

    # Keyboard (Wi-Fi password). shift: 0 off, 1 next letter, 2 caps lock.
    def kb_rows(self):
        return (KB_SYM if self.kb_sym else KB_ABC) + [KB_BOTTOM]

    def kb_label(self, key):
        if len(key) == 1:
            return key.upper() if self.shift and not self.kb_sym else key
        if key == 'Shift': return {0: 'Shift', 1: 'SHIFT', 2: 'CAPS'}[self.shift] if not self.kb_sym else 'Shift'
        if key == '#+=': return 'abc' if self.kb_sym else '#+='
        return key

    def draw_kb(self):
        g, c, o = self.g, self.c, self.opt
        setup = self.ctx == 'setup'
        th = self.topbar('Setup' if setup else 'Wi-Fi')
        y = th + self.header('Password', 'for ' + (self.pw_for or ''), 0, th)
        mx = 24 if o == 2 else 28
        fh = 40 if o == 2 else 44
        y += 2
        if o == 2:
            g.fill(mx, y + fh - 2, self.W - 2 * mx, 2, c['ac'])
        else:
            g.rrect(mx, y, self.W - 2 * mx, fh, 12, c['faint'])
        tx = mx + (2 if o == 2 else 16)
        fw = self.W - 2 * mx - (4 if o == 2 else 32) - (110 if self.dev.busy.get('connect') else 0)
        cur = clamp(self.pw_cur, 0, len(self.pw))
        if self.pw:
            vis = ''.join(ch if (self.pw_show or i == self.pw_last) else '•' for i, ch in enumerate(self.pw))
            st = 0
            while st < cur and g.measure(vis[st:cur], 700, 20, .06) > fw - 8:
                st += 1
            en = len(vis)
            while en > cur and g.measure(vis[st:en], 700, 20, .06) > fw:
                en -= 1
            ty = y + (fh - 20 * 1.366) / 2.0
            g.text(vis[st:en], tx, ty, 700, 20, c['fg'], track=.06)
            cx = tx + (g.measure(vis[st:cur], 700, 20, .06) if cur > st else 0)
            if self.shot or int(time.time() * 2) % 2 == 0:
                g.fill(cx + 1, y + (fh - 24) / 2.0, 2, 24, c['ac'])
            if not self.shot: self.dirty = True
        else:
            g.text('Password', tx, y + (fh - 19 * 1.366) / 2.0, 500, 19, c['dim'])
        if self.dev.busy.get('connect'):
            g.text('Connecting…', self.W - mx - 16 - g.measure('Connecting…', 600, 19), y + (fh - 26) / 2.0, 600, 19, c['dim']); self.dirty = True
        y += fh + 8
        rows = self.kb_rows()
        hh = HINT_H[o]
        kx0, kx1, ky1 = 22, self.W - 22, self.H - hh - 4
        gap = 5
        rhk = (ky1 - y - gap * (len(rows) - 1)) / len(rows)
        rad = {1: 9, 2: 4, 3: 50}[o]
        for r, row in enumerate(rows):
            bottom = r == len(rows) - 1
            weights = [KB_W.get(k, 1.3 if bottom else 1) for k in row]
            n = 10 if not bottom else len(row)
            unit = (kx1 - kx0 - gap * (n - 1)) / float(n) if not bottom else None
            if bottom:
                tot = kx1 - kx0 - gap * (len(row) - 1)
                x = kx0
            else:
                rw = unit * len(row) + gap * (len(row) - 1)
                x = kx0 + (kx1 - kx0 - rw) / 2.0
            for ci, key in enumerate(row):
                kw = tot * weights[ci] / sum(weights) if bottom else unit
                on = self.kb == [r, ci]
                ky = y + r * (rhk + gap)
                active = (key == 'Shift' and self.shift and not self.kb_sym) or (key == '#+=' and self.kb_sym)
                if on: g.rrect(x, ky, kw, rhk, min(rad, rhk / 2), c['ac'])
                elif active: g.rrect(x, ky, kw, rhk, min(rad, rhk / 2), c['ac'], .28)
                else: g.rrect(x, ky, kw, rhk, min(rad, rhk / 2), c['fg'], .06)
                lbl = self.kb_label(key)
                fs = 14 if bottom else (18 if o == 2 else 20); wt = 700
                tw = g.measure(lbl, wt, fs)
                g.text(lbl, x + (kw - tw) / 2.0, ky, wt, fs, c['onac'] if on else c['fg'], lineh=rhk)
                x += kw + gap
        self.hints([['Y', 'Shift'], ['X', '#+='], ['L/R', 'Move'], ['B', 'Del'], ['START', 'Join'], ['A', 'Type']])

    def kb_type(self, ch):
        cur = clamp(self.pw_cur, 0, len(self.pw))
        if len(self.pw) >= 63: return self.toast('Wi-Fi passwords are at most 63 characters')
        self.pw = self.pw[:cur] + ch + self.pw[cur:]; self.pw_cur = cur + 1; self.pw_last = cur
        if self.shift == 1: self.shift = 0

    def kb_delete(self):
        cur = clamp(self.pw_cur, 0, len(self.pw))
        if cur > 0:
            self.pw = self.pw[:cur - 1] + self.pw[cur:]; self.pw_cur = cur - 1
        self.pw_last = -1

    def kb_toggle_sym(self):
        self.kb_sym = not self.kb_sym
        rows = self.kb_rows(); r = min(self.kb[0], len(rows) - 1)
        self.kb = [r, min(self.kb[1], len(rows[r]) - 1)]

    def kb_press(self):
        rows = self.kb_rows(); r, ci = self.kb; key = rows[r][ci]
        if len(key) == 1: self.kb_type(self.kb_label(key))
        elif key == 'Shift':
            if self.kb_sym: self.kb_toggle_sym()
            self.shift = (self.shift + 1) % 3
        elif key == '#+=': self.kb_toggle_sym()
        elif key == 'Space': self.kb_type(' ')
        elif key == 'Del': self.kb_delete()
        elif key == 'Join': return self.kb_done()
        self.dirty = True

    def kb_done(self):
        if not self.pw: return self.toast('Type the password first')
        if len(self.pw) < 8: return self.toast('Wi-Fi passwords have at least 8 characters')
        self.dev.wifi_connect(self.pw_for, self.pw); self.dirty = True

    def key_kb(self, k):
        if self.dev.busy.get('connect'): return
        rows = self.kb_rows(); r, ci = self.kb
        if k in ('up', 'down'):
            nr = clamp(r + (-1 if k == 'up' else 1), 0, len(rows) - 1)
            if nr != r:
                # keep the column under the same spot on screen
                pos = (ci + .5) / len(rows[r]); self.kb = [nr, clamp(int(pos * len(rows[nr])), 0, len(rows[nr]) - 1)]
        elif k in ('left', 'right'):
            self.kb = [r, (ci + (-1 if k == 'left' else 1)) % len(rows[r])]
        elif k == 'a': return self.kb_press()
        elif k == 'b':
            if self.pw: self.kb_delete()
            else: return self.go('wifi', True)
        elif k == 'menu': return self.kb_done()
        elif k == 'y':
            if self.kb_sym: self.kb_toggle_sym()
            self.shift = (self.shift + 1) % 3
        elif k == 'x': self.kb_toggle_sym()
        elif k == 'l1': self.pw_cur = max(0, min(self.pw_cur, len(self.pw)) - 1); self.pw_last = -1
        elif k == 'r1': self.pw_cur = min(len(self.pw), self.pw_cur + 1); self.pw_last = -1
        elif k == 'select': self.pw_show = not self.pw_show
        self.dirty = True

    # Time zone
    def tz_index(self):
        cur = self.tz or 'America/Los_Angeles'
        return next((i for i, t in enumerate(TZS) if t[1] == cur), 0)

    def draw_tz(self):
        cur = self.tz_index()
        it = [{'label': t[0], 'rt': [('ico', 'check')] if i == cur else []} for i, t in enumerate(TZS)]
        self.frame('Setup', 'Time zone', 'Where you are.', 4, {'cap': 'Setup · 4 of 6', 'big': '04', 'sub': 'Time zone'},
                   lambda x, y, w, h: self.list_view('tz', it, x, y, w, h), [['B', 'Back'], ['A', 'Select']])

    def key_tz(self, k):
        if k == 'a':
            self.tz = TZS[self.s('tz', len(TZS))][1]; self.dev.set_tz(self.tz); self.persist(); self.go('time')
        elif k == 'b':
            if self.dev.wifi_present():
                if self.wifi:
                    self.sel['wifi'] = 0
                self.go('wifi', True)
            else:
                self.go('lang', True)
        else: self.nav('tz', len(TZS), k)

    # Time
    def time_items(self):
        it = [{'label': 'Set automatically', 'rt': [('t', ('On' if self.time_auto else 'Off') if self.wifi else 'Needs Wi-Fi')], 'k': 'auto'},
              {'label': '24-hour clock', 'rt': [('t', 'On' if self.h24 else 'Off')], 'k': 'h24'}]
        if not (self.wifi and self.time_auto):
            p = self.time_parts()[0].split(':')
            it += [{'label': 'Hour', 'rt': [('arrows', p[0])], 'k': 'h'}, {'label': 'Minute', 'rt': [('arrows', p[1])], 'k': 'm'}]
        it.append({'label': 'Continue', 'rt': [('chev',)], 'k': 'go'})
        return it

    def draw_time(self):
        g, c, o = self.g, self.c, self.opt
        t, ap = self.time_parts(); it = self.time_items()
        hint = [['B', 'Back'], ['◂▸', 'Adjust'], ['A', 'Select']]
        if o == 3:
            return self.frame('Setup', aside={'cap': 'Setup · 4 of 6', 'big': t, 'sub': (ap + ' · ' if ap else '') + self.fmt_date()},
                              body=lambda x, y, w, h: self.list_view('time', it, x, y, w, h), hint=hint)
        th = self.topbar('Setup')
        y = th + self.header('Time', '', 4, th)
        px = 24 if o == 2 else 28
        wt = 300 if o == 2 else 800
        tw = 0
        for ch in t: tw += g.text(ch, px + tw, y, wt, 64, c['fg'], lineh=64) - .02 * 64
        g.text((ap + ' · ' if ap else '') + self.fmt_date(), px + tw + 10, y + 64 - 22 * 1.366 - 4, 600, 22, c['dim'])
        y += 64 + 8
        self.list_view('time', it, 0, y, self.W, self.H - y - HINT_H[o])
        self.hints(hint)

    def key_time(self, k):
        it = self.time_items(); s = self.s('time', len(it)); row = it[s]
        if k == 'b': return self.go('tz', True)
        if k in ('left', 'right') and row['k'] in ('h', 'm'):
            self.man_off += (-1 if k == 'left' else 1) * (60 if row['k'] == 'h' else 1); self.dirty = True; return
        if k in ('a', 'left', 'right'):
            if row['k'] == 'auto':
                if not self.wifi: return self.toast('Connect Wi-Fi to set it automatically')
                self.time_auto = not self.time_auto
                if self.time_auto: self.man_off = 0
            elif row['k'] == 'h24': self.h24 = not self.h24; self.persist()
            elif row['k'] == 'go' and k == 'a':
                if self.man_off:
                    self.dev.set_time(self.dev.now() + self.man_off * 60); self.man_off = 0
                return self.go('card')
            self.dirty = True; return
        self.nav('time', len(it), k)

    # Games card
    def draw_card(self):
        cards = self.dev.cards()
        it = [{'label': a, 'rt': [('t', b)], 'off': idx < 0} for a, b, idx in cards]
        self.frame('Setup', 'Games location', 'Which card holds your games?', 5, {'cap': 'Setup · 5 of 6', 'big': '05', 'sub': 'Games location'},
                   lambda x, y, w, h: self.list_view('card', it, x, y, w, h), [['B', 'Back'], ['A', 'Select']])

    def key_card(self, k):
        cards = self.dev.cards()
        if k == 'a':
            i = self.s('card', len(cards))
            if cards[i][2] < 0: return self.toast('Put a card in slot 2 first')
            self.card = i + 1
            self.dev.set_games_card(cards[i][2]); self.copy_path = self.dev.make_folders(); self.go('copy')
        elif k == 'b': self.go('time', True)
        else: self.nav('card', len(cards), k)

    # Copy screen (end of Setup; also Settings > Add games)
    COPY_FEATURED = ['psp', 'psx', 'snes', 'gba', 'n64', 'genesis', 'nes', 'arcade', 'fbneo', 'gb', 'gbc', 'nds', 'dreamcast']

    def copy_lines(self):
        """('hdr', text) and ('row', folder, full name): popular systems first, then every other folder."""
        names = dict(SETUP_FOLDERS)
        names.setdefault('saves', 'Saves and save states (back these up)')
        feat = [f for f in self.COPY_FEATURED if f in names]
        rest = [f for f, _ in SETUP_FOLDERS if f not in feat] + ['saves']
        out = [('hdr', 'Popular')] + [('row', f, names[f]) for f in feat]
        out += [('hdr', 'All other folders')] + [('row', f, names[f]) for f in rest]
        return out

    def draw_copy(self):
        g, c, o, fz = self.g, self.c, self.opt, self.fz
        setup = not self.setup_done
        th = self.topbar('Setup' if setup else 'Settings')
        y = th + self.header('Copy your games here', '', 6 if setup else 0, th)
        px = 24 if o == 2 else 28
        fs = 24 * fz                      # Roomy list text size: nothing on this screen is smaller
        lh = fs * 1.32
        W = self.W - 2 * px
        path = self.copy_path or self.dev.games_where()
        share = self.dev.share_on()
        ip = self.dev.ip_addr()
        if 'GAMES' in path:
            pc = ['Open GAMES \u203a roms on a computer.']
        elif path.startswith('Card 2'):
            pc = ['Open card 2 \u203a roms on a computer.']
        else:
            pc = ['Computers can\u2019t open this card: use Wi-Fi.']
        if share:
            user, pw = self.dev.share_login()
            wifi = ['\\\\sdos\\games' + ('  or  \\\\%s\\games' % ip if ip else ''), 'user %s \u00b7 password %s' % (user, pw)]
        else:
            wifi = ['Turn on Network share in Settings.']
        lw = max(g.measure(l, 800, fs) for l in ('Computer', 'Wi-Fi')) + 16
        for lbl, lines in (('Computer', pc), ('Wi-Fi', wifi)):
            g.text(lbl, px, y, 800, fs, c['ac'], lineh=lh)
            for ln in lines:
                for part in g.wrap(ln, 600, fs, W - lw):
                    g.text(part, px + lw, y, 600, fs, c['fg'], lineh=lh); y += lh
            y += 6
        y += 2
        g.fill(px, y, W, 1, c['faint']); y += 8
        # scrollable folder list
        hh = HINT_H[o]
        cta_h = int(round(ROWH[o] * fz)) if setup else 0
        cta_gap = 10 if setup else 0
        top, bot = y, self.H - hh - 4 - (cta_h + cta_gap if setup else 0)
        lines = self.copy_lines()
        vis = max(1, int((bot - top) // lh))
        maxtop = max(0, len(lines) - vis)
        self.copy_top = min(max(0, getattr(self, 'copy_top', 0)), maxtop)
        fw = max(g.measure(ln[1], 800, fs) for ln in lines if ln[0] == 'row') + 16
        g.clip(0, top, self.W, bot - top)
        yy = top
        for ln in lines[self.copy_top:self.copy_top + vis]:
            if ln[0] == 'hdr':
                g.text(ln[1], px, yy, 800, fs, c['ac'], lineh=lh)
            else:
                g.text(ln[1], px, yy, 800, fs, c['fg'], lineh=lh)
                for i, part in enumerate(g.wrap(ln[2], 500, fs, W - fw - 14)[:1]):
                    g.text(part, px + fw, yy, 500, fs, c['dim'], lineh=lh)
            yy += lh
        g.clip()
        if maxtop:   # scroll bar
            bh = bot - top
            th2 = max(24, bh * vis / float(len(lines)))
            ty = top + (bh - th2) * self.copy_top / float(maxtop)
            g.rrect(self.W - 10, top, 4, bh, 2, c['faint'])
            g.rrect(self.W - 10, ty, 4, th2, 2, c['ac'])
        if setup:
            self.draw_cta(px, bot + cta_gap, W, cta_h, 'Continue')
        self.hints([['▲▼', 'Scroll'], ['B', 'Back'], ['A', 'Continue' if setup else 'Done']])

    def key_copy(self, k):
        if k in ('up', 'down', 'l1', 'r1'):
            step = {'up': -1, 'down': 1, 'l1': -6, 'r1': 6}[k]
            self.copy_top = max(0, getattr(self, 'copy_top', 0) + step); self.dirty = True
            return
        if self.setup_done:
            if k in ('a', 'b'):
                self.rescan(); self.go('settings', True)
            return
        if k == 'a':
            self.setup_done = True; self.ctx = 'home'; self.sel['home'] = 0; self.persist(); self.rescan(); self.go('home')
        elif k == 'b': self.go('card', True)

    # Home
    def home_items(self):
        it = []
        if self.recents: it.append({'label': 'Recently played', 'rt': [('t', str(len(self.recents)))], 'kind': 'recent', 'n': len(self.recents)})
        if self.favs: it.append({'label': 'Favorites', 'rt': [('t', str(len(self.favs)))], 'kind': 'fav', 'n': len(self.favs)})
        if it: it[-1]['sep'] = True
        for s in self.systems:
            if s['games']: it.append({'label': s['name'], 'rt': [('t', str(len(s['games'])))], 'kind': s['id'], 'n': len(s['games'])})
        if it: it[-1]['sep'] = True
        it.append({'label': 'Tools', 'rt': [('chev',)], 'kind': 'tools', 'n': len(self.tool_list())})
        return it

    def has_games(self):
        return any(s['games'] for s in self.systems)

    def draw_home(self):
        it = self.home_items()
        if not self.has_games() and not self.recents and not self.favs:
            def body(x, y, w, h):
                g, c = self.g, self.c
                msg = ['No games yet', 'Copy games into the roms folders on your card.']
                yy = y + 18
                g.text(msg[0], x + 28, yy, 800, 24, c['fg']); yy += 36
                g.text(msg[1], x + 28, yy, 500, 16, c['dim'], maxw=w - 56); yy += 34
                self.list_view('home', [{'label': 'Refresh games', 'rt': [], 'kind': 'refresh'}, it[-1]], x, yy, w, h - (yy - y))
            return self.frame('', aside={'cap': 'Games', 'big': '0', 'sub': 'No games yet'}, body=body, hint=[['☰', 'Settings', 'l'], ['A', 'Open']])
        if not it:
            def body(x, y, w, h):
                g, c = self.g, self.c
                msg = ['No games yet', 'Copy games into the roms folders on your card,', 'then come back here.']
                yy = y + h / 2.0 - 50
                g.text(msg[0], x + (w - g.measure(msg[0], 800, 24)) / 2.0, yy, 800, 24, c['fg']); yy += 40
                for m in msg[1:]:
                    g.text(m, x + (w - g.measure(m, 500, 16)) / 2.0, yy, 500, 16, c['dim']); yy += 24
            return self.frame('', aside={'cap': 'Games', 'big': '0', 'sub': 'No games yet'}, body=body, hint=[['☰', 'Settings', 'l'], ['A', 'Refresh']])
        s = it[self.s('home', len(it))]
        self.frame('', aside={'cap': 'Your list' if s['kind'] in ('recent', 'fav') else 'Games', 'big': str(s['n']), 'sub': s['label']},
                   body=lambda x, y, w, h: self.list_view('home', it, x, y, w, h), hint=[['☰', 'Settings', 'l'], ['A', 'Open']])

    def key_home(self, k):
        it = self.home_items()
        if k == 'menu': self.ctx = 'home'; self.sel['settings'] = 0; return self.go('settings')
        if not self.has_games() and not self.recents and not self.favs:
            it = [{'kind': 'refresh'}, {'kind': 'tools'}]
        if not it:
            if k == 'a': self.rescan(); self.dirty = True
            return
        if k == 'a':
            kind = it[self.s('home', len(it))]['kind']
            if kind == 'refresh':
                self.rescan(); self.toast('Found %d games' % sum(len(s['games']) for s in self.systems) if self.has_games() else 'No games found yet'); return
            if kind == 'tools': self.sel['tools'] = 0; return self.go('tools')
            self.sys = kind; self.sel['games'] = 0; self.go('games')
        else: self.nav('home', len(it), k)

    # Games
    def game_list(self):
        if self.sys == 'recent':
            lst = self.recents
        elif self.sys == 'fav':
            allg = [g for s in self.systems for g in s['games']]
            lst = sorted([g for g in allg if g['path'] in self.favs], key=lambda g: g['title'].lower())
        else:
            s = self.sys_by(self.sys); lst = s['games'] if s else []
        return lst

    def sys_label(self):
        if self.sys == 'recent': return 'Recently played'
        if self.sys == 'fav': return 'Favorites'
        s = self.sys_by(self.sys); return s['name'] if s else ''

    def game_items(self):
        mixed = self.sys in ('recent', 'fav')
        out = []
        for g in self.game_list():
            s = self.sys_by(g['sys'])
            out.append({'label': g['title'], 'g': g, 'lead': g['path'] in self.favs, 'rt': [('t', s['short'] if s else g['sys'].upper())] if mixed else []})
        return out

    def draw_games(self):
        g, c = self.g, self.c
        it = self.game_items(); n = len(it); s = self.s('games', n); cur = it[s] if n else None
        hint = [['◂▸', 'Page' if self.sys == 'recent' else 'A–Z', 'l'], ['Y', 'Unfavorite' if cur and cur['lead'] else 'Favorite'], ['B', 'Back'], ['A', 'Play']]
        def body(x, y, w, h):
            self.list_view('games', it, x, y, w, h)
            if self.jump:
                l, t0 = self.jump; dt = time.time() - t0
                if dt > .95 and not self.shot: self.jump = None; return
                a = ease(dt / .25) if dt < .7 else 1 - ease((dt - .7) / .25)
                if self.shot: a = 1
                else: self.dirty = True
                jx, jy = x + w - 30 - 84, y + h / 2.0 - 42
                g.rrect(jx, jy, 84, 84, 20, c['ac'], c['acbg_a'] * a)
                g.ring(jx, jy, 84, 84, 20, c['ac'], a, sw=2)
                tw = g.measure(l, 800, 48)
                g.text(l, jx + (84 - tw) / 2.0, jy, 800, 48, c['ac'], a, lineh=84)
        self.frame('', self.sys_label(), '%d game%s' % (n, '' if n == 1 else 's'),
                   aside={'cap': self.sys_label(), 'big': cur['label'][0].upper() if cur else '–', 'sub': ('%d of %d' % (s + 1, n)) if n else ''},
                   body=body, hint=hint)

    def key_games(self, k):
        it = self.game_items(); n = len(it); s = self.s('games', n)
        if k == 'b': return self.go('home', True)
        if k == 'menu': self.ctx = 'games'; self.sel['settings'] = 0; return self.go('settings')
        if not n: return
        if k == 'a': return self.launch(it[s]['g'])
        if k == 'y':
            p = it[s]['g']['path']
            if p in self.favs: self.favs.discard(p); self.toast('Removed from Favorites')
            else: self.favs.add(p); self.toast('Added to Favorites')
            self.persist()
            if self.sys == 'fav': self.sel['games'] = clamp(s, 0, max(0, len(self.game_items()) - 1))
            self.dirty = True; return
        if k in ('left', 'right'):
            if self.sys == 'recent':
                j = clamp(s + (-5 if k == 'left' else 5), 0, n - 1)
            else:
                L = lambda i: it[i]['label'][:1].upper(); cl = L(s)
                if k == 'right':
                    j = next((i for i in range(s + 1, n) if L(i) != cl), 0)
                else:
                    i = s
                    if i > 0 and L(i - 1) == cl:
                        while i > 0 and L(i - 1) == cl: i -= 1
                        j = i
                    else:
                        i = (s - 1 + n) % n; t = L(i)
                        while i > 0 and L(i - 1) == t: i -= 1
                        j = i
                self.jump = (L(j), time.time())
            self.sel['games'] = j; self.dirty = True; return
        self.nav('games', n, k)

    def launch(self, game):
        if not self.dev.mock and self.dev.game_running():
            self._pending_launch = ('game', game)
            self._pending_until = time.time() + 4.0
            return self.toast('Closing the last game…')
        self._start_game(game)

    def _start_game(self, game):
        self._pending_launch = None
        self.game = game
        self.recents = [game] + [r for r in self.recents if r['path'] != game['path']]
        self.recents = self.recents[:10]; self.persist()
        self.ovl = False; self.saved = False
        if self.dev.mock:
            return self.go('game')
        self.dev.launch(game)
        self.go('game')

    def _start_tool(self, t):
        self._pending_launch = None
        how = t[3]
        self.ovl = False; self.saved = False
        self.game = {'title': t[1], 'sys': 'tool', 'path': how[1]}
        if self.dev.mock: return self.go('game')
        if not self.dev.launch_tool(t):
            self.game = None; return self.toast(t[1] + " isn't available")
        return self.go('game')

    # In-game
    def draw_game(self):
        g, c, o = self.g, self.c, self.opt
        gm = self.game or {'title': 'Game', 'sys': 'psp'}
        sy = self.sys_by(gm['sys']); sname = sy['name'] if sy else ('Tools' if gm['sys'] == 'tool' else gm['sys'])
        bgimg = None if self.dev.mock else (g.image('/tmp/sdui_pause.png') if self.ovl and os.path.exists('/tmp/sdui_pause.png') else None)
        if bgimg:
            g.blit_image(bgimg, 0, 0, self.W, self.H)
        else:
            g.fill(0, 0, self.W, self.H, '#050506')
            g.alpha = 1
            for yy in range(0, self.H, 4): g.fill(0, yy, self.W, 2, '#FFFFFF', .025)
            if not self.ovl:
                if self.dev.mock:
                    t1 = gm['title']; t2 = sname + ' · the game plays here'
                else:
                    t1 = gm['title']; t2 = 'Starting ' + sname + '…'
                g.text(t1, (self.W - g.measure(t1, 800, 26)) / 2.0, self.H / 2.0 - 30, 800, 26, '#E8E8EA')
                g.text(t2, (self.W - g.measure(t2, 500, 19)) / 2.0, self.H / 2.0 + 10, 500, 19, '#8A8F95')
                hint = 'PRESS MENU TO PAUSE'
                g.text(hint, (self.W - g.measure(hint, 500, 17, .12)) / 2.0, self.H - 18 - 22, 500, 17, '#4B4F55', track=.12)
        if not self.ovl: return
        g.fill(0, 0, self.W, self.H, '#000000', .55)
        pw = round(self.W * .58)
        g.vgrad(pw, 0, 60, self.H, '#000000', .5, 0, horiz=True)
        g.fill(0, 0, pw, self.H, c['bg'])
        y = 0 if o == 3 else self.topbar('', 0, pw)
        h1, sub = ('Paused', gm['title']) if o == 2 else (gm['title'], sname + ' · paused')
        y += self.header(h1, sub, 0, y, 0, pw)
        it = [{'label': x, 'rt': [('t', ('Slot 1' if self.saved else 'Empty'))] if x == 'Load state' and self.dev.mock else ([('t', 'Slot 1')] if x == 'Save state' and self.dev.mock else [])} for x in self.ovl_list()]
        self.list_view('ovl', it, 0, y, pw, self.H - y - HINT_H[o])
        self.hints([['B', 'Resume'], ['A', 'Select']], 0, pw)

    def key_game(self, k):
        if not self.ovl:
            if k == 'menu' and (self.dev.mock or self.dev.game_running()):
                if not self.dev.mock: self.dev.pause_game()
                self.ovl = True; self.sel['ovl'] = 0; self.dirty = True
            return
        if k in ('b', 'menu'): return self.resume()
        OV = self.ovl_list()
        if k == 'a':
            o = OV[self.s('ovl', len(OV))]
            if o == 'Resume': self.resume()
            elif o == 'Save state':
                if self.dev.mock: self.saved = True; return self.toast('Saved to slot 1')
                msg, resumed = self.dev.game_save(); self.toast(msg)
                if resumed: self.ovl = False
            elif o == 'Load state':
                if self.dev.mock:
                    if not self.saved: return self.toast('No save in slot 1 yet')
                    self.ovl = False; return self.toast('Loaded slot 1')
                msg, resumed = self.dev.game_load(); self.toast(msg)
                if resumed: self.ovl = False
            elif o == 'Emulator settings':
                if self.dev.mock: return self.toast('The emulator\u2019s own menu opens here')
                msg, resumed = self.dev.emu_menu()
                if msg: self.toast(msg)
                if resumed: self.ovl = False
            elif o == 'Settings':
                self.ctx = 'game'; self.sel['settings'] = 0; self.go('settings')
            else:
                self.ovl = False
                tool = self.is_tool()
                if not self.dev.mock: self.dev.quit_game()
                self.go('tools' if tool else 'games', True)
            self.dirty = True; return
        self.nav('ovl', len(OV), k)

    def is_tool(self):
        return bool(self.game) and self.game.get('sys') == 'tool'

    def ovl_list(self):
        return OVL_TOOL if self.is_tool() else OVL

    def resume(self):
        self.ovl = False; self.dirty = True
        if not self.dev.mock: self.dev.resume_game()

    def on_game_exit(self, tool=False):
        self.ovl = False
        self.dev.raise_ui()
        if self.screen in ('game', 'settings', 'look', 'about', 'wifi', 'kb', 'bt') :
            self.ctx = 'home'; self.go('tools' if tool else 'games', True)

    # Settings
    def bt_row_status(self):
        if not self.dev.bt_on():
            return 'Off'
        for d in self.dev.bt_paired:
            if d.get('connected'):
                return d['name']
        return 'On'

    def bt_items(self):
        it = []
        on = self.dev.bt_on()
        pairing = self.dev.busy.get('bt_pair')
        scanning = self.dev.busy.get('bt_scan')
        enabling = self.dev.busy.get('bt_enable')
        if not on and not enabling:
            it.append({'label': 'Turn Bluetooth on', 'k': 'on'})
            return it
        if enabling:
            it.append({'label': 'Turning on…', 'rt': [], 'off': True, 'info': True})
            it.append({'label': 'Turn Bluetooth off', 'k': 'off'})
            return it
        it.append({'label': 'Turn Bluetooth off', 'k': 'off'})
        if scanning:
            it.append({'label': 'Searching for devices…', 'rt': [], 'off': True, 'info': True})
        else:
            it.append({'label': 'Search for devices', 'k': 'scan'})
        paired_macs = {d['mac'] for d in self.dev.bt_paired}
        if not self.dev.bt_paired and not self.dev.bt_found and not scanning:
            it.append({'label': 'No devices yet. Search to pair.', 'rt': [], 'off': True, 'info': True})
        for d in self.dev.bt_paired:
            if d.get('connected'):
                rt = [('t', 'Connected')]
            else:
                rt = [('t', 'Paired')]
            it.append({'label': d['name'], 'rt': rt, 'dev': d, 'kind': 'paired'})
        for d in self.dev.bt_found:
            if d['mac'] in paired_macs:
                continue
            it.append({'label': d['name'], 'rt': [('t', 'Found')], 'dev': d, 'kind': 'found'})
        if pairing:
            pass
        return it

    def draw_bt(self):
        it = self.bt_items()
        if it:
            s = self.s('bt', len(it))
            if it[s].get('info') or it[s].get('off'):
                for i, row in enumerate(it):
                    if not row.get('info') and not row.get('off'):
                        self.sel['bt'] = i
                        break
            it = self.bt_items()
        msg = self.dev.bt_status_msg()
        if self.dev.busy.get('bt_enable'):
            sub = 'Turning on…'
        elif not self.dev.bt_on():
            sub = 'Off until you turn it on.'
        elif msg:
            sub = msg
        elif self.dev.busy.get('bt_scan'):
            sub = 'Searching… Put the device in pairing mode.'
        else:
            sub = 'Controllers and headphones.'
        aside_sub = self.bt_row_status()
        a = {'cap': 'Settings', 'big': 'Bluetooth', 'sm': True, 'sub': aside_sub}
        s = self.s('bt', len(it)) if it else 0
        hint = [['B', 'Back'], ['A', 'Select']]
        if it and it[s].get('kind') == 'paired':
            hint = [['Y', 'Forget', 'l'], ['B', 'Back'], ['A', 'Select']]
        self.frame('Bluetooth', 'Bluetooth', sub, 0, a,
                   lambda x, y, w, h: self.list_view('bt', it, x, y, w, h, empty='No Bluetooth devices'), hint)
        if self.dev.busy.get('bt_scan') or self.dev.busy.get('bt_pair') or self.dev.busy.get('bt_enable'):
            self.dirty = True

    def key_bt(self, k):
        if self.dev.busy.get('bt_pair') or self.dev.busy.get('bt_enable'):
            if k in ('b', 'menu'):
                self.dev.bt_stop_scan()
                return self.go('settings', True)
            return
        it = self.bt_items()
        if it:
            s0 = self.s('bt', len(it))
            if it[s0].get('info') or it[s0].get('off'):
                for i, r in enumerate(it):
                    if not r.get('info') and not r.get('off'):
                        self.sel['bt'] = i
                        it = self.bt_items()
                        break
        n = len(it)
        if not n:
            if k in ('b', 'menu'):
                self.dev.bt_stop_scan(); return self.go('settings', True)
            return
        s = self.s('bt', n); row = it[s]
        if k == 'a':
            if row.get('info'):
                return
            if row.get('k') == 'on':
                self.dev.bt_enable(); self.dirty = True; return
            if row.get('k') == 'off':
                self.dev.bt_disable(); self.toast('Bluetooth off'); self.go('settings', True); return
            if row.get('k') == 'scan':
                self.dev.bt_scan(); self.dirty = True; return
            dev = row.get('dev')
            if not dev:
                return
            if row.get('kind') == 'found':
                self.dev.bt_pair(dev['mac']); self.dirty = True; return
            if dev.get('connected'):
                self.dev.bt_disconnect(dev['mac']); self.toast('Disconnected ' + dev['name']); self.dirty = True; return
            self.dev.bt_connect(dev['mac']); self.dirty = True; return
        if k == 'y':
            dev = row.get('dev')
            if dev and row.get('kind') == 'paired':
                self.dev.bt_forget(dev['mac']); self.toast('Forgot ' + dev['name']); self.dirty = True
            return
        if k in ('b', 'menu'):
            self.dev.bt_stop_scan()
            return self.go('settings', True)
        self.nav('bt', n, k)

    def on_bt(self, kind, text):
        if kind == 'bt_ok':
            self.toast('Connected to ' + (text or 'device'))
        elif kind == 'bt_fail':
            self.toast('Could not connect to ' + (text or 'that device'))
        elif kind == 'bt_nohw':
            self.toast('No Bluetooth hardware')
        elif kind == 'bt_audio' and text == 'speaker':
            self.toast('Headphones disconnected. Using speakers.')
        self.dirty = True

    def set_items(self):
        it = [{'label': 'Brightness', 'rt': [('bar', self.bright, 10)], 'k': 'bright'},
              {'label': 'Volume', 'rt': [('bar', self.vol, 10)], 'k': 'vol'},
              {'label': 'Look', 'rt': [('t', LK.look_name(self.look)), ('chev',)], 'k': 'look'}]
        if self.dev.wifi_present():
            it.append({'label': 'Wi-Fi', 'rt': [('t', self.wifi or 'Off'), ('chev',)], 'k': 'wifi'})
        if self.dev.bt_present():
            it.append({'label': 'Bluetooth', 'rt': [('t', self.bt_row_status()), ('chev',)], 'k': 'bt'})
        it += [{'label': 'Swap A/B', 'rt': [('arrows', 'On' if self.swap_ab else 'Off')], 'k': 'swap_ab'},
               {'label': 'Swap X/Y', 'rt': [('arrows', 'On' if self.swap_xy else 'Off')], 'k': 'swap_xy'},
               {'label': 'Sleep after', 'rt': [('arrows', SLEEP[self.sleep][0])], 'k': 'sleep'},
               {'label': 'Update', 'rt': [('t', {'idle': 'Check now', 'checking': 'Checking…', 'new': 'Install ' + self.upd_msg, 'none': 'Up to date', 'err': 'Try again', 'reboot': 'Restarting…'}.get(self.upd, 'Check now')), ('chev',)], 'k': 'upd'},
               {'label': 'Add games', 'rt': [('t', 'How to copy'), ('chev',)], 'k': 'copy'},
               {'label': 'Network share', 'rt': [('arrows', 'On' if self.dev.share_on() else 'Off')], 'k': 'share'},
               {'label': 'Device model', 'rt': [('t', self.model_label())] + ([] if MODEL_AUTO else [('chev',)]), 'k': 'model'},
               {'label': 'About & licenses', 'rt': [('chev',)], 'k': 'about', 'sep': True},
               {'label': 'Restart', 'rt': [('chev',)], 'k': 'restart'},
               {'label': 'Shut down', 'rt': [('chev',)], 'k': 'shutdown'}]
        return it

    def model_label(self, dt=None):
        dt = self.dev.current_model() if dt is None else dt
        return model_name(dt)

    def draw_settings(self):
        it = self.set_items(); s = it[self.s('settings', len(it))]
        am = {'bright': {'big': '%d%%' % (self.bright * 10)}, 'vol': {'big': '%d%%' % (self.vol * 10)}, 'wifi': {'big': self.wifi or 'Off', 'sm': True},
              'bt': {'big': 'BT', 'sm': True, 'sub': self.bt_row_status()},
              'swap_ab': {'big': 'A/B', 'sub': 'On' if self.swap_ab else 'Off'},
              'swap_xy': {'big': 'X/Y', 'sub': 'On' if self.swap_xy else 'Off'},
              'sleep': {'big': SLEEP[self.sleep][0].replace(' min', ''), 'sub': 'minutes' if self.sleep < 4 else ''},
              'upd': {'big': VERSION, 'sub': {'checking': 'Checking…', 'none': 'Up to date', 'new': 'New: ' + self.upd_msg}.get(self.upd, 'Version')},
              'about': {'big': 'Info', 'sm': True, 'sub': 'Open-source licenses'}, 'look': {'big': 'Aa', 'sub': LK.look_name(self.look)},
              'model': {'big': self.model_label(), 'sm': True, 'sub': 'Found automatically' if MODEL_AUTO else 'Device model'},
              'copy': {'big': 'Games', 'sm': True, 'sub': 'How to copy'}, 'share': {'big': 'On' if self.dev.share_on() else 'Off', 'sub': '\\\\sdos\\games'}, 'restart': {'big': 'Restart', 'sm': True}, 'shutdown': {'big': 'Off', 'sm': True, 'sub': 'Shut down'}}
        a = dict({'cap': 'Settings · ' + s['label']}, **am.get(s['k'], {}))
        self.frame('Settings', 'Settings', None, 0, a, lambda x, y, w, h: self.list_view('settings', it, x, y, w, h), [['◂▸', 'Change', 'l'], ['B', 'Back'], ['A', 'Open']])

    def key_settings(self, k):
        it = self.set_items(); s = self.s('settings', len(it)); row = it[s]
        if k in ('b', 'menu'):
            if self.ctx == 'game':
                if self.dev.mock or self.dev.game_running():
                    self.ovl = True; return self.go('game', True)
                return self.go('games', True)
            return self.go('games' if self.ctx == 'games' else 'home', True)
        if k in ('left', 'right'):
            d = -1 if k == 'left' else 1
            if row['k'] == 'bright': self.bright = clamp(self.bright + d, 1, 10); self.dev.set_bright(self.bright)
            elif row['k'] == 'vol': self.vol = clamp(self.vol + d, 0, 10); self.dev.set_vol(self.vol)
            elif row['k'] == 'sleep': self.sleep = clamp(self.sleep + d, 0, len(SLEEP) - 1); self.persist()
            elif row['k'] == 'swap_ab': self.set_btn_swap('ab', not self.swap_ab)
            elif row['k'] == 'swap_xy': self.set_btn_swap('xy', not self.swap_xy)
            elif row['k'] == 'share': self.dev.set_share(not self.dev.share_on())
            self.dirty = True; return
        if k == 'a':
            if row['k'] == 'wifi':
                self.ret = self.ctx; self.ctx = 'settings'; self.sel['wifi'] = 0; self._wifi_auto = [0, time.time()]; self.dev.wifi_scan(); return self.go('wifi')
            if row['k'] == 'bt':
                self.ret = self.ctx; self.ctx = 'settings'; self.sel['bt'] = 0
                if self.dev.bt_on():
                    self.dev.bt_refresh(); self.dev.bt_scan()
                return self.go('bt')
            if row['k'] == 'upd':
                if self.upd == 'new': self.dev.apply_update(); self.upd = 'reboot'; self.dirty = True; return
                self.upd = 'checking'; self.dev.check_update(); self.dirty = True; return
            if row['k'] == 'about': self.about_y = 0; return self.go('about')
            if row['k'] == 'swap_ab': self.set_btn_swap('ab', not self.swap_ab); return
            if row['k'] == 'swap_xy': self.set_btn_swap('xy', not self.swap_xy); return
            if row['k'] == 'share': self.dev.set_share(not self.dev.share_on()); self.dirty = True; return
            if row['k'] == 'copy': self.copy_path = self.dev.games_where(); return self.go('copy')
            if row['k'] == 'look': self.sel['look'] = 0; return self.go('look')
            if row['k'] == 'model':
                if MODEL_AUTO: return self.toast('Your handheld was found automatically')
                self.sel['model'] = max(0, model_of(self.dev.current_model())[0]); return self.go('model')
            if row['k'] in ('restart', 'shutdown'):
                self.confirm = (row['k'],); self.sel['confirm'] = 0; return self.go('confirm')
            return
        self.nav('settings', len(it), k)

    def on_upd(self, text):
        kind, _, msg = text.partition(':')
        self.upd = kind; self.upd_msg = msg if kind == 'new' else ''
        if kind != 'new': self.toast(msg)
        else:
            notes = str((getattr(self.dev, 'update_feed', None) or {}).get('notes') or '')
            if len(notes) > 34: notes = notes[:33].rstrip() + '…'
            self.toast(('sdOS %s: %s' % (msg, notes)) if notes else 'sdOS %s is available' % msg)

    # About
    ABOUT = [('p', 'sdOS %s by Static Divisions. A simple, text-only system for %s.' % (VERSION, FAMILY)),
             ('h', 'Source code'),
             ('p', 'This system is free software. The written source offer and license notes are in SOURCE_OFFER.txt on the SDOS drive (the card\u2019s boot partition, visible on a computer). License texts are in /usr/share/licenses.'),
             ('h', 'Credits'),
             ('p', 'sdOS is built on these open-source projects. Each keeps its own license; source is at the link.'),
             ('p', 'ROCKNIX (base system, build 20261101) \u00b7 GPL-2.0 \u00b7 github.com/ROCKNIX/distribution'),
             ('p', 'JELOS and LibreELEC (ROCKNIX\u2019s roots) \u00b7 GPL-2.0 \u00b7 github.com/LibreELEC/LibreELEC.tv'),
             ('p', 'Linux kernel 7.2 \u00b7 GPL-2.0 \u00b7 kernel.org'),
             ('p', 'U-Boot bootloader \u00b7 GPL-2.0 \u00b7 source.denx.de/u-boot/u-boot'),
             ('p', 'RetroArch \u00b7 GPL-3.0 \u00b7 github.com/libretro/RetroArch'),
             ('p', 'libretro cores (mGBA, gpSP, Gambatte, Snes9x, Genesis Plus GX, PCSX ReARMed, FCEUmm and others) \u00b7 each core\u2019s own license \u00b7 github.com/libretro'),
             ('p', 'PPSSPP \u00b7 GPL-2.0 or later \u00b7 github.com/hrydgard/ppsspp'),
             ('p', 'Flycast \u00b7 GPL-2.0 \u00b7 github.com/flyinghead/flycast'),
             ('p', 'Mupen64Plus \u00b7 GPL-2.0 \u00b7 github.com/mupen64plus'),
             ('p', 'DuckStation \u00b7 its own license \u00b7 github.com/stenzek/duckstation'),
             ('p', 'Yaba Sanshiro \u00b7 GPL-2.0 \u00b7 github.com/devmiyax/yabause'),
             ('p', 'Mednafen \u00b7 GPL-2.0 \u00b7 mednafen.github.io'),
             ('p', 'ScummVM \u00b7 GPL-3.0 or later \u00b7 github.com/scummvm/scummvm'),
             ('p', 'GZDoom \u00b7 GPL-3.0 \u00b7 github.com/ZDoom/gzdoom'),
             ('p', 'Amiberry \u00b7 GPL-3.0 \u00b7 github.com/BlitterStudio/amiberry'),
             ('p', 'Hatari \u00b7 GPL-2.0 \u00b7 github.com/hatari/hatari'),
             ('p', 'PortMaster \u00b7 MIT \u00b7 github.com/PortsMaster/PortMaster-GUI'),
             ('p', 'DraStic (Nintendo DS) \u00b7 closed-source freeware, not open source \u00b7 drastic-ds.com'),
             ('p', 'Sway and wlroots \u00b7 MIT \u00b7 github.com/swaywm'),
             ('p', 'Mesa (Panfrost graphics) \u00b7 MIT \u00b7 gitlab.freedesktop.org/mesa/mesa'),
             ('p', 'systemd \u00b7 LGPL-2.1 or later \u00b7 github.com/systemd/systemd'),
             ('p', 'BusyBox \u00b7 GPL-2.0 \u00b7 busybox.net'),
             ('p', 'NetworkManager \u00b7 GPL-2.0 or later \u00b7 networkmanager.dev'),
             ('p', 'Samba (network share) \u00b7 GPL-3.0 \u00b7 samba.org'),
             ('p', 'Python \u00b7 PSF License \u00b7 python.org'),
             ('p', 'SDL2, SDL2_ttf, SDL2_image, SDL2_mixer \u00b7 zlib \u00b7 libsdl.org'),
             ('p', 'FreeType \u00b7 FreeType License \u00b7 freetype.org'),
             ('p', 'Manrope typeface \u00b7 SIL OFL 1.1 \u00b7 github.com/sharanda/manrope'),
             ('h', 'Notes'),
             ('p', 'No games or BIOS files are included. Made for %s. Not affiliated with any handheld maker or with the projects above. Thank you to every team listed in Credits.' % FAMILY.replace('handhelds', 'devices'))]

    def draw_about(self):
        g, c, o = self.g, self.c, self.opt
        th = self.topbar('Settings')
        y = th + self.header('About & licenses', None, 0, th)
        px = 24 if o == 2 else 28
        top = y; bot = self.H - HINT_H[o]
        g.clip(0, top, self.W, bot - top)
        yy = top - self.about_y * 40
        for kind, txt in self.ABOUT:
            if kind == 'h':
                yy += 10; g.text(txt, px, yy, 700, 22 * self.fz, c['fg'], lineh=22 * self.fz * 1.4); yy += 22 * self.fz * 1.4 + 2
            else:
                for ln in g.wrap(txt, 500, 19 * self.fz, self.W - 2 * px):
                    g.text(ln, px, yy, 500, 19 * self.fz, c['dim'], lineh=19 * self.fz * 1.5); yy += 19 * self.fz * 1.5
        self.about_max = max(0, int((yy + self.about_y * 40 - bot) / 40) + 1)
        g.clip()
        self.hints([['▲▼', 'Scroll', 'l'], ['B', 'Back']])

    def key_about(self, k):
        if k in ('b', 'menu'): return self.go('settings', True)
        if k in ('up', 'down'):
            self.about_y = clamp(self.about_y + (-1 if k == 'up' else 1), 0, getattr(self, 'about_max', 6)); self.dirty = True

    # Look
    def look_items(self):
        L = self.look; c = self.c
        def slot_rt(S):
            if not S: return [('t', 'Empty')]
            nm = LK.named(LK.ACCENTS, S['ac'])[1]
            return [('sw', LK.colors(S)['ac']), ('t', nm + ' · ' + LK.named(LK.LAYOUTS, S['layout'])[1])]
        onoff = lambda v: 'On' if v else 'Off'
        it = [{'k': 'theme', 'label': 'Theme', 'rt': [('arrows', LK.look_name(L))]},
              {'k': 'layout', 'label': 'Layout', 'rt': [('arrows', LK.named(LK.LAYOUTS, L['layout'])[1])]},
              {'k': 'ac', 'label': 'Accent color', 'rt': [('sw', c['ac']), ('arrows', LK.named(LK.ACCENTS, L['ac'])[1])]},
              {'k': 'text', 'label': 'Text color', 'rt': [('arrows', LK.named(LK.TEXTS, L['text'])[1])]},
              {'k': 'bg', 'label': 'Background', 'rt': [('arrows', LK.named(LK.BGS, L['bg'])[1])]},
              {'k': 'size', 'label': 'Text size', 'rt': [('arrows', LK.named(LK.SIZES, L['size'])[1])]},
              {'k': 'clock', 'label': 'Show clock', 'rt': [('arrows', onoff(L['clock']))]},
              {'k': 'batt', 'label': 'Show battery', 'rt': [('arrows', onoff(L['batt']))], 'sep': True}]
        for i in range(3):
            it.append({'k': 'slot', 'i': i, 'label': 'Custom %d' % (i + 1), 'rt': slot_rt(self.slots[i]), 'sep': i == 2})
        it.append({'k': 'reset', 'label': 'Reset to default', 'rt': []})
        return it

    def draw_look(self):
        g, c, o = self.g, self.c, self.opt
        it = self.look_items(); s = it[self.s('look', len(it))]
        hint = [['◂▸', 'Change', 'l']] + ([['Y', 'Save here']] if s['k'] == 'slot' else []) + [['B', 'Back'], ['A', ('Load' if self.slots[s['i']] else 'Save here') if s['k'] == 'slot' else ('Reset' if s['k'] == 'reset' else 'Pick color' if s['k'] == 'ac' else 'Next')]]
        if o == 3:
            return self.frame('Settings', aside={'cap': 'Settings · Look', 'big': 'Aa', 'sub': LK.look_name(self.look), 'preview': True},
                              body=lambda x, y, w, h: self.list_view('look', it, x, y, w, h), hint=hint)
        th = self.topbar('Settings')
        y0 = th + (10 if o == 2 else 0)
        # header with preview box on the right
        hh = self.header('Look', 'Changes show right away' + ('' if o == 2 else '.'), 0, y0, 0, self.W - 190 - 16)
        pvh = self.lookpv_h()
        px = 24 if o == 2 else 28
        self.lookpv(self.W - px - 190, y0 + (6 if o != 2 else 14), 190)
        y = y0 + max(hh, pvh + (16 if o != 2 else 22))
        self.list_view('look', it, 0, y, self.W, self.H - y - HINT_H[o])
        self.hints(hint)

    def key_look(self, k):
        it = self.look_items(); s = self.s('look', len(it)); row = it[s]; L = dict(self.look)
        if k in ('b', 'menu'): return self.go('settings', True)
        if k in ('up', 'down'): return self.nav('look', len(it), k)
        d = -1 if k == 'left' else 1
        change = k in ('left', 'right', 'a')
        def cyc(lst, cur):
            ids = [x['id'] if isinstance(x, dict) else x[0] for x in lst]
            i = ids.index(cur) if cur in ids else 0
            return ids[(i + d) % len(ids)]
        if row['k'] == 'slot':
            i = row['i']
            if k == 'y' or (k == 'a' and not self.slots[i]):
                self.slots[i] = dict(self.look); self.persist(); return self.toast('Saved to Custom %d' % (i + 1))
            if k == 'a':
                self.set_look(dict(self.slots[i])); return self.toast('Custom %d loaded' % (i + 1))
            return
        if row['k'] == 'reset':
            if k == 'a': self.set_look(dict(LK.DEFAULT)); self.toast('Back to the default look')
            return
        if not change: return
        if row['k'] == 'ac' and k == 'a': self.sel['color'] = 0; return self.go('color')
        if row['k'] == 'theme': return self.set_look(LK.theme_look(cyc(LK.THEMES, L['theme']), L))
        if row['k'] == 'layout': L['layout'] = cyc(LK.LAYOUTS, L['layout'])
        elif row['k'] == 'ac': L['ac'] = cyc(LK.ACCENTS, L['ac'])
        elif row['k'] == 'text': L['text'] = cyc(LK.TEXTS, L['text'])
        elif row['k'] == 'bg': L['bg'] = cyc(LK.BGS, L['bg'])
        elif row['k'] == 'size': L['size'] = cyc(LK.SIZES, L['size'])
        elif row['k'] == 'clock': L['clock'] = not L['clock']
        elif row['k'] == 'batt': L['batt'] = not L['batt']
        self.set_look(L)

    # Accent color picker: hue 0-359 in 1° steps (hold to speed up), saturation and brightness 0-100 in 5% steps.
    # The 13 named accents are presets that set these values. 100/100 is the pure color; it is only adjusted
    # (lightened on dark pages, deepened on light ones) when it would be hard to read.
    def color_hsv(self):
        L = self.look
        return (L['hue'], L['sat'], L['val']) if L['ac'] == 'hue' else LK.preset_hsv(L['ac'])

    def color_items(self):
        h, sat, val = self.color_hsv()
        return [{'k': 'preset', 'label': 'Preset', 'rt': [('sw', LK.accent_raw(self.look)), ('arrows', LK.named(LK.ACCENTS, self.look['ac'])[1])]},
                {'k': 'hue', 'label': 'Hue', 'rt': [('hue', h, True)]},
                {'k': 'sat', 'label': 'Saturation', 'rt': [('bar', sat, 100), ('t', '%d%%' % sat)]},
                {'k': 'val', 'label': 'Brightness', 'rt': [('bar', val, 100), ('t', '%d%%' % val)]},
                {'k': 'reset', 'label': 'Reset to the theme\u2019s color', 'rt': []}]

    def color_swatch_h(self):
        return round(64 * self.fz) + 20

    def draw_color(self):
        g, c, o, fz = self.g, self.c, self.opt, self.fz
        it = self.color_items()
        th = self.topbar('Settings')
        y = th + self.header('Accent color', 'Hold left or right to move faster.', 0, th)
        px = 24 if o == 2 else 28
        sh = round(64 * fz)
        raw = LK.accent_raw(self.look)
        # live swatch: the exact color picked
        sw = round(sh * 1.6)
        g.rrect(px, y, sw, sh, 10, raw)
        g.ring(px, y, sw, sh, 10, c['faint'], sw=1)
        # sample row: how lists, highlights and buttons look with it
        sx = px + sw + 16; rw = self.W - px - sx
        rh = round(30 * fz)
        g.rrect(sx, y, rw, rh, 8, c['ac'], c['acbg_a']); g.fill(sx, y + 3, 3, rh - 6, c['ac'])
        fs = 19 * fz
        g.text('Game Boy Advance', sx + 12, y, 700, fs, c['fg'], lineh=rh, maxw=rw - 70)
        n = '14'; g.text(n, sx + rw - 12 - g.measure(n, 700, fs), y, 700, fs, c['ac'], lineh=rh)
        by = y + rh + 8; bh = sh - rh - 8
        lab = 'Play'; bw = g.measure(lab, 800, 17 * fz) + 28
        g.rrect(sx, by, bw, bh, bh / 2.0, c['ac']); g.text(lab, sx + 14, by, 800, 17 * fz, c['onac'], lineh=bh)
        note = raw.upper() + ('  \u00b7  adjusted to stay readable' if c['ac'].upper() != raw.upper() else '')
        g.text(note, sx + bw + 12, by, 600, 17 * fz, c['dim'], lineh=bh, maxw=rw - bw - 12)
        y += sh + 14
        self.list_view('color', it, 0, y, self.W, self.H - y - HINT_H[o])
        self.hints([['\u25c2\u25b8', 'Change', 'l'], ['B', 'Back'], ['A', 'Reset' if it[self.s('color', len(it))]['k'] == 'reset' else 'Done']])

    def key_color(self, k):
        it = self.color_items(); row = it[self.s('color', len(it))]
        if k in ('b', 'menu') or (k == 'a' and row['k'] != 'reset'):
            self.persist(); return self.go('look', True)
        if k in ('up', 'down'): return self.nav('color', len(it), k)
        L = dict(self.look)
        if row['k'] == 'reset':
            if k != 'a': return
            t = next((x for x in LK.THEMES if x['id'] == L['theme']), LK.THEMES[0])
            L['ac'] = t['ac']; L['hue'], L['sat'], L['val'] = LK.preset_hsv(t['ac'])
            self.set_look(L); return self.toast('Back to the theme\u2019s color')
        if k not in ('left', 'right'): return
        d = -1 if k == 'left' else 1
        now = time.time(); rk, rt, rn = getattr(self, '_crep', (None, 0, 0))
        rn = rn + 1 if (rk == (row['k'], k) and now - rt < .2) else 0
        self._crep = ((row['k'], k), now, rn)
        if row['k'] == 'preset':
            ids = [a[0] for a in LK.ACCENTS if a[2]]
            i = ids.index(L['ac']) if L['ac'] in ids else (-1 if d > 0 else 0)
            L['ac'] = ids[(i + d) % len(ids)]; L['hue'], L['sat'], L['val'] = LK.preset_hsv(L['ac'])
            return self.set_look(L)
        h, sat, val = self.color_hsv()
        if row['k'] == 'hue':
            step = 1 if rn < 6 else 4 if rn < 18 else 12
            h = (round(h) + d * step) % 360
        elif row['k'] == 'sat': sat = LK.clamp(sat + d * 5, 0, 100)
        elif row['k'] == 'val': val = LK.clamp(val + d * 5, 0, 100)
        L.update(ac='hue', hue=h, sat=sat, val=val)
        self.look = LK.clean(L); self.apply_look(); self._look_pending = now   # saved when leaving, or 2 s after the last change

    # Tools
    def tool_list(self):
        return [t for t in TOOLS if self.dev.tool_available(t)]

    def draw_tools(self):
        tl = self.tool_list()
        it = [{'label': t[1], 'rt': [('t', t[2])] if self.opt != 3 else [], 't': t} for t in tl]
        cur = tl[self.s('tools', len(tl))] if tl else None
        self.frame('Tools', 'Tools', 'Press Menu in a tool, then Quit, to come back here.', 0,
                   {'cap': 'Tools', 'big': cur[1] if cur else 'Tools', 'sm': True, 'sub': cur[2] if cur else ''},
                   lambda x, y, w, h: self.list_view('tools', it, x, y, w, h, empty='No tools available'), [['B', 'Back'], ['A', 'Open']])

    def key_tools(self, k):
        tl = self.tool_list(); n = len(tl)
        if k in ('b', 'menu'): return self.go('home', True)
        if k == 'a' and n:
            t = tl[self.s('tools', n)]; how = t[3]
            if how[0] == 'app':
                if how[1] == 'music': return self.open_music()
                if how[1] == 'macclean':
                    n = self.dev.clean_mac_files(); return self.toast('Removed %d Mac file%s' % (n, '' if n == 1 else 's'))
                if how[1] == 'rescan':
                    self.rescan(); return self.toast('Game list refreshed')
                if how[1] == 'scummvm':
                    self.toast('Looking for ScummVM games…')
                    def done(n):
                        self.rescan(); self.toast('ScummVM: %d game%s found' % (n, '' if n == 1 else 's'))
                    self.dev.scan_scummvm(done); return
                return
            if not self.dev.mock and self.dev.game_running():
                self._pending_launch = ('tool', t)
                self._pending_until = time.time() + 4.0
                return self.toast('Closing the last game…')
            return self._start_tool(t)
        self.nav('tools', n, k)

    # Music player (built in)
    def open_music(self):
        self.player = MU.Player(); self.player.scan()
        self.sel['music'] = 0; self.go('music')

    def draw_music(self):
        P = self.player or MU.Player()
        it = [{'label': P.title(i), 'rt': ([('t', 'Paused' if P.paused else 'Playing')] if i == P.cur else [])} for i in range(len(P.tracks))]
        now = P.title() if P.cur >= 0 else ''
        sub = (('Paused · ' if P.paused else 'Playing · ') + now) if now else (P.err or ('%d tracks' % len(P.tracks) if P.tracks else 'Put music files in roms/music on your card'))
        self.frame('Tools', 'Music', sub, 0, {'cap': 'Music player', 'big': str(len(P.tracks)), 'sub': now or 'tracks'},
                   lambda x, y, w, h: self.list_view('music', it, x, y, w, h, empty='No music yet: add files to roms/music'),
                   [['◂▸', 'Track', 'l'], ['Y', 'Pause'], ['B', 'Back'], ['A', 'Play']])

    def key_music(self, k):
        P = self.player
        if k in ('b', 'menu'):
            if P: P.close()
            self.player = None; return self.go('tools', True)
        if not P or not P.tracks: return
        n = len(P.tracks)
        if k == 'a':
            if not P.play(self.s('music', n)): self.toast(P.err or "Can't play that file")
        elif k == 'y': P.toggle()
        elif k in ('left', 'right'):
            P.step(-1 if k == 'left' else 1)
            if P.cur >= 0: self.sel['music'] = P.cur
        else: self.nav('music', n, k)

    # Device model (device tree on the boot partition): retail names; panel variants are one "alternate screen" toggle
    def model_rows(self):
        cur = self.dev.current_model(); ci, calt = model_of(cur)
        rows = [{'label': nm, 'rt': ([('t', 'Alternate screen')] if (i == ci and calt) else []) + ([('ico', 'check')] if i == ci else []), 'pick': (std, nm)}
                for i, (nm, std, alt) in enumerate(MODELS)]
        if ci >= 0 and MODELS[ci][2]:
            nm, std, alt = MODELS[ci]
            to = std if calt else alt
            rows.insert(ci + 1, {'label': 'Screen looks wrong? Try %s screen' % ('standard' if calt else 'alternate'), 'sep': False,
                         'col': self.c['ac'], 'pick': (to, nm + (' (alternate screen)' if to == alt else ''))})
        return rows

    def draw_model(self):
        it = self.model_rows()
        self.frame('Settings', 'Device model', 'Pick your handheld. sdOS restarts to apply it.', 0,
                   {'cap': 'Settings · Device model', 'big': self.model_label(), 'sm': True, 'sub': 'Running now'},
                   lambda x, y, w, h: self.list_view('model', it, x, y, w, h), [['B', 'Back'], ['A', 'Choose']])

    def key_model(self, k):
        it = self.model_rows()
        if k in ('b', 'menu'): return self.go('settings', True)
        if k == 'a':
            d, m = it[self.s('model', len(it))]['pick']
            if d == self.dev.current_model(): return self.toast('Already set to ' + m)
            self.mtrial_prefer_keep = False
            self.setup_resume = ''
            self.confirm_back = 'model'
            self.confirm = ('model', d, m); self.sel['confirm'] = 0; self.persist(); return self.go('confirm')
        self.nav('model', len(it), k)

    # First boot after a model switch: keep it, or go back automatically after 30 s
    MTRIAL_SECS = 30

    def draw_mtrial(self):
        if not getattr(self, 'mtrial', None):
            self.go(getattr(self, 'mtrial_back', None) or 'settings', True); return
        new, prev = self.mtrial
        left = max(0, int(self.mtrial_deadline - time.time() + .99))
        it = [{'label': 'Keep %s' % model_name(new)}, {'label': 'Go back to %s' % model_name(prev)}]
        title = 'Setup' if (not self.setup_done or self.mtrial_prefer_keep) else 'Settings'
        self.frame(title, 'Does the screen look right?', 'Going back to the previous model in %d s.' % left, 0,
                   {'cap': 'New device model', 'big': '%d' % left, 'sub': 'seconds left'},
                   lambda x, y, w, h: self.list_view('mtrial', it, x, y, w, h), [['B', 'Go back'], ['A', 'Select']])

    def key_mtrial(self, k):
        if k == 'a' and self.s('mtrial', 2) == 0:
            self.dev.confirm_model(); self.mtrial = None; self.toast('Device model saved')
            self.setup_model_done = True
            self.model_prompted = True
            self.mtrial_prefer_keep = False
            dest = self.setup_resume or self.mtrial_back or ('home' if self.setup_done else 'lang')
            self.setup_resume = ''
            self.persist()
            if dest in ('lang', 'wifi', 'kb', 'tz', 'time', 'card', 'copy'):
                self.ctx = 'setup'; self.setup_done = False
            elif dest == 'devpick':
                dest = 'lang' if not self.setup_done else 'home'
            if dest == 'home':
                self.ctx = 'home'
            return self.go(dest)
        if k in ('a', 'b'):
            self.mtrial_deadline = 0; self.dirty = True; return
        self.nav('mtrial', 2, k)

    # Confirm (restart / shut down / model switch)
    def confirm_text(self):
        c = self.confirm or ('restart',)
        if c[0] == 'shutdown': return 'Shut down?', 'sdOS will turn the handheld off.', 'Shut down now'
        if c[0] == 'model': return 'Switch to %s?' % c[2], 'sdOS restarts. If you can\u2019t confirm the new screen within 30 s, it goes back to this one.', 'Switch and restart'
        return 'Restart?', 'sdOS will close and start again.', 'Restart now'

    def draw_confirm(self):
        h1, sub, yes = self.confirm_text()
        if self.powering:
            g, c = self.g, self.c
            t = self.powering
            g.text(t, (self.W - g.measure(t, 800, 26)) / 2.0, self.H / 2.0 - 20, 800, 26, c['fg'])
            return
        it = [{'label': yes, 'rt': []}, {'label': 'Cancel', 'rt': []}]
        title = 'Setup' if (self.confirm_back == 'devpick' or not self.setup_done) else 'Settings'
        self.frame(title, h1, sub, 0, {'cap': title, 'big': h1.rstrip('?'), 'sm': True, 'sub': sub},
                   lambda x, y, w, h: self.list_view('confirm', it, x, y, w, h), [['B', 'Cancel'], ['A', 'Select']])

    def key_confirm(self, k):
        if self.powering: return
        c = self.confirm or ('restart',)
        back = self.confirm_back or ('model' if c[0] == 'model' else 'settings')
        if k in ('b', 'menu'): return self.go(back, True)
        if k == 'a':
            if self.s('confirm', 2) == 1: return self.go(back, True)
            if self.player: self.player.close(); self.player = None
            if c[0] == 'model':
                if not self.dev.set_model(c[1]): return self.toast("Couldn't change the model")
                self.powering = 'Restarting…'; self.persist(); self.dev.power('restart'); return
            self.powering = 'Shutting down…' if c[0] == 'shutdown' else 'Restarting…'
            self.persist(); self.dev.power(c[0]); return
        self.nav('confirm', 2, k)

    # ---------- input ----------
    def nav(self, key, n, k):
        if not n: return
        s = self.s(key, n)
        if k == 'up': self.sel[key] = (s - 1 + n) % n
        elif k == 'down': self.sel[key] = (s + 1) % n
        else: return
        self.dirty = True

    def key(self, k):
        self.last_input = time.time()
        # Start arrives as 'menu' from the gamepad map. On setup screens it confirms
        # the highlighted action, like A. The on-screen keyboard keeps Start = Join.
        if k == 'menu' and self.setup_start_confirms():
            k = 'a'
        h = getattr(self, 'key_' + self.screen, None)
        if h: h(k)
        self.dirty = True

    def sleep_held(self):
        """Do not idle-sleep during setup, background work, updates, or an active transfer."""
        if (not self.setup_done) or self.ctx == 'setup':
            return True
        if self.screen in ('devpick', 'lang', 'wifi', 'kb', 'tz', 'time', 'card', 'copy', 'hask'):
            return True
        if any(self.dev.busy.values()):
            return True
        if self.upd in ('checking', 'reboot'):
            return True
        if self.dev.activity_busy():
            return True
        return False

    def tick(self):
        """Housekeeping each loop: events from background jobs, game exit, idle sleep."""
        if getattr(self, '_look_pending', 0) and time.time() - self._look_pending > 2:
            self._look_pending = 0; self.persist()
        for kind, text in self.dev.drain():
            if kind in ('wifi_ok', 'wifi_fail'): self.on_wifi(kind, text)
            elif kind == 'upd': self.on_upd(text)
            elif kind in ('bt_ok', 'bt_fail', 'bt_nohw', 'bt_audio', 'bt_list'): self.on_bt(kind, text)
            elif kind == 'call' and callable(text): text()
            self.dirty = True
        if not self.dev.mock and self.dev.proc is not None and not self.dev.game_running():
            tool = self.is_tool()
            still = self.screen in ('game', 'settings', 'look', 'about', 'wifi', 'kb', 'bt')
            self.dev.proc = None; self.game = None
            if still and not self._pending_launch:
                self.on_game_exit(tool)
        if self._pending_launch and not self.dev.mock:
            kind, payload = self._pending_launch
            if not self.dev.game_running():
                if kind == 'game':
                    self._start_game(payload)
                else:
                    self._start_tool(payload)
                self.dirty = True
            elif time.time() > self._pending_until:
                self._pending_launch = None
                self.toast('Still closing the last game…')
        if not getattr(self, '_mtrial_checked', False) and self.screen != 'boot' and not self.shot:
            self._mtrial_checked = True
            if self.screen != 'mtrial':
                tr = self.dev.model_trial()
                if tr:
                    self.mtrial = tr
                    self.mtrial_back = self.setup_resume or self.screen
                    self.mtrial_deadline = time.time() + self.MTRIAL_SECS
                    # Settings path starts on Go back (broken-screen safety). Setup/hask prefers Keep.
                    self.sel['mtrial'] = 0 if self.mtrial_prefer_keep else 1
                    self.go('mtrial')
        if self.screen == 'mtrial' and getattr(self, 'mtrial', None):
            self.dirty = True
            if time.time() >= self.mtrial_deadline:
                self.mtrial = None
                self.mtrial_prefer_keep = False
                self.persist()
                self.toast('Going back to the previous model'); self.dev.revert_model()
        if self.screen == 'music' and self.player and self.player.finished():
            self.player.step(1); self.dirty = True
        if self.screen == 'wifi' and not self.dev.mock and not self.dev.busy.get('scan') and not self.dev.wifi_list() \
                and not self.dev.busy.get('connect') and self._wifi_auto[0] < 6 and time.time() - self._wifi_auto[1] > 4:
            self._wifi_auto = [self._wifi_auto[0] + 1, time.time()]; self.dev.wifi_scan(); self.dirty = True
        if self.screen == 'wifi' and self.dev.busy.get('scan'): self.dirty = True
        if self.sleep_held():
            self.last_input = time.time()
        try:
            secs = SLEEP[self.sleep][1]
        except Exception:
            secs = 0
        in_game = ((not self.dev.mock) and self.dev.game_running()) or bool(self.player and self.player.mus and not self.player.paused)
        # Never (secs == 0) disables idle suspend. There is no separate ROCKNIX idle timer.
        if secs and not in_game and not self.shot and time.time() - self.last_input > secs:
            self.last_input = time.time(); self.dev.suspend()
        # OTA probation: once the UI has run 8 s, the new app layer is confirmed good
        if not self.dev.mock and not self.shot and not getattr(self, '_ota_checked', False) and time.time() - self.t_boot > 8:
            self._ota_checked = True
            try:
                from . import ota
                rb = ota.rolled_back()
                if rb: self.toast("Update %s didn't start, so sdOS went back" % rb)
                ok = ota.confirm()
                if ok: self.toast('Updated to sdOS %s' % ok)
            except Exception:
                pass
        # refresh the clock about every 15 s
        if int(time.time()) % 15 == 0 and getattr(self, '_last_clock', 0) != int(time.time()):
            self._last_clock = int(time.time()); self.dirty = True

    def in_game_hidden(self):
        """True while a game is on screen and the overlay is closed (don't draw)."""
        return (not self.dev.mock) and self.screen == 'game' and not self.ovl and self.dev.game_running()

    # ---------- screenshot helper: jump straight to a screen state ----------
    def jump_to(self, name):
        self.toast_ = None; self.anim = {}
        setup = ['devpick', 'lang', 'wifi', 'kb', 'tz', 'time', 'card', 'copy']
        if name in setup: self.setup_done = False; self.ctx = 'setup'
        else:
            self.setup_done = True; self.ctx = 'home'
            if self.dev.mock and not self.dev.wifi_status: self.dev.wifi_status = 'Home Network'
        if name == 'devpick':
            self.dev.wifi_status = None
            self.sel['devpick'] = self.setup_model_index()
        if name == 'hask':
            self.setup_done = True; self.ctx = 'home'
            self.sel['hask'] = 0
        if name in ('wifi', 'lang'): self.dev.wifi_status = None
        if name == 'kb': self.dev.wifi_status = None; self.pw_for = 'Home Network'; self.pw = 'Sun$et-4!'; self.pw_cur = len(self.pw); self.pw_last = len(self.pw) - 1; self.kb = [2, 4]; self.kb_sym = False
        if name in ('time', 'card', 'copy', 'tz'): self.dev.wifi_status = 'Home Network'
        if name == 'card': self.sel['card'] = 0
        if name == 'copy': self.card = 1; self.copy_path = 'GAMES drive › roms'
        if name == 'home': self.sel['home'] = 2
        if name == 'games': self.sys = 'gba'; self.sel['games'] = 2
        if name == 'ingame':
            sy = self.sys_by('psp'); self.game = sy['games'][2]; self.ovl = True; self.sel['ovl'] = 0; self.saved = True
            return self.go('game')
        if name == 'settings': self.sel['settings'] = 0
        if name in ('swapab', 'swapxy'):
            want = 'swap_ab' if name == 'swapab' else 'swap_xy'
            keys = [r['k'] for r in self.set_items()]
            self.sel['settings'] = keys.index(want) if want in keys else 0
        if name in ('bt', 'btoff', 'btscan'):
            self.dev.has_bt = True
            if name == 'btoff':
                self.dev._bt_on = False
                self.dev.bt_paired = []
                self.dev.busy['bt_scan'] = False
                self.sel['bt'] = 0
            elif name == 'btscan':
                self.dev._bt_on = True
                self.dev.bt_paired = []
                self.dev.busy['bt_scan'] = True
                self.sel['bt'] = 2
            else:
                self.dev._bt_on = True
                self.dev.busy['bt_scan'] = False
                pad = {'mac': 'E4:17:D8:11:22:33', 'name': '8BitDo SN30 Pro', 'type': 'joystick', 'connected': True, 'status': ''}
                phones = {'mac': '00:1A:7D:DA:71:13', 'name': 'WH-1000XM4', 'type': 'audio', 'connected': False, 'status': ''}
                self.dev.bt_paired = [pad, phones]
                self.dev.bt_found = []
                self.sel['bt'] = 2
        if name == 'tools': self.sel['tools'] = 0
        if name == 'confirm': self.confirm = ('shutdown',); self.sel['confirm'] = 0
        if name == 'mtrial':
            self.mtrial = ((MODELS[0][2] or MODELS[1][1]), MODELS[0][1]); self.mtrial_back = 'settings'
            self.mtrial_deadline = time.time() + 24.2; self.sel['mtrial'] = 1
            self.mtrial_prefer_keep = False
        if name == 'mtrialkeep':
            self.setup_done = False; self.ctx = 'setup'
            self.mtrial = (MODELS[1][1], MODELS[0][1]); self.mtrial_back = 'lang'
            self.mtrial_deadline = time.time() + 24.2; self.sel['mtrial'] = 0
            self.mtrial_prefer_keep = True
            self.setup_resume = 'lang'
        if name == 'model': self.sel['model'] = 0
        if name == 'look': self.sel['look'] = self.sel.get('look', 0)
        if name == 'color': self.sel['color'] = 1
        self.go('mtrial' if name == 'mtrialkeep' else ('bt' if name in ('btoff', 'btscan') else ('settings' if name in ('swapab', 'swapxy') else name)))
