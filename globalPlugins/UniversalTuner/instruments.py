# -*- coding: utf-8 -*-
"""
Instrument/tuning data and note<->MIDI<->frequency helpers.
Moved out of the old single-file "Universal Tuner.py" as-is (no behaviour
changes) so the huge dictionary of instruments doesn't drown out the
actual plugin logic, and so it can be imported and unit tested without
pulling in wx/NVDA at all.
"""

INSTRUMENTS = {
    "Guitar 6-string": {
        "Standard E A D G B E": ["E2", "A2", "D3", "G3", "B3", "E4"],
        "Eb Tuning D# G# C# F# A# D#": ["D#2", "G#2", "C#3", "F#3", "A#3", "D#4"],
        "Drop D D A D G B E": ["D2", "A2", "D3", "G3", "B3", "E4"],
        "Drop C C G C F A D": ["C2", "G2", "C3", "F3", "A3", "D4"],
        "Drop B B F# B E G# C#": ["B1", "F#2", "B2", "E3", "G#3", "C#4"],
        "D Standard D G C F A D": ["D2", "G2", "C3", "F3", "A3", "D4"],
        "C Standard C F A# D# G C": ["C2", "F2", "A#2", "D#3", "G3", "C4"],
        "Open G D G D G B D": ["D2", "G2", "D3", "G3", "B3", "D4"],
        "Open D D A D F# A D": ["D2", "A2", "D3", "F#3", "A3", "D4"],
        "Open C C G C G C E": ["C2", "G2", "C3", "G3", "C4", "E4"],
        "DADGAD D A D G A D": ["D2", "A2", "D3", "G3", "A3", "D4"],
        "Double Drop D D A D G B D": ["D2", "A2", "D3", "G3", "B3", "D4"],
    },

    "Guitar 12-string": {
        "Standard E A D G B E": ["E2", "A2", "D3", "G3", "B3", "E4"],
        "Eb Tuning D# G# C# F# A# D#": ["D#2", "G#2", "C#3", "F#3", "A#3", "D#4"],
        "Drop D D A D G B E": ["D2", "A2", "D3", "G3", "B3", "E4"],
    },

    "Guitar 7-string": {
        "Standard B E A D G B E": ["B1", "E2", "A2", "D3", "G3", "B3", "E4"],
        "Drop A A E A D G B E": ["A1", "E2", "A2", "D3", "G3", "B3", "E4"],
        "A Standard A D G C F A D": ["A1", "D2", "G2", "C3", "F3", "A3", "D4"],
    },

    "Guitar 8-string": {
        "Standard F# B E A D G B E": ["F#1", "B1", "E2", "A2", "D3", "G3", "B3", "E4"],
        "Drop E E B E A D G B E": ["E1", "B1", "E2", "A2", "D3", "G3", "B3", "E4"],
    },

    "Bass 4-string": {
        "Standard E A D G": ["E1", "A1", "D2", "G2"],
        "Drop D D A D G": ["D1", "A1", "D2", "G2"],
        "Drop C C G C F": ["C1", "G1", "C2", "F2"],
        "BEAD B E A D": ["B0", "E1", "A1", "D2"],
    },

    "Bass 5-string": {
        "Standard B E A D G": ["B0", "E1", "A1", "D2", "G2"],
        "High C E A D G C": ["E1", "A1", "D2", "G2", "C3"],
    },

    "Bass 6-string": {
        "Standard B E A D G C": ["B0", "E1", "A1", "D2", "G2", "C3"],
    },

    "Double Bass": {
        "Standard E A D G": ["E1", "A1", "D2", "G2"],
    },

    "Ukulele Soprano": {
        "Standard G C E A": ["G4", "C4", "E4", "A4"],
        "Low G G C E A": ["G3", "C4", "E4", "A4"],
        "D Tuning A D F# B": ["A4", "D4", "F#4", "B4"],
        "Slack-Key G B D G": ["G4", "B3", "D4", "G4"],
    },

    "Ukulele Concert": {
        "Standard G C E A": ["G4", "C4", "E4", "A4"],
        "Low G G C E A": ["G3", "C4", "E4", "A4"],
        "D Tuning A D F# B": ["A4", "D4", "F#4", "B4"],
        "Slack-Key G B D G": ["G4", "B3", "D4", "G4"],
    },

    "Ukulele Tenor": {
        "Standard G C E A": ["G4", "C4", "E4", "A4"],
        "Low G G C E A": ["G3", "C4", "E4", "A4"],
        "D Tuning A D F# B": ["A4", "D4", "F#4", "B4"],
        "Slack-Key G B D G": ["G4", "B3", "D4", "G4"],
    },

    "Ukulele Baritone": {
        "Standard D G B E": ["D3", "G3", "B3", "E4"],
    },

    "Violin": {
        "Standard G D A E": ["G3", "D4", "A4", "E5"],
        "Cross A E A E": ["A3", "E4", "A4", "E5"],
        "Cross G D G D": ["G3", "D4", "G4", "D5"],
        "A D A E": ["A3", "D4", "A4", "E5"],
    },

    "Viola": {
        "Standard C G D A": ["C3", "G3", "D4", "A4"],
        "Scordatura D G D A": ["D3", "G3", "D4", "A4"],
    },

    "Cello": {
        "Standard C G D A": ["C2", "G2", "D3", "A3"],
    },

    "Mandolin": {
        "Standard G D A E": ["G3", "D4", "A4", "E5"],
    },

    "Mandola": {
        "Standard C G D A": ["C3", "G3", "D4", "A4"],
    },

    "Octave Mandolin": {
        "Standard G D A E": ["G2", "D3", "A3", "E4"],
    },

    "Irish Bouzouki": {
        "Standard G D A D": ["G2", "D3", "A3", "D4"],
        "A D A D": ["A2", "D3", "A3", "D4"],
    },

    "Banjo 4-string": {
        "Standard C G D A": ["C3", "G3", "D4", "A4"],
        "Irish G D A E": ["G3", "D4", "A4", "E5"],
    },

    "Banjo 5-string": {
        "Standard Open G g D G B D": ["G4", "D3", "G3", "B3", "D4"],
    },

    "Banjo 6-string": {
        "Standard E A D G B E": ["E2", "A2", "D3", "G3", "B3", "E4"],
    },

    "Phin": {
        "Standard E A E": ["E3", "A3", "E4"],
        "A Tuning A D A": ["A3", "D4", "A4"],
        "D Tuning D G D": ["D3", "G3", "D4"],
    },

    "Seung": {
        "Standard G C D G": ["G3", "C4", "D4", "G4"],
    },

    "Saw Duang": {
        "Standard D A": ["D4", "A4"],
    },

    "Saw U": {
        "Standard G D": ["G3", "D4"],
    },

    "Saw Sam Sai": {
        "Standard G D G": ["G3", "D4", "G4"],
    },

    "Jakhe": {
        "Standard C G C": ["C3", "G3", "C4"],
    },

    "Khim": {
        "C Major Scale": ["C4", "D4", "E4", "F4", "G4", "A4", "B4"],
        "G Major Scale": ["G3", "A3", "B3", "C4", "D4", "E4", "F#4"],
        "D Major Scale": ["D4", "E4", "F#4", "G4", "A4", "B4", "C#5"],
    },

    "Drum Kit Reference": {
        "Kick Low": ["E1"],
        "Kick Punch": ["F1"],
        "Snare Low": ["D3"],
        "Snare Medium": ["E3"],
        "Snare High": ["F3"],
        "Tom 10 inch": ["C3"],
        "Tom 12 inch": ["A2"],
        "Floor Tom 14 inch": ["F2"],
    },
}


