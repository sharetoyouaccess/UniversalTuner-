# -*- coding: utf-8 -*-
"""
Universal Tuner for NVDA - v2026.07.27

Package layout: instruments / tone_engine / pitch_detect / tuning_feedback /
mic_capture / live_tuner / settings / ui_dialogs - each concern lives in its
own module instead of one large file, so each can be found and tested on
its own. See manifest.ini's changelog field for the full per-version
history; this header only tracks structural/testing notes that stay
relevant across versions.

Settings (A4, volume, tone length, gap, sample rate, chromatic mode, beep
length/on-off, microphone device, last instrument/tuning) persist across
NVDA restarts via NVDA's config system.

TESTING STATUS:
This add-on was originally developed in a sandbox with no Windows, no
NVDA, no real audio hardware, and no wx GUI runtime, so the pitch-
detection math (pitch_detect.py), the cents/percent/message logic
(tuning_feedback.py), and the live-tuner decision logic
(live_tuner.LiveTunerCore) were unit tested there against synthetic
sine-wave data. As of v2.5.2, the microphone capture code
(mic_capture.py), live microphone tuning (including chromatic mode, the
L/C/O/R shortcuts, mic device switching, and disconnect detection), the
Advanced settings dialog, settings persistence across NVDA restarts, and
the Thai/English announcements have all additionally been manually
verified on a real NVDA + Windows machine and confirmed working. This
covers one tester's hardware/microphone/Windows configuration - if you
run into unexpected behaviour on a different microphone or Windows
setup, please report it.
"""
import globalPluginHandler
import gui
import ui
import wx
from scriptHandler import script

import addonHandler
addonHandler.initTranslation()

from .instruments import (
    NOTE_TO_MIDI,
    midi_to_freq,
    midi_to_note_name,
    get_notes_for,
    get_display_note_for_string_number,
    PAIRED_INSTRUMENT_MODES,
)
from .tone_engine import ReferenceToneEngine
from .live_tuner import LiveTunerController
from .mic_capture import find_device_id_by_name
from .ui_dialogs import TunerDialog
from . import settings as tuner_settings

try:
    from logHandler import log
except Exception:  # pragma: no cover
    import logging
    log = logging.getLogger("UniversalTuner")

try:
    # Speech priority "NOW" interrupts whatever NVDA is currently saying
    # and speaks immediately. Live tuning readings change quickly enough
    # (the whole point is fast feedback while turning a tuning peg) that
    # without this, a new reading queues up behind whatever the last one
    # was still saying - by the time it's spoken, it's already stale, and
    # a fast run of readings backs up into an increasingly out-of-date
    # queue. Using Spri.NOW means the user always hears the latest value,
    # never a backlog.
    from speech.priorities import Spri
    _HAVE_SPRI = True
except Exception:  # pragma: no cover - older NVDA without this API
    _HAVE_SPRI = False


