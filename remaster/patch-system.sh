#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Applies every sdOS change to an unsquashed ROCKNIX SYSTEM tree.
# Usage: sudo ./patch-system.sh <sysroot> <sd-os source dir>
set -euo pipefail
S=$1; SRC=$2; HERE=$SRC/remaster
cd "$S"

echo "== 1. frontend"
rm -rf usr/share/sd-ui; mkdir -p usr/share/sd-ui
cp -r "$SRC/frontend/sdui" usr/share/sd-ui/sdui
find usr/share/sd-ui -name __pycache__ -prune -exec rm -rf {} +
cp "$SRC/frontend/sdui/VERSION" usr/share/sd-ui/VERSION
cp "$SRC/build/SOURCE_OFFER.txt" usr/share/sd-ui/SOURCE_OFFER.txt
install -m 755 "$HERE/overlay/usr/bin/sd-ui.sh" usr/bin/sd-ui.sh
install -m 755 "$HERE/overlay/usr/bin/sd-ui-select.sh" usr/bin/sd-ui-select.sh
chmod -R u=rwX,go=rX usr/share/sd-ui

echo "== 2. make it the UI service (unit name kept: other scripts reference essway.service)"
U=usr/lib/systemd/system/essway.service
sed -i 's#^Description=.*#Description=sdOS UI on Sway#; s#^ExecStart=.*#ExecStart=/usr/bin/sd-ui.sh#' $U
grep -q '^ExecStart=/usr/bin/sd-ui.sh$' $U
# 0.1.2: diagnostics + crash fallback
install -m 755 "$HERE/overlay/usr/bin/sdos-collect-logs" usr/bin/sdos-collect-logs
install -D -m 755 "$HERE/overlay/usr/lib/sdos/sdos-error.py" usr/lib/sdos/sdos-error.py
install -D -m 644 "$HERE/overlay/usr/lib/systemd/system/essway.service.d/30-sdos.conf" usr/lib/systemd/system/essway.service.d/30-sdos.conf
for u in sdos-logs@.service sdos-logs-early.timer sdos-logs-late.timer; do
  install -m 644 "$HERE/overlay/usr/lib/systemd/system/$u" usr/lib/systemd/system/$u
done
mkdir -p usr/lib/systemd/system/timers.target.wants
ln -sf ../sdos-logs-early.timer usr/lib/systemd/system/timers.target.wants/sdos-logs-early.timer
ln -sf ../sdos-logs-late.timer usr/lib/systemd/system/timers.target.wants/sdos-logs-late.timer

echo "== 3. strip EmulationStation, themes, scraper, bezel downloader"
rm -f usr/bin/emulationstation usr/bin/start_es.sh usr/bin/rocknix-scraper usr/bin/rocknix-es-thebezelproject \
      usr/lib/systemd/system/emustation.service
rm -rf usr/share/themes/es-theme-* usr/config/emulationstation/resources usr/config/emulationstation/themes
# keep es_systems.cfg (system/emulator table) and es_input.cfg (pad mapping): the launcher reads them

echo "== 4. defaults"
C=usr/config/system/configs/system.cfg
sed -i 's#^global.bezel=.*#global.bezel=none#; s#^updates.enabled=.*#updates.enabled=0#; s#^system.hostname=.*#system.hostname=sdos#' $C
grep -q '^system.hostname=sdos$' $C
grep -q '^psp.auto_frame_skip=' $C || printf '\n# sdOS: conservative H700 PSP default\npsp.auto_frame_skip=1\n' >> $C

echo "== 5. RetroArch network commands for the in-game menu (localhost UDP 55355)"
R=usr/bin/runemu.sh
if ! grep -q 'sdOS: the in-game menu' $R; then
  sed -i '/### Enable RetroArch Network Control for this session on dual-screen devices/i\
    ### sdOS: the in-game menu pauses/saves/loads/quits RetroArch over its local command port\
    echo '"'"'network_cmd_enable = "true"'"'"' >> "${RETROARCH_APPEND_CONFIG}"\
    echo '"'"'network_cmd_port = "55355"'"'"'  >> "${RETROARCH_APPEND_CONFIG}"\
    echo '"'"'quit_press_twice = "false"'"'"'  >> "${RETROARCH_APPEND_CONFIG}"\
' $R
fi
grep -q 'sdOS: the in-game menu' $R
if ! grep -q 'quit_press_twice' $R; then
  sed -i '/network_cmd_port = "55355"/a\
    echo '"'"'quit_press_twice = "false"'"'"'  >> "${RETROARCH_APPEND_CONFIG}"\
' $R
fi
grep -q 'quit_press_twice' $R

