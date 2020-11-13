"""Hotkeys for X Server.

uses python-xlib
"""

import threading
from ht3.utils.keycodes.xserver import KEY_CODES
from Xlib.display import Display
from Xlib import X
from Xlib import XK
from Xlib.error import CatchError


MODIFIERS = {
    "ALT": X.Mod1Mask,
    "CTRL": X.ControlMask,
    "SHIFT": X.ShiftMask,
    "MOD4": X.Mod4Mask,
}

IGNORED_MODIFIERS = (
    # Numlock       ScrolLock       ?
    X.Mod2Mask | X.Mod3Mask | X.Mod5Mask,
    X.Mod2Mask | X.Mod3Mask | 0,
    X.Mod2Mask | 0 | X.Mod5Mask,
    X.Mod2Mask | 0 | 0,
    0 | X.Mod3Mask | X.Mod5Mask,
    0 | X.Mod3Mask | 0,
    0 | 0 | X.Mod5Mask,
)

HOTKEYS_BY_CODE = {}


def register(hk):
    keycode, mod = hk.code
    catch = CatchError()
    for m in IGNORED_MODIFIERS:
        root.grab_key(
            keycode, mod | m, False, X.GrabModeSync, X.GrabModeAsync, onerror=catch
        )
        if catch.get_error():
            raise catch.get_error()
    HOTKEYS_BY_CODE[hk.code] = hk


def unregister(hk):
    keycode, mod = hk.code
    catch = CatchError()
    for m in IGNORED_MODIFIERS:
        root.ungrab_key(keycode, mod | m, onerror=catch)
        if catch.get_error():
            raise catch.get_error()
    del HOTKEYS_BY_CODE[hk.code]


def prepare():
    global root, display
    display = Display()
    root = display.screen().root
    catch = CatchError()
    root.change_attributes(event_mask=X.KeyPressMask, onerror=catch)
    if catch.get_error():
        raise catch.get_error()


def loop():
    while not _LoopEvt.is_set():
        e = display.next_event()
        if not e:
            return
        mod = e.state
        keycode = e.detail
        mod = mod & IGNORED_MODIFIERS[0]
        code = (mod, keycode)

        hk = HOTKEYS_BY_CODE[code]

        hk._do_callback()


def start():
    global _LoopEvt
    _LoopEvt = threading.Event()


def stop():
    _LoopEvt.set()


def translate(s):
    """Translate a String like ``Ctrl + A`` into the virtual Key Code and modifiers."""
    parts = s.split("+")
    parts = [s.strip() for s in parts]

    key = parts[-1]
    if key.startswith("0x"):
        keycode = int(key, 0)
    else:
        keycode = KEY_CODES[key]

    mod = 0
    for m in parts[:-1]:
        mod |= MODIFIERS[m.upper()]
    return (mod, keycode)
