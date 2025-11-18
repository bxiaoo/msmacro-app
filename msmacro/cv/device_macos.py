"""
macOS-specific video capture device detection using OpenCV.

This module provides macOS-compatible device enumeration without relying
on v4l2-ctl or /sys filesystem access.
"""

import logging
import cv2
from typing import List, Optional
from .device import CaptureDevice

logger = logging.getLogger(__name__)


def list_video_devices_macos() -> List[CaptureDevice]:
    """
    Enumerate all video devices available on macOS using OpenCV.

    Since macOS doesn't expose /dev/video* devices like Linux,
    we probe device indices 0-9 using OpenCV's AVFoundation backend.

    Returns:
        List of CaptureDevice objects with actual capture capability
    """
    devices = []
    max_devices_to_check = 10  # Most systems have < 10 cameras

    logger.debug("Scanning for video capture devices on macOS...")

    for device_index in range(max_devices_to_check):
        # Try to open device with AVFoundation backend (macOS native)
        cap = cv2.VideoCapture(device_index, cv2.CAP_AVFOUNDATION)

        if cap.isOpened():
            # Device is available - get its properties
            device_name = _get_device_name_macos(cap, device_index)

            # Create synthetic device path for compatibility
            device_path = f"avfoundation://{device_index}"

            # On macOS, assume USB capture cards have "capture" or "hdmi" in name
            # Built-in cameras typically have "FaceTime" or "iSight" in name
            is_usb = _is_usb_device_macos(device_name)

            device = CaptureDevice(
                device_path=device_path,
                device_index=device_index,
                name=device_name,
                is_usb=is_usb
            )

            devices.append(device)
            logger.debug(f"Found video device: {device}")

            # Release the capture device
            cap.release()
        else:
            # No more devices available at this index
            # However, there might be gaps, so we continue scanning
            logger.debug(f"No device at index {device_index}")

    logger.info(f"Found {len(devices)} video device(s) on macOS")
    return devices


def _get_device_name_macos(cap: cv2.VideoCapture, device_index: int) -> str:
    """
    Get the human-readable name of a video device on macOS.

    Unfortunately, OpenCV doesn't expose device names directly on macOS.
    We use heuristics to identify common device types.

    Args:
        cap: Opened VideoCapture object
        device_index: Device index (0, 1, 2...)

    Returns:
        Device name or generic name if unable to determine
    """
    # Try to get backend name (not very useful on macOS)
    backend = cap.getBackendName()

    # OpenCV doesn't expose device name on macOS via standard APIs
    # We can try to infer from the device index:
    # - Index 0 is typically built-in camera
    # - Higher indices are usually external devices

    if device_index == 0:
        # Try to detect if this is a built-in camera or capture card
        # Get resolution to make a guess
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # HDMI capture cards typically support 1080p or 720p
        # Built-in cameras often default to 640x480 or 1280x720
        if width >= 1280 and height >= 720:
            return f"Video Capture Device {device_index} ({width}x{height})"
        else:
            return f"FaceTime HD Camera (Built-in)"

    # For external devices, use generic name with resolution
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return f"External Capture Device {device_index} ({width}x{height})"
    except Exception:
        return f"Video Device {device_index}"


def _is_usb_device_macos(device_name: str) -> bool:
    """
    Heuristic to determine if a device is USB on macOS.

    Args:
        device_name: Device name string

    Returns:
        True if device is likely USB (external), False if built-in
    """
    name_lower = device_name.lower()

    # Built-in cameras typically have these keywords
    builtin_keywords = ["facetime", "isight", "built-in"]
    if any(keyword in name_lower for keyword in builtin_keywords):
        return False

    # External/USB devices typically have these keywords
    usb_keywords = ["capture", "hdmi", "external", "usb", "elgato", "avermedia", "magewell"]
    if any(keyword in name_lower for keyword in usb_keywords):
        return True

    # For device indices > 0, assume they are external/USB
    # (index 0 is usually built-in camera)
    if "device 0" not in name_lower:
        return True

    # Default: assume USB (safer to include than exclude)
    return True


def validate_device_access_macos(device: CaptureDevice) -> bool:
    """
    Validate that a capture device is accessible on macOS.

    Args:
        device: CaptureDevice to validate

    Returns:
        True if device is accessible, False otherwise
    """
    try:
        # Try to open the device
        cap = cv2.VideoCapture(device.device_index, cv2.CAP_AVFOUNDATION)

        if cap.isOpened():
            # Try to read a test frame
            ret, frame = cap.read()
            cap.release()

            if ret and frame is not None:
                logger.debug(f"Device {device.device_index} is accessible")
                return True
            else:
                logger.warning(f"Device {device.device_index} opened but cannot read frames")
                return False
        else:
            logger.warning(f"Cannot open device {device.device_index}")
            return False

    except Exception as e:
        logger.error(f"Error validating device {device.device_index}: {e}")
        return False
