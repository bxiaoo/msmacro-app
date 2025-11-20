"""
Playback command handlers for msmacro daemon.

Handles playback-related IPC commands including playing single files,
playlists, and stopping playback.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any
from ..core.recorder import resolve_record_path

log = logging.getLogger(__name__)


class PlaybackCommandHandler:
    """Handler for playback-related IPC commands."""

    def __init__(self, daemon):
        """
        Initialize the playback command handler.

        Args:
            daemon: Reference to the parent MacroDaemon instance
        """
        self.daemon = daemon

    async def play(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Play a single recording file.

        Args:
            msg: IPC message containing:
                - file: Path to recording file (relative or absolute)
                - speed: Playback speed multiplier (default: 1.0)
                - jitter_time: Time jitter amount (default: 0.0)
                - jitter_hold: Hold duration jitter (default: 0.0)
                - loop: Number of times to loop (default: 1)
                - ignore_keys: List of keys to randomly ignore
                - ignore_tolerance: Probability of ignoring keys (0-1)
                - active_skills: List of active skills for injection

        Returns:
            Dictionary with playback parameters

        Raises:
            RuntimeError: If not in BRIDGE/POSTRECORD mode or file not found
        """
        if self.daemon.mode not in ("BRIDGE", "POSTRECORD"):
            raise RuntimeError(f"cannot play from mode {self.daemon.mode}")

        name = msg.get("file")
        if not name:
            raise RuntimeError("missing file")

        # Resolve file path
        p = Path(name)
        if not p.exists():
            alt = self.daemon.rec_dir / (name if str(name).endswith(".json") else f"{name}.json")
            if not alt.exists():
                raise RuntimeError(f"not found: {name}")
            p = alt

        # Extract playback parameters
        kwargs = {
            "speed": float(msg.get("speed", 1.0)),
            "jt": float(msg.get("jitter_time", 0.0)),
            "jh": float(msg.get("jitter_hold", 0.0)),
            "loop": int(msg.get("loop", 1)),
            "ignore_keys": msg.get("ignore_keys", []),
            "ignore_tolerance": float(msg.get("ignore_tolerance", 0.0)),
            "active_skills": msg.get("active_skills", []),
        }

        # Start playback task
        self.daemon._play_task = asyncio.create_task(self.daemon._do_play(str(p), **kwargs))

        return {"playing": str(p), **kwargs}

    async def play_selection(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Play multiple recording files as a playlist.

        Args:
            msg: IPC message containing:
                - names: List of file paths (relative or absolute)
                - speed: Playback speed multiplier (default: 1.0)
                - jitter_time: Time jitter amount (default: 0.0)
                - jitter_hold: Hold duration jitter (default: 0.0)
                - loop: Number of times to loop entire playlist (default: 1)
                - ignore_keys: List of keys to randomly ignore
                - ignore_tolerance: Probability of ignoring keys (0-1)
                - active_skills: List of active skills for injection

        Returns:
            Dictionary with playlist and playback parameters

        Raises:
            RuntimeError: If names missing/empty or no valid files found
        """
        names = msg.get("names") or []
        if not isinstance(names, list) or not names:
            raise RuntimeError("empty selection")

        # Resolve all file paths
        paths = []
        for n in names:
            p = resolve_record_path(self.daemon.rec_dir, n)
            if p.exists():
                paths.append(str(p))

        if not paths:
            raise RuntimeError("no valid files")

        # Extract playback parameters
        kwargs = {
            "speed": float(msg.get("speed", 1.0)),
            "jt": float(msg.get("jitter_time", 0.0)),
            "jh": float(msg.get("jitter_hold", 0.0)),
            "loop": int(msg.get("loop", 1)),
            "ignore_keys": msg.get("ignore_keys", []),
            "ignore_tolerance": float(msg.get("ignore_tolerance", 0.0)),
            "active_skills": msg.get("active_skills", []),
        }

        # Start playlist playback task
        self.daemon._play_task = asyncio.create_task(self.daemon._do_play_selection(paths, **kwargs))

        return {"playlist": paths, **kwargs}

    async def stop(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stop current playback or recording.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with stop status and current mode
        """
        log.info("IPC: stop command received (mode=%s)", self.daemon.mode)

        # Stop playback if in PLAYING mode
        if self.daemon.mode == "PLAYING" and self.daemon._stop_event:
            log.info("🛑 STOP COMMAND: Setting stop_event (id=%s, is_set_before=%s)",
                     id(self.daemon._stop_event), self.daemon._stop_event.is_set())
            self.daemon._stop_event.set()
            log.info("🛑 STOP COMMAND: stop_event.set() called (is_set_after=%s)",
                     self.daemon._stop_event.is_set())

            # Also try to cancel the play task if it exists
            if hasattr(self.daemon, '_play_task') and self.daemon._play_task and not self.daemon._play_task.done():
                log.info("Cancelling play task")
                self.daemon._play_task.cancel()

            # Wait a moment for the mode to change
            await asyncio.sleep(0.1)
            return {"stopping": "playback", "mode": self.daemon.mode}

        # Stop CV-AUTO if in CV_AUTO mode
        if self.daemon.mode == "CV_AUTO":
            from .cv_auto_commands import CVAutoCommandHandler
            cv_auto_handler = self.daemon._dispatcher.handlers.get('cv_auto')

            if cv_auto_handler and cv_auto_handler._cv_auto_stop_event:
                log.info("🛑 STOP COMMAND: Setting cv_auto_stop_event (id=%s, is_set_before=%s)",
                         id(cv_auto_handler._cv_auto_stop_event), cv_auto_handler._cv_auto_stop_event.is_set())
                cv_auto_handler._cv_auto_stop_event.set()
                log.info("🛑 STOP COMMAND: cv_auto_stop_event.set() called (is_set_after=%s)",
                         cv_auto_handler._cv_auto_stop_event.is_set())

            # Cancel CV-AUTO task if it exists
            if cv_auto_handler and cv_auto_handler._cv_auto_task and not cv_auto_handler._cv_auto_task.done():
                log.info("Cancelling CV-AUTO task")
                cv_auto_handler._cv_auto_task.cancel()

            # Wait a moment for the mode to change
            await asyncio.sleep(0.1)
            return {"stopping": "cv_auto", "mode": self.daemon.mode}

        # Stop recording if in RECORDING mode
        if self.daemon.mode == "RECORDING" and self.daemon._record_task and not self.daemon._record_task.done():
            log.info("Cancelling recording task")
            self.daemon._record_task.cancel()
            return {"stopping": "recording"}

        return {"mode": self.daemon.mode, "nothing_to_stop": True}
