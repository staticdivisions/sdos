#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# sdOS: print the app-layer directory to run (handles OTA trial + rollback).
### Pick the app layer: an OTA-installed one (if newer than the built-in copy) or the built-in one.
### A freshly installed layer is "on trial": if it fails to come up twice, roll back to the previous one.
BUILTIN=${SDUI_BUILTIN:-/usr/share/sd-ui}
APP=${SDUI_APP_DIR:-/storage/.config/sdui/app}
mkdir -p "${APP}"
ver() { cat "$1/sdui/VERSION" 2>/dev/null; }
newer() { [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -n1)" = "$1" ]; }

if [ -f "${APP}/trial" ]; then
  N=$(cat "${APP}/trial.count" 2>/dev/null); N=$(( ${N:-0} + 1 ))
  echo "${N}" > "${APP}/trial.count"
  if [ "${N}" -gt 2 ]; then
    BAD=$(cat "${APP}/trial")
    PREV=$(readlink "${APP}/previous" 2>/dev/null)
    python3 - "${APP}" "${PREV}" <<'PY'
import os, sys
app, prev = sys.argv[1], sys.argv[2]
cur = os.path.join(app, 'current')
if prev and prev != 'builtin' and os.path.isfile(os.path.join(app, prev, 'sdui', '__main__.py')):
    tmp = cur + '.new'
    if os.path.lexists(tmp): os.remove(tmp)
    os.symlink(prev, tmp); os.replace(tmp, cur)
elif os.path.lexists(cur):
    os.remove(cur)
PY
    echo "${BAD}" > "${APP}/rolledback"
    echo "$(date) rolled back from ${BAD} to ${PREV:-builtin}" >> "${APP}/rollback.log"
    rm -f "${APP}/trial" "${APP}/trial.count"
    sync
  fi
fi

ROOT="${BUILTIN}"
if [ -f "${APP}/current/sdui/__main__.py" ] && newer "$(ver "${APP}/current")" "$(ver "${BUILTIN}")"; then
  ROOT="${APP}/current"
fi

echo "${ROOT}"
