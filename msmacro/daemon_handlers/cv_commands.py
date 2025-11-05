"""
Computer Vision command handlers for msmacro daemon.

Handles IPC commands for CV capture system operations including
starting/stopping capture and retrieving frames and status.
"""

import base64
from typing import Dict, Any
from ..cv import get_capture_instance

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

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "frame" key containing base64-encoded JPEG data

        Raises:
            RuntimeError: If no frame is available
        """
        capture = get_capture_instance()
        frame_data = capture.get_latest_frame()

        if frame_data is None:
            raise RuntimeError("no frame available")

        # Encode as base64 for JSON transport
        return {"frame": base64.b64encode(frame_data).decode('ascii')}

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
