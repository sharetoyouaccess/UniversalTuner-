# -*- coding: utf-8 -*-
"""
wx dialogs for Universal Tuner: the advanced-settings popup and the main
tuner window.

v2.5.2: all user-facing strings in this module are now wrapped in _() and
translated via NVDA's standard gettext mechanism (see __init__.py's
addonHandler.initTranslation() call, which must run before this module is
imported so that _() is already installed as a builtin). The two
hardcoded-language shortcut-guide readouts (_speakShortcutsThai and
_speakShortcutsEnglish, bound to a single vs. double F1 press) are
deliberately NOT translated - their whole purpose is to always be
available in a specific language on request, regardless of NVDA's
configured language, so wrapping them in _() would defeat the point.

v2.4.0 additions: an "O" shortcut to toggle the in-tune confirmation
beep on/off (for users who only want the spoken reading), an "R"
shortcut to repeat the last live-tuner reading, a Reset to defaults
button and a beep-length field in Advanced settings, and Space bar now
cancels an in-progress in-tune beep+announcement while live listening
is on instead of touching reference-tone preview.

v2.5.1 additions: Advanced settings field order changed to Sample rate,
A4 reference, Gap between repeats, Beep length, Tone length, Microphone
device (was Sample rate, Gap, A4, Beep length, Microphone device), and a
new "Tone length" field was added (previously only adjustable from the
main window with the plus/minus keys) - both per user testing feedback.

v2.5.0 additions: a "Microphone device" field in Advanced settings (was
always the system default before), and the dialog now reacts to the
microphone unexpectedly disconnecting while listening was on (see
onListeningLost) instead of silently continuing to show "Live
listening: on".
"""
import time
import wx
import ui

import addonHandler
addonHandler.initTranslation()

from .instruments import (
    INSTRUMENTS,
    get_tunings_for,
    build_string_items,
    parse_string_number,
    get_course_count,
    find_displayed_number_for_note,
)
from .mic_capture import list_input_devices
from . import settings as tuner_settings

DEFAULT_MIC_LABEL = _("Default (system default)")


