# sdOS over-the-air updates for the app layer (this frontend), not the kernel or base system.
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
#
# Feed (JSON at OTA_URL):
#   {"version": "0.1.1", "url": "https://.../sdos-app-0.1.1.tar.gz", "sha256": "<hex>",
#    "size": 123, "notes": "What changed", "min_base": "0.1.0", "platforms": ["H700", "RK3566"]}
#   "platforms" is optional (absent = every image family).
# RK3566 0.1.9+ fetches latest-rk3566.json instead of latest.json (see feed_url).
# Tarball layout: sdui/ (the package, with sdui/VERSION) and manifest.json.
#
# On the device (APP_DIR = /storage/.config/sdui/app):
#   v<ver>/sdui/...   installed layers
#   current  -> v<ver>   symlink used by /usr/bin/sd-ui.sh (falls back to the built-in copy)
#   previous -> v<ver> | builtin
#   trial, trial.count   a new layer is on probation: the launcher rolls back to `previous`
#                        if it fails to start twice; the app calls confirm() once it is up.
import os, re, ssl, json, time, shutil, tarfile, hashlib, urllib.request

# H700 (and older clients) read latest.json. RK3566 0.1.9+ reads latest-rk3566.json
# so an H700-only layer is never offered to an RK image. Override with SDUI_OTA_URL.
DEFAULT_OTA_URL = 'https://sd-os-updates.pages.dev/latest.json'
RK_OTA_URL = 'https://sd-os-updates.pages.dev/latest-rk3566.json'


def feed_url():
    override = os.environ.get('SDUI_OTA_URL')
    if override:
        return override
    try:
        from .hw import PLATFORM
        if str(PLATFORM).upper() == 'RK3566':
            return RK_OTA_URL
    except Exception:
        pass
    return DEFAULT_OTA_URL


OTA_URL = feed_url()
APP_DIR = os.environ.get('SDUI_APP_DIR', '/storage/.config/sdui/app')


def vtuple(x):
    return tuple(int(p) for p in re.findall(r'\d+', str(x or '0')))


def base_version():
    if os.environ.get('SDUI_BASE_VERSION'):
        return os.environ['SDUI_BASE_VERSION']
    try:
        for ln in open('/etc/os-release'):
            if ln.startswith('SD_VERSION='):
                return ln.split('=', 1)[1].strip().strip('"')
    except Exception:
        pass
    return '0'


def _ctx():
    for ca in ('/etc/ssl/cert.pem', '/etc/ssl/cacert.pem'):
        if os.path.exists(ca):
            return ssl.create_default_context(cafile=ca)
    return ssl.create_default_context()


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': 'sdOS-updater', 'Cache-Control': 'no-cache'})
    return urllib.request.urlopen(req, timeout=timeout, context=_ctx())


def fetch_feed(url=OTA_URL):
    sep = '&' if '?' in url else '?'
    with _get(url + sep + 't=%d' % int(time.time())) as r:
        feed = json.loads(r.read().decode())
    for k in ('version', 'url', 'sha256'):
        if not feed.get(k):
            raise ValueError('feed missing ' + k)
    if not re.fullmatch(r'[0-9a-f]{64}', feed['sha256']):
        raise ValueError('bad sha256 in feed')
    return feed


def check(running_version, url=OTA_URL):
    """-> ('new', feed) | ('none', feed) | ('base', feed) when a full reflash is needed."""
    feed = fetch_feed(url)
    if vtuple(feed['version']) <= vtuple(running_version):
        return 'none', feed
    # optional "platforms": ["H700", "RK3566"]: a layer is only offered to the image families it lists
    plats = feed.get('platforms')
    if isinstance(plats, list) and plats:
        from .hw import PLATFORM
        if PLATFORM not in [str(p).upper() for p in plats]:
            return 'none', feed
    if feed.get('min_base') and vtuple(base_version()) < vtuple(feed['min_base']):
        return 'base', feed
    return 'new', feed


