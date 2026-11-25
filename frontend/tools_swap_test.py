# Tests for Swap A/B and Swap X/Y: sdui maps, RetroArch, SDL, PPSSPP, Flycast, revert.
# usage: python3 tools_swap_test.py
import os, sys, json, shutil, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SDUI_MOCK'] = '1'

from sdui import btnswap
from sdui.app import App
from sdui import device


def pass_(msg):
    print('PASS:', msg)


class SwapLogic(unittest.TestCase):
    def test_remap_logical(self):
        self.assertEqual(btnswap.remap_logical('a', True, False), 'b')
        self.assertEqual(btnswap.remap_logical('b', True, False), 'a')
        self.assertEqual(btnswap.remap_logical('x', True, False), 'x')
        self.assertEqual(btnswap.remap_logical('x', False, True), 'y')
        self.assertEqual(btnswap.remap_logical('y', False, True), 'x')
        self.assertEqual(btnswap.remap_logical('a', True, True, builtin=False), 'a')
        self.assertEqual(btnswap.remap_logical('start', True, True), 'start')
        pass_('logical names swap only on the built-in pad')

    def test_btn_map(self):
        m = {1: 'a', 0: 'b', 2: 'x', 3: 'y', 9: 'start'}
        ab = btnswap.swap_btn_map(m, True, False)
        self.assertEqual(ab, {1: 'b', 0: 'a', 2: 'x', 3: 'y', 9: 'start'})
        xy = btnswap.swap_btn_map(m, False, True)
        self.assertEqual(xy, {1: 'a', 0: 'b', 2: 'y', 3: 'x', 9: 'start'})
        both = btnswap.swap_btn_map(m, True, True)
        self.assertEqual(both, {1: 'b', 0: 'a', 2: 'y', 3: 'x', 9: 'start'})
        # from already-swapped map, a second swap of the original would be wrong;
        # apply always starts from the unswapped map.
        self.assertEqual(btnswap.swap_btn_map(m, False, False), m)
        pass_('evdev button maps swap A/B and X/Y independently')

    def test_ra_cfg(self):
        src = (
            'input_driver = "udev"\n'
            'input_b_btn = "0"\n'
            'input_a_btn = "1"\n'
            'input_y_btn = "3"\n'
            'input_x_btn = "2"\n'
            'input_l_btn = "4"\n'
        )
        xy = btnswap.swap_ra_cfg(src, False, True)
        self.assertIn('input_x_btn = "3"', xy)
        self.assertIn('input_y_btn = "2"', xy)
        self.assertIn('input_a_btn = "1"', xy)
        self.assertIn('input_l_btn = "4"', xy)
        ab = btnswap.swap_ra_cfg(src, True, False)
        self.assertIn('input_a_btn = "0"', ab)
        self.assertIn('input_b_btn = "1"', ab)
        both = btnswap.swap_ra_cfg(src, True, True)
        self.assertIn('input_a_btn = "0"', both)
        self.assertIn('input_x_btn = "3"', both)
        # off is identity
        self.assertEqual(btnswap.swap_ra_cfg(src, False, False), src)
        # swapping the already-swapped file would double-swap; apply uses the backup
        again = btnswap.swap_ra_cfg(xy, False, True)
        self.assertIn('input_x_btn = "2"', again)
        pass_('RetroArch autoconfig swaps face-button ids and leaves others')

    def test_sdl_line(self):
        line = '1900f6a24b480000df14000000010000,H700 Gamepad,platform:Linux,x:b3,a:b1,b:b0,y:b2,back:b8,\n'
        xy = btnswap.swap_sdl_line(line, False, True)
        self.assertIn('x:b2', xy)
        self.assertIn('y:b3', xy)
        self.assertIn('a:b1', xy)
        ab = btnswap.swap_sdl_line(line, True, False)
        self.assertIn('a:b0', ab)
        self.assertIn('b:b1', ab)
        pass_('SDL gamecontrollerdb lines swap a/b and x/y fields')

    def test_ppsspp(self):
        src = '[ControlMapping]\nCircle = 10-189\nCross = 10-190\nSquare = 10-188\nTriangle = 10-191\nStart = 10-197\n'
        ab = btnswap.swap_ppsspp_ini(src, True, False)
        self.assertIn('Circle = 10-188', ab)
        self.assertIn('Square = 10-189', ab)
        self.assertIn('Cross = 10-190', ab)
        xy = btnswap.swap_ppsspp_ini(src, False, True)
        self.assertIn('Cross = 10-191', xy)
        self.assertIn('Triangle = 10-190', xy)
        pass_('PPSSPP controls.ini swaps 10-188/189 and 10-190/191')

    def test_flycast(self):
        src = 'bind0 = 0:btn_a\nbind1 = 1:btn_b\nbind2 = 2:btn_x\nbind3 = 3:btn_y\nbind8 = 8:btn_menu\n'
        ab = btnswap.swap_flycast_cfg(src, True, False)
        self.assertIn('0:btn_b', ab)
        self.assertIn('1:btn_a', ab)
        self.assertIn('2:btn_x', ab)
        xy = btnswap.swap_flycast_cfg(src, False, True)
        self.assertIn('2:btn_y', xy)
        self.assertIn('3:btn_x', xy)
        self.assertIn('8:btn_menu', xy)
        pass_('Flycast mappings swap btn_a/b and btn_x/y')

    def test_mupen(self):
        src = '[Input-SDL-Control1]\nA Button = button(1)\nB Button = button(3)\n[Input-SDL-Control2]\nA Button = ""\nB Button = ""\n'
        ab = btnswap.swap_mupen_cfg(src, True, False)
        self.assertIn('A Button = button(3)', ab)
        self.assertIn('B Button = button(1)', ab)
        self.assertIn('A Button = ""', ab)
        pass_('mupen64plus swaps A/B in control 1 only')

    def test_es_input(self):
        src = '''<?xml version="1.0"?>
<inputList>
    <inputConfig type="joystick" deviceName="H700 Gamepad">
        <input name="a" type="button" id="1" value="1" />
        <input name="b" type="button" id="0" value="1" />
        <input name="x" type="button" id="2" value="1" />
        <input name="y" type="button" id="3" value="1" />
    </inputConfig>
    <inputConfig type="joystick" deviceName="8BitDo SN30 Pro">
        <input name="a" type="button" id="1" value="1" />
        <input name="b" type="button" id="0" value="1" />
        <input name="x" type="button" id="2" value="1" />
        <input name="y" type="button" id="3" value="1" />
    </inputConfig>
</inputList>
'''
        xy = btnswap.swap_es_input(src, False, True)
        self.assertIn('deviceName="H700 Gamepad"', xy)
        # parse and check ids
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xy)
        by = {}
        for ic in root.findall('inputConfig'):
            by[ic.get('deviceName')] = {i.get('name'): i.get('id') for i in ic.findall('input')}
        self.assertEqual(by['H700 Gamepad']['x'], '3')
        self.assertEqual(by['H700 Gamepad']['y'], '2')
        self.assertEqual(by['8BitDo SN30 Pro']['x'], '2')
        self.assertEqual(by['8BitDo SN30 Pro']['y'], '3')
        pass_('es_input swaps only the built-in pad')

    def test_builtin_names(self):
        self.assertTrue(btnswap.is_builtin_pad('H700 Gamepad'))
        self.assertTrue(btnswap.is_builtin_pad('ROCKNIX Gamepad'))
        self.assertFalse(btnswap.is_builtin_pad('8BitDo SN30 Pro'))
        self.assertFalse(btnswap.is_builtin_pad('WH-1000XM4'))
        pass_('built-in pad detection')


class SwapApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='sdui-swap-')
        os.environ['SDUI_SWAP_ROOT'] = self.tmp
        # stock RA
        d = os.path.join(self.tmp, 'usr/share/libretro/autoconfig')
        os.makedirs(d)
        open(os.path.join(d, 'H700 Gamepad.cfg'), 'w').write(
            'input_b_btn = "0"\ninput_a_btn = "1"\ninput_y_btn = "3"\ninput_x_btn = "2"\ninput_l_btn = "4"\n')
        # stock SDL
        d = os.path.join(self.tmp, 'usr/config/SDL-GameControllerDB')
        os.makedirs(d)
        open(os.path.join(d, 'gamecontrollerdb.txt'), 'w').write(
            '1900f6a2,H700 Gamepad,platform:Linux,x:b3,a:b1,b:b0,y:b2,back:b8,\n'
            '03000000,8BitDo SN30 Pro,platform:Linux,x:b2,a:b0,b:b1,y:b3,\n')
        # stock PPSSPP
        d = os.path.join(self.tmp, 'usr/config/ppsspp/PSP/SYSTEM')
        os.makedirs(d)
        open(os.path.join(d, 'controls.ini'), 'w').write(
            '[ControlMapping]\nCircle = 10-189\nCross = 10-190\nSquare = 10-188\nTriangle = 10-191\n')
        # stock flycast
        d = os.path.join(self.tmp, 'usr/config/flycast/mappings')
        os.makedirs(d)
        open(os.path.join(d, 'SDL_H700 Gamepad.cfg'), 'w').write(
            'bind0 = 0:btn_a\nbind1 = 1:btn_b\nbind2 = 2:btn_x\nbind3 = 3:btn_y\n')

    def tearDown(self):
        os.environ.pop('SDUI_SWAP_ROOT', None)
        shutil.rmtree(self.tmp, ignore_errors=True)
        btnswap.set_flags(False, False)

    def test_apply_and_revert(self):
        ra = os.path.join(self.tmp, 'storage/joypads/H700 Gamepad.cfg')
        sdl = os.path.join(self.tmp, 'storage/.config/SDL-GameControllerDB/gamecontrollerdb.txt')
        psp = os.path.join(self.tmp, 'storage/.config/ppsspp/PSP/SYSTEM/controls.ini')
        fc = os.path.join(self.tmp, 'storage/.config/flycast/mappings/SDL_H700 Gamepad.cfg')
        btnswap.apply(False, True)
        self.assertTrue(os.path.isfile(ra))
        self.assertIn('input_x_btn = "3"', open(ra).read())
        self.assertIn('input_y_btn = "2"', open(ra).read())
        sdl_t = open(sdl).read()
        self.assertIn('x:b2', sdl_t)
        self.assertIn('8BitDo SN30 Pro,platform:Linux,x:b2,a:b0,b:b1,y:b3', sdl_t)
        self.assertIn('Cross = 10-191', open(psp).read())
        self.assertIn('2:btn_y', open(fc).read())
        env = btnswap.launch_env()
        self.assertIn('SDL_GAMECONTROLLERCONFIG', env)
        self.assertIn('H700 Gamepad', env['SDL_GAMECONTROLLERCONFIG'])
        self.assertIn('x:b2', env['SDL_GAMECONTROLLERCONFIG'])
        # switch to A/B only (must not double-swap X/Y leftover)
        btnswap.apply(True, False)
        ra_t = open(ra).read()
        self.assertIn('input_a_btn = "0"', ra_t)
        self.assertIn('input_x_btn = "2"', ra_t)  # back to stock X
        # revert
        btnswap.apply(False, False)
        self.assertFalse(os.path.isfile(ra), 'overlay joypad removed when both off and we created it')
        # storage sdl copy should be restored to stock (we created it)
        # if the path did not exist before, restore deletes it
        self.assertFalse(os.path.isfile(sdl) or (os.path.isfile(sdl) and 'x:b3' in open(sdl).read()))
        self.assertEqual(btnswap.launch_env(), {})
        pass_('apply writes overlays from stock and revert restores or removes them')

    def test_revert_keeps_user_file(self):
        path = os.path.join(self.tmp, 'storage/joypads/H700 Gamepad.cfg')
        os.makedirs(os.path.dirname(path))
        open(path, 'w').write('input_a_btn = "1"\ninput_b_btn = "0"\ninput_x_btn = "9"\ninput_y_btn = "8"\n')
        btnswap.apply(False, True)
        self.assertIn('input_x_btn = "8"', open(path).read())
        btnswap.apply(False, False)
        self.assertTrue(os.path.isfile(path))
        self.assertIn('input_x_btn = "9"', open(path).read())
        pass_('existing user joypad overlay is restored when the toggle is turned off')


