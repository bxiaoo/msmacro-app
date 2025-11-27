"""
Auto-pathfinding system for CV-based navigation.

Provides 3-tier pathfinding strategies:
1. Simple Directional: Basic arrow key movement for short distances
2. Recorded Pathfinding: Pre-recorded movement sequences for complex routes
3. Waypoint-based: A* algorithm for advanced navigation (future enhancement)
"""

import asyncio
import json
import logging
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from ..io.platform_abstraction import ecodes
from msmacro.cv.map_config import DeparturePoint
from msmacro.utils.keymap import HID_USAGE, NAME_TO_ECODE

logger = logging.getLogger(__name__)


class KeystrokeMapper:
    """
    Utility to convert key names to HID usage IDs.

    Handles various key name formats:
    - Single letters: 'Q', 'A', 'Z'
    - Special keys: 'ALT', 'SPACE', 'ENTER'
    - Arrow keys: 'UP', 'DOWN', 'LEFT', 'RIGHT'
    """

    # Additional arrow key mappings (uppercase and lowercase)
    ARROW_KEYS = {
        'UP': ecodes.KEY_UP,
        'DOWN': ecodes.KEY_DOWN,
        'LEFT': ecodes.KEY_LEFT,
        'RIGHT': ecodes.KEY_RIGHT,
        'up': ecodes.KEY_UP,
        'down': ecodes.KEY_DOWN,
        'left': ecodes.KEY_LEFT,
        'right': ecodes.KEY_RIGHT,
    }

    def key_name_to_usage_id(self, key_name: str) -> Optional[int]:
        """
        Convert a key name to HID usage ID.

        Args:
            key_name: Key name (e.g., 'Q', 'ALT', 'SPACE', 'UP')

        Returns:
            HID usage ID (int) or None if not found
        """
        if not key_name:
            return None

        # Try uppercase conversion first for NAME_TO_ECODE
        key_upper = key_name.upper()

        # Check arrow keys first (special case)
        if key_name in self.ARROW_KEYS:
            ecode = self.ARROW_KEYS[key_name]
            return HID_USAGE.get(ecode)

        # Check NAME_TO_ECODE mapping
        ecode = NAME_TO_ECODE.get(key_upper)
        if ecode:
            return HID_USAGE.get(ecode)

        # Try original case
        ecode = NAME_TO_ECODE.get(key_name)
        if ecode:
            return HID_USAGE.get(ecode)

        logger.warning(f"KeystrokeMapper: Unknown key name '{key_name}'")
        return None


class HumanlikeTimer:
    """
    Utility to add humanlike timing jitter to key press durations and delays.

    Applies ±10% variation to base timings to simulate natural human input.
    """

    JITTER_VARIATION = 0.1  # ±10% variation

    @staticmethod
    def jitter(base_duration: float, variation: float = JITTER_VARIATION) -> float:
        """
        Add random jitter to a base duration.

        Args:
            base_duration: Base duration in seconds
            variation: Variation percentage (default: 0.1 for ±10%)

        Returns:
            Duration with jitter applied (base * (1 ± variation))
        """
        if base_duration <= 0:
            return base_duration

        # Calculate jitter range
        jitter_amount = base_duration * variation
        min_duration = base_duration - jitter_amount
        max_duration = base_duration + jitter_amount

        # Return random value in range
        return random.uniform(min_duration, max_duration)

    @staticmethod
    def random_gap(min_gap: float, max_gap: float) -> float:
        """
        Generate a random gap duration within a range.

        Args:
            min_gap: Minimum gap duration in seconds
            max_gap: Maximum gap duration in seconds

        Returns:
            Random duration between min_gap and max_gap
        """
        return random.uniform(min_gap, max_gap)


@dataclass
class KeyAction:
    """
    Represents a single key press action.

    Attributes:
        key: Key name (e.g., "up", "down", "left", "right")
        duration: How long to hold the key (seconds)
        delay_after: Wait time after releasing key (seconds)
    """
    key: str
    duration: float = 0.1
    delay_after: float = 0.1


class PathfindingStrategy(ABC):
    """Abstract base class for pathfinding strategies."""

    @abstractmethod
    async def navigate(
        self,
        current_pos: Tuple[int, int],
        target_point: DeparturePoint,
        hid_writer,
        position_getter
    ) -> bool:
        """
        Navigate from current position to target departure point.

        Args:
            current_pos: Current (x, y) player position
            target_point: Target departure point
            hid_writer: HIDWriter instance for sending keystrokes
            position_getter: Async callable that returns current player position

        Returns:
            True if successfully reached target, False otherwise
        """
        pass


