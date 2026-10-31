"""
ui.py - the main window.

Layout (VLC-like, styled with Material 3):
    menu bar       Media  Playback  Audio  Subtitle  Tools  View  Help
    video          (or a welcome screen with the logo when nothing is playing)
    control bar    title of the video                              0:12 / 1:45:00
                   ===============o-------------------------------- (seek bar)
                   [>] [stop] [-10] [+10]   (Dialogue Boost) [tune] [cc] (1.0x)   [vol] ---- [full]

In fullscreen the control bar moves into a small floating window over the video,
with real Windows blur behind it, and hides itself when the mouse stops moving.
"""

import ctypes
import os
import sys

from PySide6.QtCore import Qt, QTimer, Signal, QEvent, QSize
from PySide6.QtGui import QAction, QActionGroup, QPixmap, QPainterPath, QRegion, QIcon, QKeySequence, QFont, QCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSlider, QLabel, QPushButton, QToolButton,
    QMenu, QFrame, QHBoxLayout, QVBoxLayout, QStackedWidget, QFileDialog, QMessageBox, QStyle,
)

import app_info
import icons
import theme
from player import Player
from settings import save_settings
from settings_window import SettingsWindow, text

VIDEO_EXTENSIONS = ["mp4", "mkv", "avi", "mov", "webm", "wmv", "flv", "m4v",
                    "mpg", "mpeg", "ts", "m2ts", "3gp", "ogv",
                    "mp3", "flac", "m4a", "wav", "ogg", "opus"]
SUBTITLE_EXTENSIONS = ["srt", "ass", "ssa", "vtt", "sub"]
SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

SEEK_STEP = 5           # seconds for the arrow keys
BUTTON_SEEK_STEP = 10   # seconds for the replay/forward buttons
VOLUME_STEP = 5         # percent
SUB_SIZE_STEP = 10      # percent for Ctrl+[ / Ctrl+]
HIDE_DELAY_MS = 2500


def format_time(seconds):
    """83.4 -> '1:23', 3723 -> '1:02:03'"""
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def path_key(path):
    """Normalize a path so the same file always gets the same resume key."""
    return os.path.normcase(os.path.abspath(path))


class VideoWidget(QWidget):
    """mpv needs a real Windows window handle (HWND) to draw into, so we ask Qt
    to give this widget its own native window."""

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_NativeWindow)
        self.setStyleSheet("background: black;")
        self.setMinimumSize(320, 180)


class ClickSlider(QSlider):
    """A slider that jumps straight to the clicked position (a normal QSlider
    only moves one page step towards the click)."""
    clicked = Signal(int)

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            value = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), int(event.position().x()), self.width())
            self.setValue(value)
            self.clicked.emit(value)
        super().mousePressEvent(event)


def icon_button(name, slot, tip, role="onSurfaceVariant", filled=False):
    """An M3 standard icon button (40 dp)."""
    b = QPushButton()
    b.setProperty("variant", "icon")
    b.setIconSize(QSize(24, 24))
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.NoFocus)   # keep keyboard focus on the window so Space/arrows always work
    icons.bind(b, name, role, filled)
    if slot:
        b.clicked.connect(slot)
    return b