PAIRED_INSTRUMENT_MODES = {
    "Guitar 12-string": "guitar12",
    "Mandolin": "unison_pairs",
    "Mandola": "unison_pairs",
    "Octave Mandolin": "unison_pairs",
    "Irish Bouzouki": "unison_pairs",
}


NOTE_TO_MIDI = {}
MIDI_TO_NOTE = {}
_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
for _octv in range(0, 9):
    _base = 12 + _octv * 12
    for _i, _n in enumerate(_names):
        _midi_num = _base + _i
        _note_name = "%s%d" % (_n, _octv)
        NOTE_TO_MIDI[_note_name] = _midi_num
        MIDI_TO_NOTE[_midi_num] = _note_name


def midi_to_freq(midi, a4=440.0):
    return a4 * (2.0 ** ((midi - 69) / 12.0))


def midi_to_note_name(midi):
    return MIDI_TO_NOTE.get(midi)


def get_tunings_for(instrumentName):
    inst = INSTRUMENTS.get(instrumentName)
    if not inst:
        inst = INSTRUMENTS["Guitar 6-string"]
    return inst


def get_notes_for(instrumentName, tuningName):
    tunings = get_tunings_for(instrumentName)
    notes = tunings.get(tuningName)
    if not notes:
        notes = next(iter(tunings.values()))
    return notes


