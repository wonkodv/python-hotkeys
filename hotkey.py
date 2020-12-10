"""Frontend for systemwide hotkeys.

This frontend relies on the logging of others and only issues commands
if a hotkey was pressed.
The module scans all commands and registers a hotkey for those that have
the `HotKey` attribute. The commands are called without argument.
"""
import logging
import os
import threading
import time
import weakref
from typing import Callable

impl = None
if os.name == "nt":
    from . import windows as impl
elif "DISPLAY" in os.environ:
    from . import xserver as impl
else:
    raise NotImplementedError("no hotkey implementation for your target")

logger = logging.getLogger(__name__)


_running = False
_Lock = threading.RLock()

_unregistered_hotkeys = []
_hotkey_thread = None

__all__ = (
    "HotKey",
    "EventHotKey",
    "Error",
    "HOTKEYS",
    "get_hotkey",
    "start",
    "run",
    "stop",
)

HOTKEYS = weakref.WeakValueDictionary()


class Error(Exception):
    """API misused"""

    pass


class HotKey:
    """System wide HotKey.

    You need to delete the hotkey (or call its `free` method) before a new
    hotkey with the same key combination can be created. (GC will do that
    at some point, do it yourself to be sure).

    Use inside a with block to takes care of calling free.
    """

    def __init__(
        self,
        hotkey: str,
        callback: Callable[[], None],
        *,
        on_exception: Callable[[Exception], None] = None,
    ):
        """Create a hotkey, that will call callback."""

        self.hotkey = hotkey
        self.code = impl.translate(hotkey)
        self.callback = callback
        self.on_exception = on_exception
        self._registered = False
        with _Lock:
            if not _running:
                _unregistered_hotkeys.append(self)
            else:
                self._register()
        HOTKEYS[self.code] = self

    def _do_callback(self):
        logger.debug("Hotkey activated: %r", self)
        try:
            self.callback()
        except Exception as e:
            if self.on_exception:
                self.on_exception(e)
            else:
                logging.exception("Exception in Hotkey Callback: %r", self)

    def _register(self):
        if self._registered:
            raise Error("already registered")
        impl.register(self)
        logger.info("Hotkey registered: %r", self)
        self._registered = True

    def free(self):
        if self._registered:
            impl.unregister(self)
            logger.info("Hotkey unregistered: %r", self)
            self._registered = False
        try:
            del HOTKEYS[self.code]
        except KeyError:
            pass

    def __enter__(self):
        if not _running:
            raise Error("Hotkey Thread not running")
        return self

    def __exit__(self, *args):
        self.free()

    def __del__(self):
        self.free()

    def __repr__(self):
        return "{}({}, {})".format(
            self.__class__.__name__,
            self.hotkey,
            self.callback.__qualname__,
        )


class EventHotKey(HotKey):
    """A hotkey that acts as a threading Event.

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

    def __init__(self, hotkey: str):
        self.evt = threading.Event()
        super().__init__(hotkey, self.evt.set)
        self.time = time.monotonic()

    def wait(self):
        if not self._registered:
            raise Error("Not active")
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
            self.hotkey, "Set" if self.evt.is_set() else "NotSet"
        )

    def __del__(self):
        self.evt.set()
        super().__del__()


def get_hotkey(hotkey: str) -> HotKey:
    code = impl.translate(hotkey)
    return HOTKEYS[code]


def start(wait: bool = True):
    if _running:
        raise Error("Hotkey Listening already started")
    t = threading.Thread(target=run, name=__name__, daemon=False)
    t.start()
    if wait:
        while 1:
            if _running:
                return
            time.sleep(0)


def run():
    global _hotkey_thread
    global _running
    _hotkey_thread = threading.current_thread()

    if _running:
        raise Error("Hotkey Listening already started")

    impl.prepare()
    logger.debug("Hotkey Processing prepared")
    with _Lock:
        _running = True
        hotkeys = _unregistered_hotkeys.copy()
        _unregistered_hotkeys.clear()

    for hk in hotkeys:
        hk._register()

    logger.debug("Start listening for Hotkeys")
    impl.loop()

    _running = False
    logger.debug("Hotkey listening stopped")


def stop(wait: bool = True):
    logger.debug("Stopping Hotkey listening")
    impl.stop()
    if wait:
        if threading.current_thread() != _hotkey_thread:
            _hotkey_thread.join()
