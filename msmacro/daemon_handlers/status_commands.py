"""
Status command handler for msmacro daemon.

Handles the 'status' command which returns the current daemon state,
mode, file list, and other system information.
"""

from typing import Dict, Any
from ..utils.config import SETTINGS


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
