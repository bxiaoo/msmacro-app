"""
Main capture manager for HDMI video capture cards using OpenCV.
"""

import asyncio
import logging
import threading
import time
from typing import Optional, Dict, Any
import cv2
import numpy as np

from .device import CaptureDevice, find_capture_device, find_capture_device_with_retry, validate_device_access
from .frame_buffer import FrameBuffer

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

    def __init__(self, jpeg_quality: int = 85):
        """
        Initialize the capture manager.

        Args:
            jpeg_quality: JPEG compression quality (0-100, higher is better)
        """
        self.jpeg_quality = jpeg_quality
        self.frame_buffer = FrameBuffer()

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

        # Find device with retry
        self._device = await find_capture_device_with_retry(max_retries=3)
        if not self._device:
            raise CVCaptureError("No capture device found after retries")

        # Validate device access
        if not validate_device_access(self._device):
            raise CVCaptureError(f"Cannot access device: {self._device.device_path}")

        # Initialize capture
        await self._init_capture()

        # Start capture thread
        self._stop_event.clear()
        self._running = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        # Start monitoring task
        self._monitor_task = asyncio.create_task(self._monitor_device())

        logger.info(f"CV capture started with device: {self._device}")

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

        # Use device index for OpenCV
        self._capture = cv2.VideoCapture(self._device.device_index)

        if not self._capture.isOpened():
            self._capture = None
            raise CVCaptureError(f"Failed to open capture device: {self._device.device_path}")

        # Configure capture for best performance
        # Use MJPEG if available for lower CPU usage
        self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

        # Verify we can read a frame
        ret, frame = self._capture.read()
        if not ret or frame is None:
            self._release_capture()
            raise CVCaptureError("Failed to read initial frame from device")

        self._device_connected = True
        logger.info(f"Capture initialized: {int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
                    f"{int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ "
                    f"{self._capture.get(cv2.CAP_PROP_FPS)} FPS")

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
                    time.sleep(0.5)
                    continue

                # Encode as JPEG
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
                ret, jpeg_data = cv2.imencode('.jpg', frame, encode_param)

                if not ret or jpeg_data is None:
                    self._frames_failed += 1
                    logger.warning("Failed to encode frame as JPEG")
                    continue

                # Store in buffer
                height, width = frame.shape[:2]
                self.frame_buffer.update(jpeg_data.tobytes(), width, height)

                self._frames_captured += 1
                self._last_frame_time = time.time()

                # Small delay to avoid consuming 100% CPU
                time.sleep(0.03)  # ~30 FPS max capture rate

            except Exception as e:
                self._frames_failed += 1
                logger.error(f"Error in capture loop: {e}", exc_info=True)
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

    def get_latest_frame(self) -> Optional[bytes]:
        """
        Get the latest captured frame as JPEG data.

        Returns:
            JPEG-encoded frame bytes or None if no frame available
        """
        result = self.frame_buffer.get_latest()
        if result:
            jpeg_data, _ = result
            return jpeg_data
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
