import json, os, pathlib, time

PATH = os.environ.get("MSMACRO_EVENTS", "/run/msmacro.events")

def path() -> str:
    return PATH

def emit(kind: str, **kv):
    p = pathlib.Path(PATH)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    line = {"ts": time.time(), "event": kind, **kv}
    with open(p, "a") as f:
        f.write(json.dumps(line) + "\n")
    # Set secure permissions on the log file (owner read/write only)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass  # Ignore permission errors
    return line
