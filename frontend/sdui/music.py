# Built-in music player (replaces ROCKNIX's gmu, which grabbed the pad and could lock the device).
# SDL2_mixer through ctypes; runs inside the UI, so B always returns to the menu.
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
import os, ctypes as C
from . import sdl

MUSIC_DIR = '/storage/roms/music'
EXTS = {'.mp3', '.ogg', '.oga', '.flac', '.wav', '.opus', '.mod', '.xm', '.s3m', '.it'}
_mix = None


def _lib():
    global _mix
    if _mix is None:
        try:
            m = sdl._load(['libSDL2_mixer-2.0.so.0', 'libSDL2_mixer.so'])
        except OSError:
            _mix = False; return _mix
        def f(n, r, *a):
            fn = getattr(m, n); fn.restype = r; fn.argtypes = list(a); return fn
        vp, i = C.c_void_p, C.c_int
        m.Open = f('Mix_OpenAudio', i, i, C.c_uint16, i, i)
        m.Close = f('Mix_CloseAudio', None)
        m.Init = f('Mix_Init', i, i)
        m.Load = f('Mix_LoadMUS', vp, C.c_char_p)
        m.Free = f('Mix_FreeMusic', None, vp)
        m.Play = f('Mix_PlayMusic', i, vp, i)
        m.Halt = f('Mix_HaltMusic', i)
        m.Pause = f('Mix_PauseMusic', None)
        m.Resume = f('Mix_ResumeMusic', None)
        m.Paused = f('Mix_PausedMusic', i)
        m.Playing = f('Mix_PlayingMusic', i)
        _mix = m
    return _mix


def available():
    return bool(_lib())


class Player:
    def __init__(self, folder=MUSIC_DIR):
        self.folder = folder; self.tracks = []; self.cur = -1; self.mus = None
        self.opened = False; self.paused = False; self.err = ''

    def scan(self):
        out = []
        try: os.makedirs(self.folder, exist_ok=True)
        except Exception: pass
        for dp, dns, fns in os.walk(self.folder):
            dns[:] = sorted(d for d in dns if not d.startswith('.'))
            for fn in sorted(fns, key=str.lower):
                if not fn.startswith('.') and os.path.splitext(fn)[1].lower() in EXTS:
                    out.append(os.path.join(dp, fn))
            if len(out) > 2000: break
        self.tracks = out
        return out

    def _open(self):
        if self.opened: return True
        m = _lib()
        if not m: self.err = 'Music support is missing'; return False
        sdl.sdl.SDL_InitSubSystem.argtypes = [C.c_uint32]; sdl.sdl.SDL_InitSubSystem(0x10)
        m.Init(0x08 | 0x10 | 0x01 | 0x40 | 0x02)   # mp3, ogg, flac, opus, mod (whatever is built in)
        if m.Open(44100, 0x8010, 2, 2048) != 0:
            self.err = 'No audio output'; return False
        self.opened = True; return True

    def play(self, idx):
        if not self.tracks or not self._open(): return False
        m = _lib(); self.stop()
        idx %= len(self.tracks)
        for _ in range(len(self.tracks)):
            mus = m.Load(self.tracks[idx].encode())
            if mus and m.Play(mus, 1) == 0:
                self.mus, self.cur, self.paused, self.err = mus, idx, False, ''; return True
            if mus: m.Free(mus)
            self.err = "Can't play " + os.path.basename(self.tracks[idx])
            idx = (idx + 1) % len(self.tracks)
        return False

    def toggle(self):
        m = _lib()
        if not self.mus or not m: return
        if self.paused: m.Resume(); self.paused = False
        else: m.Pause(); self.paused = True

    def step(self, d):
        if self.tracks: self.play((self.cur if self.cur >= 0 else 0) + d)

    def finished(self):
        m = _lib()
        return bool(self.mus and m and not self.paused and not m.Playing())

    def stop(self):
        m = _lib()
        if self.mus and m:
            m.Halt(); m.Free(self.mus)
        self.mus = None; self.paused = False

    def close(self):
        self.stop(); self.cur = -1
        if self.opened and _lib():
            _lib().Close(); self.opened = False

    def title(self, i=None):
        i = self.cur if i is None else i
        if 0 <= i < len(self.tracks):
            return os.path.splitext(os.path.basename(self.tracks[i]))[0]
        return ''
