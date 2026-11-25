# Device backend: everything that touches the system. A mock backend with
# demo data is used on a desktop (SDUI_MOCK=1) for screenshots.
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
import os, re, json, time, shlex, socket, struct, fcntl, threading, subprocess, hashlib, glob
import xml.etree.ElementTree as ET
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = open(os.path.join(HERE, 'VERSION')).read().strip() if os.path.exists(os.path.join(HERE, 'VERSION')) else '0.1'
from . import ota, saves
from . import wifi_txt as WIFITXT
from . import btnswap
OTA_URL = ota.OTA_URL

# Idle sleep is owned by sdui (ROCKNIX has no separate idle-to-sleep after ES was
# removed; logind IdleAction is unset). Hold it off during setup, jobs, and
# transfers. smbd sessions are established TCP 139/445; smbstatus is not on the image.
SMB_PORTS = {0x8B, 0x1BD}
NET_BUSY_BYTES = 16 * 1024     # per second, excluding lo
DISK_BUSY_SECTORS = 256        # per second (~128 KiB)
ACTIVITY_GRACE = 20

def tcp_established_local_ports(text):
    ports = set()
    for i, ln in enumerate(text.splitlines()):
        if i == 0 and 'local_address' in ln:
            continue
        p = ln.split()
        if len(p) < 4 or p[3] != '01':
            continue
        try:
            ports.add(int(p[1].rsplit(':', 1)[1], 16))
        except Exception:
            pass
    return ports

def net_dev_bytes(text):
    total = 0
    for ln in text.splitlines():
        if ':' not in ln:
            continue
        name, rest = ln.split(':', 1)
        if name.strip() == 'lo':
            continue
        cols = rest.split()
        if len(cols) < 9:
            continue
        try:
            total += int(cols[0]) + int(cols[8])
        except Exception:
            pass
    return total

def diskstats_sectors(text):
    total = 0
    for ln in text.splitlines():
        p = ln.split()
        if len(p) < 14:
            continue
        name = p[2]
        if name.startswith(('loop', 'ram', 'zram', 'sr')):
            continue
        try:
            total += int(p[5]) + int(p[9])
        except Exception:
            pass
    return total

# Systems sdOS offers (H700 and RK3566 handhelds), in Home order: (ROCKNIX system id, name, short tag, roms folder, note).
# Each one's folder is created on the games card; each launches with a core/emulator verified to be in SYSTEM
# (see build/NOTES.md, "Systems"). Any other ROCKNIX system still shows up, after these, if its folder has games,
# unless it is in HEAVY.
SYSTEMS = [
    ('gb', 'Game Boy', 'GB', 'gb', ''), ('gbc', 'Game Boy Color', 'GBC', 'gbc', ''), ('gba', 'Game Boy Advance', 'GBA', 'gba', ''),
    ('nes', 'NES / Famicom', 'NES', 'nes', ''), ('fds', 'Famicom Disk System', 'FDS', 'fds', 'BIOS'), ('snes', 'Super Nintendo', 'SNES', 'snes', ''),
    ('n64', 'Nintendo 64', 'N64', 'n64', 'lighter games'), ('nds', 'Nintendo DS', 'NDS', 'nds', ''),
    ('virtualboy', 'Virtual Boy', 'VB', 'virtualboy', ''), ('pokemini', 'Pokémon Mini', 'PMINI', 'pokemini', ''),
    ('gameandwatch', 'Game & Watch', 'G&W', 'gameandwatch', ''),
    ('genesis', 'Genesis / Mega Drive', 'MD', 'genesis', ''), ('mastersystem', 'Master System', 'SMS', 'mastersystem', ''),
    ('gamegear', 'Game Gear', 'GG', 'gamegear', ''), ('sg-1000', 'SG-1000', 'SG', 'sg-1000', ''),
    ('segacd', 'Sega CD / Mega CD', 'SCD', 'segacd', 'BIOS'), ('sega32x', 'Sega 32X', '32X', 'sega32x', ''),
    ('dreamcast', 'Dreamcast', 'DC', 'dreamcast', 'BIOS, some games'),
    ('psx', 'PlayStation', 'PS1', 'psx', 'BIOS recommended'), ('psp', 'PSP', 'PSP', 'psp', ''),
    ('pcengine', 'PC Engine / TurboGrafx-16', 'PCE', 'pcengine', ''), ('pcenginecd', 'PC Engine CD / TurboGrafx-CD', 'PCECD', 'pcenginecd', 'BIOS'),
    ('neogeo', 'Neo Geo', 'NEO', 'neogeo', 'neogeo.zip BIOS'), ('ngp', 'Neo Geo Pocket', 'NGP', 'ngp', ''),
    ('ngpc', 'Neo Geo Pocket Color', 'NGPC', 'ngpc', ''),
    ('wonderswan', 'WonderSwan', 'WS', 'wonderswan', ''), ('wonderswancolor', 'WonderSwan Color', 'WSC', 'wonderswancolor', ''),
    ('atari2600', 'Atari 2600', '2600', 'atari2600', ''), ('atari5200', 'Atari 5200', '5200', 'atari5200', 'BIOS'),
    ('atari7800', 'Atari 7800', '7800', 'atari7800', ''), ('atarilynx', 'Atari Lynx', 'LYNX', 'atarilynx', 'BIOS'),
    ('atarijaguar', 'Atari Jaguar', 'JAG', 'atarijaguar', 'some games'),
    ('fbn', 'Arcade · FinalBurn Neo', 'FBNEO', 'fbneo', ''), ('mame', 'Arcade · MAME 2003-Plus', 'MAME', 'mame', ''),
    ('arcade', 'Arcade', 'ARC', 'arcade', ''),
    ('colecovision', 'ColecoVision', 'CV', 'coleco', 'BIOS'), ('intellivision', 'Intellivision', 'INTV', 'intellivision', 'BIOS'),
    ('vectrex', 'Vectrex', 'VEC', 'vectrex', ''), ('odyssey2', 'Odyssey 2', 'O2', 'odyssey', 'BIOS'),
    ('msx', 'MSX', 'MSX', 'msx', ''), ('msx2', 'MSX2', 'MSX2', 'msx2', ''),
    ('c64', 'Commodore 64', 'C64', 'c64', ''), ('amiga', 'Amiga', 'AMIGA', 'amiga', 'Kickstart BIOS'),
    ('zxspectrum', 'ZX Spectrum', 'ZX', 'zxspectrum', ''), ('amstradcpc', 'Amstrad CPC', 'CPC', 'amstradcpc', ''),
    ('pc', 'DOS', 'DOS', 'pc', ''), ('scummvm', 'ScummVM', 'SCUMM', 'scummvm', 'then Tools > Find ScummVM games'),
    ('pico-8', 'PICO-8', 'P8', 'pico-8', ''), ('tic-80', 'TIC-80', 'TIC', 'tic-80', ''),
    ('ports', 'Ports', 'PORTS', 'ports', 'Tools > PortMaster'), ('doom', 'Doom', 'DOOM', 'doom', ''),
]
ORDER = [(sid, nm, sh) for sid, nm, sh, _, _ in SYSTEMS] + [
    ('megadrive', 'Mega Drive', 'MD'), ('megacd', 'Mega CD', 'MCD'), ('famicom', 'Famicom', 'FC'), ('sfc', 'Super Famicom', 'SFC'),
    ('tg16', 'TurboGrafx-16', 'TG16'), ('tg16cd', 'TurboGrafx-CD', 'TGCD'), ('supergrafx', 'SuperGrafx', 'SGX'),
    ('neocd', 'Neo Geo CD', 'NEOCD'), ('cps1', 'Arcade · CPS-1', 'CPS1'), ('cps2', 'Arcade · CPS-2', 'CPS2'), ('cps3', 'Arcade · CPS-3', 'CPS3'),
    ('atari800', 'Atari 800', '800'), ('atarist', 'Atari ST', 'ST'), ('pspminis', 'PSP Minis', 'MINIS'),
]
# Too heavy for the H700 (or no working emulator in this build): never listed.
HEAVY = {'saturn', '3do', 'cdi', 'st-v', 'windows', 'moonlight', 'ios', 'idtech', 'channelf', 'gp32', 'ndsiware', 'naomi', 'atomiswave'}
# The short folder list the setup wizard creates and shows. ROCKNIX folder names.
GAMES_DEV = '/dev/disk/by-label/GAMES'
SAVE_FOLDERS = [f for _, _, _, f, _ in SYSTEMS]
SETUP_FOLDERS = [(f, nm) for _, nm, _, f, _ in SYSTEMS] + [('bios', 'BIOS files'), ('music', 'Music for the Music Player')]
TZS = [('Pacific · Los Angeles', 'America/Los_Angeles'), ('Mountain · Denver', 'America/Denver'), ('Central · Chicago', 'America/Chicago'),
       ('Eastern · New York', 'America/New_York'), ('Alaska · Anchorage', 'America/Anchorage'), ('Hawaii · Honolulu', 'Pacific/Honolulu'),
       ('London', 'Europe/London'), ('Berlin', 'Europe/Berlin'), ('Paris', 'Europe/Paris'), ('Madrid', 'Europe/Madrid'),
       ('São Paulo', 'America/Sao_Paulo'), ('Tokyo', 'Asia/Tokyo'), ('Seoul', 'Asia/Seoul'), ('Shanghai', 'Asia/Shanghai'),
       ('Sydney', 'Australia/Sydney'), ('UTC', 'UTC')]
