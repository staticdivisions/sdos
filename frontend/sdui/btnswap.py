# Swap A/B and Swap X/Y for the built-in pad: sdui menus, RetroArch autoconfig,
# SDL GameController users, PPSSPP, Flycast, and a few other standalone configs.
# Toggles default off. Changes are applied from a backup of the original file so
# turning a toggle off restores the previous mapping.
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
import os, re, json, shutil
import xml.etree.ElementTree as ET

BUILTIN_PAD_NAMES = (
    'H700 Gamepad', 'ROCKNIX Gamepad', 'RGB20S Gamepad',
    'GO-Super Gamepad', 'GO-Ultra Gamepad', 'XU10 Gamepad', 'XU Mini M Gamepad',
    'GameForce ACE Gamepad', 'Retro Lite CM5 Gamepad', 'r36s_Gamepad',
    'rg552_joypad', 'rg_arc_joypad', 'retrogame_joypad', 'retrogame_joypad_s1_f2',
    'odroidgo2_joypad', 'odroidgo2_v11_joypad', 'odroidgo3_joypad',
    'gkd_pixel2_joypad', 'r33s_joypad',
)

# PPSSPP maps SDL / evdev button N to NKCODE_BUTTON_1 + N (188 + N).
PPSSPP_BTN = {'b': '10-188', 'a': '10-189', 'x': '10-190', 'y': '10-191'}

_swap_ab = False
_swap_xy = False


def flags():
    return _swap_ab, _swap_xy


def set_flags(ab, xy):
    global _swap_ab, _swap_xy
    _swap_ab, _swap_xy = bool(ab), bool(xy)


def is_builtin_pad(name):
    if not name:
        return False
    n = name.strip()
    if n in BUILTIN_PAD_NAMES:
        return True
    if 'H700' in n:
        return True
    return False


def remap_logical(name, ab=None, xy=None, builtin=True):
    """Swap a logical face-button name when the toggle is on and this is the built-in pad."""
    if not name or not builtin:
        return name
    if ab is None or xy is None:
        ab, xy = flags()
    if ab and name in ('a', 'b'):
        return 'b' if name == 'a' else 'a'
    if xy and name in ('x', 'y'):
        return 'y' if name == 'x' else 'x'
    return name


def swap_btn_map(btn, ab, xy):
    """btn is {index: logical_name}. Returns a new dict with A/B and/or X/Y names swapped."""
    out = dict(btn or {})
    if ab:
        inv = {n: i for i, n in out.items()}
        if 'a' in inv and 'b' in inv:
            ia, ib = inv['a'], inv['b']
            out[ia], out[ib] = 'b', 'a'
    if xy:
        inv = {n: i for i, n in out.items()}
        if 'x' in inv and 'y' in inv:
            ix, iy = inv['x'], inv['y']
            out[ix], out[iy] = 'y', 'x'
    return out


def _root():
    return os.environ.get('SDUI_SWAP_ROOT') or ''


def _p(*parts):
    base = _root()
    if base:
        return os.path.join(base, *parts)
    return os.path.join('/', *parts)


def _backup_dir():
    return _p('storage', '.config', 'sdui', 'btnswap')


def _manifest_path():
    return os.path.join(_backup_dir(), 'manifest.json')


def _load_manifest():
    try:
        return json.load(open(_manifest_path()))
    except Exception:
        return {'files': {}}


def _save_manifest(man):
    d = _backup_dir()
    os.makedirs(d, exist_ok=True)
    tmp = _manifest_path() + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(man, f, indent=1)
    os.replace(tmp, _manifest_path())


def _backup_key(path):
    return path.replace(os.sep, '__')


def _ensure_backup(man, path):
    """Remember the original bytes (or that the path was missing) the first time we touch it."""
    files = man.setdefault('files', {})
    if path in files:
        return files[path]
    rec = {'existed': os.path.isfile(path)}
    if rec['existed']:
        bdir = os.path.join(_backup_dir(), 'orig')
        os.makedirs(bdir, exist_ok=True)
        dest = os.path.join(bdir, _backup_key(path))
        shutil.copy2(path, dest)
        rec['backup'] = dest
    files[path] = rec
    return rec


def _original_text(rec, path, stock=None):
    if rec.get('existed') and rec.get('backup') and os.path.isfile(rec['backup']):
        return open(rec['backup'], encoding='utf-8', errors='replace').read()
    if stock and os.path.isfile(stock):
        return open(stock, encoding='utf-8', errors='replace').read()
    return ''


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, path)


