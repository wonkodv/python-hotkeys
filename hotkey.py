"""Frontend for systemwide hotkeys.

This frontend relies on the logging of others and only issues commands
if a hotkey was pressed.
The module scans all commands and registers a hotkey for those that have
the `HotKey` attribute. The commands are called without argument.
"""
import threading
import time
import queue

from ht3.check import CHECK

from ht3.env import Env
from ht3 import command

if CHECK.os.win:
    from . import windows as impl


__all__ = ('disable_all_hotkeys','disable_hotkey','reload_hotkeys')

_message_loop_running = threading.Event()
_hotkeys = {}
_last_num = 0

_q = queue.Queue()

def disable_all_hotkeys():
    _q.put(_unregister_hotkeys)

def reload_hotkeys():
    _q.put(_unregister_hotkeys)
    _q.put(_load_hotkeys)

def disable_hotkey(hk):
    i = _find_hotkey_id(hk)
    _q.put(lambda:_unregister_hotkey(i))

def translate_hotkey(s):
    """Translate a String like ``Ctrl + A`` into the virtual Key Code and modifiers."""
    parts = s.split('+')
    parts = [s.strip() for s in parts]
    vk = impl.KEY_CODES[parts[-1]]
    mod = 0
    for m in parts[:-1]:
        mod |= impl.MODIFIERS[m.upper()]

    return mod, vk

def get_hotkey_command(hk):
    i = _find_hotkey_id(hk)
    c, _, _, _ = _hotkeys[i]
    return c

def _find_hotkey_id(hk):
    smod, svk = translate_hotkey(hk)
    for i, (_, _, vk, mod) in _hotkeys.items():
        if vk == svk and mod == smod:
            return i
    raise KeyError("No such hotkey registered", hk)

def _load_hotkeys():
    global _last_num
    for c in command.COMMANDS.values():
        h = c.attrs.get('HotKey',None)
        if h:
            try:
                mod, vk = translate_hotkey(h)
                num = _last_num
                _last_num += 1
                _hotkeys[num]=(c, h, vk, mod)
                impl.register_hotkey(num, mod, vk)
            except Exception as e:
                Env.error_hook(e)
            else:
                Env.log("Register Hotkey: num=%d hk=%s mod=%r vk=%r" % (num, h, mod, vk))


def _message_loop():
    hotkey_iter = impl.hotkey_loop()

    while not _message_loop_running.is_set():
        num = next(hotkey_iter)
        if num is not None:
            try:
                c, _, _, _ = _hotkeys[num]
                command.run_command_func(c)
            except Exception as e:
                Env.error_hook(e)
            continue
        time.sleep(0.05)
        try:
            c = _q.get_nowait()
        except queue.Empty:
            pass
        else:
            try:
                c()
            except Exception as e:
                Env.error_hook(e)
    hotkey_iter.close()

def _unregister_hotkeys():
    for num, (_, h, _, _) in list(_hotkeys.items()):
        try:
            impl.unregister_hotkey(num)
            del _hotkeys[num]
            Env.log("UnRegister Hotkey: num=%d hk=%s" % (num, h))
        except Exception as e:
            Env.error_hook(e)

def _unregister_hotkey(num):
    impl.unregister_hotkey(num)
    del _hotkeys[num]

def start():
    _message_loop_running.clear()

def loop():
    _load_hotkeys()
    _message_loop()
    _unregister_hotkeys()

def stop():
    _message_loop_running.set()

