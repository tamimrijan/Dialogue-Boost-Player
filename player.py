"""
player.py - a small wrapper around libmpv (through the python-mpv package).

The UI never talks to mpv directly; it calls methods on Player. That keeps all
the mpv-specific details (property names, commands, threads) in one place.

About threads: mpv runs its own background thread and calls our callbacks
(events, key presses) FROM THAT THREAD. Qt widgets may only be touched from the
main thread. So in every mpv callback we only emit a Qt Signal. Qt notices the
signal came from another thread and delivers it safely on the main thread.
"""

from PySide6.QtCore import QObject, Signal

import mpv   # main.py makes sure the libmpv DLL can be found before this import

from app_info import resource_path
from audio_filters import build_filter_chain

# A few mpv error codes, so we can show a helpful message instead of a number.
MPV_ERRORS = {
    -13: "The file could not be loaded (it may be damaged or not a media file).",
    -16: "There is nothing playable in this file.",
    -17: "This file format is not supported.",
}


class Player(QObject):
    # Signals the UI connects to. All of them arrive on the Qt main thread.
    file_loaded = Signal()
    playback_error = Signal(str)
    key_pressed = Signal(str)         # a key or mouse button pressed on the video area

    # mpv key names we want to hear about when the video window has focus.
    # (When the Qt window has focus, Qt shortcuts handle the keys instead.)
    WATCHED_KEYS = ["SPACE", "LEFT", "RIGHT", "UP", "DOWN", "f", "F", "m", "M",
                    "d", "D", "ESC", "MBTN_LEFT", "MBTN_LEFT_DBL", "MOUSE_MOVE",
                    "WHEEL_UP", "WHEEL_DOWN"]

    def __init__(self, video_widget):
        super().__init__()

        # "wid" tells mpv to draw the video inside our Qt widget instead of
        # opening its own window.
        self.mpv = mpv.MPV(
            wid=str(int(video_widget.winId())),
            input_default_bindings=False,   # we decide what every key does
            input_vo_keyboard=True,         # but still pass keys from the video area to us
            osc=False,                      # no built-in mpv on-screen controls
            keep_open="yes",                # stay on the last frame at the end instead of closing
            idle=True,                      # stay alive with no file loaded
            audio_channels="stereo",        # ALWAYS output stereo (never mono, never 5.1)
            volume_max=150,
            hwdec="auto-safe",              # use the GPU to decode video when it is safe
            cursor_autohide=1500,           # hide the mouse over the video after 1.5 s
            sub_fonts_dir=resource_path("fonts"),   # lets subtitles use the bundled Roboto Flex
            log_handler=self._on_log,
            loglevel="warn",
        )
        try:
            # Let Qt handle drag-and-drop (so we can resume position etc.).
            self.mpv["drag-and-drop"] = "no"
        except Exception:
            pass   # older mpv builds don't have this option

        self.boost_enabled = True
        self.boost_settings = None
        self.channels = 2
        self._last_af = None

        self.mpv.register_event_callback(self._on_event)
        for key in self.WATCHED_KEYS:
            # Bind each key to a small function that just forwards the key name.
            self.mpv.register_key_binding(key, self._make_key_handler(key))

    # ---------------------------------------------------------------- callbacks
    # These run on mpv's thread: only emit signals here.

    def _make_key_handler(self, key):
        def handler(state, name, char, *_):
            # state starts with 'd' (down) or 'p' (press). Ignore 'u' (key up).
            if state and state[0] in ("d", "p"):
                self.key_pressed.emit(key)
        return handler

    def _on_event(self, event):
        eid = event.event_id.value
        if eid == mpv.MpvEventID.FILE_LOADED:
            self.file_loaded.emit()
        elif eid == mpv.MpvEventID.END_FILE:
            data = event.data
            if data.reason == mpv.MpvEventEndFile.ERROR:
                message = MPV_ERRORS.get(data.error, f"Playback failed (mpv error {data.error}).")
                self.playback_error.emit(message)

    def _on_log(self, level, component, message):
        print(f"[mpv {level}] {component}: {message.strip()}")

    # ---------------------------------------------------------------- playback

    def load(self, path, start_at=0):
        # "start" is read when the file opens, so the video begins at the resume point.
        self.mpv["start"] = str(start_at) if start_at > 0 else "none"
        # We don't know the new file's channel count yet, so start with the
        # stereo version of the chain. The UI timer upgrades it once mpv knows.
        self.update_channels(2)
        self.set_subtitle_delay(0)   # a delay fixed for one video is wrong for the next
        self.mpv.play(path)
        self.mpv.pause = False

    def stop(self):
        """Unload the file. mpv goes back to idle (black, nothing playing)."""
        self.mpv.command("stop")

    def toggle_pause(self):
        self.mpv.pause = not self.mpv.pause

    def seek_relative(self, seconds):
        try:
            self.mpv.seek(seconds, reference="relative")
        except Exception:
            pass   # seeking with no file loaded raises an error; just ignore it

    def seek_to(self, seconds):
        try:
            self.mpv.seek(seconds, reference="absolute")
        except Exception:
            pass

    # Properties read by the UI timer. mpv returns None when nothing is loaded.
    @property
    def position(self):
        return self.mpv.time_pos or 0.0

    @property
    def duration(self):
        return self.mpv.duration or 0.0

    @property
    def paused(self):
        return bool(self.mpv.pause)

    @property
    def has_file(self):
        return self.mpv.path is not None

    @property
    def at_end(self):
        return bool(self.mpv.eof_reached)

    @property
    def decoder_channels(self):
        """Channels of the playing audio track as it comes out of the decoder
        (2 = stereo, 6 = 5.1, 8 = 7.1), or None when no audio is playing."""
        params = self.mpv.audio_params
        return params.get("channel-count") if params else None

    def set_volume(self, value):
        self.mpv.volume = value

    def set_mute(self, muted):
        self.mpv.mute = muted

    def set_speed(self, speed):
        self.mpv.speed = speed

    def show_message(self, text):
        """Show a short text on top of the video (mpv's OSD)."""
        try:
            self.mpv.show_text(text, 1500)
        except Exception:
            pass

    # ---------------------------------------------------------------- tracks

    def tracks(self, kind):
        """Return a list of (id, label, selected) for 'audio' or 'sub' tracks."""
        result = []
        for t in self.mpv.track_list or []:
            if t.get("type") != kind:
                continue
            parts = [f"#{t['id']}"]
            if t.get("lang"):
                parts.append(t["lang"])
            if t.get("title"):
                parts.append(t["title"])
            if kind == "audio" and t.get("demux-channel-count"):
                parts.append(f"({t['demux-channel-count']} ch)")
            if t.get("external"):
                parts.append("[external]")
            result.append((t["id"], " ".join(parts), bool(t.get("selected"))))
        return result

    def select_audio(self, track_id):
        self.mpv.aid = track_id

    def select_sub(self, track_id):
        # track_id "no" turns subtitles off
        self.mpv.sid = track_id

    def add_subtitle(self, path):
        self.mpv.sub_add(path)

    def set_subtitle_style(self, sub):
        """Apply SubtitleSettings live. These are mpv options, so they work while playing."""
        m = self.mpv
        m["sub-scale"] = sub.size / 100              # 1.0 = normal size
        m["sub-pos"] = sub.position                  # 100 = bottom of the screen
        # "scale" = keep the file's own styles but still let sub-scale resize them.
        # "force" = replace the file's fonts, sizes and colors with ours.
        m["sub-ass-override"] = "force" if sub.override else "scale"
        m["sub-font"] = sub.font
        m["sub-color"] = sub.color
        m["sub-bold"] = sub.bold
        if sub.style == "box":
            m["sub-border-style"] = "opaque-box"     # each line sits on a box...
            m["sub-outline-color"] = "#B0000000"     # ...that is black at ~70% (#AARRGGBB)
            m["sub-outline-size"] = 4.0              # box padding
            m["sub-shadow-offset"] = 0.0
        else:
            m["sub-border-style"] = "outline-and-shadow"
            m["sub-outline-color"] = "#FF000000"
            m["sub-outline-size"] = 2.2
            m["sub-shadow-offset"] = 1.0

    def set_subtitle_delay(self, seconds):
        self.mpv["sub-delay"] = seconds

    # ---------------------------------------------------------------- dialogue boost

    def set_boost(self, enabled, settings):
        """Turn Dialogue Boost on/off or change its settings. Works while playing."""
        self.boost_enabled = enabled
        self.boost_settings = settings
        self._apply_audio_filters()

    def update_channels(self, channels):
        """Called when the audio track changes (new file or new audio track)."""
        if channels != self.channels:
            self.channels = channels
            self._apply_audio_filters()

    def _apply_audio_filters(self):
        if self.boost_enabled and self.boost_settings is not None:
            af = build_filter_chain(self.boost_settings, self.channels)
        else:
            af = ""   # no filters: mpv does a normal stereo downmix by itself
        if af == self._last_af:
            return
        try:
            # Setting "af" rebuilds the audio filters on the fly. The video keeps playing.
            self.mpv.af = af
            self._last_af = af
            print(f"Audio filters ({self.channels} ch): {af or '(none)'}")
        except Exception as e:
            print(f"Could not set audio filters: {e}")

    # ---------------------------------------------------------------- cleanup

    def shutdown(self):
        try:
            self.mpv.terminate()
        except Exception:
            pass
