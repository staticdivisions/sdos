#!/bin/bash
# Local end-to-end OTA test: feed -> download -> verify -> install -> select -> trial -> rollback.
set -euo pipefail
FE=$(cd "$(dirname "$0")" && pwd); SEL=$FE/../remaster/overlay/usr/bin/sd-ui-select.sh
T=$(mktemp -d); trap 'kill $SRV 2>/dev/null; rm -rf $T' EXIT
export SDUI_BASE_VERSION=0.1.0 SDUI_APP_DIR=$T/app SDUI_BUILTIN=$FE SDUI_OTA_URL=http://127.0.0.1:8899/latest.json
mkver() { rm -rf $T/fe$1; mkdir -p $T/fe$1; cp -r $FE/sdui $T/fe$1/; cp $FE/tools_ota_pack.py $T/fe$1/; echo $1 > $T/fe$1/sdui/VERSION; }
mkdir -p $T/site; python3 -m http.server 8899 -d $T/site >/dev/null 2>&1 & SRV=$!; sleep 1
publish() { python3 $T/fe$1/tools_ota_pack.py $T/site http://127.0.0.1:8899 "test $1" >/dev/null; }
ota() { ( cd $FE && python3 -c "import sys; from sdui import ota; $1" ); }
pass() { echo "PASS: $*"; }

mkver 0.1.0; publish 0.1.0
[ "$(ota "print(ota.check('0.1.0')[0])")" = none ] && pass "same version -> up to date"
[ "$($SEL)" = "$FE" ] && pass "no layer -> built-in"

mkver 0.1.1; publish 0.1.1
[ "$(ota "print(ota.check('0.1.0')[0])")" = new ] && pass "0.1.1 offered to 0.1.0"
ota "k,f=ota.check('0.1.0'); print(ota.install(f))" >/dev/null
[ "$(readlink $T/app/current)" = v0.1.1 ] && [ "$(readlink $T/app/previous)" = builtin ] && [ -f $T/app/trial ] && pass "installed, on trial, previous=builtin"
[ "$($SEL)" = "$T/app/current" ] && pass "launcher picks the new layer"
ota "print(ota.confirm())" >/dev/null; [ ! -f $T/app/trial ] && pass "confirm clears trial"

# tampered download is refused, nothing changes
mkver 0.1.2; publish 0.1.2; python3 - $T/site/latest.json <<'PY'
import json,sys; p=sys.argv[1]; f=json.load(open(p)); f['sha256']='0'*64; json.dump(f,open(p,'w'))
PY
if ota "k,f=ota.check('0.1.1'); ota.install(f)" 2>/dev/null; then echo FAIL; exit 1; fi
[ "$(readlink $T/app/current)" = v0.1.1 ] && pass "bad checksum refused, still 0.1.1"

# syntax error is caught before switching
mkver 0.1.3; echo "def broken(:" >> $T/fe0.1.3/sdui/app.py; publish 0.1.3
if ota "k,f=ota.check('0.1.1'); ota.install(f)" 2>/dev/null; then echo FAIL; exit 1; fi
[ "$(readlink $T/app/current)" = v0.1.1 ] && pass "syntax error refused, still 0.1.1"

# compiles but crashes at start -> launcher rolls back after 2 failed starts
mkver 0.1.4; echo "raise SystemExit('boom')" > $T/fe0.1.4/sdui/__main__.py; publish 0.1.4
ota "k,f=ota.check('0.1.1'); ota.install(f)" >/dev/null
[ "$(readlink $T/app/current)" = v0.1.4 ] && [ "$(readlink $T/app/previous)" = v0.1.1 ] && pass "0.1.4 installed on trial"
for i in 1 2; do R=$($SEL); ( cd $R && PYTHONPATH=$R python3 -m sdui 2>/dev/null ) || true; done
R=$($SEL)
[ "$(readlink $T/app/current)" = v0.1.1 ] && [ "$R" = "$T/app/current" ] && [ "$(cat $T/app/rolledback)" = 0.1.4 ] && pass "crashing 0.1.4 rolled back to 0.1.1"
[ "$(ota "print(ota.rolled_back())")" = 0.1.4 ] && pass "app sees rollback note"
ls $T/app
echo ALL OK
