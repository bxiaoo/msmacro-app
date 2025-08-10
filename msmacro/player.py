import json, time, asyncio, random
from collections import defaultdict
from typing import List, Tuple, Optional
from .hidio import HIDWriter

MOD_USAGES = set(range(224, 232))  # 224..231

class Player:
    def __init__(self, hidg_path: str):
        self.w = HIDWriter(hidg_path)

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
        Enforces human-like minima: hold >= min_hold_s, same key re-press >= min_repeat_same_key_s.
        """
        data = json.load(open(path))
        actions = data["actions"]

        for _ in range(max(1, loop)):
            # Build press/release events with jitter and constraints
            # 1) compute times
            press_times = []
            last_press = defaultdict(lambda: -1e9)
            for a in actions:
                t_press = a["press"]/speed + self._jitter(a["press"], jitter_time)
                dur     = a["dur"]/speed   + self._jitter(a["dur"],   jitter_hold)
                t_press = max(0.0, t_press)
                dur     = max(min_hold_s, max(0.0, dur))
                # enforce same-key repeat spacing
                t_press = max(t_press, last_press[a["usage"]] + min_repeat_same_key_s)
                last_press[a["usage"]] = t_press
                press_times.append((t_press, dur, a["usage"]))

            # 2) expand to events
            events: List[Tuple[float, bool, int]] = []
            for t_press, dur, usage in press_times:
                events.append((t_press, True,  usage))
                events.append((t_press + dur, False, usage))
            events.sort(key=lambda x: x[0])

            # 3) run
            t0 = time.monotonic()
            down_keys = set()
            modmask = 0
            for t, is_down, usage in events:
                # cooperative wait with stop support
                if stop_event is not None:
                    # wait for either timeout or stop_event
                    remaining = max(0, t - (time.monotonic() - t0))
                    try:
                        await asyncio.wait_for(asyncio.shield(stop_event.wait()), timeout=remaining)
                        # stop signaled
                        self.w.all_up()
                        return False
                    except asyncio.TimeoutError:
                        pass
                else:
                    await asyncio.sleep(max(0, t - (time.monotonic() - t0)))

                if usage in MOD_USAGES:
                    bit = 1 << (usage - 224)
                    if is_down: modmask |= bit
                    else:       modmask &= (~bit) & 0xFF
                else:
                    if is_down: down_keys.add(usage)
                    else:       down_keys.discard(usage)
                self.w.send(modmask, down_keys)

            self.w.all_up()

        return True

    @staticmethod
    def _jitter(base: float, frac: float) -> float:
        if frac <= 0 or base <= 0: return 0.0
        return random.uniform(-frac, +frac) * base + random.uniform(-0.001, 0.001)
