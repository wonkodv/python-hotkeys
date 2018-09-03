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
elif CHECK.os.posix:
    from . import posix as impl
else:
    raise ImportError("No Hotkey Provider for your Plattform")


__all__ = (
    'HotKey',
    'EventHotKey',
    'HotKeyError',
    'disable_all_hotkeys',
    'enable_all_hotkeys',
    'get_hotkey',
    'reload_hotkeys',
)

_Lock = threading.Lock()

class HotKeyError(Exception):
    pass

class HotKey:
    """System wide HotKey.

    Before use, the hotkey must be registered.
    It can be unregistered, and then re-registered.

    You need to delete the hotkey (or call its `free` method) before a new
    hotkey with the same key combination can be created. (GC will do that
    at some point, do it yourself to be sure).

    Use inside a with block to takes care of calling register and free (can
    only be used once)
    """
    HOTKEYS = weakref.WeakValueDictionary()
    def __init__(self, hotkey, callback, *args, **kwargs):
        """Create a hotkey, that will call a callback.

        Calls `callback` with `*args` and `**kwargs` when the hotkey is
        triggered (while it is registered).
        """

        self.hotkey = hotkey
        self.code = code = impl.translate(hotkey)
        self._callback = callback
        self._args = args
        self._kwargs = kwargs
        self.active = False
        with _Lock:
            if code in self.HOTKEYS:
                raise HotKeyError("Duplicate Hotkey", hotkey)
            self.HOTKEYS[code] = self

    def _do_callback(self):
        try:
            self._callback(*self._args, **self._kwargs)
        except Exception as e:
            lib.EXCEPTION_HOOK(exception=e)

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
                impl.unregister(self)
                self.active = False
            else:
                raise HotKeyError("Already deactivated")

    def free(self):
        try:
            self.unregister()
        except HotKeyError:
            pass
        with _Lock:
            try:
                del self.HOTKEYS[self.code]
            except KeyError:
                pass

    def __enter__(self):
        self.register()
        return self

    def __exit__(self, *args):
        self.free()

    def __del__(self):
        with _Lock:
            assert not self.active, "Impl should hang on to obj while active"

    def __repr__(self):
        return "HotKey({0}, active={1}, callback={2})".format(
                self.hotkey, self.active,
                self._callback.__qualname__)

class EventHotKey(HotKey):
    """ A hotkey that acts as a threading Event.

    Wait until Hotkey is pressed, Clear and wait again.

    Can be iterated, in which case it yields the time since the last Hotkey was
    triggered last (multiple events are not queued).

    Example that prints the interval of keypress, until the key is pressed twice quickly:

        with EventHotKey("Ctrl+H") as hk:
            for t in hk:
                if t < 0.25:
                    break
                print(t)
    """

    def __init__(self, hotkey):
        self.evt = threading.Event()
        super().__init__(hotkey, self.evt.set)
        self.time = time.monotonic()

    def wait(self):
        if not self.active:
            raise HotKeyError("Not active")
        self.evt.wait()
        t2 = time.monotonic()
        t = t2 - self.time
        self.time = t2
        return t

    def clear(self):
        self.evt.clear()

    def clear_and_wait(self):
        self.clear()
        return self.wait()

    def __iter__(self):
        while True:
            yield self.clear_and_wait()

    def __repr__(self):
        return "EventHotKey({}, {})".format(
                self.hotkey, "Set" if self.evt.is_set() else "NotSet")

    def __del__(self):
        self.evt.set() # Should not be needed, but otherwise deadlocks show up :-/

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


@command.COMMAND_EXCEPTION_HOOK.register
def _command_exception(exception, command):
    if command.frontend == 'ht3.hotkey':
        return True # Don't raise the exception

def start():
    impl.start()

def loop():
    impl.prepare()
    reload_hotkeys()
    impl.loop()
    disable_all_hotkeys()

def stop():
    impl.stop()


