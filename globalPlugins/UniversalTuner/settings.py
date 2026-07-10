# -*- coding: utf-8 -*-
"""
NVDA config persistence for Universal Tuner. The v1.4.26p version reset
volume/tone-length/A4/sample-rate/gap to hardcoded defaults every time
NVDA restarted - this was one of the concrete usability gaps found while
reviewing the old code. Registers a config spec under config.conf so
these (plus the new live-tuning options) survive restarts, same pattern
NVDA add-ons conventionally use.
"""
try:
    import config
    from logHandler import log
    _HAVE_NVDA = True
except Exception:  # pragma: no cover - only importable inside NVDA
    _HAVE_NVDA = False
    import logging
    log = logging.getLogger("UniversalTuner.settings")

CONFIG_SECTION = "UniversalTuner"

CONFSPEC = {
    "a4": "float(min=400.0, max=480.0, default=440.0)",
    "volume": "float(min=0.01, max=1.0, default=0.22)",
    # Default raised from 2.0 to 5.0 in v2.5.1 per user request, after
    # testing showed 5.0 felt like the right tone length in practice -
    # "Tone length" is now also exposed as its own field in Advanced
    # settings (previously only adjustable via +/- in the main window).
    "duration": "float(min=0.2, max=10.0, default=5.0)",
    # Max raised from 2.0 to 5.0 in v2.4.1 to match the new beep-length
    # field's range, per user request, so the two timing fields in
    # Advanced settings share a consistent ceiling. Default raised from
    # 0.15 to 2.0 in v2.5.1, also per user request following real-world
    # testing.
    "gap": "float(min=0.0, max=5.0, default=2.0)",
    "sampleRate": "integer(default=44100)",
    "chromaticMode": "boolean(default=false)",
    "lastInstrument": "string(default='Guitar 6-string')",
    "lastTuning": "string(default='')",
    # v2.4.0: length of the confirmation beep played by the live tuner
    # when a reading is exactly in tune, and whether that beep plays at
    # all (some users want the spoken confirmation only) - previously
    # the beep length was a hardcoded 0.6s constant in __init__.py and
    # could not be turned off. Default raised from 0.6 to 5.0 in v2.5.1
    # per user request following real-world testing.
    "beepDuration": "float(min=0.1, max=5.0, default=5.0)",
    "beepEnabled": "boolean(default=true)",
    # v2.5.0: which microphone live listening should use. Stored as the
    # device's NAME rather than its numeric WinMM device ID, because
    # device IDs aren't stable across reboots/reconnections - the name
    # is re-resolved to whatever ID currently matches it each time
    # listening starts (see mic_capture.find_device_id_by_name). Empty
    # string means "use the system default recording device".
    "micDeviceName": "string(default='')",
}

_DEFAULTS = {
    "a4": 440.0,
    "volume": 0.22,
    "duration": 5.0,
    "gap": 2.0,
    "sampleRate": 44100,
    "chromaticMode": False,
    "lastInstrument": "Guitar 6-string",
    "lastTuning": "",
    "beepDuration": 5.0,
    "beepEnabled": True,
    "micDeviceName": "",
}

# Public read-only copy of the defaults, for the Advanced settings dialog's
# "Reset to defaults" button (ui_dialogs.py) - kept as a separate name from
# the leading-underscore _DEFAULTS above so external modules have a clearly
# intentional, stable name to import rather than reaching into a "private"
# one.
DEFAULTS = dict(_DEFAULTS)


def register():
    if not _HAVE_NVDA:
        return
    try:
        config.conf.spec[CONFIG_SECTION] = CONFSPEC
    except Exception:
        log.error("UniversalTuner: failed to register config spec", exc_info=True)


def load():
    """Returns a plain dict of settings, falling back to defaults for any
    key that can't be read (missing NVDA config module, corrupt profile,
    first-ever run, etc.) so callers never have to special-case startup."""
    if not _HAVE_NVDA:
        return dict(_DEFAULTS)
    try:
        section = config.conf[CONFIG_SECTION]
        return {
            "a4": float(section["a4"]),
            "volume": float(section["volume"]),
            "duration": float(section["duration"]),
            "gap": float(section["gap"]),
            "sampleRate": int(section["sampleRate"]),
            "chromaticMode": bool(section["chromaticMode"]),
            "lastInstrument": str(section["lastInstrument"]),
            "lastTuning": str(section["lastTuning"]),
            "beepDuration": float(section["beepDuration"]),
            "beepEnabled": bool(section["beepEnabled"]),
            "micDeviceName": str(section["micDeviceName"]),
        }
    except Exception:
        log.error("UniversalTuner: failed to load settings, using defaults", exc_info=True)
        return dict(_DEFAULTS)


def save(values):
    """values: dict with any subset of the keys in _DEFAULTS."""
    if not _HAVE_NVDA:
        return
    try:
        section = config.conf[CONFIG_SECTION]
        for key, value in values.items():
            if key in _DEFAULTS:
                section[key] = value
    except Exception:
        log.error("UniversalTuner: failed to save settings", exc_info=True)