class WelcomePage(QWidget):
    """Shown instead of the black video area when nothing is playing."""

    def __init__(self, open_clicked, settings_clicked):
        super().__init__(objectName="welcome")
        layout = QVBoxLayout(self)
        layout.addStretch()
        logo = QLabel(alignment=Qt.AlignCenter)
        pixmap = QPixmap(app_info.LOGO_PATH)
        if not pixmap.isNull():
            ratio = self.devicePixelRatioF()
            pixmap = pixmap.scaled(int(128 * ratio), int(128 * ratio), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap.setDevicePixelRatio(ratio)
            logo.setPixmap(pixmap)
        layout.addWidget(logo)
        layout.addSpacing(16)
        title = text(app_info.APP_NAME, "headlineMedium")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        hint = text("Drop a video here, or open one to start watching.", "bodyLarge")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: {theme.C['onSurfaceVariant']};")
        self.hint = hint
        layout.addWidget(hint)
        layout.addSpacing(24)

        open_button = QPushButton("  Open video")
        open_button.setProperty("variant", "filled")
        open_button.setIconSize(QSize(20, 20))
        open_button.setCursor(Qt.PointingHandCursor)
        open_button.setFocusPolicy(Qt.NoFocus)
        icons.bind(open_button, "folder_open", "onPrimary")
        open_button.clicked.connect(open_clicked)
        settings_button = QPushButton("  Settings")
        settings_button.setProperty("variant", "outlined")
        settings_button.setIconSize(QSize(20, 20))
        settings_button.setCursor(Qt.PointingHandCursor)
        settings_button.setFocusPolicy(Qt.NoFocus)
        icons.bind(settings_button, "settings", "primary")
        settings_button.clicked.connect(settings_clicked)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addStretch()
        row.addWidget(open_button)
        row.addWidget(settings_button)
        row.addStretch()
        layout.addLayout(row)
        layout.addSpacing(28)
        credit = text(f"by {app_info.AUTHOR}", "bodySmall")
        credit.setAlignment(Qt.AlignCenter)
        layout.addWidget(credit)
        layout.addStretch()

    def restyle(self):
        self.hint.setStyleSheet(f"color: {theme.C['onSurfaceVariant']};")


class OverlayWindow(QWidget):
    """A frameless, see-through window that floats over the fullscreen video and
    holds the control bar. Windows blurs the video behind it (glass effect)."""

    def __init__(self, main_window):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus)
        self.main_window = main_window
        self.setObjectName("overlay")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)   # keep keyboard focus on the main window
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.blur_enabled = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self.blur_enabled:
            self.blur_enabled = theme.enable_blur_behind(self)

    def resizeEvent(self, event):
        # Cut the window to a rounded rectangle, so the blur has rounded corners too.
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 28, 28)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def mouseMoveEvent(self, event):
        self.main_window.on_mouse_moved()


def repolish(widget):
    """Re-apply the stylesheet after a widget moved to another parent window."""
    for w in [widget] + widget.findChildren(QWidget):
        w.style().unpolish(w)
        w.style().polish(w)