# ROCKNIX "systems" that are really tool launchers; sdOS shows its own Tools list instead.
HIDDEN_SYSTEMS = {'tools', 'music', 'mplayer', 'imageviewer'} | HEAVY
# Device models: label -> device tree (all in /flash/device_trees on the boot partition). Per image family: see hw.py.
# Retail names only. (name, standard dtb, alternate-screen dtb or None). Panel variants (ROCKNIX "rev6" / "v2")
# can't be detected (ROCKNIX: "impossible to know the difference without opening the device"), so each model
# starts on the standard screen and offers "alternate screen" as a fallback.
from .hw import MODELS, MODEL_AUTO, PLATFORM, FAMILY, ALL_NAMES, DEFAULT_DTB, SETUP_STEPS, setup_model_rows, is_default_h_tree, HAS_JOYSTICKS
from . import hw

def model_of(dt):
    """dtb id -> (index in MODELS, is_alternate_screen) or (-1, False)."""
    for i, (_, std, alt) in enumerate(MODELS):
        if dt == std: return i, False
        if alt and dt == alt: return i, True
    return -1, False

def model_name(dt):
    i, alt = model_of(dt)
    if i < 0:
        return ALL_NAMES.get(dt) or (hw.board_name() if dt and dt == hw.running_dt() else '') or 'Unknown'
    return MODELS[i][0] + (' (alternate screen)' if alt else '')

def set_device_bat():
    """SET-DEVICE.bat for the SDOS drive (CRLF, ASCII): plain model names, alternate screens listed separately."""
    L = ['@echo off', 'setlocal', 'cd /d "%~dp0"', 'title sdOS - set your handheld', 'echo.',
         'echo  sdOS: choose your handheld. This copies its screen and buttons file to dtb.img.',
         'echo  You can also change it later on the handheld: Settings - Device model.', 'echo.']
    ids = []
    for name, std, alt in MODELS:
        ids.append(std); L.append('echo   %2d. %s' % (len(ids), name))
    if any(alt for _, _, alt in MODELS):
        L += ['echo.', 'echo  Screen looks wrong (lines, garbage or black)? Choose your model again here:']
        for name, std, alt in MODELS:
            if alt:
                ids.append(alt); L.append('echo   %2d. %s - alternate screen' % (len(ids), name))
    L += ['echo.', 'set "N="', 'set /p "N=Number (Enter to cancel): "', 'if "%N%"=="" goto :eof', 'set "DT="']
    for n, dt in enumerate(ids, 1):
        L.append('if "%%N%%"=="%d" set "DT=%s"' % (n, dt))
    L += ['if "%DT%"=="" (echo Not a number from the list. & pause & goto :eof)',
          'if not exist "device_trees\\%DT%.dtb" (echo device_trees\\%DT%.dtb is missing on this card. & pause & goto :eof)',
          'if exist "dtb.img" copy /y "dtb.img" "dtb.prev.img" >nul',
          'copy /y "device_trees\\%DT%.dtb" "dtb.img" >nul',
          'if errorlevel 1 (echo Could not write dtb.img. Is the card write-protected? & pause & goto :eof)',
          'if exist "sdos-model-trial" del "sdos-model-trial"',
          'echo.', 'echo  Done. Eject the card safely, put it in the handheld and turn it on.', 'pause']
    return '\r\n'.join(L) + '\r\n'

# Tools: (id, label, note, how). how = ('script', path, kill-name, retroarch?) or ('app', screen).
TOOLS = [('files', 'File Explorer', 'Browse, copy and delete files', ('script', '/usr/config/modules/commander.sh', 'commander', False)),
         ('music', 'Music Player', 'Plays the roms/music folder', ('app', 'music')),
         ('retroarch', 'RetroArch settings', 'Cores, controls, video', ('script', '/usr/config/modules/Start 64bit Retroarch.sh', 'retroarch', True)),
         ('ppsspp', 'PSP settings', 'PPSSPP options', ('script', '/usr/config/modules/Start PPSSPP.sh', 'ppsspp', False)),
         ('scummvm', 'Find ScummVM games', 'Games in roms/scummvm', ('app', 'scummvm')),
         ('portmaster', 'PortMaster', 'Get ports (needs Wi-Fi)', ('script', '/usr/config/modules/Start PortMaster.sh', '', False)),
         ('macclean', 'Clean up Mac files', 'Removes ._ files from roms', ('app', 'macclean')),
         ('rescan', 'Refresh game list', 'Look for new games', ('app', 'rescan'))]
# Emulator menu keys sent through the sdui-keys uinput keyboard (core name without -sa -> (key, modifiers)).
# PPSSPP: Esc = pause menu (Settings is in it); GZDoom: Esc = menu; Flycast: Tab = settings; ScummVM: Ctrl+F5 = main menu.
EMU_MENU_KEYS = {'ppsspp': (1, ()), 'gzdoom': (1, ()), 'flycast': (15, ()), 'scummvm': (63, (29,))}
UINPUT_KEYS = (60, 62, 1, 15, 29, 63)          # F2, F4, Esc, Tab, Left Ctrl, F5
SKIP_DIRS = {'bios', 'savestates', 'saves', 'media', 'images', 'videos', 'manuals', 'bezels', 'themes', 'music', '.tmp'}

PICO8_DIRS = ('/storage/roms/pico-8', '/storage/roms/pico-8/aarch64')
PICO8_BINS = ('pico8_64', 'pico8', 'pico8_dyn')

def pico8_official():
    """True when the official PICO-8 (needed for Splore) is in roms/pico-8 or roms/pico-8/aarch64 (where ROCKNIX looks)."""
    return any(os.path.isfile(os.path.join(d, b)) for d in PICO8_DIRS for b in PICO8_BINS)

def pico8_runnable():
    """ROCKNIX's start_pico8.sh runs pico8_64 from roms/pico-8/aarch64 if that folder exists, else from roms/pico-8."""
    d = PICO8_DIRS[1] if os.path.isdir(PICO8_DIRS[1]) else PICO8_DIRS[0]
    return os.path.isfile(os.path.join(d, 'pico8_64'))

def folder_guide():
    out = ["sdOS: put each game in its system's folder. Only systems with games show up.", '',
           '%-16s %s' % ('Folder', 'System'), '%-16s %s' % ('------', '------')]
    for _, nm, _, f, note in SYSTEMS:
        out.append('%-16s %s%s' % (f, nm, ('  (' + note + ')') if note else ''))
    out += ['%-16s %s' % ('bios', 'BIOS files for the systems marked BIOS'),
            '%-16s %s' % ('music', 'MP3 / OGG / FLAC / WAV for Tools > Music Player'),
            '%-16s %s' % ('saves', 'All saves and save states (PSP saves: saves\\psp\\SAVEDATA, see saves\\README.txt)'), '',
            'Systems too heavy for this handheld (Saturn, 3DO, CD-i, Naomi...) are not listed.']
    return '\n'.join(out) + '\n'

def run(cmd, timeout=20, shell=False):
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except Exception as e:
        return 1, str(e)

def log(msg):
    try:
        import sys; sys.stderr.write(time.strftime('%Y-%m-%d %H:%M:%S ') + str(msg) + '\n'); sys.stderr.flush()
    except Exception:
        pass

def bg(fn, *a):
    t = threading.Thread(target=fn, args=a, daemon=True); t.start(); return t

def clean_title(name):
    base = os.path.splitext(name)[0]
    t = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', base).strip()
    return t or base



# Bluetooth device lines from rocknix-bluetooth list / /run/bt_listing:
#   <device id="AA:BB:..." name="..." type="joystick" connected="yes" />
_BT_TAG = re.compile(r'<device\s+([^>]*)/?>', re.I)
_BT_ATTR = re.compile(r'(\w+)="([^"]*)"')


def parse_bt_devices(text):
    """Parse ROCKNIX bluetooth XML lines into dicts: mac, name, type, connected, status."""
    out = []
    for m in _BT_TAG.finditer(text or ''):
        attrs = dict(_BT_ATTR.findall(m.group(1)))
        mac = (attrs.get('id') or '').strip()
        if not mac:
            continue
        out.append({
            'mac': mac,
            'name': attrs.get('name') or mac,
            'type': attrs.get('type') or '',
            'connected': attrs.get('connected', '') == 'yes',
            'status': attrs.get('status') or '',
        })
    return out


