"""
Status command handler for msmacro daemon.

Handles the 'status' command which returns the current daemon state,
mode, file list, and other system information.
"""

from typing import Dict, Any
from ..utils.config import SETTINGS


# Import cv_auto_handler lazily to avoid circular imports
def _get_capture_instance():
    """Lazily import CVCapture to avoid circular imports."""
    try:
        from ..cv.capture import get_capture_instance
        return get_capture_instance()
    except Exception:
        return None


class StatusCommandHandler:
    """Handler for status-related IPC commands."""

    def __init__(self, daemon):
        """
        Initialize the status command handler.

        Args:
            daemon: Reference to the parent MacroDaemon instance
        """
        self.daemon = daemon

    async def status(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get current daemon status including mode, files, and configuration.

        Args:
            msg: IPC message (unused for status command)

        Returns:
            Dictionary containing:
                - mode: Current operating mode (BRIDGE/RECORDING/PLAYING/POSTRECORD)
                - record_dir: Path to recordings directory
                - socket: IPC socket path
                - keyboard: Path to keyboard event device
                - have_last_actions: Whether there's a recording in memory
                - files: List of recording files with metadata
                - current_playing_file: Currently playing file path (or None)
        """
        # Get top-level JSON files from recording directory
        top_files = sorted([p.name for p in self.daemon.rec_dir.glob("*.json")])

        def meta(name: str) -> Dict[str, Any]:
            """Get metadata for a single file."""
            p = self.daemon.rec_dir / name
            try:
                st = p.stat()
                return {
                    "name": name,
                    "path": str(p),
                    "size": st.st_size,
                    "mtime": int(st.st_mtime)
                }
            except Exception:
                return {
                    "name": name,
                    "path": str(p),
                    "size": 0,
                    "mtime": 0
                }

        resp = {
            "mode": self.daemon.mode,
            "record_dir": str(self.daemon.rec_dir),
            "socket": getattr(SETTINGS, "socket_path", ""),
            "keyboard": self.daemon.evdev_path,
            "have_last_actions": bool(self.daemon._last_actions),
            "files": [meta(n) for n in top_files],
            "current_playing_file": self.daemon._current_playing_file,
        }
        return resp

    async def combined_status(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get combined daemon status including object detection and CV-AUTO status.

        This method consolidates multiple IPC calls into a single call to reduce
        IPC overhead for the SSE event stream. Previously, the SSE handler made
        3 separate IPC calls per iteration which was overwhelming the Pi.

        Args:
            msg: IPC message (unused for combined_status command)

        Returns:
            Dictionary containing:
                - status: Standard daemon status (mode, files, etc.)
                - object_detection: Object detection status and last result
                - cv_auto: CV-AUTO mode status
        """
        # Get standard status
        status_resp = await self.status(msg)

        # Get object detection status
        obj_det_resp = {"enabled": False, "last_result": None}
        try:
            capture = _get_capture_instance()
            if capture:
                obj_det_resp = {
                    "enabled": capture._object_detection_enabled,
                    "last_result": capture.get_last_detection_result()
                }
        except Exception:
            pass

        # Get CV-AUTO status (access via daemon's command dispatcher)
        cv_auto_resp = {"enabled": False}
        try:
            # Access the cv_auto_handler through the dispatcher
            from . import command_dispatcher
            # Check if daemon has dispatcher initialized
            if hasattr(self.daemon, '_dispatcher') and self.daemon._dispatcher:
                cv_auto_resp = await self.daemon._dispatcher.cv_auto_handler.cv_auto_status(msg)
        except Exception:
            pass

        return {
            "status": status_resp,
            "object_detection": obj_det_resp,
            "cv_auto": cv_auto_resp
        }
