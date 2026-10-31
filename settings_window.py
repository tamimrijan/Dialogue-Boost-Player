"""
settings_window.py - the Settings window, built from Material 3 components.

    left:  navigation drawer (Appearance, Subtitles, Dialogue Boost, Shortcuts, About)
    right: the selected page

The window edits the shared AppSettings object directly and emits a signal after
each change, so the main window can apply it (theme, mpv options, filters) live.

Small reusable M3 widgets are at the top: Switch, Segmented, SubtitlePreview.
"""

from PySide6.QtCore import Qt, Signal, QSize, QRectF, QUrl
from PySide6.QtGui import QPainter, QColor, QPixmap, QDesktopServices, QFont, QPainterPath, QLinearGradient, QPen
from PySide6.QtWidgets import (
    QDialog, QWidget, QAbstractButton, QSlider, QLabel, QPushButton, QFrame, QComboBox,
    QHBoxLayout, QVBoxLayout, QButtonGroup, QStackedWidget, QScrollArea, QStyle,
)

import app_info
import icons
import theme
from audio_filters import PRESETS, DEFAULT_PRESET
from settings import SubtitleSettings


# ============================================================================
# Small helpers so the pages read like a description of the layout
# ============================================================================
def text(content, kind="bodyLarge", wrap=False):
    label = QLabel(content)
    label.setProperty("type", kind)
    label.setWordWrap(wrap)
    return label


def button(label, variant, icon_name=None, icon_role="primary"):
    b = QPushButton(label)
    b.setProperty("variant", variant)
    b.setCursor(Qt.PointingHandCursor)
    if icon_name:
        icons.bind(b, icon_name, icon_role)
        b.setIconSize(QSize(18, 18))
    return b


def card(*rows):
    """An M3 card holding rows, separated by thin dividers."""
    frame = QFrame(objectName="card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 8, 20, 8)
    layout.setSpacing(0)
    for i, row in enumerate(rows):
        if i:
            layout.addWidget(QFrame(objectName="divider"))
        layout.addWidget(row)
    return frame


class ListItem(QWidget):
    """An M3 list item: title + supporting text on the left, a control on the right,
    and optionally a full-width control below (for sliders).
    If the control is a Switch, clicking anywhere on the row flips it (big target, easy to hit)."""

    def __init__(self, title, supporting=None, trailing=None, below=None):
        super().__init__()
        self.switch = trailing if isinstance(trailing, Switch) else None
        if self.switch:
            self.setCursor(Qt.PointingHandCursor)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 12, 0, 12)
        outer.setSpacing(6)
        row = QHBoxLayout()
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(text(title, "bodyLarge"))
        if supporting:
            texts.addWidget(text(supporting, "bodyMedium", wrap=True))
        row.addLayout(texts, 1)
        if trailing is not None:
            row.addSpacing(12)
            row.addWidget(trailing, 0, Qt.AlignVCenter)
        outer.addLayout(row)
        if below is not None:
            outer.addWidget(below)

    def mouseReleaseEvent(self, event):
        if self.switch and event.button() == Qt.LeftButton:
            self.switch.click()
        super().mouseReleaseEvent(event)


def list_item(title, supporting=None, trailing=None, below=None):
    return ListItem(title, supporting, trailing, below)


class Slider(QSlider):
    """Settings slider. Click anywhere on it to jump there. The mouse wheel only moves it
    after you've clicked it, so scrolling the page never changes a setting by accident."""

    def __init__(self, minimum, maximum):
        super().__init__(Qt.Horizontal)
        self.setRange(minimum, maximum)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setValue(QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), int(event.position().x()), self.width()))
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()   # let the page scroll instead


CONTENT_WIDTH = 760   # pages never get wider than this, so lines stay easy to read


def centered(widget):
    """Center a widget horizontally and stop it from growing wider than CONTENT_WIDTH."""
    widget.setMaximumWidth(CONTENT_WIDTH)
    holder = QWidget(objectName="page")
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(widget)
    return holder