# ============================================================================
class MainWindow(QMainWindow):

    # Qt key -> the same names mpv uses, so both input paths share one handler.
    QT_KEYS = {
        Qt.Key_Space: "SPACE", Qt.Key_Left: "LEFT", Qt.Key_Right: "RIGHT",
        Qt.Key_Up: "UP", Qt.Key_Down: "DOWN", Qt.Key_F: "f", Qt.Key_M: "m",
        Qt.Key_D: "d", Qt.Key_Escape: "ESC",
    }

    def __init__(self, app_settings):
        super().__init__()
        self.s = app_settings
        self.current_path = None
        self.resumed_from = 0
        self.settings_window = None
        self.was_maximized = False
        self._icon_state = {}   # last drawn state of play/mute/fullscreen/boost icons
        self.last_mouse_position = None
        self.cursor_hidden = False

        self.setWindowTitle(app_info.APP_NAME)
        self.setWindowIcon(QIcon(app_info.LOGO_PATH))
        self.resize(self.s.window_width, self.s.window_height)
        self.setMinimumSize(760, 480)
        self.setAcceptDrops(True)

        # --- video + mpv ---
        self.video = VideoWidget()
        self.player = Player(self.video)
        self.player.set_volume(self.s.volume)
        self.player.set_mute(self.s.muted)
        self.player.set_boost(self.s.boost_enabled, self.s.boost)
        self.player.set_subtitle_style(self.s.subtitles)
        self.player.file_loaded.connect(self._on_file_loaded)
        self.player.playback_error.connect(self._on_playback_error)
        self.player.key_pressed.connect(self.handle_key)

        # --- welcome page / video, stacked on top of each other ---
        self.stack = QStackedWidget()
        self.welcome = WelcomePage(self.open_dialog, lambda: self.show_settings("appearance"))
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.video)

        self.controls = self._build_controls()
        central = QWidget()
        self.central_layout = QVBoxLayout(central)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        self.central_layout.addWidget(self.stack, 1)
        self.central_layout.addWidget(self.controls)
        self.setCentralWidget(central)
        self._build_menus()

        self.overlay = OverlayWindow(self)

        # Poll position/duration 4 times a second. Simple and thread-safe.
        self.tick_timer = QTimer(self, interval=250, timeout=self._tick)
        self.tick_timer.start()
        # Hides the controls in fullscreen after the mouse stops moving.
        self.hide_timer = QTimer(self, singleShot=True, interval=HIDE_DELAY_MS, timeout=self._hide_controls)
        # Debounce for boost sliders: apply 150 ms after the last change.
        self.boost_timer = QTimer(self, singleShot=True, interval=150, timeout=self._apply_boost)

        # See mouse movement anywhere in the app (to show controls in fullscreen).
        QApplication.instance().installEventFilter(self)
        theme.title_bar(self)
        self._refresh_icons()

    # ------------------------------------------------------------------ building
    def _build_controls(self):
        panel = QFrame(objectName="controls")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(24, 12, 24, 14)
        outer.setSpacing(2)

        # Row 1: what is playing + time
        info = QHBoxLayout()
        self.title_label = text("Nothing playing", "titleMedium")
        self.subtitle_label = text("", "bodyMedium")
        info.addWidget(self.title_label)
        info.addSpacing(10)
        info.addWidget(self.subtitle_label)
        info.addStretch()
        self.time_label = text("0:00 / 0:00", "labelLarge")
        font = self.time_label.font()
        font.setFeature(QFont.Tag("tnum"), 1)   # digits all the same width, so the time doesn't wiggle
        self.time_label.setFont(font)
        info.addWidget(self.time_label)
        outer.addLayout(info)

        # Row 2: seek bar
        self.seek_slider = ClickSlider()
        self.seek_slider.setObjectName("seek")
        self.seek_slider.clicked.connect(self.player.seek_to)
        self.seek_slider.sliderMoved.connect(self._show_time)
        self.seek_slider.sliderReleased.connect(lambda: self.player.seek_to(self.seek_slider.value()))
        outer.addWidget(self.seek_slider)

        # Row 3: buttons
        row = QHBoxLayout()
        row.setSpacing(4)
        self.play_button = QPushButton()
        self.play_button.setProperty("variant", "fab")
        self.play_button.setIconSize(QSize(30, 30))
        self.play_button.setToolTip("Play / pause (Space)")
        self.play_button.setCursor(Qt.PointingHandCursor)
        self.play_button.setFocusPolicy(Qt.NoFocus)
        self.play_button.clicked.connect(self.play_pause)
        row.addWidget(self.play_button)
        row.addSpacing(8)
        row.addWidget(icon_button("stop", self.stop, "Stop"))
        row.addWidget(icon_button("replay_10", lambda: self.player.seek_relative(-BUTTON_SEEK_STEP),
                                  f"Back {BUTTON_SEEK_STEP} seconds"))
        row.addWidget(icon_button("forward_10", lambda: self.player.seek_relative(BUTTON_SEEK_STEP),
                                  f"Forward {BUTTON_SEEK_STEP} seconds"))
        row.addStretch()

        # Dialogue Boost filter chip
        self.boost_button = QPushButton(" Dialogue Boost")
        self.boost_button.setProperty("variant", "chip")
        self.boost_button.setCheckable(True)
        self.boost_button.setChecked(self.s.boost_enabled)
        self.boost_button.setToolTip("Dialogue Boost on/off (D)")
        self.boost_button.setCursor(Qt.PointingHandCursor)
        self.boost_button.setFocusPolicy(Qt.NoFocus)
        self.boost_button.setIconSize(QSize(18, 18))
        self.boost_button.clicked.connect(self.toggle_boost)
        row.addWidget(self.boost_button)
        row.addWidget(icon_button("tune", lambda: self.show_settings("audio"), "Dialogue Boost settings"))

        # Subtitles menu button
        self.sub_button = QToolButton()
        self.sub_button.setProperty("variant", "icon")
        self.sub_button.setIconSize(QSize(24, 24))
        self.sub_button.setToolTip("Subtitles")
        self.sub_button.setFocusPolicy(Qt.NoFocus)
        self.sub_button.setCursor(Qt.PointingHandCursor)
        self.sub_button.setPopupMode(QToolButton.InstantPopup)
        icons.bind(self.sub_button, "closed_caption")
        sub_menu = QMenu(self.sub_button)
        sub_menu.aboutToShow.connect(lambda: self._fill_subtitle_menu(sub_menu))
        self.sub_button.setMenu(sub_menu)
        row.addWidget(self.sub_button)

        # Speed chip with a menu
        self.speed_button = QToolButton()
        self.speed_button.setProperty("variant", "chip")
        self.speed_button.setText("1.0×")
        self.speed_button.setToolTip("Playback speed")
        self.speed_button.setFocusPolicy(Qt.NoFocus)
        self.speed_button.setCursor(Qt.PointingHandCursor)
        self.speed_button.setPopupMode(QToolButton.InstantPopup)
        self.speed_menu = self._speed_menu()   # shared with Playback > Speed, so both stay in sync
        self.speed_button.setMenu(self.speed_menu)
        row.addWidget(self.speed_button)
        row.addStretch()

        # Volume and fullscreen (right side, like VLC)
        self.mute_button = icon_button("volume_up", self.toggle_mute, "Mute (M)")
        row.addWidget(self.mute_button)
        self.volume_slider = ClickSlider()
        self.volume_slider.setRange(0, 150)
        self.volume_slider.setValue(self.s.volume)
        self.volume_slider.setFixedWidth(130)
        self.volume_slider.setToolTip("Volume (Up / Down, mouse wheel)")
        self.volume_slider.valueChanged.connect(self._on_volume)
        row.addWidget(self.volume_slider)
        self.volume_label = text(f"{self.s.volume}%", "labelMedium")
        self.volume_label.setMinimumWidth(40)
        row.addWidget(self.volume_label)
        self.fullscreen_button = icon_button("fullscreen", self.toggle_fullscreen, "Fullscreen (F)")
        row.addWidget(self.fullscreen_button)
        outer.addLayout(row)
        return panel

    def _speed_menu(self):
        menu = QMenu("Speed", self)
        icons.bind(menu.menuAction(), "speed")
        group = QActionGroup(menu)
        for speed in SPEEDS:
            action = menu.addAction(f"{speed}×")
            action.setCheckable(True)
            action.setChecked(speed == 1.0)
            action.triggered.connect(lambda _=False, s=speed: self.set_speed(s))
            group.addAction(action)
        return menu

    def _action(self, menu, label, slot, icon_name=None, shortcut=None):
        action = menu.addAction(label)
        action.triggered.connect(slot)
        if icon_name:
            icons.bind(action, icon_name)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        return action

    def _build_menus(self):
        bar = self.menuBar()

        media = bar.addMenu("&Media")
        self._action(media, "Open File...", self.open_dialog, "folder_open", "Ctrl+O")
        self._action(media, "Open Subtitle File...", self.open_subtitle_dialog, "subtitles")
        media.addSeparator()
        self._action(media, "Quit", self.close, None, "Ctrl+Q")

        playback = bar.addMenu("&Playback")
        self._action(playback, "Play / Pause\tSpace", self.play_pause, "play_arrow")
        self._action(playback, "Stop", self.stop, "stop")
        playback.addSeparator()
        self._action(playback, "Jump Forward\tRight", lambda: self.player.seek_relative(SEEK_STEP), "forward_10")
        self._action(playback, "Jump Backward\tLeft", lambda: self.player.seek_relative(-SEEK_STEP), "replay_10")
        playback.addMenu(self.speed_menu)

        audio = bar.addMenu("&Audio")
        tracks = audio.addMenu("Audio Track")
        icons.bind(tracks.menuAction(), "audiotrack")
        tracks.aboutToShow.connect(lambda: self._fill_audio_menu(tracks))
        audio.addSeparator()
        self.boost_action = QAction("Dialogue Boost\tD", self, checkable=True)
        self.boost_action.setChecked(self.s.boost_enabled)
        self.boost_action.triggered.connect(self.toggle_boost)
        audio.addAction(self.boost_action)
        self._action(audio, "Dialogue Boost Settings...", lambda: self.show_settings("audio"), "tune")
        audio.addSeparator()
        self._action(audio, "Increase Volume\tUp", lambda: self.change_volume(VOLUME_STEP), "volume_up")
        self._action(audio, "Decrease Volume\tDown", lambda: self.change_volume(-VOLUME_STEP), "volume_down")
        self._action(audio, "Mute\tM", self.toggle_mute, "volume_off")

        # Track menus are filled right before they open, so they always match the current file.
        subtitle = bar.addMenu("S&ubtitle")
        subtitle.aboutToShow.connect(lambda: self._fill_subtitle_menu(subtitle))
        # These shortcuts must exist even while the menu is closed, so they live on the window.
        self.sub_bigger = QAction("Bigger Subtitles", self, shortcut=QKeySequence("Ctrl+]"))
        self.sub_bigger.triggered.connect(lambda: self.change_subtitle_size(SUB_SIZE_STEP))
        self.sub_smaller = QAction("Smaller Subtitles", self, shortcut=QKeySequence("Ctrl+["))
        self.sub_smaller.triggered.connect(lambda: self.change_subtitle_size(-SUB_SIZE_STEP))
        self.addActions([self.sub_bigger, self.sub_smaller])

        tools = bar.addMenu("&Tools")
        self._action(tools, "Settings...", lambda: self.show_settings(), "settings", "Ctrl+P")

        view = bar.addMenu("&View")
        self._action(view, "Fullscreen\tF", self.toggle_fullscreen, "fullscreen")
        theme_menu = view.addMenu("Theme")
        icons.bind(theme_menu.menuAction(), "palette")
        group = QActionGroup(theme_menu)
        self.theme_actions = {}
        for mode, label, icon_name in (("light", "Light", "light_mode"), ("dark", "Dark", "dark_mode"),
                                       ("system", "System", "brightness_auto")):
            action = self._action(theme_menu, label, lambda _=False, m=mode: self.set_theme(m), icon_name)
            action.setCheckable(True)
            action.setChecked(self.s.theme == mode)
            group.addAction(action)
            self.theme_actions[mode] = action

        help_menu = bar.addMenu("&Help")
        self._action(help_menu, "Keyboard Shortcuts", lambda: self.show_settings("shortcuts"), "keyboard")
        self._action(help_menu, f"About {app_info.APP_NAME}", lambda: self.show_settings("about"), "info")

    def _fill_track_menu(self, menu, kind):
        group = QActionGroup(menu)
        tracks = self.player.tracks(kind)
        if kind == "sub":
            off = menu.addAction("Off")
            off.setCheckable(True)
            off.setChecked(not any(selected for _, _, selected in tracks))
            off.triggered.connect(lambda: self.player.select_sub("no"))
            group.addAction(off)
        if not tracks and kind == "audio":
            menu.addAction("(no audio tracks)").setEnabled(False)
        for track_id, label, selected in tracks:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(selected)
            if kind == "audio":
                action.triggered.connect(lambda _=False, i=track_id: self.player.select_audio(i))
            else:
                action.triggered.connect(lambda _=False, i=track_id: self.player.select_sub(i))
            group.addAction(action)

    def _fill_audio_menu(self, menu):
        menu.clear()   # the menu is refilled every time it opens; without this, tracks pile up
        self._fill_track_menu(menu, "audio")

    def _fill_subtitle_menu(self, menu):
        menu.clear()
        self._fill_track_menu(menu, "sub")
        menu.addSeparator()
        self._action(menu, "Load Subtitle File...", self.open_subtitle_dialog, "folder_open")
        menu.addSeparator()
        menu.addAction(self.sub_bigger)
        menu.addAction(self.sub_smaller)
        self._action(menu, "Subtitle Settings...", lambda: self.show_settings("subtitles"), "format_size")

    def _refresh_icons(self, force=False):
        """Swap icons that depend on state. Only redraws when the state changed."""
        playing = self.player.has_file and not self.player.paused
        state = {"play": playing, "mute": self.s.muted, "full": self.isFullScreen(), "boost": self.s.boost_enabled}
        if state == self._icon_state and not force:
            return
        self._icon_state = state
        icons.bind(self.play_button, "pause" if playing else "play_arrow", "onPrimaryContainer", filled=True)
        icons.bind(self.mute_button, "volume_off" if self.s.muted else "volume_up")
        icons.bind(self.fullscreen_button, "fullscreen_exit" if self.isFullScreen() else "fullscreen")
        if self.s.boost_enabled:
            icons.bind(self.boost_button, "check", "onSecondaryContainer")
        else:
            icons.bind(self.boost_button, "graphic_eq", "primary")

    # ------------------------------------------------------------------ theme
    def set_theme(self, mode):
        self.s.theme = mode
        theme.apply(QApplication.instance(), mode)
        self.welcome.restyle()
        for m, action in self.theme_actions.items():
            action.setChecked(m == mode)
        if self.settings_window:
            self.settings_window.theme_picker.set_value(mode)
        repolish(self.controls)
        save_settings(self.s)

    # ------------------------------------------------------------------ opening files
    def open_dialog(self):
        patterns = " ".join(f"*.{e}" for e in VIDEO_EXTENSIONS)
        path, _ = QFileDialog.getOpenFileName(
            self, "Open video", self.s.last_folder,
            f"Media files ({patterns});;All files (*)")
        if path:
            self.open_file(path)

    def open_subtitle_dialog(self):
        if not self.player.has_file:
            QMessageBox.information(self, "No video", "Open a video first, then load a subtitle file.")
            return
        start = os.path.dirname(self.current_path) if self.current_path else self.s.last_folder
        patterns = " ".join(f"*.{e}" for e in SUBTITLE_EXTENSIONS)
        path, _ = QFileDialog.getOpenFileName(self, "Load subtitles", start,
                                              f"Subtitles ({patterns});;All files (*)")
        if path:
            self.load_subtitle(path)

    def load_subtitle(self, path):
        try:
            self.player.add_subtitle(path)
            self.player.show_message(f"Subtitles: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Subtitle error", f"Could not load subtitle file:\n{path}\n\n{e}")

    def open_file(self, path):
        if not os.path.isfile(path):
            QMessageBox.warning(self, "File not found", f"This file does not exist:\n{path}")
            return
        self.remember_position()   # save where we were in the previous video

        self.current_path = path
        self.s.last_folder = os.path.dirname(path)
        self.resumed_from = self.s.positions.get(path_key(path), 0)
        self.stack.setCurrentWidget(self.video)
        self.player.load(path, self.resumed_from)
        if self.settings_window:
            self.settings_window.reset_delay()
        name = os.path.basename(path)
        self.title_label.setText(name if len(name) < 70 else name[:67] + "...")
        self.subtitle_label.setText("")
        self.setWindowTitle(f"{name} - {app_info.APP_NAME}")
        save_settings(self.s)

    def remember_position(self):
        """Store the current position for resume, or forget it if the video was (nearly) finished."""
        if not self.current_path or not self.player.has_file:
            return
        key = path_key(self.current_path)
        pos, dur = self.player.position, self.player.duration
        self.s.positions.pop(key, None)   # remove + re-add moves it to the "newest" end
        if dur > 0 and pos > 5 and dur - pos > 15 and not self.player.at_end:
            self.s.positions[key] = round(pos, 1)

    def _show_welcome(self):
        self.current_path = None
        self.stack.setCurrentWidget(self.welcome)
        self.title_label.setText("Nothing playing")
        self.subtitle_label.setText("")
        self.setWindowTitle(app_info.APP_NAME)

    # ------------------------------------------------------------------ player events
    def _on_file_loaded(self):
        if self.resumed_from:
            self.player.show_message(f"Resumed at {format_time(self.resumed_from)}")

    def _on_playback_error(self, message):
        name = os.path.basename(self.current_path) if self.current_path else "file"
        if self.current_path:
            self.s.positions.pop(path_key(self.current_path), None)
        self._show_welcome()
        QMessageBox.warning(self, "Cannot play file", f"{name}\n\n{message}")

    def _show_time(self, position):
        self.time_label.setText(f"{format_time(position)} / {format_time(self.player.duration)}")

    def _tick(self):
        """Runs 4x per second: update the seek bar, time and icons, and notice when the
        audio track's channel count changes (new file or another audio track), so the
        downmix step of Dialogue Boost can be added or removed."""
        channels = self.player.decoder_channels
        if channels and channels != self.player.channels:
            self.player.update_channels(channels)
            if self.settings_window:
                self.settings_window.set_channel_info(channels)
        if channels:
            self.subtitle_label.setText({1: "Mono", 2: "Stereo", 6: "5.1 surround", 8: "7.1 surround"}
                                        .get(channels, f"{channels} channels"))

        dur = self.player.duration
        if self.seek_slider.maximum() != int(dur):
            self.seek_slider.setRange(0, int(dur))
        if not self.seek_slider.isSliderDown():   # don't fight the user while they drag
            pos = self.player.position
            self.seek_slider.setValue(int(pos))
            self._show_time(pos)
        self._refresh_icons()

    # ------------------------------------------------------------------ actions
    def play_pause(self):
        if self.player.has_file:
            self.player.toggle_pause()
        else:
            self.open_dialog()

    def stop(self):
        self.remember_position()
        self.player.stop()
        self._show_welcome()

    def set_speed(self, speed):
        self.player.set_speed(speed)
        self.speed_button.setText(f"{speed}×")

    def toggle_mute(self):
        self.s.muted = not self.s.muted
        self.player.set_mute(self.s.muted)
        self.player.show_message("Muted" if self.s.muted else "Unmuted")
        self._refresh_icons()

    def change_volume(self, delta):
        self.volume_slider.setValue(self.volume_slider.value() + delta)   # triggers _on_volume
        self.player.show_message(f"Volume {self.volume_slider.value()}%")

    def _on_volume(self, value):
        self.s.volume = value
        self.player.set_volume(value)
        self.volume_label.setText(f"{value}%")

    def change_subtitle_size(self, delta):
        sub = self.s.subtitles
        sub.size = max(30, min(300, sub.size + delta))
        self.player.set_subtitle_style(sub)
        self.player.show_message(f"Subtitle size {sub.size}%")
        if self.settings_window:
            self.settings_window.sync_subtitles()

    def toggle_boost(self):
        self.set_boost_enabled(not self.s.boost_enabled)

    def set_boost_enabled(self, enabled):
        self.s.boost_enabled = enabled
        # Keep the chip, menu item and switch in sync.
        self.boost_button.setChecked(enabled)
        self.boost_action.setChecked(enabled)
        if self.settings_window:
            self.settings_window.set_boost_enabled(enabled)
        self._apply_boost()
        self._refresh_icons()
        self.player.show_message(f"Dialogue Boost: {'ON' if enabled else 'OFF'}")

    def show_settings(self, page_name=None):
        if self.settings_window is None:
            w = SettingsWindow(self, self.s)
            w.theme_changed.connect(self.set_theme)
            w.boost_changed.connect(self.boost_timer.start)      # debounced
            w.boost_enabled_changed.connect(self.set_boost_enabled)
            w.subtitles_changed.connect(lambda: self.player.set_subtitle_style(self.s.subtitles))
            w.sub_delay_changed.connect(self.player.set_subtitle_delay)
            w.set_channel_info(self.player.channels)
            self.settings_window = w
        if page_name:
            self.settings_window.show_page(page_name)
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _apply_boost(self):
        self.player.set_boost(self.s.boost_enabled, self.s.boost)

    # ------------------------------------------------------------------ fullscreen
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.was_maximized = self.isMaximized()
            self.menuBar().hide()
            self.showFullScreen()
            # Move the control bar into the floating glass window.
            self.overlay.layout.addWidget(self.controls)
            repolish(self.controls)
            self._place_overlay()
            self.on_mouse_moved()
        self._refresh_icons()

    def exit_fullscreen(self):
        if not self.isFullScreen():
            return
        self.overlay.hide()
        self.central_layout.addWidget(self.controls)   # move the bar back under the video
        repolish(self.controls)
        self.controls.show()
        self.menuBar().show()
        if self.was_maximized:
            self.showMaximized()
        else:
            self.showNormal()
        self._refresh_icons()

    def _place_overlay(self):
        screen = self.screen().geometry()
        width = min(1200, screen.width() - 96)
        height = self.controls.sizeHint().height()
        self.overlay.setGeometry(screen.x() + (screen.width() - width) // 2,
                                 screen.y() + screen.height() - height - 32, width, height)

    def _hide_controls(self):
        """The mouse has been still for a while: hide the fullscreen controls and
        the cursor (only over the video, never over buttons or menus)."""
        if self.isFullScreen():
            self.overlay.hide()
        if self.player.has_file and self.isActiveWindow() and not self.overlay.underMouse() and \
                self.video.rect().contains(self.video.mapFromGlobal(QCursor.pos())):
            self._set_cursor_hidden(True)

    def _set_cursor_hidden(self, hidden):
        """Hide/show the mouse pointer. Over the video the pointer belongs to mpv's own
        window, so Qt's setCursor() can't hide it; Windows' ShowCursor() can.
        ShowCursor keeps a counter, so we only call it when the state really changes."""
        if hidden == self.cursor_hidden:
            return
        self.cursor_hidden = hidden
        if sys.platform == "win32":
            ctypes.windll.user32.ShowCursor(not hidden)

    def on_mouse_moved(self):
        # Windows also sends "mouse moved" when a window appears or disappears under a
        # still mouse (e.g. when we hide the controls). Those fake moves would keep the
        # cursor visible forever, so only react when the position really changed.
        position = QCursor.pos()
        if position == self.last_mouse_position:
            return
        self.last_mouse_position = position
        self._set_cursor_hidden(False)
        if self.isFullScreen() and not self.overlay.isVisible():
            self._place_overlay()
            self.overlay.show()
        self.hide_timer.start()   # restart the countdown

    # ------------------------------------------------------------------ input
    def handle_key(self, key):
        """One place for all shortcuts. `key` uses mpv's key names."""
        if key == "SPACE":
            self.play_pause()
        elif key == "LEFT":
            self.player.seek_relative(-SEEK_STEP)
        elif key == "RIGHT":
            self.player.seek_relative(SEEK_STEP)
        elif key in ("UP", "WHEEL_UP"):
            self.change_volume(VOLUME_STEP)
        elif key in ("DOWN", "WHEEL_DOWN"):
            self.change_volume(-VOLUME_STEP)
        elif key in ("f", "F", "MBTN_LEFT_DBL"):
            self.toggle_fullscreen()
        elif key in ("m", "M"):
            self.toggle_mute()
        elif key in ("d", "D"):
            self.toggle_boost()
        elif key == "ESC":
            self.exit_fullscreen()
        elif key == "MOUSE_MOVE":
            self.on_mouse_moved()

    def keyPressEvent(self, event):
        key = self.QT_KEYS.get(event.key())
        if key and not event.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            self.handle_key(key)
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            self.on_mouse_moved()
        elif event.type() == QEvent.ApplicationDeactivate:
            self._set_cursor_hidden(False)   # never leave the pointer hidden when switching apps
            self._show_menu_underlines(False)
        elif event.type() in (QEvent.KeyPress, QEvent.KeyRelease) and event.key() == Qt.Key_Alt:
            # Like other Windows apps: menu shortcut letters are underlined only while Alt is down.
            self._show_menu_underlines(event.type() == QEvent.KeyPress)
        return False   # never swallow the event

    def _show_menu_underlines(self, show):
        if theme.AppStyle.show_shortcut_underlines != show:
            theme.AppStyle.show_shortcut_underlines = show
            self.menuBar().update()

    # Drag and drop: open videos, load subtitle files as subtitles.
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths:
            return
        path = paths[0]
        if path.lower().rsplit(".", 1)[-1] in SUBTITLE_EXTENSIONS and self.player.has_file:
            self.load_subtitle(path)
        else:
            self.open_file(path)

    # ------------------------------------------------------------------ closing
    def closeEvent(self, event):
        self.tick_timer.stop()   # mpv is shut down below; stop polling it
        self.hide_timer.stop()
        self._set_cursor_hidden(False)
        self.remember_position()
        if not self.isFullScreen() and not self.isMaximized():
            self.s.window_width = self.width()
            self.s.window_height = self.height()
        save_settings(self.s)
        self.overlay.close()
        if self.settings_window:
            self.settings_window.close()
        self.player.shutdown()
        super().closeEvent(event)