class AdvancedSettingsDialog(wx.Dialog):
    def __init__(self, parent, params):
        wx.Dialog.__init__(self, parent, title=_("Advanced settings"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        intro = wx.StaticText(
            panel,
            label=_("Advanced audio settings. These options change how the tuner sounds and how note frequencies are calculated.")
        )
        root.Add(intro, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)

        section = wx.BoxSizer(wx.VERTICAL)

        sampleLabel = wx.StaticText(panel, label=_("Sample rate"))
        self.sampleRateChoice = wx.Choice(panel, choices=["22050", "44100", "48000"])
        self.sampleRateChoice.SetStringSelection(str(int(params["sampleRate"])))
        self.sampleRateChoice.SetName(_("Sample rate"))
        self.sampleRateChoice.SetHelpText(_("Select the audio sample rate. Higher values may sound smoother."))
        sampleDesc = wx.StaticText(
            panel,
            label=_("Sets the audio sample rate. 44100 is the standard default and works well for most users.")
        )

        a4Label = wx.StaticText(panel, label=_("A4 reference"))
        self.a4Spin = wx.SpinCtrlDouble(panel, min=400.0, max=480.0, initial=float(params["a4"]), inc=1.0)
        self.a4Spin.SetDigits(1)
        self.a4Spin.SetName(_("A4 reference"))
        self.a4Spin.SetHelpText(_("Set the A4 concert pitch used to calculate all note frequencies."))
        a4Desc = wx.StaticText(
            panel,
            label=_("Sets the master reference pitch. Standard concert tuning is 440 hertz.")
        )

        gapLabel = wx.StaticText(panel, label=_("Gap between repeats"))
        self.gapSpin = wx.SpinCtrlDouble(panel, min=0.0, max=5.0, initial=float(params["gap"]), inc=0.05)
        self.gapSpin.SetDigits(2)
        self.gapSpin.SetName(_("Gap between repeats"))
        self.gapSpin.SetHelpText(_("Set the silence between repeated tones."))
        gapDesc = wx.StaticText(
            panel,
            label=_("Controls the pause before the tone repeats again. Use 0 for almost continuous playback.")
        )

        beepLabel = wx.StaticText(panel, label=_("Beep length (in-tune confirmation)"))
        self.beepSpin = wx.SpinCtrlDouble(
            panel, min=0.1, max=5.0, initial=float(params.get("beepDuration", 0.6)), inc=0.1
        )
        self.beepSpin.SetDigits(2)
        self.beepSpin.SetName(_("Beep length"))
        self.beepSpin.SetHelpText(
            _("Set how long the confirmation beep plays when a live tuning reading is exactly in tune.")
        )
        beepDesc = wx.StaticText(
            panel,
            label=_(
                "Controls the length of the beep played when live listening detects an exact match. "
                "Use the O shortcut in the main window to turn this beep off entirely."
            )
        )

        # v2.5.1: previously "Tone length" could only be adjusted from the
        # main window with the +/- keys and was not visible in Advanced
        # settings at all - added here per user request so it can be set
        # (and reset to defaults) alongside the other timing fields.
        durationLabel = wx.StaticText(panel, label=_("Tone length"))
        self.durationSpin = wx.SpinCtrlDouble(
            panel, min=0.2, max=10.0, initial=float(params.get("duration", 2.0)), inc=0.5
        )
        self.durationSpin.SetDigits(2)
        self.durationSpin.SetName(_("Tone length"))
        self.durationSpin.SetHelpText(_("Set how long each reference tone plays."))
        durationDesc = wx.StaticText(
            panel,
            label=_(
                "Controls the length of each reference tone. Also adjustable from the main window "
                "with the plus and minus keys."
            )
        )

        micLabel = wx.StaticText(panel, label=_("Microphone device"))
        deviceNames = [DEFAULT_MIC_LABEL] + [name for _device_id, name in list_input_devices()]
        self.micChoice = wx.Choice(panel, choices=deviceNames)
        currentMicName = params.get("micDeviceName") or ""
        if currentMicName and currentMicName in deviceNames:
            self.micChoice.SetStringSelection(currentMicName)
        else:
            self.micChoice.SetSelection(0)
        self.micChoice.SetName(_("Microphone device"))
        self.micChoice.SetHelpText(
            _(
                "Choose which microphone live listening uses. Default uses whatever Windows currently "
                "treats as the default recording device."
            )
        )
        micDesc = wx.StaticText(
            panel,
            label=_(
                "Only affects live microphone listening (the L key) - reference tone playback is "
                "unaffected. If listening is already on, changing this restarts it with the new device."
            )
        )

        for labelCtrl, fieldCtrl, descCtrl in (
            (sampleLabel, self.sampleRateChoice, sampleDesc),
            (a4Label, self.a4Spin, a4Desc),
            (gapLabel, self.gapSpin, gapDesc),
            (beepLabel, self.beepSpin, beepDesc),
            (durationLabel, self.durationSpin, durationDesc),
            (micLabel, self.micChoice, micDesc),
        ):
            section.Add(labelCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
            section.Add(fieldCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
            section.Add(descCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)

        self._bindAdvancedFieldHelp(self.sampleRateChoice, _("Sample rate"), _("Audio quality"))
        self._bindAdvancedFieldHelp(self.a4Spin, _("A4 reference"), _("Pitch standard"))
        self._bindAdvancedFieldHelp(self.gapSpin, _("Gap between repeats"), _("Pause between tones"))
        self._bindAdvancedFieldHelp(self.beepSpin, _("Beep length"), _("In-tune confirmation beep"))
        self._bindAdvancedFieldHelp(self.durationSpin, _("Tone length"), _("Reference tone duration"))
        self._bindAdvancedFieldHelp(self.micChoice, _("Microphone device"), _("Live listening input"))

        root.Add(section, 0, wx.BOTTOM | wx.EXPAND, 8)

        hint = wx.StaticText(
            panel,
            label=_(
                "Press Tab to move between fields. Press Enter on OK to save or Escape to cancel. "
                "Reset to defaults only changes the fields shown here - press Cancel afterwards to discard."
            )
        )
        root.Add(hint, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        btnRow = wx.BoxSizer(wx.HORIZONTAL)
        self.resetBtn = wx.Button(panel, label=_("Reset to defaults"))
        self.okBtn = wx.Button(panel, wx.ID_OK, _("OK"))
        self.okBtn.SetDefault()
        self.cancelBtn = wx.Button(panel, wx.ID_CANCEL, _("Cancel"))
        btnRow.Add(self.resetBtn, 0, wx.RIGHT, 8)
        btnRow.Add(self.okBtn, 0, wx.RIGHT, 8)
        btnRow.Add(self.cancelBtn, 0)
        root.Add(btnRow, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        panel.SetSizer(root)
        # Height increased from 560 to 660 in v2.5.1 to fit the new Tone
        # length row without clipping/scrolling.
        self.SetSize((580, 660))

        self.resetBtn.Bind(wx.EVT_BUTTON, self._onReset)

    def _bindAdvancedFieldHelp(self, ctrl, fieldName, shortHelp):
        def onFocus(evt):
            ui.message("%s. %s" % (fieldName, shortHelp))
            evt.Skip()
        ctrl.Bind(wx.EVT_SET_FOCUS, onFocus)

    def _onReset(self, evt):
        # Only resets what's shown in this dialog's fields - nothing is
        # saved until OK is pressed, so Cancel afterwards still discards
        # cleanly, same as changing any other field by hand.
        d = tuner_settings.DEFAULTS
        self.sampleRateChoice.SetStringSelection(str(int(d["sampleRate"])))
        self.gapSpin.SetValue(float(d["gap"]))
        self.a4Spin.SetValue(float(d["a4"]))
        self.beepSpin.SetValue(float(d["beepDuration"]))
        self.durationSpin.SetValue(float(d["duration"]))
        self.micChoice.SetSelection(0)
        ui.message(_("Advanced settings reset to defaults. Press OK to save or Cancel to discard."))

    def getValues(self):
        try:
            sampleRate = int(self.sampleRateChoice.GetStringSelection())
        except Exception:
            sampleRate = 44100
        try:
            gap = float(self.gapSpin.GetValue())
        except Exception:
            gap = 2.0
        try:
            a4 = float(self.a4Spin.GetValue())
        except Exception:
            a4 = 440.0
        try:
            beepDuration = float(self.beepSpin.GetValue())
        except Exception:
            beepDuration = 5.0
        try:
            duration = float(self.durationSpin.GetValue())
        except Exception:
            duration = 5.0
        try:
            micSelection = self.micChoice.GetStringSelection()
        except Exception:
            micSelection = DEFAULT_MIC_LABEL
        micDeviceName = "" if micSelection == DEFAULT_MIC_LABEL else micSelection
        return {
            "sampleRate": sampleRate, "gap": gap, "a4": a4, "beepDuration": beepDuration,
            "duration": duration, "micDeviceName": micDeviceName,
        }


class TunerDialog(wx.Dialog):
    def __init__(
        self,
        parent,
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
        initialChromatic=False,
        initialInstrument=None,
        initialTuning=None,
        initialBeepEnabled=True,
        onClosed=None,
    ):
        wx.Dialog.__init__(self, parent, title=_("Universal Tuner"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.onStop = onStop
        self.onToggleActive = onToggleActive
        self.onPlayCourse = onPlayCourse
        self.onLiveAdjust = onLiveAdjust
        self.getLiveParams = getLiveParams
        self.onSelectionTargetChanged = onSelectionTargetChanged
        self.onToggleListen = onToggleListen
        self.onToggleChromatic = onToggleChromatic
        self.onToggleBeep = onToggleBeep
        self.onRepeatLast = onRepeatLast
        self.onClosed = onClosed
        self._previewOn = False
        self._lastF1Time = 0.0
        self._listening = False
        self._chromatic = bool(initialChromatic)
        self._beepEnabled = bool(initialBeepEnabled)

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(panel, label=_("Main tuning controls"))
        root.Add(header, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)

        grid = wx.FlexGridSizer(3, 2, 8, 10)

        instrumentLabel = wx.StaticText(panel, label=_("Instrument"))
        self.instrumentChoice = wx.Choice(panel, choices=list(INSTRUMENTS.keys()))
        instrumentNames = list(INSTRUMENTS.keys())
        if initialInstrument and initialInstrument in instrumentNames:
            self.instrumentChoice.SetStringSelection(initialInstrument)
        else:
            self.instrumentChoice.SetSelection(0)
        self.instrumentChoice.SetName(_("Instrument"))

        tuningLabel = wx.StaticText(panel, label=_("Tuning"))
        _tuningNames = list(get_tunings_for(self.instrumentChoice.GetStringSelection()).keys())
        self.tuningChoice = wx.Choice(panel, choices=_tuningNames)
        if initialTuning and initialTuning in _tuningNames:
            self.tuningChoice.SetStringSelection(initialTuning)
        else:
            self.tuningChoice.SetSelection(0)
        self.tuningChoice.SetName(_("Tuning"))

        stringLabel = wx.StaticText(panel, label=_("Selection"))
        self.stringChoice = wx.Choice(
            panel,
            choices=build_string_items(
                self.instrumentChoice.GetStringSelection(),
                self.tuningChoice.GetStringSelection()
            )
        )
        self.stringChoice.SetSelection(0)
        self.stringChoice.SetName(_("Selection"))

        grid.Add(instrumentLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.instrumentChoice, 1, wx.EXPAND)
        grid.Add(tuningLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.tuningChoice, 1, wx.EXPAND)
        grid.Add(stringLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.stringChoice, 1, wx.EXPAND)
        grid.AddGrowableCol(1, 1)
        root.Add(grid, 0, wx.ALL | wx.EXPAND, 12)

        self.quickInfo = wx.StaticText(panel, label="")
        root.Add(self.quickInfo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.hint = wx.StaticText(
            panel,
            label=_(
                "Shortcuts. Space play or stop selected item, or during live listening, cancel the "
                "in-progress in-tune beep and announcement. Home louder. End softer. "
                "Page Up longer tone. Page Down shorter tone. Number keys play strings in order. "
                "L toggles live microphone listening. C toggles chromatic mode. "
                "O toggles the in-tune confirmation beep. R repeats the last live tuning reading."
            )
        )
        root.Add(self.hint, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.status = wx.StaticText(panel, label=_("Idle"))
        root.Add(self.status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.liveStatus = wx.StaticText(panel, label=_("Live listening: off. Chromatic mode: off."))
        root.Add(self.liveStatus, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        btnRow = wx.BoxSizer(wx.HORIZONTAL)
        self.listenBtn = wx.Button(panel, label=_("Start listening (L)"))
        self.chromaticBtn = wx.Button(panel, label=_("Chromatic mode: off (C)"))
        self.beepBtn = wx.Button(panel, label=_("Beep: on (O)"))
        self.advancedBtn = wx.Button(panel, label=_("Advanced settings"))
        closeBtn = wx.Button(panel, id=wx.ID_CLOSE, label=_("Close"))

        btnRow.Add(self.listenBtn, 0, wx.RIGHT, 8)
        btnRow.Add(self.chromaticBtn, 0, wx.RIGHT, 8)
        btnRow.Add(self.beepBtn, 0, wx.RIGHT, 8)
        btnRow.Add(self.advancedBtn, 0, wx.RIGHT, 8)
        btnRow.Add(closeBtn, 0)
        root.Add(btnRow, 0, wx.ALL, 12)

        panel.SetSizer(root)
        self.SetSize((820, 420))

        self.advancedBtn.Bind(wx.EVT_BUTTON, self._openAdvanced)
        self.listenBtn.Bind(wx.EVT_BUTTON, lambda evt: self._toggleListen())
        self.chromaticBtn.Bind(wx.EVT_BUTTON, lambda evt: self._toggleChromatic())
        self.beepBtn.Bind(wx.EVT_BUTTON, lambda evt: self._toggleBeep())
        closeBtn.Bind(wx.EVT_BUTTON, self._closeClicked)
        self.Bind(wx.EVT_CLOSE, self._onCloseWindow)

        self.instrumentChoice.Bind(wx.EVT_CHOICE, self._onInstrumentChange)
        self.tuningChoice.Bind(wx.EVT_CHOICE, self._onTuningChange)
        self.stringChoice.Bind(wx.EVT_CHOICE, self._onSelectionChoiceChanged)
        self.instrumentChoice.Bind(wx.EVT_CHAR_HOOK, self._onControlCharHook)
        self.tuningChoice.Bind(wx.EVT_CHAR_HOOK, self._onControlCharHook)
        self.stringChoice.Bind(wx.EVT_CHAR_HOOK, self._onControlCharHook)
        self.Bind(wx.EVT_CHAR_HOOK, self._onCharHook)

        self._refreshAll()
        self._updateQuickInfo()
        self._notifySelectionTarget()
        self._updateLiveStatusLabel()

    # ------------------------------------------------------------------
    # Quick info / status
    # ------------------------------------------------------------------

    def _updateQuickInfo(self):
        params = self.getLiveParams()
        self.quickInfo.SetLabel(
            _(
                "Volume %d percent. Tone length %.1f seconds. A4 %.1f. Sample rate %d. Gap %.2f seconds. "
                "Beep length %.1f seconds."
            )
            % (
                int(round(params["volume"] * 100.0)),
                float(params["duration"]),
                float(params["a4"]),
                int(params["sampleRate"]),
                float(params["gap"]),
                float(params.get("beepDuration", 0.6)),
            )
        )
        self.Layout()

    def _updateLiveStatusLabel(self, extra=None):
        onLabel = _("on")
        offLabel = _("off")
        base = _("Live listening: %s. Chromatic mode: %s. Beep: %s.") % (
            onLabel if self._listening else offLabel,
            onLabel if self._chromatic else offLabel,
            onLabel if self._beepEnabled else offLabel,
        )
        if extra:
            base = base + " " + extra
        self.liveStatus.SetLabel(base)
        self.listenBtn.SetLabel(_("Stop listening (L)") if self._listening else _("Start listening (L)"))
        self.chromaticBtn.SetLabel(_("Chromatic mode: %s (C)") % (onLabel if self._chromatic else offLabel))
        self.beepBtn.SetLabel(_("Beep: %s (O)") % (onLabel if self._beepEnabled else offLabel))
        self.Layout()

    def showLiveResult(self, result, spoken):
        """Called (via wx.CallAfter, from the GlobalPlugin) with the latest
        tuning_feedback result dict. Always updates the on-screen numeric
        readout; speaking is handled separately by the caller so this
        dialog doesn't need to know about throttling policy."""
        directionLabels = {
            "in_tune": _("In tune"),
            "sharp": _("Sharp"),
            "flat": _("Flat"),
        }
        text = _("Detected %.2f Hz. Target %s %.2f Hz. %+.1f cents (%+.1f%%). %s.") % (
            result["detected_freq"],
            result.get("note_name") or "?",
            result["target_freq"],
            result["cents"],
            result["percent"],
            directionLabels.get(result["direction"], ""),
        )
        self._updateLiveStatusLabel(extra=text)

    def onListeningLost(self):
        """Called (via wx.CallAfter, from GlobalPlugin._onLiveLost) if the
        microphone was found to have disconnected/stopped responding
        while listening was on. The controller has already stopped
        itself; this just brings the dialog's own state (the "Live
        listening: on/off" label and the Start/Stop listening button
        text) back in sync so it doesn't keep claiming to be listening
        when nothing is actually happening any more."""
        self._listening = False
        self._updateLiveStatusLabel()

    # ------------------------------------------------------------------
    # Selection / target tracking
    # ------------------------------------------------------------------

    def _currentDisplayedNumber(self):
        sel = self.stringChoice.GetStringSelection()
        return parse_string_number(sel)

    def _notifySelectionTarget(self):
        inst = self.instrumentChoice.GetStringSelection()
        tuning = self.tuningChoice.GetStringSelection()
        displayedNumber = self._currentDisplayedNumber()
        if displayedNumber is not None and self.onSelectionTargetChanged:
            self.onSelectionTargetChanged(inst, tuning, displayedNumber)

    def _onSelectionChoiceChanged(self, evt):
        self._notifySelectionTarget()
        evt.Skip()

    # ------------------------------------------------------------------
    # Listening / chromatic toggles
    # ------------------------------------------------------------------

    def _toggleListen(self):
        # Live listening and reference-tone preview using audio at the
        # same time would be self-defeating (the mic would hear the
        # reference tone), so starting one stops the other.
        if not self._listening:
            self._stopPlayback()
        self._listening = bool(self.onToggleListen()) if self.onToggleListen else False
        self._updateLiveStatusLabel()
        ui.message(_("Live listening on") if self._listening else _("Live listening off"))

    def _toggleChromatic(self):
        self._chromatic = not self._chromatic
        if self.onToggleChromatic:
            self.onToggleChromatic(self._chromatic)
        if not self._chromatic:
            # Switched back to targeted mode - make sure the live tuner
            # picks up whatever string/course is currently selected again.
            self._notifySelectionTarget()
        self._updateLiveStatusLabel()
        ui.message(_("Chromatic mode on") if self._chromatic else _("Chromatic mode off"))

    def _toggleBeep(self):
        # "O" shortcut: lets users who only want the spoken confirmation
        # (not the beep) during live listening turn the beep off, without
        # affecting the reference-tone preview sounds elsewhere.
        self._beepEnabled = not self._beepEnabled
        if self.onToggleBeep:
            self.onToggleBeep(self._beepEnabled)
        self._updateLiveStatusLabel()
        ui.message(_("Beep on") if self._beepEnabled else _("Beep off"))

    # ------------------------------------------------------------------
    # Volume / duration / advanced settings
    # ------------------------------------------------------------------

    def _changeVolume(self, delta):
        params = self.getLiveParams()
        newValue = max(0.01, min(1.0, float(params["volume"]) + delta))
        self.onLiveAdjust(volume=newValue)
        self._updateQuickInfo()
        ui.message(_("Volume %d percent") % int(round(newValue * 100.0)))

    def _changeDuration(self, delta):
        params = self.getLiveParams()
        newValue = max(0.2, min(10.0, float(params["duration"]) + delta))
        self.onLiveAdjust(duration=newValue)
        self._updateQuickInfo()
        ui.message(_("Tone length %.1f seconds") % newValue)

    def _openAdvanced(self, evt):
        dlg = AdvancedSettingsDialog(self, self.getLiveParams())
        try:
            if dlg.ShowModal() == wx.ID_OK:
                values = dlg.getValues()
                # A device change on an already-open capture has no
                # effect until it's reopened - if listening is currently
                # on, restart it around the change so a new microphone
                # choice actually takes effect immediately instead of
                # silently waiting until the next manual L/L toggle.
                wasListening = self._listening
                if wasListening:
                    self._toggleListen()
                self.onLiveAdjust(
                    sampleRate=values["sampleRate"],
                    gap=values["gap"],
                    a4=values["a4"],
                    beepDuration=values["beepDuration"],
                    duration=values["duration"],
                    micDeviceName=values["micDeviceName"],
                )
                self._updateQuickInfo()
                self._notifySelectionTarget()  # target freq depends on A4
                if wasListening:
                    self._toggleListen()
                ui.message(_("Advanced settings updated"))
        finally:
            dlg.Destroy()

    # ------------------------------------------------------------------
    # Help speech
    #
    # These two methods are intentionally NOT run through _() - F1 is a
    # dedicated "hear the guide in a specific language on demand"
    # shortcut (single press = Thai, double press = English), independent
    # of whatever language NVDA itself is currently configured for. See
    # the module docstring.
    # ------------------------------------------------------------------

    def _speakShortcutsThai(self):
        ui.message(
            "คีย์ลัดในการใช้งาน Universal Tuner มีดังนี้ "
            "กด I เพื่อไปยังรายการเลือกชนิดของเครื่องดนตรี "
            "กด T เพื่อไปยังรายการเลือกรูปแบบการตั้งเสียงหรือการตั้งสาย "
            "กด Space เพื่อเล่นหรือหยุดเสียงของรายการที่เลือกในช่อง Selection "
            "กดเลข 1 ถึง 9 เพื่อเล่นเสียงตามลำดับสายของเครื่องดนตรี "
            "หากเป็นเครื่องดนตรีที่มีสายคู่ กดเลขเดิมซ้ำเพื่อสลับไปยังเสียงของสายคู่ "
            "กด Home เพื่อเพิ่มความดัง "
            "กด End เพื่อลดความดัง "
            "กด Page Up เพื่อเพิ่มความยาวของเสียง "
            "กด Page Down เพื่อลดความยาวของเสียง "
            "กด L เพื่อเปิดหรือปิดโหมดฟังเสียงจากไมโครโฟนแบบสด ระบบจะบอกว่าโน้ตตรง เพี้ยนสูงกี่เปอร์เซ็นต์ หรือเพี้ยนต่ำกี่เปอร์เซ็นต์ "
            "ระหว่างฟังสดอยู่ กด Space เพื่อหยุดเสียงบี๊พและคำพูดแจ้งผลที่กำลังเล่นอยู่ได้ทันที "
            "กด C เพื่อสลับโหมดโครมาติก ซึ่งจะตรวจจับโน้ตที่ใกล้เคียงที่สุดโดยอัตโนมัติแทนการเทียบกับสายที่เลือกไว้ "
            "กด O เพื่อเปิดหรือปิดเสียงบี๊พยืนยันตอนโน้ตตรงเป๊ะ หากต้องการฟังแค่เสียงพูดอย่างเดียว "
            "กด R เพื่อฟังผลการอ่านล่าสุดของการฟังสดซ้ำอีกครั้ง ไม่ว่าจะอยู่ในโหมดโครมาติกหรือไม่ก็ตาม "
            "กด F1 หนึ่งครั้งเพื่อฟังคำแนะนำเป็นภาษาไทย "
            "กด F1 สองครั้งติดกันเพื่อฟังคำแนะนำเป็นภาษาอังกฤษ "
            "กด Escape เพื่อปิดหน้าต่าง "
            "ผู้จัดทำ ภีร์ม นาคขวัญ"
        )

    def _speakShortcutsEnglish(self):
        ui.message(
            "Universal Tuner shortcuts are as follows "
            "Press I to move to the instrument selection list "
            "Press T to move to the tuning selection list "
            "Press Space to play or stop the sound of the selected item in the Selection field "
            "Press numbers 1 to 9 to play strings in order of the instrument "
            "For paired string instruments, press the same number again to switch to the paired string sound "
            "Press Home to increase volume "
            "Press End to decrease volume "
            "Press Page Up to increase tone length "
            "Press Page Down to decrease tone length "
            "Press L to toggle live microphone listening. It reports whether the note is in tune, "
            "sharp by a percentage, or flat by a percentage "
            "While live listening is on, press Space to immediately stop the confirmation beep and "
            "spoken announcement currently playing "
            "Press C to toggle chromatic mode, which automatically detects the nearest note instead of "
            "comparing against the currently selected string "
            "Press O to toggle the in-tune confirmation beep on or off, if you only want the spoken reading "
            "Press R to repeat the last live tuning reading, whether chromatic mode is on or off "
            "Press F1 once to hear the Thai guide "
            "Press F1 twice quickly to hear the English guide "
            "Press Escape to close the window "
            "Developed by Peem Narkkhwan"
        )

    # ------------------------------------------------------------------
    # Reference-tone playback (unchanged behaviour from v1.4.26p)
    # ------------------------------------------------------------------

    def _playCourseNumber(self, s):
        inst = self.instrumentChoice.GetStringSelection()
        tuning = self.tuningChoice.GetStringSelection()
        courseCount = get_course_count(inst, tuning)
        if s < 1 or s > courseCount:
            return False
        note = self.onPlayCourse(inst, tuning, int(s))
        if note:
            self._previewOn = True
            # Keep the Selection dropdown visually in sync with whatever
            # was just triggered via a number key, so Space/status/live
            # tuning target all agree with what's actually sounding
            # instead of silently disagreeing with an unrelated dropdown
            # value the user hasn't touched.
            self._syncSelectionToNote(note)
            return True
        return False

    def _syncSelectionToNote(self, noteName):
        inst = self.instrumentChoice.GetStringSelection()
        tuning = self.tuningChoice.GetStringSelection()
        displayedNumber = find_displayed_number_for_note(inst, tuning, noteName)
        if displayedNumber is None:
            return
        items = build_string_items(inst, tuning)
        for item in items:
            if parse_string_number(item) == displayedNumber:
                if self.stringChoice.GetStringSelection() != item:
                    self.stringChoice.SetStringSelection(item)
                break

    def _onControlCharHook(self, evt):
        key = evt.GetKeyCode()

        if key in (
            wx.WXK_ESCAPE, wx.WXK_F1, wx.WXK_SPACE, wx.WXK_HOME, wx.WXK_END,
            wx.WXK_PAGEUP, wx.WXK_PAGEDOWN,
            ord("I"), ord("i"), ord("T"), ord("t"), ord("L"), ord("l"), ord("C"), ord("c"),
            ord("O"), ord("o"), ord("R"), ord("r"),
            ord("1"), ord("2"), ord("3"), ord("4"), ord("5"),
            ord("6"), ord("7"), ord("8"), ord("9"),
            wx.WXK_NUMPAD1, wx.WXK_NUMPAD2, wx.WXK_NUMPAD3, wx.WXK_NUMPAD4,
            wx.WXK_NUMPAD5, wx.WXK_NUMPAD6, wx.WXK_NUMPAD7, wx.WXK_NUMPAD8, wx.WXK_NUMPAD9
        ):
            self._onCharHook(evt)
            return

        if (ord("A") <= key <= ord("Z")) or (ord("a") <= key <= ord("z")):
            return

        evt.Skip()

    def _onCharHook(self, evt):
        key = evt.GetKeyCode()

        if key == wx.WXK_ESCAPE:
            self._closeClicked(None)
            return

        if key == wx.WXK_F1:
            now = time.time()
            if now - self._lastF1Time <= 0.7:
                self._lastF1Time = 0.0
                self._speakShortcutsEnglish()
            else:
                self._lastF1Time = now
                self._speakShortcutsThai()
            return

        if key in (ord("I"), ord("i")):
            self.instrumentChoice.SetFocus()
            return

        if key in (ord("T"), ord("t")):
            self.tuningChoice.SetFocus()
            return

        if key in (ord("L"), ord("l")):
            self._toggleListen()
            return

        if key in (ord("C"), ord("c")):
            self._toggleChromatic()
            return

        if key in (ord("O"), ord("o")):
            self._toggleBeep()
            return

        if key in (ord("R"), ord("r")):
            if self.onRepeatLast:
                self.onRepeatLast()
            return

        numberMap = {
            ord("1"): 1, ord("2"): 2, ord("3"): 3, ord("4"): 4, ord("5"): 5,
            ord("6"): 6, ord("7"): 7, ord("8"): 8, ord("9"): 9,
            wx.WXK_NUMPAD1: 1, wx.WXK_NUMPAD2: 2, wx.WXK_NUMPAD3: 3, wx.WXK_NUMPAD4: 4,
            wx.WXK_NUMPAD5: 5, wx.WXK_NUMPAD6: 6, wx.WXK_NUMPAD7: 7, wx.WXK_NUMPAD8: 8,
            wx.WXK_NUMPAD9: 9,
        }
        if key in numberMap:
            if self._playCourseNumber(numberMap[key]):
                return

        if key == wx.WXK_SPACE:
            # onToggleActive() (GlobalPlugin.script_openTuner) branches on
            # whether live listening is on:
            #   - listening ON: cancels an in-progress in-tune beep and/or
            #     delayed spoken confirmation, and stops any number-key
            #     note cue still sounding (see _playNoteOnceForListening).
            #     Always returns False here.
            #   - listening OFF: acts on whatever is *actually currently
            #     sounding* (regardless of whether it was started via the
            #     Selection dropdown or a number-key course press) - if
            #     something is playing, this stops it; if nothing is
            #     playing, this plays whichever note is currently selected
            #     (dropdown navigation and the last number-key press both
            #     update that same shared target, whichever happened most
            #     recently).
            self._previewOn = self.onToggleActive()
            sel = self.stringChoice.GetStringSelection()
            if self._previewOn:
                self.status.SetLabel(_("Playing. %s") % sel)
            else:
                self.status.SetLabel(_("Idle"))
            return

        if key == wx.WXK_HOME:
            self._changeVolume(0.03)
            return

        if key == wx.WXK_END:
            self._changeVolume(-0.03)
            return

        if key == wx.WXK_PAGEUP:
            self._changeDuration(0.2)
            return

        if key == wx.WXK_PAGEDOWN:
            self._changeDuration(-0.2)
            return

        evt.Skip()

    def _closeClicked(self, evt):
        self._stopPlayback()
        if self._listening:
            self._toggleListen()
        if self.onClosed:
            try:
                self.onClosed()
            except Exception:
                pass
        self.Destroy()

    def _onCloseWindow(self, evt):
        self._stopPlayback()
        if self._listening:
            self._toggleListen()
        if self.onClosed:
            try:
                self.onClosed()
            except Exception:
                pass
        self.Destroy()

    def _stopPlayback(self):
        self._previewOn = False
        self.onStop()
        self.status.SetLabel(_("Idle"))

    def _onInstrumentChange(self, evt):
        self._refreshTunings()
        self._refreshStringItems()
        self._notifySelectionTarget()
        evt.Skip()

    def _onTuningChange(self, evt):
        self._refreshStringItems()
        self._notifySelectionTarget()
        evt.Skip()

    def _refreshTunings(self):
        inst = self.instrumentChoice.GetStringSelection()
        tunings = list(get_tunings_for(inst).keys())
        current = self.tuningChoice.GetStringSelection()
        self.tuningChoice.SetItems(tunings)
        if current in tunings:
            self.tuningChoice.SetStringSelection(current)
        else:
            self.tuningChoice.SetSelection(0)

    def _refreshStringItems(self):
        inst = self.instrumentChoice.GetStringSelection()
        tuning = self.tuningChoice.GetStringSelection()
        items = build_string_items(inst, tuning)
        current = self.stringChoice.GetStringSelection()
        self.stringChoice.SetItems(items)
        if current in items:
            self.stringChoice.SetStringSelection(current)
        else:
            self.stringChoice.SetSelection(0)

    def _refreshAll(self):
        self._refreshTunings()
        self._refreshStringItems()

    def setStatus(self, text):
        self.status.SetLabel(text)
