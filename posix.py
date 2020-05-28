"""Hotkeys on Posix Plattforms.

Listens to /dev/input/event* and observes Keyboard input

"""

import collections
import pathlib
import select
import struct
import threading
import time

from ht3.env import Env
from ht3.utils.keycodes.posix import KEY_CODES, KEY_NAMES

NAMED_MODIFIERS = {
    'ALT': 1,
    'LEFTALT': 1,
    'RIGHTALT': 1,
    'MENU': 1,

    'CTRL': 2,
    'CONTROL': 2,
    'LEFTCTRL': 2,
    'RIGHTCTRL': 2,

    'SHIFT': 4,
    'LEFTSHIFT': 4,
    'RIGHTSHIFT': 4,

    'MOD4': 8,
    'WIN': 8,
    'META': 8,
    'LEFTMETA': 8,
    'RIGHTMETA': 8,
}

VK_MODIFIERS = {
    KEY_CODES['LEFTALT']: 1,
    KEY_CODES['RIGHTALT']: 1,
    KEY_CODES['LEFTCTRL']: 2,
    KEY_CODES['RIGHTCTRL']: 2,
    KEY_CODES['LEFTSHIFT']: 4,
    KEY_CODES['RIGHTSHIFT']: 4,
    KEY_CODES['LEFTMETA']: 8,
    KEY_CODES['RIGHTMETA']: 8,
}


FORMAT = 'llHHI'
EVENT_SIZE = struct.calcsize(FORMAT)


DEVICES = None  # initially set by update_hotkey_devices()

HOTKEYS_BY_CODE = {}


def register(hk):
    HOTKEYS_BY_CODE[hk.code] = hk


def unregister(hk):
    del HOTKEYS_BY_CODE[hk.code]


def prepare():
    pass


def loop():
    mod = 0
    update_hotkey_devices()
    cached_devices = None
    try:
        while not _LoopEvt.is_set():
            if cached_devices is not DEVICES:
                try:
                    files = [p.open("rb") for p in DEVICES]
                    cached_devices = DEVICES
                except PermissionError:
                    raise PermissionError(
                        "You need to be allowed to read /def/input/event*. Usually by being member of the `input` group")
            r, _, _ = select.select(files, [], [], 0.1)
            for f in r:
                sec, usec, typ, code, value = struct.unpack(
                    FORMAT, f.read(EVENT_SIZE))
                if typ != 1:
                    continue
                m = VK_MODIFIERS.get(code, 0)
                if m:
                    if value:
                        mod |= m
                    else:
                        mod &= ~m
                elif value:
                    c = mod, code
                    hk = HOTKEYS_BY_CODE.get(c)
                    if hk:
                        hk._do_callback()
    finally:
        for f in files:
            f.close()


def start():
    global _LoopEvt
    _LoopEvt = threading.Event()


def stop():

    _LoopEvt.set()


def translate(s):
    """Translate a String like ``Ctrl + A`` into the virtual Key Code and modifiers."""
    parts = s.split('+')
    parts = [s.strip() for s in parts]
    try:
        vk = KEY_CODES[parts[-1]]
    except KeyError:
        vk = parts[-1]
        if vk.startswith('0x'):
            vk = int(vk, 0)
        else:
            raise
    mod = 0
    for m in parts[:-1]:
        mod |= NAMED_MODIFIERS[m.upper()]

    return (mod, vk)


def update_hotkey_devices():
    global DEVICES
    d = Env.get('HOTKEY_DEVICES', None)
    if d is None:
        d = [p for p in pathlib.Path("/dev/input").glob("event*")]
    DEVICES = d
