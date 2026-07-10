"""
Minimal WinMM (waveIn) microphone capture, pure ctypes - no pyaudio/numpy or
any other third-party dependency, matching the rest of this add-on's
dependency style (stdlib + wx + winsound only).

WHY NOT A HIGHER-LEVEL LIBRARY: NVDA's bundled Python does not ship
pyaudio/sounddevice, and add-ons can't rely on pip-installed packages being
present on the end user's machine, so raw WinMM via ctypes is the only
dependency-free way to read microphone audio inside an NVDA add-on.

TESTING STATUS: this file talks to ctypes.windll.winmm and
ctypes.windll.kernel32, which only exist on real Windows, so it could not
be exercised in the original sandbox development environment - it was
only reviewed against the documented WinMM API at that stage. As of
v2.5.2 it has been manually tested on a real NVDA + Windows machine
(microphone open/close, live capture, device switching, and disconnect
handling all confirmed working there). That covers one
hardware/microphone/Windows configuration, not the full range of audio
devices in the wild - treat any bug report about crackling audio,
silence, crashes, or hangs from a different setup as more reliable than
anything asserted here.
"""
import ctypes
import threading
import time

try:
    from logHandler import log
except Exception:  # pragma: no cover - only importable inside NVDA
    import logging
    log = logging.getLogger("UniversalTuner.mic_capture")


WAVE_MAPPER = 0xFFFFFFFF          # -1 as an unsigned UINT device id
CALLBACK_EVENT = 0x00050000
WAVE_FORMAT_PCM = 1
WHDR_DONE = 0x00000001
MMSYSERR_NOERROR = 0
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
INFINITE = 0xFFFFFFFF


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", ctypes.c_ushort),
        ("nChannels", ctypes.c_ushort),
        ("nSamplesPerSec", ctypes.c_uint32),
        ("nAvgBytesPerSec", ctypes.c_uint32),
        ("nBlockAlign", ctypes.c_ushort),
        ("wBitsPerSample", ctypes.c_ushort),
        ("cbSize", ctypes.c_ushort),
    ]


class WAVEHDR(ctypes.Structure):
    pass


WAVEHDR._fields_ = [
    ("lpData", ctypes.c_void_p),
    ("dwBufferLength", ctypes.c_uint32),
    ("dwBytesRecorded", ctypes.c_uint32),
    ("dwUser", ctypes.c_void_p),
    ("dwFlags", ctypes.c_uint32),
    ("dwLoops", ctypes.c_uint32),
    ("lpNext", ctypes.c_void_p),
    ("reserved", ctypes.c_void_p),
]


MAXPNAMELEN = 32  # WinMM's historical fixed-length device-name buffer size


class WAVEINCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_ushort),
        ("wPid", ctypes.c_ushort),
        ("vDriverVersion", ctypes.c_uint32),
        ("szPname", ctypes.c_wchar * MAXPNAMELEN),
        ("dwFormats", ctypes.c_uint32),
        ("wChannels", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
    ]


class MicCaptureError(Exception):
    pass


def list_input_devices():
    """Return [(deviceId, deviceName), ...] for every waveIn-capable
    device Windows currently sees, in device-ID order. Device IDs are
    NOT stable across reboots or reconnections (Windows just assigns
    them 0..N-1 in whatever order it currently enumerates devices), so
    callers should persist the device NAME and re-resolve it to an ID
    at connect time via find_device_id_by_name() - see settings.py's
    micDeviceName. Device names longer than 31 characters are truncated
    by WinMM itself (MAXPNAMELEN is a decades-old fixed buffer size in
    the Windows API, not a limitation added here).

    Returns an empty list if WinMM isn't available (e.g. this sandbox)
    or on any enumeration failure, so callers can safely treat that the
    same as "no devices found, fall back to Default"."""
    try:
        winmm = ctypes.windll.winmm
    except Exception:
        return []
    try:
        winmm.waveInGetNumDevs.restype = ctypes.c_uint32
        winmm.waveInGetNumDevs.argtypes = []
        winmm.waveInGetDevCapsW.restype = ctypes.c_uint32
        winmm.waveInGetDevCapsW.argtypes = [
            ctypes.c_uint32, ctypes.POINTER(WAVEINCAPSW), ctypes.c_uint32,
        ]

        count = winmm.waveInGetNumDevs()
        devices = []
        for device_id in range(count):
            caps = WAVEINCAPSW()
            result = winmm.waveInGetDevCapsW(device_id, ctypes.byref(caps), ctypes.sizeof(caps))
            if result == MMSYSERR_NOERROR:
                devices.append((device_id, caps.szPname))
            else:
                devices.append((device_id, "Microphone %d" % device_id))
        return devices
    except Exception:
        log.error("UniversalTuner: failed to enumerate microphone devices", exc_info=True)
        return []