def _safe_extract(tar, dest):
    root = os.path.realpath(dest)
    for m in tar.getmembers():
        p = os.path.realpath(os.path.join(dest, m.name))
        if not (p == root or p.startswith(root + os.sep)):
            raise ValueError('unsafe path in update: ' + m.name)
        if not (m.isfile() or m.isdir()):
            raise ValueError('links/devices not allowed in update: ' + m.name)
    tar.extractall(dest, filter='data') if hasattr(tarfile, 'data_filter') else tar.extractall(dest)


def _swap(link, target):
    tmp = link + '.new'
    if os.path.lexists(tmp):
        os.remove(tmp)
    os.symlink(target, tmp)
    os.replace(tmp, link)          # rename(2): atomic


def install(feed, progress=None, app_dir=APP_DIR):
    """Download, verify, unpack, compile-check and activate. Raises on any failure (nothing changes)."""
    ver = str(feed['version'])
    if not re.fullmatch(r'[0-9A-Za-z.\-]+', ver):
        raise ValueError('bad version')
    os.makedirs(app_dir, exist_ok=True)
    part = os.path.join(app_dir, '.download.part')
    h = hashlib.sha256(); got = 0; total = int(feed.get('size') or 0)
    with _get(feed['url'], timeout=30) as r, open(part, 'wb') as f:
        while True:
            b = r.read(1 << 16)
            if not b:
                break
            h.update(b); f.write(b); got += len(b)
            if progress and total:
                progress(got / total)
    if h.hexdigest() != feed['sha256']:
        os.remove(part)
        raise ValueError('checksum mismatch')
    stage = os.path.join(app_dir, '.stage')
    shutil.rmtree(stage, ignore_errors=True); os.makedirs(stage)
    try:
        with tarfile.open(part, 'r:gz') as t:
            _safe_extract(t, stage)
        pkg = os.path.join(stage, 'sdui')
        if not os.path.isfile(os.path.join(pkg, '__main__.py')):
            raise ValueError('update has no sdui package')
        if open(os.path.join(pkg, 'VERSION')).read().strip() != ver:
            raise ValueError('update version does not match the feed')
        for dp, _, fs in os.walk(pkg):          # catch syntax errors before switching over
            for fn in fs:
                if fn.endswith('.py'):
                    fp = os.path.join(dp, fn)
                    with open(fp, 'rb') as f:
                        compile(f.read(), fp, 'exec')
        dst = os.path.join(app_dir, 'v' + ver)
        shutil.rmtree(dst, ignore_errors=True)
        os.rename(stage, dst)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if os.path.exists(part):
            os.remove(part)
    cur = os.path.join(app_dir, 'current')
    prev = os.readlink(cur) if os.path.islink(cur) else 'builtin'
    if prev == 'v' + ver:
        prev = os.readlink(os.path.join(app_dir, 'previous')) if os.path.islink(os.path.join(app_dir, 'previous')) else 'builtin'
    _swap(os.path.join(app_dir, 'previous'), prev)
    with open(os.path.join(app_dir, 'trial'), 'w') as f:
        f.write(ver + '\n')
    with open(os.path.join(app_dir, 'trial.count'), 'w') as f:
        f.write('0\n')
    _swap(cur, 'v' + ver)
    # keep only current + previous
    for d in os.listdir(app_dir):
        if d.startswith('v') and d not in ('v' + ver, prev):
            shutil.rmtree(os.path.join(app_dir, d), ignore_errors=True)
    os.sync()
    return ver


def confirm(app_dir=APP_DIR):
    """Called once the UI has been up for a few seconds: the trial version is good."""
    t = os.path.join(app_dir, 'trial')
    if not os.path.exists(t):
        return None
    try:
        ver = open(t).read().strip()
    except Exception:
        ver = ''
    for f in ('trial', 'trial.count'):
        try:
            os.remove(os.path.join(app_dir, f))
        except FileNotFoundError:
            pass
    return ver


def rolled_back(app_dir=APP_DIR):
    """Return and clear the last rollback note written by the launcher, if any."""
    p = os.path.join(app_dir, 'rolledback')
    if not os.path.exists(p):
        return None
    try:
        v = open(p).read().strip()
    finally:
        os.remove(p)
    return v
