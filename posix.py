"""Hotkeys on the Windows Plattform."""

import collections
import pathlib
import select
import struct
import threading
import time

from ht3.env import Env
from ht3.keycodes import KEY_CODES, KEY_NAMES

NAMED_MODIFIERS = {
    'ALT': 1,
    'LEFTALT': 1,
    'RIGHTALT':1,
    'MENU': 1,

    'CTRL': 2,
    'CONTROL': 2,
    'LEFTCTRL':2,
    'RIGHTCTRL':2,

    'SHIFT': 4,
    'LEFTSHIFT':4,
    'RIGHTSHIFT':4,

    'MOD4': 8,
    'WIN': 8,
    'META': 8,
    'LEFTMETA':8,
    'RIGHTMETA':8,
}

VK_MODIFIERS = {
    KEY_CODES['LEFTALT']:     1,
    KEY_CODES['RIGHTALT']:    1,
    KEY_CODES['LEFTCTRL']:    2,
    KEY_CODES['RIGHTCTRL']:   2,
    KEY_CODES['LEFTSHIFT']:   4,
    KEY_CODES['RIGHTSHIFT']:  4,
    KEY_CODES['LEFTMETA']:    8,
    KEY_CODES['RIGHTMETA']:   8,
}


FORMAT = 'llHHI'
EVENT_SIZE = struct.calcsize(FORMAT)


DEVICES = Env.get('HOTKEY_DEVICES', None)
if DEVICES is None:
    DEVICES = [p for p in pathlib.Path("/dev/input").glob("event*")]

HOTKEYS_BY_CODE = {}

def register(hk):
    if hk.code in HOTKEYS_BY_CODE:
        raise ValueError("Duplicate Hotkey",hk,HOTKEYS_BY_CODE[hk.code])
    HOTKEYS_BY_CODE[hk.code] = hk

def unregister(hk):
    if HOTKEYS_BY_CODE.get(hk.code) is not hk:
        raise ValueError("Hotkey was not registered",hk,HOTKEYS_BY_CODE.get(hk.code))
    del HOTKEYS_BY_CODE[hk.code]

def prepare():
    pass

def loop():
    mod = 0
    try:
        files = [p.open("rb") for p in DEVICES]
    except PermissionError:
        raise PermissionError("You need to be member of the `input` group")
    try:
        while not evt.is_set():
            r,_,_ = select.select(files, [], [], 0.1)
            for f in r:
                sec, usec, typ, code, value = struct.unpack(FORMAT, f.read(EVENT_SIZE))
                if typ != 1:
                    continue
                m = VK_MODIFIERS.get(code,0)
                if m:
                    if value:
                        mod |= m
                    else:
                        mod &= ~m
                elif value:
                    c = mod,code
                    hk = HOTKEYS_BY_CODE.get(c)
                    if hk:
                        hk._do_callback()
    finally:
        for f in files:
            f.close()

def start():
    global evt
    evt = threading.Event()

def stop():
    evt.set()

def translate(s):
    """Translate a String like ``Ctrl + A`` into the virtual Key Code and modifiers."""
    parts = s.split('+')
    parts = [s.strip() for s in parts]
    try:
        vk = KEY_CODES[parts[-1]]
    except KeyError:
        vk = parts[-1]
        if vk.startswith('0x'):
            vk = int(vk,0)
        else:
            raise
    mod = 0
    for m in parts[:-1]:
        mod |= NAMED_MODIFIERS[m.upper()]

    return (mod,vk)
