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
    # Region detection info (optional)
    region_detected: bool = False
    region_x: int = 0
    region_y: int = 0
    region_width: int = 0
    region_height: int = 0
    region_confidence: float = 0.0
    region_white_ratio: float = 0.0


class FrameBuffer:
    """
    Thread-safe in-memory storage for the latest captured frame.

    Stores frames as JPEG-encoded bytes to minimize memory usage and
    allow direct serving via HTTP without re-encoding.

    Also stores raw minimap crop (before JPEG compression) for truly
    lossless calibration - small memory footprint (~88KB for 340x86).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._frame_data: Optional[bytes] = None
        self._metadata: Optional[FrameMetadata] = None
        # Raw minimap crop (BGR numpy array) for lossless calibration
        # Only ~88KB for typical 340x86 minimap, acceptable memory cost
        self._raw_minimap_crop: Optional['numpy.ndarray'] = None

    def update(
        self,
        jpeg_data: bytes,
        width: int,
        height: int,
        timestamp: Optional[float] = None,
        region_detected: bool = False,
        region_x: int = 0,
        region_y: int = 0,
        region_width: int = 0,
        region_height: int = 0,
        region_confidence: float = 0.0,
        region_white_ratio: float = 0.0,
        raw_minimap_crop: Optional['numpy.ndarray'] = None
    ) -> None:
        """
        Update the buffer with a new JPEG-encoded frame.

        Args:
            jpeg_data: JPEG-encoded frame data
            width: Frame width in pixels
            height: Frame height in pixels
            timestamp: Optional precomputed timestamp to associate with the frame
            region_detected: Whether white frame region was detected
            region_x, region_y: Region top-left coordinates
            region_width, region_height: Region dimensions
            region_confidence: Detection confidence (0.0-1.0)
            region_white_ratio: Ratio of white pixels in region
            raw_minimap_crop: Optional raw BGR minimap crop (before JPEG compression)
        """
        metadata = FrameMetadata(
            timestamp=timestamp if timestamp is not None else time.time(),
            width=width,
            height=height,
            size_bytes=len(jpeg_data),
            region_detected=region_detected,
            region_x=region_x,
            region_y=region_y,
            region_width=region_width,
            region_height=region_height,
            region_confidence=region_confidence,
            region_white_ratio=region_white_ratio
        )

        with self._lock:
            self._frame_data = jpeg_data
            self._metadata = metadata
            # Store raw minimap crop copy to prevent caller modification
            self._raw_minimap_crop = raw_minimap_crop.copy() if raw_minimap_crop is not None else None

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

    def get_raw_minimap(self) -> Optional[Tuple['numpy.ndarray', FrameMetadata]]:
        """
        Retrieve the latest raw minimap crop (before JPEG compression).

        Returns:
            Tuple of (raw_bgr_crop, metadata) or None if not available
        """
        with self._lock:
            if self._raw_minimap_crop is None or self._metadata is None:
                return None
            # Return copy to prevent caller modification
            return (self._raw_minimap_crop.copy(), self._metadata)

    def clear(self) -> None:
        """Clear the frame buffer."""
        with self._lock:
            self._frame_data = None
            self._metadata = None
            self._raw_minimap_crop = None

    def has_frame(self) -> bool:
        """Check if a frame is available."""
        with self._lock:
            return self._frame_data is not None
