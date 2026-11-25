#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# sdOS frontend launcher. Replaces start_es.sh as essway.service ExecStart.
# Derived from ROCKNIX start_es.sh, Copyright (C) 2024 ROCKNIX (https://github.com/ROCKNIX)
# 0.1.2: no exec (exit code is logged), crash counter, visible error screen, logs copied to /flash/sdos-logs.
LOG=/var/log/sd-ui.log
RUN=/run/sdos; mkdir -p "${RUN}"
sdlog() { echo "$(date '+%F %T') [sd-ui.sh] $*" >>"${LOG}"; }
sdlog "launcher start (pid $$)"

### same per-boot setup ES used (timezone, locale, quirk env)
. /usr/bin/es_settings >>"${LOG}" 2>&1
LOG=/var/log/sd-ui.log; RUN=/run/sdos   # re-set: ROCKNIX profile defines its own helpers/vars

### Pre-rotate the frontend and the games it starts where the plane can't rotate the mode
SD_MODE=$(cat /sys/class/drm/card*-"${WLR_CON}"/modes 2>/dev/null | head -n1)
prerotate_env "${WLR_CON_TRANSFORM}" "${SD_MODE%%x*}"
scanout_reset_stale

### Pick the app layer (OTA layer if newer than built-in; trial/rollback handled there)
ROOT=$(/usr/bin/sd-ui-select.sh 2>>"${LOG}")
[ -f "${ROOT}/sdui/__main__.py" ] || ROOT=/usr/share/sd-ui
# 2+ crashes in a row: skip any OTA layer and run the built-in copy
if [ "$(cat "${RUN}/fails" 2>/dev/null || echo 0)" -ge 2 ] && [ "${ROOT}" != /usr/share/sd-ui ]; then
  sdlog "recent crashes: using the built-in app layer instead of ${ROOT}"; ROOT=/usr/share/sd-ui
fi
ver() { cat "$1/sdui/VERSION" 2>/dev/null; }

### Sway must be up (the UI is a Wayland client of it)
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/var/run/0-runtime-dir} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-1}
export SWAYSOCK=${SWAYSOCK:-${XDG_RUNTIME_DIR}/sway-ipc.0.sock} SDL_VIDEODRIVER=${SDL_VIDEODRIVER:-wayland}
for i in $(seq 1 30); do [ -S "${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}" ] && break; sleep 0.5; done
[ -S "${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}" ] || sdlog "WARNING: no Wayland socket at ${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}"

mkdir -p /storage/.config/sdui
export HOME=/storage
export PYTHONPATH="${ROOT}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONFAULTHANDLER=1
export PYTHONUNBUFFERED=1
cd "${ROOT}"
sdlog "starting sdOS app layer $(ver "${ROOT}") from ${ROOT} (WAYLAND_DISPLAY=${WAYLAND_DISPLAY} SDL_VIDEODRIVER=${SDL_VIDEODRIVER})"
T0=$(date +%s)
/usr/bin/python3 -m sdui >>"${LOG}" 2>&1
RC=$?
DUR=$(( $(date +%s) - T0 ))
sdlog "sd-ui exited rc=${RC} after ${DUR}s"

[ "${RC}" -eq 0 ] && { rm -f "${RUN}/fails"; exit 0; }   # clean exit (e.g. OTA restart)

### Crash: count quick failures; a long run resets the count
N=$(cat "${RUN}/fails" 2>/dev/null); N=${N:-0}
[ "${DUR}" -ge 120 ] && N=0
N=$((N + 1)); echo "${N}" >"${RUN}/fails"
/usr/bin/sdos-collect-logs crash >/dev/null 2>&1 &

if [ "${N}" -ge 3 ]; then
  sdlog "sd-ui failed ${N} times in a row: showing the error screen"
  wait
  /usr/bin/python3 /usr/lib/sdos/sdos-error.py "${LOG}" >>"${LOG}" 2>&1
  ERC=$?
  sdlog "error screen exited rc=${ERC}"
  if [ "${ERC}" -ne 0 ]; then
    # last resort: Sway's own message bar
    timeout 600 swaynag -t warning -m "sdOS could not start its menu. Logs were copied to the SDOS drive: sdos-logs folder. Restarting in 10 minutes." >>"${LOG}" 2>&1
  fi
  rm -f "${RUN}/fails"
fi
exit "${RC}"
