"""
Port Flow handler for MapleStory portal/teleport navigation.

Implements the specific portal jump logic where the player uses UP key
to activate portals, with LEFT/RIGHT adjustments to align with the portal.
"""

import asyncio
import logging
from typing import Tuple, Optional
from msmacro.cv.map_config import DeparturePoint

logger = logging.getLogger(__name__)


class PortFlowHandler:
    """
    Handles portal/teleport navigation in MapleStory.

    Port Flow Logic (from user's flowchart):
    1. Press UP key once (attempt portal activation)
    2. Check if player hit the target departure point
    3. If not, adjust X position:
       - If player X < target X: Press RIGHT + UP
       - If player X > target X: Press LEFT + UP
    4. Repeat up to MAX_LEFT_ATTEMPTS times
    5. Return False if failed (triggers CV-AUTO mode stop)
    """

    MAX_LEFT_ATTEMPTS = 3
    UP_PRESS_DURATION = 0.1  # How long to hold UP key
    ADJUST_PRESS_DURATION = 0.1  # How long to hold LEFT/RIGHT
    CHECK_DELAY = 0.5  # Wait time after UP press before checking position

    def __init__(self, hid_writer, position_getter):
        """
        Initialize Port Flow handler.

        Args:
            hid_writer: HIDWriter instance for sending keystrokes
            position_getter: Async callable that returns current (x, y) position
        """
        self.hid_writer = hid_writer
        self.position_getter = position_getter

        # HID usage IDs for arrow keys
        self.KEY_UP = 0x52
        self.KEY_DOWN = 0x51
        self.KEY_LEFT = 0x50
        self.KEY_RIGHT = 0x4F

    async def execute_port_flow(
        self,
        current_pos: Tuple[int, int],
        target_point: DeparturePoint
    ) -> bool:
        """
        Execute portal jump flow to reach target departure point.

        Flow:
        1. Press UP once
        2. Wait and check if target reached
        3. If not reached:
           - Determine X adjustment direction
           - Press LEFT or RIGHT, then UP
           - Repeat up to MAX_LEFT_ATTEMPTS times
        4. Return True if reached, False if failed

        Args:
            current_pos: Current (x, y) player position
            target_point: Target departure point (portal destination)

        Returns:
            True if successfully reached target via portal, False otherwise
        """
        logger.info(
            f"PortFlow: Attempting portal navigation from ({current_pos[0]}, {current_pos[1]}) "
            f"to point '{target_point.name}' at ({target_point.x}, {target_point.y})"
        )

        # Attempt 0: Initial UP press
        logger.debug("PortFlow: Initial UP press attempt")
        await self._press_up()
        await asyncio.sleep(self.CHECK_DELAY)

        # Check if hit
        new_pos = await self.position_getter()
        if new_pos and target_point.check_hit(new_pos[0], new_pos[1]):
            logger.info("PortFlow: Target reached on initial UP press!")
            return True

        # Attempts 1-3: Adjust X position and retry
        for attempt in range(1, self.MAX_LEFT_ATTEMPTS + 1):
            logger.debug(f"PortFlow: Adjustment attempt {attempt}/{self.MAX_LEFT_ATTEMPTS}")

            if not new_pos:
                logger.warning("PortFlow: Failed to get player position, retrying...")
                new_pos = await self.position_getter()
                if not new_pos:
                    continue

            # Determine X adjustment direction
            current_x = new_pos[0]
            target_x = target_point.x
            dx = target_x - current_x

            logger.debug(f"PortFlow: Current X={current_x}, Target X={target_x}, Delta={dx}")

            # Press LEFT or RIGHT to adjust X position
            if current_x < target_x:
                # Player is too far left, move right
                logger.debug("PortFlow: Player too far left, pressing RIGHT + UP")
                await self._press_key(self.KEY_RIGHT, self.ADJUST_PRESS_DURATION)
            elif current_x > target_x:
                # Player is too far right, move left
                logger.debug("PortFlow: Player too far right, pressing LEFT + UP")
                await self._press_key(self.KEY_LEFT, self.ADJUST_PRESS_DURATION)
            else:
                # X position is aligned, just press UP
                logger.debug("PortFlow: X position aligned, pressing UP only")

            # Press UP to activate portal
            await self._press_up()
            await asyncio.sleep(self.CHECK_DELAY)

            # Check if hit
            new_pos = await self.position_getter()
            if new_pos and target_point.check_hit(new_pos[0], new_pos[1]):
                logger.info(f"PortFlow: Target reached on attempt {attempt}!")
                return True

        # Failed after MAX_LEFT_ATTEMPTS
        logger.error(
            f"PortFlow: Failed to reach target after {self.MAX_LEFT_ATTEMPTS} attempts. "
            f"Final position: ({new_pos[0] if new_pos else 'unknown'}, "
            f"{new_pos[1] if new_pos else 'unknown'})"
        )
        return False

    async def _press_up(self):
        """Press UP key to activate portal."""
        await self._press_key(self.KEY_UP, self.UP_PRESS_DURATION)

    async def _press_key(self, usage_id: int, duration: float):
        """
        Press and release a key.

        Args:
            usage_id: HID usage ID of the key
            duration: How long to hold the key (seconds)
        """
        # Press
        await self.hid_writer.press(usage_id)
        await asyncio.sleep(duration)

        # Release
        await self.hid_writer.release(usage_id)

        # Small delay after release
        await asyncio.sleep(0.05)


class PortDetector:
    """
    Detects when player has teleported/ported to a different location.

    Useful for detecting map changes, return scrolls, or unexpected teleports
    that should reset the CV-AUTO flow.
    """

    PORT_DISTANCE_THRESHOLD = 50  # Jump > 50px = port detected
    DETECTION_TIMEOUT = 2.0  # No detection for >2s = possible port

    def __init__(self):
        self.last_pos: Optional[Tuple[int, int]] = None
        self.last_time: float = 0.0

    def update_position(self, current_pos: Tuple[int, int], current_time: float):
        """
        Update position tracker.

        Args:
            current_pos: Current (x, y) player position
            current_time: Current timestamp
        """
        self.last_pos = current_pos
        self.last_time = current_time

    def check_port(
        self,
        current_pos: Optional[Tuple[int, int]],
        current_time: float
    ) -> bool:
        """
        Check if a port/teleport has been detected.

        Detection criteria:
        1. Abrupt position change (>50px in single frame)
        2. Loss of detection for >2 seconds

        Args:
            current_pos: Current player position (None if not detected)
            current_time: Current timestamp

        Returns:
            True if port detected, False otherwise
        """
        if not self.last_pos:
            # First position, not a port
            return False

        # Check for detection timeout
        if current_time - self.last_time > self.DETECTION_TIMEOUT:
            logger.warning(
                f"PortDetector: Detection timeout ({current_time - self.last_time:.1f}s) - "
                "possible port or map change"
            )
            return True

        # Check for abrupt position change
        if current_pos:
            dx = current_pos[0] - self.last_pos[0]
            dy = current_pos[1] - self.last_pos[1]
            distance = (dx**2 + dy**2)**0.5

            if distance > self.PORT_DISTANCE_THRESHOLD:
                logger.warning(
                    f"PortDetector: Abrupt position change ({distance:.1f}px) detected - "
                    f"from ({self.last_pos[0]}, {self.last_pos[1]}) "
                    f"to ({current_pos[0]}, {current_pos[1]})"
                )
                return True

        return False

    def reset(self):
        """Reset port detector state."""
        self.last_pos = None
        self.last_time = 0.0
        logger.debug("PortDetector: State reset")
