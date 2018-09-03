from . import hotkey

hotkey.start()
hk = hotkey.HotKey("F7", print, "Hans")
hk = hotkey.HotKey("F8", hotkey.stop)
hotkey.loop()