def get_item_label_for_instrument(instrumentName):
    if instrumentName == "Khim":
        return "Note"
    if instrumentName == "Drum Kit Reference":
        return "Voice"
    return "String"


def get_course_count(instrumentName, tuningName):
    return len(get_notes_for(instrumentName, tuningName))


def get_physical_notes_for(instrumentName, tuningName):
    course_notes = get_notes_for(instrumentName, tuningName)
    mode = PAIRED_INSTRUMENT_MODES.get(instrumentName)
    if not mode:
        return list(course_notes)

    physical = []
    for idx, note in enumerate(course_notes):
        midi_num = NOTE_TO_MIDI.get(note)
        if midi_num is None:
            physical.append(note)
            continue

        if mode == "guitar12":
            if idx <= 3:
                octave_note = midi_to_note_name(midi_num + 12)
                if octave_note is None:
                    octave_note = note
                physical.extend([note, octave_note])
            else:
                physical.extend([note, note])
        elif mode == "unison_pairs":
            physical.extend([note, note])
        else:
            physical.append(note)
    return physical


def build_string_items(instrumentName, tuningName):
    notes = get_physical_notes_for(instrumentName, tuningName)
    items = []
    count = len(notes)
    label = get_item_label_for_instrument(instrumentName)
    for s, note in zip(range(count, 0, -1), notes):
        items.append("%s %d note %s" % (label, s, note))
    return items


def parse_string_number(selection):
    if not selection:
        return None
    parts = selection.strip().split()
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except Exception:
            pass
    try:
        return int(parts[0])
    except Exception:
        return None


def get_display_note_for_string_number(instrumentName, tuningName, displayedNumber):
    physical_notes = get_physical_notes_for(instrumentName, tuningName)
    count = len(physical_notes)
    if displayedNumber < 1 or displayedNumber > count:
        return None
    idx = count - int(displayedNumber)
    return physical_notes[idx]


def find_displayed_number_for_note(instrumentName, tuningName, noteName):
    """Reverse of get_display_note_for_string_number: given a note name,
    find which displayed "Selection" list entry (1..count) it corresponds
    to. Used to keep the Selection dropdown visually in sync when a note
    is played via the number-key/course shortcut instead of the dropdown
    itself - otherwise the dropdown can silently show a different string
    than whatever is actually sounding, which is confusing (this was the
    bug the number-key/Space-bar/dropdown sync fix addressed). If the same
    note name appears more than once (e.g. a unison pair), the first
    match (highest displayed number... actually lowest count-down index)
    is returned - any of them is equally correct since they're the same
    pitch."""
    physical_notes = get_physical_notes_for(instrumentName, tuningName)
    count = len(physical_notes)
    for idx, note in enumerate(physical_notes):
        if note == noteName:
            return count - idx
    return None
# -*- coding: utf-8 -*-
"""
Instrument/tuning data and note<->MIDI<->frequency helpers.
Moved out of the old single-file "Universal Tuner.py" as-is (no behaviour
changes) so the huge dictionary of instruments doesn't drown out the
actual plugin logic, and so it can be imported and unit tested without
pulling in wx/NVDA at all.
"""