def fold_bt_listing(text):
    """Apply added/removed events from the live listing file, last event wins."""
    found = {}
    for d in parse_bt_devices(text):
        if d.get('status') == 'removed':
            found.pop(d['mac'], None)
        else:
            found[d['mac']] = d
    return list(found.values())


class Base:
    mock = False
    def __init__(self):
        self.state_path = None
        self.state = {}
        self.wifi_status = None      # connected SSID or None
        self.busy = {}               # name -> True while a background job runs
        self.events = []             # (kind, text) posted from threads, drained by the UI
        self.lock = threading.Lock()

    def post(self, kind, text=''):
        with self.lock:
            self.events.append((kind, text))

    def drain(self):
        with self.lock:
            ev, self.events = self.events, []
        return ev

    def smb_active(self):
        return bool(getattr(self, '_test_smb', False))

    def net_bytes(self):
        return int(getattr(self, '_test_net', 0) or 0)

    def disk_sectors(self):
        return int(getattr(self, '_test_disk', 0) or 0)

    def activity_busy(self, now=None):
        """True while an SMB session or a sizable network/disk transfer is going, and for a short grace after."""
        now = time.time() if now is None else now
        if self.smb_active():
            self._act_until = now + ACTIVITY_GRACE
            return True
        t_prev, net_prev, disk_prev = getattr(self, '_act_sample', (0, None, None))
        if t_prev and now - t_prev < 1.0:
            return now < getattr(self, '_act_until', 0)
        net = self.net_bytes()
        disk = self.disk_sectors()
        self._act_sample = (now, net, disk)
        if t_prev and net_prev is not None:
            dt = max(0.001, now - t_prev)
            if (net - net_prev) >= NET_BUSY_BYTES * dt or (disk - disk_prev) >= DISK_BUSY_SECTORS * dt:
                self._act_until = now + ACTIVITY_GRACE
        return now < getattr(self, '_act_until', 0)

    # persistent UI state
    def load_state(self):
        try:
            with open(self.state_path) as f:
                self.state = json.load(f)
        except Exception:
            self.state = {}
        return self.state

    def save_state(self):
        if not self.state_path:
            return
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp = self.state_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(self.state, f, indent=1)
            os.replace(tmp, self.state_path)
        except Exception:
            pass


    def import_wifi_txt(self, path=None):
        """If wifi.txt on the boot partition names a network, connect and scrub the file."""
        path = path or WIFITXT.WIFI_TXT_PATH
        try:
            data = open(path, 'rb').read()
        except Exception:
            return False
        parsed = WIFITXT.parse_wifi_txt(data)
        if not parsed or not parsed[0]:
            return False
        ssid, psk = parsed
        # Scrub first so a plaintext password is never left on the FAT32 card,
        # even if the connection later fails.
        self._scrub_wifi_txt(path)
        self.wifi_connect(ssid, psk or '')
        return True

    def _scrub_wifi_txt(self, path):
        try:
            WIFITXT.write_wifi_txt_template(path)
            return True
        except Exception:
            return False

class Mock(Base):
    """Desktop stand-in with demo data."""
    mock = True
    def __init__(self):
        super().__init__()
        self.state_path = None
        self.has_wifi = True
        self.wifi_status = None
        self.bright, self.vol = 8, 6
        self.nets = [{'ssid': 'Home Network', 'sig': 3, 'lock': 1}, {'ssid': 'Studio 5G', 'sig': 3, 'lock': 1}, {'ssid': 'Guest', 'sig': 2, 'lock': 0},
                     {'ssid': 'Upstairs', 'sig': 1, 'lock': 1}, {'ssid': 'Coffee Bar', 'sig': 1, 'lock': 0}]
        self.systems = self._demo()
        self.tz = 'America/Los_Angeles'
        self.fixed_time = os.environ.get('SDUI_FIXED_TIME')
        self._dtb = MODELS[0][1]
        self._trial = None
        self._powers = []
        self.has_bt = True
        self._bt_on = False
        self.bt_paired = []
        self.bt_found = [
            {'mac': 'E4:17:D8:11:22:33', 'name': '8BitDo SN30 Pro', 'type': 'joystick', 'connected': False, 'status': 'added'},
            {'mac': '00:1A:7D:DA:71:13', 'name': 'WH-1000XM4', 'type': 'audio', 'connected': False, 'status': 'added'},
        ]

    def _demo(self):
        A1 = 'Amber Astro Basalt Cobalt Copper Dusk Echo Ember Frost Glass Granite Hollow Ivory Jade Kilo Lumen Marble Moss Neon Nova Opal Paper Quartz Quiet Rust Salt Signal Tidal Tin Umber Velvet Vector Willow Xenon Yonder Zephyr Zinc'.split()
        A2 = 'Circuit Courier Harbor Lantern Relay Run Garden Knights Orbit Pilot Rally Ferry Depot Express Tactics Quest Raceway Lane Station Picnic Drift Arcade Parcel Shepherd Bakery Loop'.split()
        st = [42]
        def R():
            M = 0xFFFFFFFF
            s = (st[0] + 0x6D2B79F5) & M; st[0] = s
            def imul(a, b): return (a * b) & M
            t = imul(s ^ (s >> 15), 1 | s)
            t = ((t + imul(t ^ (t >> 7), 61 | t)) & M) ^ t
            return ((t ^ (t >> 14)) & M) / 4294967296
        spec = [('gb', 'Game Boy', 'GB', 9), ('gbc', 'Game Boy Color', 'GBC', 0), ('gba', 'Game Boy Advance', 'GBA', 14), ('nes', 'NES', 'NES', 12),
                ('snes', 'Super Nintendo', 'SNES', 11), ('genesis', 'Genesis', 'MD', 8), ('n64', 'Nintendo 64', 'N64', 6), ('psx', 'PlayStation', 'PS1', 10), ('psp', 'PSP', 'PSP', 7)]
        used, out = set(), []
        for sid, name, short, n in spec:
            lst = []
            while len(lst) < n:
                t = A1[int(R() * len(A1))] + ' ' + A2[int(R() * len(A2))]
                if R() < .12:
                    t += ' ' + ['II', '2', 'DX', 'Deluxe', 'Zero'][int(R() * 5)]
                if t in used:
                    continue
                used.add(t); lst.append({'title': t, 'path': '/demo/%s/%s' % (sid, t), 'sys': sid})
            lst.sort(key=lambda g: g['title'].lower())
            out.append({'id': sid, 'name': name, 'short': short, 'games': lst})
        return out

    def scan(self):
        return [s for s in self.systems if s['games']]
    def battery(self): return 82, False
    def now(self):
        if self.fixed_time:
            return float(self.fixed_time)
        return time.time()
    def wifi_present(self): return self.has_wifi
    def wifi_scan(self): self.post('wifi_list', '')
    def wifi_list(self): return self.nets
    def wifi_connect(self, ssid, psk):
        self.wifi_status = ssid; self.post('wifi_ok', ssid)
    def wifi_off(self): self.wifi_status = None
    def set_tz(self, tz): self.tz = tz
    def set_time(self, epoch): pass
    def set_bright(self, v): self.bright = v
    def set_vol(self, v): self.vol = v
    def get_bright(self): return self.bright
    def get_vol(self): return self.vol
    def cards(self): return [('Card 1', 'GAMES drive · 22 GB free', 0), ('Card 2', 'Second slot · 119 GB free', 1)]
    def set_games_card(self, idx): pass
    def make_folders(self): return 'GAMES drive › roms'
    def games_where(self): return 'GAMES drive › roms'
    def games_part(self): return '/dev/mmcblk0p3'
    def share_on(self): return getattr(self, '_share', True)
    def set_share(self, on): self._share = on
    def ip_addr(self): return '192.168.1.42'
    def share_login(self): return ('sdos', 'sdos')
    def check_update(self): self.post('upd', 'none:You have the latest version')
    def apply_update(self): pass
    def launch(self, game): return None
    def game_save(self): return 'Saved', False
    def launch_tool(self, tool): return None
    def tool_available(self, tool): return True
    def clean_mac_files(self): return 0
    def scan_scummvm(self, done): done(0)
    def power(self, action):
        self._powers.append(action)
    def current_model(self):
        return self._dtb
    def is_default_h_tree(self):
        return is_default_h_tree(self._dtb)
    def set_model(self, dtb):
        if MODEL_AUTO:
            return False
        self._trial = (dtb, self._dtb)
        self._dtb = dtb
        return True
    def model_trial(self):
        return self._trial
    def confirm_model(self):
        self._trial = None
    def revert_model(self):
        if self._trial:
            self._dtb = self._trial[1]
            self._trial = None
        self.power('restart')
        return True
    def refresh_set_device_bat(self): pass
    def game_load(self): return 'Loaded', False
    def emu_menu(self): return 'Emulator menu opens here', False
    def suspend(self): pass
    def joy_controllers(self): return ''

    def bt_present(self):
        return self.has_bt
    def bt_on(self):
        return self._bt_on
    def bt_status_msg(self):
        if self.busy.get('bt_pair'):
            return 'Pairing…'
        if self.busy.get('bt_scan'):
            return 'Searching…'
        return ''
    def bt_enable(self):
        self._bt_on = True
        self.post('bt_list', '')
    def bt_disable(self):
        self._bt_on = False
        for d in self.bt_paired:
            d['connected'] = False
        self.bt_found = []
        self.post('bt_list', '')
    def bt_scan(self):
        self._bt_on = True
        self.busy['bt_scan'] = True
        self.post('bt_list', '')
        def done():
            self.busy['bt_scan'] = False
            self.post('bt_list', '')
        self.post('call', done)
    def bt_stop_scan(self):
        self.busy['bt_scan'] = False
    def bt_refresh(self):
        self.post('bt_list', '')
    def bt_pair(self, mac):
        self._bt_on = True
        d = next((x for x in self.bt_found if x['mac'] == mac), None)
        if d is None:
            d = next((x for x in self.bt_paired if x['mac'] == mac), None)
        if d is None:
            self.post('bt_fail', mac); return
        d = dict(d, connected=True)
        self.bt_paired = [x for x in self.bt_paired if x['mac'] != mac] + [d]
        self.bt_found = [x for x in self.bt_found if x['mac'] != mac]
        self.post('bt_ok', d['name'])
    def bt_connect(self, mac):
        for d in self.bt_paired:
            if d['mac'] == mac:
                d['connected'] = True
                self.post('bt_ok', d['name']); return
        self.post('bt_fail', mac)
    def bt_disconnect(self, mac):
        for d in self.bt_paired:
            if d['mac'] == mac:
                d['connected'] = False
        self.post('bt_list', '')
    def bt_forget(self, mac):
        self.bt_paired = [x for x in self.bt_paired if x['mac'] != mac]
        self.post('bt_list', '')
    def restore_speaker_sink(self):
        pass