def _restore(rec, path):
    if rec.get('existed') and rec.get('backup') and os.path.isfile(rec['backup']):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copy2(rec['backup'], path)
    elif os.path.isfile(path):
        os.remove(path)


# ---------- transformers ----------

_RA_FACE = (('input_a_btn', 'input_b_btn'), ('input_x_btn', 'input_y_btn'))
_RA_PLAYER = (('input_player1_a_btn', 'input_player1_b_btn'), ('input_player1_x_btn', 'input_player1_y_btn'))


def _ra_pairs(ab, xy):
    pairs = []
    if ab:
        pairs.extend(_RA_FACE[0:1] + _RA_PLAYER[0:1])
    if xy:
        pairs.extend(_RA_FACE[1:2] + _RA_PLAYER[1:2])
    return pairs


def swap_ra_cfg(text, ab, xy):
    """Swap input_*_btn values for A/B and/or X/Y. Leaves other keys alone."""
    if not text or not (ab or xy):
        return text
    keys = {}
    pat = re.compile(r'^(\s*([A-Za-z0-9_]+)\s*=\s*"?([^"\n]*)"?\s*)$', re.M)
    for m in pat.finditer(text):
        keys[m.group(2)] = m.group(3).strip()
    out = text
    for k1, k2 in _ra_pairs(ab, xy):
        if k1 not in keys or k2 not in keys:
            continue
        v1, v2 = keys[k1], keys[k2]
        def sub(k, new, s):
            return re.sub(
                r'(^\s*' + re.escape(k) + r'\s*=\s*)"?[^"\n]*"?\s*$',
                lambda m, p=new: m.group(1) + ('"%s"' % p if '"' in m.group(0) else p),
                s, flags=re.M)
        out = sub(k1, v2, out)
        out = sub(k2, v1, out)
        keys[k1], keys[k2] = v2, v1
    return out


def swap_sdl_line(line, ab, xy):
    """Rewrite a: / b: / x: / y: fields in one gamecontrollerdb line."""
    if not line or line.lstrip().startswith('#') or ',' not in line:
        return line
    if not (ab or xy):
        return line
    def fields(s):
        d = {}
        for part in s.split(','):
            if ':' in part:
                k, v = part.split(':', 1)
                d[k] = v
        return d
    d = fields(line)
    if ab and 'a' in d and 'b' in d:
        d['a'], d['b'] = d['b'], d['a']
    if xy and 'x' in d and 'y' in d:
        d['x'], d['y'] = d['y'], d['x']
    parts = []
    for part in line.rstrip('\n').split(','):
        if ':' in part:
            k, _ = part.split(':', 1)
            if k in d:
                parts.append('%s:%s' % (k, d[k]))
                continue
        parts.append(part)
    nl = line.endswith('\n')
    return ','.join(parts) + ('\n' if nl and not ','.join(parts).endswith('\n') else '')


def swap_sdl_db(text, ab, xy):
    if not text:
        return text
    out = []
    for line in text.splitlines(True):
        name = ''
        if ',' in line and not line.lstrip().startswith('#'):
            bits = line.split(',')
            if len(bits) > 1:
                name = bits[1]
        if is_builtin_pad(name):
            out.append(swap_sdl_line(line, ab, xy))
        else:
            out.append(line)
    return ''.join(out)


def swap_ppsspp_ini(text, ab, xy):
    if not text or not (ab or xy):
        return text
    table = {}
    if ab:
        table[PPSSPP_BTN['a']] = PPSSPP_BTN['b']
        table[PPSSPP_BTN['b']] = PPSSPP_BTN['a']
    if xy:
        table[PPSSPP_BTN['x']] = PPSSPP_BTN['y']
        table[PPSSPP_BTN['y']] = PPSSPP_BTN['x']
    def one(val):
        parts = [p.strip() for p in val.split(',')]
        return ','.join(table.get(p, p) for p in parts)
    def sub(m):
        return m.group(1) + one(m.group(2))
    return re.sub(r'(?m)^([A-Za-z0-9.\-]+(?:\.[A-Za-z0-9.\-]+)*\s*=\s*)(.+)$', sub, text)


