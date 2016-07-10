"""Hotkeys on the Windows Plattform."""

import queue
import time
import threading


from ctypes import windll, byref, WinError
from ctypes.wintypes import MSG

from ht3.keycodes import KEY_CODES


WM_HOTKEY = 0x312

MODIFIERS = {
    'ALT': 1,
    'MENU': 1,
    'CTRL': 2,
    'CONTROL': 2,
    'SHIFT': 4,
    'MOD4': 8,
    'WIN': 8
}

HOTKEYS_BY_ID = {}

HK_WORKER_THREAD = None

HK_OP_Q = queue.Queue()

def do_in_hk_thread(f):
    def wrapper(*args, **kwargs):
        if HK_WORKER_THREAD is None:
            raise Exception("No Hotkey Worker Thread", threading.current_thread())

        if threading.current_thread() == HK_WORKER_THREAD:
            return f(*args, **kwargs)
        else:
            e = threading.Event()
            HK_OP_Q.put((e,f,args,kwargs))
            e.wait()
            if e._exception:
                raise e._exception
            return e._result
    return wrapper

@do_in_hk_thread
def register(hk):
    code = hk.code
    vk = hk.code & 0xFF
    mod = hk.code >> 8

    id = len(HOTKEYS_BY_ID) + 42
    while id in HOTKEYS_BY_ID:
        id += 1
    hk._win_hk_id = id

    if not windll.user32.RegisterHotKey(0, hk._win_hk_id, mod, vk):
        raise WinError()
    HOTKEYS_BY_ID[hk._win_hk_id] = hk

@do_in_hk_thread
def unregister(hk):
    if not windll.user32.UnregisterHotKey(0, hk._win_hk_id):
        raise WinError();
    del HOTKEYS_BY_ID[hk._win_hk_id]
    del hk._win_hk_id


def loop(stop_evt):
    msg = MSG()
    lpmsg = byref(msg)

    while not stop_evt.is_set():
        time.sleep(0.05)

        while 1:
            try:
                e, f, args, kwargs = HK_OP_Q.get_nowait()
            except queue.Empty:
                break
            try:
                e._result = f(*args, **kwargs)
                e._exception = None
            except Exception as e:
                e._exception = e
            e.set()

        while windll.user32.PeekMessageW(lpmsg, 0, 0, 0, 1):
            if msg.message != WM_HOTKEY:
                raise OSError("Unknown Message", msg)
            HOTKEYS_BY_ID[msg.wParam].do_callback()

def prepare():
    global HK_WORKER_THREAD
    HK_WORKER_THREAD = threading.current_thread()

def stop():
    global HK_WORKER_THREAD
    HK_WORKER_THREAD = None

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
        mod |= MODIFIERS[m.upper()]

    return mod <<8 | vk

