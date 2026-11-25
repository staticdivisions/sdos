"""sdOS 0.1.4: every save lives on the GAMES drive under roms/saves (Windows: GAMES:\\roms\\saves).

Runs from the app layer (so it can ship over the air) as root, at every UI start and before every launch.
Idempotent: safe to run any number of times, never overwrites a save (a clash keeps both, the moved one
gets a .old suffix).

  roms/saves/<system>/            RetroArch save files (sorted by the game's folder name = system folder)
  roms/saves/states/<system>/     RetroArch save states (also DraStic: states/nds)
  roms/saves/nds/                 DraStic .dsv saves
  roms/saves/psp/SAVEDATA/        PPSSPP memory-stick saves (bind-mounted into PPSSPP's memstick)
  roms/saves/psp/PPSSPP_STATE/    PPSSPP save states (also bind-mounted)

exFAT has no symlinks, so PPSSPP gets bind mounts, and the read-only base scripts that hard-code
roms/savestates are bind-mounted over by copies with the new path (generated from the base's own file,
so nothing else in them changes; if the expected text isn't there the original is left alone).
If the GAMES drive is missing, /storage/roms is the internal folder and the same layout is used there.
"""
import os, re, shutil, subprocess, threading, time

ROMS = '/storage/roms'
SAVES = ROMS + '/saves'
STATES = SAVES + '/states'
PSP_MEM = '/storage/.config/ppsspp'
RA_CFG = '/storage/.config/retroarch/retroarch.cfg'
PATCH_DIR = '/run/sdos/patched'
LOG = '/var/log/sdos-saves.log'
MOVED_NOTE = 'MOVED - see saves.txt'
MARK = '/storage/.config/sdui/saves-0.1.4.done'
SAVE_EXT = {'.srm', '.rtc', '.dsv'}
NOT_SYSTEMS = {'saves', 'savestates', 'bios', 'music', 'ports', 'bezels', 'themes', '.tmp', 'games-external'}

RA_SET = [('savefile_directory', SAVES), ('savefiles_in_content_dir', 'false'),
          ('sort_savefiles_by_content_enable', 'true'), ('sort_savefiles_enable', 'false'),
          ('savestates_in_content_dir', 'false'), ('sort_savestates_by_content_enable', 'false'),
          ('sort_savestates_enable', 'false')]

# base script -> list of (old, new) text replacements
PATCHES = {
    '/usr/bin/setsettings.sh': [('SNAPSHOTS="${ROMS_DIR}/savestates"', 'SNAPSHOTS="${ROMS_DIR}/saves/states"')],
    '/usr/bin/start_drastic.sh': [('/storage/roms/savestates', '/storage/roms/saves/states'),
                                  ('ln -sf /storage/roms/nds /storage/.config/drastic/backup',
                                   'mkdir -p /storage/roms/saves/nds; ln -sf /storage/roms/saves/nds /storage/.config/drastic/backup')],
    '/usr/bin/start_ppsspp.sh': [('/storage/roms/savestates/psp/ppsspp-sa', '/storage/roms/saves/psp/PPSSPP_STATE')],
    '/usr/bin/start_dsperate.sh': [('/storage/roms/savestates', '/storage/roms/saves/states')],
    '/usr/bin/start_duckstation.sh': [('/storage/roms/savestates', '/storage/roms/saves/states')],
    '/usr/bin/start_yabasanshiro.sh': [('/storage/roms/savestates', '/storage/roms/saves/states')],
    '/usr/bin/start_mednafen.sh': [(r'\/storage\/roms\/savestates', r'\/storage\/roms\/saves\/states')],
}

