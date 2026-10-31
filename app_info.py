"""
app_info.py - the app's name, version and author, in ONE place.

The About window, the .exe properties and the setup wizard all read from here,
so when you release a new version you only change VERSION.
"""

import os
import sys

APP_NAME = "Dialogue Boost Player"
EXE_NAME = "DialogueBoostPlayer"
VERSION = "1.1.2"
MUTEX_NAME = "TamimRijan.DialogueBoostPlayer.Running"   # must match AppMutexName in installer/setup.iss
DESCRIPTION = "A video player that makes movie dialogue clear without blowing up the explosions."

AUTHOR = "Tamim Ahmed Rijan"
GITHUB = "https://github.com/tamimrijan"
INSTAGRAM = "https://www.instagram.com/tamim_ahmed_rijan/"


def app_folder():
    """Folder with the app's files. When running as a PyInstaller build, the
    bundled files live in sys._MEIPASS (the '_internal' folder)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts):
    """Full path to a bundled file, e.g. resource_path('logo', 'play.png')."""
    return os.path.join(app_folder(), *parts)


LOGO_PATH = resource_path("logo", "play.png")