echo "== 6. PPSSPP: conservative H700 defaults + keyboard save/load keys for the in-game menu"
P=usr/config/ppsspp/PSP/SYSTEM
sed -i 's#^FrameSkip = .*#FrameSkip = 1#; s#^AnisotropyLevel = .*#AnisotropyLevel = 0#' $P/ppsspp.ini
# F2/F4 are appended to whatever the image binds (H700: 10-4010 / 10-4008; RK3566: button combos)
sed -i '/1-132/! s#^\(Save State = .*[^ ]\)$#\1,1-132#; /1-134/! s#^\(Load State = .*[^ ]\)$#\1,1-134#' $P/controls.ini
grep -q '^Save State = .*,1-132$' $P/controls.ini && grep -q '^Load State = .*,1-134$' $P/controls.ini

echo "== 7. folders: one per system sdOS lists (frontend/sdui/device.py SYSTEMS)"
D=usr/config/system-dirs.conf
PYTHONDONTWRITEBYTECODE=1 python3 - "$D" "$SRC/frontend" <<'PY'
import re,sys
p=sys.argv[1]; sys.path.insert(0, sys.argv[2])
from sdui.device import SYSTEMS
keep={f for _, _, _, f, _ in SYSTEMS} | {'bios', 'savestates', 'music'}
out=[]
for l in open(p):
    m=re.match(r'^d\s+/storage/roms/([^/\s]+)/?\s',l)
    if m and m.group(1) not in keep: continue
    out.append(l)
open(p,'w').writelines(out)
PY

echo "== 8. branding: sdOS (ROCKNIX credited in About + licenses)"
sed -i 's#^OS_NAME=.*#OS_NAME="sdOS"#; s#^HOME_URL=.*#HOME_URL="https://staticdivisions.com"#' etc/os-release
grep -q '^NAME=' etc/os-release || printf 'NAME="sdOS"\nPRETTY_NAME="sdOS by Static Divisions"\nBASED_ON="ROCKNIX"\n' >> etc/os-release
grep -q '^SD_VERSION=' etc/os-release || echo "SD_VERSION=\"$(cat "$SRC/frontend/sdui/VERSION")\"" >> etc/os-release
cp "$HERE/overlay/etc/motd" etc/motd
echo "sdOS $(cat "$SRC/frontend/sdui/VERSION")" > etc/issue

echo "== 9. no telemetry"
rm -f usr/lib/systemd/system/*.wants/rocknix-report-stats.timer usr/lib/systemd/system/*.wants/rocknix-report-stats.service
rm -f usr/lib/systemd/system/rocknix-report-stats.timer usr/lib/systemd/system/rocknix-report-stats.service

echo "== 10. licenses"
L=usr/share/licenses/sdos; mkdir -p $L
cp "$SRC/frontend/sdui/fonts/OFL.txt" $L/Manrope-OFL.txt
for f in GPL-2 GPL-3 LGPL-2.1; do [ -e /usr/share/common-licenses/$f ] && cp /usr/share/common-licenses/$f $L/$f.txt; done
cp "$SRC/build/SOURCE_OFFER.txt" $L/SOURCE_OFFER.txt
cat > $L/README.txt <<TXT
sdOS by Static Divisions: a simple handheld system for ${SDOS_FAMILY:-Anbernic H700 devices}.
Built on ROCKNIX (https://rocknix.org, https://github.com/ROCKNIX/distribution), GPL-2.0,
upstream build 20261101 (commit cefc14339a4ae18c02bb69888f27835e50664b60). Thank you, ROCKNIX team.
Frontend (/usr/share/sd-ui): GPL-2.0-or-later. Font: Manrope, SIL Open Font License 1.1.
Emulators keep their own licenses (RetroArch GPL-3.0, PPSSPP GPL-2.0, libretro cores various).
No BIOS files, games or keys are included.
TXT

echo "== 12. 0.1.3: GAMES drive, network share, names, quieter logs"
# first boot: STORAGE 4 GiB (cards 12-24 GiB) or 8 GiB (24 GiB+) + exFAT GAMES partition; smaller cards keep the upstream layout; fatlabel on a read-only /flash
install -m 0755 "$HERE/overlay/usr/lib/rocknix/fs-resize" usr/lib/rocknix/fs-resize
# automount: an exFAT games partition left dirty (unclean power-off, card pulled from a PC) gets fsck.exfat -p first
python3 - usr/bin/automount <<'PY'
import sys; p = sys.argv[1]; s = open(p).read()
a = '        log $0 "Mounting ${1} on ${MOUNT_PATH}"\n'
assert s.count(a) == 1, 'automount anchor'
b = ('        if [ "${FSTYPE}" = "exfat" ]; then\n'
     '          VF=$(dd if=${1} bs=1 skip=106 count=1 2>/dev/null | od -An -tu1 | tr -d " ")\n'
     '          if [ -n "${VF}" ] && [ $(( VF & 2 )) -ne 0 ]; then\n'
     '            log $0 "exFAT volume ${1} was not cleanly unmounted, checking."\n'
     '            /usr/sbin/fsck.exfat -p ${1} >/dev/null 2>&1\n'
     '          fi\n'
     '        fi\n')
open(p, 'w').write(s.replace(a, b + a))
PY
C=usr/config/system/configs/system.cfg
sed -i 's/^root.password=.*/root.password=sdos/; s/^samba.enabled=.*/samba.enabled=1/; s/^system.hostname=.*/system.hostname=sdos/; s/^system.automount=.*/system.automount=1/' $C
grep -q '^system.gamesdevice=' $C || echo 'system.gamesdevice=/dev/disk/by-label/GAMES' >> $C
grep -q '^root.password=sdos$' $C && grep -q '^samba.enabled=1$' $C && grep -q '^system.hostname=sdos$' $C && grep -q '^system.automount=1$' $C
echo sdos > etc/hostname
# Samba: one authenticated [games] share (Windows 11 refuses guest shares); config/logs need the login; no update/themes shares
cp "$HERE/overlay/usr/config/smb.conf" usr/config/smb.conf
printf 'root = sdos\n' > etc/samba/sdos-users.map
# Sway: every new window (File Explorer terminal, RetroArch, PPSSPP...) opens fullscreen and focused over the menu
grep -q 'sdOS: new windows' usr/share/sway/config.kiosk || cat >> usr/share/sway/config.kiosk <<'SW'
# sdOS: new windows open fullscreen and take focus (tools were starting hidden behind the menu)
for_window [app_id=".*"] fullscreen enable, focus
for_window [class=".*"] fullscreen enable, focus
SW
# udev: input_sense restarts on hotplug; don't log a failure when it isn't running
sed -i 's#RUN+="/usr/bin/killall input_sense"#RUN+="/bin/sh -c \x27/usr/bin/killall input_sense 2>/dev/null; exit 0\x27"#' usr/lib/udev/rules.d/99-input.rules
! grep -q 'RUN+="/usr/bin/killall input_sense"' usr/lib/udev/rules.d/99-input.rules
# NetworkManager: no dispatcher chatter in the journal (no dispatcher scripts are installed)
grep -q '^\[logging\]' etc/NetworkManager/NetworkManager.conf || printf '\n[logging]\n# sdOS: no dispatcher scripts exist; keep its messages out of the journal\ndomains=DEFAULT,DISPATCH:ERR\n' >> etc/NetworkManager/NetworkManager.conf

