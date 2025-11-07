"""
Computer Vision module for HDMI capture card support.

This module provides:
- HDMI capture device detection and hot-plug support
- Real-time frame capture using OpenCV
- In-memory JPEG frame buffering
- Region-based analysis (white/black detection, color detection)
- Preparation for future CV automation (OCR, template matching, etc.)
"""

from .capture import CVCapture, CVCaptureError, get_capture_instance
from .device import CaptureDevice, find_capture_device, list_video_devices
from .frame_buffer import FrameBuffer, FrameMetadata
from .region_analysis import (
    Region,
    extract_region,
    is_white_region,
    is_black_region,
    detect_color_in_region,
    get_region_average_color,
    visualize_region,
    REGIONS,
)

__all__ = [
    # Main capture interface
    "CVCapture",
    "CVCaptureError",
    "get_capture_instance",

    # Device management
    "CaptureDevice",
    "find_capture_device",
    "list_video_devices",

    # Frame buffer
    "FrameBuffer",
    "FrameMetadata",

    # Region analysis
    "Region",
    "extract_region",
    "is_white_region",
    "is_black_region",
    "detect_color_in_region",
    "get_region_average_color",
    "visualize_region",
    "REGIONS",
]