class Device(Base):
    def __init__(self):
        super().__init__()
        self.state_path = '/storage/.config/sdui/state.json'
        self.cfg = '/storage/.config/system/configs/system.cfg'
        self.es_systems = self._find_es_systems()
        self.sysdefs = self._parse_systems()
        self.nets = []
        self.bt_paired = []
        self.bt_found = []
        self._bt_scan_stop = False
        self._speaker_sink = None
        self.proc = None
        self.game = None
        self.game_con = None
        self._systems_cache = None
        self.uinput = None
        bg(self._init_uinput)
        bg(self._poll_wifi)
        bg(saves.ensure, SAVE_FOLDERS)       # 0.1.4: all saves on the GAMES drive (roms/saves)
        bg(self.refresh_set_device_bat)
        bg(self._ensure_gb_analogue)
        bg(self.import_wifi_txt)
        bg(self._poll_bt_audio)

    # ---------- settings (ROCKNIX system.cfg) ----------
    def get_setting(self, key, system=None):
        keys = ([system + '.' + key] if system else []) + ['system.' + key, key, 'global.' + key]
        try:
            lines = open(self.cfg).read().splitlines()
        except Exception:
            return ''
        d = {}
        for ln in lines:
            if '=' in ln:
                k, v = ln.split('=', 1); d[k] = v
        for k in keys:
            if d.get(k):
                return d[k]
        return ''

    def set_setting(self, key, val):
        run(['bash', '-c', '. /etc/profile.d/001-functions; set_setting "$0" "$1"', key, str(val)])

    def _ensure_gb_analogue(self):
        # Gambatte (the default Game Boy core) ignores Down while Up is also held.
        # Analog-as-D-pad can hold Up from a drifted stick, or from leftover stick
        # axes when a no-stick handheld is still on the default RG35XX H device tree.
        # Force Game Boy / Game Boy Color to use the D-pad only.
        try:
            for sid in ('gb', 'gbc', 'gbh', 'gbch'):
                key = '%s.analogue' % sid
                if self.get_setting(key) != '0':
                    self.set_setting(key, '0')
                    log('%s=0 (D-pad only, so a stick cannot block Down)' % key)
        except Exception as e:
            log('gb analogue default failed: %r' % e)

    # ---------- systems & games ----------
    def _find_es_systems(self):
        for p in ('/storage/.config/emulationstation/es_systems.cfg', '/usr/config/emulationstation/es_systems.cfg', '/etc/emulationstation/es_systems.cfg'):
            if os.path.exists(p):
                return p
        return None

    def _parse_systems(self):
        out = {}
        if not self.es_systems:
            return out
        try:
            root = ET.parse(self.es_systems).getroot()
        except Exception:
            return out
        for s in root.findall('system'):
            name = (s.findtext('name') or '').strip()
            if not name:
                continue
            emus, demu, dcore = [], None, None
            for e in s.findall('emulators/emulator'):
                en = e.get('name')
                for c in e.findall('cores/core'):
                    emus.append((en, c.text.strip()))
                    if c.get('default') == 'true' and not demu:
                        demu, dcore = en, c.text.strip()
            if not demu and emus:
                demu, dcore = emus[0]
            out[name] = {'name': name, 'full': (s.findtext('fullname') or name).strip(), 'path': (s.findtext('path') or '').strip(),
                         'ext': set(x.lower() for x in (s.findtext('extension') or '').split()), 'cmd': (s.findtext('command') or '').strip(),
                         'emu': demu, 'core': dcore, 'emus': emus}
        return out

    def _scan_dir(self, path, exts, depth=0):
        found = []
        try:
            it = list(os.scandir(path))
        except Exception:
            return found
        for e in it:
            n = e.name
            if n.startswith('.') or n.startswith('._'):
                continue
            if e.is_dir(follow_symlinks=False):
                if depth < 2 and n.lower() not in SKIP_DIRS:
                    found += self._scan_dir(e.path, exts, depth + 1)
            elif os.path.splitext(n)[1].lower() in exts:
                found.append(e.path)
        return found

    def scan(self):
        known = {k: (n, sh) for k, n, sh in ORDER}
        order = [k for k, _, _ in ORDER] + sorted(k for k in self.sysdefs if k not in known)
        out = []
        seen_paths = set()
        for sid in order:
            d = self.sysdefs.get(sid)
            if sid in HIDDEN_SYSTEMS:
                continue
            if not d or not d['path'] or not os.path.isdir(d['path']):
                continue
            real = os.path.realpath(d['path'])
            if real in seen_paths:
                continue
            seen_paths.add(real)
            files = self._scan_dir(d['path'], d['ext'])
            if not files:
                continue
            files = self._hide_parts(files)
            if sid == 'pico-8' and not pico8_official():
                files = [f for f in files if 'splore' not in os.path.basename(f).lower()]   # Splore needs the official PICO-8
                if not files:
                    continue
            names = [clean_title(os.path.basename(f)) for f in files]
            dup = {n for n in names if names.count(n) > 1}
            games = [{'title': (os.path.splitext(os.path.basename(f))[0] if n in dup else n), 'path': f, 'sys': sid} for f, n in zip(files, names)]
            games.sort(key=lambda g: g['title'].lower())
            nm, sh = known.get(sid, (d['full'], sid.upper()[:4]))
            out.append({'id': sid, 'name': nm, 'short': sh, 'games': games})
        self._systems_cache = out
        return out

    def _hide_parts(self, files):
        """Hide .bin/.img tracks referenced by a .cue and discs referenced by an .m3u."""
        hide = set()
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.cue', '.m3u'):
                try:
                    txt = open(f, errors='ignore').read()
                except Exception:
                    continue
                d = os.path.dirname(f)
                if ext == '.cue':
                    for m in re.finditer(r'FILE\s+"([^"]+)"', txt):
                        hide.add(os.path.normpath(os.path.join(d, m.group(1))))
                else:
                    for ln in txt.splitlines():
                        ln = ln.strip()
                        if ln and not ln.startswith('#'):
                            hide.add(os.path.normpath(os.path.join(d, ln)))
        return [f for f in files if os.path.normpath(f) not in hide]

    # ---------- status ----------
    def battery(self):
        for b in glob.glob('/sys/class/power_supply/*'):
            if os.path.basename(b).lower().startswith('bat') or open(os.path.join(b, 'type')).read().strip() == 'Battery':
                try:
                    cap = int(open(os.path.join(b, 'capacity')).read().strip())
                    st = open(os.path.join(b, 'status')).read().strip()
                    return cap, st == 'Charging'
                except Exception:
                    continue
        return None, False

    def now(self):
        return time.time()

    def get_bright(self):
        v = self.get_setting('display.brightness')
        try: return max(1, min(10, round(int(v) / 10)))
        except Exception: return 5

    def get_vol(self):
        v = self.get_setting('audio.volume')
        try: return max(0, min(10, round(int(v) / 10)))
        except Exception: return 6

    def set_bright(self, v):
        bg(run, ['brightness', 'set', str(int(v) * 10)])
    def set_vol(self, v):
        bg(run, ['volume', str(int(v) * 10)])

    # ---------- wifi ----------
    def wifi_present(self):
        return any(os.path.basename(p).startswith('wlan') for p in glob.glob('/sys/class/net/*'))

    def _poll_wifi(self):
        while True:
            rc, out = run(['nmcli', '-t', '-f', 'TYPE,STATE,CONNECTION', 'device'], timeout=5)
            ssid = None
            if rc == 0:
                for ln in out.splitlines():
                    p = ln.split(':')
                    if len(p) >= 3 and p[0] == 'wifi' and p[1] == 'connected':
                        ssid = ':'.join(p[2:]).replace('\\:', ':')
            self.wifi_status = ssid
            time.sleep(10)

    def wifi_scan(self):
        def job():
            if self.busy.get('scan'):
                return
            self.busy['scan'] = True
            try:
                self._wifi_scan_job()
            finally:
                self.busy['scan'] = False
                self.post('wifi_list', '')
        bg(job)

    def _wifi_ready(self):
        rc, out = run(['nmcli', '-t', '-f', 'TYPE,STATE', 'device'], timeout=5)
        return rc == 0 and any(l.startswith('wifi:') and 'unavailable' not in l and 'unmanaged' not in l for l in out.splitlines())

    def _wifi_scan_job(self):
        # The radio and NetworkManager need a few seconds after boot or after "enable";
        # the first scan used to come back empty. Wait for the device, then scan until networks appear.
        run(['wifictl', 'enable'], timeout=10)
        for _ in range(20):
            if self._wifi_ready(): break
            time.sleep(1)
        for attempt in range(6):
            nets = self._wifi_parse()
            if nets:
                self.nets = nets[:12]; return
            time.sleep(2.5)
        self.nets = []

    def _wifi_parse(self):
        rc, out = run(['nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list', '--rescan', 'yes'], timeout=25)
        nets, seen = [], set()
        for ln in out.splitlines() if rc == 0 else []:
            parts = re.split(r'(?<!\\):', ln)
            if len(parts) < 4:
                continue
            ssid = parts[1].replace('\\:', ':')
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            try: sig = int(parts[2])
            except Exception: sig = 0
            nets.append({'ssid': ssid, 'sig': 3 if sig >= 67 else 2 if sig >= 34 else 1, 'lock': 1 if parts[3] and parts[3] != '--' else 0})
        nets.sort(key=lambda n: -n['sig'])
        return nets

    def wifi_list(self):
        return self.nets

    def wifi_connect(self, ssid, psk):
        def job():
            self.busy['connect'] = True
            self.set_setting('wifi.enabled', '1')
            self.set_setting('wifi.ssid', ssid)
            self.set_setting('wifi.key', psk or '')
            run(['wifictl', 'enable'], timeout=10)
            run(['wifictl', 'connect', ssid, psk or ''], timeout=120)
            rc, out = run(['nmcli', '-t', '-f', 'TYPE,STATE,CONNECTION', 'device'], timeout=5)
            ok = any(l.startswith('wifi:connected:') for l in out.splitlines())
            self.busy['connect'] = False
            if ok:
                self.wifi_status = ssid
                run(['wifictl', 'pin'], timeout=10)
                self.post('wifi_ok', ssid)
            else:
                self.post('wifi_fail', ssid)
        bg(job)

    def wifi_off(self):
        self.set_setting('wifi.enabled', '0')
        bg(run, ['wifictl', 'disable'])
        self.wifi_status = None

    # ---------- bluetooth (ROCKNIX rocknix-bluetooth + PipeWire) ----------
    def bt_present(self):
        # hci0 is the kernel adapter; it shows up even when bluetoothd is stopped.
        # Also show the row if the user already turned Bluetooth on, so they can turn it off
        # if the adapter later disappears.
        return bool(glob.glob('/sys/class/bluetooth/hci*')) or self.bt_on()

    def bt_on(self):
        return self.get_setting('controllers.bluetooth.enabled') == '1'

    def _bt_write(self, path, text):
        try:
            with open(path, 'w') as f:
                f.write(text)
            return True
        except Exception:
            return False

    def bt_status_msg(self):
        if self.busy.get('bt_pair'):
            try:
                msg = open('/run/bt_status').read().strip()
                if msg:
                    return msg
            except Exception:
                pass
            return 'Pairing…'
        if self.busy.get('bt_scan'):
            return 'Searching…'
        return ''

    def _bt_ensure_on(self, timeout=12):
        if self.bt_on() and glob.glob('/sys/class/bluetooth/hci*'):
            rc, _ = run(['systemctl', 'is-active', 'bluetooth'], timeout=5)
            if rc == 0:
                return True
        run(['rocknix-bluetooth', 'enable'], timeout=20)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if glob.glob('/sys/class/bluetooth/hci*'):
                return True
            time.sleep(0.5)
        return bool(glob.glob('/sys/class/bluetooth/hci*'))

    def bt_enable(self):
        def job():
            self.busy['bt_enable'] = True
            self.post('bt_list', '')
            ok = self._bt_ensure_on()
            self.busy['bt_enable'] = False
            if not ok:
                self.post('bt_nohw', '')
            else:
                self._bt_refresh_sync()
                self.post('bt_list', '')
        bg(job)

    def bt_disable(self):
        self.bt_stop_scan()
        def job():
            run(['rocknix-bluetooth', 'disable'], timeout=15)
            for d in self.bt_paired:
                d['connected'] = False
            self.bt_found = []
            self.restore_speaker_sink()
            self.post('bt_list', '')
        bg(job)

    def _bt_refresh_sync(self):
        rc, out = run(['rocknix-bluetooth', 'list'], timeout=30)
        self.bt_paired = parse_bt_devices(out if rc == 0 else '')

    def bt_refresh(self):
        def job():
            self._bt_refresh_sync()
            self.post('bt_list', '')
        bg(job)

    def bt_scan(self):
        def job():
            if self.busy.get('bt_scan'):
                return
            self.busy['bt_scan'] = True
            self._bt_scan_stop = False
            self.post('bt_list', '')
            try:
                if not self._bt_ensure_on():
                    self.post('bt_nohw', '')
                    return
                try:
                    open('/run/bt_listing', 'w').close()
                except Exception:
                    pass
                self._bt_write('/run/bt_discovery_control', 'start\n')
                found = {}
                for _ in range(20):
                    if self._bt_scan_stop:
                        break
                    try:
                        text = open('/run/bt_listing').read()
                    except Exception:
                        text = ''
                    found = {d['mac']: d for d in fold_bt_listing(text)}
                    self.bt_found = list(found.values())
                    self.post('bt_list', '')
                    time.sleep(1)
            finally:
                self._bt_write('/run/bt_discovery_control', 'stop\n')
                self.busy['bt_scan'] = False
                self.post('bt_list', '')
        bg(job)

    def bt_stop_scan(self):
        self._bt_scan_stop = True
        self._bt_write('/run/bt_discovery_control', 'stop\n')

    def _bt_name(self, mac):
        for d in (self.bt_paired + self.bt_found):
            if d['mac'] == mac:
                return d['name']
        return mac

    def bt_pair(self, mac):
        def job():
            self.busy['bt_pair'] = mac
            self.post('bt_list', '')
            if not self._bt_ensure_on():
                self.busy['bt_pair'] = False
                self.post('bt_nohw', '')
                return
            try:
                if not os.path.exists('/run/bt_listing'):
                    open('/run/bt_listing', 'w').close()
            except Exception:
                pass
            self._bt_write('/run/bt_discovery_control', 'start\n')
            rc, out = run(['rocknix-bluetooth', 'trust', mac], timeout=75)
            run(['rocknix-bluetooth', 'connect', mac], timeout=30)
            self._bt_write('/run/bt_discovery_control', 'stop\n')
            self._bt_refresh_sync()
            self.busy['bt_pair'] = False
            name = self._bt_name(mac)
            ok = any(d['mac'] == mac for d in self.bt_paired)
            self.post('bt_ok' if ok else 'bt_fail', name)
        bg(job)

    def bt_connect(self, mac):
        def job():
            self.busy['bt_pair'] = mac
            self.post('bt_list', '')
            rc, out = run(['rocknix-bluetooth', 'connect', mac], timeout=30)
            self._bt_refresh_sync()
            self.busy['bt_pair'] = False
            name = self._bt_name(mac)
            ok = any(d['mac'] == mac and d['connected'] for d in self.bt_paired)
            self.post('bt_ok' if ok or rc == 0 else 'bt_fail', name)
        bg(job)

    def bt_disconnect(self, mac):
        def job():
            run(['rocknix-bluetooth', 'disconnect', mac], timeout=20)
            self._bt_refresh_sync()
            self.restore_speaker_sink()
            self.post('bt_list', '')
        bg(job)

    def bt_forget(self, mac):
        def job():
            run(['rocknix-bluetooth', 'remove', mac], timeout=20)
            self.bt_paired = [d for d in self.bt_paired if d['mac'] != mac]
            self.restore_speaker_sink()
            self._bt_refresh_sync()
            self.post('bt_list', '')
        bg(job)

    def _pulse_sinks(self):
        rc, out = run(['pactl', 'list', 'short', 'sinks'], timeout=5)
        names = []
        if rc == 0:
            for ln in out.splitlines():
                parts = ln.split()
                if len(parts) >= 2:
                    names.append(parts[1])
        return names

    def _internal_sink(self, sinks=None):
        if self._speaker_sink:
            return self._speaker_sink
        for s in (sinks or self._pulse_sinks()):
            if not s.startswith('bluez_'):
                self._speaker_sink = s
                return s
        return None

    def restore_speaker_sink(self):
        sink = self._internal_sink()
        if sink:
            run(['pactl', 'set-default-sink', sink], timeout=5)

    def _poll_bt_audio(self):
        """If a Bluetooth headset was the default sink and then drops, send audio back to the speakers."""
        had_bt = False
        while True:
            try:
                sinks = self._pulse_sinks()
                for s in sinks:
                    if not s.startswith('bluez_'):
                        self._speaker_sink = s
                        break
                rc, out = run(['pactl', 'get-default-sink'], timeout=5)
                cur = (out or '').strip()
                is_bt = cur.startswith('bluez_')
                missing = bool(cur) and cur not in sinks
                if (had_bt and (not is_bt or missing)) or (is_bt and missing):
                    self.restore_speaker_sink()
                    self.post('bt_audio', 'speaker')
                    had_bt = False
                else:
                    had_bt = is_bt and not missing
            except Exception:
                pass
            time.sleep(3)

    # ---------- time ----------
    def set_tz(self, tz):
        self.set_setting('system.timezone', tz)
        try:
            os.makedirs('/storage/.cache', exist_ok=True)
            open('/storage/.cache/timezone', 'w').write('TIMEZONE=' + tz)
            open('/storage/.cache/system_timezone', 'w').write(tz)
        except Exception:
            pass
        bg(run, ['systemctl', 'restart', 'tz-data.service'])
        os.environ['TZ'] = tz
        time.tzset()

    def set_time(self, epoch):
        run(['date', '-s', '@%d' % int(epoch)])
        bg(run, ['hwclock', '--systohc', '--utc'])

    # ---------- cards ----------
    def _boot_disk(self):
        try:
            for ln in open('/proc/mounts'):
                dev, mnt = ln.split()[:2]
                if mnt == '/flash':
                    return re.sub(r'p\d+$', '', os.path.basename(dev))
        except Exception:
            pass
        return 'mmcblk0'

    def card2_present(self):
        return self.card2_part() is not None or os.path.ismount('/storage/games-external') and not self.games_part()

    def card2_part(self):
        """Largest partition (or the bare disk) of an SD card in slot 2, e.g. /dev/mmcblk1p1."""
        boot = self._boot_disk()
        for b in sorted(glob.glob('/sys/block/mmcblk*')):
            n = os.path.basename(b)
            if n == boot or 'boot' in n or 'rpmb' in n:
                continue
            try:
                if open(os.path.join(b, 'device/type')).read().strip() != 'SD':
                    continue
            except Exception:
                continue
            best, size = n, -1
            for pp in glob.glob(os.path.join(b, n + 'p*')):
                try: sz = int(open(os.path.join(pp, 'size')).read())
                except Exception: continue
                if sz > size: best, size = os.path.basename(pp), sz
            return '/dev/' + best
        return None

    def games_part(self):
        """The exFAT GAMES partition sdOS makes on card 1 at first boot (cards of 12 GiB and up, i.e. real 16 GB cards;
        0.1.3/0.1.4 images needed 24 GiB). Only freshly flashed cards get the new sizes."""
        if not os.path.exists(GAMES_DEV):
            return None
        real = os.path.realpath(GAMES_DEV)
        return real if os.path.basename(real).startswith(self._boot_disk()) else None

    @staticmethod
    def _mount_of(dev):
        try:
            for ln in open('/proc/mounts'):
                d, m = ln.split()[:2]
                if os.path.realpath(d) == dev and m.startswith('/storage/games'):
                    return m
        except Exception:
            pass
        return None

    @staticmethod
    def _free(path):
        try:
            s = os.statvfs(path)
            return '%d GB free' % round(s.f_bavail * s.f_frsize / 1e9)
        except Exception:
            return 'free space unknown'

    def cards(self):
        gp = self.games_part()
        if gp:
            m = self._mount_of(gp)
            out = [('Card 1', 'GAMES drive · ' + (self._free(m) if m else 'free space unknown'), 0)]
        else:
            out = [('Card 1', 'This card · ' + self._free('/storage'), 0)]
        if self.card2_part():
            p = '/storage/games-external' if os.path.ismount('/storage/games-external') and not gp else None
            out.append(('Card 2', 'Second slot · ' + (self._free(p) if p else 'ready'), 1))
        else:
            out.append(('Card 2', 'No card in slot 2', -1))
        return out

    def set_games_card(self, idx):
        # ROCKNIX automount mounts system.gamesdevice (or the first free card) on /storage/games-external
        # and bind-mounts its roms folder on /storage/roms.
        gp = self.games_part()
        if idx == 1:
            self.set_setting('system.automount', '1')
            self.set_setting('system.gamesdevice', self.card2_part() or 'default')
            self.set_setting('system.merged.device', 'external')
        elif gp:
            self.set_setting('system.automount', '1')
            self.set_setting('system.gamesdevice', GAMES_DEV)
        elif self.card2_part():
            self.set_setting('system.automount', '0')          # keep games on card 1's Linux partition
        else:
            self.set_setting('system.automount', '1')
            self.set_setting('system.gamesdevice', 'default')
        saves.unbind()
        run(['bash', '-c', 'umount /storage/roms 2>/dev/null; systemctl restart rocknix-automount.service'], timeout=90)
        self._systems_cache = None
        bg(saves.ensure, SAVE_FOLDERS, True)

    def make_folders(self):
        base = '/storage/roms'
        for f, _ in SETUP_FOLDERS:
            try: os.makedirs(os.path.join(base, f), exist_ok=True)
            except Exception: pass
        saves.make_folders(SAVE_FOLDERS)
        try:
            with open(os.path.join(base, 'sdOS - which folder.txt'), 'w', newline='\r\n') as fh:
                fh.write(folder_guide())
        except Exception:
            pass
        return self.games_where()

    def games_where(self):
        gp = self.games_part()
        ext = os.path.ismount('/storage/games-external') and self.get_setting('system.automount') == '1'
        if ext and gp and self._mount_of(gp):
            return 'GAMES drive › roms'
        if ext:
            return 'Card 2 › roms'
        return 'Card 1 › STORAGE › roms'

    # ---------- network share (Samba) ----------
    def share_on(self):
        return self.get_setting('samba.enabled') == '1'

    def set_share(self, on):
        self.set_setting('samba.enabled', '1' if on else '0')
        cmd = 'mkdir -p /run/samba; ln -sf /etc/samba/smb.conf /run/samba/smb.conf; systemctl %s nmbd smbd' % ('start' if on else 'stop')
        threading.Thread(target=run, args=(['bash', '-c', cmd],), kwargs={'timeout': 30}, daemon=True).start()

    def share_login(self):
        """(user, password) for the games share. The 0.1.3 base maps sdos -> root; older bases log in as root."""
        user = 'sdos' if os.path.exists('/etc/samba/sdos-users.map') else 'root'
        return user, (self.get_setting('root.password') or 'sdos')

    @staticmethod
    def ip_addr():
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('10.255.255.255', 1)); ip = s.getsockname()[0]; s.close()
            return '' if ip.startswith('127.') else ip
        except Exception:
            return ''

    # ---------- updates: app layer only (see ota.py) ----------
    def check_update(self):
        def job():
            self.busy['upd'] = True
            try:
                if not self.wifi_status:
                    self.post('upd', 'err:Connect Wi-Fi to check'); return
                try:
                    kind, feed = ota.check(VERSION)
                    self.update_feed = feed
                    if kind == 'new':
                        self.post('upd', 'new:' + feed['version'])
                    elif kind == 'base':
                        self.post('upd', 'err:%s needs a fresh install from the website' % feed['version'])
                    else:
                        self.post('upd', 'none:You have the latest version')
                except Exception as e:
                    log('update check failed: %r' % e)
                    self.post('upd', "err:Couldn't reach the update server")
            finally:
                self.busy['upd'] = False
        bg(job)

    def apply_update(self):
        feed = getattr(self, 'update_feed', None)
        if not feed:
            return
        def job():
            self.busy['upd'] = True
            try:
                try:
                    ver = ota.install(feed)
                except Exception as e:
                    log('update install failed: %r' % e)
                    self.post('upd', 'err:' + ('Download was damaged, try again' if 'checksum' in str(e) else 'Update failed, nothing changed'))
                    return
                self.post('upd', 'reboot:Restarting into %s' % ver)
                time.sleep(1.5)
                os._exit(0)          # essway.service (Restart=always) starts the new layer
            finally:
                self.busy['upd'] = False
        bg(job)

    # ---------- launching games ----------
    def joy_controllers(self):
        return getattr(self, 'controllers', '')

    def launch(self, game):
        d = self.sysdefs.get(game['sys'])
        if not d:
            return None
        emu = self.get_setting('emulator', game['sys']) or d['emu']
        core = self.get_setting('core', game['sys']) or d['core']
        emu, core = self.pick_core(game['sys'], d, emu, core)
        if game['sys'] in ('gb', 'gbc', 'gbh', 'gbch'):
            self._ensure_gb_analogue()
        cmd = d['cmd'] or '/usr/bin/runemu.sh %ROM% -P%SYSTEM% --core=%CORE% --emulator=%EMULATOR% --controllers="%CONTROLLERSCONFIG%"'
        cmd = (cmd.replace('%ROM%', shlex.quote(game['path'])).replace('%SYSTEM%', game['sys'])
               .replace('%CORE%', core or '').replace('%EMULATOR%', emu or '').replace('%CONTROLLERSCONFIG%', self.joy_controllers().replace('"', '')))
        saves.ensure(SAVE_FOLDERS)          # quick: folders, config and mounts in place before the game starts
        self.game = dict(game, emu=emu, core=core)
        self.game_con = None
        env = dict(os.environ)
        for k in ('SDL_VIDEO_WAYLAND_WMCLASS', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'PYTHONFAULTHANDLER', 'PYTHONUNBUFFERED'):
            env.pop(k, None)   # the game must not inherit the UI's app_id or Python setup
        try:
            btnswap.apply(*btnswap.flags())
            env.update(btnswap.launch_env())
        except Exception as e:
            log('btn swap launch apply failed: %r' % (e,))
        self.proc = subprocess.Popen(['bash', '-c', cmd], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return self.proc

    @staticmethod
    def core_ok(emu, core):
        """True when the emulator/core the launcher would run exists in this SYSTEM."""
        if not emu or not core:
            return False
        if emu == 'retroarch':
            return any(os.path.exists('%s/%s_libretro.so' % (d, core)) for d in ('/tmp/cores', '/usr/lib/libretro'))
        if emu == 'mednafen':
            return os.path.exists('/usr/bin/start_mednafen.sh')
        if emu == 'portmaster':
            return True
        return os.path.exists('/usr/bin/start_%s.sh' % core.rsplit('-', 1)[0])

    def pick_core(self, sid, d, emu, core):
        if sid == 'pico-8' and emu == 'pico-8' and not pico8_runnable():
            emu, core = 'retroarch', 'fake08'          # official PICO-8 is not included; fake-08 plays .p8/.png carts
        if self.core_ok(emu, core):
            return emu, core
        for e, c in d.get('emus', []):
            if self.core_ok(e, c):
                log('%s: %s/%s missing, using %s/%s' % (sid, emu, core, e, c)); return e, c
        return emu, core

    def launch_tool(self, tool):
        """Start a tool script like a game (Menu -> Quit works the same way)."""
        tid, label, note, how = tool
        path, killname, is_ra = how[1], how[2], how[3]
        if not os.path.exists(path):
            return None
        self.game = {'title': label, 'sys': 'tool', 'path': path, 'emu': 'retroarch' if is_ra else 'tool', 'kill': killname}
        self.game_con = None
        env = dict(os.environ)
        for k in ('SDL_VIDEO_WAYLAND_WMCLASS', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'PYTHONFAULTHANDLER', 'PYTHONUNBUFFERED'):
            env.pop(k, None)
        try:
            btnswap.apply(*btnswap.flags())
            env.update(btnswap.launch_env())
        except Exception as e:
            log('btn swap tool apply failed: %r' % (e,))
        log('tool: %s (%s)' % (label, path))
        self.proc = subprocess.Popen(['bash', path], env=env, cwd='/storage', stdout=open('/var/log/sdui-tool.log', 'ab'),
                                     stderr=subprocess.STDOUT, start_new_session=True)
        return self.proc

    def tool_available(self, tool):
        how = tool[3]
        if how[0] == 'script':
            return os.path.exists(how[1])
        if how[1] == 'music':
            from . import music
            return music.available()
        return True

    def scan_scummvm(self, done):
        """ROCKNIX's ScummVM scan (games in roms/scummvm -> .scummvm entries), without restarting the UI."""
        def job():
            run(['bash', '-c', 'bash /usr/bin/start_scummvm.sh add; bash /usr/bin/start_scummvm.sh create'], timeout=300)
            n = len(glob.glob('/storage/.config/scummvm/games/*.scummvm'))
            self._systems_cache = None
            self.post('call', lambda: done(n))
        bg(job)

    def clean_mac_files(self):
        n = 0
        for dp, dns, fns in os.walk('/storage/roms'):
            for fn in fns + dns:
                if fn.startswith('._') or fn == '.DS_Store':
                    p = os.path.join(dp, fn)
                    try:
                        if os.path.isdir(p) and not os.path.islink(p):
                            import shutil; shutil.rmtree(p)
                        else:
                            os.remove(p)
                        n += 1
                    except Exception:
                        pass
        return n

    # ---------- power ----------
    def power(self, action):
        log('power: %s' % action)
        run(['sync'], timeout=20)
        bg(run, ['systemctl', 'reboot' if action == 'restart' else 'poweroff'])

    # ---------- device model (which device tree the boot partition uses) ----------
    def current_model(self):
        return hw.running_dt()

    def is_default_h_tree(self):
        return is_default_h_tree(self.current_model())

    FLASH_RW = 'ro=0; grep -q " /flash [^ ]* ro[, ]" /proc/mounts && { mount -o remount,rw /flash && ro=1; }; '
    FLASH_RO = '; r=$?; sync; [ $ro = 1 ] && mount -o remount,ro /flash; exit $r'
    TRIAL = '/flash/sdos-model-trial'

    def _flash(self, body):
        rc, _ = run(['bash', '-c', self.FLASH_RW + body + self.FLASH_RO], timeout=30)
        return rc == 0

    def _scrub_wifi_txt(self, path):
        path = path or WIFITXT.WIFI_TXT_PATH
        # Anything not on the boot partition (tests, a copied file) is a plain rewrite.
        flash = os.path.realpath(WIFITXT.WIFI_TXT_PATH)
        try:
            on_flash = os.path.realpath(path) == flash or path == WIFITXT.WIFI_TXT_PATH
        except Exception:
            on_flash = path == WIFITXT.WIFI_TXT_PATH
        if not on_flash:
            return super()._scrub_wifi_txt(path)
        tmp = '/tmp/wifi.txt'
        try:
            open(tmp, 'wb').write(WIFITXT.wifi_txt_template_bytes())
        except Exception:
            return False
        return self._flash('cp -f %s /flash/wifi.txt.new && mv -f /flash/wifi.txt.new /flash/wifi.txt' % tmp)


    def set_model(self, dtb):
        """Switch dtb.img on trial: the old one is kept as dtb.prev.img and the next boot must confirm the new one,
        otherwise the UI puts the old one back after 30 s (see model_trial)."""
        src = '/flash/device_trees/%s.dtb' % dtb
        if MODEL_AUTO or not os.path.exists(src):
            return False
        ok = self._flash('cp -f /flash/dtb.img /flash/dtb.prev.img && printf "%%s\\n%%s\\n" "%s" "%s" > %s && '
                         'cp -f "%s" /flash/dtb.img.new && mv -f /flash/dtb.img.new /flash/dtb.img'
                         % (dtb, self.current_model(), self.TRIAL, src))
        log('set model %s ok=%s' % (dtb, ok))
        return ok

    def model_trial(self):
        """(new, previous) when this boot is the first one after a model switch, else None."""
        try:
            new, prev = (open(self.TRIAL).read().splitlines() + ['', ''])[:2]
        except Exception:
            return None
        if not os.path.exists('/flash/dtb.prev.img'):
            return None
        return new, prev

    def confirm_model(self):
        self._flash('rm -f %s' % self.TRIAL)

    def revert_model(self):
        ok = self._flash('cp -f /flash/dtb.prev.img /flash/dtb.img.new && mv -f /flash/dtb.img.new /flash/dtb.img && rm -f %s' % self.TRIAL)
        log('model trial not confirmed: reverted to the previous dtb ok=%s' % ok)
        if ok:
            self.power('restart')
        return ok

    def refresh_set_device_bat(self):
        """0.1.4 over the air: rewrite SET-DEVICE.bat on the SDOS drive with the plain model names."""
        if MODEL_AUTO:      # RK3566 image: U-Boot picks the device tree; there is nothing to choose
            return
        want = set_device_bat().encode('ascii')
        try:
            if open('/flash/SET-DEVICE.bat', 'rb').read() == want:
                return
        except Exception:
            pass
        tmp = '/tmp/SET-DEVICE.bat'
        open(tmp, 'wb').write(want)
        self._flash('cp -f %s /flash/SET-DEVICE.bat.new && mv -f /flash/SET-DEVICE.bat.new /flash/SET-DEVICE.bat' % tmp)

    def game_running(self):
        return self.proc is not None and self.proc.poll() is None

    # RetroArch network commands (enabled for every game by our runemu patch)
    def ra(self, cmd, want=False):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(0.4)
            s.sendto(cmd.encode(), ('127.0.0.1', 55355))
            if want:
                data, _ = s.recvfrom(4096); return data.decode(errors='ignore')
        except Exception:
            return ''
        finally:
            try: s.close()
            except Exception: pass
        return ''

    def is_ra(self):
        return bool(self.game) and self.game.get('emu') == 'retroarch'

    def _focused_con(self):
        rc, out = run(['swaymsg', '-t', 'get_tree'], timeout=3)
        if rc != 0:
            return None
        try:
            tree = json.loads(out)
        except Exception:
            return None
        stack = [tree]
        while stack:
            n = stack.pop()
            if n.get('focused') and n.get('type') in ('con', 'floating_con'):
                return n.get('id')
            stack += n.get('nodes', []) + n.get('floating_nodes', [])
        return None

    def pause_game(self):
        """Called when Menu is tapped in a game: grab a still, pause, raise the UI."""
        self.game_con = self._focused_con()
        run(['grim', '-t', 'png', '-l', '1', '/tmp/sdui_pause.png'], timeout=3)
        if self.is_ra():
            st = self.ra('GET_STATUS', True)
            if 'PLAYING' in st:
                self.ra('PAUSE_TOGGLE')
            self._frozen = False
        else:
            run(['rocknix-games-freeze', 'freeze'], timeout=6)
            self._frozen = True
        run(['swaymsg', '[app_id="sdui"] focus, fullscreen enable'], timeout=3)

    def resume_game(self):
        if self.game_con:
            run(['swaymsg', '[con_id=%d] focus, fullscreen enable' % self.game_con], timeout=3)
        if getattr(self, '_frozen', False):
            run(['rocknix-games-freeze', 'thaw'], timeout=6); self._frozen = False
        if self.is_ra():
            time.sleep(0.15)
            if 'PAUSED' in self.ra('GET_STATUS', True):
                self.ra('PAUSE_TOGGLE')

    def game_save(self):
        if self.is_ra():
            self.ra('SAVE_STATE'); return 'Saved', False
        if self.game and self.game.get('sys') == 'psp':
            self.resume_game(); time.sleep(0.4); self.key_tap(60); return 'Saved', True   # F2 in PPSSPP
        return 'This system saves from its own menu', False

    def game_load(self):
        if self.is_ra():
            self.ra('LOAD_STATE'); self.resume_game(); return 'Loaded', True
        if self.game and self.game.get('sys') == 'psp':
            self.resume_game(); time.sleep(0.4); self.key_tap(62); return 'Loaded', True   # F4 in PPSSPP
        return 'This system loads from its own menu', False

    def emu_menu(self):
        """In-game menu > Emulator settings: open the running emulator's own menu, then hand the game back.
        Leaving that menu returns straight to the game."""
        g = self.game or {}
        if self.is_ra():
            self.resume_game(); time.sleep(0.2); self.ra('MENU_TOGGLE'); return 'RetroArch menu', True
        key = EMU_MENU_KEYS.get((g.get('core') or '').rsplit('-', 1)[0])
        if key:
            code, mods = key
            self.resume_game(); time.sleep(0.4); self.key_tap(code, mods); return '', True
        return 'This emulator opens its menu with its own button', False

    def quit_game(self):
        """Ask the emulator to exit and raise the menu immediately.

        The menu used to wait on the whole launch wrapper (up to 4s, then a
        systemd stop, then SIGTERM/KILL). SRAM / memory-card data is flushed
        on RetroArch QUIT; a second QUIT covers quit_press_twice if the
        session config still has it on. The reap has a few-second cap so a
        heavy core (PS1 especially) cannot linger in the background.
        """
        if getattr(self, '_frozen', False):
            run(['rocknix-games-freeze', 'thaw'], timeout=6); self._frozen = False
        if self.is_ra():
            self.ra('QUIT')
            self.ra('QUIT')
        else:
            data = ''
            try: data = open('/tmp/.process-kill-data').read().strip()
            except Exception: pass
            if self.game and self.game.get('kill'):
                data = data or self.game['kill']
            if data:
                run(['bash', '-c', 'killall ' + data], timeout=5)
        self.raise_ui()
        if not getattr(self, '_reaping', False):
            self._reaping = True
            bg(self._reap_game)

    def _reap_game(self):
        # Give RetroArch a few seconds to flush the memory card and exit.
        # Then SIGTERM, then SIGKILL — do not wait 8s+ on a stuck PS1 core.
        try:
            for _ in range(30):
                if not self.game_running():
                    return
                time.sleep(0.1)
            if not self.game_running():
                return
            try: os.killpg(self.proc.pid, 15)
            except Exception: pass
            run(['bash', '-c', 'systemctl stop "game-*.scope"'], timeout=2)
            for _ in range(10):
                if not self.game_running():
                    return
                time.sleep(0.1)
            try: os.killpg(self.proc.pid, 9)
            except Exception: pass
            for _ in range(10):
                if not self.game_running():
                    return
                time.sleep(0.1)
        finally:
            self._reaping = False

    # uinput keyboard so PPSSPP can be told to save/load (F2/F4 are bound in its controls.ini)
    def _init_uinput(self):
        try:
            fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
            fcntl.ioctl(fd, 0x40045564, 1)            # UI_SET_EVBIT EV_KEY
            for k in UINPUT_KEYS:                     # F2/F4 (PPSSPP save/load) + emulator menu keys
                fcntl.ioctl(fd, 0x40045565, k)        # UI_SET_KEYBIT
            name = b'sdui-keys'.ljust(80, b'\0')
            dev = name + struct.pack('<HHHHI', 3, 0x5344, 0x0001, 1, 0) + b'\0' * (64 * 4 * 4)
            os.write(fd, dev)
            fcntl.ioctl(fd, 0x5501)                   # UI_DEV_CREATE
            self.uinput = fd
        except Exception:
            self.uinput = None

    def key_tap(self, code, mods=()):
        if self.uinput is None:
            return
        def ev(t, c, v):
            now = time.time()
            return struct.pack('<qqHHi', int(now), int((now % 1) * 1e6), t, c, v)
        try:
            for m in mods: os.write(self.uinput, ev(1, m, 1) + ev(0, 0, 0))
            os.write(self.uinput, ev(1, code, 1) + ev(0, 0, 0)); time.sleep(0.08)
            os.write(self.uinput, ev(1, code, 0) + ev(0, 0, 0))
            for m in mods: os.write(self.uinput, ev(1, m, 0) + ev(0, 0, 0))
        except Exception:
            pass

    def raise_ui(self):
        run(['swaymsg', '[app_id="sdui"] focus, fullscreen enable'], timeout=3)

    def _read_proc(self, path):
        try:
            return open(path).read()
        except Exception:
            return ''

    def smb_active(self):
        ports = tcp_established_local_ports(self._read_proc('/proc/net/tcp'))
        ports |= tcp_established_local_ports(self._read_proc('/proc/net/tcp6'))
        return bool(ports & SMB_PORTS)

    def net_bytes(self):
        return net_dev_bytes(self._read_proc('/proc/net/dev'))

    def disk_sectors(self):
        return diskstats_sectors(self._read_proc('/proc/diskstats'))

    def suspend(self):
        bg(run, ['systemctl', 'suspend'])


def make():
    if os.environ.get('SDUI_MOCK') == '1' or not os.path.exists('/usr/bin/runemu.sh'):
        return Mock()
    return Device()
