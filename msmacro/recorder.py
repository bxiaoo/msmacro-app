import json, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List

@dataclass
class Action:
    usage: int   # HID usage (includes modifiers 224..231)
    press: float # seconds from start
    dur: float   # seconds held

@dataclass
class Recording:
    format: str
    created: str
    count: int
    actions: List[Action]

class Recorder:
    def __init__(self):
        self.t0 = None
        self.pressed_at: Dict[int, float] = {}
        self.actions: List[Action] = []

    def start(self):
        self.t0 = time.monotonic()
        self.pressed_at.clear()
        self.actions.clear()

    def on_down(self, usage: int):
        if usage and usage not in self.pressed_at:
            self.pressed_at[usage] = time.monotonic()

    def on_up(self, usage: int):
        t = time.monotonic()
        if usage and usage in self.pressed_at and self.t0 is not None:
            press = self.pressed_at.pop(usage)
            self.actions.append(Action(usage=usage, press=press - self.t0, dur=t - press))

    def to_json(self) -> str:
        from datetime import datetime
        rec = Recording(
            format="msmacro.v1",
            created=datetime.utcnow().isoformat()+"Z",
            count=len(self.actions),
            actions=self.actions,
        )
        d = asdict(rec)
        d["actions"] = [asdict(a) for a in self.actions]
        import json
        return json.dumps(d, indent=2)

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())
