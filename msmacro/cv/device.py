"""
HDMI capture device detection and validation.

Platform-aware implementation:
- Linux: Uses V4L2 (/dev/video*, v4l2-ctl)
- macOS: Uses OpenCV AVFoundation backend
"""

import logging
import subprocess
import platform
from pathlib import Path
from typing import Optional, List, Dict
import asyncio

logger = logging.getLogger(__name__)

# Detect platform at module load time
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


class CaptureDevice:
    """Represents a video capture device."""

    def __init__(self, device_path: str, device_index: int, name: str = "", is_usb: bool = False):
        self.device_path = device_path
        self.device_index = device_index
        self.name = name or f"Video Device {device_index}"
        self.is_usb = is_usb

    def __repr__(self):
        device_type = "USB" if self.is_usb else "Platform"
        return f"CaptureDevice(path={self.device_path}, index={self.device_index}, name={self.name}, type={device_type})"


def list_video_devices() -> List[CaptureDevice]:
    """
    Enumerate all video devices available on the system.

    Platform-aware implementation:
    - macOS: Uses OpenCV AVFoundation to probe devices
    - Linux: Uses V4L2 (/dev/video*) with format filtering

    Returns:
        List of CaptureDevice objects with actual capture capability
    """
    if IS_MACOS:
        # Use macOS-specific implementation
        from .device_macos import list_video_devices_macos
        return list_video_devices_macos()
    else:
        # Use Linux V4L2 implementation (original code)
        return _list_video_devices_linux()


def _list_video_devices_linux() -> List[CaptureDevice]:
    """
    Linux-specific device enumeration using V4L2.

    Filters out metadata-only devices that have no capture formats.

    Returns:
        List of CaptureDevice objects with actual capture capability
    """
    devices = []
    video_dir = Path("/dev")

    # Find all /dev/video* devices
    for video_path in sorted(video_dir.glob("video*")):
        if not video_path.is_char_device():
            continue

        # Extract device index from /dev/videoN
        device_name = video_path.name
        if device_name.startswith("video"):
            try:
                device_index = int(device_name[5:])
                device_path_str = str(video_path)

                # Filter out metadata-only devices (no capture formats)
                if not _check_device_has_capture_formats(device_path_str):
                    logger.debug(f"Skipping metadata-only device: {device_path_str}")
                    continue

                # Check if device is USB
                is_usb = _is_usb_device(device_index)

                device = CaptureDevice(
                    device_path=device_path_str,
                    device_index=device_index,
                    name=_get_device_name(device_path_str),
                    is_usb=is_usb
                )
                devices.append(device)
                logger.debug(f"Found capture-capable video device: {device}")
            except ValueError:
                continue

    return devices


def _get_device_name(device_path: str) -> str:
    """
    Get the human-readable name of a video device using v4l2-ctl.

    Args:
        device_path: Path to the video device (e.g., /dev/video0)

    Returns:
        Device name or empty string if unable to determine
    """
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", device_path, "--info"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            # Parse output for "Card type" line
            for line in result.stdout.splitlines():
                if line.strip().startswith("Card type"):
                    return line.split(":", 1)[1].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Could not get device name for {device_path}: {e}")

    return ""


def _is_usb_device(device_index: int) -> bool:
    """
    Check if a video device is connected via USB.

    Args:
        device_index: Video device index (e.g., 0 for /dev/video0)

    Returns:
        True if device is USB, False if platform/built-in device
    """
    try:
        # Check sysfs for device connection type
        uevent_path = Path(f"/sys/class/video4linux/video{device_index}/device/uevent")
        if uevent_path.exists():
            uevent_content = uevent_path.read_text()
            # USB devices have DEVTYPE=usb_interface or DRIVER=uvcvideo
            if "usb" in uevent_content.lower() or "uvc" in uevent_content.lower():
                return True

        # Alternative: check parent device path for "usb"
        device_path_link = Path(f"/sys/class/video4linux/video{device_index}/device")
        if device_path_link.exists():
            real_path = str(device_path_link.resolve())
            if "/usb" in real_path:
                return True

        return False
    except Exception as e:
        logger.debug(f"Could not determine USB status for video{device_index}: {e}")
        # If we can't determine, assume it might be USB (don't filter out)
        return False


