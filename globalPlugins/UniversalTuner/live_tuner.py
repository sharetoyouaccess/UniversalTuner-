      # -*- coding: utf-8 -*-
"""
Live microphone tuning: ties mic_capture + pitch_detect + tuning_feedback
together.

Split deliberately into two layers:

  - LiveTunerCore: pure decision logic (rolling buffer management, target
    selection, speech throttling). No threading, no wx, no NVDA imports -
    fully unit testable with synthetic sample chunks and a fake clock.
  - LiveTunerController: thin real-world wrapper that owns a WaveInRecorder
    and marshals results back to the UI thread via wx.CallAfter. This part
    could not be exercised in an automated test in the original sandbox
    development environment (no real mic/Windows there), which is why it
    was kept thin. As of v2.5.3 it has been manually tested end-to-end on
    a real NVDA + Windows machine (live microphone tuning, chromatic mode,
    the L/C/O/R shortcuts, and microphone device switching all confirmed
    working there), consistent with the testing-status notes in
    __init__.py and mic_capture.py.
"""
import threading
import time

from .pitch_detect import detect_pitch, decimate
from .tuning_feedback import describe_tuning, nearest_note_frequency, freq_to_cents
from .instruments import midi_to_note_name
from .mic_capture import WaveInRecorder, pcm16_bytes_to_floats

try:
    from logHandler import log
except Exception:  # pragma: no cover - only importable inside NVDA
    import logging
    log = logging.getLogger("UniversalTuner.live_tuner")


