"""
Computer Vision command handlers for msmacro daemon.

Handles IPC commands for CV capture system operations including
starting/stopping capture and retrieving frames and status.
"""

import asyncio
import base64
import logging
from dataclasses import asdict
from typing import Dict, Any
from ..cv import get_capture_instance, CVCaptureError

logger = logging.getLogger(__name__)

# Import event emitter with fallback
try:
    from ..events import emit
except Exception:
    def emit(*_a, **_kw):
        return


class CVCommandHandler:
    """Handler for computer vision IPC commands."""

    def __init__(self, daemon):
        """
        Initialize the CV command handler.

        Args:
            daemon: Reference to the parent MacroDaemon instance
        """
        self.daemon = daemon

    async def cv_status(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get CV capture device status and latest frame information.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with CV status including:
                - connected: Whether device is connected
                - capturing: Whether capture is active
                - has_frame: Whether a frame is available
                - device: Device information (if connected)
                - capture: Capture settings (if capturing)
                - frame: Frame metadata (if available)
                - frames_captured: Total frames captured
                - frames_failed: Total failed frame captures
        """
        capture = get_capture_instance()
        status = capture.get_status()
        return status

    async def cv_get_frame(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get the latest captured frame as JPEG data.

        Auto-starts capture if not already running.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "frame" key containing base64-encoded JPEG data

        Raises:
            RuntimeError: If capture fails to start or no frame available after timeout
        """
        capture = get_capture_instance()
        status = capture.get_status()

        logger.debug(f"cv_get_frame called: capturing={status.get('capturing')}, has_frame={status.get('has_frame')}")

        # Auto-start capture if not running
        if not status.get('capturing'):
            logger.info("CV capture not running, auto-starting...")
            try:
                await capture.start()
                logger.info("CV capture auto-started successfully")

                # Wait up to 3 seconds for first frame to be captured
                for attempt in range(30):  # 30 x 0.1s = 3 seconds
                    await asyncio.sleep(0.1)
                    frame_result = capture.get_latest_frame()
                    if frame_result is not None:
                        logger.info(f"First frame captured after {(attempt + 1) * 0.1:.1f}s")
                        break
                else:
                    # Timeout waiting for first frame
                    last_error = capture.get_status().get('last_error')
                    error_detail = f": {last_error}" if last_error else ""
                    raise RuntimeError(f"Timed out waiting for first frame after auto-start{error_detail}")

            except CVCaptureError as e:
                logger.error(f"Failed to auto-start CV capture: {e}")
                raise RuntimeError(f"Failed to start CV capture: {e}")
            except Exception as e:
                logger.error(f"Unexpected error auto-starting CV capture: {e}", exc_info=True)
                raise RuntimeError(f"Failed to start CV capture: {e}")

        # Get frame
        frame_result = capture.get_latest_frame()

        if frame_result is None:
            last_error = capture.get_status().get('last_error')
            error_context = f" (last error: {last_error})" if last_error else ""
            logger.warning(f"No frame available{error_context}")
            raise RuntimeError(f"no frame available{error_context}")

        frame_data, metadata = frame_result

        # Encode as base64 for JSON transport
        payload: Dict[str, Any] = {
            "frame": base64.b64encode(frame_data).decode('ascii')
        }
        if metadata is not None:
            payload["metadata"] = asdict(metadata)

        logger.debug(f"Returning frame: {len(frame_data)} bytes, {metadata.width}x{metadata.height}")
        return payload

    async def cv_start(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start the CV capture system.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "started" key set to True and "status" with current state

        Note:
            Emits CV_STARTED event on success
        """
        capture = get_capture_instance()
        await capture.start()
        emit("CV_STARTED")
        return {"started": True, "status": capture.get_status()}

    async def cv_stop(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stop the CV capture system.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "stopped" key set to True

        Note:
            Emits CV_STOPPED event on success
        """
        capture = get_capture_instance()
        await capture.stop()
        emit("CV_STOPPED")
        return {"stopped": True}
