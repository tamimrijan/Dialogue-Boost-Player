"""
settings.py - load and save the app settings as a JSON file.

The file lives in %APPDATA%\\DialogueBoostPlayer\\config.json
(for example C:\\Users\\<you>\\AppData\\Roaming\\DialogueBoostPlayer\\config.json).
We use APPDATA instead of the program folder, because a program installed in
"Program Files" is not allowed to write next to itself.
"""

import json
import os
from dataclasses import dataclass, field, asdict, fields, is_dataclass

from audio_filters import BoostSettings, DEFAULT_PRESET

APP_NAME = "DialogueBoostPlayer"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

MAX_REMEMBERED_POSITIONS = 300   # don't let the resume list grow forever


@dataclass
class SubtitleSettings:
    size: int = 100              # % of normal size (mpv "sub-scale"). Lower it for huge subtitles.
    position: int = 100          # 0 = top of the screen, 100 = bottom (mpv "sub-pos")
    override: bool = False       # ignore the subtitle file's own fonts/sizes/colors (fixes badly made .ass files)
    font: str = "Roboto Flex"
    color: str = "#FFFFFF"
    style: str = "outline"       # "outline" (text with a black edge) or "box" (text on a dark box)
    bold: bool = False


@dataclass
class AppSettings:
    theme: str = "light"                # "light", "dark" or "system"
    volume: int = 80
    muted: bool = False
    boost_enabled: bool = True          # Dialogue Boost is ON by default
    preset: str = DEFAULT_PRESET        # "Light", "Normal", "Night mode" or "Custom"
    boost: BoostSettings = field(default_factory=BoostSettings)
    subtitles: SubtitleSettings = field(default_factory=SubtitleSettings)
    window_width: int = 1100
    window_height: int = 700
    last_folder: str = ""
    # Resume positions: { "c:/path/to/movie.mkv": seconds }
    positions: dict = field(default_factory=dict)


def from_dict(cls, data):
    """Build a dataclass from a dict loaded from JSON. Missing keys or values of the
    wrong type keep their default, so an old or hand-edited config never crashes the app."""
    result = cls()
    if not isinstance(data, dict):
        return result
    for f in fields(cls):
        if f.name not in data:
            continue
        default, value = getattr(result, f.name), data[f.name]
        if is_dataclass(default):
            setattr(result, f.name, from_dict(type(default), value))
        elif isinstance(default, bool):
            if isinstance(value, bool):
                setattr(result, f.name, value)
        elif isinstance(default, (int, float)) and isinstance(value, (int, float)) and not isinstance(value, bool):
            setattr(result, f.name, type(default)(value))
        elif isinstance(value, type(default)):
            setattr(result, f.name, value)
    return result


def load_settings():
    """Read config.json. If it is missing or broken, fall back to defaults instead of crashing."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return from_dict(AppSettings, json.load(f))
    except FileNotFoundError:
        return AppSettings()             # first run
    except (OSError, ValueError) as e:
        print(f"Could not read settings ({e}), using defaults.")
        return AppSettings()


def save_settings(settings):
    """Write config.json. Errors are printed, not raised, so closing the app never crashes."""
    # Trim the resume list: dicts keep insertion order, so the oldest entries come first.
    while len(settings.positions) > MAX_REMEMBERED_POSITIONS:
        del settings.positions[next(iter(settings.positions))]
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        # Write to a temp file first, then rename. If the app dies mid-write,
        # the old config.json is still intact.
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(settings), f, indent=2)
        os.replace(tmp, CONFIG_FILE)
    except OSError as e:
        print(f"Could not save settings: {e}")
