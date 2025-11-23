"""
CV-AUTO command handler for msmacro daemon.

Handles IPC commands for CV-based automatic rotation playback:
- Starting/stopping CV-AUTO mode
- Getting current status
- Managing auto-navigation settings
"""

import asyncio
import contextlib
import logging
import random
from pathlib import Path
from typing import Dict, Any, Optional

from msmacro.cv.map_config import get_manager as get_map_manager
from msmacro.cv.cv_item import get_cv_item_manager
from msmacro.cv.object_detection import get_detector
from msmacro.daemon.point_navigator import PointNavigator
from msmacro.cv.pathfinding import PathfindingController
from msmacro.cv.port_flow import PortFlowHandler, PortDetector
from msmacro.core.player import Player
from msmacro.io.hidio import HIDWriter, AsyncHIDWriter
from msmacro.io.platform_abstraction import IS_MACOS
from msmacro.utils.config import SETTINGS
from msmacro.utils.keymap import name_to_usage

# Platform-specific imports for keyboard monitoring
if not IS_MACOS:
    from evdev import InputDevice, ecodes
    from msmacro.utils.keymap import parse_hotkey
else:
    from msmacro.io.keyboard_mock import MockInputDevice as InputDevice
    # Mock ecodes for macOS
    class ecodes:
        EV_KEY = 1
    parse_hotkey = None

try:
    from msmacro.events import emit
except Exception:
    def emit(*_a, **_kw):
        return

log = logging.getLogger(__name__)


