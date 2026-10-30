"""
make_fonts.py - prepare the fonts in this folder. You only need to run this again
if you want to add an icon (add its name to ICONS) or change the font weights.

    python fonts/make_fonts.py <folder with the downloaded files>

Downloads (free):
    RobotoFlex.ttf                     https://github.com/google/fonts/tree/main/ofl/robotoflex   (OFL)
    MaterialSymbolsRounded.ttf         https://github.com/google/material-design-icons/tree/master/variablefont  (Apache 2.0)
    MaterialSymbolsRounded.codepoints  (same place)

Why: both are "variable fonts" (one file with sliders for weight, width, fill...).
Qt and libass (the subtitle renderer) work most reliably with plain static fonts, so we
cut fixed versions out of them. The icon font has ~3800 icons (15 MB); we keep only
the ones the app uses, which makes it tiny.
"""

import json
import os
import sys

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = os.path.dirname(os.path.abspath(__file__))

WEIGHTS = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}

ICONS = [
    "play_arrow", "pause", "stop", "replay_10", "forward_10", "fullscreen", "fullscreen_exit",
    "volume_up", "volume_down", "volume_off", "tune", "subtitles", "subtitles_off", "graphic_eq",
    "folder_open", "info", "speed", "settings", "palette", "dark_mode", "light_mode", "brightness_auto",
    "check", "close", "format_size", "format_color_text", "audiotrack", "movie", "open_in_new",
    "restart_alt", "keyboard", "bedtime", "vertical_align_bottom", "text_fields", "format_bold",
    "record_voice_over", "hearing", "timer", "video_file", "brand_awareness", "code", "favorite",
    "add", "remove", "closed_caption", "person",
]


def make_text_fonts(source):
    for style, weight in WEIGHTS.items():
        font = TTFont(source)
        # Pin every axis: chosen weight, everything else at its default.
        axes = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
        axes["wght"] = weight
        static = instancer.instantiateVariableFont(font, axes)
        # Give each file proper names so Windows/Qt see one family with 4 weights.
        names = static["name"]
        for record in list(names.names):
            if record.nameID in (1, 2, 3, 4, 6, 16, 17):
                names.removeNames(nameID=record.nameID)
        names.setName("Roboto Flex", 1, 3, 1, 0x409)
        names.setName("Regular", 2, 3, 1, 0x409)
        if style != "Regular":
            names.setName(f"Roboto Flex {style}", 1, 3, 1, 0x409)
            names.setName("Roboto Flex", 16, 3, 1, 0x409)      # typographic family
            names.setName(style, 17, 3, 1, 0x409)               # typographic style
        names.setName(f"Roboto Flex {style}", 4, 3, 1, 0x409)
        names.setName(f"RobotoFlex-{style}", 6, 3, 1, 0x409)
        names.setName(f"RobotoFlex-{style};2026", 3, 3, 1, 0x409)
        static["OS/2"].usWeightClass = weight
        out = os.path.join(HERE, f"RobotoFlex-{style}.ttf")
        static.save(out)
        print(f"{out}: {os.path.getsize(out) // 1024} KB")


def make_icon_fonts(source, codepoints_file):
    codepoints = {}
    with open(codepoints_file, encoding="utf-8") as f:
        for line in f:
            name, code = line.split()
            codepoints[name] = int(code, 16)
    missing = [n for n in ICONS if n not in codepoints]
    if missing:
        sys.exit(f"Unknown icon names: {missing}")

    for fill, family in ((0, "Material Symbols Rounded"), (1, "Material Symbols Rounded Filled")):
        font = TTFont(source)
        static = instancer.instantiateVariableFont(font, {"FILL": fill, "GRAD": 0, "opsz": 24, "wght": 400})
        options = subset.Options()
        options.layout_features = []          # we use code points, not ligature names
        options.name_IDs = ["*"]
        subsetter = subset.Subsetter(options)
        subsetter.populate(unicodes=[codepoints[n] for n in ICONS])
        subsetter.subset(static)
        names = static["name"]
        for record in list(names.names):
            if record.nameID in (1, 4, 6, 16, 17):
                names.removeNames(nameID=record.nameID)
        names.setName(family, 1, 3, 1, 0x409)
        names.setName(family, 4, 3, 1, 0x409)
        names.setName(family.replace(" ", ""), 6, 3, 1, 0x409)
        out = os.path.join(HERE, family.replace(" ", "") + ".ttf")
        static.save(out)
        print(f"{out}: {os.path.getsize(out) // 1024} KB")

    with open(os.path.join(HERE, "icons.json"), "w", encoding="utf-8") as f:
        json.dump({n: codepoints[n] for n in ICONS}, f, indent=1)


if __name__ == "__main__":
    downloads = sys.argv[1] if len(sys.argv) > 1 else HERE
    make_text_fonts(os.path.join(downloads, "RobotoFlex.ttf"))
    make_icon_fonts(os.path.join(downloads, "MaterialSymbolsRounded.ttf"),
                    os.path.join(downloads, "MaterialSymbolsRounded.codepoints"))
