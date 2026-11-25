# Idle sleep: setup, jobs, transfers and Never must not call systemctl suspend.
# usage: SDL_VIDEODRIVER=offscreen python3 tools_sleep_test.py
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SDUI_MOCK'] = '1'
os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
from sdui import main as M, device
from sdui.device import (
    tcp_established_local_ports, net_dev_bytes, diskstats_sectors,
    SMB_PORTS, ACTIVITY_GRACE,
)
from sdui.gfx import Gfx
from sdui.app import App, SLEEP
from sdui import look as LK

def check(cond, msg):
    if not cond:
        raise SystemExit('FAIL: ' + msg)

def fresh(ren, W, H, shot=False):
    app = App(Gfx(ren, W, H), device.make(), shot=shot)
    app.set_look(LK.theme_look('teal'))
    app.setup_done = True
    app.ctx = 'home'
    app.screen = 'home'
    app.upd = 'idle'
    app.dev.busy.clear()
    app.dev._test_smb = False
    app.dev._test_net = 0
    app.dev._test_disk = 0
    app.dev._act_sample = (0, None, None)
    app.dev._act_until = 0
    return app

def hits_of(app):
    hits = []
    app.dev.suspend = lambda: hits.append(time.time())
    return hits

def fire(app, ago=120):
    app.sleep = 0   # 1 min
    app.last_input = time.time() - ago
    app.tick()
    return app

def test_parsers():
    tcp = (
        '  sl  local_address rem_address   st tx_queue rx_queue\n'
        '   0: 00000000:01BD 00000000:0000 0A 00000000:00000000\n'
        '   1: 2A01A8C0:01BD 2B01A8C0:C1C0 01 00000000:00000000\n'
        '   2: 2A01A8C0:0050 2C01A8C0:1234 01 00000000:00000000\n'
    )
    ports = tcp_established_local_ports(tcp)
    check(0x1BD in ports, 'established 445 is detected')
    check(0x50 in ports, 'established 80 is parsed')
    listen_only = (
        '  sl  local_address rem_address   st\n'
        '   0: 00000000:01BD 00000000:0000 0A 00000000:00000000\n'
    )
    check(not (tcp_established_local_ports(listen_only) & SMB_PORTS), 'LISTEN 445 is not a session')
    tcp6 = '  sl  local_address rem_address   st\n   0: 00000000000000000000000000000000:008B 00000000000000000000000000000000:C000 01 0\n'
    check(0x8B in tcp_established_local_ports(tcp6), 'IPv6 established 139 is detected')

    dev = (
        'Inter-|   Receive                                                |  Transmit\n'
        ' face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets\n'
        '    lo: 1000000 10 0 0 0 0 0 0 1000000 10 0 0 0 0 0 0\n'
        '  wlan0: 5000 10 0 0 0 0 0 0 7000 8 0 0 0 0 0 0\n'
    )
    check(net_dev_bytes(dev) == 12000, 'net bytes ignore lo, got %s' % net_dev_bytes(dev))

    disks = (
        '   1       0 ram0 0 0 0 0 0 0 0 0 0 0 0\n'
        '   7       0 loop0 1 0 100 0 1 0 100 0 0 0 0\n'
        ' 179       0 mmcblk0 10 0 200 0 20 0 400 0 0 0 0\n'
    )
    check(diskstats_sectors(disks) == 600, 'disk sectors skip ram/loop, got %s' % diskstats_sectors(disks))

def test_activity_busy():
    d = device.Mock()
    now = 1000.0
    d._test_net = 1000
    d._test_disk = 10
    check(d.activity_busy(now=now) is False, 'first net sample is not a transfer')
    d._test_net = 1000 + 32 * 1024
    check(d.activity_busy(now=now + 1.0) is True, '16+ KiB/s of network holds sleep')
    d._test_net = 1000 + 32 * 1024
    check(d.activity_busy(now=now + 1.0 + ACTIVITY_GRACE - 1) is True, 'grace keeps the hold after traffic pauses')
    check(d.activity_busy(now=now + 1.0 + ACTIVITY_GRACE + 1.1) is False, 'hold ends after grace with no traffic')

    d2 = device.Mock()
    d2._test_smb = True
    check(d2.activity_busy(now=2000.0) is True, 'an SMB session holds sleep with no button input')

    d3 = device.Mock()
    d3._test_disk = 10
    check(d3.activity_busy(now=3000.0) is False, 'first disk sample is not a transfer')
    d3._test_disk = 10 + 512
    check(d3.activity_busy(now=3001.0) is True, 'sizable disk I/O holds sleep')

