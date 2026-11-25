# Local tests for Bluetooth XML parsing, controller flags, and the mock Settings flow.
# usage: python3 tools_bt_test.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SDUI_MOCK'] = '1'
from sdui.device import parse_bt_devices, fold_bt_listing, Mock
from sdui.main import controller_flags
from sdui.app import App
from sdui.gfx import Gfx

def check(cond, msg):
    if not cond:
        raise SystemExit('FAIL: ' + msg)
    print('PASS:', msg)

LIST = '''
<device id="E4:17:D8:11:22:33" name="8BitDo SN30 Pro" type="joystick" connected="yes" />
<device id="00:1A:7D:DA:71:13" name="WH-1000XM4" type="audio" connected="no" />
'''
devs = parse_bt_devices(LIST)
check(len(devs) == 2, 'parse two devices')
check(devs[0]['mac'] == 'E4:17:D8:11:22:33' and devs[0]['connected'], 'joystick connected')
check(devs[1]['name'] == 'WH-1000XM4' and not devs[1]['connected'], 'headset paired but not connected')

listing = '''
<device id="AA:BB:CC:00:11:22" name="Pad" status="added" type="joystick" />
<device id="AA:BB:CC:00:11:22" name="Pad" status="removed" type="joystick" />
<device id="11:22:33:44:55:66" name="Buds" status="added" type="audio" />
'''
found = fold_bt_listing(listing)
check(len(found) == 1 and found[0]['name'] == 'Buds', 'listing fold removes then keeps')

pads = [
    {'idx': 0, 'guid': 'aaaa', 'name': 'Built In', 'nbbuttons': 16, 'nbhats': 1, 'nbaxes': 4},
    {'idx': 1, 'guid': 'bbbb', 'name': '8BitDo SN30 Pro', 'nbbuttons': 16, 'nbhats': 0, 'nbaxes': 6},
]
flags = controller_flags(pads)
check('-p1index 0' in flags and '-p2index 1' in flags, 'p1 and p2 flags present')
check('-p2name 8BitDo_SN30_Pro' in flags, 'p2 name underscored')
check('-p3index' not in flags, 'no p3 when only two pads')

# Mock UI flow
class FakeGfx:
    W, H = 640, 480
    def __getattr__(self, name):
        def fn(*a, **k):
            return 0
        return fn

# Avoid SDL: only test item building and keys that don't draw
dev = Mock()
check(dev.bt_present() and not dev.bt_on(), 'mock has BT, starts off')
# Build a minimal app-like walk using device methods
dev.bt_enable()
check(dev.bt_on(), 'enable turns it on')
dev.bt_pair('E4:17:D8:11:22:33')
check(any(d['mac'].endswith('22:33') and d['connected'] for d in dev.bt_paired), 'pair moves pad to connected')
dev.bt_disconnect('E4:17:D8:11:22:33')
check(any(d['mac'].endswith('22:33') and not d['connected'] for d in dev.bt_paired), 'disconnect clears connected')
dev.bt_forget('E4:17:D8:11:22:33')
check(not any(d['mac'].endswith('22:33') for d in dev.bt_paired), 'forget removes pad')
dev.bt_disable()
check(not dev.bt_on(), 'disable turns it off')

# No em-dashes in new UI copy
from sdui import app as AP
src = open(os.path.join(os.path.dirname(AP.__file__), 'app.py'), encoding='utf-8').read()
# only scan our new methods roughly
start = src.find('def bt_row_status')
chunk = src[start:src.find('def set_items')]
check('\u2014' not in chunk and '\u2013' not in chunk, 'no en/em dashes in Bluetooth UI copy')
print('ALL OK')
