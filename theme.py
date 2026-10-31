"""
theme.py - Material Design 3 colors, typography and component styles.

Material 3 doesn't use "random" colors: every color has a ROLE (primary, surface,
onSurface, secondaryContainer, ...). The light and dark schemes below are generated
from one seed color (the indigo of the logo) with Google's Material Theme Builder.
Widgets only ask for roles, so switching light/dark just swaps the table.

Qt Style Sheets (QSS) work like CSS. build_stylesheet() turns the current color table
into one big stylesheet. Buttons choose their M3 look with a "variant" property:
    button.setProperty("variant", "filled")    # filled / tonal / outlined / text / icon / fab / chip / segment / nav
and labels choose their text style with a "type" property:
    label.setProperty("type", "titleLarge")    # M3 type scale
"""

import ctypes
import os
import sys
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor, QFont, QFontDatabase

import app_info

FONT = "Roboto Flex"

LIGHT = {
    "primary": "#4355B9", "onPrimary": "#FFFFFF",
    "primaryContainer": "#DEE0FF", "onPrimaryContainer": "#00105C",
    "secondary": "#5B5D72", "onSecondary": "#FFFFFF",
    "secondaryContainer": "#E0E1F9", "onSecondaryContainer": "#181A2C",
    "tertiaryContainer": "#FFD7F1", "onTertiaryContainer": "#2D1228",
    "error": "#BA1A1A", "errorContainer": "#FFDAD6",
    "surface": "#FBF8FF",
    "surfaceContainerLowest": "#FFFFFF", "surfaceContainerLow": "#F5F2FA",
    "surfaceContainer": "#EFEDF4", "surfaceContainerHigh": "#E9E7EF", "surfaceContainerHighest": "#E4E1E9",
    "onSurface": "#1B1B21", "onSurfaceVariant": "#46464F",
    "outline": "#767680", "outlineVariant": "#C7C5D0",
    "inverseSurface": "#303036", "inverseOnSurface": "#F2EFF7",
}

DARK = {
    "primary": "#BAC3FF", "onPrimary": "#08218A",
    "primaryContainer": "#293CA0", "onPrimaryContainer": "#DEE0FF",
    "secondary": "#C3C5DD", "onSecondary": "#2D2F42",
    "secondaryContainer": "#434659", "onSecondaryContainer": "#E0E1F9",
    "tertiaryContainer": "#5D3C55", "onTertiaryContainer": "#FFD7F1",
    "error": "#FFB4AB", "errorContainer": "#93000A",
    "surface": "#131318",
    "surfaceContainerLowest": "#0E0E13", "surfaceContainerLow": "#1B1B21",
    "surfaceContainer": "#1F1F25", "surfaceContainerHigh": "#2A292F", "surfaceContainerHighest": "#35343A",
    "onSurface": "#E4E1E9", "onSurfaceVariant": "#C7C5D0",
    "outline": "#90909A", "outlineVariant": "#46464F",
    "inverseSurface": "#E4E1E9", "inverseOnSurface": "#303036",
}

# The current colors. Everything reads from here: theme.C["primary"]
C = dict(LIGHT)
MODE = "light"     # what the user picked: "light", "dark" or "system"
DARK_ACTIVE = False


def rgba(hex_color, alpha):
    """'#4355B9', 0.08 -> 'rgba(67,85,185,20)'  (M3 "state layers" are the content color at low opacity)"""
    c = QColor(hex_color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{int(alpha * 255)})"


def mix(base, overlay, amount):
    """Blend overlay onto base. Used for hover/pressed colors of filled buttons."""
    a, b = QColor(base), QColor(overlay)
    r = [int(a.getRgb()[i] + (b.getRgb()[i] - a.getRgb()[i]) * amount) for i in range(3)]
    return QColor(*r).name()


def load_fonts():
    """Register the bundled fonts with Qt, so they work even if not installed on the PC."""
    folder = app_info.resource_path("fonts")
    for name in sorted(os.listdir(folder)):
        if name.endswith(".ttf"):
            QFontDatabase.addApplicationFont(os.path.join(folder, name))


def _arrow_icon_file(color):
    """QSS needs a file for the combo box arrow, so we write a tiny SVG to the temp folder."""
    path = os.path.join(tempfile.gettempdir(), f"dbp_arrow_{color.strip('#')}.svg")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
                    f'<path fill="{color}" d="M7 10l5 5 5-5z"/></svg>')
    return path.replace("\\", "/")


