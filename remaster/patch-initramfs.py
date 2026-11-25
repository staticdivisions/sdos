#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Swap the ROCKNIX boot splash in the kernel's built-in initramfs for the sdOS splash,
# and rebrand the few user-visible strings in /init. The kernel Image keeps its size:
# the new gzip'd initramfs is written over the old one and zero-padded (the kernel's
# initramfs unpacker skips zero padding).
# usage: patch-initramfs.py <KERNEL in> <KERNEL out> <sdos-splash binary>
import sys, gzip, zlib

kin, kout, splash = sys.argv[1:4]
d = bytearray(open(kin, 'rb').read())

# locate the compressed newc cpio: gzip (H700 kernels) or lzop (RK3566 kernels, CONFIG_INITRAMFS_COMPRESSION_LZO)
import struct, subprocess

def lzop_len(b, p):
    """Byte length of the lzop stream starting at b[p] (header + blocks + end marker)."""
    q = p + 9
    ver, = struct.unpack_from('>H', b, q); q += 4                 # version, lib version
    if ver >= 0x0940: q += 2                                       # version needed
    q += 1                                                         # method
    if ver >= 0x0940: q += 1                                       # level
    flags, = struct.unpack_from('>I', b, q); q += 4
    if flags & 0x800: q += 4                                       # filter
    q += 8                                                         # mode, mtime low
    if ver >= 0x0940: q += 4                                       # mtime high
    q += 1 + b[q] + 4                                              # name, header checksum
    while True:
        dst, = struct.unpack_from('>I', b, q); q += 4
        if dst == 0: return q - p
        src, = struct.unpack_from('>I', b, q); q += 4
        q += 4 * (bool(flags & 1) + bool(flags & 0x100))           # adler32 / crc32 of the data
        if src < dst: q += 4 * (bool(flags & 2) + bool(flags & 0x200))
        q += src

def lzop(args, data):
    return subprocess.run(['lzop'] + args, input=data, stdout=subprocess.PIPE, check=True).stdout

KIND = None; off = -1; i = -1
while True:
    i = d.find(b'\x1f\x8b\x08', i + 1)
    if i < 0: break
    try:
        o = zlib.decompressobj(31); head = o.decompress(bytes(d[i:i + 4096]))
        if head.startswith(b'070701'):
            off = i; KIND = 'gzip'; break
    except Exception:
        pass
if off < 0:
    i = -1
    while True:
        i = d.find(b'\x89LZO\x00\r\n\x1a\n', i + 1)
        if i < 0: break
        try:
            n = lzop_len(d, i)
            body = lzop(['-dc'], bytes(d[i:i + n]))
        except Exception:
            continue
        if body.startswith(b'070701'):
            off = i; KIND = 'lzop'; glen = n; cpio = body; break
assert off > 0, 'initramfs not found'
if KIND == 'gzip':
    o = zlib.decompressobj(31); cpio = o.decompress(bytes(d[off:]))
    glen = len(d) - off - len(o.unused_data)

def entries(b):
    p = 0
    while True:
        h = b[p:p + 110]; assert h[:6] == b'070701', 'bad cpio at %d' % p
        f = [int(h[6 + 8 * k:14 + 8 * k], 16) for k in range(13)]
        nsz, fsz = f[11], f[6]
        name = b[p + 110:p + 110 + nsz - 1].decode()
        dp = (p + 110 + nsz + 3) & ~3
        data = b[dp:dp + fsz]
        yield f, name, data
        p = (dp + fsz + 3) & ~3
        if name == 'TRAILER!!!': return

def pad(x): return x + b'\0' * (-len(x) % 4)

def entry(f, name, data):
    f = list(f); nb = name.encode() + b'\0'; f[11] = len(nb); f[6] = len(data)
    h = b'070701' + b''.join(b'%08X' % v for v in f)
    return pad(h + nb) + pad(data)

INIT_EDITS = [
    (b'/usr/bin/rocknix-splash', b'/usr/bin/sdos-splash'),
    (b'echo "ROCKNIX" > ${g}/strings/0x409/manufacturer', b'echo "sdOS" > ${g}/strings/0x409/manufacturer'),
    (b'echo "Please re-install ROCKNIX"', b'echo "Please re-install sdOS"'),
    # 0.1.3: nothing printed over the splash (the issue line + "\n\n" also scrolled the console and shifted it)
    (b'  echo -en "\\033[1000H\\033[2K$(cat /sysroot/etc/issue)\\n\\n" >/dev/console\n', b''),
    (b'==> Loading, please wait...', b''),
    (b'==> Initializing, please wait...', b'  Setting up sdOS...'),
    # friendlier, shorter fsck prompt (same logic)
    (b'echo "Filesystem corruption has been detected!"', b'echo "sdOS found a problem on the card and will repair it."'),
    (b'echo "To prevent an automatic repair attempt continuing,"', b'echo "Press a key within 15 seconds to cancel."'),
    (b'echo "press any key or power off your system within the next 120 seconds"', b'true'),
    (b'read -t120 -n1', b'read -t15 -n1'),
    (b'echo "Forced fsck failed. Your system is broken beyond repair"', b'echo "The card could not be repaired."'),
]
out = bytearray(); seen = set()
for f, name, data in entries(cpio):
    if name == 'usr/bin/rocknix-splash':
        assert f[4] == 1, 'splash is hardlinked'
        name, data = 'usr/bin/sdos-splash', open(splash, 'rb').read(); seen.add('splash')
    elif name == 'init':
        for a, b in INIT_EDITS:
            assert a in data, 'init edit not found: %r' % a
            data = data.replace(a, b)
        seen.add('init')
    out += entry(f, name, data)
assert seen == {'splash', 'init'}, seen
new = gzip.compress(bytes(out), compresslevel=9, mtime=0) if KIND == 'gzip' else lzop(['-9c', '--no-name', '--no-mode', '--no-time'], bytes(out))
if KIND == 'gzip' and len(new) > glen:
    # 0.1.8: the larger splash art no longer fits at gzip -9; zopfli (pigz -11) is plain deflate, just denser
    z = subprocess.run(['pigz', '-11', '-n', '-m', '-c'], input=bytes(out), stdout=subprocess.PIPE, check=True).stdout
    print('initramfs gzip -9 %d bytes > %d; zopfli %d bytes' % (len(new), glen, len(z)))
    new = z
print('initramfs %s: old %d bytes, new %d bytes' % (KIND, glen, len(new)))
assert len(new) <= glen, 'new initramfs does not fit'
d[off:off + glen] = new + b'\0' * (glen - len(new))
open(kout, 'wb').write(d)
# verify
if KIND == 'gzip':
    o = zlib.decompressobj(31); back = o.decompress(bytes(d[off:]))
else:
    back = lzop(['-dc'], bytes(d[off:off + lzop_len(d, off)]))
assert back == bytes(out)
names = [n for _, n, _ in entries(back)]
assert 'usr/bin/sdos-splash' in names and 'usr/bin/rocknix-splash' not in names
print('ok: %d entries, kernel size unchanged (%d)' % (len(names), len(d)))
