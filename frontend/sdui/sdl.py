# Minimal ctypes bindings for SDL2, SDL2_ttf and SDL2_image (only what the UI uses).
# Copyright (C) 2026 Static Divisions. GPL-2.0-or-later.
import ctypes as C
import ctypes.util

def _load(names):
    for n in names:
        try:
            return C.CDLL(n)
        except OSError:
            continue
    p = ctypes.util.find_library(names[0].split('.so')[0].replace('lib', '', 1))
    if p:
        return C.CDLL(p)
    raise OSError('cannot load ' + names[0])

sdl = _load(['libSDL2-2.0.so.0', 'libSDL2.so'])
ttf = _load(['libSDL2_ttf-2.0.so.0', 'libSDL2_ttf.so'])
img = _load(['libSDL2_image-2.0.so.0', 'libSDL2_image.so'])

INIT_VIDEO = 0x20; INIT_JOYSTICK = 0x200; INIT_EVENTS = 0x4000; INIT_TIMER = 0x1
WINDOW_FULLSCREEN = 0x1; WINDOW_FULLSCREEN_DESKTOP = 0x1001; WINDOW_SHOWN = 0x4; WINDOW_HIDDEN = 0x8
RENDERER_ACCELERATED = 0x2; RENDERER_PRESENTVSYNC = 0x4; RENDERER_SOFTWARE = 0x1; RENDERER_TARGETTEXTURE = 0x8
BLENDMODE_BLEND = 1
PIXELFORMAT_ABGR8888 = 0x16762004
PIXELFORMAT_RGBA32 = PIXELFORMAT_ABGR8888  # little endian
QUIT = 0x100; WINDOWEVENT = 0x200; KEYDOWN = 0x300; KEYUP = 0x301
JOYAXISMOTION = 0x600; JOYHATMOTION = 0x602; JOYBUTTONDOWN = 0x603; JOYBUTTONUP = 0x604
JOYDEVICEADDED = 0x605; JOYDEVICEREMOVED = 0x606
MOUSEBUTTONDOWN = 0x401

class Rect(C.Structure):
    _fields_ = [('x', C.c_int), ('y', C.c_int), ('w', C.c_int), ('h', C.c_int)]

class FRect(C.Structure):
    _fields_ = [('x', C.c_float), ('y', C.c_float), ('w', C.c_float), ('h', C.c_float)]

class Color(C.Structure):
    _fields_ = [('r', C.c_uint8), ('g', C.c_uint8), ('b', C.c_uint8), ('a', C.c_uint8)]

class FPoint(C.Structure):
    _fields_ = [('x', C.c_float), ('y', C.c_float)]

class Vertex(C.Structure):
    _fields_ = [('position', FPoint), ('color', Color), ('tex_coord', FPoint)]

class Keysym(C.Structure):
    _fields_ = [('scancode', C.c_int), ('sym', C.c_int32), ('mod', C.c_uint16), ('unused', C.c_uint32)]

class KeyboardEvent(C.Structure):
    _fields_ = [('type', C.c_uint32), ('timestamp', C.c_uint32), ('windowID', C.c_uint32), ('state', C.c_uint8),
                ('repeat', C.c_uint8), ('p2', C.c_uint8), ('p3', C.c_uint8), ('keysym', Keysym)]

class JoyButtonEvent(C.Structure):
    _fields_ = [('type', C.c_uint32), ('timestamp', C.c_uint32), ('which', C.c_int32), ('button', C.c_uint8), ('state', C.c_uint8), ('p1', C.c_uint8), ('p2', C.c_uint8)]

class JoyHatEvent(C.Structure):
    _fields_ = [('type', C.c_uint32), ('timestamp', C.c_uint32), ('which', C.c_int32), ('hat', C.c_uint8), ('value', C.c_uint8), ('p1', C.c_uint8), ('p2', C.c_uint8)]

class JoyAxisEvent(C.Structure):
    _fields_ = [('type', C.c_uint32), ('timestamp', C.c_uint32), ('which', C.c_int32), ('axis', C.c_uint8), ('p1', C.c_uint8), ('p2', C.c_uint8), ('p3', C.c_uint8), ('value', C.c_int16), ('p4', C.c_uint16)]

