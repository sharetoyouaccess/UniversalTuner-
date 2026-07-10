# -*- coding: utf-8 -*-
"""
Reference-tone playback engine. Behaviour is unchanged from the original
single-file add-on (v1.4.26p) - this is the same design (generate a short
WAV per frequency/params combination, cache it on disk, loop it with
winsound), just moved into its own module. One small fix from the
original: temp wav files are now cleaned up on shutdown instead of being
left behind under %TEMP%\\nvda_universal_tuner forever.
"""
import math
import threading
import struct
import wave
import os
import tempfile
import time
import winsound


class ReferenceToneEngine(object):
    def __init__(self):
        self._running = False
        self._thread = None
        self._sr = 44100
        self._duration = 2.0
        self._gap = 0.15
        self._volume = 0.22
        self._lock = threading.Lock()
        self._currentFreq = None
        self._stopEvent = threading.Event()
        self._cache = {}
        self._cacheLock = threading.Lock()
        self._lastError = None
        self._tempDir = os.path.join(tempfile.gettempdir(), "nvda_universal_tuner")
        if not os.path.isdir(self._tempDir):
            try:
                os.makedirs(self._tempDir)
            except Exception:
                pass

    def setParams(self, sampleRate=None, duration=None, gap=None, volume=None):
        with self._lock:
            if sampleRate is not None:
                self._sr = int(sampleRate)
                self._clearCache()
            if duration is not None:
                self._duration = max(0.2, min(10.0, float(duration)))
                self._clearCache()
            if gap is not None:
                self._gap = max(0.0, min(5.0, float(gap)))
            if volume is not None:
                self._volume = max(0.01, min(1.0, float(volume)))
                self._clearCache()

    def getParams(self):
        with self._lock:
            return {
                "sampleRate": self._sr,
                "duration": self._duration,
                "gap": self._gap,
                "volume": self._volume,
            }

    def _clearCache(self):
        with self._cacheLock:
            for path in self._cache.values():
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except Exception:
                    pass
            self._cache = {}

    def start(self, freq):
        with self._lock:
            self._currentFreq = float(freq)
        if self._running:
            return
        self._running = True
        self._stopEvent.clear()
        self._thread = threading.Thread(target=self._loop)
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        self._running = False
        self._stopEvent.set()
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def shutdown(self):
        """Stop playback and remove all cached wav files. Call this from
        the GlobalPlugin's terminate() so repeated NVDA restarts don't
        leave an ever-growing pile of tone files under %TEMP%."""
        self.stop()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._clearCache()
        try:
            if os.path.isdir(self._tempDir) and not os.listdir(self._tempDir):
                os.rmdir(self._tempDir)
        except Exception:
            pass

    def _make_cache_key(self, freq):
        params = self.getParams()
        return (
            round(float(freq), 3),
            int(params["sampleRate"]),
            float(params["duration"]),
            float(params["volume"]),
        )

    def _render_wave_file(self, path, freq, sr, duration, volume):
        """Shared WAV-rendering math, used both for the looping reference
        tone and for one-shot beeps (see playOnce()) so there is exactly
        one place that generates a sine tone with fade-in/out."""
        nframes = int(sr * duration)
        fade_len = max(1, int(sr * 0.01))
        frames = bytearray()
        for i in range(nframes):
            t = float(i) / float(sr)
            s = math.sin(2.0 * math.pi * float(freq) * t)
            gain = 1.0
            if i < fade_len:
                gain = float(i) / float(fade_len)
            elif i >= nframes - fade_len:
                remain = max(0, nframes - i - 1)
                gain = float(remain) / float(fade_len)
            sample = int(max(-1.0, min(1.0, s * volume * gain)) * 32767.0)
            frames.extend(struct.pack("<h", sample))

        wf = wave.open(path, "wb")
        try:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(bytes(frames))
        finally:
            wf.close()

    def _cacheInsert(self, key, path):
        """Shared cache-bookkeeping for both the looping reference tone
        (_make_wave_path) and one-shot beeps (playOnce) - both write into
        the same self._cache dict, so the eviction cap needs to live here
        rather than being duplicated (and, before this fix, only actually
        applied) in _make_wave_path alone. That gap mattered little while
        playOnce() was only used for the rare "exactly in tune" beep, but
        v2.4.2 started calling playOnce() for every number-key press
        during live listening too (a different target frequency each
        time) - without a shared cap, that path alone could accumulate an
        unbounded number of tiny .wav files under %TEMP% over a long
        session."""
        with self._cacheLock:
            if len(self._cache) > 24:
                try:
                    old_key = next(iter(self._cache))
                    old_path = self._cache.pop(old_key)
                    if old_path != path and os.path.isfile(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass
                except Exception:
                    pass
            self._cache[key] = path

    def _make_wave_path(self, freq):
        key = self._make_cache_key(freq)
        with self._cacheLock:
            cached = self._cache.get(key)
            if cached and os.path.isfile(cached):
                return cached

        params = self.getParams()
        sr = int(params["sampleRate"])
        duration = float(params["duration"])
        volume = float(params["volume"])

        safe_name = "tone_%0.3f_%d_%0.2f_%0.2f.wav" % (
            round(float(freq), 3),
            sr,
            duration,
            volume,
        )
        safe_name = safe_name.replace(".", "_")
        path = os.path.join(self._tempDir, safe_name)

        if not os.path.isfile(path):
            self._render_wave_file(path, freq, sr, duration, volume)

        self._cacheInsert(key, path)
        return path

    def playOnce(self, freq, duration=0.6):
        """Play a single short beep at `freq` and return immediately (no
        looping, no repeat/gap scheduling thread) - used both for the
        "you're exactly in tune" confirmation sound and, since v2.4.2,
        for the brief note cue played on a number-key press while live
        listening is on. Reuses the same cache dict as the looping tones
        (keyed separately by duration, so it never collides with the
        user's chosen loop duration) and the user's current
        volume/sample-rate settings, for a consistent sound. Safe to call
        even while the looping engine is stopped (it should always be
        stopped before this - see callers) since this bypasses the loop
        thread entirely and just calls winsound.PlaySound once."""
        params = self.getParams()
        sr = int(params["sampleRate"])
        volume = float(params["volume"])
        key = ("oneshot", round(float(freq), 3), sr, float(duration), volume)

        with self._cacheLock:
            cached = self._cache.get(key)
            if cached and os.path.isfile(cached):
                path = cached
            else:
                path = None

        if path is None:
            safe_name = "beep_%0.3f_%d_%0.2f_%0.2f.wav" % (round(float(freq), 3), sr, duration, volume)
            safe_name = safe_name.replace(".", "_")
            path = os.path.join(self._tempDir, safe_name)
            if not os.path.isfile(path):
                self._render_wave_file(path, freq, sr, duration, volume)
            self._cacheInsert(key, path)

        try:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            pass

    def _wait_until_finished_or_stopped(self, seconds):
        if seconds <= 0:
            return not self._stopEvent.is_set()
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self._stopEvent.wait(0.01):
                return False
        return not self._stopEvent.is_set()

    def _loop(self):
        try:
            while self._running and not self._stopEvent.is_set():
                with self._lock:
                    freq = self._currentFreq
                    duration = self._duration
                    gap = self._gap
                if not freq:
                    self._stopEvent.wait(0.05)
                    continue

                wavePath = self._make_wave_path(freq)
                winsound.PlaySound(
                    wavePath,
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
                )
                if not self._wait_until_finished_or_stopped(duration):
                    break
                try:
                    winsound.PlaySound(None, winsound.SND_PURGE)
                except Exception:
                    pass
                if not self._wait_until_finished_or_stopped(gap):
                    break
        except Exception as e:
            self._lastError = str(e)
        finally:
            self._running = False
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