class SimplePathfinder(PathfindingStrategy):
    """
    Simple directional pathfinding using arrow keys.

    Best for short distances (<20 pixels) where direct movement works.
    Calculates direction based on delta X/Y and sends arrow key presses.
    """

    MAX_ATTEMPTS = 5
    MOVE_DURATION = 0.1  # How long to hold arrow key
    CHECK_INTERVAL = 0.3  # How long to wait before checking position

    async def navigate(
        self,
        current_pos: Tuple[int, int],
        target_point: DeparturePoint,
        hid_writer,
        position_getter
    ) -> bool:
        """
        Navigate using simple directional movement.

        Strategy:
        1. Calculate delta X and Y
        2. Press arrow keys in the direction needed
        3. Check if target reached
        4. Repeat up to MAX_ATTEMPTS times
        """
        logger.info(
            f"SimplePathfinder: Navigating from ({current_pos[0]}, {current_pos[1]}) "
            f"to point '{target_point.name}' at ({target_point.x}, {target_point.y})"
        )

        for attempt in range(self.MAX_ATTEMPTS):
            # Check if already at target
            if target_point.check_hit(current_pos[0], current_pos[1]):
                logger.info(f"SimplePathfinder: Target reached in {attempt} attempts")
                return True

            # Calculate deltas
            dx = target_point.x - current_pos[0]
            dy = target_point.y - current_pos[1]
            distance = math.sqrt(dx**2 + dy**2)

            logger.debug(
                f"SimplePathfinder: Attempt {attempt + 1}/{self.MAX_ATTEMPTS} - "
                f"distance={distance:.1f}px, dx={dx}, dy={dy}"
            )

            # Generate movement actions
            actions = self._generate_movement_actions(dx, dy, distance)

            # Execute actions
            for action in actions:
                await self._execute_key_action(action, hid_writer)

            # Wait before checking position
            await asyncio.sleep(self.CHECK_INTERVAL)

            # Get new position
            new_pos = await position_getter()
            if not new_pos:
                logger.warning("SimplePathfinder: Failed to get player position")
                continue

            current_pos = new_pos

        logger.warning(
            f"SimplePathfinder: Failed to reach target after {self.MAX_ATTEMPTS} attempts"
        )
        return False

    def _generate_movement_actions(
        self,
        dx: int,
        dy: int,
        distance: float
    ) -> List[KeyAction]:
        """
        Generate arrow key actions based on delta X/Y.

        Prioritizes the axis with larger delta.
        """
        actions = []

        # Scale duration based on distance (but cap it)
        duration = min(0.3, self.MOVE_DURATION + distance / 200)

        # Move horizontally if needed
        if abs(dx) > 5:  # Tolerance threshold
            key = "right" if dx > 0 else "left"
            actions.append(KeyAction(key, duration=duration, delay_after=0.05))

        # Move vertically if needed
        if abs(dy) > 5:
            key = "down" if dy > 0 else "up"
            actions.append(KeyAction(key, duration=duration, delay_after=0.05))

        return actions

    async def _execute_key_action(self, action: KeyAction, hid_writer):
        """Execute a single key press action."""
        # Map arrow key names to HID usage IDs
        key_map = {
            "up": 0x52,      # Up Arrow
            "down": 0x51,    # Down Arrow
            "left": 0x50,    # Left Arrow
            "right": 0x4F    # Right Arrow
        }

        usage_id = key_map.get(action.key)
        if not usage_id:
            logger.warning(f"Unknown key: {action.key}")
            return

        logger.debug(f"Pressing {action.key} for {action.duration}s")

        # Press key
        await hid_writer.press(usage_id)
        await asyncio.sleep(action.duration)

        # Release key
        await hid_writer.release(usage_id)
        await asyncio.sleep(action.delay_after)


class RecordedPathfinder(PathfindingStrategy):
    """
    Pathfinding using pre-recorded movement sequences.

    Best for complex routes that require specific navigation (e.g., rope climb,
    double jump, portal use). Reuses the rotation JSON format with type="pathfinding".
    """

    def __init__(self, sequence_path: str):
        """
        Initialize recorded pathfinder.

        Args:
            sequence_path: Path to recorded movement sequence JSON file
        """
        self.sequence_path = Path(sequence_path)

    async def navigate(
        self,
        current_pos: Tuple[int, int],
        target_point: DeparturePoint,
        hid_writer,
        position_getter
    ) -> bool:
        """
        Navigate by replaying a pre-recorded movement sequence.

        Strategy:
        1. Load recorded actions from JSON
        2. Play back the sequence (similar to rotation playback)
        3. Check if target reached
        """
        logger.info(
            f"RecordedPathfinder: Playing sequence '{self.sequence_path}' "
            f"to reach point '{target_point.name}'"
        )

        # Load sequence
        try:
            actions = self._load_sequence()
        except Exception as e:
            logger.error(f"Failed to load pathfinding sequence: {e}")
            return False

        # Play sequence
        try:
            await self._play_sequence(actions, hid_writer)
        except Exception as e:
            logger.error(f"Failed to play pathfinding sequence: {e}")
            return False

        # Wait a bit for movement to complete
        await asyncio.sleep(0.3)

        # Check if target reached
        final_pos = await position_getter()
        if final_pos and target_point.check_hit(final_pos[0], final_pos[1]):
            logger.info("RecordedPathfinder: Target reached successfully")
            return True

        logger.warning("RecordedPathfinder: Sequence completed but target not reached")
        return False

    def _load_sequence(self) -> List[dict]:
        """
        Load movement sequence from JSON file.

        Expected format (same as rotation):
        {
            "t0": 0.0,
            "actions": [
                {"usage": 30, "press": 0.5, "dur": 0.123},
                ...
            ],
            "metadata": {
                "type": "pathfinding",
                "map_name": "...",
                ...
            }
        }
        """
        if not self.sequence_path.exists():
            raise FileNotFoundError(f"Sequence file not found: {self.sequence_path}")

        with open(self.sequence_path, 'r') as f:
            data = json.load(f)

        actions = data.get('actions', [])
        if not actions:
            raise ValueError(f"No actions found in sequence: {self.sequence_path}")

        logger.info(f"Loaded {len(actions)} actions from sequence")
        return actions

    async def _play_sequence(self, actions: List[dict], hid_writer):
        """
        Play back the recorded action sequence.

        This is a simplified version of Player.play() focused on movement.
        """
        if not actions:
            return

        start_time = asyncio.get_event_loop().time()
        t0 = actions[0]['press']

        for action in actions:
            usage = action['usage']
            press_time = action['press']
            duration = action['dur']

            # Calculate when to press this key
            target_time = start_time + (press_time - t0)
            now = asyncio.get_event_loop().time()
            wait_time = target_time - now

            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # Press key
            await hid_writer.press(usage)

            # Hold for duration
            await asyncio.sleep(duration)

            # Release key
            await hid_writer.release(usage)