def build_stylesheet():
    c = C
    hover = rgba(c["onSurface"], 0.08)
    pressed = rgba(c["onSurface"], 0.12)
    arrow = _arrow_icon_file(c["onSurfaceVariant"])
    return f"""
* {{ font-family: "{FONT}"; font-size: 14px; color: {c['onSurface']}; }}
QMainWindow, QDialog, QWidget#page, QWidget#welcome {{ background: {c['surface']}; }}
QToolTip {{ background: {c['inverseSurface']}; color: {c['inverseOnSurface']}; border: none;
            border-radius: 4px; padding: 6px 8px; font-size: 12px; }}

/* ---------------- typography (M3 type scale) ---------------- */
QLabel[type="displaySmall"]   {{ font-size: 36px; }}
QLabel[type="headlineMedium"] {{ font-size: 28px; }}
QLabel[type="headlineSmall"]  {{ font-size: 24px; }}
QLabel[type="titleLarge"]     {{ font-size: 22px; }}
QLabel[type="titleMedium"]    {{ font-size: 16px; font-weight: 500; }}
QLabel[type="titleSmall"]     {{ font-size: 14px; font-weight: 500; }}
QLabel[type="bodyLarge"]      {{ font-size: 16px; }}
QLabel[type="bodyMedium"]     {{ font-size: 14px; color: {c['onSurfaceVariant']}; }}
QLabel[type="bodySmall"]      {{ font-size: 12px; color: {c['onSurfaceVariant']}; }}
QLabel[type="labelLarge"]     {{ font-size: 14px; font-weight: 500; }}
QLabel[type="labelMedium"]    {{ font-size: 12px; font-weight: 500; color: {c['onSurfaceVariant']}; }}
QLabel[type="overline"]       {{ font-size: 12px; font-weight: 600; color: {c['primary']}; }}
QLabel[type="value"]          {{ font-size: 14px; font-weight: 600; color: {c['primary']}; }}

/* ---------------- menu bar + menus ---------------- */
QMenuBar {{ background: {c['surface']}; padding: 4px 8px; border-bottom: 1px solid {c['outlineVariant']}; }}
QMenuBar::item {{ padding: 8px 14px; border-radius: 8px; color: {c['onSurfaceVariant']}; font-weight: 500; background: transparent; }}
QMenuBar::item:selected {{ background: {hover}; color: {c['onSurface']}; }}
QMenuBar::item:pressed {{ background: {c['secondaryContainer']}; color: {c['onSecondaryContainer']}; }}
QMenu {{ background: {c['surfaceContainer']}; border: 1px solid {c['outlineVariant']}; border-radius: 4px; padding: 8px 0; }}
QMenu::item {{ padding: 10px 40px 10px 16px; background: transparent; }}
QMenu::item:selected {{ background: {hover}; }}
QMenu::item:disabled {{ color: {rgba(c['onSurface'], 0.38)}; }}
QMenu::icon {{ padding-left: 14px; }}
QMenu::separator {{ height: 1px; background: {c['outlineVariant']}; margin: 8px 0; }}
QMenu::indicator {{ width: 18px; height: 18px; padding-left: 12px; }}

/* ---------------- buttons ---------------- */
QPushButton, QToolButton {{ border: none; background: transparent; border-radius: 20px; font-weight: 500; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

QPushButton[variant="filled"] {{ background: {c['primary']}; color: {c['onPrimary']}; padding: 0 24px; min-height: 40px; }}
QPushButton[variant="filled"]:hover {{ background: {mix(c['primary'], c['onPrimary'], 0.08)}; }}
QPushButton[variant="filled"]:pressed {{ background: {mix(c['primary'], c['onPrimary'], 0.12)}; }}

QPushButton[variant="tonal"] {{ background: {c['secondaryContainer']}; color: {c['onSecondaryContainer']}; padding: 0 24px; min-height: 40px; }}
QPushButton[variant="tonal"]:hover {{ background: {mix(c['secondaryContainer'], c['onSecondaryContainer'], 0.08)}; }}

QPushButton[variant="outlined"] {{ border: 1px solid {c['outline']}; color: {c['primary']}; padding: 0 24px; min-height: 38px; }}
QPushButton[variant="outlined"]:hover {{ background: {rgba(c['primary'], 0.08)}; }}

QPushButton[variant="text"] {{ color: {c['primary']}; padding: 0 12px; min-height: 40px; }}
QPushButton[variant="text"]:hover {{ background: {rgba(c['primary'], 0.08)}; }}

QPushButton[variant="icon"], QToolButton[variant="icon"] {{
    min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px; border-radius: 20px; padding: 0; }}
QPushButton[variant="icon"]:hover, QToolButton[variant="icon"]:hover {{ background: {rgba(c['onSurfaceVariant'], 0.08)}; }}
QPushButton[variant="icon"]:pressed, QToolButton[variant="icon"]:pressed {{ background: {rgba(c['onSurfaceVariant'], 0.12)}; }}
QPushButton[variant="icon"]:checked {{ background: {c['secondaryContainer']}; }}

/* M3 FAB: 56 dp, rounded square, primary container */
QPushButton[variant="fab"] {{ background: {c['primaryContainer']}; border-radius: 16px;
    min-width: 56px; max-width: 56px; min-height: 56px; max-height: 56px; padding: 0; }}
QPushButton[variant="fab"]:hover {{ background: {mix(c['primaryContainer'], c['onPrimaryContainer'], 0.08)}; }}
QPushButton[variant="fab"]:pressed {{ background: {mix(c['primaryContainer'], c['onPrimaryContainer'], 0.12)}; }}

/* M3 filter chip */
QPushButton[variant="chip"], QToolButton[variant="chip"] {{ border: 1px solid {c['outlineVariant']}; border-radius: 8px;
    min-height: 30px; max-height: 30px; padding: 0 14px 0 8px; color: {c['onSurfaceVariant']}; }}
QToolButton[variant="chip"] {{ padding: 0 14px; }}
QPushButton[variant="chip"]:hover, QToolButton[variant="chip"]:hover {{ background: {hover}; }}
QPushButton[variant="chip"]:checked {{ background: {c['secondaryContainer']}; border-color: {c['secondaryContainer']};
    color: {c['onSecondaryContainer']}; }}

/* M3 segmented button */
QPushButton[variant="segment"] {{ border: 1px solid {c['outline']}; border-radius: 0; min-height: 38px;
    padding: 0 12px; color: {c['onSurface']}; }}
QPushButton[variant="segment"][pos="mid"], QPushButton[variant="segment"][pos="last"] {{ border-left: none; }}
QPushButton[variant="segment"][pos="first"] {{ border-top-left-radius: 20px; border-bottom-left-radius: 20px; }}
QPushButton[variant="segment"][pos="last"] {{ border-top-right-radius: 20px; border-bottom-right-radius: 20px; }}
QPushButton[variant="segment"]:hover {{ background: {hover}; }}
QPushButton[variant="segment"]:checked {{ background: {c['secondaryContainer']}; color: {c['onSecondaryContainer']}; }}

/* M3 navigation drawer item */
QPushButton[variant="nav"] {{ text-align: left; padding: 0 16px; min-height: 56px; border-radius: 28px;
    color: {c['onSurfaceVariant']}; }}
QPushButton[variant="nav"]:hover {{ background: {hover}; }}
QPushButton[variant="nav"]:checked {{ background: {c['secondaryContainer']}; color: {c['onSecondaryContainer']}; font-weight: 600; }}
QPushButton[variant="nav"][rail="true"] {{ text-align: center; padding: 0; min-width: 56px; max-width: 56px;
    min-height: 56px; max-height: 56px; border-radius: 28px; margin-left: 4px; }}

/* color swatch for subtitle colors */
QPushButton[variant="swatch"] {{ min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px;
    border-radius: 18px; border: 1px solid {c['outline']}; }}
QPushButton[variant="swatch"]:checked {{ border: 3px solid {c['primary']}; }}

/* ---------------- containers ---------------- */
QFrame#controls {{ background: {c['surfaceContainer']}; }}
QWidget#overlay QFrame#controls {{ background: {rgba(c['surfaceContainer'], 0.80)};
    border: 1px solid {rgba(c['outlineVariant'], 0.7)}; border-radius: 28px; }}
QFrame#card {{ background: {c['surfaceContainerLow']}; border-radius: 16px; }}
QWidget#drawer {{ background: {c['surfaceContainerLow']}; }}
QFrame#divider {{ background: {c['outlineVariant']}; max-height: 1px; min-height: 1px; }}

/* ---------------- sliders (M3 expressive: thick track + bar handle with a gap) ---------------- */
QSlider {{ min-height: 32px; background: transparent; }}
QSlider::groove:horizontal {{ height: 12px; border-radius: 6px; background: {c['secondaryContainer']}; }}
QSlider::sub-page:horizontal {{ height: 12px; border-radius: 6px; background: {c['primary']}; }}
QSlider::handle:horizontal {{ width: 4px; margin: -9px 0; border-radius: 4px; background: {c['primary']};
    border: 3px solid {c['surface']}; }}
QFrame#controls QSlider::handle:horizontal {{ border-color: {c['surfaceContainer']}; }}
QFrame#card QSlider::handle:horizontal {{ border-color: {c['surfaceContainerLow']}; }}
QSlider#seek::groove:horizontal, QSlider#seek::sub-page:horizontal {{ height: 8px; border-radius: 4px; }}
QSlider#seek::handle:horizontal {{ margin: -11px 0; }}

/* ---------------- inputs ---------------- */
QComboBox {{ border: 1px solid {c['outline']}; border-radius: 4px; min-height: 38px; padding: 0 12px;
    background: transparent; }}
QComboBox:hover {{ border-color: {c['onSurface']}; }}
QComboBox:on {{ border: 2px solid {c['primary']}; }}
QComboBox::drop-down {{ border: none; width: 32px; }}
QComboBox::down-arrow {{ image: url({arrow}); width: 20px; height: 20px; }}
QComboBox QAbstractItemView {{ background: {c['surfaceContainer']}; border: 1px solid {c['outlineVariant']};
    selection-background-color: {pressed}; selection-color: {c['onSurface']}; padding: 6px 0; outline: 0; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {rgba(c['onSurfaceVariant'], 0.35)}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

QMessageBox {{ background: {c['surfaceContainerHigh']}; }}
QMessageBox QPushButton {{ color: {c['primary']}; min-width: 64px; min-height: 40px; padding: 0 12px; }}
QMessageBox QPushButton:hover {{ background: {rgba(c['primary'], 0.08)}; }}
"""


