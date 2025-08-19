# /opt/msmacro-app/msmacro/recorder.py
from __future__ import annotations

import json
from dataclasses import dataclass, is_dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Union, Optional

# Optional legacy shape
@dataclass
class Action:
    usage: int
    press: float
    dur: float

SerializableAction = Union[Action, Dict[str, Any]]

class Recorder:
    """
    Collects raw key DOWN/UP timestamps and emits compact press/duration "actions".
    Supports mixed legacy dict/dataclass inputs when loading/saving.
    """
    def __init__(self, actions: Optional[List[SerializableAction]] = None, *, t0: float = 0.0) -> None:
        self.t0: float = float(t0)
        self.actions: List[SerializableAction] = list(actions or [])
        # live capture state (usage -> press_time)
        self._downs: Dict[int, float] = {}
        self._last_time: float = self.t0

    # ----- live collection API -----
    def on_down(self, usage: int, now: float) -> None:
        # Don't double-enter; keep first timestamp
        self._downs.setdefault(int(usage), float(now))

    def on_up(self, usage: int, now: float) -> None:
        u = int(usage)
        t_press = self._downs.pop(u, None)
        if t_press is None:
            # synthesize a tiny press if we missed the down
            t_press = float(now)
            dur = 0.0
        else:
            dur = max(0.0, float(now) - float(t_press))
        self._append_action(u, float(t_press), float(dur))
        self._last_time = float(now)

    def finalize(self, now: Optional[float] = None) -> None:
        """
        If keys are still held, close them with the provided 'now' timestamp.
        """
        n = float(now if now is not None else self._last_time)
        if self._downs:
            for u, t_press in list(self._downs.items()):
                dur = max(0.0, n - float(t_press))
                self._append_action(int(u), float(t_press), float(dur))
            self._downs.clear()

    # ----- internal -----
    def _append_action(self, usage: int, abs_press: float, dur: float) -> None:
        rel_press = max(0.0, float(abs_press) - float(self.t0))
        self.actions.append({"usage": int(usage), "press": rel_press, "dur": float(dur)})

    # ----- serialization -----
    @staticmethod
    def _normalize_action_dict(a: Dict[str, Any]) -> Dict[str, Any]:
        keys = set(a.keys())
        if {"usage", "press", "dur"}.issubset(keys):
            return {"usage": int(a["usage"]), "press": float(a["press"]), "dur": float(a["dur"])}
        if {"t", "type", "usage"}.issubset(keys):
            # keep event shape; let player convert when needed
            return {"t": float(a["t"]), "type": str(a["type"]), "usage": int(a["usage"])}
        raise ValueError(f"Unknown action/event shape: keys={sorted(keys)}")

    def to_dict(self, prefer: str = "actions") -> Dict[str, Any]:
        """
        prefer: 'actions' | 'events'
        If prefer='actions' but items look like events, we will still write events.
        """
        out: Dict[str, Any] = {"t0": float(self.t0)}
        if not self.actions:
            out["actions" if prefer == "actions" else "events"] = []
            return out

        first = self.actions[0]
        if is_dataclass(first):
            dlist = [asdict(x) for x in self.actions]  # type: ignore[arg-type]
            fkeys = set(dlist[0].keys())
            if {"usage","press","dur"}.issubset(fkeys):
                out["actions"] = [self._normalize_action_dict(x) for x in dlist]
            elif {"t","type","usage"}.issubset(fkeys):
                out["events"] = [self._normalize_action_dict(x) for x in dlist]
            else:
                raise ValueError("Unknown dataclass fields")
            return out

        if isinstance(first, dict):
            first_norm = self._normalize_action_dict(first)
            if {"usage","press","dur"}.issubset(first_norm.keys()) and prefer == "actions":
                out["actions"] = [self._normalize_action_dict(x) for x in self.actions]  # type: ignore[list-item]
                return out
            if {"t","type","usage"}.issubset(first_norm.keys()):
                out["events"] = [self._normalize_action_dict(x) for x in self.actions]  # type: ignore[list-item]
                return out
            # default to actions
            out["actions"] = [self._normalize_action_dict(x) for x in self.actions]  # type: ignore[list-item]
            return out

        raise TypeError("Recorder.actions must contain dicts or dataclass instances")

    def to_json(self, prefer: str = "actions") -> str:
        return json.dumps(self.to_dict(prefer=prefer), ensure_ascii=False, indent=2)

    def save(self, path: Union[str, Path], prefer: str = "actions") -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(prefer=prefer), encoding="utf-8")

    # ----- loaders -----
    @classmethod
    def from_json(cls, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> "Recorder":
        if isinstance(data, dict):
            if "actions" in data and isinstance(data["actions"], list):
                return cls(actions=list(data["actions"]), t0=float(data.get("t0", 0.0)))
            if "events" in data and isinstance(data["events"], list):
                return cls(actions=list(data["events"]), t0=float(data.get("t0", 0.0)))
            raise TypeError("Unknown recording dict shape (expected 'actions' or 'events').")
        elif isinstance(data, list):
            return cls(actions=data, t0=0.0)
        else:
            raise TypeError("Recording JSON must be dict or list.")

    @classmethod
    def load_from_path(cls, path: Union[str, Path]) -> "Recorder":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_json(data)

# ---------- playlist-friendly helpers ----------

def _safe_relpath(name: str) -> Path:
    p = Path(str(name).strip().strip("/"))
    if not p.parts:
        raise ValueError("Empty recording name")
    for part in p.parts:
        if part in ("", ".", ".."):
            raise ValueError(f"Invalid path component: {part!r}")
    return p

def resolve_record_path(base_dir: Union[str, Path], name_or_path: Union[str, Path]) -> Path:
    base = Path(base_dir)
    p = Path(name_or_path)
    if p.is_absolute():
        return p
    if p.suffix.lower() != ".json":
        p = _safe_relpath(str(p)).with_suffix(".json")
    else:
        p = _safe_relpath(str(p))
    return base / p

def list_recordings_recursive(base_dir: Union[str, Path]) -> List[Dict[str, Any]]:
    base = Path(base_dir)
    items: List[Dict[str, Any]] = []
    if not base.exists():
        return items
    for f in base.rglob("*.json"):
        try:
            logical = f.relative_to(base).with_suffix("").as_posix()
        except Exception:
            continue
        meta: Dict[str, Any] = {}
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                if "actions" in data and isinstance(data["actions"], list):
                    meta["actions"] = len(data["actions"])
                if "events" in data and isinstance(data["events"], list):
                    meta["events"] = len(data["events"])
                if "duration" in data:
                    try:
                        meta["duration"] = float(data["duration"])
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            stat = f.stat()
            items.append({
                "name": logical,
                "path": str(f),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                **({"meta": meta} if meta else {}),
            })
        except Exception:
            continue
    items.sort(key=lambda x: x["name"])
    return items

__all__ = [
    "Action",
    "Recorder",
    "resolve_record_path",
    "list_recordings_recursive",
]
