"""
Point Navigator for sequential departure point progression.

Manages the flow of navigating through departure points in order,
selecting rotations based on configured mode, and tracking progress.
"""

import logging
import random
from dataclasses import dataclass
from typing import List, Optional
from msmacro.cv.map_config import MapConfig, DeparturePoint

logger = logging.getLogger(__name__)


@dataclass
class NavigationState:
    """
    Represents the current state of CV-AUTO navigation.

    Attributes:
        current_point_index: Index of the current target departure point
        total_points: Total number of departure points in the map
        current_point_name: Name of the current departure point
        last_rotation_played: Path of the last rotation played
        rotations_played_count: Total number of rotations played in this session
        cycles_completed: Number of complete cycles through all points
    """
    current_point_index: int
    total_points: int
    current_point_name: str
    last_rotation_played: Optional[str] = None
    rotations_played_count: int = 0
    cycles_completed: int = 0


class PointNavigator:
    """
    Manages sequential progression through departure points.

    Responsibilities:
    - Track current position in the departure points sequence
    - Select which rotation to play based on point's rotation_mode
    - Handle cycling back to first point after completing sequence
    - Maintain counters for sequential rotation mode
    """

    def __init__(self, departure_points: List[DeparturePoint], map_name: str, loop: bool = True):
        """
        Initialize point navigator.

        Args:
            departure_points: List of DeparturePoint objects to navigate through
            map_name: Name of the map being navigated
            loop: Whether to loop back to first point after last (default: True)
        """
        if not departure_points:
            raise ValueError("No departure points provided")

        # Sort points by order to ensure correct sequence
        self.points = sorted(departure_points, key=lambda p: p.order)
        self.map_name = map_name
        self.loop = loop

        # Navigation state
        self.current_index = 0
        self.rotations_played_count = 0
        self.cycles_completed = 0
        self.last_rotation_played: Optional[str] = None

        logger.info(
            f"PointNavigator initialized: {len(self.points)} points in map '{self.map_name}', "
            f"loop={self.loop}"
        )
        for i, point in enumerate(self.points):
            logger.info(
                f"  Point {i}: '{point.name}' at ({point.x}, {point.y}) - "
                f"{len(point.rotation_paths)} rotation(s), "
                f"mode={point.rotation_mode}, teleport={point.is_teleport_point}"
            )

    def get_current_point(self) -> DeparturePoint:
        """
        Get the current target departure point.

        Returns:
            Current DeparturePoint
        """
        return self.points[self.current_index]

    def get_next_point(self) -> Optional[DeparturePoint]:
        """
        Get the next departure point without advancing.

        Returns:
            Next DeparturePoint if available, None if at end and not looping
        """
        next_index = self.current_index + 1

        if next_index >= len(self.points):
            if self.loop:
                return self.points[0]  # Loop back to first
            else:
                return None  # End of sequence

        return self.points[next_index]

    def advance(self) -> bool:
        """
        Advance to the next departure point in the sequence.

        Returns:
            True if advanced, False if at end and not looping
        """
        next_index = self.current_index + 1

        if next_index >= len(self.points):
            if self.loop:
                # Loop back to first point
                self.current_index = 0
                self.cycles_completed += 1
                logger.info(
                    f"PointNavigator: Completed cycle {self.cycles_completed}, "
                    f"looping back to point 0 ('{self.points[0].name}')"
                )
                return True
            else:
                # End of sequence, no loop
                logger.info("PointNavigator: Reached end of sequence (no loop)")
                return False

        self.current_index = next_index
        current_point = self.get_current_point()
        logger.info(
            f"PointNavigator: Advanced to point {self.current_index} ('{current_point.name}')"
        )
        return True

    def reset(self):
        """
        Reset navigator to first point.

        Useful when port/teleport detected or manual reset requested.
        """
        logger.info("PointNavigator: Resetting to first point")
        self.current_index = 0
        self.rotations_played_count = 0
        self.cycles_completed = 0
        self.last_rotation_played = None

    def select_rotation(self, point: Optional[DeparturePoint] = None) -> Optional[str]:
        """
        Select a rotation to play for the given (or current) departure point.

        Selection logic based on point.rotation_mode:
        - "single": Always return the first rotation
        - "random": Randomly select from the list (default, enforced by CVItem)

        Args:
            point: DeparturePoint to select rotation for (default: current point)

        Returns:
            Path to rotation file, or None if no rotations available
        """
        if point is None:
            point = self.get_current_point()

        if not point.rotation_paths:
            logger.warning(f"No rotations linked to point '{point.name}'")
            return None

        rotation_path = None

        if point.rotation_mode == "single":
            # Always play the first rotation
            rotation_path = point.rotation_paths[0]
            logger.debug(f"Selected rotation (single mode): {rotation_path}")

        elif point.rotation_mode == "random":
            # Randomly pick one (this is the enforced default)
            rotation_path = random.choice(point.rotation_paths)
            logger.debug(
                f"Selected rotation (random mode): {rotation_path} "
                f"from {len(point.rotation_paths)} options"
            )

        else:
            # Should never happen due to CVItem enforcement, but handle gracefully
            logger.error(
                f"Unsupported rotation_mode '{point.rotation_mode}' for point '{point.name}'. "
                f"Falling back to random selection."
            )
            rotation_path = random.choice(point.rotation_paths)

        # Update tracking
        self.last_rotation_played = rotation_path
        self.rotations_played_count += 1

        return rotation_path

    def get_state(self) -> NavigationState:
        """
        Get current navigation state for status reporting.

        Returns:
            NavigationState with current progress info
        """
        current_point = self.get_current_point()

        return NavigationState(
            current_point_index=self.current_index,
            total_points=len(self.points),
            current_point_name=current_point.name,
            last_rotation_played=self.last_rotation_played,
            rotations_played_count=self.rotations_played_count,
            cycles_completed=self.cycles_completed
        )

    def get_all_points(self) -> List[DeparturePoint]:
        """
        Get all departure points in sequence order.

        Returns:
            List of DeparturePoint objects
        """
        return self.points.copy()

    def get_progress_percentage(self) -> float:
        """
        Calculate navigation progress percentage.

        Returns:
            Progress as percentage (0.0 to 100.0)
        """
        if not self.points:
            return 0.0

        return (self.current_index / len(self.points)) * 100.0

    def is_last_point(self) -> bool:
        """
        Check if currently at the last departure point.

        Returns:
            True if at last point, False otherwise
        """
        return self.current_index == len(self.points) - 1

    def is_first_point(self) -> bool:
        """
        Check if currently at the first departure point.

        Returns:
            True if at first point, False otherwise
        """
        return self.current_index == 0
