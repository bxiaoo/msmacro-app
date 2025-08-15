# /opt/msmacro-app/msmacro/bridge.py
from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from evdev import InputDevice, ecodes

from .hidio import HIDWriter
from .keymap import parse_hotkey, usage_from_ecode, is_modifier, mod_bit
from .events import emit  # if you don't use SSE events, you can comment out emit() calls


@dataclass(frozen=True)
class Chord:
    mod_ecode: int
    key_ecode: int
    key_usage: int


def _parse_chord(spec: str) -> Chord:
    mod_ec, key_ec = parse_hotkey(spec)
    return Chord(mod_ecode=mod_ec, key_ecode=key_ec, key_usage=usage_from_ecode(key_ec))


class Bridge:
    """
    Live keyboard bridge:
      - Forwards events from /dev/input event device to HID gadget.
      - Detects chords (stop, record, optional extras) using press→release.
      - Suppresses ONLY the active chord keys while armed (to avoid leakage).

    Returns from run_bridge():
      - "RECORD" if record chord fired (press→release)
      - <label> for any extra hotkey (if provided)
      - None if cancelled by daemon (e.g., to start PLAY)
    """

    def __init__(
        self,
        evdev_path: str,
        hidg_path: str,
        *,
        stop_hotkey: str,
        record_hotkey: Optional[str] = None,
        grab: bool = True,
        extra_hotkeys: Optional[Dict[str, str]] = None,  # spec -> label
    ):
        self.evdev_path = evdev_path
        self.hidg_path = hidg_path
        self.grab = grab

        self._hid = HIDWriter(hidg_path)
        self._modmask: int = 0
        self._down: Set[int] = set()
        self._suppress_codes: Set[int] = set()  # kernel key codes to suppress while a chord is armed

        # chords
        self._stop = _parse_chord(stop_hotkey)
        self._stop_armed = False

        self._record: Optional[Chord] = _parse_chord(record_hotkey) if record_hotkey else None
        self._record_armed = False

        self._extras: Dict[Tuple[int, int], str] = {}     # (mod_ec, key_usage) -> label
        self._extra_armed: Dict[Tuple[int, int], bool] = {}
        if extra_hotkeys:
            for spec, label in extra_hotkeys.items():
                ch = _parse_chord(spec)
                key = (ch.mod_ecode, ch.key_usage)
                self._extras[key] = label
                self._extra_armed[key] = False

    # ---------------- helpers ----------------

    def _active(self, chord: Chord) -> bool:
        if not chord:
            return False
        mod_down = (self._modmask & mod_bit(chord.mod_ecode)) != 0
        key_down = chord.key_usage in self._down
        return mod_down and key_down

    def _update_state(self, code: int, val: int):
        """Return (is_mod, usage, is_down). Update internal modmask/_down."""
        if val == 2:  # repeat
            return False, None, False
        is_down = (val == 1)
        if is_modifier(code):
            bit = mod_bit(code)
            if is_down:
                self._modmask |= bit
            else:
                self._modmask &= (~bit) & 0xFF
            return True, None, is_down
        usage = usage_from_ecode(code)
        if is_down:
            self._down.add(usage)
        else:
            self._down.discard(usage)
        return False, usage, is_down

    def _send(self):
        self._hid.send(self._modmask, self._down)

    # ---------------- live bridge ----------------

    async def run_bridge(self):
        dev = InputDevice(self.evdev_path)
        try:
            if self.grab:
                with contextlib.suppress(Exception):
                    dev.grab()

            # ensure clean state on gadget
            self._modmask = 0
            self._down.clear()
            self._suppress_codes.clear()
            self._send()

            with contextlib.suppress(NameError):
                emit("BRIDGE_START", device=self.evdev_path)

            async for ev in dev.async_read_loop():
                if ev.type != ecodes.EV_KEY:
                    continue
                code, val = ev.code, ev.value

                prev_stop = self._active(self._stop)
                prev_rec = self._active(self._record) if self._record else False

                is_mod, usage, is_down = self._update_state(code, val)

                # arm chords on first full press (mod+key down)
                curr_stop = self._active(self._stop)
                if (not self._stop_armed) and (not prev_stop) and curr_stop:
                    self._stop_armed = True
                    self._suppress_codes.update({self._stop.mod_ecode, self._stop.key_ecode})

                if self._record:
                    curr_rec = self._active(self._record)
                    if (not self._record_armed) and (not prev_rec) and curr_rec:
                        self._record_armed = True
                        self._suppress_codes.update({self._record.mod_ecode, self._record.key_ecode})
                else:
                    curr_rec = False

                # extras: arm/disarm; no suppression (avoid over-suppression bugs)
                for (mod_ec, key_usage), _label in self._extras.items():
                    armed = self._extra_armed[(mod_ec, key_usage)]
                    mod_down = (self._modmask & mod_bit(mod_ec)) != 0
                    key_down = (key_usage in self._down)
                    curr = mod_down and key_down
                    if (not armed) and curr:
                        self._extra_armed[(mod_ec, key_usage)] = True
                    elif armed and (not curr) and (code in (mod_ec, ecodes.KEY_S, ecodes.KEY_P, ecodes.KEY_D)) and (val == 0):
                        # fire in the return path below
                        pass

                # forward unless this is a chord key we are suppressing
                if code not in self._suppress_codes:
                    self._send()

                # fire stop on release edge
                if self._stop_armed and (not curr_stop) and (code in (self._stop.mod_ecode, self._stop.key_ecode)) and (val == 0):
                    self._stop_armed = False
                    self._suppress_codes.difference_update({self._stop.mod_ecode, self._stop.key_ecode})
                    # clean to gadget
                    self._modmask = 0
                    self._down.clear()
                    self._send()
                    with contextlib.suppress(NameError):
                        emit("BRIDGE_STOP")
                    return None

                # fire record on release edge
                if self._record and self._record_armed and (not curr_rec) and (code in (self._record.mod_ecode, self._record.key_ecode)) and (val == 0):
                    self._record_armed = False
                    self._suppress_codes.difference_update({self._record.mod_ecode, self._record.key_ecode})
                    self._send()
                    with contextlib.suppress(NameError):
                        emit("RECORD_REQUEST")
                    return "RECORD"

                # extras: fire on release edge
                for (mod_ec, key_usage), label in self._extras.items():
                    armed = self._extra_armed[(mod_ec, key_usage)]
                    mod_down = (self._modmask & mod_bit(mod_ec)) != 0
                    key_down = (key_usage in self._down)
                    curr = mod_down and key_down
                    if armed and (not curr) and (val == 0) and (code == mod_ec or usage == key_usage):
                        self._extra_armed[(mod_ec, key_usage)] = False
                        self._send()
                        with contextlib.suppress(NameError):
                            emit("CHOICE", label=label)
                        return label

        except asyncio.CancelledError:
            raise
        finally:
            # leave clean and ungrab
            with contextlib.suppress(Exception):
                self._modmask = 0
                self._down.clear()
                self._send()
            with contextlib.suppress(Exception):
                if self.grab:
                    dev.ungrab()
            with contextlib.suppress(Exception):
                dev.close()

    # ---------------- recording ----------------

    async def run_record(self):
        """
        Record every key down/up (including modifiers 224..231) until STOP chord releases.
        Forward everything live to HID gadget, but never leak the STOP chord to target.
        Returns a list of {"t": seconds, "type": "down"/"up", "usage": int}.
        """
        dev = InputDevice(self.evdev_path)
        actions = []
        try:
            if self.grab:
                with contextlib.suppress(Exception):
                    dev.grab()

            self._modmask = 0
            self._down.clear()
            self._suppress_codes.clear()
            self._send()

            with contextlib.suppress(NameError):
                emit("RECORD_LOOP_START", device=self.evdev_path)

            t0 = time.monotonic()
            stop_armed = False

            async for ev in dev.async_read_loop():
                if ev.type != ecodes.EV_KEY:
                    continue
                code, val = ev.code, ev.value
                if val == 2:
                    continue

                prev_stop = self._active(self._stop)
                is_mod, usage, is_down = self._update_state(code, val)
                curr_stop = self._active(self._stop)
                if (not stop_armed) and (not prev_stop) and curr_stop:
                    stop_armed = True
                    self._suppress_codes.update({self._stop.mod_ecode, self._stop.key_ecode})

                rec_usage = usage_from_ecode(code) if is_mod else usage
                t = round(time.monotonic() - t0, 6)

                if code not in self._suppress_codes:
                    self._send()

                if rec_usage is not None and (code not in self._suppress_codes):
                    actions.append({
                        "t": t,
                        "type": "down" if is_down else "up",
                        "usage": int(rec_usage),
                    })

                if stop_armed and (not curr_stop) and (code in (self._stop.mod_ecode, self._stop.key_ecode)) and (val == 0):
                    break

        except asyncio.CancelledError:
            # daemon cancelled to stop recording via IPC
            pass
        finally:
            with contextlib.suppress(Exception):
                self._modmask = 0
                self._down.clear()
                self._send()
            with contextlib.suppress(Exception):
                if self.grab:
                    dev.ungrab()
            with contextlib.suppress(Exception):
                dev.close()

        with contextlib.suppress(NameError):
            emit("RECORD_LOOP_STOP", count=len(actions))
        return actions
