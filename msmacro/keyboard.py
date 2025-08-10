import glob, subprocess, os

def _is_keyboard_event(evpath: str) -> bool:
    # Ask udev for properties; ID_INPUT_KEYBOARD=1 means "this really is a keyboard"
    try:
        out = subprocess.check_output(
            ["udevadm", "info", "-q", "property", "-n", evpath],
            text=True, stderr=subprocess.DEVNULL
        )
        return any(line.strip() == "ID_INPUT_KEYBOARD=1" for line in out.splitlines())
    except Exception:
        return False

def find_keyboard_event() -> str:
    # 1) Prefer friendly by-id symlinks
    byid = sorted(glob.glob("/dev/input/by-id/*-event-kbd"))
    for p in byid:
        if os.path.exists(p):
            return p
    # 2) Fallback: scan all event* and pick the first with ID_INPUT_KEYBOARD=1
    for ev in sorted(glob.glob("/dev/input/event*")):
        if _is_keyboard_event(ev):
            return ev
    raise SystemExit("No keyboard input device found (ID_INPUT_KEYBOARD=1)")
