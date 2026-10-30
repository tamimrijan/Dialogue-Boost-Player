"""
audio_filters.py - builds the "Dialogue Boost" audio filter chain for mpv.

mpv can run any ffmpeg audio filter through its "af" (audio filter) property.
We build ONE ffmpeg filter graph string and hand it to mpv like this:

    af = "lavfi=[pan=...,equalizer=...,acompressor=...,dynaudnorm=...,volume=...,alimiter=...]"

The audio flows through the filters from left to right:

    decoded audio (2 or 5.1 or 7.1 channels)
      -> 0. aformat      : convert to floating point, so nothing clips inside the chain
      -> 1. pan         : surround to stereo, with the center (dialogue) channel louder
      -> 2. equalizer    : gentle "presence" bump around 1-4 kHz where voices live
      -> 3. acompressor  : turns down loud parts (music, explosions)
      -> 4. dynaudnorm   : slowly raises quiet scenes, so the overall level stays even
      -> 5. volume       : the user's "overall gain" slider
      -> 6. alimiter     : hard safety ceiling, so nothing ever clips
      -> stereo output to your speakers

This file has no Qt or mpv code in it, so you can test it on its own:
    python audio_filters.py
"""

from dataclasses import dataclass, asdict


@dataclass
class BoostSettings:
    """The four slider values from the settings panel."""
    compression: int = 55      # 0..100 (%), how hard the compressor works
    voice_boost: float = 4.0   # 0..12 dB, EQ bump in the voice range
    center_boost: float = 6.0  # 0..12 dB, extra level for the center channel (5.1 / 7.1 only)
    gain: float = 0.0          # -12..+12 dB, overall volume after processing


# Presets. "Normal" is the default and is what "Reset to default" goes back to.
PRESETS = {
    "Light":      BoostSettings(compression=30, voice_boost=2.0, center_boost=3.0, gain=0.0),
    "Normal":     BoostSettings(compression=55, voice_boost=4.0, center_boost=6.0, gain=0.0),
    "Night mode": BoostSettings(compression=90, voice_boost=5.0, center_boost=8.0, gain=0.0),
}
DEFAULT_PRESET = "Normal"


def db_to_linear(db):
    """Convert decibels to a plain multiplier. +6 dB is about x2, -6 dB is about x0.5."""
    return 10 ** (db / 20)


# ---------------------------------------------------------------------------
# Step 1: surround -> stereo downmix with the center channel boosted
# ---------------------------------------------------------------------------
def build_pan(channels, center_boost_db):
    """
    Movies mix almost all dialogue into the CENTER channel of a 5.1 / 7.1 track.
    A normal downmix adds the center at -3 dB (x0.707) to left and right.
    We add it louder, so voices stand out over the music and effects.

    We use channel NUMBERS (c0, c1, ...) instead of names (FL, FR, ...), because
    5.1 files label their rear channels either BL/BR or SL/SR. The order is the
    same in both: c0=FL c1=FR c2=FC(center) c3=LFE(bass) c4.. = surround L/R pairs.

    Returns None when no downmix is needed (mono or stereo file).
    """
    if channels < 6:
        return None

    center = 0.707 * db_to_linear(center_boost_db)
    front = 1.0
    surround = 0.707
    lfe = 0.5   # keep some of the bass channel; your subwoofer gets it from the stereo signal

    left = [f"{front}*c0", f"{center:.3f}*c2", f"{lfe}*c3"]
    right = [f"{front}*c1", f"{center:.3f}*c2", f"{lfe}*c3"]
    # Surround channels come in pairs: c4/c5 (and c6/c7 for 7.1). Even = left, odd = right.
    for ch in range(4, channels):
        if ch % 2 == 0:
            left.append(f"{surround}*c{ch}")
        else:
            right.append(f"{surround}*c{ch}")

    # "pan=stereo|c0=...|c1=..." means: make a stereo output, and output channel
    # c0 (left) / c1 (right) is the sum of these input channels with these gains.
    return f"pan=stereo|c0={'+'.join(left)}|c1={'+'.join(right)}"


# ---------------------------------------------------------------------------
# Step 2: voice EQ
# ---------------------------------------------------------------------------
def build_voice_eq(voice_boost_db):
    """
    A peaking EQ centered at 2 kHz with a width of 2 octaves (so about 1 kHz
    to 4 kHz). That is the range that makes speech clear and understandable.
    """
    if voice_boost_db <= 0:
        return None
    return f"equalizer=f=2000:t=o:w=2:g={voice_boost_db:.1f}"


