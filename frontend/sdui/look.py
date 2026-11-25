# Look system: themes + customization.
# Every look is forced legible: text >= 10:1, secondary >= 4.6:1, accent >= 4.5:1.
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
# Accent presets (ids kept from 0.1.x so saved looks still load; names are the Static Divisions set).
ACCENTS = [('teal', 'Signal', '#00E5CC'), ('amber', 'Ember', '#FFB23F'), ('magenta', 'Pulse', '#FF4FD8'),
           ('ice', 'Glacier', '#9EF0FF'), ('lime', 'Phosphor', '#7CFFB2'), ('violet', 'Ultraviolet', '#B98CFF'),
           ('blue', 'Cobalt', '#5AA8FF'), ('coral', 'Flare', '#FF8A5B'), ('gold', 'Halo', '#FFC857'),
           ('white', 'Chrome', '#F2F2F2'), ('red', 'Siren', '#FF4D5E'), ('volt', 'Volt', '#E4FF3A'),
           ('rose', 'Bloom', '#FF77A8'), ('hue', 'Custom', None)]
LAYOUTS = [('roomy', 'Roomy', 1), ('dense', 'Dense', 2), ('split', 'Split', 3)]
TEXTS = [('white', 'Neutral'), ('warm', 'Warm'), ('cool', 'Cool'), ('tint', 'Tint')]
# Backgrounds: the first three are dark, the last three light (dark text).
BGS = [('tinted', 'Tinted'), ('graphite', 'Graphite'), ('deep', 'Deep'), ('paper', 'Paper'), ('frost', 'Frost'), ('bright', 'Bright')]
LIGHT_BGS = ('paper', 'frost', 'bright')
SIZES = [('s', 'Small', .88), ('m', 'Medium', 1.0), ('l', 'Large', 1.14)]
# 13 presets, all Roomy so they match. 8 dark, 5 light.
THEMES = [
    dict(id='teal', name='Signal Monolith', layout='roomy', ac='teal', text='tint', bg='tinted'),
    dict(id='amber', name='Ember Grid', layout='roomy', ac='amber', text='warm', bg='tinted'),
    dict(id='magenta', name='Pulse Theory', layout='roomy', ac='magenta', text='tint', bg='tinted'),
    dict(id='ice', name='Glacier Relay', layout='roomy', ac='ice', text='cool', bg='deep'),
    dict(id='lime', name='Phosphor Field', layout='roomy', ac='lime', text='white', bg='graphite'),
    dict(id='violet', name='Ultraviolet Hour', layout='roomy', ac='violet', text='cool', bg='deep'),
    dict(id='deadch', name='Dead Channel', layout='roomy', ac='red', text='warm', bg='graphite'),
    dict(id='mono', name='Graphite Slab', layout='roomy', ac='white', text='white', bg='graphite'),
    dict(id='blueprint', name='Blueprint Zero', layout='roomy', ac='blue', text='cool', bg='frost'),
    dict(id='daylight', name='Daylight Signal', layout='roomy', ac='teal', text='tint', bg='paper'),
    dict(id='solar', name='Solar Slab', layout='roomy', ac='amber', text='warm', bg='paper'),
    dict(id='bloom', name='Frost Bloom', layout='roomy', ac='rose', text='tint', bg='frost'),
    dict(id='whitenoise', name='White Noise', layout='roomy', ac='white', text='white', bg='bright'),
]
DEFAULT = dict(theme='teal', layout='roomy', ac='teal', hue=174, sat=100, val=90, text='tint', bg='tinted', size='m', clock=True, batt=True)

def named(lst, k):
    for x in lst:
        if x[0] == k:
            return x
    return lst[0]

def opt_of(layout): return named(LAYOUTS, layout)[2]
def fz(L): return named(SIZES, L['size'])[2]

def clamp(v, a, b): return max(a, min(b, v))
def hx(h): return [int(h[i:i + 2], 16) for i in (1, 3, 5)]
def xh(a): return '#' + ''.join('%02X' % int(round(clamp(v, 0, 255))) for v in a)
def mix(a, b, t):
    A, B = hx(a), hx(b); return xh([v + (B[i] - v) * t for i, v in enumerate(A)])
def lum(h):
    c = [(v / 255) / 12.92 if v / 255 <= .03928 else ((v / 255 + .055) / 1.055) ** 2.4 for v in hx(h)]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
def contrast(a, b):
    x, y = lum(a), lum(b); return (max(x, y) + .05) / (min(x, y) + .05)
def hsl(h, s, l):
    s /= 100; l /= 100
    def f(n):
        k = (n + h / 30) % 12; a = s * min(l, 1 - l)
        return 255 * (l - a * max(-1, min(k - 3, 9 - k, 1)))
    return xh([f(0), f(8), f(4)])
def hue_of(hexs):
    r, g, b = [v / 255 for v in hx(hexs)]; mx, mn = max(r, g, b), min(r, g, b); d = mx - mn
    if not d: return 0, 0
    if mx == r: h = ((g - b) / d) % 6
    elif mx == g: h = (b - r) / d + 2
    else: h = (r - g) / d + 4
    return (h * 60 + 360) % 360, d

def hsv(h, s, v):
    """Hue 0-360, saturation and brightness 0-100. 100/100 is the pure, full-strength color."""
    s, v = clamp(s, 0, 100) / 100.0, clamp(v, 0, 100) / 100.0
    def f(n):
        k = (n + h / 60.0) % 6
        return 255 * (v - v * s * max(0, min(k, 4 - k, 1)))
    return xh([f(5), f(3), f(1)])

