"""Mock evdev.InputDevice for macOS development.

This module provides mock keyboard input functionality for testing
and development on macOS where evdev is not available.
"""

import asyncio
import logging
import time
from typing import AsyncIterator, Optional
from .platform_abstraction import ecodes

logger = logging.getLogger(__name__)


class MockInputEvent:
    """
    Mock evdev InputEvent.

    Mimics the structure of evdev.InputEvent for compatibility.
    """

    def __init__(self, sec: int, usec: int, type: int, code: int, value: int):
        self.sec = sec
        self.usec = usec
        self.type = type
        self.code = code
        self.value = value
        self.timestamp = float(sec) + (usec / 1000000.0)

    def __repr__(self):
        return f"MockInputEvent(type={self.type}, code={self.code}, value={self.value})"


class MockInputDevice:
    """
    Mock evdev.InputDevice for macOS development.

    Provides the same API as evdev.InputDevice but doesn't require
    /dev/input/* devices. Useful for:
    - Testing daemon logic on macOS
    - Developing UI/state machine without hardware
    - Simulating keyboard events for testing

    Note: This does NOT capture actual keyboard input on macOS.
    For real keyboard capture, use the Linux/Pi deployment.
    """

    def __init__(self, device_path: str):
        """
        Initialize mock keyboard device.

        Args:
            device_path: Path to mock device (e.g., /dev/input/event0)
        """
        self.path = device_path
        self.name = "Mock Keyboard Device (macOS Development)"
        self.phys = "mock/input/keyboard"
        self.uniq = "mock-keyboard-00:00:00"
        self.info = (0x0001, 0x0001, 0x0001, 0x0001)  # (bustype, vendor, product, version)
        self._fd = -1
        self._grabbed = False
        self._event_queue = asyncio.Queue()
        self._closed = False

        logger.warning(f"🔶 MOCK Keyboard Device Initialized: {device_path}")
        logger.info("  → No actual keyboard will be captured")
        logger.info("  → Events can be injected via inject_event() for testing")
        logger.info("  → For real keyboard capture, deploy to Linux/Raspberry Pi")

    async def async_read_loop(self) -> AsyncIterator[MockInputEvent]:
        """
        Asynchronously yield mock keyboard events.

        This method provides the same async interface as evdev.InputDevice.
        Events can be injected using inject_event() method.

        Yields:
            MockInputEvent: Mock keyboard events
        """
        logger.debug("MOCK: Starting async_read_loop")

        while not self._closed:
            try:
                # Wait for event with timeout to allow checking closed flag
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=0.5
                )
                logger.debug(f"MOCK: Yielding event: {event}")
                yield event

            except asyncio.TimeoutError:
                # No events available, continue loop
                continue

            except asyncio.CancelledError:
                logger.debug("MOCK: async_read_loop cancelled")
                break

            except Exception as e:
                logger.error(f"MOCK: Error in async_read_loop: {e}")
                break

        logger.debug("MOCK: Exiting async_read_loop")

    def read_loop(self):
        """
        Synchronous event reading (generator).

        Provides compatibility with synchronous event reading code.
        """
        logger.debug("MOCK: Starting read_loop (sync)")

        while not self._closed:
            try:
                # Blocking get with timeout
                event = self._event_queue.get_nowait()
                logger.debug(f"MOCK: Yielding event (sync): {event}")
                yield event
            except:
                # No events, sleep briefly
                time.sleep(0.1)

    def grab(self):
        """
        Mock exclusive device access.

        On Linux, this grabs the device exclusively. On macOS, this
        just sets a flag for compatibility.
        """
        self._grabbed = True
        logger.debug("MOCK: Device grabbed (exclusive access mode)")

    def ungrab(self):
        """
        Mock release exclusive access.
        """
        self._grabbed = False
        logger.debug("MOCK: Device ungrabbed (released exclusive access)")

    def close(self):
        """
        Close the mock device.
        """
        self._closed = True
        logger.debug("MOCK: Device closed")

    def fileno(self):
        """
        Return file descriptor (mock).

        Returns:
            int: Mock file descriptor (-1)
        """
        return self._fd

    # Testing/Development Helper Methods

    def inject_event(self, type: int, code: int, value: int):
        """
        Inject a mock event for testing.

        This method allows injecting keyboard events programmatically
        for testing purposes. Useful for:
        - Unit testing keyboard handling logic
        - Simulating hotkey presses
        - Testing state machine transitions

        Args:
            type: Event type (e.g., ecodes.EV_KEY)
            code: Key code (e.g., ecodes.KEY_A)
            value: Event value (1=press, 0=release, 2=repeat)

        Example:
            >>> device = MockInputDevice("/dev/input/event0")
            >>> device.inject_event(ecodes.EV_KEY, ecodes.KEY_A, 1)  # Press 'A'
            >>> device.inject_event(ecodes.EV_KEY, ecodes.KEY_A, 0)  # Release 'A'
        """
        now = time.time()
        sec = int(now)
        usec = int((now - sec) * 1000000)

        event = MockInputEvent(sec, usec, type, code, value)
        self._event_queue.put_nowait(event)
        logger.debug(f"MOCK: Injected event: type={type}, code={code}, value={value}")

    def inject_key_press(self, key_code: int):
        """
        Inject a key press event.

        Args:
            key_code: Key code (e.g., ecodes.KEY_A)
        """
        self.inject_event(ecodes.EV_KEY, key_code, 1)

    def inject_key_release(self, key_code: int):
        """
        Inject a key release event.

        Args:
            key_code: Key code (e.g., ecodes.KEY_A)
        """
        self.inject_event(ecodes.EV_KEY, key_code, 0)

    def inject_key_sequence(self, key_codes: list, delay: float = 0.1):
        """
        Inject a sequence of key presses and releases.

        Args:
            key_codes: List of key codes to press in sequence
            delay: Delay between key press/release (seconds)
        """
        for key_code in key_codes:
            self.inject_key_press(key_code)
            time.sleep(delay)
            self.inject_key_release(key_code)


def find_keyboard_event_mock() -> str:
    """
    Mock keyboard device discovery.

    On Linux, this would scan /dev/input/* for keyboard devices.
    On macOS, we just return a mock path.

    Returns:
        str: Mock device path
    """
    logger.warning("🔶 MOCK: Keyboard device discovery")
    logger.info("  → Returning mock keyboard device path")
    logger.info("  → No actual keyboard will be detected or captured")
    logger.info("  → For real keyboard capture, use Linux/Raspberry Pi")

    return "/dev/input/event-mock-keyboard"


async def find_keyboard_with_retry_mock(
    max_retries: int = 10,
    initial_delay: float = 1.0,
    max_delay: float = 30.0
) -> Optional[str]:
    """
    Mock keyboard discovery with retry logic.

    Args:
        max_retries: Maximum retry attempts (-1 for infinite)
        initial_delay: Initial retry delay (seconds)
        max_delay: Maximum retry delay (seconds)

    Returns:
        str: Mock device path (always succeeds)
    """
    logger.warning("🔶 MOCK: Keyboard device discovery with retry")
    logger.info("  → Mock mode always returns device immediately")

    # Simulate brief delay for realism
    await asyncio.sleep(0.1)

    return find_keyboard_event_mock()


def find_keyboard_event_safe() -> str:
    """
    Safe keyboard device discovery (never raises exceptions).

    Returns:
        str: Mock device path
    """
    try:
        return find_keyboard_event_mock()
    except Exception as e:
        logger.error(f"MOCK: Error in find_keyboard_event_safe: {e}")
        return "/dev/input/event-mock-fallback"
