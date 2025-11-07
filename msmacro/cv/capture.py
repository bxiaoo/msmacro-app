"""
Main capture manager for HDMI video capture cards using OpenCV.
"""

import asyncio
import json
import logging
import threading
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import cv2
import numpy as np

from .device import CaptureDevice, find_capture_device_with_retry, list_video_devices, validate_device_access
from .frame_buffer import FrameBuffer, FrameMetadata
from .region_analysis import detect_and_crop_white_frame, Region

logger = logging.getLogger(__name__)


class CVCaptureError(Exception):
    """Raised when capture operations fail."""
    pass


class CVCapture:
    """
    Main capture manager for HDMI video capture cards.

    This class manages:
    - Device discovery and hot-plug detection
    - Continuous frame capture in a background thread
    - JPEG encoding and in-memory storage
    - Device reconnection on failures
    """

    def __init__(self, jpeg_quality: int = 70):
        """
        Initialize the capture manager.

        Args:
            jpeg_quality: JPEG compression quality (0-100, higher is better)
                        Default 70 balances quality and memory usage on Raspberry Pi
        """
        self.jpeg_quality = jpeg_quality
        self.frame_buffer = FrameBuffer()
        self._preferred_device_cfg = os.environ.get("MSMACRO_CV_DEVICE", "").strip()
        frame_path_env = os.environ.get("MSMACRO_CV_FRAME_PATH", "/dev/shm/msmacro_cv_frame.jpg").strip()
        self._shared_frame_path = Path(frame_path_env) if frame_path_env else None
        meta_path_env = os.environ.get("MSMACRO_CV_META_PATH", "").strip()
        if meta_path_env:
            self._shared_meta_path = Path(meta_path_env)
        elif self._shared_frame_path is not None:
            self._shared_meta_path = self._shared_frame_path.with_suffix(".json")
        else:
            self._shared_meta_path = None

        # White frame detection configuration
        self._detect_white_frame = os.environ.get("MSMACRO_CV_DETECT_WHITE_FRAME", "false").lower() in ("true", "1", "yes")
        self._white_frame_threshold = int(os.environ.get("MSMACRO_CV_WHITE_THRESHOLD", "240"))
        self._white_frame_min_pixels = int(os.environ.get("MSMACRO_CV_WHITE_MIN_PIXELS", "100"))

        # Parse scan region from env (format: "x,y,width,height" or empty for default)
        scan_region_str = os.environ.get("MSMACRO_CV_WHITE_SCAN_REGION", "").strip()
        if scan_region_str:
            try:
                parts = [int(p.strip()) for p in scan_region_str.split(",")]
                if len(parts) == 4:
                    self._white_frame_scan_region = Region(x=parts[0], y=parts[1], width=parts[2], height=parts[3])
                else:
                    logger.warning(f"Invalid MSMACRO_CV_WHITE_SCAN_REGION format: {scan_region_str}, using default")
                    self._white_frame_scan_region = None
            except ValueError as e:
                logger.warning(f"Failed to parse MSMACRO_CV_WHITE_SCAN_REGION: {e}, using default")
                self._white_frame_scan_region = None
        else:
            self._white_frame_scan_region = None  # Use default from detect_and_crop_white_frame

        # Capture state
        self._capture: Optional[cv2.VideoCapture] = None
        self._device: Optional[CaptureDevice] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        # Device monitoring
        self._monitor_task: Optional[asyncio.Task] = None
        self._device_connected = False

        # Statistics
        self._frames_captured = 0
        self._frames_failed = 0
        self._last_frame_time = 0.0
        self._error_lock = threading.Lock()
        self._last_error: Optional[Dict[str, Any]] = None

    def get_status(self) -> Dict[str, Any]:
        """
        Get current capture status.

        Returns:
            Dictionary with status information
        """
        frame_result = self.frame_buffer.get_latest()
        has_frame = frame_result is not None

        status = {
            "connected": self._device_connected,
            "capturing": self._running,
            "has_frame": has_frame,
            "frames_captured": self._frames_captured,
            "frames_failed": self._frames_failed,
            "last_error": self._get_last_error(),
        }

        if self._device:
            status["device"] = {
                "path": self._device.device_path,
                "index": self._device.device_index,
                "name": self._device.name,
            }

        if has_frame:
            _, metadata = frame_result
            status["frame"] = {
                "width": metadata.width,
                "height": metadata.height,
                "timestamp": metadata.timestamp,
                "age_seconds": time.time() - metadata.timestamp,
                "size_bytes": metadata.size_bytes,
            }

        if self._capture and self._device_connected:
            # Get capture properties
            try:
                status["capture"] = {
                    "fps": self._capture.get(cv2.CAP_PROP_FPS),
                    "width": int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "height": int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                }
            except Exception as e:
                logger.debug(f"Could not get capture properties: {e}")

        return status

    async def start(self) -> None:
        """
        Start the capture system.

        This will:
        1. Find a capture device
        2. Initialize OpenCV VideoCapture
        3. Start the capture thread
        4. Start the monitoring task
        """
        if self._running:
            logger.warning("Capture already running")
            return

        logger.info("Starting CV capture system...")
        logger.debug(f"Current state: connected={self._device_connected}, has_frame={self.frame_buffer.has_frame()}")
        self._clear_last_error()

        # Wait for a device to appear
        logger.debug("Searching for capture devices...")
        preferred_device = await find_capture_device_with_retry(max_retries=3)
        if not preferred_device:
            self._set_last_error("No capture device found after retries")
            raise CVCaptureError("No capture device found after retries")

        logger.info(f"Preferred device selected: {preferred_device}")

        # Build candidate list (preferred device first, then the rest ordered by priority)
        all_devices = list_video_devices()
        if not all_devices:
            self._set_last_error("No capture devices detected on system")
            raise CVCaptureError("No capture devices detected on system")

        logger.debug(f"Building candidate list from {len(all_devices)} available devices")

        def _priority(device: CaptureDevice) -> tuple:
            name_lower = (device.name or "").lower()
            keyword = 0 if ("hdmi" in name_lower or "capture" in name_lower) else 1
            return (keyword, device.device_index)

        ordered_devices = sorted(all_devices, key=_priority)

        def _env_matches(device: CaptureDevice) -> bool:
            if not self._preferred_device_cfg:
                return False
            pref = self._preferred_device_cfg
            if pref.isdigit():
                return device.device_index == int(pref)
            if pref.startswith("/dev/"):
                return device.device_path == pref
            return pref.lower() in (device.name or "").lower()

        candidates: list[CaptureDevice] = []
        seen = set()

        for dev in ordered_devices:
            if _env_matches(dev) and dev.device_path not in seen:
                candidates.append(dev)
                seen.add(dev.device_path)

        if preferred_device.device_path not in seen:
            candidates.append(preferred_device)
            seen.add(preferred_device.device_path)

        for dev in ordered_devices:
            if dev.device_path not in seen:
                candidates.append(dev)
                seen.add(dev.device_path)

        init_error: Optional[str] = None
        logger.info(f"Trying {len(candidates)} candidate device(s) in priority order:")
        for idx, candidate in enumerate(candidates, 1):
            logger.info(f"  Attempt {idx}/{len(candidates)}: {candidate}")

            if not validate_device_access(candidate):
                init_error = f"Cannot access device: {candidate.device_path}"
                logger.warning(f"    ✗ {init_error}")
                continue

            self._device = candidate
            try:
                await self._init_capture()
                logger.info(f"    ✓ Successfully initialized {candidate.device_path}")
                break
            except CVCaptureError as exc:
                init_error = str(exc)
                logger.warning(f"    ✗ Failed to initialize: {exc}")
                self._release_capture()
                self._device = None
                continue
        else:
            self._set_last_error(init_error or "Failed to initialize capture device")
            logger.error("All device candidates failed!")
            raise CVCaptureError(init_error or "Failed to initialize capture device")

        # Start capture thread
        self._stop_event.clear()
        self._running = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True, name="CV-Capture")
        self._capture_thread.start()
        logger.debug("Capture thread started")

        # Start monitoring task
        self._monitor_task = asyncio.create_task(self._monitor_device())
        logger.debug("Monitor task started")

        logger.info(f"CV capture started successfully with device: {self._device.device_path}")

    async def stop(self) -> None:
        """Stop the capture system."""
        if not self._running:
            return

        logger.info("Stopping CV capture system...")

        # Stop monitoring task
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        # Stop capture thread
        self._stop_event.set()
        if self._capture_thread:
            self._capture_thread.join(timeout=5.0)
            self._capture_thread = None

        # Release capture
        self._release_capture()

        self._running = False
        logger.info("CV capture stopped")

    async def _init_capture(self) -> None:
        """Initialize OpenCV VideoCapture."""
        if not self._device:
            raise CVCaptureError("No device available")

        logger.info(f"Initializing capture on {self._device.device_path}")

        # Try opening by explicit device path first (more reliable on multi-node capture cards)
        open_attempts = [
            (self._device.device_path, cv2.CAP_V4L2),
            (self._device.device_index, cv2.CAP_V4L2),
            (self._device.device_index, cv2.CAP_ANY),
        ]

        self._capture = None
        last_error = None
        cap = None  # Initialize to avoid warning

        for target, api_pref in open_attempts:
            try:
                logger.debug("Attempting to open capture device %r with API preference %s", target, api_pref)
                cap = cv2.VideoCapture(target, api_pref)
                if cap is not None and cap.isOpened():
                    # Device opened, now set format parameters immediately
                    # USB capture cards often need explicit resolution/format set before first read
                    logger.debug("Device opened, configuring format parameters...")

                    # Set resolution - use 1280x720 to reduce memory usage on Raspberry Pi
                    # Original 1920x1080 uses 6MB per frame, 1280x720 uses only 2.7MB (55% less)
                    # Quality is still excellent for web preview, and saves critical RAM
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

                    # Try YUYV format first (most USB capture cards support this)
                    fourcc_yuyv = cv2.VideoWriter_fourcc(*'YUYV')
                    cap.set(cv2.CAP_PROP_FOURCC, fourcc_yuyv)

                    # Try to read a test frame to verify the configuration works
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None:
                        logger.debug("Successfully read test frame with YUYV format")
                        self._capture = cap
                        break
                    else:
                        # YUYV didn't work, try MJPEG
                        logger.debug("YUYV format failed, trying MJPEG...")
                        fourcc_mjpg = cv2.VideoWriter_fourcc(*'MJPG')
                        cap.set(cv2.CAP_PROP_FOURCC, fourcc_mjpg)

                        ret, test_frame = cap.read()
                        if ret and test_frame is not None:
                            logger.debug("Successfully read test frame with MJPEG format")
                            self._capture = cap
                            break
                        else:
                            # Neither worked, try with no format preference (device default)
                            logger.debug("MJPEG also failed, trying device default format...")
                            cap.set(cv2.CAP_PROP_FOURCC, 0)  # Reset to default

                            ret, test_frame = cap.read()
                            if ret and test_frame is not None:
                                logger.debug("Successfully read test frame with device default format")
                                self._capture = cap
                                break

                    # If we get here, this open attempt failed
                    last_error = f"Opened device but could not read frames (api={api_pref})"
                    cap.release()

                else:
                    if cap is not None:
                        last_error = f"OpenCV could not open target {target} (api={api_pref})"
                        cap.release()
            except Exception as exc:
                last_error = str(exc)
                logger.debug(f"Exception during open attempt: {exc}")
                if cap is not None:
                    try:
                        cap.release()
                    except:
                        pass

        if not self._capture or not self._capture.isOpened():
            self._capture = None
            detail = str(last_error) if last_error else "unknown error"
            msg = f"Failed to open capture device: {self._device.device_path} ({detail})"
            self._set_last_error(msg)
            raise CVCaptureError(msg)

        self._device_connected = True

        # Log capture properties
        width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self._capture.get(cv2.CAP_PROP_FPS)
        fourcc = int(self._capture.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])

        logger.info(f"Capture initialized: {width}x{height} @ {fps} FPS, format: {fourcc_str}")
        self._clear_last_error()

    def _release_capture(self) -> None:
        """Release the OpenCV VideoCapture."""
        if self._capture:
            self._capture.release()
            self._capture = None
        self._device_connected = False

    def _capture_loop(self) -> None:
        """
        Main capture loop running in a background thread.

        Continuously captures frames, encodes them as JPEG, and stores
        them in the frame buffer.
        """
        logger.info("Capture loop started")

        while not self._stop_event.is_set():
            try:
                if not self._capture or not self._device_connected:
                    time.sleep(0.1)
                    continue

                # Capture frame
                ret, frame = self._capture.read()

                if not ret or frame is None:
                    self._frames_failed += 1
                    logger.warning("Failed to read frame")
                    self._device_connected = False
                    self._set_last_error("Failed to read frame from capture device")
                    time.sleep(0.5)
                    continue

                # White frame detection and cropping (if enabled)
                if self._detect_white_frame:
                    cropped_frame = detect_and_crop_white_frame(
                        frame,
                        scan_region=self._white_frame_scan_region,
                        threshold=self._white_frame_threshold,
                        min_white_pixels=self._white_frame_min_pixels
                    )

                    # Delete original frame to free memory
                    del frame

                    if cropped_frame is not None:
                        # Use cropped frame
                        frame = cropped_frame
                    else:
                        # No white frame detected - create blank error image
                        # Create a small gray image with text indicating no frame detected
                        error_img = self._create_no_frame_error_image()
                        frame = error_img

                # Get frame dimensions before encoding
                height, width = frame.shape[:2]

                # Encode as JPEG
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
                ret, jpeg_data = cv2.imencode('.jpg', frame, encode_param)

                # Explicitly delete frame to free memory immediately
                # Each frame is ~6MB for 1920x1080, critical on Raspberry Pi
                del frame

                if not ret or jpeg_data is None:
                    self._frames_failed += 1
                    logger.warning("Failed to encode frame as JPEG")
                    self._set_last_error("Failed to encode frame as JPEG")
                    continue

                # Convert to bytes
                jpeg_bytes = jpeg_data.tobytes()

                # Explicitly delete jpeg_data to free memory immediately
                # JPEG numpy array is ~1MB, needs immediate cleanup on Pi
                del jpeg_data

                timestamp = time.time()

                # Store in buffer
                self.frame_buffer.update(jpeg_bytes, width, height, timestamp=timestamp)

                # Write to shared filesystem location for cross-process access
                self._write_shared_frame(jpeg_bytes, width, height, timestamp)

                self._frames_captured += 1
                self._last_frame_time = timestamp
                self._clear_last_error()

                # Capture at 2 FPS (web UI polls every 2 seconds, so 2 FPS is plenty)
                # Original 30 FPS was wasting 240MB/sec on Raspberry Pi!
                time.sleep(0.5)  # 2 FPS capture rate

            except Exception as e:
                self._frames_failed += 1
                logger.error(f"Error in capture loop: {e}", exc_info=True)
                self._set_last_error("Unexpected error in capture loop", exception=e)
                time.sleep(0.5)

        logger.info("Capture loop stopped")

    async def _monitor_device(self) -> None:
        """
        Monitor device connection status and attempt reconnection.

        Runs as a background asyncio task.
        """
        logger.info("Device monitoring started")

        while True:
            try:
                await asyncio.sleep(5.0)  # Check every 5 seconds

                # If device is disconnected, try to reconnect
                if not self._device_connected and self._running:
                    logger.info("Device disconnected, attempting reconnection...")

                    # Try to find device again
                    device = await find_capture_device_with_retry(max_retries=1, initial_delay=1.0)

                    if device and validate_device_access(device):
                        self._device = device
                        try:
                            await self._init_capture()
                            logger.info("Device reconnected successfully")
                        except CVCaptureError as e:
                            logger.warning(f"Reconnection failed: {e}")

            except asyncio.CancelledError:
                logger.info("Device monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Error in device monitoring: {e}", exc_info=True)

    def get_latest_frame(self) -> Optional[Tuple[bytes, FrameMetadata]]:
        """
        Get the latest captured frame as JPEG data.

        Returns:
            Tuple of (JPEG-encoded frame bytes, FrameMetadata) or None if no frame available
        """
        return self.frame_buffer.get_latest()

    def _write_shared_frame(self, jpeg_bytes: bytes, width: int, height: int, timestamp: float) -> None:
        """Persist latest frame to shared memory for other processes."""
        if not self._shared_frame_path:
            return

        path = self._shared_frame_path
        meta_path = self._shared_meta_path
        try:
            if path.parent != path and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)

            tmp_path = path.with_name(path.name + ".tmp")
            with open(tmp_path, "wb") as fh:
                fh.write(jpeg_bytes)
            os.replace(tmp_path, path)

            if meta_path:
                if meta_path.parent != meta_path and not meta_path.parent.exists():
                    meta_path.parent.mkdir(parents=True, exist_ok=True)

                metadata = {
                    "width": width,
                    "height": height,
                    "timestamp": timestamp,
                    "size_bytes": len(jpeg_bytes),
                }
                meta_tmp = meta_path.with_name(meta_path.name + ".tmp")
                with open(meta_tmp, "w", encoding="utf-8") as fh:
                    json.dump(metadata, fh)
                os.replace(meta_tmp, meta_path)
        except Exception as exc:
            # Failure to persist shared frame shouldn't break capture loop; log at debug level
            logger.debug(f"Failed to write shared CV frame: {exc}", exc_info=True)

    def _set_last_error(self, message: str, *, exception: Optional[Exception] = None) -> None:
        """Record the most recent capture error for diagnostics."""
        error: Dict[str, Any] = {
            "message": message,
            "timestamp": time.time(),
        }
        if exception:
            error["detail"] = str(exception)
        with self._error_lock:
            self._last_error = error

    def _clear_last_error(self) -> None:
        with self._error_lock:
            self._last_error = None

    def _get_last_error(self) -> Optional[Dict[str, Any]]:
        with self._error_lock:
            return dict(self._last_error) if self._last_error else None

    def _create_no_frame_error_image(self) -> "np.ndarray":
        """
        Create a blank error image to display when no white frame is detected.

        Returns:
            numpy array containing a gray image with error text
        """
        # Create a 320x240 gray image
        img = np.full((240, 320, 3), 64, dtype=np.uint8)  # Dark gray background

        # Add text
        text = "No white frame detected"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        font_thickness = 2
        text_color = (200, 200, 200)  # Light gray

        # Get text size to center it
        text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
        text_x = (320 - text_size[0]) // 2
        text_y = (240 + text_size[1]) // 2

        # Draw text
        cv2.putText(img, text, (text_x, text_y), font, font_scale, text_color, font_thickness)

        return img


# Global capture instance
_capture_instance: Optional[CVCapture] = None


def get_capture_instance() -> CVCapture:
    """
    Get the global CVCapture instance.

    Returns:
        CVCapture instance (creates if not exists)
    """
    global _capture_instance
    if _capture_instance is None:
        _capture_instance = CVCapture()
    return _capture_instance
