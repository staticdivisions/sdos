# Build the sdOS app-layer OTA bundle + feed.
# usage: python3 tools_ota_pack.py <outdir> <base_url> [notes] [min_base]
#   -> <outdir>/app/sdos-app-<ver>.tar.gz, <outdir>/latest.json
import os, sys, io, json, gzip, tarfile, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
out, base = sys.argv[1], sys.argv[2].rstrip('/')
notes = sys.argv[3] if len(sys.argv) > 3 else ''
min_base = sys.argv[4] if len(sys.argv) > 4 else '0.1.0'
src = os.path.join(HERE, 'sdui')
ver = open(os.path.join(src, 'VERSION')).read().strip()
os.makedirs(os.path.join(out, 'app'), exist_ok=True)
name = 'sdos-app-%s.tar.gz' % ver
MT = 1763164800  # fixed mtime -> reproducible bundle
def add(t, path, arc):
    ti = t.gettarinfo(path, arc); ti.uid = ti.gid = 0; ti.uname = ti.gname = 'root'; ti.mtime = MT
    ti.mode = 0o755 if ti.isdir() else 0o644
    if ti.isfile():
        with open(path, 'rb') as f: t.addfile(ti, f)
    else: t.addfile(ti)
raw = io.BytesIO()
with tarfile.open(fileobj=raw, mode='w', format=tarfile.GNU_FORMAT) as t:
    man = json.dumps({'name': 'sdOS app layer', 'version': ver, 'min_base': min_base}, indent=1).encode()
    ti = tarfile.TarInfo('manifest.json'); ti.size = len(man); ti.mtime = MT; ti.mode = 0o644
    t.addfile(ti, io.BytesIO(man))
    add(t, src, 'sdui')
    for dp, dns, fns in os.walk(src):
        dns[:] = sorted(d for d in dns if d != '__pycache__')
        for d in dns: add(t, os.path.join(dp, d), os.path.relpath(os.path.join(dp, d), HERE))
        for fn in sorted(fns):
            if fn.endswith('.pyc'): continue
            add(t, os.path.join(dp, fn), os.path.relpath(os.path.join(dp, fn), HERE))
gz = io.BytesIO()
with gzip.GzipFile(fileobj=gz, mode='wb', compresslevel=9, mtime=MT) as g: g.write(raw.getvalue())
data = gz.getvalue()
open(os.path.join(out, 'app', name), 'wb').write(data)
sha = hashlib.sha256(data).hexdigest()
feed = {'version': ver, 'url': '%s/app/%s' % (base, name), 'sha256': sha, 'size': len(data),
        'notes': notes, 'min_base': min_base, 'channel': 'stable', 'device': 'h700'}
open(os.path.join(out, 'latest.json'), 'w').write(json.dumps(feed, indent=1) + '\n')
open(os.path.join(out, 'app', name + '.sha256'), 'w').write('%s  %s\n' % (sha, name))
print(json.dumps(feed))
