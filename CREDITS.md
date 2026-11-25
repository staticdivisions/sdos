# Credits

sdOS is built on the work of these open-source projects. Each keeps its own license, and its source is at the link. This list matches the About screen in sdOS (Settings > About).

## Base system

| Project | License | Source |
| --- | --- | --- |
| ROCKNIX (base system, build 20261101, commit `cefc14339a4ae18c02bb69888f27835e50664b60`) | GPL-2.0 (ROCKNIX scripts are GPL-2.0-or-later; bundled works keep their own licenses) | https://github.com/ROCKNIX/distribution |
| JELOS and LibreELEC (ROCKNIX's roots) | GPL-2.0 | https://github.com/LibreELEC/LibreELEC.tv |
| Linux kernel | GPL-2.0 | https://kernel.org |
| U-Boot | GPL-2.0 | https://source.denx.de/u-boot/u-boot |
| systemd | LGPL-2.1-or-later | https://github.com/systemd/systemd |
| BusyBox | GPL-2.0 | https://busybox.net |
| NetworkManager | GPL-2.0-or-later | https://networkmanager.dev |
| Samba (network share) | GPL-3.0 | https://www.samba.org |
| Sway and wlroots | MIT | https://github.com/swaywm |
| Mesa (Panfrost graphics) | MIT | https://gitlab.freedesktop.org/mesa/mesa |
| Python | PSF License | https://www.python.org |
| SDL2, SDL2_ttf, SDL2_image, SDL2_mixer | zlib | https://libsdl.org |
| FreeType | FreeType License | https://freetype.org |

## Emulators and apps

| Project | License | Source |
| --- | --- | --- |
| RetroArch | GPL-3.0 | https://github.com/libretro/RetroArch |
| libretro cores (mGBA, gpSP, Gambatte, Snes9x, Genesis Plus GX, PCSX ReARMed, FCEUmm and others) | Each core's own license | https://github.com/libretro |
| PPSSPP | GPL-2.0-or-later | https://github.com/hrydgard/ppsspp |
| Flycast | GPL-2.0 | https://github.com/flyinghead/flycast |
| Mupen64Plus | GPL-2.0 | https://github.com/mupen64plus |
| DuckStation | Its own license | https://github.com/stenzek/duckstation |
| Yaba Sanshiro | GPL-2.0 | https://github.com/devmiyax/yabause |
| Mednafen | GPL-2.0 | https://mednafen.github.io |
| ScummVM | GPL-3.0-or-later | https://github.com/scummvm/scummvm |
| GZDoom | GPL-3.0 | https://github.com/ZDoom/gzdoom |
| Amiberry | GPL-3.0 | https://github.com/BlitterStudio/amiberry |
| Hatari | GPL-2.0 | https://github.com/hatari/hatari |
| PortMaster | MIT | https://github.com/PortsMaster/PortMaster-GUI |
| DraStic (Nintendo DS) | Closed-source freeware, not open source | https://drastic-ds.com |

## Files in this repository from other projects

| File | Origin | License |
| --- | --- | --- |
| `remaster/overlay/usr/bin/sd-ui.sh` | Derived from ROCKNIX `start_es.sh`, Copyright (C) 2024 ROCKNIX | GPL-2.0-or-later |
| `remaster/overlay/usr/lib/rocknix/fs-resize` | Based on ROCKNIX `fs-resize`, Copyright (C) 2009-2014 Stephan Raue | GPL-2.0-or-later |
| `remaster/overlay/usr/config/smb.conf` | Based on the LibreELEC / ROCKNIX Samba config, Copyright (C) 2009-2016 Stephan Raue and Team LibreELEC | GPL-2.0-or-later |
| `frontend/sdui/fonts/Manrope-*.ttf` | Manrope typeface, Copyright 2018 The Manrope Project Authors | SIL OFL 1.1 (`frontend/sdui/fonts/OFL.txt`) |

Thank you to every team listed here.