README = """sdOS saves
==========
Every save from every emulator is in this folder, so you can back it up from a computer.

  saves\\<system>\\            in-game saves (RetroArch), one folder per system, e.g. saves\\gba
  saves\\states\\<system>\\     save states (Menu > Save / Load), e.g. saves\\states\\snes
  saves\\nds\\                 Nintendo DS saves (DraStic, .dsv)
  saves\\psp\\SAVEDATA\\        PSP saves
  saves\\psp\\PPSSPP_STATE\\    PSP save states

PSP: copy each game's save folder (named after the game ID, e.g. ULUS10336) into
saves\\psp\\SAVEDATA, so it becomes saves\\psp\\SAVEDATA\\ULUS10336\\...
On a Windows PC that is GAMES:\\roms\\saves\\psp\\SAVEDATA (GAMES is the card's drive letter).

Eject the card safely in Windows before putting it back in the handheld.
"""

_lock = threading.Lock()
_booted = False


def log(msg):
    try:
        with open(LOG, 'a') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + '\n')
    except Exception:
        pass


def _mounts():
    out = set()
    try:
        for ln in open('/proc/self/mountinfo'):
            mp = ln.split()[4]
            out.add(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), mp))
    except Exception:
        pass
    return out


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode:
            log('%s -> %d %s' % (' '.join(cmd), r.returncode, (r.stderr or '').strip()[:200]))
        return r.returncode == 0
    except Exception as e:
        log('%s -> %r' % (' '.join(cmd), e)); return False


def _free_name(dst):
    if not os.path.lexists(dst):
        return dst
    i = 1
    while True:
        cand = dst + ('.old' if i == 1 else '.old%d' % i)
        if not os.path.lexists(cand):
            return cand
        i += 1


def _same(a, b):
    try:
        sa, sb = os.stat(a), os.stat(b)
        if sa.st_size != sb.st_size:
            return False
        with open(a, 'rb') as fa, open(b, 'rb') as fb:
            return fa.read() == fb.read()
    except Exception:
        return False


