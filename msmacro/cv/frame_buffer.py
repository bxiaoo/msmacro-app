"""
Thread-safe frame buffer for storing the latest captured frame in memory.
"""

import threading
import time
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class FrameMetadata:
    """Metadata for a captured frame."""
    timestamp: float
    width: int
    height: int
    size_bytes: int


class FrameBuffer:
    """
    Thread-safe in-memory storage for the latest captured frame.

    Stores frames as JPEG-encoded bytes to minimize memory usage and
    allow direct serving via HTTP without re-encoding.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._frame_data: Optional[bytes] = None
        self._metadata: Optional[FrameMetadata] = None

    def update(self, jpeg_data: bytes, width: int, height: int, timestamp: Optional[float] = None) -> None:
        """
        Update the buffer with a new JPEG-encoded frame.

        Args:
            jpeg_data: JPEG-encoded frame data
            width: Frame width in pixels
            height: Frame height in pixels
            timestamp: Optional precomputed timestamp to associate with the frame
        """
        metadata = FrameMetadata(
            timestamp=timestamp if timestamp is not None else time.time(),
            width=width,
            height=height,
            size_bytes=len(jpeg_data)
        )

        with self._lock:
            self._frame_data = jpeg_data
            self._metadata = metadata

    def get_latest(self) -> Optional[Tuple[bytes, FrameMetadata]]:
        """
        Retrieve the latest frame and its metadata.

        Returns:
            Tuple of (jpeg_data, metadata) or None if no frame available
        """
        with self._lock:
            if self._frame_data is None or self._metadata is None:
                return None
            # Return actual copies to prevent memory leaks from web request references
            # Critical on Raspberry Pi with limited RAM
            return (bytes(self._frame_data), self._metadata)

    def clear(self) -> None:
        """Clear the frame buffer."""
        with self._lock:
            self._frame_data = None
            self._metadata = None

    def has_frame(self) -> bool:
        """Check if a frame is available."""
        with self._lock:
            return self._frame_data is not None