def _palette():
    c = C
    p = QPalette()
    p.setColor(QPalette.Window, QColor(c["surface"]))
    p.setColor(QPalette.WindowText, QColor(c["onSurface"]))
    p.setColor(QPalette.Base, QColor(c["surfaceContainerLowest"]))
    p.setColor(QPalette.AlternateBase, QColor(c["surfaceContainer"]))
    p.setColor(QPalette.Text, QColor(c["onSurface"]))
    p.setColor(QPalette.PlaceholderText, QColor(c["onSurfaceVariant"]))
    p.setColor(QPalette.Button, QColor(c["surfaceContainerHigh"]))
    p.setColor(QPalette.ButtonText, QColor(c["onSurface"]))
    p.setColor(QPalette.Highlight, QColor(c["primary"]))
    p.setColor(QPalette.HighlightedText, QColor(c["onPrimary"]))
    p.setColor(QPalette.Link, QColor(c["primary"]))
    p.setColor(QPalette.ToolTipBase, QColor(c["inverseSurface"]))
    p.setColor(QPalette.ToolTipText, QColor(c["inverseOnSurface"]))
    return p


def apply(app, mode):
    """Switch the whole app to "light", "dark" or "system" (follow Windows)."""
    global MODE, DARK_ACTIVE
    MODE = mode
    if mode == "system":
        DARK_ACTIVE = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    else:
        DARK_ACTIVE = mode == "dark"
    C.clear()
    C.update(DARK if DARK_ACTIVE else LIGHT)

    app.setStyle("Fusion")
    font = QFont(FONT)
    font.setPixelSize(14)
    app.setFont(font)
    app.setPalette(_palette())
    app.setStyleSheet(build_stylesheet())

    import icons            # here, not at the top, because icons.py imports theme
    icons.refresh_all()
    for window in app.topLevelWidgets():
        if window.isWindow() and window.testAttribute(Qt.WA_WState_Created):
            title_bar(window)
        window.update()