INSTRUMENTS = {
    "Guitar 6-string": {
        "Standard E A D G B E": ["E2", "A2", "D3", "G3", "B3", "E4"],
        "Eb Tuning D# G# C# F# A# D#": ["D#2", "G#2", "C#3", "F#3", "A#3", "D#4"],
        "Drop D D A D G B E": ["D2", "A2", "D3", "G3", "B3", "E4"],
        "Drop C C G C F A D": ["C2", "G2", "C3", "F3", "A3", "D4"],
        "Drop B B F# B E G# C#": ["B1", "F#2", "B2", "E3", "G#3", "C#4"],
        "D Standard D G C F A D": ["D2", "G2", "C3", "F3", "A3", "D4"],
        "C Standard C F A# D# G C": ["C2", "F2", "A#2", "D#3", "G3", "C4"],
        "Open G D G D G B D": ["D2", "G2", "D3", "G3", "B3", "D4"],
        "Open D D A D F# A D": ["D2", "A2", "D3", "F#3", "A3", "D4"],
        "Open C C G C G C E": ["C2", "G2", "C3", "G3", "C4", "E4"],
        "DADGAD D A D G A D": ["D2", "A2", "D3", "G3", "A3", "D4"],
        "Double Drop D D A D G B D": ["D2", "A2", "D3", "G3", "B3", "D4"],
        "Open E E B E G# B E": ["E2", "B2", "E3", "G#3", "B3", "E4"],
        "Open A E A E A C# E": ["E2", "A2", "E3", "A3", "C#4", "E4"],
        "All Fourths E A D G C F": ["E2", "A2", "D3", "G3", "C4", "F4"],
    },

    "Guitar 12-string": {
        "Standard E A D G B E": ["E2", "A2", "D3", "G3", "B3", "E4"],
        "Eb Tuning D# G# C# F# A# D#": ["D#2", "G#2", "C#3", "F#3", "A#3", "D#4"],
        "Drop D D A D G B E": ["D2", "A2", "D3", "G3", "B3", "E4"],
    },

    "Guitar 7-string": {
        "Standard B E A D G B E": ["B1", "E2", "A2", "D3", "G3", "B3", "E4"],
        "Drop A A E A D G B E": ["A1", "E2", "A2", "D3", "G3", "B3", "E4"],
        "A Standard A D G C F A D": ["A1", "D2", "G2", "C3", "F3", "A3", "D4"],
    },

    "Guitar 8-string": {
        "Standard F# B E A D G B E": ["F#1", "B1", "E2", "A2", "D3", "G3", "B3", "E4"],
        "Drop E E B E A D G B E": ["E1", "B1", "E2", "A2", "D3", "G3", "B3", "E4"],
    },

    "Guitar Baritone": {
        "Standard B E A D F# B": ["B1", "E2", "A2", "D3", "F#3", "B3"],
    },

    "Guitar Requinto": {
        "Standard A D G C E A": ["A2", "D3", "G3", "C4", "E4", "A4"],
    },

    "Guitar Tenor": {
        "Irish Fifths G D A E": ["G2", "D3", "A3", "E4"],
        "Chicago D G B E": ["D3", "G3", "B3", "E4"],
        "Fifths C G D A": ["C3", "G3", "D4", "A4"],
    },

    "Bass 4-string": {
        "Standard E A D G": ["E1", "A1", "D2", "G2"],
        "Drop D D A D G": ["D1", "A1", "D2", "G2"],
        "Drop C C G C F": ["C1", "G1", "C2", "F2"],
        "BEAD B E A D": ["B0", "E1", "A1", "D2"],
        "Eb Standard D# G# C# F#": ["D#1", "G#1", "C#2", "F#2"],
    },

    "Bass 5-string": {
        "Standard B E A D G": ["B0", "E1", "A1", "D2", "G2"],
        "High C E A D G C": ["E1", "A1", "D2", "G2", "C3"],
        "Drop A A E A D G": ["A0", "E1", "A1", "D2", "G2"],
    },

    "Bass 6-string": {
        "Standard B E A D G C": ["B0", "E1", "A1", "D2", "G2", "C3"],
    },

    "Double Bass": {
        "Standard E A D G": ["E1", "A1", "D2", "G2"],
    },

    "Ukulele Soprano": {
        "Standard G C E A": ["G4", "C4", "E4", "A4"],
        "Low G G C E A": ["G3", "C4", "E4", "A4"],
        "D Tuning A D F# B": ["A4", "D4", "F#4", "B4"],
        "Slack-Key G B D G": ["G4", "B3", "D4", "G4"],
    },

    "Ukulele Concert": {
        "Standard G C E A": ["G4", "C4", "E4", "A4"],
        "Low G G C E A": ["G3", "C4", "E4", "A4"],
        "D Tuning A D F# B": ["A4", "D4", "F#4", "B4"],
        "Slack-Key G B D G": ["G4", "B3", "D4", "G4"],
    },

    "Ukulele Tenor": {
        "Standard G C E A": ["G4", "C4", "E4", "A4"],
        "Low G G C E A": ["G3", "C4", "E4", "A4"],
        "D Tuning A D F# B": ["A4", "D4", "F#4", "B4"],
        "Slack-Key G B D G": ["G4", "B3", "D4", "G4"],
    },

    "Ukulele Baritone": {
        "Standard D G B E": ["D3", "G3", "B3", "E4"],
    },

    "Violin": {
        "Standard G D A E": ["G3", "D4", "A4", "E5"],
        "Cross A E A E": ["A3", "E4", "A4", "E5"],
        "Cross G D G D": ["G3", "D4", "G4", "D5"],
        "A D A E": ["A3", "D4", "A4", "E5"],
    },

    "Viola": {
        "Standard C G D A": ["C3", "G3", "D4", "A4"],
        "Scordatura D G D A": ["D3", "G3", "D4", "A4"],
    },

    "Cello": {
        "Standard C G D A": ["C2", "G2", "D3", "A3"],
    },

    "Mandolin": {
        "Standard G D A E": ["G3", "D4", "A4", "E5"],
    },

    "Mandola": {
        "Standard C G D A": ["C3", "G3", "D4", "A4"],
    },

    "Octave Mandolin": {
        "Standard G D A E": ["G2", "D3", "A3", "E4"],
    },

    "Irish Bouzouki": {
        "Standard G D A D": ["G2", "D3", "A3", "D4"],
        "A D A D": ["A2", "D3", "A3", "D4"],
    },

    "Mandocello": {
        "Standard C G D A": ["C2", "G2", "D3", "A3"],
    },

    "Charango": {
        "Standard G C E A E": ["G4", "C5", "E5", "A4", "E5"],
    },

    "Oud": {
        "Arabic Standard C F A D G C": ["C2", "F2", "A2", "D3", "G3", "C4"],
    },

    "Balalaika Prima": {
        "Standard E E A": ["E4", "E4", "A4"],
    },

    "Erhu": {
        "Standard D A": ["D4", "A4"],
    },

    "Pipa": {
        "Standard A D E A": ["A2", "D3", "E3", "A3"],
    },

    "Cavaquinho": {
        "Standard D G B D": ["D4", "G4", "B4", "D5"],
    },

    "Cuatro Venezolano": {
        "Standard A D F# B": ["A3", "D4", "F#4", "B3"],
    },

    "Mountain Dulcimer": {
        "DAD Mixolydian D A D": ["D3", "A3", "D4"],
        "DAA D A A": ["D3", "A3", "A4"],
    },

    "Banjo 4-string": {
        "Standard C G D A": ["C3", "G3", "D4", "A4"],
        "Irish G D A E": ["G3", "D4", "A4", "E5"],
    },

    "Banjo 5-string": {
        "Standard Open G g D G B D": ["G4", "D3", "G3", "B3", "D4"],
        "Double C g C G C D": ["G4", "C3", "G3", "C4", "D4"],
        "Sawmill G Modal g D G C D": ["G4", "D3", "G3", "C4", "D4"],
        "Open D f# D F# A D": ["F#4", "D3", "F#3", "A3", "D4"],
    },

    "Banjo 6-string": {
        "Standard E A D G B E": ["E2", "A2", "D3", "G3", "B3", "E4"],
    },

    "Phin": {
        "Standard E A E": ["E3", "A3", "E4"],
        "A Tuning A D A": ["A3", "D4", "A4"],
        "D Tuning D G D": ["D3", "G3", "D4"],
    },

    "Seung": {
        "Standard G C D G": ["G3", "C4", "D4", "G4"],
    },

    "Saw Duang": {
        "Standard D A": ["D4", "A4"],
    },

    "Saw U": {
        "Standard G D": ["G3", "D4"],
    },

    "Saw Sam Sai": {
        "Standard G D G": ["G3", "D4", "G4"],
    },

    "Jakhe": {
        "Standard C G C": ["C3", "G3", "C4"],
    },

    "Khim": {
        "C Major Scale": ["C4", "D4", "E4", "F4", "G4", "A4", "B4"],
        "G Major Scale": ["G3", "A3", "B3", "C4", "D4", "E4", "F#4"],
        "D Major Scale": ["D4", "E4", "F#4", "G4", "A4", "B4", "C#5"],
    },

    "Drum Kit Reference": {
        "Kick Low": ["E1"],
        "Kick Punch": ["F1"],
        "Snare Low": ["D3"],
        "Snare Medium": ["E3"],
        "Snare High": ["F3"],
        "Tom 10 inch": ["C3"],
        "Tom 12 inch": ["A2"],
        "Floor Tom 14 inch": ["F2"],
    },
}


