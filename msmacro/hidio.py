import os
from typing import Iterable

def _build_report(modmask: int, keys: Iterable[int]) -> bytes:
    arr = [0] * 8
    arr[0] = modmask & 0xFF
    arr[1] = 0
    ks = list(keys)[:6] + [0] * (6 - min(6, len(list(keys))))
    arr[2:8] = ks
    return bytes(arr)

class HIDWriter:
    def __init__(self, path: str = "/dev/hidg0"):
        self.fd = os.open(path, os.O_WRONLY | os.O_CLOEXEC)
    def send(self, modmask: int, keys: set[int]):
        os.write(self.fd, _build_report(modmask, sorted(keys)))
    def all_up(self):
        os.write(self.fd, b"\x00" * 8)
    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass
