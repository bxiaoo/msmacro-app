# Fixed player.py with better stop event handling and timing

from __future__ import annotations

import asyncio
import json
import random
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from ..io.hidio import HIDWriter
from ..utils.keymap import name_to_usage

from .humanJitter import HumanJitter
from .skill_injector import SkillInjector

# HID usage IDs for modifier keys (Left/Right Ctrl, Shift, Alt, GUI)
MOD_USAGES = set(range(224, 232))  # 224..231


class Player:
    """
    Replays a recorded keyboard sequence to the HID gadget.
    """

    def __init__(self, hidg_path: Union[str, Path]) -> None:
        self.w = HIDWriter(hidg_path)

    @staticmethod
    def _parse_ignore_keys(ignore_keys: Optional[List[str]]) -> set[int]:
        """Convert user-friendly key names to HID usage IDs for ignoring."""
        if not ignore_keys:
            return set()
        
        ignore_usages = set()
        
        for key_name in ignore_keys:
            usage = name_to_usage(key_name)
            if usage > 0:
                ignore_usages.add(usage)
        
        return ignore_usages

    # ---------------- utils ----------------
    @staticmethod
    def _load(path: Union[str, Path]) -> Dict[str, Any]:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if "events" in data:
                return {"mode": "events", "events": list(data["events"] or [])}
            if "actions" in data:
                return {"mode": "actions", "actions": list(data["actions"] or [])}
            # Unknown dict shape; try to guess
            if data.get("type") in ("down", "up") and "usage" in data and "t" in data:
                return {"mode": "events", "events": [data]}
            raise TypeError("Unknown recording dict shape.")
        elif isinstance(data, list):
            # Heuristic: items with key 't' => events, else actions
            if data and isinstance(data[0], dict) and "t" in data[0]:
                return {"mode": "events", "events": data}
            else:
                return {"mode": "actions", "actions": data}
        else:
            raise TypeError("Recording JSON must be dict or list.")

    @staticmethod
    def _events_to_actions(events: List[Dict[str, Any]]) -> List[Dict[str, float]]:
        """
        Turn down/up pairs into sequential actions.
        """
        # actions: List[Dict[str, float]] = []
        # down_time: Dict[int, float] = {}
        # cursor = 0.0

        # for ev in sorted(events, key=lambda e: float(e.get("t", 0.0))):
        #     t = float(ev.get("t", 0.0))
        #     typ = str(ev.get("type", "")).lower()
        #     usage = int(ev.get("usage", -1))
        #     if usage < 0:
        #         continue

        #     if typ in ("down", "press"):
        #         down_time[usage] = t
        #     elif typ in ("up", "release"):
        #         t0 = down_time.pop(usage, None)
        #         if t0 is None:
        #             # unmatched up; treat as a tap with minimal duration
        #             press_delay = max(0.0, t - cursor)
        #             dur = 0.010  # 10ms default
        #         else:
        #             press_delay = max(0.0, t0 - cursor)
        #             dur = max(0.001, t - t0)  # At least 1ms
        #         actions.append({"usage": usage, "press": press_delay, "dur": dur})
        #         cursor = t

        # # any residual downs -> synthesize small taps at end
        # for usage, t0 in down_time.items():
        #     press_delay = max(0.0, t0 - cursor)
        #     actions.append({"usage": int(usage), "press": press_delay, "dur": 0.010})
        #     cursor = t0 + 0.010

        # return actions
        evs = sorted(events or [], key=lambda e: float(e.get("t", 0.0)))
        if not evs:
            return []

        t0 = float(evs[0].get("t", 0.0))  # base time
        down_at: Dict[int, float] = {}
        actions: List[Dict[str, float]] = []

        for ev in evs:
            t_abs = float(ev.get("t", 0.0))
            t = t_abs - t0  # seconds since start
            typ = str(ev.get("type", "")).lower()
            usage = int(ev.get("usage", -1))
            if usage < 0:
                continue

            if typ in ("down", "press"):
                down_at[usage] = t
            elif typ in ("up", "release"):
                t_down = down_at.pop(usage, None)
                if t_down is None:
                    # unmatched up => synthesize a short tap ending at t
                    t_down = max(0.0, t - 0.001)
                dur = max(0.0, t - t_down)
                actions.append({"usage": usage, "press": t_down, "dur": dur})

        # Close any residual downs as tiny taps
        for usage, t_down in down_at.items():
            actions.append({"usage": usage, "press": t_down, "dur": 0.010})

        actions.sort(key=lambda a: (a["press"], a["usage"]))
        return actions

    @staticmethod
    async def _sleep_or_stop(delay: float, stop_event: Optional[asyncio.Event]) -> bool:
        """
        Sleep cooperatively for 'delay' seconds, checking stop_event frequently.
        Returns True if interrupted by stop_event, False otherwise.
        """
        if delay <= 0:
            return False
        if not stop_event:
            await asyncio.sleep(delay)
            return False
        
        # Check stop event frequently (every 10ms) for responsive stopping
        check_interval = 0.010  # 10ms
        elapsed = 0.0
        
        while elapsed < delay:
            if stop_event.is_set():
                return True
            
            sleep_time = min(check_interval, delay - elapsed)
            await asyncio.sleep(sleep_time)
            elapsed += sleep_time
            
        return False

    # ---------------- core playback ----------------
    async def play(
        self,
        path: Union[str, Path],
        *,
        speed: float = 1.0,
        jitter_time: float = 0.0,
        jitter_hold: float = 0.0,
        min_hold_s: float = 0.001,  # Reduced to 1ms minimum
        min_repeat_same_key_s: float = 0.010,  # Reduced to 10ms minimum
        loop: int = 1,
        stop_event: Optional[asyncio.Event] = None,
        ignore_keys: Optional[List[str]] = None,
        ignore_tolerance: float = 0.0,
        skill_injector: Optional[SkillInjector] = None,
    ) -> bool:
        """
        Returns True if playback completed fully; False if interrupted.
        """
        loaded = self._load(path)
        # if loaded["mode"] == "events":
        #     base_actions = self._events_to_actions(loaded["events"])
        # else:
        #     base_actions = loaded["actions"]

        # if not base_actions:
        #     self.w.all_up()
        #     return True

        # # Apply speed factor properly
        # # When speed > 1.0, everything should be faster (shorter delays)
        # # When speed < 1.0, everything should be slower (longer delays)
        # actions: List[Dict[str, float]] = []
        # for a in base_actions:
        #     usage = int(a["usage"])
        #     press = float(a.get("press", 0.0))
        #     dur = float(a.get("dur", 0.010))
            
        #     # Apply speed factor (divide by speed to make faster when speed > 1)
        #     if speed > 0:
        #         press = press / speed
        #         dur = dur / speed
            
        #     actions.append({"usage": usage, "press": press, "dur": dur})

        # # Key state
        # modmask: int = 0
        # down_keys: set[int] = set()
        # last_up_time: Dict[int, float] = {}
        # now = 0.0  # virtual time within the loop

        if loaded["mode"] == "events":
            abs_actions = self._events_to_actions(loaded["events"])
        else:
            # recorder already stores seconds since t0 for actions
            abs_actions = loaded["actions"]

        if not abs_actions:
            self.w.all_up()
            return True

        # 2) Apply speed: faster => divide timeline & holds
        inv_speed = 1.0 / speed if speed and speed > 0 else 1.0

        scaled = [{
            "usage": int(a["usage"]),
            "press_at": max(0.0, float(a.get("press", 0.0)) * inv_speed),   # absolute on the scaled timeline
            "dur":     max(0.0, float(a.get("dur",   0.0)) * inv_speed),
        } for a in abs_actions]

        # 2) Apply keystroke ignore randomization
        ignore_usages = self._parse_ignore_keys(ignore_keys)
        if ignore_usages and ignore_tolerance > 0:
            original_count = len(scaled)
            filtered_scaled = []
            ignored_count = 0
            for a in scaled:
                usage = a["usage"]
                # Apply ignore randomization if this key is in the ignore list
                if usage in ignore_usages and random.random() < ignore_tolerance:
                    # Skip this keystroke (ignore it)
                    ignored_count += 1
                    continue
                filtered_scaled.append(a)
            scaled = filtered_scaled
            print(f"🎲 Keystroke randomization: ignored {ignored_count}/{original_count} actions")
            print(f"   ignore_keys={ignore_keys}, ignore_usages={ignore_usages}, tolerance={ignore_tolerance}")
        elif ignore_keys or ignore_tolerance > 0:
            print(f"🎲 Keystroke randomization: no filtering applied")
            print(f"   ignore_keys={ignore_keys}, ignore_usages={ignore_usages}, tolerance={ignore_tolerance}")

        # 3) Jitter per keystroke (independent), with same-key gap enforcement
        #    - press jitter anchor: time since previous press of the same key; if none, 40ms anchor
        #    - hold jitter anchor: the action's own duration
        last_press_of_key: Dict[int, float] = {}
        last_up_time: Dict[int, float] = {}

        hj = HumanJitter(
            factor_time=jitter_time,
            factor_hold=jitter_hold,
            drift_strength=0.90,
            drift_ratio=0.35,
            time_floor_s=0.040,
            time_soft_s=0.200,
            abs_cap_time_s=0.012,
        )

        jittered = []
        for a in scaled:
            u = a["usage"]
            press_at = a["press_at"]
            dur = a["dur"]

            # press jitter
            press_anchor = max(0.040, press_at - last_press_of_key.get(u, -1e9))  # seconds
            press_at += hj.time_jitter(u, press_anchor)
            if press_at < 0.0:
                press_at = 0.0

            # hold jitter with floor
            hold = max(min_hold_s, dur + hj.hold_jitter(u, dur))

            # same-key spacing: ensure next press >= last_up + min_repeat
            earliest_for_key = last_up_time.get(u, -1e9) + min_repeat_same_key_s
            if press_at < earliest_for_key:
                press_at = earliest_for_key
            
            release_at = press_at + hold

            jittered.append({"usage": u, "press_at": press_at, "release_at": release_at})

            last_press_of_key[u] = press_at
            last_up_time[u] = release_at  # for spacing of the NEXT press of this key

        # 3) Build a unified event timeline (press & release), sorted by time
        events: List[Tuple[float, str, int]] = []
        for x in jittered:
            events.append((x["press_at"],   "down", x["usage"]))
            events.append((x["release_at"], "up",   x["usage"]))
        events.sort(key=lambda t: (t[0], 0 if t[1] == "down" else 1, t[2]))  # if same time: down before up

        # 4) Run (stop-responsive); supports overlaps by updating HID state at each event
        def iter_loops():
            return range(loop) if loop > 0 else iter(int, 1)

        for _ in iter_loops():
            if stop_event and stop_event.is_set():
                self.w.all_up(); return False

            now = 0.0
            modmask = 0
            down_keys: set[int] = set()
            self.w.all_up()

            for t, kind, usage in events:
                wait = max(0.0, t - now)
                if await self._sleep_or_stop(wait, stop_event):
                    self.w.all_up(); return False
                now = t

                # Check for skill injection (only when no keys are pressed)
                if skill_injector:
                    current_time = time.time()

                    # Check if rotation is frozen
                    if skill_injector.should_freeze_rotation(current_time):
                        # Skip this event if rotation is frozen
                        continue

                    # Check for skill injection when no keys are pressed
                    current_keys_list = list(down_keys)

                    # Try to inject skill (this checks all conditions)
                    skill_cast_info = skill_injector.check_and_inject_skills(
                        current_keys_list, current_time
                    )

                    if skill_cast_info:
                        # A skill should be cast!
                        skill_usage = skill_cast_info["usage"]
                        pre_pause = skill_cast_info["pre_pause"]
                        post_pause = skill_cast_info["post_pause"]
                        press_duration = skill_cast_info["press_duration"]

                        # Pre-pause (for frozen rotation)
                        if pre_pause > 0:
                            if await self._sleep_or_stop(pre_pause, stop_event):
                                self.w.all_up(); return False

                        # Press skill key
                        if skill_usage in MOD_USAGES:
                            modmask |= (1 << (skill_usage - 224))
                        else:
                            down_keys.add(skill_usage)
                        self.w.send(modmask, down_keys)

                        # Hold key
                        if await self._sleep_or_stop(press_duration, stop_event):
                            self.w.all_up(); return False

                        # Release skill key
                        if skill_usage in MOD_USAGES:
                            modmask &= (~(1 << (skill_usage - 224))) & 0xFF
                        else:
                            down_keys.discard(skill_usage)
                        self.w.send(modmask, down_keys)

                        # Post-pause (for frozen rotation)
                        if post_pause > 0:
                            if await self._sleep_or_stop(post_pause, stop_event):
                                self.w.all_up(); return False

                # Process original event
                if kind == "down":
                    if usage in MOD_USAGES:
                        modmask |= (1 << (usage - 224))
                    else:
                        down_keys.add(usage)
                    self.w.send(modmask, down_keys)
                else:
                    if usage in MOD_USAGES:
                        modmask &= (~(1 << (usage - 224))) & 0xFF
                    else:
                        down_keys.discard(usage)
                    self.w.send(modmask, down_keys)

            # loop boundary: ensure all keys up
            self.w.all_up()

        return True

    # ---------------- playlist wrapper ----------------
    async def play_playlist(
        self,
        selections: Iterable[Union[str, Path]],
        *,
        loop: int = 1,
        speed: float = 1.0,
        jitter_time: float = 0.0,
        jitter_hold: float = 0.0,
        min_hold_s: float = 0.001,
        min_repeat_same_key_s: float = 0.010,
        stop_event: Optional[asyncio.Event] = None,
        ignore_keys: Optional[List[str]] = None,
        ignore_tolerance: float = 0.0,
        skill_injector: Optional[SkillInjector] = None,
    ) -> bool:
        """
        Randomly pick ONE recording from 'selections' per loop and play it.
        """
        paths: List[str] = []
        for s in selections or []:
            sp = str(s)
            if not sp.endswith(".json") and not Path(sp).exists():
                sp = sp + ".json"
            if Path(sp).exists():
                paths.append(sp)
        if not paths:
            self.w.all_up()
            return True

        def iter_loops():
            if loop <= 0:
                while True:
                    yield
            else:
                for _ in range(loop):
                    yield

        for _ in iter_loops():
            if stop_event and stop_event.is_set():
                self.w.all_up()
                return False
                
            pick = random.choice(paths)
            ok = await self.play(
                pick,
                speed=speed,
                jitter_time=jitter_time,
                jitter_hold=jitter_hold,
                min_hold_s=min_hold_s,
                min_repeat_same_key_s=min_repeat_same_key_s,
                loop=1,
                stop_event=stop_event,
                ignore_keys=ignore_keys,
                ignore_tolerance=ignore_tolerance,
                skill_injector=skill_injector,
            )
            if not ok:
                return False

        return True


__all__ = ["Player"]
