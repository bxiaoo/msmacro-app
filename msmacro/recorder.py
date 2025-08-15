# /opt/msmacro-app/msmacro/recorder.py
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass, dataclass
from pathlib import Path
from typing import Any, Dict, List, Union


# (Optional) legacy shape used by older code paths:
@dataclass
class Action:
    usage: int
    press: float
    dur: float


SerializableAction = Union[Action, Dict[str, Any]]


class Recorder:
    """
    Flexible recorder container.
    - self.actions may be a list of legacy Action dataclasses OR plain dict events:
      • legacy "actions": {"usage": int, "press": float, "dur": float}
      • new "events"   : {"t": float, "type": "down"/"up", "usage": int}
    The save() method will detect the shape and serialize accordingly.
    """

    def __init__(self):
        self.actions: List[SerializableAction] = []
        self.t0: float = 0.0

    def _normalize_action_dict(self, a: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure numeric fields are the right type and keys are present.
        Returns a cleaned dict in the same shape.
        """
        keys = set(a.keys())
        if {"t", "type", "usage"}.issubset(keys):
            return {"t": float(a["t"]), "type": str(a["type"]), "usage": int(a["usage"])}
        if {"press", "dur", "usage"}.issubset(keys):
            return {"press": float(a["press"]), "dur": float(a["dur"]), "usage": int(a["usage"])}
        raise ValueError(f"Unknown action/event shape: keys={sorted(keys)}")

    def to_dict(self) -> Dict[str, Any]:
        """
        Produce a dict ready for JSON dump.
        Prefer the shape already present in self.actions:
          - if items look like {"t","type","usage"} → write {"t0", "events":[...]}
          - if items look like {"press","dur","usage"} or Action dataclass → write {"t0","actions":[...]}
        """
        out: Dict[str, Any] = {"t0": float(self.t0)}

        if not self.actions:
            # default to events list (works fine with the new player)
            out["events"] = []
            return out

        first = self.actions[0]

        # Dataclass?
        if is_dataclass(first):
            dlist = [asdict(x) for x in self.actions]  # type: ignore[arg-type]
            # Decide which shape based on keys present in the first item
            fkeys = set(dlist[0].keys())
            if {"t", "type", "usage"}.issubset(fkeys):
                out["events"] = [{**self._normalize_action_dict(x)} for x in dlist]
            elif {"press", "dur", "usage"}.issubset(fkeys):
                out["actions"] = [{**self._normalize_action_dict(x)} for x in dlist]
            else:
                raise ValueError(f"Unknown dataclass fields in Recorder: {sorted(fkeys)}")
            return out

        # Dict?
        if isinstance(first, dict):
            first_norm = self._normalize_action_dict(first)
            if {"t", "type", "usage"}.issubset(first_norm.keys()):
                out["events"] = [self._normalize_action_dict(x) for x in self.actions]  # type: ignore[list-item]
                return out
            if {"press", "dur", "usage"}.issubset(first_norm.keys()):
                out["actions"] = [self._normalize_action_dict(x) for x in self.actions]  # type: ignore[list-item]
                return out

        # Anything else: error
        raise TypeError("Recorder.actions must contain dicts or dataclass instances")

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def save(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json())
