"""
HDMI capture device detection and validation.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict
import asyncio

logger = logging.getLogger(__name__)


class CaptureDevice:
    """Represents a video capture device."""

    def __init__(self, device_path: str, device_index: int, name: str = ""):
        self.device_path = device_path
        self.device_index = device_index
        self.name = name or f"Video Device {device_index}"

    def __repr__(self):
        return f"CaptureDevice(path={self.device_path}, index={self.device_index}, name={self.name})"


def list_video_devices() -> List[CaptureDevice]:
    """
    Enumerate all video devices available on the system.

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

                device = CaptureDevice(
                    device_path=device_path_str,
                    device_index=device_index,
                    name=_get_device_name(device_path_str)
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
    Find the first available HDMI capture device.

    Prioritizes devices with "capture" or "HDMI" in their name,
    falls back to the first available video device if none found.

    Returns:
        CaptureDevice or None if no devices found
    """
    devices = list_video_devices()

    if not devices:
        logger.warning("No video devices found on the system")
        return None

    # Prioritize HDMI/capture devices
    for device in devices:
        name_lower = device.name.lower()
        if "hdmi" in name_lower or "capture" in name_lower:
            logger.info(f"Found HDMI capture device: {device}")
            return device

    # Fall back to first device
    logger.info(f"No HDMI capture device found, using first available: {devices[0]}")
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
