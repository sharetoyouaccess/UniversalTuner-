  Universal Tuner for NVDA
Universal Tuner is an accessible instrument tuner add-on for NVDA. It plays reference tones for over two dozen instruments and tunings, and can also listen through your microphone in real time and tell you whether the note you just played is in tune, sharp, or flat.
Opening the tuner
Press NVDA+shift+g to open the Universal Tuner window from anywhere in Windows.
Reference tone playback
• Choose an Instrument and Tuning, then move through the Selection list to pick a string, course, or note.
• Space plays or stops the sound of the currently selected item.
• Number keys 1-9 play strings directly, in order. On instruments with paired/course strings (12-string guitar, mandolin family, Irish bouzouki), pressing the same number again switches between the paired string sounds.
• Home / End raise or lower the volume.
• Page Up / Page Down lengthen or shorten the reference tone.
Live microphone tuning
Press L to start or stop listening through your microphone while you play a string. Roughly every two seconds, Universal Tuner reports one clear reading: in tune, sharp by a percentage, or flat by a percentage (100% equals one semitone).
• C toggles chromatic mode, which compares the detected pitch against the nearest note automatically instead of a specific selected string.
• When a reading is exactly in tune, Universal Tuner plays a short confirmation beep at the target note's own pitch, then announces the note name.
• O turns the confirmation beep on or off, for anyone who only wants the spoken reading.
• R repeats the last live-tuning reading on demand, in case you did not catch it clearly.
• While live listening is on, Space immediately cancels an in-progress confirmation beep and announcement.
Other shortcuts inside the tuner window
• I jumps to the Instrument list, T jumps to the Tuning list.
• F1 once speaks a full shortcuts guide in Thai; pressing F1 a second time within under a second speaks the same guide in English.
• Escape closes the window.
• The Advanced settings button opens a dialog with sample rate, A4 reference pitch, gap between repeats, beep length, tone length, and microphone device selection, plus a Reset to defaults option.
Settings that are remembered
A4 reference pitch, volume, tone length, gap between repeats, sample rate, chromatic mode, beep length, beep on/off, microphone device, and your last selected instrument and tuning are all saved and restored automatically the next time NVDA starts.
Testing status
As of version 2.5.2, this add-on has been manually tested end-to-end on a real NVDA + Windows machine, including live microphone tuning, chromatic mode, microphone device switching, disconnect handling, the Advanced settings dialog, settings persistence across restarts, and Thai/English announcements. This covers one tester's hardware and microphone setup, not the full range of audio devices in the wild - if you notice unexpected behaviour with a specific microphone or audio device, please report it.
