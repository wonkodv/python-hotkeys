Python Hotkeys
==============


Register systemwide hotkeys from python


Usage
---------

    import hotkey
    hotkey.start()
    hk = hotkey.HotKey("F7", print, "Hans")
    hk = hotkey.HotKey("F8", hotkey.stop)
    hotkey.loop()


TODOs
--------

* remove all the hanstool dependencies

