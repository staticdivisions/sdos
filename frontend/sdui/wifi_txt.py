# wifi.txt on the SDOS boot partition (/flash/wifi.txt).
# People can fill this in on a computer so they never have to type a password
# on the handheld D-pad. After a non-empty network= is read, the file is
# rewritten to the blank template so the password is not left in plaintext
# on the FAT32 card.
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WIFI_TXT_PATH = '/flash/wifi.txt'
WIFI_TXT_KEYS_NET = ('network', 'ssid')
WIFI_TXT_KEYS_PW = ('password', 'pass', 'psk')


def wifi_txt_template_bytes():
    """Blank wifi.txt as UTF-8 with Windows CRLF (Notepad-safe, no BOM)."""
    path = os.path.join(HERE, 'wifi.txt')
    text = open(path, 'r', encoding='utf-8').read()
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if not text.endswith('\n'):
        text += '\n'
    return text.replace('\n', '\r\n').encode('utf-8')


def parse_wifi_txt(data):
    """Parse wifi.txt contents. Returns (ssid, password) or (None, None) if network is blank.

    Accepts Windows CRLF, UTF-8 BOM, surrounding whitespace, optional matching quotes,
    spaces in SSIDs, special characters in passwords, and open networks (empty password).
    Keys: network= (alias ssid=), password= (aliases pass=, psk=).
    """
    if not data:
        return None, None
    if isinstance(data, str):
        data = data.encode('utf-8')
    if data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        text = data.decode('utf-8', 'replace')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    found = {}
    for raw in text.split('\n'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, val = line.split('=', 1)
        key = key.strip().lower()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        if key in WIFI_TXT_KEYS_NET or key in WIFI_TXT_KEYS_PW:
            found[key] = val
    ssid = None
    for k in WIFI_TXT_KEYS_NET:
        if k in found:
            ssid = found[k]
            break
    if not ssid:
        return None, None
    psk = ''
    for k in WIFI_TXT_KEYS_PW:
        if k in found:
            psk = found[k]
            break
    return ssid, psk


def write_wifi_txt_template(path):
    """Atomically replace path with the blank CRLF template. Returns the bytes written."""
    data = wifi_txt_template_bytes()
    folder = os.path.dirname(os.path.abspath(path)) or '.'
    tmp = os.path.join(folder, '.wifi.txt.new')
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return data
