import json, os, pathlib, time

PATH = os.environ.get("MSMACRO_EVENTS", "/run/msmacro.events")

def path() -> str:
    return PATH

def emit(kind: str, **kv):
    p = pathlib.Path(PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = {"ts": time.time(), "event": kind, **kv}
    with open(p, "a") as f:
        f.write(json.dumps(line) + "\n")
    return line