# power safety: card-removal watcher (powers off instead of hanging dark), power key hold = clean shut down
install -m 0755 "$SRC/cardwatch/sdos-cardwatch" usr/bin/sdos-cardwatch
install -m 0644 "$HERE/overlay/usr/lib/systemd/system/sdos-cardwatch.service" usr/lib/systemd/system/sdos-cardwatch.service
mkdir -p usr/lib/systemd/system/multi-user.target.wants
ln -sf ../sdos-cardwatch.service usr/lib/systemd/system/multi-user.target.wants/sdos-cardwatch.service
install -D -m 0644 "$HERE/overlay/usr/lib/systemd/logind.conf.d/50-sdos.conf" usr/lib/systemd/logind.conf.d/50-sdos.conf
install -D -m 0755 "$HERE/overlay/usr/lib/sdos/sdos-smbpass" usr/lib/sdos/sdos-smbpass
install -D -m 0644 "$HERE/overlay/usr/lib/systemd/system/smbd.service.d/30-sdos.conf" usr/lib/systemd/system/smbd.service.d/30-sdos.conf
# udev: treat the SDOS / GAMES partitions like ROCKNIX / STORAGE
sed -i 's/ENV{ID_FS_LABEL}!="ROCKNIX|STORAGE"/ENV{ID_FS_LABEL}!="ROCKNIX|SDOS|STORAGE|GAMES"/' usr/lib/udev/rules.d/61-rocknix-internal-emmc.rules

echo "== 13. 0.1.6/0.1.7: Game Boy ignores stick-as-D-pad (phantom presses on stick-less XX models)"
C=usr/config/system/configs/system.cfg
for k in gb.analogue gbc.analogue gbh.analogue gbch.analogue; do
  if grep -q "^${k}=" "$C"; then sed -i "s/^${k}=.*/${k}=0/" "$C"; else echo "${k}=0" >> "$C"; fi
done
for k in gb gbc gbh gbch; do grep -q "^${k}.analogue=0$" "$C"; done

echo "== 11. sanity"
for f in usr/bin/sd-ui.sh usr/bin/sd-ui-select.sh usr/bin/sdos-collect-logs usr/bin/runemu.sh usr/bin/start_ppsspp.sh usr/bin/python3 usr/lib/rocknix/fs-resize usr/bin/automount usr/lib/sdos/sdos-smbpass; do [ -x "$f" ] || { echo "not executable: $f"; exit 1; }; done
[ -e usr/config/emulationstation/es_systems.cfg ] && [ -e usr/config/emulationstation/es_input.cfg ]
bash -n usr/bin/automount && sh -n usr/lib/rocknix/fs-resize && bash -n usr/bin/sd-ui.sh && bash -n usr/bin/sd-ui-select.sh && bash -n usr/bin/sdos-collect-logs && bash -n usr/bin/runemu.sh
echo "patched OK"
