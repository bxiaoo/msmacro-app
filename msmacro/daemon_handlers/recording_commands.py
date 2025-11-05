"""
Recording command handlers for msmacro daemon.

Handles recording lifecycle IPC commands including start, save,
discard, and preview operations.
"""

import asyncio
import json
import logging
from typing import Dict, Any

log = logging.getLogger(__name__)

# Import event emitter with fallback
try:
    from ..events import emit
except Exception:
    def emit(*_a, **_kw):
        return


# Import event conversion utility
from ..core.event_utils import events_to_actions as _events_to_actions


class RecordingCommandHandler:
    """Handler for recording lifecycle IPC commands."""

    def __init__(self, daemon):
        """
        Initialize the recording command handler.

        Args:
            daemon: Reference to the parent MacroDaemon instance
        """
        self.daemon = daemon

    async def record_start(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start a new recording session.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "recording" key set to True

        Raises:
            RuntimeError: If not in BRIDGE or POSTRECORD mode
        """
        if self.daemon.mode not in ("BRIDGE", "POSTRECORD"):
            raise RuntimeError(f"cannot start record from mode {self.daemon.mode}")

        # Start recording task if not already running
        if not (self.daemon._record_task and not self.daemon._record_task.done()):
            self.daemon._record_task = asyncio.create_task(self.daemon._record_direct())

        return {"recording": True}

    async def save_last(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save the last recorded actions to a file.

        Args:
            msg: IPC message containing:
                - name: Filename to save (with or without .json extension)

        Returns:
            Dictionary with "saved" key containing the file path

        Raises:
            RuntimeError: If no recording in memory or name not provided
        """
        if not self.daemon._last_actions:
            raise RuntimeError("no last recording")

        name = msg.get("name")
        if not name:
            raise RuntimeError("missing name")

        # Get actions and convert format if needed
        items = self.daemon._last_actions or []
        if items and isinstance(items[0], dict) and ('t' in items[0] or 'type' in items[0]) and 'press' not in items[0]:
            items = _events_to_actions(items)

        # Ensure .json extension
        filename = name if str(name).endswith(".json") else f"{name}.json"
        path = (self.daemon.rec_dir / filename).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        data = {"t0": 0.0, "actions": items}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Emit event and update state
        emit("SAVED", path=str(path))
        log.info("Saved recording: %s (%d actions)", path, len(items))

        self.daemon._last_actions = None
        await self.daemon._stop_post_hotkeys()
        self.daemon.mode = "BRIDGE"
        emit("MODE", mode=self.daemon.mode)
        await self.daemon._ensure_runner_started()

        return {"saved": str(path)}

    async def discard_last(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Discard the last recording without saving.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "discarded" key set to True
        """
        await self.daemon._discard_last()
        return {"discarded": True}

    async def preview_last(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preview (play once) the last recording.

        Args:
            msg: IPC message containing optional playback parameters:
                - speed: Playback speed multiplier (default: 1.0)
                - jitter_time: Time jitter amount (default: 0.0)
                - jitter_hold: Hold duration jitter (default: 0.0)
                - ignore_keys: List of keys to randomly ignore
                - ignore_tolerance: Probability of ignoring keys (0-1)

        Returns:
            Dictionary with "previewed" key set to True
        """
        speed = float(msg.get("speed", 1.0))
        jt = float(msg.get("jitter_time", 0.0))
        jh = float(msg.get("jitter_hold", 0.0))
        ignore_keys = msg.get("ignore_keys", [])
        ignore_tolerance = float(msg.get("ignore_tolerance", 0.0))

        await self.daemon._preview_last_once(
            speed=speed,
            jt=jt,
            jh=jh,
            ignore_keys=ignore_keys,
            ignore_tolerance=ignore_tolerance
        )

        return {"previewed": True}