tuner_settings.register()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("Universal Tuner")

    def __init__(self):
        globalPluginHandler.GlobalPlugin.__init__(self)
        self._dlg = None

        saved = tuner_settings.load()
        self._a4 = saved["a4"]
        self._chromaticMode = saved["chromaticMode"]
        self._lastInstrument = saved["lastInstrument"]
        self._lastTuning = saved["lastTuning"]
        self._beepDuration = saved["beepDuration"]
        self._beepEnabled = saved["beepEnabled"]
        self._micDeviceName = saved["micDeviceName"]

        # Last message spoken by the live tuner (chromatic on or off) -
        # kept so the "R" shortcut can repeat it if the user didn't catch
        # it clearly the first time.
        self._lastLiveMessage = None
        # Handle for the pending wx.CallLater that speaks the "in tune"
        # confirmation after its beep finishes - lets Space bar cancel
        # that wait early while live listening is on (see
        # _cancelPendingLiveAnnouncement()).
        self._pendingBeepTimer = None

        self._instrument = self._lastInstrument or "Guitar 6-string"
        self._tuning = self._lastTuning or "Standard E A D G B E"

        self._refEngine = ReferenceToneEngine()
        self._refEngine.setParams(
            sampleRate=saved["sampleRate"],
            duration=saved["duration"],
            gap=saved["gap"],
            volume=saved["volume"],
        )

        self._previewActive = False
        self._lastCourseKey = None
        self._courseToggle = 0

        self._liveTuner = LiveTunerController(on_result=self._onLiveResult, on_lost=self._onLiveLost)
        self._liveTuner.set_device(find_device_id_by_name(self._micDeviceName) if self._micDeviceName else None)
        self._currentTargetFreq = None
        self._currentTargetNote = None

    def terminate(self):
        try:
            self._cancelPendingLiveAnnouncement()
        except Exception:
            log.error("UniversalTuner: failed to cancel pending live announcement on terminate", exc_info=True)
        try:
            if self._liveTuner.isRunning():
                self._liveTuner.stop()
        except Exception:
            log.error("UniversalTuner: failed to stop live tuner on terminate", exc_info=True)
        try:
            self._refEngine.shutdown()
        except Exception:
            log.error("UniversalTuner: failed to shut down reference tone engine", exc_info=True)
        globalPluginHandler.GlobalPlugin.terminate(self)

    # ------------------------------------------------------------------
    # Opening the dialog
    # ------------------------------------------------------------------

    @script(description=_("Open Universal Tuner dialog"))
    def script_openTuner(self, gesture):
        if self._dlg:
            try:
                alreadyShown = self._dlg.IsShown()
            except Exception:
                # The wx dialog object was destroyed (e.g. closed) without
                # onClosed() managing to run/clear self._dlg first -
                # calling methods on a destroyed wx object typically
                # raises RuntimeError. Treat that the same as "no dialog"
                # so a second NVDA+shift+g press still opens a fresh one
                # instead of erroring.
                alreadyShown = False
                self._dlg = None
            if alreadyShown:
                self._dlg.Raise()
                try:
                    self._dlg.SetFocus()
                    self._dlg.instrumentChoice.SetFocus()
                except Exception:
                    pass
                return

        def onStop():
            self.stop()

        def onToggleActive():
            # Space bar. Per user request: while live listening is on,
            # Space cuts off whatever is currently audible - an
            # in-progress "you're exactly in tune" beep+announcement, and/or
            # a number-key note cue (see _playNoteOnceForListening) that's
            # still sounding - instead of touching the old looping
            # reference-tone preview (which stays off while listening is
            # active - see _toggleListen).
            if self._liveTuner.isRunning():
                self._cancelPendingLiveAnnouncement()
                try:
                    self._refEngine.stop()
                except Exception:
                    log.error("UniversalTuner: failed to stop note cue during live listening", exc_info=True)
                return False
            # Otherwise: stop whatever is actually sounding right now
            # (regardless of whether it was started via the Selection
            # dropdown or a number-key course press); if nothing is
            # sounding, play whichever note is currently the shared
            # "selected" target - which the dropdown and the number keys
            # both keep up to date, whichever was touched most recently.
            if self._previewActive:
                self.stop()
                return False
            if self._currentTargetNote and self._currentTargetFreq is not None:
                self._playNote(self._currentTargetNote, self._currentTargetFreq)
                return True
            ui.message(_("Invalid selection"))
            return False

        def onPlayCourse(instrument, tuning, courseNumber):
            return self.play_course(instrument, tuning, courseNumber)

        def onLiveAdjust(sampleRate=None, duration=None, gap=None, volume=None, a4=None,
                         beepDuration=None, micDeviceName=None):
            self._refEngine.setParams(sampleRate=sampleRate, duration=duration, gap=gap, volume=volume)
            if a4 is not None:
                self._a4 = float(a4)
                # A4 changed - refresh whatever the live tuner's current
                # fixed target is so it's calculated from the new A4.
                if self._currentTargetNote:
                    self._pushLiveTarget(self._currentTargetNote)
            if beepDuration is not None:
                self._beepDuration = float(beepDuration)
            if micDeviceName is not None:
                self._micDeviceName = micDeviceName
                self._liveTuner.set_device(
                    find_device_id_by_name(micDeviceName) if micDeviceName else None
                )
            self._saveSettings()

        def getLiveParams():
            params = self._refEngine.getParams()
            params["a4"] = self._a4
            params["beepDuration"] = self._beepDuration
            params["beepEnabled"] = self._beepEnabled
            params["micDeviceName"] = self._micDeviceName
            return params

        def onToggleBeep(isOn):
            self._beepEnabled = bool(isOn)
            self._saveSettings()

        def onRepeatLast():
            # "R" shortcut: repeat the last live-tuner spoken reading,
            # in case the user didn't catch it clearly - works the same
            # whether chromatic mode is on or off, since it just replays
            # whatever was actually announced last.
            if self._lastLiveMessage:
                if _HAVE_SPRI:
                    ui.message(self._lastLiveMessage, speechPriority=Spri.NOW)
                else:
                    ui.message(self._lastLiveMessage)
                return True
            ui.message(_("No reading yet"))
            return False

        def onSelectionTargetChanged(instrument, tuning, displayedNumber):
            self._instrument = instrument
            self._tuning = tuning
            self._lastInstrument = instrument
            self._lastTuning = tuning
            noteName = get_display_note_for_string_number(instrument, tuning, displayedNumber)
            if noteName:
                self._pushLiveTarget(noteName)
            self._saveSettings()

        def onToggleListen():
            if self._liveTuner.isRunning():
                self._liveTuner.stop()
                return False
            if not self._chromaticMode and self._currentTargetNote:
                self._pushLiveTarget(self._currentTargetNote)
            elif self._chromaticMode:
                self._liveTuner.configure_chromatic(a4=self._a4)
            started = self._liveTuner.start()
            if not started:
                detail = self._liveTuner.lastError()
                if detail:
                    ui.message(
                        _("Could not start the microphone: %s. Check your microphone is connected and permitted.")
                        % detail
                    )
                else:
                    ui.message(_("Could not start the microphone. Check your microphone is connected and permitted."))
                return False
            return True

        def onToggleChromatic(isOn):
            self._chromaticMode = bool(isOn)
            if self._chromaticMode:
                self._liveTuner.configure_chromatic(a4=self._a4)
            elif self._currentTargetNote:
                self._pushLiveTarget(self._currentTargetNote)
            self._saveSettings()

        def onClosed():
            self._dlg = None

        self._dlg = TunerDialog(
            gui.mainFrame,
            onStop,
            onToggleActive,
            onPlayCourse,
            onLiveAdjust,
            getLiveParams,
            onSelectionTargetChanged,
            onToggleListen,
            onToggleChromatic,
            onToggleBeep,
            onRepeatLast,
            initialChromatic=self._chromaticMode,
            initialInstrument=self._lastInstrument,
            initialTuning=self._lastTuning,
            initialBeepEnabled=self._beepEnabled,
            onClosed=onClosed,
        )
        self._dlg.Show()

        try:
            self._dlg.Raise()
            self._dlg.SetFocus()
            self._dlg.instrumentChoice.SetFocus()
        except Exception:
            pass

        ui.message(_("Universal Tuner ready"))

    __gestures = {
        "kb:NVDA+shift+g": "openTuner",
    }

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _saveSettings(self):
        params = self._refEngine.getParams()
        tuner_settings.save({
            "a4": self._a4,
            "volume": params["volume"],
            "duration": params["duration"],
            "gap": params["gap"],
            "sampleRate": params["sampleRate"],
            "chromaticMode": self._chromaticMode,
            "lastInstrument": self._instrument,
            "lastTuning": self._tuning,
            "beepDuration": self._beepDuration,
            "beepEnabled": self._beepEnabled,
            "micDeviceName": self._micDeviceName,
        })

    # ------------------------------------------------------------------
    # Live tuner target tracking
    # ------------------------------------------------------------------

    def _pushLiveTarget(self, noteName):
        freq = self._get_freq_for_note_name(noteName)
        if freq is None:
            return
        self._currentTargetFreq = freq
        self._currentTargetNote = noteName
        if not self._chromaticMode:
            self._liveTuner.configure_target(freq, noteName)

    def _cancelPendingBeepTimer(self):
        """Stop a still-in-flight beep+delayed-speech sequence from an
        earlier round, if any, without touching whatever NVDA is
        currently speaking. This matters because Beep length is now
        user-adjustable up to 5 seconds (see Advanced settings) while a
        live-tuning round is fixed at ~2 seconds - if beep length is set
        close to or longer than the round interval, a new round's result
        can arrive before the previous round's delayed "speak after
        beep" callback has fired. Without cancelling the old one first,
        it would still fire later on its own schedule with a now-stale
        message and could override the newer, correct announcement.
        Called at the start of every new announcement (see
        _onLiveResult) as well as from _cancelPendingLiveAnnouncement
        (the Space-bar handler), which additionally cancels speech."""
        if self._pendingBeepTimer is not None:
            try:
                if self._pendingBeepTimer.IsRunning():
                    self._pendingBeepTimer.Stop()
            except Exception:
                pass
            self._pendingBeepTimer = None
        try:
            self._refEngine.stop()
        except Exception:
            log.error("UniversalTuner: failed to stop in-tune beep", exc_info=True)

    def _cancelPendingLiveAnnouncement(self):
        """Cut off an in-progress "exactly in tune" beep+announcement:
        stops the beep sound immediately, cancels the delayed speak
        callback if it hasn't fired yet, and cancels whatever NVDA is
        speaking right now. Bound to Space bar while live listening is
        on (see onToggleActive above), per user request - sometimes the
        pitch is obviously dead-on before the full beep+announcement
        finishes playing and waiting it out is just friction."""
        self._cancelPendingBeepTimer()
        try:
            import speech
            speech.cancelSpeech()
        except Exception:
            pass

    def _onLiveLost(self):
        """Called (via wx.CallAfter, from LiveTunerController's watchdog)
        if the microphone capture appears to have died unexpectedly while
        live listening was still supposed to be on - e.g. the device was
        unplugged, or WinMM stopped delivering audio buffers. Without
        this, the dialog would keep showing "Live listening: on" forever
        with nothing actually being analysed, and the user would have no
        idea readings had silently stopped. The controller has already
        stopped and released the microphone by the time this runs."""
        if self._dlg:
            try:
                self._dlg.onListeningLost()
            except Exception:
                log.error("UniversalTuner: failed to update dialog after losing the microphone", exc_info=True)
        ui.message(
            _(
                "Live listening stopped: the microphone appears to have disconnected or stopped "
                "responding. Press L to try again."
            )
        )

    def _onLiveResult(self, result, shouldSpeak):
        # Called on the main GUI thread (see LiveTunerController._on_chunk,
        # which wraps this in wx.CallAfter).
        if self._dlg:
            try:
                self._dlg.showLiveResult(result, shouldSpeak)
            except Exception:
                log.error("UniversalTuner: failed to update live status label", exc_info=True)
        if not shouldSpeak:
            return

        # result["message"] is already a fully translated sentence (see
        # tuning_feedback.describe_tuning) that follows NVDA's configured
        # language automatically via gettext, the same way any other NVDA
        # message does.
        message = result.get("message")
        if not message:
            return
        self._lastLiveMessage = message

        # A new announcement is starting - clear out any still-pending
        # beep+delayed-speech sequence from an earlier round first (see
        # _cancelPendingBeepTimer for why this can happen), so it can
        # never fire late with a stale message on top of this one.
        self._cancelPendingBeepTimer()

        # Beep-on-exact-match applies the same way whether chromatic mode
        # is on or off - result["target_freq"] is populated in both cases
        # (fixed string target, or the nearest-note frequency the
        # detected pitch snapped to), so this condition alone already
        # covers both modes. self._beepEnabled ("O" shortcut) is the only
        # gate for whether it plays at all.
        if result.get("direction") == "in_tune" and result.get("target_freq") and self._beepEnabled:
            # Play a beep AT the actual target note's pitch first, so the
            # user can hear for themselves that it really matches - then
            # speak the confirmation once the beep has finished, so the
            # two don't talk over each other.
            try:
                self._refEngine.playOnce(result["target_freq"], duration=self._beepDuration)
            except Exception:
                log.error("UniversalTuner: failed to play in-tune confirmation beep", exc_info=True)

            def _speakAfterBeep(msg=message):
                self._pendingBeepTimer = None
                if _HAVE_SPRI:
                    ui.message(msg, speechPriority=Spri.NOW)
                else:
                    ui.message(msg)

            self._pendingBeepTimer = wx.CallLater(int(self._beepDuration * 1000) + 80, _speakAfterBeep)
        else:
            if _HAVE_SPRI:
                ui.message(message, speechPriority=Spri.NOW)
            else:
                ui.message(message)

    # ------------------------------------------------------------------
    # Frequency / target helpers
    # ------------------------------------------------------------------

    def _get_freq_for_note_name(self, noteName):
        # NOTE: v1.4.26p multiplied this by 2.0, which silently played every
        # reference tone exactly one octave sharp of the note it claimed to
        # be (e.g. selecting "String 6 note E2" played 164.81 Hz, which is
        # E3, instead of the real E2 at 82.41 Hz - standard concert pitch,
        # A4=440Hz). midi_to_freq() alone already returns the correct
        # scientific-pitch frequency for the given note name; found this
        # while reviewing the old code and confirmed against standard
        # tuning references (e.g. guitar low E = 82.41 Hz). Verify by ear
        # on a real machine to be sure, but the math here is unambiguous.
        midi_num = NOTE_TO_MIDI.get(noteName)
        if midi_num is None:
            return None
        return midi_to_freq(midi_num, self._a4)

    def _get_course_target(self, instrument, tuning, courseNumber):
        course_notes = get_notes_for(instrument, tuning)
        count = len(course_notes)
        if courseNumber < 1 or courseNumber > count:
            return None

        idx = count - int(courseNumber)
        primaryNote = course_notes[idx]
        primaryMidi = NOTE_TO_MIDI.get(primaryNote)
        if primaryMidi is None:
            return None

        secondaryNote = None
        mode = PAIRED_INSTRUMENT_MODES.get(instrument)

        if mode == "guitar12":
            if idx <= 3:
                secondaryNote = midi_to_note_name(primaryMidi + 12)
                if secondaryNote is None:
                    secondaryNote = primaryNote
            else:
                secondaryNote = primaryNote
        elif mode == "unison_pairs":
            secondaryNote = primaryNote

        return {
            "primaryNote": primaryNote,
            "secondaryNote": secondaryNote,
            "isPaired": bool(mode),
            "courseNumber": int(courseNumber),
        }

    # ------------------------------------------------------------------
    # Reference-tone playback (unchanged behaviour from v1.4.26p)
    # ------------------------------------------------------------------

    def _playNote(self, noteName, freq):
        """Single shared entry point for actually starting reference-tone
        playback, used by both the Selection-dropdown path (play_selection)
        and the number-key/course path (play_course) - previously these
        tracked "what's currently playing" separately (_previewKey vs
        _lastCourseKey), so Space bar's stop/toggle logic could miss a note
        that had been started via the other path. Now there is exactly one
        notion of "what's currently sounding"."""
        self._refEngine.stop()
        self._refEngine.start(freq)
        self._previewActive = True

        ui.message(_("Playing %s") % noteName)
        if self._dlg:
            wx.CallAfter(self._dlg.setStatus, _("Playing %s") % noteName)

    def _playNoteOnceForListening(self, noteName, freq):
        """Number-key/course path while live listening is on. Per user
        feedback: while listening, a number-key press is for picking
        which note to check the microphone against, not for tuning by
        ear - looping the reference tone until Space is pressed was
        confusing (and, after the Space bar started doubling as the
        "cancel in-tune announcement" key in v2.4.0, there was no longer
        an easy way to stop it without turning listening off first).
        Plays a single short cue instead - press the same or another
        number key again to hear it again, or Space to cut it off early.
        Reuses the beep-length setting for how long the cue lasts, since
        this is meant as a brief confirmation, not a sustained tone to
        tune by ear."""
        self._refEngine.stop()
        try:
            self._refEngine.playOnce(freq, duration=self._beepDuration)
        except Exception:
            log.error("UniversalTuner: failed to play one-shot note cue during live listening", exc_info=True)
        ui.message(_("Playing %s") % noteName)
        if self._dlg:
            wx.CallAfter(self._dlg.setStatus, _("Playing %s") % noteName)

    def _announceSelectionOnlyForListening(self, noteName):
        """Number-key/course path while live listening AND chromatic mode
        are both on. Chromatic mode always compares against whatever note
        is nearest to what's actually heard, ignoring which string is
        "selected" - so per user feedback, there's no need to play that
        string's reference tone at all here; just confirm the selection
        by speech."""
        ui.message(_("Selected %s") % noteName)
        if self._dlg:
            wx.CallAfter(self._dlg.setStatus, _("Selected %s") % noteName)

    # play_selection() was removed here - it's superseded by the unified
    # _playNote()/onToggleActive() design: the Selection dropdown's
    # onSelectionTargetChanged callback already resolves the note and
    # calls _pushLiveTarget(), and Space bar (onToggleActive) just plays
    # whatever that shared target currently is. Nothing calls the old
    # dropdown-specific play path anymore.

    def play_course(self, instrument, tuning, courseNumber):
        target = self._get_course_target(instrument, tuning, courseNumber)
        if not target:
            ui.message(_("Invalid selection"))
            return None

        primaryNote = target["primaryNote"]
        secondaryNote = target["secondaryNote"]
        isPaired = target["isPaired"]

        key = ("course", instrument, tuning, int(courseNumber))

        if isPaired:
            if self._lastCourseKey == key:
                self._courseToggle = 1 - self._courseToggle
            else:
                self._lastCourseKey = key
                self._courseToggle = 0
        else:
            self._lastCourseKey = None
            self._courseToggle = 0

        playNote = primaryNote
        if isPaired and self._courseToggle == 1 and secondaryNote is not None:
            playNote = secondaryNote

        playFreq = self._get_freq_for_note_name(playNote)
        if playFreq is None:
            ui.message(_("Invalid selection"))
            return None

        self._instrument = instrument
        self._tuning = tuning
        # Number-key plays now update the same shared target the Selection
        # dropdown uses, so Space bar and the live tuner both follow
        # whichever note was most recently triggered - by dropdown
        # navigation or by a number key, whichever happened last.
        self._pushLiveTarget(playNote)

        if self._liveTuner.isRunning():
            if self._chromaticMode:
                self._announceSelectionOnlyForListening(playNote)
            else:
                self._playNoteOnceForListening(playNote, playFreq)
        else:
            self._playNote(playNote, playFreq)

        return playNote

    def stop(self):
        wasActive = self._previewActive
        self._cancelPendingLiveAnnouncement()
        self._refEngine.stop()
        self._previewActive = False
        self._lastCourseKey = None
        self._courseToggle = 0
        if self._dlg:
            wx.CallAfter(self._dlg.setStatus, _("Idle"))
        if wasActive:
            ui.message(_("Playback stopped"))
