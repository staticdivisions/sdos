# wifi.txt parse + scrub tests (no SDL). Fail on the first assertion.
# usage: python3 tools_wifi_txt_test.py
import os, sys, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdui.wifi_txt import parse_wifi_txt, wifi_txt_template_bytes, write_wifi_txt_template, WIFI_TXT_PATH
from sdui import device

def check(cond, msg):
    if not cond:
        raise SystemExit('FAIL: ' + msg)

def parse_cases():
    blank = wifi_txt_template_bytes()
    check(blank.endswith(b'network=\r\npassword=\r\n'), 'template ends with blank network=/password= CRLF')
    check(b'\n' in blank and b'\r\n' in blank, 'template uses CRLF')
    check(not blank.startswith(b'\xef\xbb\xbf'), 'template has no UTF-8 BOM')
    check(parse_wifi_txt(blank) == (None, None), 'blank template is a no-op')
    check(parse_wifi_txt(b'') == (None, None), 'empty is a no-op')
    check(parse_wifi_txt(b'password=secret\r\n') == (None, None), 'password without network is a no-op')
    check(parse_wifi_txt(b'network=\r\npassword=secret\r\n') == (None, None), 'blank network is a no-op')

    crlf = b'network=HomeWiFi\r\npassword=mysecretpassword\r\n'
    check(parse_wifi_txt(crlf) == ('HomeWiFi', 'mysecretpassword'), 'CRLF network/password')

    bom = b'\xef\xbb\xbf' + crlf
    check(parse_wifi_txt(bom) == ('HomeWiFi', 'mysecretpassword'), 'UTF-8 BOM + CRLF')

    spaces = b'network=Cafe WiFi\r\npassword=pass word\r\n'
    check(parse_wifi_txt(spaces) == ('Cafe WiFi', 'pass word'), 'spaces in SSID and password')

    quoted = b'network="Cafe WiFi"\r\npassword=\'p@ss,word!\'\r\n'
    check(parse_wifi_txt(quoted) == ('Cafe WiFi', 'p@ss,word!'), 'matching quotes')

    special = b"network=Net-1_OK\r\npassword=Sun$et-4!;#notcomment\r\n"
    check(parse_wifi_txt(special) == ('Net-1_OK', 'Sun$et-4!;#notcomment'), 'special characters in password')

    open_net = b'network=Guest\r\npassword=\r\n'
    check(parse_wifi_txt(open_net) == ('Guest', ''), 'open network, empty password')

    aliases = b'ssid=AliasNet\r\npass=aliaspw\r\n'
    check(parse_wifi_txt(aliases) == ('AliasNet', 'aliaspw'), 'ssid= and pass= aliases')

    psk = b'ssid=PskNet\r\npsk=pskvalue\r\n'
    check(parse_wifi_txt(psk) == ('PskNet', 'pskvalue'), 'psk= alias')

    prefer = b'ssid=OldName\r\nnetwork=RealName\r\npass=x\r\npassword=y\r\n'
    check(parse_wifi_txt(prefer) == ('RealName', 'y'), 'network=/password= win over aliases')

    padded = b'  network =  Spaced  \r\n  password =  "  inner  "  \r\n'
    # key is stripped+lowered; value is stripped, then quotes removed, inner spaces kept
    check(parse_wifi_txt(padded) == ('Spaced', '  inner  '), 'whitespace and quoted inner spaces')

    # commented example in the shipped template must not be read as credentials
    check(b'#   network=HomeWiFi' in blank or b'#   network=HomeWiFi' in blank.replace(b'\r\n', b'\n'), 'template includes commented example')
    check(parse_wifi_txt(blank) == (None, None), 'commented example is ignored')

    lf_only = b'network=UnixNet\npassword=unixpw\n'
    check(parse_wifi_txt(lf_only) == ('UnixNet', 'unixpw'), 'LF-only (mac/unix editors)')

    print('ok parse')

def scrub_and_import():
    td = tempfile.mkdtemp(prefix='wifi_txt_')
    try:
        path = os.path.join(td, 'wifi.txt')
        # filled file, Windows-style
        open(path, 'wb').write(b'\xef\xbb\xbfnetwork=Home WiFi\r\npassword=s3cret!@#\r\n')
        dev = device.Mock()
        check(dev.wifi_status is None, 'mock starts disconnected')
        ok = dev.import_wifi_txt(path)
        check(ok is True, 'import returns True when network is set')
        check(dev.wifi_status == 'Home WiFi', 'import connects via wifi_connect')
        got = open(path, 'rb').read()
        want = wifi_txt_template_bytes()
        check(got == want, 'password is scrubbed back to the blank CRLF template\n got=%r\nwant=%r' % (got, want))
        check(b's3cret' not in got, 'plaintext password is gone')
        check(parse_wifi_txt(got) == (None, None), 'scrubbed file is a no-op')

        # blank file: no-op, contents left alone (already template or empty network)
        open(path, 'wb').write(want)
        dev2 = device.Mock()
        ok = dev2.import_wifi_txt(path)
        check(ok is False, 'blank template import is a no-op')
        check(dev2.wifi_status is None, 'blank import does not connect')
        check(open(path, 'rb').read() == want, 'blank no-op does not rewrite the file needlessly')

        # missing file
        os.remove(path)
        check(device.Mock().import_wifi_txt(path) is False, 'missing file is a no-op')

        # write_wifi_txt_template helper
        write_wifi_txt_template(path)
        check(open(path, 'rb').read() == want, 'write_wifi_txt_template matches canonical bytes')

        # Device.WIFI path constant
        check(WIFI_TXT_PATH == '/flash/wifi.txt', 'boot path is /flash/wifi.txt')
        print('ok scrub+import')
    finally:
        shutil.rmtree(td, ignore_errors=True)

if __name__ == '__main__':
    parse_cases()
    scrub_and_import()
    print('ok all wifi.txt tests')
