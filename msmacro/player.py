# /opt/msmacro-app/msmacro/player.py
from __future__ import annotations

import asyncio
import json
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .hidio import HIDWriter

# HID usage IDs for modifier keys (Left/Right Ctrl, Shift, Alt, GUI)
MOD_USAGES = set(range(224, 232))  # 224..231


def _clamp_nonneg(x: float) -> float:
    return x if x > 0 else 0.0


class Player:
    """
    Replays a recorded keyboard sequence to the HID gadget.

    Recording formats supported:
      - Events: {"t": <sec>, "type": "down"/"up", "usage": <int>}
        wrapped as {"t0": 0, "events": [...] }  OR a bare list [ ... ]
      - Actions: {"usage": <int>, "press": <sec>, "dur": <sec>}
        wrapped as {"t0": 0, "actions": [...] } OR a bare list [ ... ]

    Timing:
      - speed > 1.0  -> faster (press & durations are divided by speed)
      - jitter_time  -> +/- fraction of t_press (per event, re-sampled each loop)
      - jitter_hold  -> +/- fraction of dur (per event, re-sampled each loop)
      - min_hold_s   -> minimum hold per key
      - min_repeat_same_key_s -> minimum time between two presses of the SAME key
                                 (enforced inside a loop AND across loop boundaries)
      - loop         -> number of repetitions; <= 0 means infinite
      - stop_event   -> external cancel handle; immediate all-up on stop
    """

    def __init__(self, hidg_path: str):
        self.w = HIDWriter(hidg_path)

    # ----------------- loading & normalization -----------------

    @staticmethod
    def _load(path: str) -> Dict[str, Any]:
        data = json.loads(Path(path).read_text())
        if isinstance(data, dict):
            if "events" in data:
                ev = data["events"] or []
                assert isinstance(ev, list)
                return {"mode": "events", "events": ev}
            if "actions" in data:
                ac = data["actions"] or []
                assert isinstance(ac, list)
                return {"mode": "actions", "actions": ac}
        if isinstance(data, list):
            # try to detect
            if data and isinstance(data[0], dict) and {"t", "type", "usage"}.issubset(data[0].keys()):
                return {"mode": "events", "events": data}
            return {"mode": "actions", "actions": data}
        raise ValueError("Unknown recording format")

    @staticmethod
    def _events_to_actions(events: List[Dict[str, Any]]) -> List[Dict[str, float]]:
        """
        Convert a down/up event stream into press/dur actions.
        Unmatched downs are ignored (final all_up will clear them).
        """
        down_t: Dict[int, float] = {}
        out: List[Dict[str, float]] = []
        # Ensure chronological order
        for e in sorted(events, key=lambda x: float(x.get("t", 0.0))):
            usage = int(e["usage"])
            typ = str(e["type"])
            t = float(e["t"])
            if typ == "down":
                down_t[usage] = t
            elif typ == "up":
                t0 = down_t.pop(usage, None)
                if t0 is not None and t >= t0:
                    out.append({"usage": usage, "press": t0, "dur": t - t0})
        return out

    @staticmethod
    def _jitter(base: float, frac: float) -> float:
        """Symmetric +/- jitter around base; tiny extra noise to de-correlate."""
        if frac <= 0 or base <= 0:
            return 0.0
        return random.uniform(-frac, +frac) * base + random.uniform(-0.001, 0.001)

    @staticmethod
    async def _sleep_or_stop(delay: float, stop_event: Optional[asyncio.Event]) -> bool:
        """
        Sleep cooperatively for 'delay' seconds.
        Returns True if interrupted by stop_event, False otherwise.
        """
        if delay <= 0:
            return False
        if not stop_event:
            await asyncio.sleep(delay)
            return False
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
            return True
        except asyncio.TimeoutError:
            return False

    # ----------------- main playback -----------------

    async def play(
        self,
        path: str,
        *,
        speed: float = 1.0,
        jitter_time: float = 0.0,
        jitter_hold: float = 0.0,
        min_hold_s: float = 0.083,
        min_repeat_same_key_s: float = 0.134,
        loop: int = 1,
        stop_event: Optional[asyncio.Event] = None,
    ) -> bool:
        """
        Returns True if playback completed fully; False if interrupted.
        Supports repeating the recording `loop` times; if loop <= 0, repeats forever.
        """
        loaded = self._load(path)
        if loaded["mode"] == "events":
            base_actions = self._events_to_actions(loaded["events"])
        else:
            base_actions = loaded["actions"]

        if not base_actions:
            self.w.all_up()
            return True

        # Normalize press/dur for speed; keep no jitter yet
        norm_actions: List[Dict[str, float]] = []
        for a in base_actions:
            usage = int(a["usage"])
            press = float(a["press"]) / max(1e-6, speed)
            dur = float(a["dur"]) / max(1e-6, speed)
            dur = max(min_hold_s, _clamp_nonneg(dur))
            norm_actions.append({"usage": usage, "press": _clamp_nonneg(press), "dur": dur})

        # Track the last press time **globally** for each usage across loops
        global_last_press: Dict[int, float] = defaultdict(lambda: -1e9)

        def build_loop_schedule(offset: float) -> Tuple[List[Tuple[float, bool, int]], float, Dict[int, float]]:
            """
            Build one loop worth of events (with fresh jitter), shifted by `offset`.
            Ensures min_repeat per usage against both local last press and global_last_press.
            Returns (events, loop_end_time, last_press_this_loop)
            """
            last_press_local: Dict[int, float] = defaultdict(lambda: -1e-9)
            press_times: List[Tuple[float, float, int]] = []

            for a in norm_actions:
                usage = a["usage"]
                # Jitter per loop so each pass looks slightly different
                t_press = max(0.0, a["press"] + self._jitter(a["press"], jitter_time))
                dur = max(min_hold_s, max(0.0, a["dur"] + self._jitter(a["dur"], jitter_hold)))

                # Enforce min-repeat on the SAME key (do not apply to modifiers)
                if usage not in MOD_USAGES:
                    t_press = max(
                        t_press,
                        last_press_local[usage] + min_repeat_same_key_s,
                        (global_last_press[usage] + min_repeat_same_key_s) - offset,
                    )
                last_press_local[usage] = t_press

                press_times.append((t_press, dur, usage))

            # Convert press/dur into down/up with absolute times
            events: List[Tuple[float, bool, int]] = []
            loop_end = 0.0
            for t_press, dur, usage in press_times:
                t_down = offset + t_press
                t_up = t_down + dur
                events.append((t_down, True, usage))
                events.append((t_up, False, usage))
                if t_up > loop_end:
                    loop_end = t_up

            events.sort(key=lambda x: x[0])
            return events, loop_end, last_press_local

        # ---- Playback over loops ----
        played_fully = True
        t0 = time.monotonic()
        current_offset = 0.0
        loop_count = 0
        infinite = loop <= 0

        while infinite or loop_count < loop:
            # Allow stop between loops immediately
            if stop_event and stop_event.is_set():
                played_fully = False
                break

            # Fresh jitter every loop
            events, loop_end, last_press_local = build_loop_schedule(current_offset)

            # Play this loop
            modmask = 0
            down_keys: set[int] = set()
            now_rel = lambda: time.monotonic() - t0

            for t_abs, is_down, usage in events:
                if stop_event and stop_event.is_set():
                    self.w.all_up()
                    played_fully = False
                    break

                # Wait until it is time for this event (interruptible)
                remain = max(0.0, t_abs - now_rel())
                if await self._sleep_or_stop(remain, stop_event):
                    self.w.all_up()
                    played_fully = False
                    break

                # Apply the change
                if usage in MOD_USAGES:
                    bit = 1 << (usage - 224)
                    if is_down:
                        modmask |= bit
                    else:
                        modmask &= (~bit) & 0xFF
                else:
                    if is_down:
                        down_keys.add(usage)
                    else:
                        down_keys.discard(usage)

                self.w.send(modmask, down_keys)

            # Ensure all-up between loops (prevents stuck keys)
            self.w.all_up()

            if not played_fully:
                break

            # Update global last press timestamps using this loop's local presses
            for u, lp in last_press_local.items():
                global_last_press[u] = current_offset + lp

            # Next loop starts right after this one
            current_offset = loop_end
            loop_count += 1

        return played_fully