def find_device_id_by_name(name):
    """Resolve a persisted device name back to whatever waveIn device ID
    currently matches it. Returns None (meaning "use the system default
    recording device") if name is empty, or if no currently-connected
    device matches it (e.g. it was unplugged) - callers should treat
    None as a safe, always-valid fallback rather than an error."""
    if not name:
        return None
    for device_id, device_name in list_input_devices():
        if device_name == name:
            return device_id
    return None


class WaveInRecorder(object):
    """Captures mono 16-bit PCM from the default microphone in small
    chunks, using a small ring of buffers so recording never has to stop
    to hand data to the caller. Call start(on_chunk), where on_chunk(bytes,
    sample_rate) is invoked from a background thread every ~buffer_ms of
    audio - keep that callback fast and non-blocking (it should just push
    into a queue/list), same discipline as any audio callback."""

    NUM_BUFFERS = 4

    def __init__(self, sample_rate=22050, buffer_ms=100, device_id=None):
        self._sample_rate = int(sample_rate)
        self._buffer_ms = int(buffer_ms)
        # None = WAVE_MAPPER (whatever Windows currently treats as the
        # default recording device). Only takes effect on the *next*
        # start() - changing it while already capturing does nothing
        # until stop()+start() reopens the device.
        self._device_id = device_id
        self._hwi = ctypes.c_void_p(0)
        self._event = None
        self._buffers = []       # list of (WAVEHDR, ctypes buffer) tuples, kept alive
        self._thread = None
        self._running = False
        self._on_chunk = None
        self._winmm = None
        self._kernel32 = None
        self._lastError = None

    def setDeviceId(self, device_id):
        self._device_id = device_id

    def _check(self, mmresult, what):
        if mmresult != MMSYSERR_NOERROR:
            raise MicCaptureError("%s failed, MMRESULT=%d" % (what, mmresult))

    def _bindApiSignatures(self):
        """Declare argtypes/restype explicitly for every winmm/kernel32
        call used here. Without this, ctypes falls back to a default
        return type of plain c_int for every call - on 64-bit Windows a
        HANDLE or other pointer-sized value is 8 bytes, and a call with
        no declared restype can have its return value silently
        misinterpreted/truncated. This costs nothing and removes a class
        of subtle, hard-to-diagnose corruption that would only show up on
        certain systems."""
        HWAVEIN = ctypes.c_void_p
        LPWAVEFORMATEX = ctypes.POINTER(WAVEFORMATEX)
        LPWAVEHDR = ctypes.POINTER(WAVEHDR)
        DWORD_PTR = ctypes.c_void_p
        UINT = ctypes.c_uint32
        MMRESULT = ctypes.c_uint32

        self._kernel32.CreateEventW.restype = ctypes.c_void_p
        self._kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
        self._kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        self._kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self._kernel32.CloseHandle.restype = ctypes.c_int
        self._kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

        self._winmm.waveInOpen.restype = MMRESULT
        self._winmm.waveInOpen.argtypes = [
            ctypes.POINTER(HWAVEIN), UINT, LPWAVEFORMATEX, DWORD_PTR, DWORD_PTR, ctypes.c_uint32,
        ]
        self._winmm.waveInPrepareHeader.restype = MMRESULT
        self._winmm.waveInPrepareHeader.argtypes = [HWAVEIN, LPWAVEHDR, UINT]
        self._winmm.waveInAddBuffer.restype = MMRESULT
        self._winmm.waveInAddBuffer.argtypes = [HWAVEIN, LPWAVEHDR, UINT]
        self._winmm.waveInStart.restype = MMRESULT
        self._winmm.waveInStart.argtypes = [HWAVEIN]
        self._winmm.waveInStop.restype = MMRESULT
        self._winmm.waveInStop.argtypes = [HWAVEIN]
        self._winmm.waveInReset.restype = MMRESULT
        self._winmm.waveInReset.argtypes = [HWAVEIN]
        self._winmm.waveInUnprepareHeader.restype = MMRESULT
        self._winmm.waveInUnprepareHeader.argtypes = [HWAVEIN, LPWAVEHDR, UINT]
        self._winmm.waveInClose.restype = MMRESULT
        self._winmm.waveInClose.argtypes = [HWAVEIN]

    def _teardownPartialStart(self):
        """Best-effort cleanup after start() fails partway through, so a
        failed attempt never leaks a device/event handle and a later
        retry (pressing L again) always begins from a genuinely clean
        state instead of piling a second open on top of a leaked one."""
        for hdr, buf in self._buffers:
            try:
                self._winmm.waveInUnprepareHeader(self._hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))
            except Exception:
                pass
        self._buffers = []

        if self._hwi and self._winmm:
            try:
                self._winmm.waveInClose(self._hwi)
            except Exception:
                pass
        self._hwi = ctypes.c_void_p(0)

        if self._event and self._kernel32:
            try:
                self._kernel32.CloseHandle(self._event)
            except Exception:
                pass
        self._event = None

        self._running = False

    def start(self, on_chunk):
        if self._running:
            return
        self._on_chunk = on_chunk
        self._winmm = ctypes.windll.winmm
        self._kernel32 = ctypes.windll.kernel32
        self._bindApiSignatures()

        try:
            wfx = WAVEFORMATEX()
            wfx.wFormatTag = WAVE_FORMAT_PCM
            wfx.nChannels = 1
            wfx.nSamplesPerSec = self._sample_rate
            wfx.wBitsPerSample = 16
            wfx.nBlockAlign = wfx.nChannels * (wfx.wBitsPerSample // 8)
            wfx.nAvgBytesPerSec = wfx.nSamplesPerSec * wfx.nBlockAlign
            wfx.cbSize = 0

            # auto-reset event, unsignaled initially, unnamed
            self._event = self._kernel32.CreateEventW(None, False, False, None)
            if not self._event:
                raise MicCaptureError("CreateEventW failed")

            device = WAVE_MAPPER if self._device_id is None else int(self._device_id)

            hwi = ctypes.c_void_p(0)
            result = self._winmm.waveInOpen(
                ctypes.byref(hwi),
                device,
                ctypes.byref(wfx),
                self._event,
                None,
                CALLBACK_EVENT,
            )
            self._check(result, "waveInOpen")
            self._hwi = hwi

            bytes_per_buffer = int(self._sample_rate * (self._buffer_ms / 1000.0)) * 2  # 16-bit mono
            bytes_per_buffer = max(bytes_per_buffer, 256)

            self._buffers = []
            for _ in range(self.NUM_BUFFERS):
                buf = ctypes.create_string_buffer(bytes_per_buffer)
                hdr = WAVEHDR()
                hdr.lpData = ctypes.cast(buf, ctypes.c_void_p)
                hdr.dwBufferLength = bytes_per_buffer
                hdr.dwFlags = 0
                result = self._winmm.waveInPrepareHeader(self._hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))
                self._check(result, "waveInPrepareHeader")
                result = self._winmm.waveInAddBuffer(self._hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))
                self._check(result, "waveInAddBuffer")
                # keep both the header and the underlying buffer alive together,
                # and keep the header at a fixed address via a persistent list
                self._buffers.append([hdr, buf])

            result = self._winmm.waveInStart(self._hwi)
            self._check(result, "waveInStart")
        except Exception:
            self._lastError = "failed to start microphone capture"
            log.error("UniversalTuner: mic_capture.start() failed partway through, cleaning up", exc_info=True)
            self._teardownPartialStart()
            raise

        self._running = True
        self._thread = threading.Thread(target=self._captureLoop)
        self._thread.daemon = True
        self._thread.start()

    def _captureLoop(self):
        try:
            while self._running:
                waitResult = self._kernel32.WaitForSingleObject(self._event, 200)
                if not self._running:
                    break
                if waitResult == WAIT_TIMEOUT:
                    continue
                for entry in self._buffers:
                    hdr, buf = entry
                    if hdr.dwFlags & WHDR_DONE:
                        n = hdr.dwBytesRecorded
                        if n > 0 and self._on_chunk:
                            try:
                                data = ctypes.string_at(hdr.lpData, n)
                                self._on_chunk(data, self._sample_rate)
                            except Exception:
                                log.error("UniversalTuner: on_chunk callback failed", exc_info=True)
                        if self._running:
                            hdr.dwFlags = 0
                            hdr.dwBytesRecorded = 0
                            try:
                                self._winmm.waveInPrepareHeader(self._hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))
                                self._winmm.waveInAddBuffer(self._hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))
                            except Exception:
                                log.error("UniversalTuner: failed to requeue capture buffer", exc_info=True)
        except Exception as e:
            self._lastError = str(e)
            log.error("UniversalTuner: mic capture loop crashed", exc_info=True)
        finally:
            self._running = False

    def stop(self):
        if not self._hwi or not self._winmm:
            self._running = False
            return
        self._running = False
        try:
            self._winmm.waveInStop(self._hwi)
            self._winmm.waveInReset(self._hwi)
        except Exception:
            log.error("UniversalTuner: waveInStop/Reset failed", exc_info=True)

        if self._thread:
            self._thread.join(timeout=1.0)

        for hdr, buf in self._buffers:
            try:
                self._winmm.waveInUnprepareHeader(self._hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))
            except Exception:
                log.error("UniversalTuner: waveInUnprepareHeader failed", exc_info=True)

        try:
            self._winmm.waveInClose(self._hwi)
        except Exception:
            log.error("UniversalTuner: waveInClose failed", exc_info=True)

        if self._event:
            try:
                self._kernel32.CloseHandle(self._event)
            except Exception:
                pass
            self._event = None

        self._buffers = []
        self._hwi = ctypes.c_void_p(0)

    def isRunning(self):
        return self._running

    def lastError(self):
        return self._lastError


def pcm16_bytes_to_floats(data):
    """Convert little-endian signed 16-bit PCM bytes to a list of floats
    in roughly [-1, 1], for feeding into the pure-Python pitch detector."""
    import struct
    count = len(data) // 2
    if count == 0:
        return []
    values = struct.unpack("<%dh" % count, data[:count * 2])
    return [v / 32768.0 for v in values]