PAIRED_INSTRUMENT_MODES = {
    "Guitar 12-string": "guitar12",
    "Mandolin": "unison_pairs",
    "Mandola": "unison_pairs",
    "Octave Mandolin": "unison_pairs",
    "Irish Bouzouki": "unison_pairs",
    "Mandocello": "unison_pairs",
    "Oud": "unison_pairs",
    # Charango: 5 courses, re-entrant tuning (G C E A E). Four courses are
    # ordinary unison pairs, but the 3rd course (index 2, the "E" course)
    # is an octave pair like a 12-string guitar's bass courses - the
    # companion string is an octave BELOW the listed E5, not the same
    # pitch. See "charango" handling in get_physical_notes_for() below and
    # the matching branch in __init__.py's _get_course_target().
    "Charango": "charango",
}


# Capo simulation (v2026.09.09): instruments with frets only - a capo
# clamps across the fingerboard and raises every open string by the same
# number of semitones, so it only makes sense for fretted instruments.
# Verified per-instrument against reference sources rather than assumed:
# fretless instruments (violin family, Oud, Erhu, the Thai "saw" bowed
# fiddles, Khim, Double Bass, Drum Kit Reference) are deliberately left
# out. Pipa, Jakhe, and Seung/Phin were specifically checked since they
# are less commonly known to be fretted - all three are.
MAX_CAPO_FRETS = 9