def swap_flycast_cfg(text, ab, xy):
    """Swap btn_a/btn_b and/or btn_x/btn_y on the right-hand side of bind lines."""
    if not text or not (ab or xy):
        return text
    def repl(m):
        name = m.group(2)
        if ab and name in ('btn_a', 'btn_b'):
            name = 'btn_b' if name == 'btn_a' else 'btn_a'
        if xy and name in ('btn_x', 'btn_y'):
            name = 'btn_y' if name == 'btn_x' else 'btn_x'
        return m.group(1) + name
    return re.sub(r'(?m)(:|=)\s*(btn_[abxy])\b', repl, text)


def swap_mupen_cfg(text, ab, xy):
    """Swap the button(...) values of A Button and B Button. N64 has no X/Y."""
    if not text or not ab:
        return text
    # Process each [Input-SDL-ControlN] section on its own so empty later ports stay put.
    parts = re.split(r'(?m)(?=^\[Input-SDL-Control\d+\])', text)
    out = []
    for part in parts:
        a = re.search(r'(?m)^(A Button\s*=\s*)(.+)$', part)
        b = re.search(r'(?m)^(B Button\s*=\s*)(.+)$', part)
        if a and b and a.group(2).strip() and b.group(2).strip():
            va, vb = a.group(2), b.group(2)
            part = part[:a.start(2)] + vb + part[a.end(2):]
            b = re.search(r'(?m)^(B Button\s*=\s*)(.+)$', part)
            part = part[:b.start(2)] + va + part[b.end(2):]
        out.append(part)
    return ''.join(out)


def swap_es_input(text, ab, xy):
    if not text or not (ab or xy):
        return text
    try:
        root = ET.fromstring(text)
    except Exception:
        return text
    for ic in root.iter('inputConfig'):
        if ic.get('type') != 'joystick' or not is_builtin_pad(ic.get('deviceName') or ''):
            continue
        face = {}
        for inp in ic.findall('input'):
            if inp.get('type') == 'button' and inp.get('name') in ('a', 'b', 'x', 'y'):
                face[inp.get('name')] = inp
        if ab and 'a' in face and 'b' in face:
            ia, ib = face['a'].get('id'), face['b'].get('id')
            face['a'].set('id', ib); face['b'].set('id', ia)
            changed = True
        if xy and 'x' in face and 'y' in face:
            ix, iy = face['x'].get('id'), face['y'].get('id')
            face['x'].set('id', iy); face['y'].set('id', ix)
            changed = True
    if not changed:
        return text
    # Keep an xml declaration if the original had one
    body = ET.tostring(root, encoding='unicode')
    if text.strip().startswith('<?xml'):
        decl = text.strip().split('\n', 1)[0] + '\n'
        if not body.startswith('<?xml'):
            body = decl + body
    if text.endswith('\n') and not body.endswith('\n'):
        body += '\n'
    return body


def sdl_config_env(ab, xy):
    """SDL_GAMECONTROLLERCONFIG value for built-in pads, or '' when both toggles are off."""
    if not (ab or xy):
        return ''
    stock = _p('usr', 'config', 'SDL-GameControllerDB', 'gamecontrollerdb.txt')
    alt = _p('storage', '.config', 'SDL-GameControllerDB', 'gamecontrollerdb.txt')
    text = ''
    if os.path.isfile(stock):
        text = open(stock, encoding='utf-8', errors='replace').read()
    elif os.path.isfile(alt):
        text = open(alt, encoding='utf-8', errors='replace').read()
    if not text:
        return ''
    lines = []
    for line in swap_sdl_db(text, ab, xy).splitlines():
        if ',' in line and not line.lstrip().startswith('#'):
            name = line.split(',')[1] if len(line.split(',')) > 1 else ''
            if is_builtin_pad(name):
                lines.append(line.rstrip('\n'))
    return '\n'.join(lines)


def launch_env(ab=None, xy=None):
    if ab is None or xy is None:
        ab, xy = flags()
    env = {}
    val = sdl_config_env(ab, xy)
    if val:
        env['SDL_GAMECONTROLLERCONFIG'] = val
    return env


# ---------- apply / revert ----------

def _stock_ra(name):
    return _p('usr', 'share', 'libretro', 'autoconfig', name + '.cfg')


def _iter_builtin_ra_names():
    names = set(BUILTIN_PAD_NAMES)
    for folder in (_p('usr', 'share', 'libretro', 'autoconfig'),
                   _p('tmp', 'joypads'),
                   _p('storage', 'joypads')):
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            if not fn.endswith('.cfg'):
                continue
            name = fn[:-4]
            if is_builtin_pad(name):
                names.add(name)
    return sorted(names)