def move_file(src, dst):
    """Move one file without ever overwriting: identical -> drop src; different -> keep both."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.lexists(dst):
        if _same(src, dst):
            os.remove(src); return 'dup'
        dst = _free_name(dst)
    try:
        os.rename(src, dst)            # same filesystem: instant
    except OSError:
        shutil.copy2(src, dst)         # ext4 -> exFAT: copy, check, then delete
        if os.path.getsize(dst) != os.path.getsize(src):
            raise IOError('short copy %s' % dst)
        os.remove(src)
    return dst


def merge_tree(src, dst):
    """Move everything under src into dst (merging folders). Returns the number of files moved."""
    n = 0
    if not os.path.isdir(src) or os.path.realpath(src) == os.path.realpath(dst):
        return 0
    for dp, dns, fns in os.walk(src, topdown=False):
        rel = os.path.relpath(dp, src)
        for fn in fns:
            s = os.path.join(dp, fn)
            if os.path.islink(s) or fn == MOVED_NOTE:
                continue
            try:
                move_file(s, os.path.normpath(os.path.join(dst, rel, fn))); n += 1
            except Exception as e:
                log('move %s failed: %r' % (s, e))
        if dp != src:
            try: os.rmdir(dp)
            except OSError: pass
    return n


def _rom_index():
    """stem of every game file -> its folder name (what RetroArch's sort-by-content uses)."""
    idx = {}
    try:
        top = [e for e in os.scandir(ROMS) if e.is_dir(follow_symlinks=False) and e.name.lower() not in NOT_SYSTEMS]
    except Exception:
        return idx
    for t in top:
        for dp, dns, fns in os.walk(t.path):
            dns[:] = [d for d in dns if not d.startswith('.') and dp.count(os.sep) - t.path.count(os.sep) < 2]
            for fn in fns:
                stem, ext = os.path.splitext(fn)
                if ext.lower() not in SAVE_EXT and not fn.startswith('.'):
                    idx.setdefault(stem, os.path.basename(dp))
    return idx


def _stem(fn):
    m = re.match(r'(.+?)\.(state[0-9]*|state\.auto)(\.png)?$', fn, re.I)
    return m.group(1) if m else os.path.splitext(fn)[0]


def migrate():
    moved = 0
    idx = _rom_index()
    # 1. RetroArch's own folders (~/.config/retroarch/saves|states): sort each file to its system by the ROM name
    for src, base in (('/storage/.config/retroarch/saves', SAVES), ('/storage/.config/retroarch/states', STATES)):
        if not os.path.isdir(src):
            continue
        for dp, dns, fns in os.walk(src, topdown=False):
            for fn in fns:
                s = os.path.join(dp, fn)
                rel = os.path.relpath(dp, src)
                sysdir = rel.split(os.sep)[0] if rel != '.' else idx.get(_stem(fn), '_unsorted')
                try:
                    move_file(s, os.path.join(base, sysdir, fn)); moved += 1
                except Exception as e:
                    log('move %s failed: %r' % (s, e))
            if dp != src:
                try: os.rmdir(dp)
                except OSError: pass
    # 2. saves written next to the games (savefiles_in_content_dir was on; DraStic wrote .dsv into roms/nds)
    try:
        tops = [e.path for e in os.scandir(ROMS) if e.is_dir(follow_symlinks=False) and e.name.lower() not in NOT_SYSTEMS]
    except Exception:
        tops = []
    for t in tops:
        for dp, dns, fns in os.walk(t):
            dns[:] = [d for d in dns if not d.startswith('.') and dp.count(os.sep) - t.count(os.sep) < 2]
            for fn in fns:
                if os.path.splitext(fn)[1].lower() in SAVE_EXT and not fn.startswith('.'):
                    try:
                        move_file(os.path.join(dp, fn), os.path.join(SAVES, os.path.basename(dp), fn)); moved += 1
                    except Exception as e:
                        log('move %s failed: %r' % (fn, e))
    # 3. the old state folder (roms/savestates/<system>); PPSSPP's ppsspp-sa copies go with the PSP states
    old = ROMS + '/savestates'
    if os.path.isdir(old) and old + '/' not in [m + '/' for m in _mounts()]:
        moved += merge_tree(old + '/psp/ppsspp-sa', SAVES + '/psp/PPSSPP_STATE')
        moved += merge_tree(old, STATES)
        try:
            os.makedirs(old, exist_ok=True)
            with open(old + '/' + MOVED_NOTE, 'w', newline='\r\n') as f:
                f.write('Save states are now in the saves\\states folder (next to this one).\n')
        except Exception:
            pass
    # 4. older ROCKNIX PSP save mover copies (roms/psp/PSP/SAVEDATA)
    moved += merge_tree(ROMS + '/psp/PSP/SAVEDATA', SAVES + '/psp/SAVEDATA')
    return moved


def make_folders(system_folders=()):
    for d in [SAVES, STATES, SAVES + '/nds', STATES + '/nds', SAVES + '/psp/SAVEDATA', SAVES + '/psp/PPSSPP_STATE'] + \
             [SAVES + '/' + f for f in system_folders if f not in ('bios', 'music', 'psp', 'nds')]:
        try: os.makedirs(d, exist_ok=True)
        except Exception as e: log('mkdir %s: %r' % (d, e))
    try:
        p = SAVES + '/README.txt'
        if not os.path.exists(p) or open(p, newline='').read() != README.replace('\n', '\r\n'):
            with open(p, 'w', newline='\r\n') as f:
                f.write(README)
    except Exception as e:
        log('README: %r' % e)


def retroarch_config(path=RA_CFG):
    if not os.path.exists(path):
        return False
    try:
        lines = open(path, errors='replace').read().splitlines()
    except Exception:
        return False
    want = dict(RA_SET)
    out, seen = [], set()
    for ln in lines:
        k = ln.split('=', 1)[0].strip()
        if k in want:
            if k in seen:
                continue
            seen.add(k)
            ln = '%s = "%s"' % (k, want[k])
        out.append(ln)
    out += ['%s = "%s"' % (k, v) for k, v in RA_SET if k not in seen]
    if out != lines:
        tmp = path + '.sdos-tmp'
        with open(tmp, 'w') as f:
            f.write('\n'.join(out) + '\n')
        os.replace(tmp, path)
        log('retroarch.cfg: saves -> %s' % SAVES)
    return True


def patch_scripts(mounts):
    os.makedirs(PATCH_DIR, exist_ok=True)
    for path, reps in PATCHES.items():
        if path in mounts or not os.path.exists(path):
            continue
        try:
            txt = open(path, errors='surrogateescape').read()
        except Exception:
            continue
        new = txt
        for a, b in reps:
            new = new.replace(a, b)
        if new == txt:
            log('%s: expected text not found, left as is' % path); continue
        dst = os.path.join(PATCH_DIR, os.path.basename(path))
        with open(dst, 'w', errors='surrogateescape') as f:
            f.write(new)
        os.chmod(dst, 0o755)
        if _run(['mount', '--bind', dst, path]):
            log('%s -> saves/states' % path)


def ppsspp_binds(mounts):
    if not os.path.isdir(PSP_MEM):
        if os.path.isdir('/usr/config/ppsspp'):
            shutil.copytree('/usr/config/ppsspp', PSP_MEM, symlinks=True)   # what start_ppsspp.sh does on first run
        else:
            return
    for sub in ('SAVEDATA', 'PPSSPP_STATE'):
        tgt, src = PSP_MEM + '/PSP/' + sub, SAVES + '/psp/' + sub
        if tgt in mounts:
            continue
        if os.path.islink(tgt):
            os.remove(tgt)
        if os.path.isdir(tgt):
            n = merge_tree(tgt, src)
            if n:
                log('PPSSPP %s: moved %d files to %s' % (sub, n, src))
        os.makedirs(tgt, exist_ok=True)
        os.makedirs(src, exist_ok=True)
        _run(['mount', '--bind', src, tgt])


PPSSPP_KEYS = {'Pause': '1-111', 'Save State': '1-132', 'Load State': '1-134'}   # Esc, F2, F4 (keyboard device 1)


def ppsspp_keys(path=PSP_MEM + '/PSP/SYSTEM/controls.ini'):
    """The sdOS in-game menu drives PPSSPP with keys: Esc opens its pause menu (Emulator settings), F2/F4 save/load."""
    try:
        lines = open(path).read().splitlines()
    except Exception:
        return False
    out, changed = [], False
    for ln in lines:
        k, sep, v = ln.partition(' = ')
        if sep and k in PPSSPP_KEYS and PPSSPP_KEYS[k] not in v.split(','):
            ln = '%s = %s' % (k, ','.join([x for x in v.split(',') if x] + [PPSSPP_KEYS[k]])); changed = True
        out.append(ln)
    if changed:
        with open(path + '.sdos-tmp', 'w') as f:
            f.write('\n'.join(out) + '\n')
        os.replace(path + '.sdos-tmp', path)
        log('PPSSPP controls: Esc/F2/F4 mapped')
    return True


def unbind():
    """Drop the PPSSPP binds (before the games folder is switched to another card)."""
    m = _mounts()
    for sub in ('SAVEDATA', 'PPSSPP_STATE'):
        t = PSP_MEM + '/PSP/' + sub
        if t in m:
            _run(['umount', t])


def ensure(system_folders=(), full=None):
    """Make the layout, move old saves, set the config. full=None: migrate once per UI start."""
    global _booted
    if os.geteuid() != 0 or not os.path.isdir(ROMS):
        return False
    with _lock:
        try:
            do_full = (not _booted) if full is None else full
            make_folders(system_folders)
            if do_full:
                n = migrate()
                if n:
                    log('moved %d save files into %s' % (n, SAVES))
                _booted = True
                try:
                    os.makedirs(os.path.dirname(MARK), exist_ok=True)
                    open(MARK, 'w').write(time.strftime('%Y-%m-%d %H:%M:%S\n'))
                except Exception:
                    pass
            retroarch_config()
            m = _mounts()
            patch_scripts(m)
            ppsspp_binds(m)
            ppsspp_keys()
            return True
        except Exception as e:
            log('ensure failed: %r' % e)
            return False