CAPO_ELIGIBLE_INSTRUMENTS = {
    "Guitar 6-string", "Guitar 12-string", "Guitar 7-string", "Guitar 8-string",
    "Guitar Baritone", "Guitar Requinto", "Guitar Tenor",
    "Bass 4-string", "Bass 5-string", "Bass 6-string",
    "Ukulele Soprano", "Ukulele Concert", "Ukulele Tenor", "Ukulele Baritone",
    "Mandolin", "Mandola", "Octave Mandolin", "Irish Bouzouki", "Mandocello",
    "Charango", "Balalaika Prima", "Pipa", "Cavaquinho", "Cuatro Venezolano",
    "Mountain Dulcimer",
    "Banjo 4-string", "Banjo 5-string", "Banjo 6-string",
    "Phin", "Seung", "Jakhe",
}


NOTE_TO_MIDI = {}
MIDI_TO_NOTE = {}
_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
for _octv in range(0, 9):
    _base = 12 + _octv * 12
    for _i, _n in enumerate(_names):
        _midi_num = _base + _i
        _note_name = "%s%d" % (_n, _octv)
        NOTE_TO_MIDI[_note_name] = _midi_num
        MIDI_TO_NOTE[_midi_num] = _note_name


def midi_to_freq(midi, a4=440.0):
    return a4 * (2.0 ** ((midi - 69) / 12.0))