def hsv_of(hexs):
    r, g, b = [x / 255.0 for x in hx(hexs)]; mx, mn = max(r, g, b), min(r, g, b)
    h, _ = hue_of(hexs)
    return round(h) % 360, round(100 * ((mx - mn) / mx if mx else 0)), round(100 * mx)

def preset_hsv(ac):
    hexs = named(ACCENTS, ac)[2]
    return hsv_of(hexs) if hexs else None

def accent_raw(L): return hsv(L['hue'], L['sat'], L['val']) if L['ac'] == 'hue' else named(ACCENTS, L['ac'])[2]
def accent_hex(L): return accent_raw(L)

def is_light(L): return L.get('bg') in LIGHT_BGS

def colors(L):
    ac = accent_hex(L); h, s = hue_of(ac); grey = s < .05
    t = L['text']
    if is_light(L):
        if L['bg'] == 'bright': bg = '#F6F7F7'
        elif L['bg'] == 'paper': bg = '#F2EEE6'
        elif grey: bg = '#ECEFF1'
        else: bg = hsl(h, 38, 94)
        fg = '#2A2016' if t == 'warm' else '#13202E' if t == 'cool' else mix('#141718', ac, .14) if t == 'tint' else '#16191B'
        while contrast(fg, bg) < 10: fg = mix(fg, '#000000', .2)
        if L['ac'] == 'hue': ac = ac          # custom: the chosen color, darkened below only as far as contrast needs
        else: ac = '#2B2F33' if grey else hsl(h, 92, 36)   # preset: same hue, deepened for a light page
        while contrast(ac, bg) < 4.5: ac = mix(ac, '#000000', .08)
        dim = mix(fg, bg, .45)
        while contrast(dim, bg) < 4.6: dim = mix(dim, fg, .08)
        faint = mix(bg, mix(fg, ac, .35), .16)
        onac = mix(bg, '#FFFFFF', .6)
        while contrast(onac, ac) < 4.5 and onac != '#FFFFFF': onac = mix(onac, '#FFFFFF', .5)
        return dict(bg=bg, fg=fg, dim=dim, faint=faint, ac=ac, onac=onac, acbg_a=(.10 if grey else .14), light=True, glow=0.0,
                    cr=dict(text=contrast(fg, bg), dim=contrast(dim, bg), accent=contrast(ac, bg)))
    if L['bg'] == 'graphite': bg = '#0E1112'
    elif grey: bg = '#14171A' if L['bg'] == 'deep' else '#0D0F10'
    elif L['bg'] == 'deep': bg = hsl(h, 42, 8)
    else: bg = hsl(h, 28, 6)
    fg = '#F5EDE1' if t == 'warm' else '#E7F0FA' if t == 'cool' else mix('#F4F7F7', ac, .10) if t == 'tint' else '#F4F6F6'
    while contrast(fg, bg) < 10: fg = mix(fg, '#FFFFFF', .2)
    while contrast(ac, bg) < 4.5: ac = mix(ac, '#FFFFFF', .08)
    dim = mix(fg, bg, .48)
    while contrast(dim, bg) < 4.6: dim = mix(dim, fg, .08)
    faint = mix(bg, mix(fg, ac, .35), .12)
    onac = mix(bg, '#000000', .45)
    return dict(bg=bg, fg=fg, dim=dim, faint=faint, ac=ac, onac=onac, acbg_a=(.10 if grey else .13), light=False, glow=0.035,
                cr=dict(text=contrast(fg, bg), dim=contrast(dim, bg), accent=contrast(ac, bg)))

def clean(x):
    L = dict(DEFAULT)
    if isinstance(x, dict):
        for k in DEFAULT:
            if k in x and x[k] is not None: L[k] = x[k]
    if not any(t['id'] == L['theme'] for t in THEMES): L['theme'] = 'teal'
    if not any(t[0] == L['layout'] for t in LAYOUTS): L['layout'] = 'roomy'
    if not any(t[0] == L['ac'] for t in ACCENTS): L['ac'] = 'teal'
    if not any(t[0] == L['text'] for t in TEXTS): L['text'] = 'tint'
    if not any(t[0] == L['bg'] for t in BGS): L['bg'] = 'tinted'
    if not any(t[0] == L['size'] for t in SIZES): L['size'] = 'm'
    try: L['hue'] = (float(L['hue']) % 360 + 360) % 360
    except Exception: L['hue'] = 174
    if isinstance(x, dict) and 'sat' not in x and L['ac'] == 'hue':
        L['sat'], L['val'] = 76, 100          # 0.1.3 custom hue was hsl(h, 100%, 62%) = this
    for k in ('sat', 'val'):
        try: L[k] = clamp(int(round(float(L[k]))), 0, 100)
        except Exception: L[k] = DEFAULT[k]
    L['clock'] = L['clock'] is not False; L['batt'] = L['batt'] is not False
    return L

def theme_look(tid, keep=None):
    t = next((x for x in THEMES if x['id'] == tid), THEMES[0])
    L = dict(keep or DEFAULT); L.update(theme=t['id'], layout=t['layout'], ac=t['ac'], text=t['text'], bg=t['bg']); return L

def is_edited(L):
    t = next((x for x in THEMES if x['id'] == L['theme']), None)
    return (not t) or t['layout'] != L['layout'] or t['ac'] != L['ac'] or t['text'] != L['text'] or t['bg'] != L['bg']

def look_name(L):
    t = next((x for x in THEMES if x['id'] == L['theme']), None)
    return ((t['name'] if t else 'Custom') + ' · edited') if is_edited(L) else t['name']
