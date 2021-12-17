import logging

from . import hotkey

logging.getLogger().setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


hotkey.start()
with hotkey.EventHotKey("F6") as hk:
    for t in hk:
        print(t)
        if t < 0.2:
            hotkey.stop()
            break


hk1 = hotkey.HotKey("F6", lambda: print("Hans"))
hk2 = hotkey.HotKey("F7", hotkey.stop)
hotkey.run()
