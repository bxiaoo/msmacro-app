import json, asyncio, random, time
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from .hidio import HIDWriter

MOD_USAGES = set(range(224, 232))  # 224..231


class Player:
    def __init__(self, hidg_path: str):
        self.w = HIDWriter(hidg_path)

    # --- helper: jitter ---
    @staticmethod
    def _jitter(base: float, frac: float) -> float:
        if frac <= 0 or base <= 0:
            return 0.0
        return random.uniform(-frac, +frac) * base + random.uniform(-0.001, 0.001)

    # --- NEW: load actions/events from JSON and normalize ---
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
            # try to detect list shape
            if data and isinstance(data[0], dict) and {"t", "type", "usage"}.issubset(data[0].keys()):
                return {"mode": "events", "events": data}
            return {"mode": "actions", "actions": data}
        raise ValueError("Unknown recording format")

    # --- NEW: convert event stream -> action (press/dur) list ---
    @staticmethod
    def _events_to_actions(events: List[Dict[str, Any]]) -> List[Dict[str, float]]:
        down_t: Dict[int, float] = {}
        out: List[Dict[str, float]] = []
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
        # We ignore keys left down with no up; they’ll be “all_up” at the end anyway.
        return out

    # --- cooperative sleep (interruptible) ---
    @staticmethod
    async def _sleep_or_stop(delay: float, stop_event: Optional[asyncio.Event]) -> bool:
        if not stop_event or delay <= 0:
            if delay > 0:
                await asyncio.sleep(delay)
            return False
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
            return True
        except asyncio.TimeoutError:
            return False

    async def play(self, path: str, *,
                   speed: float = 1.0,
                   jitter_time: float = 0.0,
                   jitter_hold: float = 0.0,
                   min_hold_s: float = 0.083,
                   min_repeat_same_key_s: float = 0.134,
                   loop: int = 1,
                   stop_event: Optional[asyncio.Event] = None) -> bool:
        """
        Returns True if playback completed; False if interrupted via stop_event.
        Supports recordings saved as {"events":[...]} or {"actions":[...]}.
        """
        loaded = self._load(path)
        mode = loaded["mode"]
        if mode == "events":
            actions = self._events_to_actions(loaded["events"])
        else:
            actions = loaded["actions"]

        if not actions:
            self.w.all_up()
            return True

        # normalize actions (apply speed, jitter, minima)
        press_times: List[Tuple[float, float, int]] = []
        last_press: Dict[int, float] = defaultdict(lambda: -1e9)
        for a in actions:
            usage = int(a["usage"])
            t_press = float(a["press"]) / max(1e-6, speed)
            dur = float(a["dur"]) / max(1e-6, speed)
            t_press = max(0.0, t_press + self._jitter(t_press, jitter_time))
            dur = max(min_hold_s, max(0.0, dur + self._jitter(dur, jitter_hold)))
            t_press = max(t_press, last_press[usage] + min_repeat_same_key_s)
            last_press[usage] = t_press
            press_times.append((t_press, dur, usage))

        # build event schedule
        events: List[Tuple[float, bool, int]] = []
        for t_press, dur, usage in press_times:
            events.append((t_press, True, usage))
            events.append((t_press + dur, False, usage))
        events.sort(key=lambda x: x[0])

        t0 = time.monotonic()
        down_keys = set()
        modmask = 0

        for t, is_down, usage in events:
            if stop_event and stop_event.is_set():
                self.w.all_up()
                return False

            remaining = max(0.0, t - (time.monotonic() - t0))
            if await self._sleep_or_stop(remaining, stop_event):
                self.w.all_up()
                return False

            # update state
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

            if stop_event and stop_event.is_set():
                self.w.all_up()
                return False

        self.w.all_up()
        return True
