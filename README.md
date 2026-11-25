# sdOS

sdOS is a free, simple operating system for Anbernic XX handhelds, made by Static Divisions. It replaces the stock menu with a clean, text-only frontend: a setup wizard, Home, an in-game menu, Settings, themes, a games network share, and over-the-air updates for the app layer.

sdOS is built on [ROCKNIX](https://github.com/ROCKNIX/distribution) and the open-source emulators it ships. This repository holds everything Static Divisions changed or added: the frontend, the boot splash, the card-removal watcher, the overlay files, and the scripts that turn an official ROCKNIX image into an sdOS image.

Current version: **0.1.13**. See [RELEASES.md](RELEASES.md) and [CHANGES.txt](CHANGES.txt).

## Supported devices

RG35XX H, RG35XX Plus, RG35XX 2024, RG35XX Pro, RG35XX SP, RG34XX, RG34XX SP, RG40XX H, RG40XX V, RG CubeXX, RG28XX.

## Downloads

Official sdOS images are only published at **https://staticdivisions.com/sdos/**. Images from anywhere else are not ours.

No games, BIOS files or encryption keys are included in sdOS or in this repository.

## Repository layout

| Path | What it is |
| --- | --- |
| `frontend/sdui/` | The sdOS frontend (Python + SDL2). This is also the over-the-air app layer. |
| `frontend/tools_*.py`, `tools_ota_test.sh` | Tests, screenshot tools, the splash renderer and the OTA bundle packer. |
| `remaster/` | Scripts that turn an official ROCKNIX image into sdOS, plus the overlay files they install. |
| `splash/` | The boot splash program (`sdos-splash.c`) and its generated image header. |
| `cardwatch/` | `sdos-cardwatch`, which powers the handheld off cleanly if the SD card is pulled. |
| `build/SOURCE_OFFER.txt` | The written source offer copied onto every image. |
| `ota-feed/` | Example update feed files, showing the format devices read. |

## Building an image

You need a Linux machine (Debian or Ubuntu works) and an official ROCKNIX H700 image, build 20261101 (commit `cefc14339a4ae18c02bb69888f27835e50664b60`), from the ROCKNIX releases page.

Install the tools:

```sh
sudo apt install squashfs-tools zstd mtools pigz fdisk dos2unix python3 python3-pil libsdl2-2.0-0 libsdl2-ttf-2.0-0 gcc-aarch64-linux-gnu
```

Build:

```sh
sudo ./remaster/remaster.sh <official ROCKNIX H700 image>.img.gz sdOS-0.1.13.img.gz
```

The script renders and cross-compiles the boot splash, cross-compiles `sdos-cardwatch`, unpacks the ROCKNIX image, applies every change in `remaster/patch-system.sh` and `remaster/patch-initramfs.py`, and writes `sdOS-0.1.13.img.gz` plus a `.sha256` file. The image boots the RG35XX H by default; set `SDOS_DTB` to another device tree name from the image's `device_trees/` folder to change that, or use `SET-DEVICE.bat` on the boot partition after flashing.

`remaster/remaster-rk3566.sh` does the same for the ROCKNIX RK3566 images. RK3566 support is not part of the supported device list above yet.

### Running the frontend on a desktop

```sh
cd frontend
SDUI_MOCK=1 python3 -m sdui
```

`SDUI_MOCK=1` uses demo data instead of real hardware. Tests: `python3 tools_wifi_txt_test.py`, `tools_swap_test.py`, `tools_setup_input_test.py`, `tools_sleep_test.py`, `tools_bt_test.py` (run with `SDL_VIDEODRIVER=offscreen` on a machine without a display).

### Updates

Devices check the feed in `frontend/sdui/ota.py`. If you build your own version, set `SDUI_OTA_URL` or change the feed URL so your devices never pull official sdOS updates. `frontend/tools_ota_pack.py` builds an update bundle and its `latest.json`.

## Reporting bugs

Join the Static Divisions Discord at https://discord.gg/7ewFaH8tXA and post in #sdos-help, or use the support page at https://staticdivisions.com/sdos/support/. Please include your handheld model, your sdOS version (Settings > About) and what you were doing when it went wrong. The diagnostic logs sdOS writes to the `sdos-logs` folder on the SDOS drive help a lot.

## License

sdOS code is free software under the GNU General Public License, version 2 or (at your option) any later version. See [LICENSE](LICENSE). ROCKNIX and every bundled emulator keep their own licenses; see [CREDITS.md](CREDITS.md). The Manrope font is under the SIL Open Font License 1.1 (`frontend/sdui/fonts/OFL.txt`).

The Static Divisions and sdOS names, logo and themes are not covered by the GPL. See [TRADEMARKS.md](TRADEMARKS.md). If you share a modified version, give it a different name.
