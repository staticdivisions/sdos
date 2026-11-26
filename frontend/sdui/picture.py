# Screen look for RetroArch games (a few shader and overlay presets) and
# multi-disc (.m3u) helpers for the in-game menu.
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
import os, re, json, struct, zlib

SHADER_DIR = '/tmp/shaders'        # ROCKNIX overlay of common-, glsl- and slang-shaders
OVL_LIVE = '/tmp/overlays'          # merged overlay folder; its upper layer is /storage/overlays
OVL_STORE = '/storage/overlays'     # setsettings.sh reads global.overlayset relative to this
RA_CFG = '/storage/.config/retroarch/retroarch.cfg'

# (id, label, slang preset, glsl preset). Light single-pass shaders only: the H700/RK3566 GPUs are small.
SHADERS = [
    ('off', 'Off', None, None),
    ('sharp', 'Sharp', 'pixel-art-scaling/sharp-bilinear-simple.slangp', 'interpolation/sharp-bilinear-simple.glslp'),
    ('lines', 'Scanlines', 'scanlines/scanline.slangp', 'scanlines/scanline.glslp'),
    ('lcd', 'LCD', 'handheld/lcd3x.slangp', 'handheld/lcd3x.glslp'),
    ('crt', 'CRT', 'crt/zfast-crt.slangp', 'crt/zfast-crt.glslp'),
]
PASSTHRU = {'slang': 'nearest.slangp', 'glsl': 'nearest.glslp'}

# Overlays are drawn by us at the screen's own size, so they cost no GPU time.
OVERLAYS = [('off', 'Off'), ('lines', 'Scanlines'), ('grid', 'Grid')]


def ids(table):
    return [x[0] for x in table]


def label(table, key):
    for x in table:
        if x[0] == key:
            return x[1]
    return table[0][1]


def step(table, key, d):
    k = ids(table)
    i = k.index(key) if key in k else 0
    return k[(i + d) % len(k)]


def shader_kind(cfg=None):
    """'glsl' for the gl driver, else 'slang' (glcore and vulkan load .slangp only)."""
    try:
        for ln in open(cfg or RA_CFG, errors='ignore'):
            m = re.match(r'\s*video_driver\s*=\s*"?([^"\s]*)', ln)
            if m:
                return 'glsl' if m.group(1) in ('gl', 'gl1') else 'slang'
    except Exception:
        pass
    return 'slang'


def shader_rel(key, kind):
    """Preset path relative to the shader folder, or None for Off/unknown."""
    for sid, _, slang, glsl in SHADERS:
        if sid == key:
            return slang if kind == 'slang' else glsl
    return None


def shader_live_path(key, kind, root=None):
    """Absolute preset to send with SET_SHADER. Off uses a plain pass-through preset."""
    rel = shader_rel(key, kind) or PASSTHRU[kind]
    return os.path.join(root or SHADER_DIR, rel)


# ---------- overlays ----------
def _png(w, h, rows):
    """Tiny RGBA PNG writer (no PIL on the handheld). rows(y) -> bytes of w*4."""
    raw = b''.join(b'\x00' + rows(y) for y in range(h))
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def overlay_png(key, w, h):
    clear, dark = b'\x00\x00\x00\x00', b'\x00\x00\x00'
    if key == 'lines':
        a = dark + bytes([120])
        on, off = a * w, clear * w
        return _png(w, h, lambda y: on if y % 2 else off)
    if key == 'grid':
        a, b = dark + bytes([80]), dark + bytes([140])
        line = (b * w)
        cols = b''.join(a if x % 2 else clear for x in range(w))
        return _png(w, h, lambda y: line if y % 2 else cols)
    return None


def overlay_rel(key):
    return 'sdos/%s.cfg' % key


def write_overlay(key, w, h, live=None, store=None):
    """Write sdos/<key>.cfg + png. Returns the setsettings value (relative to /storage/overlays) or 'none'."""
    live, store = live or OVL_LIVE, store or OVL_STORE
    data = overlay_png(key, int(w), int(h))
    if data is None:
        return 'none'
    base = live if os.path.ismount(live) else store
    d = os.path.join(base, 'sdos')
    os.makedirs(d, exist_ok=True)
    png = '%s-%dx%d.png' % (key, w, h)
    tmp = os.path.join(d, png + '.tmp')
    open(tmp, 'wb').write(data); os.replace(tmp, os.path.join(d, png))
    cfg = ('overlays = 1\noverlay0_overlay = "%s"\noverlay0_full_screen = true\n'
           'overlay0_descs = 0\n' % os.path.join(store, 'sdos', png))
    tmp = os.path.join(d, key + '.cfg.tmp')
    open(tmp, 'w').write(cfg); os.replace(tmp, os.path.join(d, key + '.cfg'))
    return overlay_rel(key)


# ---------- discs ----------
def m3u_discs(path):
    """[(file, label)] for an .m3u playlist, else []."""
    if not path or not path.lower().endswith('.m3u'):
        return []
    try:
        txt = open(path, errors='ignore').read()
    except Exception:
        return []
    out = []
    for ln in txt.splitlines():
        ln = ln.strip().lstrip('\ufeff')
        if not ln or ln.startswith('#'):
            continue
        f, _, lab = ln.partition('|')
        f = f.strip()
        stem = os.path.splitext(os.path.basename(f))[0]
        m = re.search(r'(?i)\b(?:disc|disk|cd)\s*([0-9]+)', stem)
        out.append((f, lab.strip() or ('Disc %s' % m.group(1) if m else 'Disc %d' % (len(out) + 1))))
    return out


def last_disc(path, saves='/storage/roms/saves'):
    """Disc index RetroArch will restore (its .ldci file next to the saves), else 0."""
    stem = os.path.splitext(os.path.basename(path))[0]
    folder = os.path.basename(os.path.dirname(path))
    for p in (os.path.join(saves, folder, stem + '.ldci'), os.path.join(saves, stem + '.ldci'),
              os.path.join('/storage/.config/retroarch/saves', stem + '.ldci')):
        try:
            return max(0, int(json.load(open(p)).get('image_index', 0)))
        except Exception:
            continue
    return 0


def disc_commands(target, count):
    """RetroArch network commands that land on disc `target` from any start disc:
    open the tray, walk back to disc 1 (DISK_PREV stops at the first), step forward, close."""
    target = max(0, min(int(target), count - 1))
    return ['DISK_EJECT_TOGGLE'] + ['DISK_PREV'] * (count - 1) + ['DISK_NEXT'] * target + ['DISK_EJECT_TOGGLE']