class CVAutoCommandHandler:
    """
    Handler for CV-AUTO mode IPC commands.

    Manages the CV-based automatic rotation playback system that:
    1. Monitors player position via object detection
    2. Automatically plays rotations when hitting departure points
    3. Navigates between departure points using pathfinding or port flow
    4. Progresses sequentially through configured waypoints
    """

    def __init__(self, daemon):
        """
        Initialize CV-AUTO command handler.

        Args:
            daemon: Reference to parent MacroDaemon instance
        """
        self.daemon = daemon
        self._cv_auto_task: Optional[asyncio.Task] = None
        self._cv_auto_stop_event: Optional[asyncio.Event] = None
        self._navigator: Optional[PointNavigator] = None
        self._pathfinder: Optional[PathfindingController] = None
        self._port_handler: Optional[PortFlowHandler] = None
        self._port_detector: Optional[PortDetector] = None

        # CV-AUTO settings
        self._loop = 1  # Loop count (int, not bool)
        self._speed = 1.0
        self._jitter_time = 0.05
        self._jitter_hold = 0.02
        self._jump_key = "SPACE"  # Jump key alias for pathfinding
        self._loop_counter = 0  # Track completed loop cycles
        self._cv_auto_state = "idle"  # Current CV-AUTO state for UI debugging
        self._last_triggered_point = None  # Track last triggered point to prevent re-triggering

    async def cv_auto_start(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start CV-AUTO mode.

        Message format:
        {
            "cmd": "cv_auto_start",
            "loop": 1,                 # Loop count (repeat entire sequence N times)
            "speed": 1.0,              # Rotation playback speed
            "jitter_time": 0.05,       # Time jitter for human-like playback
            "jitter_hold": 0.02,       # Hold duration jitter
            "jump_key": "SPACE",       # Jump key alias (default: "SPACE")
            "ignore_keys": [],         # List of keys to randomly ignore (e.g., ["s", "w"])
            "ignore_tolerance": 0.0    # Probability (0.0-1.0) to ignore each key
        }

        Returns:
            {"ok": true} on success, {"error": "..."} on failure
        """
        log.info("=" * 70)
        log.info("🚀 DAEMON: CV-AUTO START REQUEST RECEIVED")
        log.info(f"Request params: {msg}")
        log.info("=" * 70)

        # Check if already running
        if self._cv_auto_task and not self._cv_auto_task.done():
            error_msg = "CV-AUTO mode already running"
            log.warning(f"❌ {error_msg}")
            log.info("=" * 70)
            return {"error": error_msg}

        log.info("✓ CV-AUTO not currently running")

        # Try to get active CV Item first (new system)
        cv_item_manager = get_cv_item_manager()
        active_cv_item = cv_item_manager.get_active_item()

        log.info(f"Active CV Item: {active_cv_item.name if active_cv_item else 'None'}")

        # Log detailed CV item data for debugging rotation issues
        if active_cv_item:
            log.info("=" * 70)
            log.info(f"📋 CV ITEM LOADED: {active_cv_item.name}")
            log.info(f"   Created: {active_cv_item.created_at}")
            log.info(f"   Last used: {active_cv_item.last_used_at}")
            log.info(f"   Departure points: {len(active_cv_item.departure_points)}")
            for i, point in enumerate(active_cv_item.departure_points):
                log.info(
                    f"   Point {i}: '{point.name}' at ({point.x}, {point.y}) - "
                    f"{len(point.rotation_paths)} rotation(s), mode={point.rotation_mode}"
                )
                for j, rot_path in enumerate(point.rotation_paths):
                    log.info(f"      Rotation {j}: {rot_path}")
            log.info("=" * 70)

        # Get map config and departure points
        if active_cv_item:
            # Use CV Item system (new)
            log.info(f"✅ Using active CV Item: {active_cv_item.name}")
            map_manager = get_map_manager()
            map_config = map_manager.get_active_config()

            # Enhanced logging: compare CV Item departure points with map config
            if map_config and map_config.departure_points:
                log.info("=" * 70)
                log.info(f"📍 MAP CONFIG COMPARISON")
                log.info(f"   Map config name: {map_config.name}")
                log.info(f"   Map config departure points: {len(map_config.departure_points)}")
                log.info(f"   CV Item departure points: {len(active_cv_item.departure_points)}")

                if len(map_config.departure_points) != len(active_cv_item.departure_points):
                    log.warning(
                        f"⚠️  MISMATCH: CV Item has {len(active_cv_item.departure_points)} points, "
                        f"but map config has {len(map_config.departure_points)} points"
                    )
                else:
                    # Compare each point
                    mismatches = []
                    for i, (cv_pt, map_pt) in enumerate(zip(active_cv_item.departure_points, map_config.departure_points)):
                        if cv_pt.rotation_paths != map_pt.rotation_paths:
                            mismatches.append(f"Point {i} ('{cv_pt.name}'): rotations differ")

                    if mismatches:
                        log.warning(f"⚠️  Departure point mismatches found:")
                        for mismatch in mismatches:
                            log.warning(f"      {mismatch}")
                    else:
                        log.info("   ✓ CV Item departure points match map config")
                log.info("=" * 70)

            if not map_config:
                error_msg = "CV Item is active but map config is not loaded"
                log.error(f"❌ {error_msg}")
                log.error(f"   CV Item: {active_cv_item.name}")
                log.error(f"   Expected map: {active_cv_item.map_config_name}")
                log.info("=" * 70)
                return {"error": error_msg}

            log.info(f"✓ Map config loaded: {map_config.name}")
            departure_points = active_cv_item.departure_points
            pathfinding_config = active_cv_item.pathfinding_config
        else:
            # Fallback to direct map config (legacy)
            log.warning("⚠️  No active CV Item, falling back to direct map config")
            map_manager = get_map_manager()
            map_config = map_manager.get_active_config()

            if not map_config:
                error_msg = "No active map config or CV Item selected"
                log.error(f"❌ {error_msg}")
                log.error("   Please activate a CV Item in the web UI")
                log.info("=" * 70)
                return {"error": error_msg}

            log.info(f"✓ Using map config: {map_config.name}")
            departure_points = map_config.departure_points
            pathfinding_config = {}

        if not departure_points:
            error_msg = "No departure points configured"
            log.error(f"❌ {error_msg}")
            log.error(f"   Map: {map_config.name if map_config else 'None'}")
            log.error(f"   CV Item: {active_cv_item.name if active_cv_item else 'None'}")
            log.error("   Please add departure points in the web UI")
            log.info("=" * 70)
            return {"error": error_msg}

        log.info(f"✓ Departure points configured: {len(departure_points)} points")

        # Check if object detection is running
        detector = get_detector()
        if not detector:
            error_msg = "Object detection must be enabled first"
            log.error(f"❌ {error_msg}")
            log.error(f"   Detector exists: {detector is not None}")
            log.error("   Please ensure CV capture and object detection are started")
            log.info("=" * 70)
            return {"error": error_msg}

        log.info("✓ Object detection is enabled")

        # Extract settings
        self._loop = msg.get("loop", 1)  # Loop count (int)
        self._speed = msg.get("speed", 1.0)
        self._jitter_time = msg.get("jitter_time", 0.05)
        self._jitter_hold = msg.get("jitter_hold", 0.02)
        self._jump_key = msg.get("jump_key", "SPACE")  # Jump key alias
        self._active_skills = msg.get("active_skills", [])  # CD skills for injection
        self._ignore_keys = msg.get("ignore_keys", [])  # Keys to randomly ignore during rotation playback
        self._ignore_tolerance = float(msg.get("ignore_tolerance", 0.0))  # Ignore probability (0.0-1.0)

        # Validate ignore_tolerance range
        if self._ignore_tolerance < 0.0 or self._ignore_tolerance > 1.0:
            log.warning(f"⚠️  Invalid ignore_tolerance {self._ignore_tolerance}, clamping to [0.0, 1.0]")
            self._ignore_tolerance = max(0.0, min(1.0, self._ignore_tolerance))

        # Reset skill injector state for new CV auto session
        if self._active_skills:
            skill_injector = self.daemon._get_or_create_skill_injector(self._active_skills)
            if skill_injector:
                skill_injector.reset_state(preserve_cooldowns=False)
                log.info("✓ Skill injector state reset for new CV auto session")

        # DEBUG: Log loop setting
        log.info(f"🔢 LOOP SETTING: {self._loop} cycles requested (loop counter starts at 0)")

        # Convert jump_key to HID usage ID
        jump_key_usage = name_to_usage(self._jump_key)
        if jump_key_usage == 0:
            log.warning(f"Invalid jump key alias '{self._jump_key}', using default SPACE (44)")
            jump_key_usage = 44  # Default to SPACE

        log.info(
            f"Starting CV-AUTO mode: map='{map_config.name}', "
            f"points={len(departure_points)}, "
            f"loop={self._loop}, speed={self._speed}, jump_key='{self._jump_key}' ({jump_key_usage}), "
            f"pathfinding_config={'configured' if pathfinding_config else 'legacy'}"
        )

        # Initialize components
        try:
            # Always use loop=True for navigator (we handle loop count manually)
            self._navigator = PointNavigator(
                departure_points=departure_points,
                map_name=map_config.name,
                loop=True
            )
            self._loop_counter = 0  # Reset loop counter
            self._last_triggered_point = None  # Reset trigger tracking

            # Create HID writer and wrap in async interface for pathfinding
            base_hid_writer = HIDWriter(self.daemon.hid_path if hasattr(self.daemon, 'hid_path')
                                        else "/dev/hidg0")
            hid_writer = AsyncHIDWriter(base_hid_writer)

            async def get_position():
                """Get current player position from cached detection results."""
                from ..cv.capture import get_capture_instance

                capture = get_capture_instance()
                if not capture:
                    return None

                result_dict = capture.get_last_detection_result()
                if result_dict:
                    player_data = result_dict.get("player", {})
                    if player_data.get("detected"):
                        return (player_data.get("x"), player_data.get("y"))

                return None

            self._pathfinder = PathfindingController(
                hid_writer,
                get_position,
                pathfinding_config=pathfinding_config,
                jump_key=jump_key_usage
            )
            self._port_handler = PortFlowHandler(hid_writer, get_position)
            self._port_detector = PortDetector()

        except Exception as e:
            log.error(f"Failed to initialize CV-AUTO components: {e}", exc_info=True)
            return {"error": f"Initialization failed: {str(e)}"}

        # Pause bridge runner to block physical keyboard (like PLAY mode)
        log.info("Pausing bridge runner to block physical keyboard during CV-AUTO...")
        await self.daemon._pause_runner()

        # Create stop event
        self._cv_auto_stop_event = asyncio.Event()

        # Start hotkey watcher for stop shortcut
        await self._start_cv_auto_hotkeys()

        # Start CV-AUTO loop
        self._cv_auto_task = asyncio.create_task(self._cv_auto_loop())

        # Update daemon mode
        self.daemon.mode = "CV_AUTO"
        emit("MODE", mode="CV_AUTO")
        emit("CV_AUTO_STARTED", map_name=map_config.name, total_points=len(departure_points))

        log.info("CV-AUTO mode started successfully")
        return {"ok": True}

    async def cv_auto_stop(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stop CV-AUTO mode.

        Message format:
        {
            "cmd": "cv_auto_stop"
        }

        Returns:
            {"ok": true} on success
        """
        if not self._cv_auto_task or self._cv_auto_task.done():
            return {"ok": True, "message": "CV-AUTO mode not running"}

        log.info("=" * 70)
        log.info("🛑 CV-AUTO STOP INITIATED")
        log.info(f"   Current mode: {self.daemon.mode}")
        log.info(f"   Task running: {self._cv_auto_task and not self._cv_auto_task.done()}")
        log.info(f"   Loop counter: {self._loop_counter}/{self._loop}")
        log.info(f"   Rotations played: {self._navigator.rotations_played_count if self._navigator else 0}")
        log.info("=" * 70)

        # Signal stop
        if self._cv_auto_stop_event:
            self._cv_auto_stop_event.set()
            log.info("✓ Stop event signaled")

        # Wait for task to complete
        try:
            await asyncio.wait_for(self._cv_auto_task, timeout=3.0)
            log.info("✓ CV-AUTO task completed gracefully")
        except asyncio.TimeoutError:
            log.warning("CV-AUTO task did not stop gracefully, cancelling...")
            self._cv_auto_task.cancel()
            try:
                await self._cv_auto_task
                log.info("✓ CV-AUTO task cancelled")
            except asyncio.CancelledError:
                pass

        # Stop hotkey watcher
        await self._stop_cv_auto_hotkeys()
        log.info("✓ Hotkey watcher stopped")

        # Cleanup components
        self._cv_auto_task = None
        self._cv_auto_stop_event = None
        self._navigator = None
        self._pathfinder = None
        self._port_handler = None
        self._port_detector = None
        log.info("✓ Components cleaned up")

        # Reset state variables (CRITICAL: prevents state pollution between sessions)
        self._loop_counter = 0
        self._last_triggered_point = None
        self._cv_auto_state = "idle"
        log.info("✓ State variables reset")

        # Return to BRIDGE mode (BEFORE restarting bridge runner)
        log.info("🔄 MODE TRANSITION: CV_AUTO → BRIDGE")
        self.daemon.mode = "BRIDGE"
        emit("MODE", mode="BRIDGE")
        log.info(f"✓ Mode set to: {self.daemon.mode}")

        # Restart bridge runner to enable physical keyboard again
        log.info("🔄 Restarting bridge runner to enable physical keyboard...")
        await self.daemon._ensure_runner_started()
        log.info("✓ Bridge runner restarted")

        # Emit stopped event
        emit("CV_AUTO_STOPPED")

        log.info("=" * 70)
        log.info("✅ CV-AUTO STOPPED SUCCESSFULLY")
        log.info("=" * 70)
        return {"ok": True}

    async def cv_auto_status(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get CV-AUTO mode status.

        Message format:
        {
            "cmd": "cv_auto_status"
        }

        Returns:
            {
                "enabled": bool,
                "current_point_index": int,
                "current_point_name": str,
                "total_points": int,
                "last_rotation_played": str,
                "rotations_played_count": int,
                "cycles_completed": int,
                "player_position": {"x": int, "y": int}
            }
        """
        enabled = self._cv_auto_task and not self._cv_auto_task.done()

        if not enabled or not self._navigator:
            return {
                "enabled": False,
                "current_point_index": 0,
                "current_point_name": "",
                "total_points": 0,
                "last_rotation_played": None,
                "rotations_played_count": 0,
                "cycles_completed": 0,
                "player_position": None,
                "state": "idle",
                "is_at_point": False
            }

        # Get navigator state
        state = self._navigator.get_state()

        # Get current player position
        player_pos = None
        is_at_point = False
        try:
            detector = get_detector()
            if detector and detector.enabled:
                result = await detector.detect()
                if result and result.player.detected:
                    player_pos = {"x": result.player.x, "y": result.player.y}
                    # Check if player is at current departure point
                    current_point = self._navigator.get_current_point()
                    is_at_point = current_point.check_hit(result.player.x, result.player.y)
        except Exception as e:
            log.warning(f"Failed to get player position for status: {e}")

        return {
            "enabled": True,
            "current_point_index": state.current_point_index,
            "current_point_name": state.current_point_name,
            "total_points": state.total_points,
            "last_rotation_played": state.last_rotation_played,
            "rotations_played_count": state.rotations_played_count,
            "cycles_completed": state.cycles_completed,
            "player_position": player_pos,
            "state": self._cv_auto_state,
            "is_at_point": is_at_point
        }

    async def _sleep_or_stop(self, delay: float) -> bool:
        """
        Sleep cooperatively for 'delay' seconds, checking stop event frequently.
        Returns True if interrupted by stop event, False otherwise.
        """
        if delay <= 0:
            return False

        # Check stop event frequently (every 10ms) for responsive stopping
        check_interval = 0.010  # 10ms
        elapsed = 0.0

        while elapsed < delay:
            if self._cv_auto_stop_event.is_set():
                log.info("Stop event detected during sleep")
                return True

            sleep_time = min(check_interval, delay - elapsed)
            await asyncio.sleep(sleep_time)
            elapsed += sleep_time

        return False

    async def _cv_auto_loop(self):
        """
        Main CV-AUTO mode loop.

        Continuously monitors player position and triggers rotations
        when departure points are hit. Handles navigation between points.
        """
        log.info("CV-AUTO loop starting...")
        log.info(f"🔢 INITIAL STATE: _loop_counter={self._loop_counter}, target _loop={self._loop}")

        try:
            while not self._cv_auto_stop_event.is_set():
                # Get current player position from cached detection results
                from ..cv.capture import get_capture_instance

                capture = get_capture_instance()
                if not capture:
                    log.warning("CV capture not available during CV-AUTO, stopping...")
                    await self._stop_cv_auto("CV capture was stopped")
                    break

                result_dict = capture.get_last_detection_result()
                if not result_dict:
                    # No detection result yet, wait and retry
                    await self._sleep_or_stop(0.1)
                    continue

                player_data = result_dict.get("player", {})
                if not player_data.get("detected"):
                    # No player detection, wait and retry
                    await self._sleep_or_stop(0.1)
                    continue

                player_pos = (player_data.get("x"), player_data.get("y"))
                current_time = asyncio.get_event_loop().time()

                # Check for port/teleport
                if self._port_detector.check_port(player_pos, current_time):
                    log.warning("Port/teleport detected, resetting navigator...")
                    self._navigator.reset()
                    self._port_detector.reset()
                    emit("CV_AUTO_PORT_DETECTED")
                    await self._sleep_or_stop(1.0)  # Wait for player to stabilize
                    continue

                self._port_detector.update_position(player_pos, current_time)

                # Get current target point
                current_point = self._navigator.get_current_point()

                # Check if player hit current point AND it's not the same point we just triggered
                # This prevents re-triggering the same point multiple times (important for single-point loops)
                if current_point.check_hit(player_pos[0], player_pos[1]):
                    if self._last_triggered_point == current_point.name:
                        # Already triggered this point, skip to avoid double-counting
                        log.debug(f"⏭️  Point '{current_point.name}' already triggered, skipping")
                        await self._sleep_or_stop(0.1)
                        continue

                    # Calculate distance for logging
                    import math
                    distance = math.sqrt((player_pos[0] - current_point.x)**2 + (player_pos[1] - current_point.y)**2)

                    log.info("=" * 70)
                    log.info(f"🎯 HIT DEPARTURE POINT: '{current_point.name}'")
                    log.info(f"   Player position: ({player_pos[0]}, {player_pos[1]})")
                    log.info(f"   Point position: ({current_point.x}, {current_point.y})")
                    log.info(f"   Distance: {distance:.1f}px")
                    log.info(f"   Tolerance: {current_point.tolerance_mode}={current_point.tolerance_value}")
                    log.info(f"   Auto-play: {current_point.auto_play}")
                    log.info("=" * 70)
                    self._cv_auto_state = "hit_departure_point"

                    # Select rotation to play
                    rotation_path = self._navigator.select_rotation(current_point)

                    if rotation_path and current_point.auto_play:
                        # Play rotation
                        log.info(f"Playing rotation: {rotation_path}")
                        self._cv_auto_state = "rotating"
                        emit("CV_AUTO_ROTATION_START",
                             point=current_point.name,
                             rotation=rotation_path)

                        success = await self._play_rotation(rotation_path)

                        # Check for stop event after rotation completes
                        if self._cv_auto_stop_event.is_set():
                            log.info("Stop event detected after rotation playback")
                            break

                        if success:
                            emit("CV_AUTO_ROTATION_END",
                                 point=current_point.name,
                                 rotation=rotation_path)
                        else:
                            log.warning(f"Rotation playback failed: {rotation_path}")
                    else:
                        if not rotation_path:
                            log.warning(f"No rotation linked to point '{current_point.name}'")
                        if not current_point.auto_play:
                            log.info(f"Auto-play disabled for point '{current_point.name}', skipping")

                    # Mark this point as triggered to prevent re-triggering
                    self._last_triggered_point = current_point.name

                    # Advance to next point
                    current_index = self._navigator.get_state().current_point_index
                    has_next = self._navigator.advance()
                    next_index = self._navigator.get_state().current_point_index

                    # Check if we completed a cycle (looped back to first point)
                    # For single point: every rotation is a cycle
                    # For multiple points: only when wrapping back to index 0
                    total_points = self._navigator.get_state().total_points
                    if next_index == 0 and (current_index > 0 or total_points == 1):
                        self._loop_counter += 1

                        # DEBUG: Detailed loop counter diagnostics
                        log.info("=" * 70)
                        log.info(f"🔄 CYCLE COMPLETED")
                        log.info(f"   Cycle: {self._loop_counter}/{self._loop}")
                        log.info(f"   DEBUG: next_index={next_index}, current_index={current_index}, total_points={total_points}")
                        log.info(f"   DEBUG: Increment condition: next_index==0 ({next_index == 0}) AND (current_index>0 ({current_index > 0}) OR total_points==1 ({total_points == 1}))")
                        log.info(f"   Total points: {total_points}")
                        log.info(f"   Total rotations played: {self._navigator.rotations_played_count}")
                        log.info(f"   Returning to: Point 0 ('{self._navigator.points[0].name}')")
                        log.info("=" * 70)

                        # Check if we've completed all desired loops
                        # DEBUG: Log the exit condition check
                        log.info(f"🔍 CHECKING EXIT: _loop_counter ({self._loop_counter}) >= _loop ({self._loop}) = {self._loop_counter >= self._loop}")

                        if self._loop_counter >= self._loop:
                            log.info("=" * 70)
                            log.info(f"✅ ALL LOOPS COMPLETED")
                            log.info(f"   Total cycles: {self._loop_counter}")
                            log.info(f"   Total rotations: {self._navigator.rotations_played_count}")
                            log.info(f"   DEBUG: Exit triggered because {self._loop_counter} >= {self._loop}")
                            log.info(f"   Stopping CV-AUTO...")
                            log.info("=" * 70)
                            await self._stop_cv_auto(f"Completed {self._loop} loop cycles")
                            break

                    next_point = self._navigator.get_current_point()
                    log.info(f"Advanced to next point: '{next_point.name}'")

                    # Check for stop event before starting navigation
                    if self._cv_auto_stop_event.is_set():
                        log.info("Stop event detected before navigation")
                        break

                    # Navigate to next point and wait until player hits it
                    post_rotation_wait = random.uniform(0.5, 1.2)  # Randomized pause after rotation
                    if await self._sleep_or_stop(post_rotation_wait):
                        log.info("Stop event detected during post-rotation pause")
                        break

                    # Keep navigating until player hits the departure point
                    from ..cv.capture import get_capture_instance
                    max_navigation_attempts = 20  # Prevent infinite loops
                    navigation_attempt = 0
                    stuck_check_interval = 5  # Check for stuck player every N attempts
                    last_stuck_check_pos = None  # Track position for stuck detection
                    stuck_threshold = 2  # Player must move >2px to not be considered stuck

                    while navigation_attempt < max_navigation_attempts:
                        # Check for stop event at start of each navigation attempt
                        if self._cv_auto_stop_event.is_set():
                            log.info("Stop event detected during navigation loop")
                            break

                        # Get current player position (with null checks)
                        capture = get_capture_instance()
                        if not capture:
                            log.warning("CV capture not available during navigation, retrying...")
                            navigation_attempt += 1
                            await self._sleep_or_stop(0.3)
                            continue

                        current_result = capture.get_last_detection_result()
                        if not current_result:
                            log.debug("No detection result during navigation, retrying...")
                            navigation_attempt += 1
                            await self._sleep_or_stop(0.3)
                            continue

                        player_data = current_result.get("player", {})
                        if not player_data.get("detected"):
                            log.debug("Player not detected during navigation, retrying...")
                            navigation_attempt += 1
                            await self._sleep_or_stop(0.3)
                            continue

                        current_pos = (player_data.get("x"), player_data.get("y"))

                        # Check if player has hit the next departure point
                        if next_point.check_hit(current_pos[0], current_pos[1]):
                            log.info(f"Player reached next departure point '{next_point.name}'")
                            break

                        # Stuck detection: Check if player has moved since last stuck check
                        if navigation_attempt > 0 and navigation_attempt % stuck_check_interval == 0:
                            if last_stuck_check_pos:
                                distance_moved = ((current_pos[0] - last_stuck_check_pos[0])**2 +
                                                (current_pos[1] - last_stuck_check_pos[1])**2)**0.5
                                if distance_moved <= stuck_threshold:
                                    log.warning(
                                        f"Player stuck at ({current_pos[0]}, {current_pos[1]}) - "
                                        f"moved only {distance_moved:.1f}px in {stuck_check_interval} attempts. "
                                        f"Skipping to next point."
                                    )
                                    break
                            last_stuck_check_pos = current_pos

                        # Player hasn't hit the point yet, continue navigating
                        navigation_attempt += 1
                        log.debug(f"Player not at '{next_point.name}' yet (attempt {navigation_attempt}/{max_navigation_attempts}), navigating...")
                        self._cv_auto_state = "pathfinding"

                        # Signal to skill injector that pathfinding is starting (freeze cooldowns)
                        skill_injector = self.daemon._skill_injector
                        if skill_injector:
                            skill_injector.enter_pathfinding_mode(asyncio.get_event_loop().time())

                        await self._navigate_to_point(next_point)

                        # Exit pathfinding mode after navigation completes (resume cooldowns)
                        if skill_injector:
                            skill_injector.exit_pathfinding_mode(asyncio.get_event_loop().time())
                            log.debug(f"✓ Exited pathfinding mode after navigation to '{next_point.name}'")

                        # Use responsive sleep that checks stop event frequently
                        if await self._sleep_or_stop(0.6):
                            log.info("Stop event detected after navigation")
                            break

                    if navigation_attempt >= max_navigation_attempts:
                        log.warning(f"Failed to reach '{next_point.name}' after {max_navigation_attempts} attempts, continuing...")

                    # Reset trigger tracking to allow next point detection
                    # For single-point scenarios, this allows re-triggering the same point
                    self._last_triggered_point = None

                else:
                    # Not at current point, try to navigate there
                    self._cv_auto_state = "navigating"

                    # Signal to skill injector that pathfinding is starting (freeze cooldowns)
                    skill_injector = self.daemon._skill_injector
                    if skill_injector:
                        skill_injector.enter_pathfinding_mode(asyncio.get_event_loop().time())

                    await self._navigate_to_point(current_point)

                    # Exit pathfinding mode after navigation completes (resume cooldowns)
                    if skill_injector:
                        skill_injector.exit_pathfinding_mode(asyncio.get_event_loop().time())
                        log.debug(f"✓ Exited pathfinding mode after navigation to current point '{current_point.name}'")

                # Emit status update
                state = self._navigator.get_state()
                is_at_point = current_point.check_hit(player_pos[0], player_pos[1])
                emit("CV_AUTO_STATUS",
                     current_index=state.current_point_index,
                     current_point=state.current_point_name,
                     total_points=state.total_points,
                     player_position={"x": player_pos[0], "y": player_pos[1]},
                     state=self._cv_auto_state,
                     is_at_point=is_at_point)

                # Wait before next iteration (responsive sleep to check stop event)
                await self._sleep_or_stop(0.1)

        except asyncio.CancelledError:
            log.info("CV-AUTO loop cancelled")
            raise
        except Exception as e:
            log.error(f"CV-AUTO loop error: {e}", exc_info=True)
            await self._stop_cv_auto(f"Error: {str(e)}")
        finally:
            log.info("CV-AUTO loop ended")

    async def _navigate_to_point(self, target_point):
        """
        Navigate to a target departure point.

        Uses Port flow if is_teleport_point=True, otherwise uses pathfinding.
        """
        # Check for stop event at start of navigation
        if self._cv_auto_stop_event.is_set():
            log.info("Stop event detected at start of navigation")
            return

        # Get current position from cached detection results
        from ..cv.capture import get_capture_instance

        capture = get_capture_instance()
        if not capture:
            return

        result_dict = capture.get_last_detection_result()
        if not result_dict:
            return

        player_data = result_dict.get("player", {})
        if not player_data.get("detected"):
            return

        current_pos = (player_data.get("x"), player_data.get("y"))

        # Check if already at target
        if target_point.check_hit(current_pos[0], current_pos[1]):
            return

        # Check for stop event before navigation
        if self._cv_auto_stop_event.is_set():
            log.info("Stop event detected before executing navigation")
            return

        # Navigate based on point type
        if target_point.is_teleport_point:
            log.debug(f"Using Port flow to reach '{target_point.name}'")
            success = await self._port_handler.execute_port_flow(current_pos, target_point)

            if not success:
                log.error(f"Port flow failed to reach '{target_point.name}'")
                await self._stop_cv_auto("Port flow navigation failed")
        else:
            log.debug(f"Using pathfinding to reach '{target_point.name}'")
            success = await self._pathfinder.navigate_to(current_pos, target_point)

            if not success:
                log.warning(f"Pathfinding failed to reach '{target_point.name}', continuing...")

    async def _play_rotation(self, rotation_path: str) -> bool:
        """
        Play a rotation file.

        Returns:
            True if playback completed successfully, False otherwise
        """
        try:
            # Create Player instance and play the rotation
            from ..core.player import Player
            from ..utils.config import SETTINGS
            from pathlib import Path

            log.info("=" * 70)
            log.info(f"🎮 ROTATION PLAYBACK START")
            log.info(f"   Rotation path (from CV item): {rotation_path}")
            log.info(f"   Records directory: {SETTINGS.record_dir}")

            # Construct full path to rotation file
            if Path(rotation_path).is_absolute():
                full_path = rotation_path
                log.info(f"   Path type: ABSOLUTE")
            else:
                # Relative path - resolve from records directory
                full_path = SETTINGS.record_dir / rotation_path
                log.info(f"   Path type: RELATIVE (resolved from record_dir)")

            log.info(f"   Full path resolved: {full_path}")
            log.info(f"   File exists: {Path(full_path).exists()}")
            log.info(f"   Playback settings:")
            log.info(f"      Speed: {self._speed}x")
            log.info(f"      Jitter time: {self._jitter_time}s")
            log.info(f"      Jitter hold: {self._jitter_hold}s")
            log.info(f"      Active skills: {len(getattr(self, '_active_skills', []))}")
            log.info(f"   Cycle progress: {self._loop_counter + 1}/{self._loop}")

            if not Path(full_path).exists():
                log.error(f"❌ ROTATION FILE NOT FOUND: {full_path}")
                log.error(f"   Original path from CV item: {rotation_path}")
                log.error(f"   Tried absolute path: {Path(rotation_path).is_absolute()}")
                log.error(f"   Record directory: {SETTINGS.record_dir}")
                log.info("=" * 70)
                return False

            hid_path = self.daemon.hid_path if hasattr(self.daemon, 'hid_path') else "/dev/hidg0"
            player = Player(hid_path)

            # Create or reuse SkillInjector if active_skills configured
            skill_injector = self.daemon._get_or_create_skill_injector(
                getattr(self, '_active_skills', [])
            )

            # Use instance variables for ignore keys (set during cv_auto_start)
            ignore_keys = getattr(self, '_ignore_keys', [])
            ignore_tolerance = getattr(self, '_ignore_tolerance', 0.0)

            # Log if ignore keys are configured
            if ignore_keys:
                log.info(
                    f"🎲 Rotation playback with ignore_keys={ignore_keys}, "
                    f"tolerance={ignore_tolerance:.2f}"
                )

            # Signal to skill injector that rotation is starting (exit pathfinding mode)
            if skill_injector:
                skill_injector.exit_pathfinding_mode(asyncio.get_event_loop().time())

            success = await player.play(
                path=full_path,
                speed=self._speed,
                jitter_time=self._jitter_time,
                jitter_hold=self._jitter_hold,
                loop=1,  # Play once (not False)
                stop_event=self._cv_auto_stop_event,
                ignore_keys=ignore_keys,           # ✅ From CV auto session settings
                ignore_tolerance=ignore_tolerance, # ✅ From CV auto session settings
                skill_injector=skill_injector  # Use SkillInjector for CD skill casting
            )

            if success:
                log.info(f"✅ ROTATION PLAYBACK COMPLETED: {rotation_path}")
            else:
                log.warning(f"⚠️  ROTATION PLAYBACK INCOMPLETE: {rotation_path}")
            log.info("=" * 70)

            return success
        except Exception as e:
            log.error(f"❌ ROTATION PLAYBACK ERROR: {rotation_path}")
            log.error(f"   Exception: {e}", exc_info=True)
            log.info("=" * 70)
            return False

    async def _stop_cv_auto(self, reason: str):
        """
        Stop CV-AUTO mode with a reason.

        Args:
            reason: Reason for stopping
        """
        log.warning(f"Stopping CV-AUTO: {reason}")
        emit("CV_AUTO_ERROR", reason=reason)

        if self._cv_auto_stop_event:
            self._cv_auto_stop_event.set()

    async def _cv_auto_hotkeys(self):
        """
        Listen for the stop chord while in CV_AUTO mode and set self._cv_auto_stop_event.

        Similar to daemon._play_hotkeys() but for CV-AUTO mode.
        """
        stop_spec = getattr(SETTINGS, "stop_hotkey", "LCTRL+Q")
        log.info("🎹 CV-AUTO HOTKEY WATCHER STARTED")
        log.info(f"   Stop hotkey: {stop_spec}")

        try:
            if parse_hotkey is None:
                log.warning("CV-AUTO hotkeys: parse_hotkey not available (macOS mock mode)")
                return
            mod_ec, key_ec = parse_hotkey(stop_spec)
        except Exception:
            mod_ec = key_ec = None

        # Resolve keyboard device
        evdev_path = self.daemon.evdev_path
        if not evdev_path or not Path(evdev_path).exists():
            from msmacro.io.keyboard import find_keyboard_with_retry
            evdev_path = await find_keyboard_with_retry(max_retries=10)

        if not evdev_path:
            log.warning("CV-AUTO hotkeys: No keyboard found after retries, disabling hotkey support")
            return

        try:
            dev = InputDevice(evdev_path)
        except Exception as e:
            log.warning("CV-AUTO hotkeys: cannot open %s: %s", evdev_path, e)
            return

        mod_dn = key_dn = armed = False
        try:
            async for ev in dev.async_read_loop():
                # Exit if mode changed or stop event cleared
                if self.daemon.mode != "CV_AUTO" or not self._cv_auto_stop_event:
                    log.debug("CV-AUTO watcher: mode changed or no stop event, exiting")
                    break
                if ev.type != ecodes.EV_KEY:
                    continue
                code, val = ev.code, ev.value
                if val == 2:  # repeat
                    continue

                if mod_ec is not None and key_ec is not None:
                    if code == mod_ec:
                        mod_dn = (val != 0)
                        if mod_dn and key_dn:
                            armed = True
                            log.debug("CV-AUTO watcher: stop chord ARMED")
                        if armed and not mod_dn and not key_dn:
                            log.info("CV-AUTO hotkey: STOP")
                            log.debug("CV-AUTO hotkey: Setting stop event (current mode=%s)", self.daemon.mode)
                            if self._cv_auto_stop_event:
                                self._cv_auto_stop_event.set()
                                log.info("CV-AUTO stop event SET")
                            break
                    elif code == key_ec:
                        key_dn = (val != 0)
                        if mod_dn and key_dn:
                            armed = True
                            log.debug("CV-AUTO watcher: stop chord ARMED")
                        if armed and not mod_dn and not key_dn:
                            log.info("CV-AUTO hotkey: STOP")
                            log.debug("CV-AUTO hotkey: Setting stop event (current mode=%s)", self.daemon.mode)
                            if self._cv_auto_stop_event:
                                self._cv_auto_stop_event.set()
                                log.info("CV-AUTO stop event SET")
                            break
        except asyncio.CancelledError:
            log.debug("CV-AUTO hotkeys watcher cancelled")
        except Exception:
            log.exception("CV-AUTO hotkeys watcher crashed.")
        finally:
            with contextlib.suppress(Exception):
                dev.close()
            log.debug("CV-AUTO hotkeys watcher stopped.")

    async def _start_cv_auto_hotkeys(self):
        """Start the CV-AUTO hotkey watcher task."""
        if getattr(self, "_cv_auto_hotkey_task", None) and not self._cv_auto_hotkey_task.done():
            return
        if self.daemon.mode != "CV_AUTO":
            return
        log.info("Starting CV-AUTO hotkey watcher (stop shortcut: %s)",
                 getattr(SETTINGS, "stop_hotkey", "LCTRL+Q"))
        self._cv_auto_hotkey_task = asyncio.create_task(self._cv_auto_hotkeys())

    async def _stop_cv_auto_hotkeys(self):
        """Stop the CV-AUTO hotkey watcher task."""
        t = getattr(self, "_cv_auto_hotkey_task", None)
        if t and not t.done():
            log.info("Stopping CV-AUTO hotkey watcher...")
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._cv_auto_hotkey_task = None
