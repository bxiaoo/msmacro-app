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
            "jump_key": "SPACE"        # Jump key alias (default: "SPACE")
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

        # Get map config and departure points
        if active_cv_item:
            # Use CV Item system (new)
            log.info(f"✅ Using active CV Item: {active_cv_item.name}")
            map_manager = get_map_manager()
            map_config = map_manager.get_active_config()

            if not map_config:
                error_msg = "CV Item is active but map config is not loaded"
                log.error(f"❌ {error_msg}")
                log.error(f"   CV Item: {active_cv_item.name}")
                log.error(f"   Expected map: {active_cv_item.map_config_name}")
                log.info("=" * 70)
                return {"error": error_msg}

            log.info(f"✓ Map config loaded: {map_config.name}")
            departure_points = active_cv_item.departure_points
            # Attach CV item's departure points to map_config for PointNavigator
            map_config.departure_points = departure_points
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
            self._navigator = PointNavigator(map_config, loop=True)
            self._loop_counter = 0  # Reset loop counter

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

        log.info("Stopping CV-AUTO mode...")

        # Signal stop
        if self._cv_auto_stop_event:
            self._cv_auto_stop_event.set()

        # Wait for task to complete
        try:
            await asyncio.wait_for(self._cv_auto_task, timeout=3.0)
        except asyncio.TimeoutError:
            log.warning("CV-AUTO task did not stop gracefully, cancelling...")
            self._cv_auto_task.cancel()
            try:
                await self._cv_auto_task
            except asyncio.CancelledError:
                pass

        # Stop hotkey watcher
        await self._stop_cv_auto_hotkeys()

        # Cleanup
        self._cv_auto_task = None
        self._cv_auto_stop_event = None
        self._navigator = None
        self._pathfinder = None
        self._port_handler = None
        self._port_detector = None

        # Restart bridge runner to enable physical keyboard again
        log.info("Restarting bridge runner to enable physical keyboard...")
        await self.daemon._ensure_runner_started()

        # Return to BRIDGE mode
        self.daemon.mode = "BRIDGE"
        emit("MODE", mode="BRIDGE")
        emit("CV_AUTO_STOPPED")

        log.info("CV-AUTO mode stopped")
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

    async def _cv_auto_loop(self):
        """
        Main CV-AUTO mode loop.

        Continuously monitors player position and triggers rotations
        when departure points are hit. Handles navigation between points.
        """
        log.info("CV-AUTO loop starting...")

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
                    await asyncio.sleep(0.5)
                    continue

                player_data = result_dict.get("player", {})
                if not player_data.get("detected"):
                    # No player detection, wait and retry
                    await asyncio.sleep(0.5)
                    continue

                player_pos = (player_data.get("x"), player_data.get("y"))
                current_time = asyncio.get_event_loop().time()

                # Check for port/teleport
                if self._port_detector.check_port(player_pos, current_time):
                    log.warning("Port/teleport detected, resetting navigator...")
                    self._navigator.reset()
                    self._port_detector.reset()
                    emit("CV_AUTO_PORT_DETECTED")
                    await asyncio.sleep(1.0)  # Wait for player to stabilize
                    continue

                self._port_detector.update_position(player_pos, current_time)

                # Get current target point
                current_point = self._navigator.get_current_point()

                # Check if player hit current point
                if current_point.check_hit(player_pos[0], player_pos[1]):
                    log.info(f"Player hit departure point '{current_point.name}'!")
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

                    # Advance to next point
                    current_index = self._navigator.get_state().current_point_index
                    has_next = self._navigator.advance()
                    next_index = self._navigator.get_state().current_point_index

                    # Check if we completed a cycle (looped back to first point)
                    if next_index == 0 and current_index > 0:
                        self._loop_counter += 1
                        log.info(f"Completed cycle {self._loop_counter}/{self._loop}")

                        # Check if we've completed all desired loops
                        if self._loop_counter >= self._loop:
                            log.info(f"Completed {self._loop} loop(s), stopping CV-AUTO")
                            await self._stop_cv_auto(f"Completed {self._loop} loop cycles")
                            break

                    next_point = self._navigator.get_current_point()
                    log.info(f"Advanced to next point: '{next_point.name}'")

                    # Navigate to next point and wait until player hits it
                    await asyncio.sleep(0.5)  # Brief pause after rotation

                    # Keep navigating until player hits the departure point
                    from ..cv.capture import get_capture_instance
                    max_navigation_attempts = 20  # Prevent infinite loops
                    navigation_attempt = 0

                    while navigation_attempt < max_navigation_attempts:
                        # Get current player position
                        capture = get_capture_instance()
                        current_result = capture.get_last_detection_result()
                        player_data = current_result.get("player", {})
                        current_pos = (player_data.get("x"), player_data.get("y"))

                        # Check if player has hit the next departure point
                        if next_point.check_hit(current_pos[0], current_pos[1]):
                            log.info(f"Player reached next departure point '{next_point.name}'")
                            break

                        # Player hasn't hit the point yet, continue navigating
                        navigation_attempt += 1
                        log.debug(f"Player not at '{next_point.name}' yet (attempt {navigation_attempt}/{max_navigation_attempts}), navigating...")
                        self._cv_auto_state = "pathfinding"

                        await self._navigate_to_point(next_point)
                        await asyncio.sleep(0.5)

                    if navigation_attempt >= max_navigation_attempts:
                        log.warning(f"Failed to reach '{next_point.name}' after {max_navigation_attempts} attempts, continuing...")

                else:
                    # Not at current point, try to navigate there
                    self._cv_auto_state = "navigating"
                    await self._navigate_to_point(current_point)

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

                # Wait before next iteration
                await asyncio.sleep(0.5)

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

            # Construct full path to rotation file
            if Path(rotation_path).is_absolute():
                full_path = rotation_path
            else:
                # Relative path - resolve from records directory
                full_path = SETTINGS.record_dir / rotation_path

            hid_path = self.daemon.hid_path if hasattr(self.daemon, 'hid_path') else "/dev/hidg0"
            player = Player(hid_path)

            # Create or reuse SkillInjector if active_skills configured
            skill_injector = self.daemon._get_or_create_skill_injector(
                getattr(self, '_active_skills', [])
            )

            success = await player.play(
                path=full_path,
                speed=self._speed,
                jitter_time=self._jitter_time,
                jitter_hold=self._jitter_hold,
                loop=1,  # Play once (not False)
                stop_event=self._cv_auto_stop_event,
                ignore_keys=[],
                ignore_tolerance=0,
                skill_injector=skill_injector  # Use SkillInjector for CD skill casting
            )
            return success
        except Exception as e:
            log.error(f"Rotation playback error: {e}", exc_info=True)
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
        log.debug("CV-AUTO hotkeys watcher starting (mode=%s, stop_event=%s)",
                  self.daemon.mode, self._cv_auto_stop_event is not None)

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
            log.debug("CV-AUTO hotkeys: Successfully opened device %s", evdev_path)
        except Exception as e:
            log.warning("CV-AUTO hotkeys: cannot open %s: %s", evdev_path, e)
            return

        log.debug("CV-AUTO hotkeys watcher running (stop=%s)", stop_spec)

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

                if val == 1:
                    log.debug("CV-AUTO watcher: key DOWN code=%d", code)
                elif val == 0:
                    log.debug("CV-AUTO watcher: key UP code=%d", code)

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