def _check_device_has_capture_formats(device_path: str) -> bool:
    """
    Check if a video device has actual capture formats available.

    Many video devices are metadata-only (like /dev/video1 companion to /dev/video0)
    and have no formats available. This function filters those out.

    Args:
        device_path: Path to the video device (e.g., /dev/video0)

    Returns:
        True if device has at least one capture format, False otherwise
    """
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", device_path, "--list-formats-ext"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            # Check if there are any format entries in output
            # Format lines look like: "[0]: 'YUYV' (YUYV 4:2:2)"
            for line in result.stdout.splitlines():
                if line.strip().startswith("[") and ":" in line:
                    logger.debug(f"Device {device_path} has capture formats")
                    return True
        logger.debug(f"Device {device_path} has no capture formats (likely metadata-only)")
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Could not check formats for {device_path}: {e}")
        # If we can't check, assume it might be valid (don't filter out)
        return True


def find_capture_device() -> Optional[CaptureDevice]:
    """
    Find the best available capture device with smart prioritization.

    Priority order:
    1. USB devices with "HDMI" or "capture" in name
    2. Any USB devices
    3. Platform devices with "HDMI" or "capture" in name
    4. Lowest-numbered platform device (video0 > video19)

    Returns:
        CaptureDevice or None if no devices found
    """
    devices = list_video_devices()

    if not devices:
        logger.warning("No video devices found on the system")
        return None

    logger.info(f"Found {len(devices)} capture-capable device(s):")
    for dev in devices:
        logger.info(f"  - {dev}")

    # Priority 1: USB devices with HDMI/capture in name
    for device in devices:
        if device.is_usb:
            name_lower = device.name.lower()
            if "hdmi" in name_lower or "capture" in name_lower:
                logger.info(f"Selected USB HDMI/capture device (priority 1): {device}")
                return device

    # Priority 2: Any USB device
    usb_devices = [d for d in devices if d.is_usb]
    if usb_devices:
        # Sort by device index (prefer lower numbers)
        usb_devices.sort(key=lambda d: d.device_index)
        logger.info(f"Selected USB device (priority 2): {usb_devices[0]}")
        return usb_devices[0]

    # Priority 3: Platform devices with HDMI/capture in name
    for device in devices:
        name_lower = device.name.lower()
        if "hdmi" in name_lower or "capture" in name_lower:
            logger.info(f"Selected platform HDMI/capture device (priority 3): {device}")
            return device

    # Priority 4: Lowest-numbered device (video0 preferred over video19)
    devices.sort(key=lambda d: d.device_index)
    logger.info(f"Selected lowest-numbered device (priority 4): {devices[0]}")
    return devices[0]


async def find_capture_device_with_retry(
    max_retries: int = 10,
    initial_delay: float = 1.0,
    max_delay: float = 30.0
) -> Optional[CaptureDevice]:
    """
    Find a capture device with exponential backoff retry logic.

    This function is useful for handling hot-plug scenarios where
    the device may not be immediately available at startup.

    Args:
        max_retries: Maximum number of retry attempts (-1 for infinite)
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds

    Returns:
        CaptureDevice or None if max_retries exceeded
    """
    attempt = 0
    delay = initial_delay

    while max_retries < 0 or attempt < max_retries:
        device = find_capture_device()
        if device:
            return device

        attempt += 1
        if max_retries > 0 and attempt >= max_retries:
            break

        logger.info(f"No capture device found (attempt {attempt}), retrying in {delay:.1f}s...")
        await asyncio.sleep(delay)

        # Exponential backoff
        delay = min(delay * 2, max_delay)

    logger.error(f"Failed to find capture device after {attempt} attempts")
    return None


def validate_device_access(device: CaptureDevice) -> bool:
    """
    Validate that a capture device is accessible.

    Platform-aware implementation:
    - macOS: Uses OpenCV to test device access
    - Linux: Checks /dev/video* device file access

    Args:
        device: CaptureDevice to validate

    Returns:
        True if device is accessible, False otherwise
    """
    if IS_MACOS:
        # Use macOS-specific validation
        from .device_macos import validate_device_access_macos
        return validate_device_access_macos(device)
    else:
        # Use Linux V4L2 validation (original code)
        return _validate_device_access_linux(device)


def _validate_device_access_linux(device: CaptureDevice) -> bool:
    """
    Linux-specific device validation using file system access.

    Args:
        device: CaptureDevice to validate

    Returns:
        True if device is accessible, False otherwise
    """
    device_path = Path(device.device_path)

    if not device_path.exists():
        logger.warning(f"Device does not exist: {device.device_path}")
        return False

    if not device_path.is_char_device():
        logger.warning(f"Device is not a character device: {device.device_path}")
        return False

    # Check if we can read from the device
    try:
        with open(device.device_path, "rb") as f:
            # Just checking if we can open it
            pass
        return True
    except PermissionError:
        logger.error(f"Permission denied accessing device: {device.device_path}")
        return False
    except Exception as e:
        logger.error(f"Error accessing device {device.device_path}: {e}")
        return False
