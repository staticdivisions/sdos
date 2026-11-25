# Releases

Current version: **0.1.13** (`frontend/sdui/VERSION`).

Each release gets a git tag `v<version>` that matches this list and the changelog at https://staticdivisions.com/sdos/. "Image" means a new card image on the download page. "OTA" means an over-the-air app-layer update from Settings > Update (needs base 0.1.2 or later).

Only 0.1.13 is in this first public commit. Earlier versions are listed for reference and are not tagged.

| Version | Date | Type | Notes |
| --- | --- | --- | --- |
| 0.1.13 | 2026-11-24 | OTA | New Swap A/B and Swap X/Y options in Settings, for handhelds with buttons labeled differently. |
| 0.1.12 | 2026-11-24 | OTA | Bluetooth turned on, with a Settings > Bluetooth screen for pairing controllers and headphones. |
| 0.1.11 | 2026-11-24 | OTA | Sleep no longer turns on during setup, library scans, Wi-Fi transfers or updates. Sleep timer can be set to Never. |
| 0.1.10 | 2026-11-23 | OTA | Four-button cue on setup Continue rows, Start also confirms. Optional wifi.txt on the SDOS drive for automatic Wi-Fi setup. |
| 0.1.9 | 2026-11-23 | Image + OTA | Starting a game while the last one closes now waits and launches. Image: PlayStation hang, H700 Triangle/Square, and L3/R3 fixes. |
| 0.1.8 | 2026-11-23 | Image + OTA | Much faster game quit. Larger boot screen. |
| 0.1.7 | 2026-11-17 | Image + OTA | Setup starts by asking which handheld you have. Stick input no longer blocks Down in Game Boy games. |
| 0.1.6 | 2026-11-17 | OTA | Fixes and polish. |
| 0.1.5 | | | Not released. |
| 0.1.4 | 2026-11-16 | OTA | Saves on the GAMES drive, emulator settings in the in-game menu, accent color picker, bigger copy screen, plain device model names. |
| 0.1.3 | 2026-11-15 | Image | Splash at power-on, SDOS boot label, GAMES partition on 32 GB+ cards, network share, File Explorer, PortMaster, Music Player, thirteen themes. |
| 0.1.2 | 2026-11-15 | Image | Fixed a post-boot black screen. Diagnostic logs on the boot partition. |
| 0.1.1 | 2026-11-15 | Image | Fixed a missing screen-and-buttons file. Cannot take later updates; reflash. |
| 0.1.0 | 2026-11-15 | Image | First release: setup, Home, in-game menu, Settings, seven themes, OTA updates. |

To tag the first public commit once it is published:

```sh
git tag -a v0.1.13 -m "sdOS 0.1.13"
```
