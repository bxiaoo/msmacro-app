"""
IPC command dispatcher for msmacro daemon.

Routes IPC commands to appropriate specialized command handlers.
This module acts as the central router, delegating commands to
focused handler classes organized by functionality.
"""

import logging
from typing import Dict, Any

from .status_commands import StatusCommandHandler
from .file_commands import FileCommandHandler
from .recording_commands import RecordingCommandHandler
from .playback_commands import PlaybackCommandHandler
from .skills_commands import SkillsCommandHandler
from .cv_commands import CVCommandHandler
from .system_commands import SystemCommandHandler
from .cv_auto_commands import CVAutoCommandHandler

log = logging.getLogger(__name__)


class CommandDispatcher:
    """
    Central command dispatcher for the msmacro daemon.

    Routes incoming IPC commands to appropriate handler classes
    based on command functionality (recording, playback, skills, CV, etc.).
    """

    def __init__(self, daemon):
        """
        Initialize the command dispatcher with all handler instances.

        Args:
            daemon: Reference to the parent MacroDaemon instance
        """
        self.daemon = daemon

        # Initialize all command handlers
        self.status_handler = StatusCommandHandler(daemon)
        self.file_handler = FileCommandHandler(daemon)
        self.recording_handler = RecordingCommandHandler(daemon)
        self.playback_handler = PlaybackCommandHandler(daemon)
        self.skills_handler = SkillsCommandHandler(daemon)
        self.cv_handler = CVCommandHandler(daemon)
        self.system_handler = SystemCommandHandler(daemon)
        self.cv_auto_handler = CVAutoCommandHandler(daemon)

    async def dispatch(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch an IPC command to the appropriate handler.

        Args:
            msg: IPC message dictionary containing at minimum a "cmd" key

        Returns:
            Response dictionary from the command handler

        Raises:
            RuntimeError: If command is unknown
            Other exceptions: Propagated from command handlers
        """
        cmd = msg.get("cmd", "").strip()

        # Status commands
        if cmd == "status":
            return await self.status_handler.status(msg)
        elif cmd == "combined_status":
            return await self.status_handler.combined_status(msg)

        # File management commands
        elif cmd == "list":
            return await self.file_handler.list(msg)
        elif cmd == "list_recursive":
            return await self.file_handler.list_recursive(msg)
        elif cmd == "rename_recording":
            return await self.file_handler.rename_recording(msg)

        # Recording commands
        elif cmd == "record_start":
            return await self.recording_handler.record_start(msg)
        elif cmd == "save_last":
            return await self.recording_handler.save_last(msg)
        elif cmd == "discard_last":
            return await self.recording_handler.discard_last(msg)
        elif cmd == "preview_last":
            return await self.recording_handler.preview_last(msg)

        # Playback commands
        elif cmd == "play":
            return await self.playback_handler.play(msg)
        elif cmd == "play_selection":
            return await self.playback_handler.play_selection(msg)
        elif cmd == "stop":
            return await self.playback_handler.stop(msg)

        # Skills management commands
        elif cmd == "list_skills":
            return await self.skills_handler.list_skills(msg)
        elif cmd == "save_skill":
            return await self.skills_handler.save_skill(msg)
        elif cmd == "update_skill":
            return await self.skills_handler.update_skill(msg)
        elif cmd == "delete_skill":
            return await self.skills_handler.delete_skill(msg)
        elif cmd == "get_selected_skills":
            return await self.skills_handler.get_selected_skills(msg)
        elif cmd == "reorder_skills":
            return await self.skills_handler.reorder_skills(msg)

        # Computer Vision commands
        elif cmd == "cv_status":
            return await self.cv_handler.cv_status(msg)
        elif cmd == "cv_get_frame":
            return await self.cv_handler.cv_get_frame(msg)
        elif cmd == "cv_start":
            return await self.cv_handler.cv_start(msg)
        elif cmd == "cv_stop":
            return await self.cv_handler.cv_stop(msg)
        elif cmd == "cv_get_raw_minimap":
            return await self.cv_handler.cv_get_raw_minimap(msg)
        elif cmd == "cv_reload_config":
            return await self.cv_handler.cv_reload_config(msg)

        # Object Detection commands
        elif cmd == "object_detection_status":
            return await self.cv_handler.object_detection_status(msg)
        elif cmd == "object_detection_start":
            return await self.cv_handler.object_detection_start(msg)
        elif cmd == "object_detection_stop":
            return await self.cv_handler.object_detection_stop(msg)
        elif cmd == "object_detection_config":
            return await self.cv_handler.object_detection_config(msg)
        elif cmd == "object_detection_config_save":
            return await self.cv_handler.object_detection_config_save(msg)
        elif cmd == "object_detection_config_export":
            return await self.cv_handler.object_detection_config_export(msg)
        elif cmd == "object_detection_performance":
            return await self.cv_handler.object_detection_performance(msg)
        elif cmd == "object_detection_calibrate":
            return await self.cv_handler.object_detection_calibrate(msg)
        elif cmd == "cv_get_detection_preview":
            return await self.cv_handler.cv_get_detection_preview(msg)
        elif cmd == "cv_save_calibration_sample":
            return await self.cv_handler.cv_save_calibration_sample(msg)

        # System information commands
        elif cmd == "system_stats":
            return await self.system_handler.system_stats(msg)

        # CV-AUTO commands
        elif cmd == "cv_auto_start":
            return await self.cv_auto_handler.cv_auto_start(msg)
        elif cmd == "cv_auto_stop":
            return await self.cv_auto_handler.cv_auto_stop(msg)
        elif cmd == "cv_auto_status":
            return await self.cv_auto_handler.cv_auto_status(msg)

        # Rotation linking command
        elif cmd == "link_rotations_to_point":
            return await self.cv_handler.link_rotations_to_point(msg)

        # Unknown command
        else:
            raise RuntimeError(f"unknown cmd: {cmd}")