# ---- Windows-only window effects (they silently do nothing elsewhere) ------

def title_bar(widget):
    """Make the Windows title bar match the theme (dark or light)."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(1 if DARK_ACTIVE else 0)
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE (19 on older Windows 10 builds)
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), 4) == 0:
                break
        if widget.isVisible() and not (widget.isMaximized() or widget.isFullScreen()):
            # Windows 10 doesn't repaint the title bar by itself. A 1-pixel resize and back
            # forces it. (A maximized window repaints it the next time it's activated.)
            size = widget.size()
            widget.resize(size.width() + 1, size.height())
            widget.resize(size)
    except Exception:
        pass


class _AccentPolicy(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]


class _CompositionData(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.POINTER(_AccentPolicy)),
                ("SizeOfData", ctypes.c_size_t)]


def enable_blur_behind(widget):
    """Real "frosted glass": Windows blurs whatever is behind this window
    (here: the video). The widget must have a translucent background."""
    if sys.platform != "win32":
        return False
    try:
        accent = _AccentPolicy(3, 0, 0, 0)   # 3 = ACCENT_ENABLE_BLURBEHIND
        data = _CompositionData(19, ctypes.pointer(accent), ctypes.sizeof(accent))   # 19 = WCA_ACCENT_POLICY
        return bool(ctypes.windll.user32.SetWindowCompositionAttribute(int(widget.winId()), ctypes.byref(data)))
    except Exception:
        return False
