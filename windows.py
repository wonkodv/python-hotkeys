"""Hotkeys on the Windows Plattform."""

import queue
import time
import threading


from ctypes import windll, byref, WinError
from ctypes.wintypes import MSG

from ht3.keycodes import KEY_CODES


WM_HOTKEY = 0x312
WM_USER = 0x0400
WM_STOP = WM_USER + 1
WM_NOTIFY = WM_USER + 2

MODIFIERS = {
    'ALT': 1,
    'MENU': 1,
    'CTRL': 2,
    'CONTROL': 2,
    'SHIFT': 4,
    'MOD4': 8,
    'WIN': 8
}

_next_id = 0
HOTKEYS_BY_ID = {}

HK_WORKER_THREAD = None
HK_WORKER_THREAD_ID = None

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
            if not windll.user32.PostThreadMessageW(HK_WORKER_THREAD_ID, WM_NOTIFY, 0, 0):
                raise WinError()
            e.wait()
            if e._exception:
                raise e._exception
            return e._result
    return wrapper

@do_in_hk_thread
def register(hk):
    global _next_id

    _next_id = _next_id + 1
    hk._win_hk_id = _next_id

    mod, vk = hk.code

    if not windll.user32.RegisterHotKey(0, hk._win_hk_id, mod, vk):
        raise WinError()

    HOTKEYS_BY_ID[hk._win_hk_id] = hk

@do_in_hk_thread
def unregister(hk):
    if not windll.user32.UnregisterHotKey(0, hk._win_hk_id):
        raise WinError();
    del HOTKEYS_BY_ID[hk._win_hk_id]

def prepare():
    global HK_WORKER_THREAD, HK_WORKER_THREAD_ID
    HK_WORKER_THREAD = threading.current_thread()
    HK_WORKER_THREAD_ID = windll.kernel32.GetCurrentThreadId()

def loop():
    try:
        msg = MSG()
        lpmsg = byref(msg)

        while windll.user32.GetMessageW(lpmsg, 0, 0, 0):
            if msg.message == WM_HOTKEY:
                HOTKEYS_BY_ID[msg.wParam]._do_callback()
            elif  msg.message == WM_STOP:
                return
            elif msg.message == WM_NOTIFY:
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
            else:
                raise AssertionError(msg)

    finally:
        HK_WORKER_THREAD = None
        HK_WORKER_THREAD_ID = None

def start():
    pass

def stop():
    assert HK_WORKER_THREAD
    if not windll.user32.PostThreadMessageW(HK_WORKER_THREAD_ID, WM_STOP, 0, 0):
        raise WinError()

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

    return (mod,vk)