def midi_to_note_name(midi):
    return MIDI_TO_NOTE.get(midi)


def get_tunings_for(instrumentName):
    inst = INSTRUMENTS.get(instrumentName)
    if not inst:
        inst = INSTRUMENTS["Guitar 6-string"]
    return inst


def get_notes_for(instrumentName, tuningName):
    tunings = get_tunings_for(instrumentName)
    notes = tunings.get(tuningName)
    if not notes:
        notes = next(iter(tunings.values()))
    return notes


def get_item_label_for_instrument(instrumentName):
    if instrumentName == "Khim":
        return "Note"
    if instrumentName == "Drum Kit Reference":
        return "Voice"
    return "String"


def get_course_count(instrumentName, tuningName):
    return len(get_notes_for(instrumentName, tuningName))


def get_physical_notes_for(instrumentName, tuningName):
    course_notes = get_notes_for(instrumentName, tuningName)
    mode = PAIRED_INSTRUMENT_MODES.get(instrumentName)
    if not mode:
        return list(course_notes)

    physical = []
    for idx, note in enumerate(course_notes):
        midi_num = NOTE_TO_MIDI.get(note)
        if midi_num is None:
            physical.append(note)
            continue

        if mode == "guitar12":
            if idx <= 3:
                octave_note = midi_to_note_name(midi_num + 12)
                if octave_note is None:
                    octave_note = note
                physical.extend([note, octave_note])
            else:
                physical.extend([note, note])
        elif mode == "unison_pairs":
            physical.extend([note, note])
        elif mode == "charango":
            if idx == 2:
                octave_note = midi_to_note_name(midi_num - 12)
                if octave_note is None:
                    octave_note = note
                physical.extend([note, octave_note])
            else:
                physical.extend([note, note])
        else:
            physical.append(note)
    return physical


def build_string_items(instrumentName, tuningName):
    notes = get_physical_notes_for(instrumentName, tuningName)
    items = []
    count = len(notes)
    label = get_item_label_for_instrument(instrumentName)
    for s, note in zip(range(count, 0, -1), notes):
        items.append("%s %d note %s" % (label, s, note))
    return items


def parse_string_number(selection):
    if not selection:
        return None
    parts = selection.strip().split()
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except Exception:
            pass
    try:
        return int(parts[0])
    except Exception:
        return None


def get_display_note_for_string_number(instrumentName, tuningName, displayedNumber):
    physical_notes = get_physical_notes_for(instrumentName, tuningName)
    count = len(physical_notes)
    if displayedNumber < 1 or displayedNumber > count:
        return None
    idx = count - int(displayedNumber)
    return physical_notes[idx]


def find_displayed_number_for_note(instrumentName, tuningName, noteName):
    """Reverse of get_display_note_for_string_number: given a note name,
    find which displayed "Selection" list entry (1..count) it corresponds
    to. Used to keep the Selection dropdown visually in sync when a note
    is played via the number-key/course shortcut instead of the dropdown
    itself - otherwise the dropdown can silently show a different string
    than whatever is actually sounding, which is confusing (this was the
    bug the number-key/Space-bar/dropdown sync fix addressed). If the same
    note name appears more than once (e.g. a unison pair), the first
    match (highest displayed number... actually lowest count-down index)
    is returned - any of them is equally correct since they're the same
    pitch."""
    physical_notes = get_physical_notes_for(instrumentName, tuningName)
    count = len(physical_notes)
    for idx, note in enumerate(physical_notes):
        if note == noteName:
            return count - idx
    return None
