"""
Cents / percent deviation math and spoken-message formatting for the live
tuner feature. Kept separate from audio/DSP code so it can be unit tested
in isolation - this is pure arithmetic and string formatting, no NVDA,
wx, or Windows dependency at all.

User-specified convention: 100% = 1 semitone (100 cents), so "percent" is
numerically identical to "cents" here - it's the same number, just labeled
in the friendlier unit the user asked for instead of music-theory jargon.
A small "in tune" tolerance window is treated as "spot on" rather than
reporting +0.4% etc, since no human pluck is perfectly exact and reporting
near-zero noise as "sharp" would be more confusing than helpful.

v2.5.2: the spoken result is now built as a single, fully-formed sentence
per case and passed through NVDA's standard gettext translation (_()),
instead of two separately hand-maintained English/Thai strings that were
concatenated from smaller fragments ("Note X. " + "In tune."). Building
whole sentences per language, rather than splicing translated fragments
together, is the correct approach for translation - fragment concatenation
does not hold up across languages with different word order. This also
fixes a real bug: the old code always spoke the English variant during
live tuning regardless of NVDA's configured language, because nothing
ever selected the Thai variant at the call site. Translated output now
simply follows whatever language NVDA/the add-on's locale is set to, the
same way every other NVDA add-on message does.
"""
import math

try:
    import addonHandler
    addonHandler.initTranslation()
except Exception:  # pragma: no cover - only importable inside NVDA
    def _(s):
        return s

IN_TUNE_CENTS_TOLERANCE = 5.0  # within +/-5 cents counts as "spot on"


def freq_to_cents(detected_freq, target_freq):
    """Positive = sharp (too high), negative = flat (too low)."""
    if detected_freq <= 0 or target_freq <= 0:
        return None
    return 1200.0 * math.log2(detected_freq / target_freq)


def cents_to_percent(cents):
    # 100 cents == 1 semitone == "100%" per the user's chosen convention,
    # so percent is numerically identical to cents. Kept as its own
    # function so there is exactly one place this convention is defined.
    return cents


def nearest_note_frequency(freq, a4=440.0):
    """Given an arbitrary detected frequency, find the nearest 12-TET
    semitone's frequency and MIDI number (for chromatic / free-note mode,
    where the user isn't necessarily tuning to a specific instrument
    string)."""
    if freq <= 0:
        return None, None
    midi_float = 69 + 12 * math.log2(freq / a4)
    midi_nearest = round(midi_float)
    nearest_freq = a4 * (2.0 ** ((midi_nearest - 69) / 12.0))
    return nearest_freq, midi_nearest


def describe_tuning(detected_freq, target_freq, note_name=None):
    """Return a dict with the numeric result plus a ready-to-speak,
    translated message string, following the exact rule the user asked
    for:
      - if flat (too low): "flat by X%"
      - if sharp (too high): "sharp by X%"
      - if within tolerance: "in tune"
    """
    cents = freq_to_cents(detected_freq, target_freq)
    if cents is None:
        return None
    percent = cents_to_percent(cents)

    if abs(cents) <= IN_TUNE_CENTS_TOLERANCE:
        direction = "in_tune"
    elif cents > 0:
        direction = "sharp"
    else:
        direction = "flat"

    result = {
        "cents": cents,
        "percent": percent,
        "direction": direction,
        "detected_freq": detected_freq,
        "target_freq": target_freq,
        "note_name": note_name,
    }

    abs_pct = abs(percent)

    # Each branch is one complete, translatable sentence (rather than
    # translated fragments spliced together), so word order can differ
    # freely between languages.
    if note_name:
        if direction == "in_tune":
            message = _("Note %s. In tune.") % note_name
        elif direction == "sharp":
            message = _("Note %s. Sharp by plus %.1f percent.") % (note_name, abs_pct)
        else:
            message = _("Note %s. Flat by minus %.1f percent.") % (note_name, abs_pct)
    else:
        if direction == "in_tune":
            message = _("In tune.")
        elif direction == "sharp":
            message = _("Sharp by plus %.1f percent.") % abs_pct
        else:
            message = _("Flat by minus %.1f percent.") % abs_pct

    result["message"] = message
    return result