class ClassBasedPathfinder(PathfindingStrategy):
    """
    Class-based pathfinding using character-specific movement strategies.

    Supports two class types:
    - "other": Standard classes with jump, rope lift, diagonal movement skills
    - "magician": Mage classes with teleport-based movement

    Uses humanlike timing jitter for natural movement simulation.
    """

    # Constants
    LARGE_DISTANCE_THRESHOLD_X = 24  # pixels (threshold for using double jump on X-axis)
    LARGE_DISTANCE_THRESHOLD_Y = 38  # pixels (threshold for using double jump on Y-axis)
    SMALL_Y_TOLERANCE = 3  # pixels (threshold for fine vertical adjustments with up/down arrow)
    JUMP_DURATION_BASE = 0.15  # Base duration for jump key press
    ARROW_DURATION_BASE = 0.15  # Base duration for arrow key press
    DOUBLE_JUMP_GAP_MIN = 0.3  # Minimum gap between double jump presses
    DOUBLE_JUMP_GAP_MAX = 0.5  # Maximum gap between double jump presses
    MAX_TOLERANCE = 5  # Position tolerance in pixels

    # HID usage IDs for arrow keys (directional input only)
    ARROW_UP = 0x52
    ARROW_DOWN = 0x51
    ARROW_LEFT = 0x50
    ARROW_RIGHT = 0x4F

    def __init__(self, pathfinding_config: Dict[str, Any], jump_key: int = 44):
        """
        Initialize class-based pathfinder.

        Args:
            pathfinding_config: Dictionary containing:
                - class_type: "other" or "magician"
                - rope_lift_key: Key name for rope lift (optional)
                - diagonal_movement_key: Key name for diagonal skill (other class only)
                - double_jump_up_allowed: Bool for double jump UP (other class, default True)
                - y_axis_jump_skill: Key name for Y-axis jump (other class only)
                - teleport_skill: Key name for teleport (magician class only)
            jump_key: HID usage ID for jump key (default: 44 for SPACE)
        """
        self.config = pathfinding_config or {}
        self.class_type = self.config.get('class_type', 'other')
        self.mapper = KeystrokeMapper()
        self.timer = HumanlikeTimer()
        self.jump_key = jump_key  # Configurable jump key

        # Parse configuration keys
        self.rope_lift_key = self._parse_key(self.config.get('rope_lift_key'))
        self.diagonal_movement_key = self._parse_key(self.config.get('diagonal_movement_key'))
        self.double_jump_up_allowed = self.config.get('double_jump_up_allowed', True)
        self.y_axis_jump_skill = self._parse_key(self.config.get('y_axis_jump_skill'))
        self.teleport_skill = self._parse_key(self.config.get('teleport_skill'))

        logger.info(
            f"ClassBasedPathfinder initialized: class_type={self.class_type}, "
            f"jump_key={self.jump_key}, "
            f"rope_lift={self.rope_lift_key is not None}, "
            f"diagonal={self.diagonal_movement_key is not None}, "
            f"teleport={self.teleport_skill is not None}"
        )

    def _parse_key(self, key_name: Optional[str]) -> Optional[int]:
        """Convert key name to HID usage ID."""
        if not key_name:
            return None
        return self.mapper.key_name_to_usage_id(key_name)

    async def navigate(
        self,
        current_pos: Tuple[int, int],
        target_point: DeparturePoint,
        hid_writer,
        position_getter
    ) -> bool:
        """
        Navigate from current position to target departure point.

        Routes to class-specific navigation method.
        """
        logger.info(
            f"ClassBasedPathfinder ({self.class_type}): Navigating from "
            f"({current_pos[0]}, {current_pos[1]}) to '{target_point.name}' "
            f"at ({target_point.x}, {target_point.y})"
        )

        # Route to class-specific method
        if self.class_type == 'magician':
            return await self._navigate_magician(
                current_pos, target_point, hid_writer, position_getter
            )
        else:
            return await self._navigate_other_class(
                current_pos, target_point, hid_writer, position_getter
            )

    async def _navigate_other_class(
        self,
        current_pos: Tuple[int, int],
        target_point: DeparturePoint,
        hid_writer,
        position_getter
    ) -> bool:
        """
        Navigate using "other class" movement logic with X-first, Y-second priority.

        Strategy (ALWAYS align X-axis first, then Y-axis):
        - X diff > 45px: Double jump + arrow key
        - X diff <= 45px: Regular arrow key movement
        - After X aligned:
          - Y diff > 40px: Use double jump (if allowed) or Y-axis jump skill
          - Player Y < target Y: Down arrow + jump (need to go down)
          - Y diff <= 40px: Use simple pathfinding
        """
        dx = target_point.x - current_pos[0]
        dy = target_point.y - current_pos[1]
        distance = math.sqrt(dx**2 + dy**2)

        logger.debug(f"Other class navigation: dx={dx}, dy={dy}, distance={distance:.1f}px")

        # Check if already at target
        if target_point.check_hit(current_pos[0], current_pos[1]):
            logger.info("Already at target position")
            return True

        # STEP 1: Align X-axis FIRST (priority)
        x_ok = abs(dx) <= self.MAX_TOLERANCE
        if not x_ok:
            logger.debug("X-axis not aligned, moving horizontally first")
            return await self._move_horizontal_other(
                dx, target_point, hid_writer, position_getter
            )

        # STEP 2: X-axis aligned, now align Y-axis
        y_ok = abs(dy) <= self.MAX_TOLERANCE
        if not y_ok:
            logger.debug("X-axis aligned, now moving vertically")
            return await self._move_vertical_other(
                dy, target_point, hid_writer, position_getter
            )

        return True

    async def _navigate_magician(
        self,
        current_pos: Tuple[int, int],
        target_point: DeparturePoint,
        hid_writer,
        position_getter
    ) -> bool:
        """
        Navigate using "magician class" movement logic with X-first, Y-second priority.

        Strategy (ALWAYS align X-axis first, then Y-axis):
        - X diff > 45px: Arrow key + Teleport skill + Release arrow
        - X diff <= 45px: Use simple pathfinding
        - After X aligned:
          - Y diff > 40px:
            * Player under target: Jump + Up + Teleport + Release Up
            * Player above target: Down + Wait(0.2-0.4s) + Teleport + Release Down
          - Y diff <= 40px: Use simple pathfinding
        """
        dx = target_point.x - current_pos[0]
        dy = target_point.y - current_pos[1]
        distance = math.sqrt(dx**2 + dy**2)

        logger.debug(f"Magician navigation: dx={dx}, dy={dy}, distance={distance:.1f}px")

        # Check if already at target
        if target_point.check_hit(current_pos[0], current_pos[1]):
            logger.info("Already at target position")
            return True

        # STEP 1: Align X-axis FIRST (priority)
        x_ok = abs(dx) <= self.MAX_TOLERANCE
        if not x_ok:
            logger.debug("X-axis not aligned, moving horizontally first")
            await self._move_horizontal_magician(dx, hid_writer)
            # Re-check position after movement
            final_pos = await position_getter()
            if final_pos and target_point.check_hit(final_pos[0], final_pos[1]):
                logger.info("Magician pathfinding: Target reached after horizontal movement")
                return True
            return False

        # STEP 2: X-axis aligned, now align Y-axis
        y_ok = abs(dy) <= self.MAX_TOLERANCE
        if not y_ok:
            logger.debug("X-axis aligned, now moving vertically")
            await self._move_vertical_magician(dy, hid_writer)

        # Final position check (wait already done inside movement method)
        final_pos = await position_getter()
        if final_pos and target_point.check_hit(final_pos[0], final_pos[1]):
            logger.info("Magician pathfinding: Target reached")
            return True

        logger.warning("Magician pathfinding: Target not reached")
        return False

    # ========== Other Class Movement Methods ==========

    async def _move_horizontal_other(
        self,
        dx: int,
        target_point: DeparturePoint,
        hid_writer,
        position_getter
    ) -> bool:
        """Handle horizontal movement for other class (X-axis alignment)."""
        distance = abs(dx)
        arrow_key = self.ARROW_RIGHT if dx > 0 else self.ARROW_LEFT

        if distance > self.LARGE_DISTANCE_THRESHOLD_X:
            # Large distance (>24px): Arrow + double jump
            logger.debug(f"Large horizontal movement: {distance}px, using double jump")
            await self._double_jump_horizontal(arrow_key, hid_writer)
            movement_type = 'double_jump'
        else:
            # Small distance (<=24px): Regular arrow key press
            duration = self._calculate_timed_duration(distance)
            logger.debug(f"Small horizontal movement: {distance}px, duration={duration:.2f}s")
            await self._press_key_timed(arrow_key, duration, hid_writer)
            movement_type = 'double_jump'  # Use same wait time scaling

        # Dynamic wait time based on distance
        wait_time = self._calculate_wait_time(distance, movement_type)
        await asyncio.sleep(wait_time)
        final_pos = await position_getter()
        if final_pos and target_point.check_hit(final_pos[0], final_pos[1]):
            return True
        return False

    async def _move_vertical_other(
        self,
        dy: int,
        target_point: DeparturePoint,
        hid_writer,
        position_getter
    ) -> bool:
        """Handle vertical movement for other class (X-axis already aligned)."""
        distance_y = abs(dy)
        movement_type = None  # Track movement type for dynamic wait time

        # Step 1: Try fine adjustment for very small distances (<3px)
        if distance_y < self.SMALL_Y_TOLERANCE:
            logger.debug(f"Very small Y distance ({distance_y}px < 3px), trying fine adjustment")
            await self._fine_adjust_vertical(dy, hid_writer)
            movement_type = 'fine_adjust'
        elif dy < 0:
            # Player is below target (player Y > target Y) - move UP
            logger.debug(f"Vertical UP movement: {distance_y}px")

            if distance_y > self.LARGE_DISTANCE_THRESHOLD_Y:
                # Large distance (>38px): Use rope lift
                if self.rope_lift_key:
                    logger.debug(f"Large UP distance ({distance_y}px > 38px), using rope lift")
                    await self._execute_rope_lift(hid_writer)
                    movement_type = 'rope_lift'
                elif self.y_axis_jump_skill:
                    logger.debug(f"Large UP distance ({distance_y}px > 38px), using Y-axis jump skill (fallback)")
                    await self._y_axis_jump(hid_writer)
                    movement_type = 'y_axis_jump'
                else:
                    logger.warning("No vertical UP movement configured for large distances")
                    return False
            else:
                # Small distance (<=38px): Use double jump up
                logger.debug(f"Small UP distance ({distance_y}px <= 38px), using double jump")
                if self.double_jump_up_allowed:
                    await self._double_jump_up(distance_y, hid_writer)
                    movement_type = 'double_jump'
                elif self.y_axis_jump_skill:
                    await self._y_axis_jump(hid_writer)
                    movement_type = 'y_axis_jump'
                else:
                    logger.warning("No vertical UP movement configured for small distances")
                    return False
        else:
            # Player is above target (player Y < target Y) - move DOWN
            logger.debug(f"Vertical DOWN movement: {distance_y}px, using down arrow + jump")
            await self._jump_down(hid_writer)
            movement_type = 'jump_down'

        # Dynamic wait time based on movement type and distance
        if movement_type == 'rope_lift':
            wait_time = self._calculate_wait_time(distance_y, 'rope_lift')
        elif movement_type in ['double_jump', 'y_axis_jump', 'jump_down']:
            wait_time = self._calculate_wait_time(distance_y, 'double_jump')
        else:
            # Fine adjustment or unknown - use shorter wait
            wait_time = random.uniform(0.5, 0.8)

        await asyncio.sleep(wait_time)
        final_pos = await position_getter()
        if final_pos and target_point.check_hit(final_pos[0], final_pos[1]):
            return True
        return False

    async def _move_diagonal_other(
        self,
        dx: int,
        dy: int,
        target_point: DeparturePoint,
        hid_writer,
        position_getter
    ) -> bool:
        """Handle diagonal movement for other class."""
        logger.debug(f"Diagonal movement: dx={dx}, dy={dy}")

        if dy < 0 and self.diagonal_movement_key:
            # Player is lower than target and diagonal skill available
            arrow_key = self.ARROW_RIGHT if dx > 0 else self.ARROW_LEFT
            await self._diagonal_jump_with_skill(arrow_key, hid_writer)
        elif dy > 0:
            # Player is higher than target - do X first, then Y
            await self._move_horizontal_other(dx, target_point, hid_writer, position_getter)
            await asyncio.sleep(1.3)
            new_pos = await position_getter()
            if new_pos:
                dy_new = target_point.y - new_pos[1]
                if abs(dy_new) > self.MAX_TOLERANCE:
                    await self._move_vertical_other(dy_new, target_point, hid_writer, position_getter)
        else:
            # No diagonal skill - do larger axis first
            if abs(dx) > abs(dy):
                await self._move_horizontal_other(dx, target_point, hid_writer, position_getter)
                await asyncio.sleep(1.3)
                new_pos = await position_getter()
                if new_pos:
                    dy_new = target_point.y - new_pos[1]
                    if abs(dy_new) > self.MAX_TOLERANCE:
                        await self._move_vertical_other(dy_new, target_point, hid_writer, position_getter)
            else:
                await self._move_vertical_other(dy, target_point, hid_writer, position_getter)
                await asyncio.sleep(random.uniform(0.9, 1.3))
                new_pos = await position_getter()
                if new_pos:
                    dx_new = target_point.x - new_pos[0]
                    if abs(dx_new) > self.MAX_TOLERANCE:
                        await self._move_horizontal_other(dx_new, target_point, hid_writer, position_getter)

        # Final check (wait optimized for improved detection rate)
        await asyncio.sleep(random.uniform(1.1, 1.5))
        final_pos = await position_getter()
        if final_pos and target_point.check_hit(final_pos[0], final_pos[1]):
            return True
        return False

    # ========== Magician Class Movement Methods ==========

    async def _move_horizontal_magician(self, dx: int, hid_writer):
        """Handle horizontal movement for magician class (X-axis alignment)."""
        distance = abs(dx)
        arrow_key = self.ARROW_RIGHT if dx > 0 else self.ARROW_LEFT

        if distance > self.LARGE_DISTANCE_THRESHOLD_X:
            # Large distance (>24px): Arrow press + Teleport + Release arrow
            if self.teleport_skill:
                logger.debug(f"Magician horizontal (teleport): {distance}px > 24px")
                # Step 1: Press arrow key
                await hid_writer.press(arrow_key)
                # Step 2: Press and release Teleport skill (humanlike duration)
                await asyncio.sleep(random.uniform(0.05, 0.15))
                await self._press_key(self.teleport_skill, hid_writer)
                # Step 3: Release arrow key
                await asyncio.sleep(random.uniform(0.05, 0.15))
                await hid_writer.release(arrow_key)
            else:
                logger.warning("Teleport skill not configured for large horizontal movement")
                # Fallback to timed movement
                duration = self._calculate_timed_duration(distance)
                await self._press_key_timed(arrow_key, duration, hid_writer)
        else:
            # Small distance (<=24px): Use simple pathfinding (timed arrow press)
            duration = self._calculate_timed_duration(distance)
            logger.debug(f"Magician horizontal (timed): {distance}px <= 24px, duration={duration:.2f}s")
            await self._press_key_timed(arrow_key, duration, hid_writer)

        # Dynamic wait time based on distance
        wait_time = self._calculate_wait_time(distance, 'double_jump')
        await asyncio.sleep(wait_time)

    async def _move_vertical_magician(self, dy: int, hid_writer):
        """Handle vertical movement for magician class (Y-axis alignment)."""
        distance_y = abs(dy)
        movement_type = None  # Track movement type for dynamic wait time

        # Step 1: Try fine adjustment for very small distances (<3px)
        if distance_y < self.SMALL_Y_TOLERANCE:
            logger.debug(f"Very small Y distance ({distance_y}px < 3px), trying fine adjustment")
            await self._fine_adjust_vertical(dy, hid_writer)
            movement_type = 'fine_adjust'
        elif dy < 0:
            # Player below target (player Y > target Y) - move UP
            logger.debug(f"Magician vertical UP: {distance_y}px")

            if distance_y > self.LARGE_DISTANCE_THRESHOLD_Y:
                # Large distance (>38px): Use rope lift (priority), fallback to teleport
                if self.rope_lift_key:
                    logger.debug(f"Large UP distance ({distance_y}px > 38px), using rope lift")
                    await self._execute_rope_lift(hid_writer)
                    movement_type = 'rope_lift'
                elif self.teleport_skill:
                    logger.debug(f"Large UP distance ({distance_y}px > 38px), using Jump+Up+Teleport (fallback)")
                    # Step 1: Jump key (humanlike press/release)
                    await self._press_key(self.jump_key, hid_writer)
                    # Step 2: Up key press
                    await hid_writer.press(self.ARROW_UP)
                    # Step 3: Teleport skill (humanlike press/release)
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                    await self._press_key(self.teleport_skill, hid_writer)
                    # Step 4: Release up key
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                    await hid_writer.release(self.ARROW_UP)
                    movement_type = 'double_jump'
                else:
                    logger.warning("No vertical UP movement configured for large distances")
            else:
                # Small distance (<=38px): Use Jump+Up+Teleport
                logger.debug(f"Small UP distance ({distance_y}px <= 38px), using Jump+Up+Teleport")
                if self.teleport_skill:
                    # Step 1: Jump key (humanlike press/release)
                    await self._press_key(self.jump_key, hid_writer)
                    # Step 2: Up key press
                    await hid_writer.press(self.ARROW_UP)
                    # Step 3: Teleport skill (humanlike press/release)
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                    await self._press_key(self.teleport_skill, hid_writer)
                    # Step 4: Release up key
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                    await hid_writer.release(self.ARROW_UP)
                    movement_type = 'double_jump'
                elif self.rope_lift_key:
                    await self._execute_rope_lift(hid_writer)
                    movement_type = 'rope_lift'
                else:
                    logger.warning("No vertical UP movement configured for small distances")
        else:
            # Player above target (player Y < target Y) - move DOWN
            logger.debug(f"Magician vertical DOWN: {distance_y}px")

            if distance_y > self.LARGE_DISTANCE_THRESHOLD_Y:
                # Large distance (> 38px): Down + Wait(0.2-0.4s) + Teleport + Release Down
                if self.teleport_skill:
                    logger.debug(f"Large DOWN distance ({distance_y}px > 38px), using Down+Wait+Teleport sequence")
                    # Step 1: Down key press
                    await hid_writer.press(self.ARROW_DOWN)
                    # Step 2: Wait 0.2-0.4s (randomized)
                    await asyncio.sleep(random.uniform(0.2, 0.4))
                    # Step 3: Teleport skill (humanlike press/release)
                    await self._press_key(self.teleport_skill, hid_writer)
                    # Step 4: Release down key
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                    await hid_writer.release(self.ARROW_DOWN)
                    movement_type = 'double_jump'
                else:
                    logger.warning("Teleport skill not configured for large vertical DOWN movement")
            else:
                # Small distance (<= 38px): Use simple pathfinding
                logger.debug(f"Small DOWN distance ({distance_y}px <= 38px), using simple movement")
                if self.teleport_skill:
                    # Simplified teleport for small distances
                    await hid_writer.press(self.ARROW_DOWN)
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                    await self._press_key(self.teleport_skill, hid_writer)
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                    await hid_writer.release(self.ARROW_DOWN)
                    movement_type = 'double_jump'

        # Dynamic wait time based on movement type and distance
        if movement_type == 'rope_lift':
            wait_time = self._calculate_wait_time(distance_y, 'rope_lift')
        elif movement_type == 'double_jump':
            wait_time = self._calculate_wait_time(distance_y, 'double_jump')
        else:
            # Fine adjustment or unknown - use shorter wait
            wait_time = random.uniform(0.5, 0.8)

        await asyncio.sleep(wait_time)

    # ========== Atomic Movement Primitives ==========

    async def _press_key(self, usage_id: int, hid_writer):
        """Press and release a single key with humanlike timing."""
        duration = self.timer.jitter(self.JUMP_DURATION_BASE)
        await hid_writer.press(usage_id)
        await asyncio.sleep(duration)
        await hid_writer.release(usage_id)

    async def _press_key_timed(self, usage_id: int, duration: float, hid_writer):
        """Press and hold a key for a specific duration."""
        jittered_duration = self.timer.jitter(duration)
        await hid_writer.press(usage_id)
        await asyncio.sleep(jittered_duration)
        await hid_writer.release(usage_id)

    async def _double_jump_horizontal(self, arrow_key: int, hid_writer):
        """Execute double jump with arrow key (for horizontal movement)."""
        # Press arrow
        await hid_writer.press(arrow_key)
        await asyncio.sleep(0.05)

        # First jump
        jump_duration = self.timer.jitter(self.JUMP_DURATION_BASE)
        await hid_writer.press(self.jump_key)  # Use configurable jump key
        await asyncio.sleep(jump_duration)
        await hid_writer.release(self.jump_key)

        # Gap between jumps
        gap = self.timer.random_gap(self.DOUBLE_JUMP_GAP_MIN, self.DOUBLE_JUMP_GAP_MAX)
        await asyncio.sleep(gap)

        # Second jump
        jump_duration2 = self.timer.jitter(self.JUMP_DURATION_BASE)
        await hid_writer.press(self.jump_key)
        await asyncio.sleep(jump_duration2)
        await hid_writer.release(self.jump_key)

        # Release arrow
        await asyncio.sleep(0.05)
        await hid_writer.release(arrow_key)

    async def _double_jump_up(self, distance_y: int, hid_writer):
        """Execute double jump UP (jump + up arrow + jump)."""
        # First jump
        jump_duration = self.timer.jitter(self.JUMP_DURATION_BASE)
        await hid_writer.press(self.jump_key)
        await asyncio.sleep(jump_duration)
        await hid_writer.release(self.jump_key)

        # Dynamic gap based on Y-axis distance (larger distance = shorter gap)
        # Linear interpolation: 5px=0.25s, 38px+=0.14s
        # Formula: gap = 0.25 - ((distance - 5) / 33) * 0.11
        base_gap = 0.25 - ((distance_y - 5) / 33.0) * 0.11
        base_gap = max(0.14, min(0.25, base_gap))  # Clamp to [0.14, 0.25]
        gap = self.timer.jitter(base_gap)
        await asyncio.sleep(gap)

        # Press up arrow (directional input)
        await hid_writer.press(self.ARROW_UP)
        await asyncio.sleep(0.05)

        # Second jump while holding up
        jump_duration2 = self.timer.jitter(self.JUMP_DURATION_BASE)
        await hid_writer.press(self.jump_key)  # Use configurable jump key
        await asyncio.sleep(jump_duration2)
        await hid_writer.release(self.jump_key)

        # Release up arrow (directional input)
        await asyncio.sleep(0.05)
        await hid_writer.release(self.ARROW_UP)

    async def _y_axis_jump(self, hid_writer):
        """Execute Y-axis jump skill (jump + wait + skill)."""
        # Jump first
        jump_duration = self.timer.jitter(self.JUMP_DURATION_BASE)
        await hid_writer.press(self.jump_key)
        await asyncio.sleep(jump_duration)
        await hid_writer.release(self.jump_key)

        # Wait
        wait_time = self.timer.random_gap(0.1, 0.3)
        await asyncio.sleep(wait_time)

        # Execute skill
        skill_duration = self.timer.jitter(self.JUMP_DURATION_BASE)
        await hid_writer.press(self.y_axis_jump_skill)
        await asyncio.sleep(skill_duration)
        await hid_writer.release(self.y_axis_jump_skill)

    async def _jump_down(self, hid_writer):
        """Execute jump down (down arrow + jump + release)."""
        # Press down
        await hid_writer.press(self.ARROW_DOWN)
        await asyncio.sleep(0.05)

        # Jump
        jump_duration = self.timer.jitter(self.JUMP_DURATION_BASE)
        await hid_writer.press(self.jump_key)
        await asyncio.sleep(jump_duration)
        await hid_writer.release(self.jump_key)

        # Release down (within 0.3s after jump released)
        release_delay = self.timer.jitter(0.2)
        release_delay = min(release_delay, 0.3)
        await asyncio.sleep(release_delay)
        await hid_writer.release(self.ARROW_DOWN)

    async def _diagonal_jump_with_skill(self, arrow_key: int, hid_writer):
        """Execute diagonal jump with skill (arrow + jump + up + skill + release)."""
        # Press arrow
        await hid_writer.press(arrow_key)
        await asyncio.sleep(0.05)

        # Jump
        jump_duration = self.timer.jitter(self.JUMP_DURATION_BASE)
        await hid_writer.press(self.jump_key)
        await asyncio.sleep(jump_duration)
        await hid_writer.release(self.jump_key)

        # Press up (directional input)
        await asyncio.sleep(0.05)
        await hid_writer.press(self.ARROW_UP)
        await asyncio.sleep(0.05)

        # Execute diagonal skill
        skill_duration = self.timer.jitter(self.JUMP_DURATION_BASE)
        await hid_writer.press(self.diagonal_movement_key)
        await asyncio.sleep(skill_duration)
        await hid_writer.release(self.diagonal_movement_key)

        # Release all keys together
        await asyncio.sleep(0.05)
        await hid_writer.release(arrow_key)
        await hid_writer.release(self.ARROW_UP)

    async def _execute_rope_lift(self, hid_writer):
        """Execute rope lift keystroke."""
        rope_duration = self.timer.jitter(0.2)
        await hid_writer.press(self.rope_lift_key)
        await asyncio.sleep(rope_duration)
        await hid_writer.release(self.rope_lift_key)

    def _calculate_wait_time(self, distance: int, movement_type: str) -> float:
        """
        Calculate dynamic wait time after movement based on distance and movement type.

        Args:
            distance: Distance traveled in pixels
            movement_type: Type of movement ('rope_lift' or 'double_jump')

        Returns:
            Wait time in seconds with linear scaling based on distance
        """
        if movement_type == 'rope_lift':
            # Rope lift: 1.5s at small distances → 2.0s at large distances (38px)
            min_wait = 1.5
            max_wait = 2.0
            max_distance = 38
        elif movement_type == 'double_jump':
            # Double jump: 0.9s at small distances → 1.3s at large distances
            min_wait = 0.9
            max_wait = 1.3
            max_distance = 38  # Use Y-axis threshold as reference
        else:
            # Default wait time for unknown movement types
            return 1.0

        # Linear interpolation from min to max based on distance
        # Clamp distance to range [5, max_distance]
        distance = max(5, min(distance, max_distance))

        # Calculate interpolated wait time
        if max_distance > 5:
            ratio = (distance - 5) / (max_distance - 5)
            wait_time = min_wait + ratio * (max_wait - min_wait)
        else:
            wait_time = min_wait

        return wait_time

    async def _fine_adjust_vertical(self, dy: int, hid_writer) -> bool:
        """
        Perform fine vertical adjustment for small Y-axis differences (<3px).

        Args:
            dy: Vertical distance (negative = move up, positive = move down)
            hid_writer: HIDWriter instance

        Returns:
            True if fine adjustment was performed, False otherwise
        """
        distance_y = abs(dy)

        # Only perform fine adjustment if distance is very small
        if distance_y >= self.SMALL_Y_TOLERANCE:
            return False

        # Determine direction
        arrow_key = self.ARROW_UP if dy < 0 else self.ARROW_DOWN

        # Short press duration (0.1-0.15s with jitter)
        duration = self.timer.jitter(random.uniform(0.1, 0.15))

        logger.debug(f"Fine vertical adjustment: {distance_y}px, direction={'UP' if dy < 0 else 'DOWN'}")

        # Execute short arrow press
        await hid_writer.press(arrow_key)
        await asyncio.sleep(duration)
        await hid_writer.release(arrow_key)

        return True

    def _calculate_timed_duration(self, distance: int) -> float:
        """
        Calculate timed arrow press duration based on distance.

        Linear interpolation:
        - 1px = 0.12s
        - 50px = 2.0s
        """
        if distance <= 0:
            return 0.12

        # Linear interpolation: duration = 0.12 + (distance - 1) * slope
        slope = (2.0 - 0.12) / (50 - 1)
        duration = 0.12 + (distance - 1) * slope
        return min(duration, 2.0)  # Cap at 2.0s


class PathfindingController:
    """
    High-level pathfinding controller that selects the appropriate strategy.

    Chooses between ClassBased, Recorded, and Simple (legacy) strategies based on:
    - Whether pathfinding_config is available
    - Whether a recorded sequence is available
    - Distance to target (for legacy mode)
    """

    SIMPLE_DISTANCE_THRESHOLD = 50  # Use simple pathfinding for < 50px (legacy)

    def __init__(self, hid_writer, position_getter, pathfinding_config: Optional[Dict[str, Any]] = None, jump_key: int = 44):
        """
        Initialize pathfinding controller.

        Args:
            hid_writer: HIDWriter instance for sending keystrokes
            position_getter: Async callable that returns current (x, y) position
            pathfinding_config: Optional pathfinding configuration from CV Item
            jump_key: HID usage ID for jump key (default: 44 for SPACE)
        """
        self.hid_writer = hid_writer
        self.position_getter = position_getter
        self.pathfinding_config = pathfinding_config or {}
        self.jump_key = jump_key

    async def navigate_to(
        self,
        current_pos: Tuple[int, int],
        target_point: DeparturePoint
    ) -> bool:
        """
        Navigate to target point using the best available strategy.

        Strategy selection:
        1. If target_point.pathfinding_sequence is set → Use RecordedPathfinder
        2. If distance < 50px → Use SimplePathfinder
        3. Otherwise → Use SimplePathfinder as fallback

        Args:
            current_pos: Current (x, y) player position
            target_point: Target departure point

        Returns:
            True if successfully reached target, False otherwise
        """
        # Calculate distance
        dx = target_point.x - current_pos[0]
        dy = target_point.y - current_pos[1]
        distance = math.sqrt(dx**2 + dy**2)

        logger.info(
            f"PathfindingController: Navigating to '{target_point.name}' "
            f"(distance={distance:.1f}px)"
        )

        # Select strategy
        strategy = self._select_strategy(distance, target_point)

        # Execute navigation
        success = await strategy.navigate(
            current_pos,
            target_point,
            self.hid_writer,
            self.position_getter
        )

        if success:
            logger.info(f"PathfindingController: Successfully reached '{target_point.name}'")
        else:
            logger.warning(f"PathfindingController: Failed to reach '{target_point.name}'")

        return success

    def _select_strategy(
        self,
        distance: float,
        target_point: DeparturePoint
    ) -> PathfindingStrategy:
        """
        Select the appropriate pathfinding strategy.

        Priority:
        1. Recorded sequence (if available)
        2. Class-based pathfinding (if pathfinding_config available)
        3. Simple directional (legacy fallback)
        """
        # Priority 1: Recorded sequence
        if target_point.pathfinding_sequence:
            logger.info(
                f"Using RecordedPathfinder with sequence: {target_point.pathfinding_sequence}"
            )
            return RecordedPathfinder(target_point.pathfinding_sequence)

        # Priority 2: Class-based pathfinding
        if self.pathfinding_config and self.pathfinding_config.get('class_type'):
            class_type = self.pathfinding_config.get('class_type', 'other')
            logger.info(
                f"Using ClassBasedPathfinder with class_type='{class_type}' "
                f"(distance={distance:.1f}px, jump_key={self.jump_key})"
            )
            return ClassBasedPathfinder(self.pathfinding_config, jump_key=self.jump_key)

        # Priority 3: Legacy simple directional fallback
        logger.info(
            f"Using SimplePathfinder (legacy mode) - "
            f"distance={distance:.1f}px, no pathfinding_config available"
        )
        return SimplePathfinder()
