"""Frontend for systemwide hotkeys.

This frontend relies on the logging of others and only issues commands
if a hotkey was pressed.
The module scans all commands and registers a hotkey for those that have
the `HotKey` attribute. The commands are called without argument.
"""

import queue
import threading
import time
import weakref

from ht3.check import CHECK

from ht3.env import Env
from ht3 import command
from ht3 import lib

if CHECK.os.win:
    from . import windows as impl


__all__ = (
    'HotKey',
    'HotKeyError',
    'disable_all_hotkeys',
    'enable_all_hotkeys',
    'get_hotkey',
    'reload_hotkeys',
)

_message_loop_running = threading.Event()
_Lock = threading.Lock()

class HotKeyError(Exception):
    pass

class HotKey:
    HOTKEYS = weakref.WeakValueDictionary()
    def __init__(self, hotkey, callback, *args, **kwargs):
        self.hotkey = hotkey
        self.code = code = impl.translate(hotkey)
        self._callback = callback
        self._args = args
        self._kwargs = kwargs
        self.active = False
        with _Lock:
            if code in HotKey.HOTKEYS:
                raise HotKeyError("Duplicate Hotkey", hotkey)
            HotKey.HOTKEYS[code] = self

    def register(self):
        with _Lock:
            if not self.active:
                impl.register(self)
                lib.DEBUG_HOOK(message="{0} registered".format(self))
                self.active = True
            else:
                raise HotKeyError("Already active")


    def unregister(self):
        with _Lock:
            if self.active:
                lib.DEBUG_HOOK(message="{0} unregistered".format(self))
                self.active = False
                impl.unregister(self)
            else:
                raise HotKeyError("Already active")

    def do_callback(self):
        try:
            self._callback(*self._args, **self._kwargs)
        except Exception as e:
            lib.EXCEPTION_HOOK(exception=e)

    def __del__(self):
        with _Lock:
            assert not self.active, "Impl should hang on to obj while active"

    def __repr__(self):
        return "HotKey({0}, active={1}, callback={2})".format(
                self.hotkey, self.active,
                self._callback.__qualname__)

def disable_all_hotkeys():
    for hk in list(HotKey.HOTKEYS.values()): # size changes during iteration, list fixes the problem
        try:
            hk.unregister()
        except HotKeyError:
            pass

def enable_all_hotkeys():
    for hk in list(HotKey.HOTKEYS.values()):
        try:
            hk.register()
        except HotKeyError:
            pass

def get_hotkey(hk):
    code = impl.translate(hk)
    hk = HotKey.HOTKEYS[code]
    return hk

def reload_hotkeys():
    """For all commands that have a HotKey attribute, register a hotkey.

    If the command already had a hotkey, register it, otherwise create a new hotkey and
    attach it to the command.
    """

    for c in command.COMMANDS.values():
        try:
            try:
                hk = c.attrs['HotKey']
            except KeyError:
                continue

            hko = None
            try:
                hko = c._HotKey
                assert not hko.acive
                assert hko.hotkey == hk
            except AttributeError:
                pass

            if not hko:
                def run_command(c,hk):
                    c(hk,"")()
                run_command.__qualname__ = c.__qualname__
                hko = HotKey(hk, run_command, c, hk)
                c.attrs['_HotKey'] = hko

            hko.register()
        except Exception as e:
            lib.EXCEPTION_HOOK(exception=e)


def start():
    _message_loop_running.clear()

def loop():
    impl.prepare()
    reload_hotkeys()
    impl.loop(_message_loop_running)
    disable_all_hotkeys()
    impl.stop()

def stop():
    _message_loop_running.set()
