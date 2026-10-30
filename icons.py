"""
icons.py - Material Symbols Rounded icons (Google's official Material 3 icons).

The icons live in a font (fonts/MaterialSymbolsRounded*.ttf). Each icon is one
character; fonts/icons.json maps names like "play_arrow" to their character code.
We draw that character into a picture to make a QIcon.

Icons follow the theme: use bind() instead of setIcon(), and when the theme
changes, refresh_all() redraws every bound icon in the new colors.

    icons.bind(button, "pause", role="onPrimaryContainer", filled=True)
"""

import json
import weakref

from PySide6.QtCore import Qt, QByteArray, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QFont, QColor
from PySide6.QtSvg import QSvgRenderer

import app_info
import theme

with open(app_info.resource_path("fonts", "icons.json"), encoding="utf-8") as _f:
    CODEPOINTS = json.load(_f)

# Brand logos are not part of Material Symbols, so these two are SVG paths.
BRANDS = {
    "github": "M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.09.68-.22.68-.49v-1.71c-2.78.62-3.37-1.37"
              "-3.37-1.37-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.62.07-.62 1 .07 1.53 1.06 1.53 1.06.89 1.57 2.34"
              " 1.12 2.91.85.09-.66.35-1.12.63-1.37-2.22-.26-4.56-1.14-4.56-5.07 0-1.12.39-2.03 1.03-2.75-.1-.26-.45"
              "-1.3.1-2.71 0 0 .84-.28 2.75 1.05A9.4 9.4 0 0 1 12 6.84c.85 0 1.7.12 2.5.34 1.91-1.33 2.75-1.05 2.75"
              "-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.94-2.34 4.81-4.57 5.06.36.32.68.94.68 1.9"
              "v2.81c0 .27.18.59.69.49A10.1 10.1 0 0 0 22 12.25C22 6.58 17.52 2 12 2z",
    "instagram": "M7.8 2h8.4C19.4 2 22 4.6 22 7.8v8.4a5.8 5.8 0 0 1-5.8 5.8H7.8C4.6 22 2 19.4 2 16.2V7.8A5.8 5.8 0"
                 " 0 1 7.8 2m-.2 2A3.6 3.6 0 0 0 4 7.6v8.8C4 18.39 5.61 20 7.6 20h8.8a3.6 3.6 0 0 0 3.6-3.6V7.6"
                 "C20 5.61 18.39 4 16.4 4H7.6m9.65 1.5a1.25 1.25 0 0 1 1.25 1.25A1.25 1.25 0 0 1 17.25 8 1.25 1.25"
                 " 0 0 1 16 6.75a1.25 1.25 0 0 1 1.25-1.25M12 7a5 5 0 0 1 5 5 5 5 0 0 1-5 5 5 5 0 0 1-5-5 5 5 0 0 1"
                 " 5-5m0 2a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3z",
}


def icon(name, role="onSurfaceVariant", filled=False, color=None, size=64):
    """Draw one icon. `role` is a theme color role; `color` (e.g. '#FFFFFF') overrides it.
    Drawn large (64 px) so it stays sharp on high-DPI screens."""
    color = QColor(color or theme.C[role])
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    if name in BRANDS:
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
               f'<path fill="{color.name()}" d="{BRANDS[name]}"/></svg>')
        QSvgRenderer(QByteArray(svg.encode())).render(painter, QRectF(4, 4, size - 8, size - 8))
    else:
        font = QFont("Material Symbols Rounded Filled" if filled else "Material Symbols Rounded")
        font.setPixelSize(size)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, chr(CODEPOINTS[name]))
    painter.end()
    return QIcon(pixmap)


# ---- theme-aware icons ---------------------------------------------------------
_bound = {}   # id(widget) -> (weak reference, name, role, filled)


def bind(widget, name, role="onSurfaceVariant", filled=False):
    """Set an icon on a button/action AND remember it, so a theme change can recolor it.
    Calling bind() again on the same widget replaces its icon (e.g. play -> pause)."""
    _bound[id(widget)] = (weakref.ref(widget), name, role, filled)
    widget.setIcon(icon(name, role, filled))


def unbind(widget):
    """Remove a bound icon."""
    _bound.pop(id(widget), None)
    widget.setIcon(QIcon())


def refresh_all():
    for key, (ref, name, role, filled) in list(_bound.items()):
        widget = ref()
        try:
            widget.setIcon(icon(name, role, filled))
        except (AttributeError, RuntimeError):   # widget was deleted
            del _bound[key]