def page(title, intro=None, header_extra=None):
    """A page: a fixed header (title, intro, optional widget such as a preview) that stays
    visible, and scrollable content below it.
    Returns (page widget, layout to add the content to)."""
    outer = QWidget(objectName="page")
    column = QVBoxLayout(outer)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(0)

    header = QWidget(objectName="page")
    head = QVBoxLayout(header)
    head.setContentsMargins(32, 28, 32, 12)
    head.setSpacing(6)
    head.addWidget(text(title, "headlineSmall"))
    if intro:
        head.addWidget(text(intro, "bodyMedium", wrap=True))
    if header_extra is not None:
        head.addSpacing(8)
        head.addWidget(header_extra)
    column.addWidget(centered(header))

    content = QWidget(objectName="page")
    layout = QVBoxLayout(content)
    layout.setContentsMargins(32, 8, 32, 28)
    layout.setSpacing(16)
    scroll = QScrollArea()
    scroll.setWidget(centered(content))
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.verticalScrollBar().setSingleStep(24)
    column.addWidget(scroll, 1)
    return outer, layout


# ============================================================================
# M3 components
# ============================================================================
class Switch(QAbstractButton):
    """Material 3 switch: 52x32 track. On = primary track with a big thumb and a check."""

    def __init__(self, checked=False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(52, 32)

    def sizeHint(self):
        return QSize(52, 32)

    def paintEvent(self, _event):
        c = theme.C
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.isChecked():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c["primary"]))
            p.drawRoundedRect(QRectF(0, 0, 52, 32), 16, 16)
            p.setBrush(QColor(c["onPrimary"]))
            p.drawEllipse(QRectF(24, 4, 24, 24))
            p.drawPixmap(28, 8, icons.icon("check", "onPrimaryContainer", size=32).pixmap(16, 16))
        else:
            p.setPen(QPen(QColor(c["outline"]), 2))
            p.setBrush(QColor(c["surfaceContainerHighest"]))
            p.drawRoundedRect(QRectF(1, 1, 50, 30), 15, 15)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c["outline"]))
            p.drawEllipse(QRectF(8, 8, 16, 16))


class Segmented(QWidget):
    """Material 3 segmented button. The selected segment gets a check mark.
    value None = nothing selected (used for a "Custom" preset)."""
    changed = Signal(str)

    def __init__(self, options):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.buttons = {}
        for i, (key, label) in enumerate(options):
            b = QPushButton(label)
            b.setProperty("variant", "segment")
            b.setProperty("pos", "first" if i == 0 else "last" if i == len(options) - 1 else "mid")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIconSize(QSize(18, 18))
            b.clicked.connect(lambda _=False, k=key: self._clicked(k))
            layout.addWidget(b, 1)
            self.buttons[key] = b
        self.value = None

    def set_value(self, key):
        self.value = key
        for k, b in self.buttons.items():
            b.setChecked(k == key)
            if k == key:
                icons.bind(b, "check", "onSecondaryContainer")
            else:
                icons.unbind(b)

    def _clicked(self, key):
        self.set_value(key)
        self.changed.emit(key)


class SubtitlePreview(QWidget):
    """A small fake video frame that shows how the subtitles will look."""

    def __init__(self, sub):
        super().__init__()
        self.sub = sub
        self.setMinimumHeight(150)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, 16, 16)
        p.setClipPath(path)
        sky = QLinearGradient(0, 0, r.width(), r.height())
        sky.setColorAt(0, QColor("#2B3A67"))
        sky.setColorAt(0.6, QColor("#4E5D94"))
        sky.setColorAt(1, QColor("#C08497"))
        p.fillRect(r, sky)

        font = QFont(self.sub.font)
        font.setPixelSize(max(6, int(20 * self.sub.size / 100)))
        font.setBold(self.sub.bold)
        line = "This is how your subtitles will look."
        text_path = QPainterPath()
        text_path.addText(0, 0, font, line)
        box = text_path.boundingRect()
        # sub-pos: 100 = bottom, 0 = top
        usable = r.height() - box.height() - 24
        y = 12 + usable * self.sub.position / 100 + box.height()
        x = (r.width() - box.width()) / 2 - box.left()
        text_path.translate(x, y - box.bottom())
        if self.sub.style == "box":
            b = text_path.boundingRect().adjusted(-8, -5, 8, 5)
            p.fillRect(b, QColor(0, 0, 0, 176))
        else:
            p.strokePath(text_path, QPen(QColor("black"), max(2.0, font.pixelSize() / 7), Qt.SolidLine,
                                         Qt.RoundCap, Qt.RoundJoin))
        p.fillPath(text_path, QColor(self.sub.color))