class LiveTunerCore(object):
    """Discrete-round live tuning: rather than a continuously streaming
    readout, the mic is analysed for one fixed-length ROUND, and at the
    end of that round a single result is reported (spoken + live label
    update) - by design, per the user's own request: reporting too fast
    or too often makes it unclear which pluck/attempt a given announcement
    is even about. Each round's announcement clearly covers "whatever you
    played in roughly the last ROUND_SECONDS."

    Within a round, small-scale attack-transient rejection still runs
    continuously (see _updateStability) so that a round's result reflects
    the settled note, not a stray noise spike right after a pluck."""

    CAPTURE_RATE = 44100
    DECIMATE_FACTOR = 5              # -> ~8820 Hz effective analysis rate
    ANALYSIS_WINDOW_SECONDS = 0.22    # ~7 cycles even for the lowest note (B0, 30.87Hz)
    CHROMATIC_FMIN = 27.0
    CHROMATIC_FMAX = 2000.0
    TARGETED_RANGE_RATIO = 1.6

    # One report every ROUND_SECONDS - chosen with the user so that a
    # listener can always tell "this announcement is about what I just
    # played", without waiting so long it feels unresponsive. Lowered
    # from the original 2.5s to 2.0s per user feedback after real-world
    # testing - 2.0s still gives at least ~9 analysis windows to settle
    # on a stable reading (ANALYSIS_WINDOW_SECONDS=0.22s at
    # DETECTION_INTERVAL_SECONDS=0.15s spacing) while feeling snappier.
    ROUND_SECONDS = 2.0

    # Detection attempts within a round don't need to run on every single
    # ~50ms audio chunk - that's more CPU than a tuner needs and doesn't
    # change what gets reported at the round boundary anyway (only the
    # *last* stable reading in the round is used).
    DETECTION_INTERVAL_SECONDS = 0.15

    # Anti-jumpiness (reject transient/attack noise): the first ~100-200ms
    # right after a pluck is often noisy/inharmonic before the note
    # settles. Requiring two consecutive detections to agree closely
    # before trusting a reading filters that out.
    STABILITY_TOLERANCE_CENTS = 4.0
    STABILITY_MIN_COUNT = 2

    # Confidence gate on the raw autocorrelation peak (0..1), separate
    # from and in addition to the stability check above. A single clean
    # note - even with realistic harmonics, string inharmonicity, mic
    # hum, or clipping - consistently scores 0.89+ in testing. Two
    # simultaneous notes at comparable volume (e.g. an adjacent string
    # bleeding in almost as loud as the one being tuned) can score as low
    # as ~0.60 and, worse, can do so *consistently* enough to slip past
    # the stability check and get confidently reported as a wrong
    # reading - found via adversarial testing with synthetic two-tone
    # mixtures. Raising the bar here trades "reports nothing when truly
    # ambiguous" for "never confidently reports a wrong note", which is
    # the right trade for a tuning tool.
    CONFIDENCE_THRESHOLD = 0.85

    # Per user feedback: while a note keeps ringing/sustaining across
    # several rounds without changing, don't keep repeating the exact
    # same beep+announcement every ROUND_SECONDS - that reads as
    # unwanted noise when the user already heard the confirmation once
    # and just wants to check again on demand (the "R" shortcut). Only
    # re-announce automatically once the reading has moved by more than
    # this many cents (or the note name/direction changed) since the
    # last thing actually announced.
    ANNOUNCE_REPEAT_TOLERANCE_CENTS = 3.0

    def __init__(self, capture_rate=None):
        self.capture_rate = capture_rate or self.CAPTURE_RATE
        self._rolling = []
        self._max_rolling_len = int(self.capture_rate * self.ANALYSIS_WINDOW_SECONDS)
        self.chromatic = False
        self.target_freq = None
        self.target_note = None
        self.a4 = 440.0

        self._last_detection_attempt_time = None
        self._last_raw_freq = None
        self._stable_count = 0

        self._round_start_time = None
        self._round_candidate = None  # most recent stable (freq, note_name) seen this round
        self._lastAnnounced = None  # {"note_name", "direction", "cents"} of the last spoken result

    def configure_target(self, freq, note_name):
        self.chromatic = False
        self.target_freq = freq
        self.target_note = note_name

    def configure_chromatic(self, a4=440.0):
        self.chromatic = True
        self.target_freq = None
        self.target_note = None
        self.a4 = a4

    def reset(self):
        self._rolling = []
        self._last_detection_attempt_time = None
        self._last_raw_freq = None
        self._stable_count = 0
        self._round_start_time = None
        self._round_candidate = None
        self._lastAnnounced = None

    def _isSameAsLastAnnounced(self, result):
        prev = self._lastAnnounced
        if prev is None:
            return False
        if result.get("note_name") != prev.get("note_name"):
            return False
        if result.get("direction") != prev.get("direction"):
            return False
        prevCents = prev.get("cents")
        curCents = result.get("cents")
        if prevCents is None or curCents is None:
            return False
        return abs(curCents - prevCents) <= self.ANNOUNCE_REPEAT_TOLERANCE_CENTS

    def _shouldAttemptDetection(self, now):
        if self._last_detection_attempt_time is None:
            return True
        return (now - self._last_detection_attempt_time) >= self.DETECTION_INTERVAL_SECONDS

    def _updateStability(self, detected_freq):
        if self._last_raw_freq is not None:
            drift = abs(freq_to_cents(detected_freq, self._last_raw_freq) or 0.0)
            if drift <= self.STABILITY_TOLERANCE_CENTS:
                self._stable_count += 1
            else:
                self._stable_count = 1
        else:
            self._stable_count = 1
        self._last_raw_freq = detected_freq
        return self._stable_count >= self.STABILITY_MIN_COUNT

    def _resolveTarget(self, detected_freq):
        """Returns (compare_target_freq, note_name) for a stable detected
        frequency, honouring chromatic vs fixed-target mode."""
        if self.chromatic:
            nearest_freq, midi = nearest_note_frequency(detected_freq, a4=self.a4)
            note_name = midi_to_note_name(midi) if midi is not None else None
            return nearest_freq, note_name
        return self.target_freq, self.target_note

    def process_chunk(self, floats, now=None):
        """floats: new samples at self.capture_rate.
        now: current time.time()-style timestamp (injectable for tests).

        Returns (result_dict_or_None, should_speak_bool).

        result_dict is returned (for a live on-screen numeric display)
        whenever a stable reading exists *within the current round*, even
        when should_speak is False. should_speak is only True once, right
        when a round boundary is crossed and that round had a stable
        candidate to report - this is the only time the caller should
        call ui.message()/play the confirmation beep.
        """
        if now is None:
            now = time.time()

        if self._round_start_time is None:
            self._round_start_time = now

        self._rolling.extend(floats)
        if len(self._rolling) > self._max_rolling_len:
            self._rolling = self._rolling[-self._max_rolling_len:]

        live_result = None

        if len(self._rolling) >= self._max_rolling_len and self._shouldAttemptDetection(now):
            self._last_detection_attempt_time = now

            if not self.chromatic and self.target_freq:
                fmin = max(20.0, self.target_freq / self.TARGETED_RANGE_RATIO)
                fmax = self.target_freq * self.TARGETED_RANGE_RATIO
            else:
                fmin, fmax = self.CHROMATIC_FMIN, self.CHROMATIC_FMAX

            decimated = decimate(self._rolling, self.DECIMATE_FACTOR)
            analysis_rate = self.capture_rate // self.DECIMATE_FACTOR
            detected = detect_pitch(
                decimated, analysis_rate, fmin=fmin, fmax=fmax,
                confidence_threshold=self.CONFIDENCE_THRESHOLD,
            )

            if detected is not None and self._updateStability(detected):
                compare_target, note_name = self._resolveTarget(detected)
                if compare_target:
                    result = describe_tuning(detected, compare_target, note_name=note_name)
                    if result is not None:
                        self._round_candidate = result
                        live_result = result

        should_speak = False
        if (now - self._round_start_time) >= self.ROUND_SECONDS:
            final_result = self._round_candidate
            # Start the next round fresh regardless of whether this one
            # had anything to report.
            self._round_start_time = now
            self._round_candidate = None
            self._stable_count = 0
            self._last_raw_freq = None

            if final_result is None:
                # Signal dropped out this round (string rang out, user
                # stopped playing, or nothing stable was detected) -
                # clear the "already announced" gate so the very next
                # pluck's first stable reading always gets announced
                # fresh, even if it lands on the same note/direction as
                # whatever was last announced before the pause.
                self._lastAnnounced = None
                return None, False

            if self._isSameAsLastAnnounced(final_result):
                # Same note, same direction, barely-changed cents as the
                # last thing actually spoken - still update the on-screen
                # numeric readout (the caller does this regardless of
                # should_speak) but don't re-announce; press "R" to hear
                # it again on demand.
                return final_result, False

            self._lastAnnounced = {
                "note_name": final_result.get("note_name"),
                "direction": final_result.get("direction"),
                "cents": final_result.get("cents"),
            }
            return final_result, True

        return live_result, should_speak


