import os
import time
import logging
import glob
from typing import Iterable

# Platform abstraction
from .platform_abstraction import IS_MACOS, IS_LINUX, HAS_HID_GADGET

log = logging.getLogger(__name__)

def _build_report(modmask: int, keys: Iterable[int]) -> bytes:
    arr = [0] * 8
    arr[0] = modmask & 0xFF
    arr[1] = 0
    ks = list(keys)[:6] + [0] * (6 - min(6, len(list(keys))))
    arr[2:8] = ks
    return bytes(arr)

class LinuxHIDWriter:
    def __init__(self, path: str = "/dev/hidg0"):
        # Validate that this looks like a HID gadget device
        if not path.startswith("/dev/hidg"):
            raise ValueError(f"Path '{path}' does not appear to be a HID gadget device")
        if not os.path.exists(path):
            raise FileNotFoundError(f"HID gadget device '{path}' not found")
        self.path = path
        self.fd = self._open_device()

        # Circuit breaker state to prevent rapid crash loops
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._last_usb_check = 0.0

    def _open_device(self) -> int:
        """Open the HID device with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CLOEXEC)
                log.debug(f"HID device {self.path} opened successfully (fd={fd})")
                return fd
            except OSError as e:
                if attempt < max_retries - 1:
                    delay = 0.1 * (2 ** attempt)  # exponential backoff
                    log.warning(f"Failed to open HID device (attempt {attempt+1}/{max_retries}): {e}, retrying in {delay}s")
                    time.sleep(delay)
                else:
                    raise
        raise RuntimeError("Failed to open HID device after retries")

    def _reopen_device(self):
        """Close and reopen the HID device."""
        try:
            os.close(self.fd)
        except OSError:
            pass
        log.info(f"Reopening HID device {self.path}")
        self.fd = self._open_device()

    def _is_gadget_configured(self) -> bool:
        """
        Check if USB gadget is configured (connected to host).

        Returns:
            True if gadget is in "configured" state (USB host connected)
            False if not configured or state cannot be determined
        """
        try:
            # Check all UDC (USB Device Controller) state files
            # When USB host is connected and enumerated, state should be "configured"
            for state_file in glob.glob("/sys/class/udc/*/state"):
                try:
                    with open(state_file, 'r') as f:
                        state = f.read().strip()
                        if state == "configured":
                            return True
                except (OSError, IOError):
                    continue

            # If we get here, no UDC is in configured state
            return False

        except Exception as e:
            # If we can't check state, assume not configured
            log.debug(f"Could not check USB gadget state: {e}")
            return False

    def _write_with_retry(self, data: bytes):
        """
        Write data with automatic device reopen on broken pipe.

        Implements:
        - Circuit breaker to prevent rapid crash loops
        - Exponential backoff retry logic
        - USB gadget state checking before retry
        - Graceful handling of USB disconnection
        """
        # Circuit breaker check: if we've had too many consecutive failures,
        # wait before attempting more writes
        current_time = time.time()
        if current_time < self._circuit_open_until:
            remaining = self._circuit_open_until - current_time
            log.debug(f"Circuit breaker open: suppressing HID write for {remaining:.1f}s more")
            # Don't raise exception - just skip the write gracefully
            return

        max_retries = 5  # Increased from 2 to allow more recovery attempts
        for attempt in range(max_retries):
            try:
                os.write(self.fd, data)

                # Success! Reset circuit breaker state
                if self._consecutive_failures > 0:
                    log.info(f"HID write succeeded after {self._consecutive_failures} previous failures - USB reconnected")
                    self._consecutive_failures = 0
                return

            except BrokenPipeError as e:
                self._consecutive_failures += 1

                if attempt < max_retries - 1:
                    # Calculate exponential backoff delay
                    delay = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s, 4s, 8s

                    log.warning(
                        f"BrokenPipeError on HID write (attempt {attempt+1}/{max_retries}): {e}"
                        f" - USB gadget connection lost, waiting {delay}s for reconnection"
                    )

                    # Wait for USB to potentially reconnect
                    time.sleep(delay)

                    # Check if USB gadget is actually configured before reopening
                    usb_configured = self._is_gadget_configured()
                    if not usb_configured:
                        log.warning(
                            f"USB gadget not in 'configured' state after {delay}s delay, "
                            f"host may still be disconnected"
                        )

                    # Reopen device file (this succeeds even if USB not connected)
                    self._reopen_device()

                else:
                    # Max retries exceeded
                    log.error(
                        f"BrokenPipeError persists after {max_retries} retries "
                        f"({self._consecutive_failures} consecutive failures total)"
                    )

                    # Activate circuit breaker if we've had too many consecutive failures
                    if self._consecutive_failures >= 3:
                        cooldown = 10.0  # 10 second cooldown
                        self._circuit_open_until = current_time + cooldown
                        log.error(
                            f"Circuit breaker activated: too many consecutive USB failures, "
                            f"suppressing HID writes for {cooldown}s"
                        )

                    raise

            except OSError as e:
                # For other OS errors (not BrokenPipe), don't retry
                log.error(f"OSError on HID write: {e}")
                self._consecutive_failures += 1
                raise

    def send(self, modmask: int, keys: set[int]):
        self._write_with_retry(_build_report(modmask, sorted(keys)))

    def all_up(self):
        self._write_with_retry(b"\x00" * 8)

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass


class AsyncHIDWriter:
    """
    Async wrapper around HIDWriter that provides stateful press/release API.

    This class is used by pathfinding code that needs to press and release
    individual keys asynchronously. It maintains the state of currently pressed
    keys and calls the underlying HIDWriter.send() method.
    """

    def __init__(self, hid_writer):
        """
        Initialize async HID writer.

        Args:
            hid_writer: LinuxHIDWriter or MockHIDWriter instance
        """
        self._writer = hid_writer
        self._pressed_keys = set()  # Set of currently pressed key usage IDs
        self._modmask = 0  # Current modifier mask

    async def press(self, usage_id: int):
        """
        Press a key (add to pressed keys set and send updated state).

        Args:
            usage_id: HID usage ID of the key to press (4-231)
        """
        # Add to pressed keys
        self._pressed_keys.add(usage_id)

        # Update modifier mask if this is a modifier key (224-231)
        if 224 <= usage_id <= 231:
            mod_bit = usage_id - 224
            self._modmask |= (1 << mod_bit)

        # Send updated state
        self._writer.send(self._modmask, self._pressed_keys)

    async def release(self, usage_id: int):
        """
        Release a key (remove from pressed keys set and send updated state).

        Args:
            usage_id: HID usage ID of the key to release
        """
        # Remove from pressed keys
        self._pressed_keys.discard(usage_id)

        # Update modifier mask if this is a modifier key
        if 224 <= usage_id <= 231:
            mod_bit = usage_id - 224
            self._modmask &= ~(1 << mod_bit)

        # Send updated state
        self._writer.send(self._modmask, self._pressed_keys)

    def all_up(self):
        """Release all keys (synchronous for compatibility)."""
        self._pressed_keys.clear()
        self._modmask = 0
        self._writer.all_up()

    async def async_all_up(self):
        """Release all keys (async version)."""
        self.all_up()


# Platform-aware HIDWriter export
# On macOS or when HID gadget is not available, use mock implementation
# On Linux with HID gadget, use real implementation
if IS_MACOS or not HAS_HID_GADGET:
    from .hidio_mock import MockHIDWriter
    HIDWriter = MockHIDWriter
    log.info("Using MockHIDWriter (macOS or HID gadget not available)")
else:
    HIDWriter = LinuxHIDWriter
    log.debug("Using LinuxHIDWriter (real HID gadget)")
