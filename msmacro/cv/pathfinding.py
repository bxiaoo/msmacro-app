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
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional
from msmacro.cv.map_config import DeparturePoint

logger = logging.getLogger(__name__)


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

    Best for short distances (<50 pixels) where direct movement works.
    Calculates direction based on delta X/Y and sends arrow key presses.
    """

    MAX_ATTEMPTS = 10
    MOVE_DURATION = 0.15  # How long to hold arrow key
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
        await asyncio.sleep(0.5)

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


class PathfindingController:
    """
    High-level pathfinding controller that selects the appropriate strategy.

    Chooses between Simple, Recorded, and Waypoint strategies based on:
    - Distance to target
    - Whether a recorded sequence is available
    - Complexity of navigation required
    """

    SIMPLE_DISTANCE_THRESHOLD = 50  # Use simple pathfinding for < 50px

    def __init__(self, hid_writer, position_getter):
        """
        Initialize pathfinding controller.

        Args:
            hid_writer: HIDWriter instance for sending keystrokes
            position_getter: Async callable that returns current (x, y) position
        """
        self.hid_writer = hid_writer
        self.position_getter = position_getter

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
        2. Simple directional (for short distances)
        3. Simple directional (fallback)
        """
        # Priority 1: Recorded sequence
        if target_point.pathfinding_sequence:
            logger.info(
                f"Using RecordedPathfinder with sequence: {target_point.pathfinding_sequence}"
            )
            return RecordedPathfinder(target_point.pathfinding_sequence)

        # Priority 2 & 3: Simple directional
        if distance < self.SIMPLE_DISTANCE_THRESHOLD:
            logger.info(f"Using SimplePathfinder (distance={distance:.1f}px < threshold)")
        else:
            logger.info(f"Using SimplePathfinder as fallback (distance={distance:.1f}px)")

        return SimplePathfinder()
