#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# sdOS for RK3566 handhelds: remaster of the two official ROCKNIX RK3566 images (same KERNEL + SYSTEM,
# different U-Boot). Makes:
#   sdOS-<ver>-rk3566.img.gz    from "Generic": U-Boot finds the device tree itself (FDTDIR)
#   sdOS-<ver>-rk3566-b.img.gz  from "Specific": X55 / X35S / RG DS / RG DS Plus; extlinux loads /dtb.img
#                               (X55 by default), chosen in Settings > Device model or SET-DEVICE.bat
# Usage: sudo ./remaster-rk3566.sh <ROCKNIX-RK3566...-Generic.img.gz> <ROCKNIX-RK3566...-Specific.img.gz> <outdir> [workdir]
# Needs: squashfs-tools (zstd), mtools, pigz, sfdisk, lzop, python3, aarch64-linux-gnu-gcc.
set -euo pipefail
export PATH=$PATH:/usr/sbin:/sbin
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(cd "$HERE/.." && pwd)
GEN=$1; SPEC=$2; OUTD=$3; W=${4:-$(mktemp -d)}
VER=$(cat "$SRC/frontend/sdui/VERSION")
mkdir -p "$W" "$OUTD"
export SDOS_FAMILY="Anbernic and Powkiddy RK3566 handhelds"

echo "== splash (size-optimised build: the RK3566 kernel's LZO initramfs has little slack)"
if [ ! -f "$SRC/splash/logo.h" ]; then
  ( cd "$SRC/frontend" && SDL_VIDEODRIVER=offscreen python3 tools_splash.py ../splash )
fi
aarch64-linux-gnu-gcc -Os -s -Wall -ffunction-sections -fdata-sections -Wl,--gc-sections -Wl,-z,max-page-size=4096 \
  -o "$W/sdos-splash" "$SRC/splash/sdos-splash.c"

echo "== card-removal watcher (static, cross-compiled)"
if [ ! -x "$SRC/cardwatch/sdos-cardwatch" ] || [ "$SRC/cardwatch/sdos-cardwatch.c" -nt "$SRC/cardwatch/sdos-cardwatch" ]; then
  aarch64-linux-gnu-gcc -O2 -s -static -Wall -o "$SRC/cardwatch/sdos-cardwatch" "$SRC/cardwatch/sdos-cardwatch.c"
fi

p1off() { echo $(( $(sfdisk -d "$1" | awk -F'[=,]' '/img1 /{gsub(/ /,"",$2); print $2}') * 512 )); }

echo "== unpack (Generic)"
pigz -dc "$GEN" > "$W/gen.img"
OFF=$(p1off "$W/gen.img")
for f in SYSTEM KERNEL SYSTEM.md5 KERNEL.md5; do mcopy -n -o -i "$W/gen.img@@$OFF" ::$f "$W/$f.orig"; done
[ "$(md5sum < "$W/SYSTEM.orig" | cut -d' ' -f1)" = "$(cut -d' ' -f1 "$W/SYSTEM.md5.orig")" ]
[ "$(md5sum < "$W/KERNEL.orig" | cut -d' ' -f1)" = "$(cut -d' ' -f1 "$W/KERNEL.md5.orig")" ]
rm -rf "$W/sys"; unsquashfs -q -no-progress -d "$W/sys" "$W/SYSTEM.orig"
grep -q '^HW_DEVICE="RK3566"$' "$W/sys/etc/os-release"
"$HERE/patch-system.sh" "$W/sys" "$SRC"

echo "== kernel: sdOS splash in the built-in initramfs (same size)"
python3 "$HERE/patch-initramfs.py" "$W/KERNEL.orig" "$W/KERNEL" "$W/sdos-splash"
[ "$(stat -c %s "$W/KERNEL")" = "$(stat -c %s "$W/KERNEL.orig")" ]

echo "== SYSTEM"
rm -f "$W/SYSTEM"
mksquashfs "$W/sys" "$W/SYSTEM" -comp zstd -Xcompression-level 19 -b 1M -noappend -no-progress >/dev/null
rm -rf "$W/sys" "$W/SYSTEM.orig"
echo "$(md5sum < "$W/SYSTEM" | cut -d' ' -f1)  target/SYSTEM" > "$W/SYSTEM.md5"
echo "$(md5sum < "$W/KERNEL" | cut -d' ' -f1)  target/KERNEL" > "$W/KERNEL.md5"
sed 's/^sdOS is made by Static Divisions. This system image is built on ROCKNIX$/sdOS is made by Static Divisions. This system image is built on ROCKNIX RK3566/' \
  "$SRC/build/SOURCE_OFFER.txt" | sed 's/$/\r/' > "$W/SOURCE_OFFER.txt"

