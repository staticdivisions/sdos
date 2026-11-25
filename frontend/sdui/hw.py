# Which handheld family this card runs on, and its device models (one frontend for every sdOS image).
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
#
# H700 image: U-Boot loads /dtb.img, which sdOS copies from /flash/device_trees (Settings > Device model,
#   SET-DEVICE.bat). RK3566 image: U-Boot picks the device tree itself (extlinux FDTDIR), nothing to choose.
# RK3566 "B" image (X55, X35S, RG DS, RG DS Plus): U-Boot can't tell these apart, so extlinux loads /dtb.img
#   and the model is chosen the same way as on H700.
import os


def _osrel(key):
    try:
        for ln in open('/etc/os-release'):
            if ln.startswith(key + '='):
                return ln.split('=', 1)[1].strip().strip('"')
    except Exception:
        pass
    return ''


PLATFORM = (os.environ.get('SDUI_PLATFORM') or _osrel('HW_DEVICE') or 'H700').upper()

# (name, standard dtb, alternate-screen dtb or None). Retail names only, the safe default first.
_P = 'sun50i-h700-anbernic-'
H700_MODELS = [('RG35XX H', _P + 'rg35xx-h', _P + 'rg35xx-h-rev6-panel'),
               ('RG35XX Plus', _P + 'rg35xx-plus', _P + 'rg35xx-plus-rev6-panel'),
               ('RG35XX 2024', _P + 'rg35xx-2024', _P + 'rg35xx-2024-rev6-panel'),
               ('RG35XX Pro', _P + 'rg35xx-pro', None),
               ('RG35XX SP', _P + 'rg35xx-sp', _P + 'rg35xx-sp-v2-panel'),
               ('RG34XX', _P + 'rg34xx', None),
               ('RG34XX SP', _P + 'rg34xx-sp', _P + 'rg34xx-sp-v2-panel'),
               ('RG40XX H', _P + 'rg40xx-h', _P + 'rg40xx-h-v2-panel'),
               ('RG40XX V', _P + 'rg40xx-v', _P + 'rg40xx-v-v2-panel'),
               ('RG CubeXX', _P + 'rgcubexx', None),
               ('RG28XX', _P + 'rg28xx', None),
               ('RG SP', _P + 'rg-sp', None)]
# Chosen automatically by U-Boot (sdOS RK3566 image). Listed so Settings can show the name.
RK_AUTO_MODELS = [('RG353P', 'rk3566-anbernic-rg353p', None), ('RG353PS', 'rk3566-anbernic-rg353ps', None),
                  ('RG353V', 'rk3566-anbernic-rg353v', None), ('RG353VS', 'rk3566-anbernic-rg353vs', None),
                  ('RG503', 'rk3566-anbernic-rg503', None),
                  ('RG ARC-D', 'rk3566-anbernic-rg-arc-d', None), ('RG ARC-S', 'rk3566-anbernic-rg-arc-s', None),
                  ('RGB30', 'rk3566-powkiddy-rgb30', None), ('RGB20SX', 'rk3566-powkiddy-rgb20sx', None),
                  ('RGB20 Pro', 'rk3566-powkiddy-rgb20-pro', None), ('RGB10 Max 3', 'rk3566-powkiddy-rgb10max3', None),
                  ('RK2023', 'rk3566-powkiddy-rk2023', None)]
# Picked by the user (sdOS RK3566 B image): X55 is the image's default.
RK_PICK_MODELS = [('X55', 'rk3566-powkiddy-x55', None), ('X35S', 'rk3566-powkiddy-x35s', None),
                  ('RG DS', 'rk3568-anbernic-rg-ds', None), ('RG DS Plus', 'rk3568-anbernic-rg-ds-plus', None)]


def _auto_boot():
    """True when U-Boot chooses the device tree (no FDT line in extlinux.conf)."""
    if os.environ.get('SDUI_MODEL_AUTO') is not None:
        return os.environ['SDUI_MODEL_AUTO'] == '1'
    try:
        for ln in open('/flash/extlinux/extlinux.conf'):
            w = ln.split()
            if w and w[0].upper() == 'FDT':
                return False
            if w and w[0].upper() == 'FDTDIR':
                return True
    except Exception:
        pass
    return False


if PLATFORM == 'RK3566':
    MODEL_AUTO = _auto_boot()
    MODELS = RK_AUTO_MODELS if MODEL_AUTO else RK_PICK_MODELS
    FAMILY = 'Anbernic and Powkiddy handhelds'
else:
    MODEL_AUTO = False
    MODELS = H700_MODELS
    FAMILY = 'Anbernic XX handhelds'
ALL_NAMES = {std: nm for nm, std, _ in H700_MODELS + RK_AUTO_MODELS + RK_PICK_MODELS}

# Flash default for the H700 image (remaster.sh SDOS_DTB). Not a hardware probe.
DEFAULT_DTB = H700_MODELS[0][1]

# First-boot picker: supported XX models, in the order we show them. RG SP is
# omitted here (it stays in Settings). Joystick hints come from each model's
# shipped device-tree amux-count (4 = sticks, 0 = none). This is not a live
# board probe — it describes the model as listed.
SETUP_MODEL_NAMES = (
    'RG35XX H', 'RG35XX Plus', 'RG35XX 2024', 'RG35XX Pro', 'RG35XX SP',
    'RG34XX', 'RG34XX SP', 'RG40XX H', 'RG40XX V', 'RG CubeXX', 'RG28XX',
)
HAS_JOYSTICKS = {
    'RG35XX H': True, 'RG35XX Plus': False, 'RG35XX 2024': False,
    'RG35XX Pro': True, 'RG35XX SP': False, 'RG34XX': False,
    'RG34XX SP': True, 'RG40XX H': True, 'RG40XX V': True,
    'RG CubeXX': True, 'RG28XX': False, 'RG SP': False,
}
SETUP_STEPS = 6


def setup_model_rows():
    """(name, standard dtb, alt dtb, has_joysticks) for the first-boot list."""
    by = {nm: (nm, std, alt) for nm, std, alt in MODELS}
    rows = []
    for nm in SETUP_MODEL_NAMES:
        if nm not in by:
            continue
        name, std, alt = by[nm]
        rows.append((name, std, alt, bool(HAS_JOYSTICKS.get(nm))))
    return rows


def is_default_h_tree(dt=None):
    """True when the loaded tree is exactly the H700 flash default (RG35XX H, standard panel)."""
    if MODEL_AUTO:
        return False
    if dt is None:
        dt = running_dt()
    return dt == DEFAULT_DTB


def running_dt():
    """Device tree id of the running kernel: ROCKNIX's rocknix-dt-id (H700), else <soc>-<vendor>-<board>
    from the compatible list (e.g. 'anbernic,rg353p' + 'rockchip,rk3566' -> rk3566-anbernic-rg353p)."""
    try:
        return open('/proc/device-tree/rocknix-dt-id').read().strip('\x00 \n')
    except Exception:
        pass
    try:
        comp = [c for c in open('/proc/device-tree/compatible', 'rb').read().decode(errors='ignore').split('\x00') if c]
        board, soc = comp[0], comp[-1]
        return '%s-%s' % (soc.split(',', 1)[1], board.replace(',', '-', 1))
    except Exception:
        return ''


def board_name():
    """The model string the device tree gives, minus the brand (fallback for unlisted boards)."""
    try:
        m = open('/proc/device-tree/model').read().strip('\x00 \n')
    except Exception:
        return ''
    for b in ('Anbernic ', 'Powkiddy ', 'powkiddy '):
        if m.startswith(b):
            m = m[len(b):]
    return m
