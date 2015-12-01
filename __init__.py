import os
import threading
import warnings
import time

from ht3.lib import Check
from ht3.keycodes import KEY_CODES

from ht3 import env
from ht3 import command

if Check.os.win:
    from .windows import *


__all__ = ['register_hotkey', 'unregister_hotkey', 'hotkey_loop', 'MODIFIERS', 'KEY_CODES']

def translate_hotkey(s):
    parts = s.split('+')
    parts = [s.strip() for s in parts]
    vk = KEY_CODES[parts[-1]]
    mod = 0
    for m in parts[:-1]:
        mod |= MODIFIERS[m]

    return mod, vk

_message_loop_running = threading.Event()

def loop():
    _message_loop_running.clear()

    hotkeys = []

    for c in command.COMMANDS.values():
        h = c.attrs.get('HotKey',None)
        if h:
            mod, vk = translate_hotkey(h)
            id = len(hotkeys)
            hotkeys.append([c, h])

            try:
                register_hotkey(id, mod, vk)
            except Exception as e:
                env.Env.handle_exception(e)
            else:
                env.Env.log("Register Hotkey: id=%d hk=%s mod=%r vk=%r" % (id, h, mod, vk))

    hotkey_iter = hotkey_loop()

    while not _message_loop_running.is_set():
        id = next(hotkey_iter)
        if id is None:
            time.sleep(0.05)
            continue
        if id < 0 or id >= len(hotkeys):
            lib.handle_exception(ValueError("Invalid Hotkey ID"))
            continue
        c, h = hotkeys[id]
        try:
            r = c()
            env.Env.log("Hotkey %s: %s => %r", h, c.name, r)
        except Exception as e:
            env.Env.handle_exception(e)
    hotkey_iter.close()

    for i in range(len(hotkeys)):
        try:
            unregister_hotkey(i)
        except Exception as e:
            env.Env.handle_exception(e)

def stop():
    _message_loop_running.set()
