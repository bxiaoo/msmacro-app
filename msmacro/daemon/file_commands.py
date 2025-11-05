"""
File management command handlers for msmacro daemon.

Handles file-related IPC commands including listing, renaming,
and directory operations for recordings.
"""

import logging
from typing import Dict, Any
from ..core.recorder import list_recordings_recursive, resolve_record_path

log = logging.getLogger(__name__)


class FileCommandHandler:
    """Handler for file management IPC commands."""

    def __init__(self, daemon):
        """
        Initialize the file command handler.

        Args:
            daemon: Reference to the parent MacroDaemon instance
        """
        self.daemon = daemon

    async def list(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all recording files in the top-level recording directory.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "files" key containing list of filenames
        """
        if self.daemon.rec_dir.exists():
            files = sorted(x.name for x in self.daemon.rec_dir.glob("*.json"))
        else:
            files = []
        return {"files": files}

    async def list_recursive(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all recordings recursively with folder structure.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "items" key containing recursive file tree
        """
        items = list_recordings_recursive(self.daemon.rec_dir)
        return {"items": items}

    async def rename_recording(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rename a recording file.

        Args:
            msg: IPC message containing:
                - old: Current file path (relative or absolute)
                - new: New file path (relative or absolute)

        Returns:
            Dictionary with "renamed" key containing from/to paths

        Raises:
            RuntimeError: If old/new paths missing or old file not found
        """
        old = msg.get("old")
        new = msg.get("new")

        if not old or not new:
            raise RuntimeError("missing old/new")

        oldp = resolve_record_path(self.daemon.rec_dir, old)
        newp = resolve_record_path(self.daemon.rec_dir, new)

        # Ensure target directory exists
        newp.parent.mkdir(parents=True, exist_ok=True)

        if not oldp.exists():
            raise RuntimeError(f"not found: {old}")

        oldp.rename(newp)
        log.info("Renamed recording: %s -> %s", oldp, newp)

        return {"renamed": {"from": str(oldp), "to": str(newp)}}