class JoyDeviceEvent(C.Structure):
    _fields_ = [('type', C.c_uint32), ('timestamp', C.c_uint32), ('which', C.c_int32)]

class WindowEvent(C.Structure):
    _fields_ = [('type', C.c_uint32), ('timestamp', C.c_uint32), ('windowID', C.c_uint32), ('event', C.c_uint8),
                ('p1', C.c_uint8), ('p2', C.c_uint8), ('p3', C.c_uint8), ('data1', C.c_int32), ('data2', C.c_int32)]

class Event(C.Union):
    _fields_ = [('type', C.c_uint32), ('key', KeyboardEvent), ('jbutton', JoyButtonEvent), ('jhat', JoyHatEvent),
                ('jaxis', JoyAxisEvent), ('jdevice', JoyDeviceEvent), ('window', WindowEvent), ('pad', C.c_uint8 * 56)]

class Surface(C.Structure):
    _fields_ = [('flags', C.c_uint32), ('format', C.c_void_p), ('w', C.c_int), ('h', C.c_int), ('pitch', C.c_int), ('pixels', C.c_void_p)]

class GUID(C.Structure):
    _fields_ = [('data', C.c_uint8 * 16)]

def _f(lib, name, res, *args):
    fn = getattr(lib, name)
    fn.restype = res
    fn.argtypes = list(args)
    return fn

vp = C.c_void_p; i = C.c_int; u32 = C.c_uint32; u8 = C.c_uint8; cs = C.c_char_p; fl = C.c_float
Init = _f(sdl, 'SDL_Init', i, u32)
Quit = _f(sdl, 'SDL_Quit', None)
GetError = _f(sdl, 'SDL_GetError', cs)
SetHint = _f(sdl, 'SDL_SetHint', i, cs, cs)
CreateWindow = _f(sdl, 'SDL_CreateWindow', vp, cs, i, i, i, i, u32)
SetWindowFullscreen = _f(sdl, 'SDL_SetWindowFullscreen', i, vp, u32)
GetWindowSize = _f(sdl, 'SDL_GetWindowSize', None, vp, C.POINTER(i), C.POINTER(i))
DestroyWindow = _f(sdl, 'SDL_DestroyWindow', None, vp)
CreateRenderer = _f(sdl, 'SDL_CreateRenderer', vp, vp, i, u32)
GetRendererOutputSize = _f(sdl, 'SDL_GetRendererOutputSize', i, vp, C.POINTER(i), C.POINTER(i))
RenderSetLogicalSize = _f(sdl, 'SDL_RenderSetLogicalSize', i, vp, i, i)
SetRenderDrawColor = _f(sdl, 'SDL_SetRenderDrawColor', i, vp, u8, u8, u8, u8)
SetRenderDrawBlendMode = _f(sdl, 'SDL_SetRenderDrawBlendMode', i, vp, i)
RenderClear = _f(sdl, 'SDL_RenderClear', i, vp)
RenderFillRect = _f(sdl, 'SDL_RenderFillRect', i, vp, C.POINTER(Rect))
RenderFillRectF = _f(sdl, 'SDL_RenderFillRectF', i, vp, C.POINTER(FRect))
RenderCopy = _f(sdl, 'SDL_RenderCopy', i, vp, vp, C.POINTER(Rect), C.POINTER(Rect))
RenderCopyF = _f(sdl, 'SDL_RenderCopyF', i, vp, vp, C.POINTER(Rect), C.POINTER(FRect))
RenderGeometry = _f(sdl, 'SDL_RenderGeometry', i, vp, vp, C.POINTER(Vertex), i, C.POINTER(i), i)
RenderSetClipRect = _f(sdl, 'SDL_RenderSetClipRect', i, vp, C.POINTER(Rect))
RenderPresent = _f(sdl, 'SDL_RenderPresent', None, vp)
RenderReadPixels = _f(sdl, 'SDL_RenderReadPixels', i, vp, C.POINTER(Rect), u32, vp, i)
SetRenderTarget = _f(sdl, 'SDL_SetRenderTarget', i, vp, vp)
CreateTexture = _f(sdl, 'SDL_CreateTexture', vp, vp, u32, i, i, i)
CreateTextureFromSurface = _f(sdl, 'SDL_CreateTextureFromSurface', vp, vp, vp)
DestroyTexture = _f(sdl, 'SDL_DestroyTexture', None, vp)
SetTextureColorMod = _f(sdl, 'SDL_SetTextureColorMod', i, vp, u8, u8, u8)
SetTextureAlphaMod = _f(sdl, 'SDL_SetTextureAlphaMod', i, vp, u8)
SetTextureBlendMode = _f(sdl, 'SDL_SetTextureBlendMode', i, vp, i)
QueryTexture = _f(sdl, 'SDL_QueryTexture', i, vp, C.POINTER(u32), C.POINTER(i), C.POINTER(i), C.POINTER(i))
FreeSurface = _f(sdl, 'SDL_FreeSurface', None, vp)
CreateRGBSurfaceWithFormat = _f(sdl, 'SDL_CreateRGBSurfaceWithFormat', C.POINTER(Surface), u32, i, i, i, u32)
CreateRGBSurfaceWithFormatFrom = _f(sdl, 'SDL_CreateRGBSurfaceWithFormatFrom', C.POINTER(Surface), vp, i, i, i, i, u32)
PollEvent = _f(sdl, 'SDL_PollEvent', i, C.POINTER(Event))
WaitEventTimeout = _f(sdl, 'SDL_WaitEventTimeout', i, C.POINTER(Event), i)
GetTicks = _f(sdl, 'SDL_GetTicks', u32)
Delay = _f(sdl, 'SDL_Delay', None, u32)
ShowCursor = _f(sdl, 'SDL_ShowCursor', i, i)
NumJoysticks = _f(sdl, 'SDL_NumJoysticks', i)
JoystickOpen = _f(sdl, 'SDL_JoystickOpen', vp, i)
JoystickName = _f(sdl, 'SDL_JoystickName', cs, vp)
JoystickInstanceID = _f(sdl, 'SDL_JoystickInstanceID', i, vp)
JoystickNumButtons = _f(sdl, 'SDL_JoystickNumButtons', i, vp)
JoystickNumAxes = _f(sdl, 'SDL_JoystickNumAxes', i, vp)
JoystickNumHats = _f(sdl, 'SDL_JoystickNumHats', i, vp)
JoystickGetGUID = _f(sdl, 'SDL_JoystickGetGUID', GUID, vp)
JoystickGetGUIDString = _f(sdl, 'SDL_JoystickGetGUIDString', None, GUID, C.c_char_p, i)
JoystickClose = _f(sdl, 'SDL_JoystickClose', None, vp)
RWFromConstMem = _f(sdl, 'SDL_RWFromConstMem', vp, vp, i)