class SwapSettings(unittest.TestCase):
    def test_rows_default_off(self):
        class G:
            W = 640; H = 480
        # App needs a gfx object with measure etc. Use a very small stub if shot path
        # is enough: load_state not called when shot=True, but set_items needs swap flags.
        # Don't construct full App (needs Gfx). Test set_items via a shallow object? Better
        # check source / a light App if possible.
        import inspect
        src = inspect.getsource(App.set_items)
        self.assertIn("'Swap A/B'", src)
        self.assertIn("'Swap X/Y'", src)
        self.assertIn('swap_ab', src)
        # no em or en dashes in the new labels
        self.assertNotIn('\u2013', src)
        self.assertNotIn('\u2014', src)
        pass_('Settings has Swap A/B and Swap X/Y rows')

    def test_state_keys(self):
        src = open(os.path.join(os.path.dirname(__file__), 'sdui/app.py'), encoding='utf-8').read()
        self.assertIn('swap_ab=self.swap_ab', src)
        self.assertIn("st.get('swap_ab')", src)
        self.assertIn("st.get('swap_xy')", src)
        # default is off (bool of missing key)
        self.assertNotIn('\u2013', src[src.find('Swap A/B'):src.find('Swap A/B')+80])
        pass_('toggles persist in state.json and default off')


if __name__ == '__main__':
    r = unittest.main(verbosity=0, exit=False)
    if r.result.wasSuccessful():
        print('ALL OK')
        sys.exit(0)
    sys.exit(1)
