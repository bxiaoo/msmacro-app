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
# White frame detection removed - replaced by manual map configuration
# Only keep bgr_to_yuyv_bytes for potential future use
from .region_analysis import bgr_to_yuyv_bytes, Region

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

        # Map configuration manager for region-based detection
        from .map_config import get_manager
        self._map_config_manager = get_manager()
        self._active_map_config = None  # Will be loaded in start()
        self._config_lock = threading.Lock()

        # Minimap region is now user-defined via map configuration
        # No auto-detection - users manually configure minimap position/size

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
        
        # Object detection
        self._object_detector = None
        self._object_detection_enabled = False
        self._last_detection_result = None
        self._detection_lock = threading.Lock()

        # Immediate capture trigger (for config changes)
        self._immediate_capture_requested = threading.Event()

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

        # Load active map configuration
        self._load_map_config()

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

    def _load_map_config(self) -> None:
        """Load the active map configuration from manager."""
        with self._config_lock:
            self._active_map_config = self._map_config_manager.get_active_config()

        if self._active_map_config:
            logger.info(
                f"Loaded active map config: '{self._active_map_config.name}' "
                f"at ({self._active_map_config.tl_x}, {self._active_map_config.tl_y}) "
                f"size {self._active_map_config.width}x{self._active_map_config.height}"
            )
        else:
            logger.info("No active map config - using full-screen detection")

    def reload_config(self) -> None:
        """
        Reload map configuration from disk.

        This can be called when configs are modified via the web API
        to update the active config without restarting capture.
        """
        logger.info("Reloading map configuration...")
        self._load_map_config()

        # Force immediate frame capture to update metadata
        # This prevents race condition where frontend polls status before
        # the capture loop updates region_detected (up to 0.5s delay)
        if self._running and self._capture and self._device_connected:
            logger.info("Triggering immediate frame capture after config reload...")
            self._immediate_capture_requested.set()

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

                # Use manually-defined minimap region from map config
                # When map_config is active, the region is NOT auto-detected - it's user-defined
                # CV2 only detects objects (player, enemies) WITHIN the user-defined region
                region_detected = False
                region_x, region_y = 0, 0
                region_width, region_height = 0, 0

                frame_height, frame_width = frame.shape[:2]

                # Get user-defined minimap coordinates from active map config
                with self._config_lock:
                    active_config = self._active_map_config

                if active_config:
                    # Use map config coordinates directly (no auto-detection)
                    region_x = active_config.tl_x
                    region_y = active_config.tl_y
                    region_width = active_config.width
                    region_height = active_config.height

                    # Validate region is within frame bounds
                    if (region_x + region_width <= frame_width and
                        region_y + region_height <= frame_height):
                        region_detected = True

                        logger.debug(
                            f"✓ Region detected: '{active_config.name}' at ({region_x},{region_y}) "
                            f"size {region_width}x{region_height} (frame: {frame_width}x{frame_height})"
                        )

                        # Draw visual indicator ONLY when object detection is active
                        # This shows which area CV2 is processing for object detection
                        if self._object_detection_enabled:
                            cv2.rectangle(
                                frame,
                                (region_x, region_y),
                                (region_x + region_width, region_y + region_height),
                                (0, 0, 255),  # Red color in BGR
                                2  # 2-pixel thickness
                            )
                    else:
                        error_msg = (
                            f"❌ Map config '{active_config.name}' region OUT OF BOUNDS: "
                            f"region=({region_x},{region_y}) size={region_width}x{region_height}, "
                            f"frame={frame_width}x{frame_height}. "
                            f"Region extends beyond frame boundaries."
                        )
                        logger.warning(error_msg)
                        self._set_last_error(
                            f"Map config '{active_config.name}' region is out of bounds for current frame",
                            detail=f"Config: ({region_x},{region_y}) {region_width}x{region_height}, Frame: {frame_width}x{frame_height}"
                        )
                else:
                    # No active map config - skip minimap detection
                    logger.debug("No active map config - minimap detection disabled")

                # Always use full frame (no cropping) - the red rectangle shows the minimap region
                height, width = frame.shape[:2]

                # Extract raw minimap crop BEFORE JPEG encoding for truly lossless calibration
                # Store this separately in frame buffer (~88KB for 340x86, acceptable memory cost)
                raw_minimap_crop = None
                if region_detected:
                    raw_minimap_crop = frame[
                        region_y:region_y + region_height,
                        region_x:region_x + region_width
                    ].copy()  # Copy to prevent reference to full frame

                # Run object detection if enabled (only detects objects within the minimap region)
                if self._object_detection_enabled and region_detected:
                    try:
                        with self._detection_lock:
                            if self._object_detector:
                                # Use the raw minimap crop we already extracted
                                # (no need to extract again, saves CPU cycles)

                                # Run detection
                                detection_result = self._object_detector.detect(raw_minimap_crop)
                                self._last_detection_result = detection_result

                                # Emit SSE event (if needed)
                                try:
                                    from ..events import emit
                                    emit("OBJECT_DETECTED", detection_result.to_dict())
                                except Exception:
                                    pass  # Event emission failure shouldn't break capture
                    except Exception as det_err:
                        logger.debug(f"Object detection failed: {det_err}")

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

                # Store in buffer with region metadata AND raw minimap crop
                # The raw crop enables truly lossless calibration (no JPEG artifacts)
                self.frame_buffer.update(
                    jpeg_bytes,
                    width,
                    height,
                    timestamp=timestamp,
                    region_detected=region_detected,
                    region_x=region_x,
                    region_y=region_y,
                    region_width=region_width,
                    region_height=region_height,
                    raw_minimap_crop=raw_minimap_crop
                )

                # Write to shared filesystem location for cross-process access
                self._write_shared_frame(
                    jpeg_bytes,
                    width,
                    height,
                    timestamp,
                    region_detected=region_detected,
                    region_x=region_x,
                    region_y=region_y,
                    region_width=region_width,
                    region_height=region_height
                )

                self._frames_captured += 1
                self._last_frame_time = timestamp
                self._clear_last_error()

                # Capture at 2 FPS (web UI polls every 2 seconds, so 2 FPS is plenty)
                # Original 30 FPS was wasting 240MB/sec on Raspberry Pi!
                # BUT: Skip sleep if immediate capture was requested (e.g., after config change)
                if self._immediate_capture_requested.is_set():
                    logger.debug("Immediate capture requested - skipping sleep for immediate next frame")
                    self._immediate_capture_requested.clear()
                else:
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

    def get_raw_minimap(self) -> Optional[Tuple[np.ndarray, FrameMetadata]]:
        """
        Get the latest raw minimap crop (before JPEG compression).

        This provides truly lossless minimap data for calibration, without
        JPEG compression artifacts. Memory footprint is small (~88KB for 340x86).

        Returns:
            Tuple of (raw BGR numpy array, FrameMetadata) or None if not available
        """
        return self.frame_buffer.get_raw_minimap()

    def _write_shared_frame(
        self,
        jpeg_bytes: bytes,
        width: int,
        height: int,
        timestamp: float,
        region_detected: bool = False,
        region_x: int = 0,
        region_y: int = 0,
        region_width: int = 0,
        region_height: int = 0,
        region_confidence: float = 0.0,
        region_white_ratio: float = 0.0
    ) -> None:
        """Persist latest frame and region metadata to shared memory for other processes."""
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
                    "region_detected": region_detected,
                    "region_x": region_x,
                    "region_y": region_y,
                    "region_width": region_width,
                    "region_height": region_height,
                    "region_confidence": region_confidence,
                    "region_white_ratio": region_white_ratio,
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
    
    def enable_object_detection(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Enable object detection on minimap frames.
        
        Args:
            config: Optional detector configuration dict with keys:
                - player_hsv_lower: Tuple[int, int, int]
                - player_hsv_upper: Tuple[int, int, int]
                - other_player_hsv_ranges: List[Tuple[Tuple, Tuple]]
                - min_blob_size: int
                - max_blob_size: int
                - min_circularity: float
                - temporal_smoothing: bool
                
        If config is None, loads from:
            1. Config file (~/.local/share/msmacro/object_detection_config.json)
            2. Environment variables (MSMACRO_PLAYER_COLOR_*)
            3. Defaults (placeholder HSV ranges)
        """
        from .object_detection import MinimapObjectDetector, DetectorConfig
        from .detection_config import load_config
        
        try:
            if config:
                # Filter config to only include valid DetectorConfig fields
                valid_fields = {
                    'player_hsv_lower', 'player_hsv_upper', 'other_player_hsv_ranges',
                    'min_blob_size', 'max_blob_size', 'min_circularity', 'min_circularity_other',
                    'temporal_smoothing', 'smoothing_alpha'
                }
                filtered_config = {k: v for k, v in config.items() if k in valid_fields}
                
                # Convert nested lists to tuples for hsv ranges
                if 'player_hsv_lower' in filtered_config:
                    filtered_config['player_hsv_lower'] = tuple(filtered_config['player_hsv_lower'])
                if 'player_hsv_upper' in filtered_config:
                    filtered_config['player_hsv_upper'] = tuple(filtered_config['player_hsv_upper'])
                if 'other_player_hsv_ranges' in filtered_config:
                    filtered_config['other_player_hsv_ranges'] = [
                        (tuple(lower), tuple(upper))
                        for lower, upper in filtered_config['other_player_hsv_ranges']
                    ]
                
                detector_config = DetectorConfig(**filtered_config)
            else:
                # Load from config file/env/defaults
                detector_config = load_config()
            
            with self._detection_lock:
                self._object_detector = MinimapObjectDetector(detector_config)
                self._object_detection_enabled = True
                logger.info("Object detection enabled")
        except Exception as e:
            logger.error(f"Failed to enable object detection: {e}", exc_info=True)
            raise CVCaptureError(f"Failed to enable object detection: {e}")
    
    def disable_object_detection(self) -> None:
        """Disable object detection."""
        with self._detection_lock:
            self._object_detection_enabled = False
            self._object_detector = None
            self._last_detection_result = None
            logger.info("Object detection disabled")
    
    def get_last_detection_result(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest object detection result.
        
        Returns:
            Detection result dict or None if no detection has run
        """
        with self._detection_lock:
            if self._last_detection_result:
                return self._last_detection_result.to_dict()
            return None


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