def _transform_path(man, path, stock, fn, ab, xy):
    rec = _ensure_backup(man, path)
    if not (ab or xy):
        _restore(rec, path)
        return
    src = _original_text(rec, path, stock)
    if not src and stock and os.path.isfile(stock):
        src = open(stock, encoding='utf-8', errors='replace').read()
    if not src:
        return
    _write_text(path, fn(src, ab, xy))


def apply(ab, xy):
    """Write or restore every mapping we manage. Safe to call repeatedly. Uses backups."""
    set_flags(ab, xy)
    man = _load_manifest()
    # RetroArch overlay joypads
    for name in _iter_builtin_ra_names():
        path = _p('storage', 'joypads', name + '.cfg')
        _transform_path(man, path, _stock_ra(name), swap_ra_cfg, ab, xy)
    # SDL GameController DB (storage copy; launch_env also sets the override)
    sdl_stock = _p('usr', 'config', 'SDL-GameControllerDB', 'gamecontrollerdb.txt')
    sdl_path = _p('storage', '.config', 'SDL-GameControllerDB', 'gamecontrollerdb.txt')
    if os.path.isfile(sdl_path) or os.path.isfile(sdl_stock):
        _transform_path(man, sdl_path, sdl_stock, swap_sdl_db, ab, xy)
    # PPSSPP: create the config dir if needed so start_ppsspp.sh will not clobber it
    psp_stock = _p('usr', 'config', 'ppsspp', 'PSP', 'SYSTEM', 'controls.ini')
    psp_path = _p('storage', '.config', 'ppsspp', 'PSP', 'SYSTEM', 'controls.ini')
    psp_dir = _p('storage', '.config', 'ppsspp')
    stock_dir = _p('usr', 'config', 'ppsspp')
    if (ab or xy) and not os.path.isdir(psp_dir) and os.path.isdir(stock_dir):
        shutil.copytree(stock_dir, psp_dir)
    if os.path.isfile(psp_path) or os.path.isfile(psp_stock):
        _transform_path(man, psp_path, psp_stock, swap_ppsspp_ini, ab, xy)
    # Flycast mappings for built-in pads
    fc_stock_dir = _p('usr', 'config', 'flycast', 'mappings')
    fc_dir = _p('storage', '.config', 'flycast', 'mappings')
    fc_names = set()
    for folder in (fc_stock_dir, fc_dir):
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            if fn.startswith('SDL_') and fn.endswith('.cfg'):
                name = fn[4:-4]
                if is_builtin_pad(name):
                    fc_names.add(name)
    for name in sorted(fc_names):
        _transform_path(man, os.path.join(fc_dir, 'SDL_%s.cfg' % name),
                        os.path.join(fc_stock_dir, 'SDL_%s.cfg' % name),
                        swap_flycast_cfg, ab, xy)
    # es_input (sdui reads this; Yaba also copies it at launch)
    for rel in (('storage', '.config', 'emulationstation', 'es_input.cfg'),
                ('storage', '.emulationstation', 'es_input.cfg')):
        path = _p(*rel)
        stock = path if os.path.isfile(path) else _p('usr', 'config', 'emulationstation', 'es_input.cfg')
        if os.path.isfile(path) or (ab or xy) and os.path.isfile(stock):
            _transform_path(man, path, stock, swap_es_input, ab, xy)
    # mupen64plus-sa: only the persistent cfg (start script may still install stock InputAutoCfg.ini)
    mp_stock = _p('usr', 'local', 'share', 'mupen64plus', 'mupen64plus.cfg')
    mp_path = _p('storage', '.config', 'mupen64plus', 'mupen64plus.cfg')
    if os.path.isfile(mp_path) or os.path.isfile(mp_stock):
        _transform_path(man, mp_path, mp_stock, swap_mupen_cfg, ab, xy)

    if not (ab or xy):
        # drop backups once everything is restored, so a later first-on captures a fresh original
        bdir = _backup_dir()
        man = {'files': {}}
        _save_manifest(man)
        orig = os.path.join(bdir, 'orig')
        if os.path.isdir(orig):
            shutil.rmtree(orig, ignore_errors=True)
    else:
        man['swap_ab'] = bool(ab)
        man['swap_xy'] = bool(xy)
        _save_manifest(man)
    return True
