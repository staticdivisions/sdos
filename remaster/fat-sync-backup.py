#!/usr/bin/env python3
# After relabelling a FAT32 partition, copy its boot sector over the backup boot sector
# (BPB_BkBootSec) so fsck.fat sees no "differences between boot sector and its backup".
# usage: fat-sync-backup.py <disk image> <partition byte offset>
import sys, struct
img, off = sys.argv[1], int(sys.argv[2])
with open(img, 'r+b') as f:
    f.seek(off); bs = f.read(512)
    assert bs[510:512] == b'\x55\xaa' and bs[82:90] == b'FAT32   ', 'not a FAT32 boot sector'
    bps = struct.unpack_from('<H', bs, 11)[0]; bk = struct.unpack_from('<H', bs, 50)[0]
    assert bps == 512 and 0 < bk < 32, (bps, bk)
    assert bs[65] == 0, 'FAT dirty flag set'
    f.seek(off + bk * bps); old = f.read(512)
    f.seek(off + bk * bps); f.write(bs)
    print('backup boot sector %d synced (%d bytes differed), label %r' % (bk, sum(a != b for a, b in zip(old, bs)), bs[71:82].decode()))
