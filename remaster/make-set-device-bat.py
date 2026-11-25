#!/usr/bin/env python3
# Writes SET-DEVICE.bat (CRLF) for the boot partition from the frontend's model list (one source of truth;
# 0.1.4+ also refreshes it on the card over the air).
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend'))
from sdui.device import set_device_bat
open(sys.argv[1], 'wb').write(set_device_bat().encode('ascii'))
print('wrote', sys.argv[1])