finish() {   # <img> <flavor: auto|pick> <out.img.gz>
  local IMG=$1 FL=$2 OUT=$3 O; O=$(p1off "$IMG")
  # upstream KERNEL/SYSTEM must be the ones we patched (both RK3566 images ship the same pair)
  mcopy -n -o -i "$IMG@@$O" ::KERNEL.md5 "$W/k.md5"; cmp -s "$W/k.md5" "$W/KERNEL.md5.orig"
  mcopy -n -o -i "$IMG@@$O" ::SYSTEM.md5 "$W/s.md5"; cmp -s "$W/s.md5" "$W/SYSTEM.md5.orig"
  mdel -i "$IMG@@$O" ::SYSTEM
  mcopy -o -i "$IMG@@$O" "$W/SYSTEM" "$W/SYSTEM.md5" "$W/KERNEL" "$W/KERNEL.md5" ::
  mcopy -n -o -i "$IMG@@$O" ::extlinux/extlinux.conf "$W/extlinux.conf"
  sed -i 's/^LABEL ROCKNIX$/LABEL sdOS/; s/boot=LABEL=ROCKNIX /boot=LABEL=SDOS /' "$W/extlinux.conf"
  if [ "$FL" = auto ]; then
    grep -q '^  FDTDIR /device_trees$' "$W/extlinux.conf"
  else
    DTB=$(sed -n 's#^  FDT /device_trees/\(.*\)\.dtb$#\1#p' "$W/extlinux.conf")
    [ "$DTB" = rk3566-powkiddy-x55 ]
    sed -i 's#^  FDT /device_trees/.*$#  FDT /dtb.img#' "$W/extlinux.conf"
    mcopy -n -o -i "$IMG@@$O" ::device_trees/$DTB.dtb "$W/dtb.img"
    mcopy -o -i "$IMG@@$O" "$W/dtb.img" ::dtb.img
    ( cd "$SRC/frontend" && SDUI_PLATFORM=RK3566 SDUI_MODEL_AUTO=0 PYTHONDONTWRITEBYTECODE=1 python3 "$HERE/make-set-device-bat.py" "$W/SET-DEVICE.bat" )
    mcopy -o -i "$IMG@@$O" "$W/SET-DEVICE.bat" ::SET-DEVICE.bat
  fi
  grep -q 'boot=LABEL=SDOS ' "$W/extlinux.conf" && ! grep -q ROCKNIX "$W/extlinux.conf"
  sed -i 's/\r//' "$W/extlinux.conf"
  mcopy -o -i "$IMG@@$O" "$W/extlinux.conf" ::extlinux/extlinux.conf
  mcopy -o -i "$IMG@@$O" "$W/SOURCE_OFFER.txt" ::SOURCE_OFFER.txt
  mlabel -i "$IMG@@$O" ::SDOS
  python3 "$HERE/fat-sync-backup.py" "$IMG" "$O"
  # zero the FAT's free clusters (old SYSTEM data) so the image compresses like upstream
  local FREE ZB
  FREE=$(mdir -i "$IMG@@$O" :: | tr -d ' ' | sed -n 's/^\([0-9]*\)bytesfree$/\1/p')
  ZB=$(( FREE / 1048576 - 4 ))
  if [ "$ZB" -gt 0 ]; then
    dd if=/dev/zero of="$W/zero.bin" bs=1M count="$ZB" status=none
    mcopy -i "$IMG@@$O" "$W/zero.bin" ::ZERO.BIN && mdel -i "$IMG@@$O" ::ZERO.BIN
    rm -f "$W/zero.bin"
  fi
  python3 "$HERE/fat-sync-backup.py" "$IMG" "$O"
  pigz -9 -c "$IMG" > "$OUT"
  ( cd "$(dirname "$OUT")" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256" )
  echo "done: $OUT"
}

echo "== image 1: sdOS-$VER-rk3566 (device tree found automatically)"
finish "$W/gen.img" auto "$OUTD/sdOS-$VER-rk3566.img.gz"
rm -f "$W/gen.img"
echo "== image 2: sdOS-$VER-rk3566-b (X55 / X35S / RG DS / RG DS Plus)"
pigz -dc "$SPEC" > "$W/spec.img"
finish "$W/spec.img" pick "$OUTD/sdOS-$VER-rk3566-b.img.gz"
rm -f "$W/spec.img"