TTF_Init = _f(ttf, 'TTF_Init', i)
TTF_OpenFont = _f(ttf, 'TTF_OpenFont', vp, cs, i)
TTF_SetFontHinting = _f(ttf, 'TTF_SetFontHinting', None, vp, i)
TTF_SetFontKerning = _f(ttf, 'TTF_SetFontKerning', None, vp, i)
TTF_FontHeight = _f(ttf, 'TTF_FontHeight', i, vp)
TTF_FontAscent = _f(ttf, 'TTF_FontAscent', i, vp)
TTF_FontDescent = _f(ttf, 'TTF_FontDescent', i, vp)
TTF_SizeUTF8 = _f(ttf, 'TTF_SizeUTF8', i, vp, cs, C.POINTER(i), C.POINTER(i))
TTF_RenderUTF8_Blended = _f(ttf, 'TTF_RenderUTF8_Blended', C.POINTER(Surface), vp, cs, Color)
TTF_GlyphIsProvided32 = _f(ttf, 'TTF_GlyphIsProvided32', i, vp, u32)
TTF_HINTING_LIGHT = 1; TTF_HINTING_NONE = 3; TTF_HINTING_LIGHT_SUBPIXEL = 4

IMG_Init = _f(img, 'IMG_Init', i, i)
IMG_LoadSizedSVG_RW = _f(img, 'IMG_LoadSizedSVG_RW', C.POINTER(Surface), vp, i, i)
IMG_Load = _f(img, 'IMG_Load', C.POINTER(Surface), cs)
IMG_SavePNG = _f(img, 'IMG_SavePNG', i, C.POINTER(Surface), cs)