# ============================================================================
class SettingsWindow(QDialog):
    theme_changed = Signal(str)
    boost_changed = Signal()
    boost_enabled_changed = Signal(bool)
    subtitles_changed = Signal()
    sub_delay_changed = Signal(float)

    PAGES = [("appearance", "Appearance", "palette"), ("subtitles", "Subtitles", "subtitles"),
             ("audio", "Dialogue Boost", "graphic_eq"), ("shortcuts", "Shortcuts", "keyboard"),
             ("about", "About", "info")]

    SUB_COLORS = [("#FFFFFF", "White"), ("#FFE45C", "Yellow"), ("#7FE7FF", "Cyan"), ("#9CFFA0", "Green")]
    SUB_FONTS = ["Roboto Flex", "Arial", "Segoe UI", "Verdana", "Tahoma", "Georgia"]

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.s = settings
        self.sub_delay = 0.0
        self._updating = False
        self.compact = None   # True = narrow window: the drawer shrinks to an icon rail
        self.setWindowTitle("Settings")
        self.setMinimumSize(560, 460)
        self.resize(self.s.settings_width, self.s.settings_height)   # remembered from last time

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- navigation drawer ----
        self.drawer = QWidget(objectName="drawer")
        nav = QVBoxLayout(self.drawer)
        nav.setContentsMargins(12, 20, 12, 16)
        nav.setSpacing(2)
        self.heading = text("Settings", "titleSmall")
        self.heading.setContentsMargins(16, 0, 0, 12)
        nav.addWidget(self.heading)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = {}
        self.stack = QStackedWidget()
        builders = {"appearance": self._appearance_page, "subtitles": self._subtitles_page,
                    "audio": self._audio_page, "shortcuts": self._shortcuts_page, "about": self._about_page}
        for key, label, icon_name in self.PAGES:
            b = QPushButton("   " + label)
            b.setProperty("variant", "nav")
            b.setToolTip(label)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIconSize(QSize(22, 22))
            icons.bind(b, icon_name, "onSurfaceVariant")
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self.nav_group.addButton(b)
            self.nav_buttons[key] = b
            nav.addWidget(b)
            self.stack.addWidget(builders[key]())
        nav.addStretch()
        self.footer = text("Changes are saved automatically.", "bodySmall", wrap=True)
        self.footer.setAlignment(Qt.AlignCenter)
        nav.addWidget(self.footer)
        self.version_label = text(f"Version {app_info.VERSION}", "bodySmall")
        nav.addWidget(self.version_label, 0, Qt.AlignHCenter)
        root.addWidget(self.drawer)
        root.addWidget(self.stack, 1)

        keys = [k for k, _, _ in self.PAGES]
        self.show_page(self.s.settings_page if self.s.settings_page in keys else "appearance")
        self._update_layout()
        theme.title_bar(self)   # before the first show, so Windows 10 draws it right away

    # ------------------------------------------------------------------ responsive layout
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.s.settings_width, self.s.settings_height = self.width(), self.height()
        self._update_layout()

    def _update_layout(self):
        """Wide window: drawer with labels. Narrow window: a slim rail with icons only
        (hover an icon to see its name), leaving more room for the settings."""
        compact = self.width() < 780
        if compact == self.compact:
            return
        self.compact = compact
        self.drawer.setFixedWidth(88 if compact else 250)
        self.heading.setVisible(not compact)
        self.footer.setVisible(not compact)
        self.version_label.setVisible(not compact)
        for key, label, _ in self.PAGES:
            b = self.nav_buttons[key]
            b.setText("" if compact else "   " + label)
            b.setProperty("rail", compact)
            b.style().unpolish(b)
            b.style().polish(b)

    # ------------------------------------------------------------------ public
    def show_page(self, key):
        keys = [k for k, _, _ in self.PAGES]
        self.stack.setCurrentIndex(keys.index(key))
        self.s.settings_page = key   # reopen here next time
        for k, b in self.nav_buttons.items():
            b.setChecked(k == key)
            icons.bind(b, dict((p[0], p[2]) for p in self.PAGES)[k],
                       "onSecondaryContainer" if k == key else "onSurfaceVariant", filled=(k == key))

    def set_boost_enabled(self, enabled):
        self.boost_switch.blockSignals(True)
        self.boost_switch.setChecked(enabled)
        self.boost_switch.blockSignals(False)
        self.boost_switch.update()

    def set_channel_info(self, channels):
        if channels >= 6:
            self.channel_label.setText(f"Now playing {channels}-channel audio: it is mixed down to stereo with "
                                       "the center (dialogue) channel boosted.")
        else:
            self.channel_label.setText(f"Now playing {channels}-channel audio: it's already stereo, "
                                       "so Center channel boost has no effect.")

    def sync_subtitles(self):
        """Refresh the subtitle controls from the settings (e.g. after a size hotkey)."""
        sub = self.s.subtitles
        self._updating = True
        self.sub_size.setValue(sub.size)
        self.sub_pos.setValue(sub.position)
        self.sub_override.setChecked(sub.override)
        self.sub_font.setCurrentText(sub.font)
        for color, b in self.swatches.items():
            b.setChecked(color == sub.color)
        self.sub_style.set_value(sub.style)
        self.sub_bold.setChecked(sub.bold)
        self.sub_override.update()
        self.sub_bold.update()
        self._updating = False
        self._show_sub_values()

    def reset_delay(self):
        self.sub_delay = 0.0
        self.delay_label.setText("0.0 s")

    # ------------------------------------------------------------------ pages
    def _appearance_page(self):
        scroll, layout = page("Appearance", "Choose how the app looks. Light is the default.")
        self.theme_picker = Segmented([("light", "Light"), ("dark", "Dark"), ("system", "System")])
        self.theme_picker.set_value(self.s.theme)
        self.theme_picker.changed.connect(self._on_theme)
        layout.addWidget(card(list_item("Theme", "System follows your Windows light/dark setting.",
                                        below=self.theme_picker)))
        layout.addStretch()
        return scroll

    def _subtitles_page(self):
        sub = self.s.subtitles
        # The preview sits in the fixed header, so it stays visible while you scroll and tweak.
        self.preview = SubtitlePreview(sub)
        self.preview.setFixedHeight(120)
        scroll, layout = page("Subtitles", "Changes apply right away to the video that is playing.",
                              header_extra=self.preview)

        # Size & position
        self.sub_size = Slider(30, 300)
        self.sub_size.setSingleStep(5)
        self.sub_size.setPageStep(10)
        self.sub_size_value = text("", "value")
        self.sub_size_quick = Segmented([("70", "Small"), ("100", "Normal"), ("140", "Large")])
        self.sub_size_quick.changed.connect(lambda key: self.sub_size.setValue(int(key)))
        size_box = QWidget()
        size_layout = QVBoxLayout(size_box)
        size_layout.setContentsMargins(0, 4, 0, 0)
        size_layout.setSpacing(8)
        size_layout.addWidget(self.sub_size_quick)
        size_layout.addWidget(self.sub_size)
        self.sub_pos = Slider(0, 100)
        self.sub_pos_value = text("", "value")
        self.sub_override = Switch(sub.override)
        layout.addWidget(text("SIZE AND POSITION", "overline"))
        layout.addWidget(card(
            list_item("Size", "Too big or too small? Pick a size, or drag for any size. Shortcut: Ctrl+[ and Ctrl+]",
                      self.sub_size_value, size_box),
            list_item("Position", "Move the subtitles up from the bottom edge.", self.sub_pos_value, self.sub_pos),
            list_item("Override subtitle file styles",
                      "Use these settings even when the subtitle file has its own fonts, sizes and colors. "
                      "Turn this on if subtitles fill the screen or look strange.", self.sub_override),
        ))

        # Look
        self.sub_font = QComboBox()
        self.sub_font.addItems(self.SUB_FONTS)
        self.sub_font.setMinimumWidth(180)
        swatch_row = QWidget()
        swatch_layout = QHBoxLayout(swatch_row)
        swatch_layout.setContentsMargins(0, 0, 0, 0)
        swatch_layout.setSpacing(10)
        self.swatches = {}
        for color, name in self.SUB_COLORS:
            b = QPushButton()
            b.setProperty("variant", "swatch")
            b.setCheckable(True)
            b.setToolTip(name)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background: {color}; }}")
            b.clicked.connect(lambda _=False, c=color: self._on_sub_color(c))
            swatch_layout.addWidget(b)
            self.swatches[color] = b
        self.sub_style = Segmented([("outline", "Outline"), ("box", "Dark box")])
        self.sub_style.setFixedWidth(240)
        self.sub_bold = Switch(sub.bold)
        layout.addWidget(text("LOOK", "overline"))
        layout.addWidget(card(
            list_item("Font", None, self.sub_font),
            list_item("Text color", None, swatch_row),
            list_item("Background", "A dark box is easier to read on bright scenes.", self.sub_style),
            list_item("Bold", None, self.sub_bold),
        ))

        # Timing (only for the current video)
        delay_box = QWidget()
        delay_layout = QHBoxLayout(delay_box)
        delay_layout.setContentsMargins(0, 0, 0, 0)
        minus = button("", "icon", "remove", "onSurfaceVariant")
        plus = button("", "icon", "add", "onSurfaceVariant")
        self.delay_label = text("0.0 s", "value")
        self.delay_label.setMinimumWidth(56)
        self.delay_label.setAlignment(Qt.AlignCenter)
        minus.clicked.connect(lambda: self._change_delay(-0.1))
        plus.clicked.connect(lambda: self._change_delay(0.1))
        for w in (minus, self.delay_label, plus):
            delay_layout.addWidget(w)
        layout.addWidget(text("TIMING", "overline"))
        layout.addWidget(card(list_item("Delay", "Subtitles too early or late? Applies to the current video only.",
                                        delay_box)))

        reset = button("Reset subtitle settings", "text", "restart_alt")
        reset.clicked.connect(self._reset_subtitles)
        layout.addWidget(reset, 0, Qt.AlignLeft)
        layout.addStretch()

        self.sub_size.valueChanged.connect(lambda v: self._on_sub("size", v))
        self.sub_pos.valueChanged.connect(lambda v: self._on_sub("position", v))
        self.sub_override.toggled.connect(lambda v: self._on_sub("override", v))
        self.sub_font.currentTextChanged.connect(lambda v: self._on_sub("font", v))
        self.sub_style.changed.connect(lambda v: self._on_sub("style", v))
        self.sub_bold.toggled.connect(lambda v: self._on_sub("bold", v))
        self.sync_subtitles()
        return scroll

    def _audio_page(self):
        scroll, layout = page("Dialogue Boost", "Makes voices clear and keeps music and explosions from "
                                                "getting too loud. The sound stays in stereo.")
        self.boost_switch = Switch(self.s.boost_enabled)
        self.boost_switch.toggled.connect(self.boost_enabled_changed.emit)
        layout.addWidget(card(list_item("Dialogue Boost", "Hotkey: D", self.boost_switch)))

        self.preset_picker = Segmented([(name, name) for name in PRESETS])
        layout.addWidget(text("PRESET", "overline"))
        layout.addWidget(self.preset_picker)
        self.custom_label = text("Custom settings. Pick a preset to go back.", "bodySmall")
        layout.addWidget(self.custom_label)
        self.preset_picker.changed.connect(self._on_preset)

        # (attribute, title, supporting, min, max, unit)
        specs = [
            ("compression", "Compression strength", "How much loud parts are turned down.", 0, 100, "%"),
            ("voice_boost", "Voice boost", "Extra clarity in the 1-4 kHz speech range.", 0, 12, "dB"),
            ("center_boost", "Center channel boost", "Louder dialogue channel (5.1 and 7.1 audio).", 0, 12, "dB"),
            ("gain", "Overall gain", "Volume after all the processing.", -12, 12, "dB"),
        ]
        self.boost_sliders = {}
        self.boost_values = {}
        rows = []
        for attr, title, supporting, lo, hi, unit in specs:
            slider = Slider(lo, hi)
            value = text("", "value")
            slider.valueChanged.connect(lambda v, a=attr, u=unit: self._on_boost_slider(a, v, u))
            self.boost_sliders[attr] = slider
            self.boost_values[attr] = value
            rows.append(list_item(title, supporting, value, slider))
        layout.addWidget(text("ADJUST", "overline"))
        layout.addWidget(card(*rows))
        self.channel_label = text("", "bodySmall", wrap=True)
        layout.addWidget(self.channel_label)
        self.set_channel_info(2)
        reset = button("Reset to default", "tonal", "restart_alt", "onSecondaryContainer")
        reset.clicked.connect(lambda: self._on_preset(DEFAULT_PRESET))
        layout.addWidget(reset, 0, Qt.AlignLeft)
        layout.addStretch()

        self._set_boost_sliders(self.s.boost)
        self._show_preset(self.s.preset)
        return scroll

    def _shortcuts_page(self):
        scroll, layout = page("Keyboard shortcuts")
        shortcuts = [("Space", "Play / pause"), ("← / →", "Back / forward 5 seconds"),
                     ("↑ / ↓", "Volume up / down"), ("F  or double-click", "Fullscreen"), ("Esc", "Leave fullscreen"),
                     ("M", "Mute"), ("D", "Dialogue Boost on / off"), ("Ctrl + [  /  Ctrl + ]", "Smaller / bigger subtitles"),
                     ("Ctrl + O", "Open a file"), ("Ctrl + P", "Settings")]
        rows = []
        for keys, action in shortcuts:
            chip = QLabel(keys)
            chip.setStyleSheet(f"background: {theme.C['surfaceContainerHigh']}; border-radius: 8px; padding: 6px 12px;"
                               "font-weight: 600;")
            chip.setProperty("type", "labelLarge")
            rows.append(list_item(action, None, chip))
        layout.addWidget(card(*rows))
        layout.addStretch()
        return scroll

    def _about_page(self):
        scroll, layout = page("About")
        top = QHBoxLayout()
        logo = QLabel()
        pixmap = QPixmap(app_info.LOGO_PATH)
        if not pixmap.isNull():
            ratio = self.devicePixelRatioF()
            pixmap = pixmap.scaled(int(88 * ratio), int(88 * ratio), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap.setDevicePixelRatio(ratio)
            logo.setPixmap(pixmap)
        top.addWidget(logo)
        top.addSpacing(12)
        names = QVBoxLayout()
        names.setSpacing(2)
        names.addStretch()
        names.addWidget(text(app_info.APP_NAME, "titleLarge"))
        names.addWidget(text(f"Version {app_info.VERSION}", "bodyMedium"))
        names.addStretch()
        top.addLayout(names, 1)
        layout.addLayout(top)
        layout.addWidget(text(app_info.DESCRIPTION, "bodyLarge", wrap=True))

        # Author card: avatar with initials, name, and link buttons
        avatar = QLabel("TR")
        avatar.setFixedSize(56, 56)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setObjectName("avatar")
        self.avatar = avatar
        self._style_avatar()
        who = QVBoxLayout()
        who.setSpacing(2)
        who.addWidget(text("BUILT BY", "overline"))
        who.addWidget(text(app_info.AUTHOR, "titleLarge"))
        who.addWidget(text("Developer · BSc in CSE", "bodyMedium"))
        head = QHBoxLayout()
        head.addWidget(avatar)
        head.addSpacing(8)
        head.addLayout(who, 1)
        links = QHBoxLayout()
        github = button("  GitHub", "outlined", "github", "onSurfaceVariant")
        github.setToolTip(app_info.GITHUB)
        github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(app_info.GITHUB)))
        insta = button("  Instagram", "outlined", "instagram", "onSurfaceVariant")
        insta.setToolTip(app_info.INSTAGRAM)
        insta.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(app_info.INSTAGRAM)))
        links.addWidget(github)
        links.addWidget(insta)
        links.addStretch()
        author_box = QWidget()
        author_layout = QVBoxLayout(author_box)
        author_layout.setContentsMargins(0, 16, 0, 16)
        author_layout.setSpacing(14)
        author_layout.addLayout(head)
        author_layout.addLayout(links)
        layout.addWidget(card(author_box))

        layout.addWidget(text("Powered by mpv, FFmpeg and Qt. Font: Roboto Flex. Icons: Material Symbols.",
                              "bodySmall", wrap=True))
        layout.addStretch()
        return scroll

    def _style_avatar(self):
        c = theme.C
        self.avatar.setStyleSheet(f"background: {c['primaryContainer']}; color: {c['onPrimaryContainer']};"
                                  "border-radius: 28px; font-size: 20px; font-weight: 600;")

    # ------------------------------------------------------------------ handlers
    def _on_theme(self, mode):
        self.s.theme = mode
        self.theme_changed.emit(mode)
        # a few widgets use inline colors; refresh them for the new theme
        self._style_avatar()
        for chip in self.findChildren(QLabel):
            if chip.property("type") == "labelLarge" and chip.styleSheet():
                chip.setStyleSheet(f"background: {theme.C['surfaceContainerHigh']}; border-radius: 8px;"
                                   "padding: 6px 12px; font-weight: 600;")

    def _show_sub_values(self):
        sub = self.s.subtitles
        self.sub_size_value.setText(f"{sub.size} %")
        quick = str(sub.size)
        self.sub_size_quick.set_value(quick if quick in self.sub_size_quick.buttons else None)
        self.sub_pos_value.setText("Bottom" if sub.position == 100 else f"{sub.position} %")
        self.preview.update()

    def _on_sub(self, attr, value):
        if self._updating:
            return
        setattr(self.s.subtitles, attr, value)
        self._show_sub_values()
        self.subtitles_changed.emit()

    def _on_sub_color(self, color):
        for c, b in self.swatches.items():
            b.setChecked(c == color)
        self._on_sub("color", color)

    def _reset_subtitles(self):
        self.s.subtitles = SubtitleSettings()
        self.preview.sub = self.s.subtitles
        self.sync_subtitles()
        self.subtitles_changed.emit()

    def _change_delay(self, step):
        self.sub_delay = round(self.sub_delay + step, 1)
        self.delay_label.setText(f"{self.sub_delay:+.1f} s" if self.sub_delay else "0.0 s")
        self.sub_delay_changed.emit(self.sub_delay)

    def _show_preset(self, name):
        self.preset_picker.set_value(name if name in PRESETS else None)
        self.custom_label.setVisible(name not in PRESETS)

    def _set_boost_sliders(self, boost):
        self._updating = True
        for attr, slider in self.boost_sliders.items():
            slider.setValue(int(round(getattr(boost, attr))))
        self._updating = False

    def _on_boost_slider(self, attr, value, unit):
        sign = "+" if unit == "dB" and value > 0 else ""
        self.boost_values[attr].setText(f"{sign}{value} {unit}")
        if self._updating:
            return
        setattr(self.s.boost, attr, value)
        self.s.preset = "Custom"
        self._show_preset("Custom")
        self.boost_changed.emit()

    def _on_preset(self, name):
        p = PRESETS[name]
        self.s.boost = type(p)(p.compression, p.voice_boost, p.center_boost, p.gain)   # a copy, not the preset itself
        self.s.preset = name
        self._set_boost_sliders(self.s.boost)
        self._show_preset(name)
        self.boost_changed.emit()
