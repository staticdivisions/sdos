#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# sdOS: remaster of the official ROCKNIX H700 (DDR4) image.
# Usage: sudo ./remaster.sh <ROCKNIX-H700...img.gz> <out.img.gz> [workdir]
# Needs: squashfs-tools (zstd), mtools, pigz, sfdisk, python3, aarch64-linux-gnu-gcc, python3-pil + SDL2 (splash art).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(cd "$HERE/.." && pwd)
IN=$1; OUT=$2; W=${3:-$(mktemp -d)}
mkdir -p "$W"

echo "== splash (rendered from the frontend's boot screen, then cross-compiled)"
if [ ! -x "$SRC/splash/sdos-splash" ] || [ "$SRC/frontend/sdui/app.py" -nt "$SRC/splash/logo.h" ]; then
  ( cd "$SRC/frontend" && SDL_VIDEODRIVER=offscreen python3 tools_splash.py ../splash )
  aarch64-linux-gnu-gcc -O2 -s -Wall -o "$SRC/splash/sdos-splash" "$SRC/splash/sdos-splash.c"
fi

echo "== card-removal watcher (static, cross-compiled)"
if [ ! -x "$SRC/cardwatch/sdos-cardwatch" ] || [ "$SRC/cardwatch/sdos-cardwatch.c" -nt "$SRC/cardwatch/sdos-cardwatch" ]; then
  aarch64-linux-gnu-gcc -O2 -s -static -Wall -o "$SRC/cardwatch/sdos-cardwatch" "$SRC/cardwatch/sdos-cardwatch.c"
fi

echo "== unpack"
pigz -dc "$IN" > "$W/img"
P1=$(sfdisk -d "$W/img" | awk -F'[=,]' '/img1/{gsub(/ /,"",$2); print $2}')
OFF=$((P1*512))
mcopy -n -o -i "$W/img@@$OFF" ::SYSTEM "$W/SYSTEM.orig"
mcopy -n -o -i "$W/img@@$OFF" ::KERNEL "$W/KERNEL.orig"
rm -rf "$W/sys"; unsquashfs -q -no-progress -d "$W/sys" "$W/SYSTEM.orig"
"$HERE/patch-system.sh" "$W/sys" "$SRC"

echo "== kernel: sdOS splash in the built-in initramfs (same size, re-gzipped in place)"
python3 "$HERE/patch-initramfs.py" "$W/KERNEL.orig" "$W/KERNEL" "$SRC/splash/sdos-splash"
[ "$(stat -c %s "$W/KERNEL")" = "$(stat -c %s "$W/KERNEL.orig")" ]

echo "== repack"
rm -f "$W/SYSTEM"
mksquashfs "$W/sys" "$W/SYSTEM" -comp zstd -Xcompression-level 19 -b 1M -noappend -no-progress >/dev/null
echo "$(md5sum < "$W/SYSTEM" | cut -d' ' -f1)  target/SYSTEM" > "$W/SYSTEM.md5"
echo "$(md5sum < "$W/KERNEL" | cut -d' ' -f1)  target/KERNEL" > "$W/KERNEL.md5"
mcopy -o -i "$W/img@@$OFF" "$W/SYSTEM" "$W/SYSTEM.md5" "$W/KERNEL" "$W/KERNEL.md5" ::
# boot partition label SDOS (the kernel args find it by label)
mcopy -n -o -i "$W/img@@$OFF" ::extlinux/extlinux.conf "$W/extlinux.conf"
sed -i 's/^LABEL ROCKNIX$/LABEL sdOS/; s/boot=LABEL=ROCKNIX /boot=LABEL=SDOS /' "$W/extlinux.conf"
grep -q 'boot=LABEL=SDOS ' "$W/extlinux.conf" && ! grep -q ROCKNIX "$W/extlinux.conf"
mcopy -o -i "$W/img@@$OFF" "$W/extlinux.conf" ::extlinux/extlinux.conf
mlabel -i "$W/img@@$OFF" ::SDOS
python3 "$HERE/fat-sync-backup.py" "$W/img" "$OFF"
# SET-DEVICE.bat: pick the handheld model on a PC (copies its device tree to dtb.img)
python3 "$HERE/make-set-device-bat.py" "$W/SET-DEVICE.bat"
mcopy -o -i "$W/img@@$OFF" "$W/SET-DEVICE.bat" ::SET-DEVICE.bat
unix2dos -n "$SRC/build/SOURCE_OFFER.txt" "$W/SOURCE_OFFER.txt" 2>/dev/null || sed 's/$/\r/' "$SRC/build/SOURCE_OFFER.txt" > "$W/SOURCE_OFFER.txt"
mcopy -o -i "$W/img@@$OFF" "$W/SOURCE_OFFER.txt" ::SOURCE_OFFER.txt
# ROCKNIX H700 boots only with a per-device /dtb.img on the boot partition. Default: RG35XX H.
DTB=${SDOS_DTB:-sun50i-h700-anbernic-rg35xx-h}
mcopy -n -o -i "$W/img@@$OFF" ::device_trees/$DTB.dtb "$W/dtb.img"
mcopy -o -i "$W/img@@$OFF" "$W/dtb.img" ::dtb.img
# zero the FAT's free clusters (old SYSTEM data) so the image compresses like upstream
FREE=$(mdir -i "$W/img@@$OFF" :: | tr -d ' ' | sed -n 's/^\([0-9]*\)bytesfree$/\1/p')
ZB=$(( (FREE / 1048576 - 4) ))
if [ "$ZB" -gt 0 ]; then
  dd if=/dev/zero of="$W/zero.bin" bs=1M count="$ZB" status=none
  mcopy -i "$W/img@@$OFF" "$W/zero.bin" ::ZERO.BIN && mdel -i "$W/img@@$OFF" ::ZERO.BIN
  rm -f "$W/zero.bin"
fi
pigz -9 -c "$W/img" > "$OUT"
( cd "$(dirname "$OUT")" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256" )
echo "done: $OUT"