def test_app(ren, W, H):
    check(SLEEP[-1] == ('Never', 0), 'Sleep after includes Never')
    check(SLEEP[2][1] == 300, 'default index 2 is 5 minutes')

    # Idle on home with a short timer should sleep
    app = fresh(ren, W, H)
    hits = hits_of(app)
    fire(app)
    check(len(hits) == 1, 'idle home should sleep, got %d' % len(hits))

    # Never disables idle suspend
    app = fresh(ren, W, H)
    hits = hits_of(app)
    app.sleep = len(SLEEP) - 1
    app.last_input = time.time() - 9999
    app.tick()
    check(len(hits) == 0, 'Never must not idle-sleep')
    check(SLEEP[app.sleep][1] == 0, 'Never is zero seconds')

    # First-boot setup (the reported Wi-Fi copy case)
    app = fresh(ren, W, H)
    hits = hits_of(app)
    app.setup_done = False
    app.ctx = 'setup'
    app.screen = 'copy'
    before = time.time()
    fire(app, ago=999)
    check(len(hits) == 0, 'setup copy screen must not sleep during a transfer with no buttons')
    check(app.last_input >= before, 'setup activity must reset the idle timer')

    # Any setup step, including the device picker
    app = fresh(ren, W, H)
    hits = hits_of(app)
    app.setup_done = False
    app.ctx = 'setup'
    app.screen = 'tz'
    fire(app)
    check(len(hits) == 0, 'setup time-zone screen must not sleep')

    # Background job
    app = fresh(ren, W, H)
    hits = hits_of(app)
    app.dev.busy['scan'] = True
    fire(app)
    check(len(hits) == 0, 'a busy background job must not sleep')

    # OTA
    app = fresh(ren, W, H)
    hits = hits_of(app)
    app.upd = 'checking'
    fire(app)
    check(len(hits) == 0, 'update check must not sleep')
    app.upd = 'reboot'
    app.last_input = time.time() - 999
    app.tick()
    check(len(hits) == 0, 'update install must not sleep')

    # Active SMB / Wi-Fi transfer after setup, still no buttons
    app = fresh(ren, W, H)
    hits = hits_of(app)
    app.dev._test_smb = True
    fire(app)
    check(len(hits) == 0, 'incoming SMB transfer must not sleep')
    check(app.sleep_held(), 'sleep_held sees the SMB session')

    # When the hold lifts, the timer starts fresh (does not sleep on the next tick)
    app.dev._test_smb = False
    app.dev._act_until = 0
    t0 = app.last_input
    app.tick()
    check(len(hits) == 0, 'must not sleep the instant work ends')
    check(abs(app.last_input - t0) < 2, 'timer is leftover from the hold, not expired')

    # After the hold, once the timer actually elapses, sleep is allowed again
    app.last_input = time.time() - 120
    app.tick()
    check(len(hits) == 1, 'idle sleep works again after a transfer ends, got %d' % len(hits))

    # Any input resets the timer
    app = fresh(ren, W, H)
    hits = hits_of(app)
    app.sleep = 0
    app.last_input = time.time() - 120
    app.key('down')
    app.tick()
    check(len(hits) == 0, 'a key press must reset the idle timer')
    check(time.time() - app.last_input < 2, 'last_input is fresh after a key')

def main():
    test_parsers()
    test_activity_busy()
    win, ren, W, H = M.setup_sdl(640, 480, False, software=True)
    test_app(ren, W, H)
    print('PASS: sleep holds during setup, jobs, updates, SMB/network transfers; Never disables idle sleep')
    print('ALL OK')

if __name__ == '__main__':
    main()