# ---------------------------------------------------------------------------
# Step 3: compressor
# ---------------------------------------------------------------------------
def build_compressor(strength):
    """
    A compressor watches the level. When the sound goes above the THRESHOLD,
    it is turned down by the RATIO (ratio 4 means: 4 dB over the threshold
    comes out as only 1 dB over). Then MAKEUP gain lifts everything back up,
    so quiet parts end up louder than before and loud parts quieter.

    One "strength" slider (0-100) controls all of these together:
        strength 0   -> no compressor
        strength 50  -> threshold -24 dB, ratio about 5.8:1
        strength 100 -> threshold -36 dB, ratio 10:1   (Night mode territory)
    """
    if strength <= 0:
        return None
    s = strength / 100
    threshold_db = -12 - 24 * s
    ratio = 1.5 + 8.5 * s
    # Makeup gain: give back about half of the gain the compressor takes away.
    makeup_db = min(-threshold_db * (1 - 1 / ratio) * 0.5, 18)

    # acompressor wants threshold and makeup as plain multipliers, not dB.
    return (
        "acompressor="
        f"threshold={db_to_linear(threshold_db):.5f}:"
        f"ratio={ratio:.2f}:"
        "attack=10:"          # ms - react fast to a sudden explosion
        "release=200:"        # ms - let go fairly quickly so it doesn't "pump"
        f"makeup={db_to_linear(makeup_db):.3f}"
    )


# ---------------------------------------------------------------------------
# Step 4: dynamic normalizer
# ---------------------------------------------------------------------------
def build_normalizer(strength):
    """
    dynaudnorm cuts the audio into short frames (f = frame length in ms) and
    computes a gain for each frame, smoothed over g frames (must be an odd number).
    A smaller g reacts faster (stronger leveling), a larger g is gentler.
    m = maximum gain it is allowed to add to quiet parts.

    We keep frames short (75 ms) so the delay it adds stays small.
    """
    s = strength / 100
    g = int(31 - 22 * s)     # 31 (gentle) .. 9 (strong)
    if g % 2 == 0:
        g += 1
    max_gain = 5 + 7 * s     # 5x .. 12x
    return f"dynaudnorm=f=75:g={g}:p=0.9:m={max_gain:.1f}"


# ---------------------------------------------------------------------------
# Step 6: limiter
# ---------------------------------------------------------------------------
def build_limiter():
    """
    The last safety net. Nothing can go above 'limit' (0.95 = about -0.4 dB).
    level=0 turns off alimiter's auto-level, otherwise it would make everything louder.
    """
    return "alimiter=limit=0.95:attack=5:release=50:level=0"


# ---------------------------------------------------------------------------
# Put it all together
# ---------------------------------------------------------------------------
def build_filter_chain(settings, channels):
    """
    Returns the full string for mpv's "af" property.

    settings: a BoostSettings
    channels: how many channels the file's audio track has (2 for stereo, 6 for 5.1, ...)
    """
    filters = [
        # Step 0: work in 32-bit float. Files like FLAC/WAV decode to integer
        # samples, and integer math hard-clips as soon as the pan or EQ adds
        # level. Float has huge headroom; the limiter at the end tames the peaks.
        "aformat=sample_fmts=fltp",
        build_pan(channels, settings.center_boost),
        build_voice_eq(settings.voice_boost),
        build_compressor(settings.compression),
        build_normalizer(settings.compression),
        f"volume={settings.gain:.1f}dB" if settings.gain != 0 else None,
        build_limiter(),
    ]
    # Drop the steps that were turned off (None) and join with commas.
    # Commas inside [...] chain ffmpeg filters one after another.
    graph = ",".join(f for f in filters if f)
    return f"lavfi=[{graph}]"


def settings_from_dict(data):
    """Make a BoostSettings from a dict (e.g. loaded from JSON), ignoring unknown keys."""
    default = BoostSettings()
    values = asdict(default)
    for key in values:
        if key in data:
            values[key] = type(values[key])(data[key])
    return BoostSettings(**values)


if __name__ == "__main__":
    # Quick self-test: print the chains so you can read them.
    for name, preset in PRESETS.items():
        print(f"--- {name} (stereo file) ---")
        print(build_filter_chain(preset, 2))
        print(f"--- {name} (5.1 file) ---")
        print(build_filter_chain(preset, 6))
        print()
