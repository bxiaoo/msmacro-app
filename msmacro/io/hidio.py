import os
import time
import logging
from typing import Iterable

log = logging.getLogger(__name__)

def _build_report(modmask: int, keys: Iterable[int]) -> bytes:
    arr = [0] * 8
    arr[0] = modmask & 0xFF
    arr[1] = 0
    ks = list(keys)[:6] + [0] * (6 - min(6, len(list(keys))))
    arr[2:8] = ks
    return bytes(arr)

class HIDWriter:
    def __init__(self, path: str = "/dev/hidg0"):
        # Validate that this looks like a HID gadget device
        if not path.startswith("/dev/hidg"):
            raise ValueError(f"Path '{path}' does not appear to be a HID gadget device")
        if not os.path.exists(path):
            raise FileNotFoundError(f"HID gadget device '{path}' not found")
        self.path = path
        self.fd = self._open_device()

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

    def _write_with_retry(self, data: bytes):
        """Write data with automatic device reopen on broken pipe."""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                os.write(self.fd, data)
                return
            except BrokenPipeError as e:
                if attempt < max_retries - 1:
                    log.warning(f"BrokenPipeError on HID write (attempt {attempt+1}/{max_retries}): {e}, reopening device")
                    self._reopen_device()
                else:
                    log.error(f"BrokenPipeError persists after {max_retries} retries")
                    raise
            except OSError as e:
                # For other OS errors, don't retry
                log.error(f"OSError on HID write: {e}")
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
