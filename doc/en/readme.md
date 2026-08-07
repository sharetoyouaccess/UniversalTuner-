# Universal Tuner for NVDA

Universal Tuner is an accessible instrument tuner add-on for NVDA. It plays
reference tones for over 40 instruments and nearly 100 tunings between them,
and can also listen through your microphone in real time and tell you
whether the note you just played is in tune, sharp, or flat.

## Opening the tuner

Press <kbd>NVDA+shift+g</kbd> to open the Universal Tuner window from
anywhere in Windows.

## Reference tone playback

- Choose an **Instrument** and **Tuning**, then move through the
  **Selection** list to pick a string, course, or note.
- <kbd>Space</kbd> plays or stops the sound of the currently selected item.
- Number keys <kbd>1</kbd>-<kbd>9</kbd>, then <kbd>0</kbd>, <kbd>-</kbd> and
  <kbd>=</kbd> (12 keys total, matching the row above the letters) play
  strings directly, in order. On instruments with paired/course strings
  (12-string guitar, mandolin family, Irish bouzouki, Oud, Mandocello,
  Charango), pressing the same key again switches between the paired
  string sounds.
- <kbd>Home</kbd> / <kbd>End</kbd> raise or lower the volume.
- <kbd>Page Up</kbd> / <kbd>Page Down</kbd> lengthen or shorten the
  reference tone.
- <kbd>[</kbd> / <kbd>]</kbd> lower or raise a simulated capo position
  (0-9 frets), on instruments with frets. Reference playback, live-tuning
  targets, and spoken note names all transpose to match what the string
  will actually sound like with a capo on. Has no effect on fretless
  instruments (violin family, Oud, Erhu, the Thai "saw" fiddles, Khim,
  Double Bass).

## Live microphone tuning

Press <kbd>L</kbd> to start or stop listening through your microphone while
you play a string. Roughly every two seconds, Universal Tuner reports one
clear reading: in tune, sharp by a percentage, or flat by a percentage
(100% equals one semitone).

- <kbd>C</kbd> toggles chromatic mode, which compares the detected pitch
  against the nearest note automatically instead of a specific selected
  string.
- When a reading is exactly in tune, Universal Tuner plays a short
  confirmation beep at the target note's own pitch, then announces the
  note name.
- <kbd>O</kbd> turns the confirmation beep on or off, for anyone who only
  wants the spoken reading.
- <kbd>R</kbd> repeats the last live-tuning reading on demand, in case you
  did not catch it clearly.
- While live listening is on, <kbd>Space</kbd> immediately cancels an
  in-progress confirmation beep and announcement.

## Other shortcuts inside the tuner window

- <kbd>I</kbd> jumps to the Instrument list, <kbd>T</kbd> jumps to the
  Tuning list.
- <kbd>F1</kbd> once speaks a full shortcuts guide in Thai; pressing
  <kbd>F1</kbd> a second time within under a second speaks the same guide
  in English.
- <kbd>Escape</kbd> closes the window.
- The **Advanced settings** button opens a dialog with sample rate, A4
  reference pitch, gap between repeats, beep length, tone length, and
  microphone device selection, plus a Reset to defaults option.

## Settings that are remembered

A4 reference pitch, volume, tone length, gap between repeats, sample rate,
chromatic mode, beep length, beep on/off, microphone device, capo
position, and your last selected instrument and tuning are all saved and
restored automatically the next time NVDA starts.

## Testing status

As of version 2.5.2, this add-on has been manually tested end-to-end on a
real NVDA + Windows machine, including live microphone tuning, chromatic
mode, microphone device switching, disconnect handling, the Advanced
settings dialog, settings persistence across restarts, and Thai/English
announcements. This covers one tester's hardware and microphone setup, not
the full range of audio devices in the wild - if you notice unexpected
behaviour with a specific microphone or audio device, please report it.

Version 2026.09.09 adds new instruments, tunings, the 12-key direct
string-selection shortcut (1-9, 0, -, =), and capo simulation ([ and ]).
This has been manually tested end-to-end on Windows 11 with the latest
official NVDA release (2026.1.1), including the new 0/-/=/[/] key
handling, and confirmed working.

## Author

Peem Narkkhwan &lt;sharetoyouaccess@gmail.com&gt;

## Source code

<https://github.com/sharetoyouaccess/UniversalTuner->