class LiveTunerController(object):
    """Real-world wrapper: owns the mic recorder thread and dispatches
    results to the caller-supplied on_result(result, should_speak)
    callback via wx.CallAfter so it always runs on NVDA's main GUI thread,
    same as every other UI update in this add-on.

    Not covered by the automated unit tests (there is no microphone or
    Windows audio stack in the development sandbox those run in), but as
    of v2.5.2 has been manually tested end-to-end on a real NVDA +
    Windows machine and confirmed working there."""

    # How often the watchdog checks whether the capture pipeline still
    # looks alive while listening is supposedly on.
    WATCHDOG_INTERVAL_MS = 1000

    # If no chunk at all - silence or not, WinMM completes buffers on a
    # timer regardless of audio content - has arrived in this long, treat
    # the capture pipeline as dead (device unplugged, driver crashed,
    # etc.) rather than "just a quiet room". A healthy mic keeps
    # delivering ~50ms buffers continuously even with nothing playing.
    MAX_SILENCE_SECONDS = 3.0

    def __init__(self, on_result, on_lost=None):
        self._core = LiveTunerCore()
        self._recorder = WaveInRecorder(sample_rate=LiveTunerCore.CAPTURE_RATE, buffer_ms=50)
        self._on_result = on_result
        # Called (via wx.CallAfter, so always on the main GUI thread) if
        # the watchdog decides the microphone capture has died
        # unexpectedly while the caller still thinks listening is on -
        # e.g. the device was unplugged mid-session. Without this, there
        # was previously no way for the caller to ever find out; the
        # dialog would keep showing "Live listening: on" forever with
        # nothing actually being analysed.
        self._on_lost = on_lost
        self._running = False
        self._lastChunkTime = None
        self._watchdogTimer = None
        # LiveTunerCore's internal state (rolling buffer, round timer,
        # target) is mutated both by _on_chunk() on the mic capture
        # thread and by configure_target()/configure_chromatic() on the
        # main GUI thread (e.g. the user changes the selected string or
        # toggles chromatic mode while listening is active) - this lock
        # makes those two sides mutually exclusive so the core is never
        # read/written from two threads at once.
        self._coreLock = threading.Lock()

    def configure_target(self, freq, note_name):
        with self._coreLock:
            self._core.configure_target(freq, note_name)
            self._core.reset()

    def configure_chromatic(self, a4=440.0):
        with self._coreLock:
            self._core.configure_chromatic(a4)
            self._core.reset()

    def set_device(self, device_id):
        """Choose which microphone device the *next* start() call opens
        (changing the device on an already-open capture has no effect
        until listening is stopped and started again). device_id is
        None for "use whatever Windows currently treats as the default
        recording device"."""
        self._recorder.setDeviceId(device_id)

    def start(self):
        if self._running:
            return True
        try:
            self._recorder.start(self._on_chunk)
        except Exception:
            log.error("UniversalTuner: failed to start microphone capture", exc_info=True)
            return False
        self._running = True
        self._lastChunkTime = time.time()
        self._scheduleWatchdog()
        return True

    def stop(self):
        self._running = False
        self._cancelWatchdog()
        try:
            self._recorder.stop()
        except Exception:
            log.error("UniversalTuner: failed to stop microphone capture", exc_info=True)
        with self._coreLock:
            self._core.reset()

    def isRunning(self):
        return self._running

    def lastError(self):
        """Best-effort diagnostic string from the last failed start()
        attempt (e.g. no microphone device, device busy) - surfaced to
        the user in onToggleListen()'s failure message instead of a
        generic "could not start" with no explanation."""
        return self._recorder.lastError()

    def _cancelWatchdog(self):
        if self._watchdogTimer is not None:
            try:
                if self._watchdogTimer.IsRunning():
                    self._watchdogTimer.Stop()
            except Exception:
                pass
            self._watchdogTimer = None

    def _scheduleWatchdog(self):
        try:
            import wx
        except Exception:  # pragma: no cover - no wx outside real NVDA
            return
        self._watchdogTimer = wx.CallLater(self.WATCHDOG_INTERVAL_MS, self._checkHealth)

    def _checkHealth(self):
        """Runs on the main GUI thread (wx.CallLater semantics) roughly
        once a second while listening is on. Two independent signals of
        "the capture pipeline died": the recorder's own background
        thread already gave up (isRunning() went False on its own,
        e.g. the WinMM capture loop hit a fatal error), or no buffer has
        arrived in a suspiciously long time (the thread is technically
        alive but WinMM has silently stopped delivering audio - observed
        as a real failure mode with some USB audio devices on
        disconnect)."""
        if not self._running:
            return  # stopped normally (or already handled) in the meantime

        deadRecorder = not self._recorder.isRunning()
        silentTooLong = (
            self._lastChunkTime is not None
            and (time.time() - self._lastChunkTime) > self.MAX_SILENCE_SECONDS
        )

        if deadRecorder or silentTooLong:
            log.error(
                "UniversalTuner: microphone capture appears to have died "
                "(recorder running=%s, seconds since last chunk=%s) - "
                "stopping live listening"
                % (
                    self._recorder.isRunning(),
                    (time.time() - self._lastChunkTime) if self._lastChunkTime is not None else None,
                )
            )
            self.stop()
            if self._on_lost:
                try:
                    import wx
                    wx.CallAfter(self._on_lost)
                except Exception:
                    log.error("UniversalTuner: failed to dispatch on_lost callback", exc_info=True)
            return

        self._scheduleWatchdog()

    def _on_chunk(self, data, sample_rate):
        if not self._running:
            return
        self._lastChunkTime = time.time()
        try:
            floats = pcm16_bytes_to_floats(data)
            with self._coreLock:
                result, should_speak = self._core.process_chunk(floats)
        except Exception:
            log.error("UniversalTuner: live tuner processing failed", exc_info=True)
            return
        if result is None:
            return
        try:
            import wx
            wx.CallAfter(self._on_result, result, should_speak)
        except Exception:
            log.error("UniversalTuner: failed to dispatch live tuner result to UI thread", exc_info=True)
