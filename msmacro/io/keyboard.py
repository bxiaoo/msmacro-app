import glob, subprocess, os, asyncio, logging
import shlex
from typing import Optional

# Platform abstraction
from .platform_abstraction import IS_MACOS, IS_LINUX, HAS_EVDEV

log = logging.getLogger(__name__)

def _is_keyboard_event(evpath: str) -> bool:
    # Ask udev for properties; ID_INPUT_KEYBOARD=1 means "this really is a keyboard"
    try:
        # Validate input path to prevent injection
        if not evpath.startswith('/dev/input/'):
            return False
        # Use shlex.quote for additional safety
        safe_path = shlex.quote(evpath)
        out = subprocess.check_output(
            ["udevadm", "info", "-q", "property", "-n", safe_path],
            text=True, stderr=subprocess.DEVNULL
        )
        return any(line.strip() == "ID_INPUT_KEYBOARD=1" for line in out.splitlines())
    except Exception:
        return False

def find_keyboard_event() -> str:
    """
    Find keyboard input device (platform-aware).

    On Linux: Scans /dev/input/* for keyboard devices
    On macOS: Returns mock keyboard device path

    Returns:
        str: Device path

    Raises:
        SystemExit: If no keyboard found on Linux
    """
    # macOS: Use mock keyboard
    if IS_MACOS:
        from .keyboard_mock import find_keyboard_event_mock
        return find_keyboard_event_mock()

    # Linux: Real keyboard discovery
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

def find_keyboard_event_safe() -> Optional[str]:
    """
    Always Work™ version that returns None instead of raising SystemExit.
    Use this for service startup where we want graceful degradation.

    Platform-aware: Returns mock keyboard on macOS.
    """
    # macOS: Use mock keyboard (always succeeds)
    if IS_MACOS:
        from .keyboard_mock import find_keyboard_event_safe as find_keyboard_event_safe_mock
        return find_keyboard_event_safe_mock()

    # Linux: Real keyboard discovery
    try:
        # 1) Prefer friendly by-id symlinks
        byid = sorted(glob.glob("/dev/input/by-id/*-event-kbd"))
        for p in byid:
            if os.path.exists(p):
                return p
        # 2) Fallback: scan all event* and pick the first with ID_INPUT_KEYBOARD=1
        for ev in sorted(glob.glob("/dev/input/event*")):
            if _is_keyboard_event(ev):
                return ev
        return None
    except Exception:
        return None

async def find_keyboard_with_retry(
    max_retries: Optional[int] = None,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_multiplier: float = 1.5
) -> Optional[str]:
    """
    Always Work™ keyboard discovery with exponential backoff retry logic.

    Platform-aware: Returns mock keyboard immediately on macOS.

    Args:
        max_retries: Maximum number of retry attempts. None for infinite retries.
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_multiplier: Factor to multiply delay by each retry

    Returns:
        Keyboard device path if found, None if max_retries exceeded
    """
    # macOS: Use mock keyboard (no retry needed)
    if IS_MACOS:
        from .keyboard_mock import find_keyboard_with_retry_mock
        return await find_keyboard_with_retry_mock(max_retries, initial_delay, max_delay)

    # Linux: Real keyboard discovery with retry
    retry_count = 0
    delay = initial_delay

    while max_retries is None or retry_count < max_retries:
        # Try to find keyboard
        device_path = find_keyboard_event_safe()
        if device_path:
            if retry_count > 0:
                log.info(f"Keyboard found after {retry_count} retries: {device_path}")
            else:
                log.debug(f"Keyboard found: {device_path}")
            return device_path

        # Log attempt
        if retry_count == 0:
            log.warning("No keyboard detected, will retry with exponential backoff...")
        else:
            log.debug(f"Keyboard discovery attempt {retry_count + 1} failed, retrying in {delay:.1f}s")

        # Wait before next retry
        await asyncio.sleep(delay)

        # Update for next iteration
        retry_count += 1
        delay = min(delay * backoff_multiplier, max_delay)

    log.error(f"Failed to find keyboard after {max_retries} retries")
    return None
