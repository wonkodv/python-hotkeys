"""Frontend for systemwide hotkeys.

This frontend relies on the logging of others and only issues commands
if a hotkey was pressed.
The module scans all commands and registers a hotkey for those that have
the `HotKey` attribute. The commands are called without argument.
"""
import threading
import time

from ht3.check import CHECK
from ht3.keycodes import KEY_CODES

from ht3 import env
from ht3 import command

if CHECK.os.win:
    from .windows import *


__all__ = ('register_hotkey', 'unregister_hotkey', 'hotkey_loop', 'MODIFIERS', 'KEY_CODES')

def translate_hotkey(s):
    """Translate a String like ``Ctrl + A`` into the virtual Key Code and modifiers."""
    parts = s.split('+')
    parts = [s.strip() for s in parts]
    vk = KEY_CODES[parts[-1]]
    mod = 0
    for m in parts[:-1]:
        mod |= MODIFIERS[m.upper()]

    return mod, vk

_message_loop_running = threading.Event()

def loop():
    _message_loop_running.clear()

    hotkeys = []

    for c in command.COMMANDS.values():
        h = c.attrs.get('HotKey',None)
        if h:
            try:
                mod, vk = translate_hotkey(h)
                num = len(hotkeys)
                hotkeys.append([c, h])
                register_hotkey(num, mod, vk)
            except Exception as e:
                env.Env.log_error(e)
            else:
                env.Env.log("Register Hotkey: num=%d hk=%s mod=%r vk=%r" % (num, h, mod, vk))

    hotkey_iter = hotkey_loop()

    while not _message_loop_running.is_set():
        num = next(hotkey_iter)
        if num is None:
            time.sleep(0.05)
            continue
        try:
            c, h = hotkeys[num]
        except Exception as e:
            env.Env.log_error(e)
        else:
            command.run_command_func(c)
    hotkey_iter.close()

    for i in range(len(hotkeys)):
        try:
            unregister_hotkey(i)
        except Exception as e:
            env.Env.log_error(e)

def stop():
    _message_loop_running.set()
