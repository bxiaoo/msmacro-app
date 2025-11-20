"""
Map configuration management for CV region detection.

Allows users to save and manage multiple mini-map detection regions
for performance optimization on Raspberry Pi.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional, Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class DeparturePoint:
    """
    Represents a departure point (waypoint) on the minimap.

    Attributes:
        id: Unique identifier (UUID)
        name: User-defined name for the point
        x: X coordinate relative to minimap top-left
        y: Y coordinate relative to minimap top-left
        order: Sequential order in the path (0-based)
        tolerance_mode: How to check if player hits this point
            - "y_axis": Check Y-axis within ±tolerance_value
            - "x_axis": Check X-axis within ±tolerance_value
            - "y_greater": Check if current Y > saved Y
            - "y_less": Check if current Y < saved Y
            - "x_greater": Check if current X > saved X
            - "x_less": Check if current X < saved X
            - "both": Check both X and Y within ±tolerance_value
        tolerance_value: Pixel tolerance for range-based modes (default: 5)
        created_at: Unix timestamp when point was created
        rotation_paths: List of rotation file paths linked to this point
        rotation_mode: How to select rotation from linked list
            - "random": Randomly pick one rotation per trigger
            - "sequential": Cycle through rotations in order
            - "single": Always play the first rotation
        is_teleport_point: Enable Port flow navigation for this point
        auto_play: Auto-trigger rotation when player hits this point
        pathfinding_sequence: Optional path to pre-recorded movement sequence
    """
    id: str
    name: str
    x: int
    y: int
    order: int
    tolerance_mode: str = "both"
    tolerance_value: int = 5
    created_at: float = 0.0
    rotation_paths: List[str] = field(default_factory=list)
    rotation_mode: str = "random"
    is_teleport_point: bool = False
    auto_play: bool = True
    pathfinding_sequence: Optional[str] = None

    def __post_init__(self):
        """Validate tolerance mode and rotation mode."""
        valid_tolerance_modes = {"y_axis", "x_axis", "y_greater", "y_less", "x_greater", "x_less", "both"}
        if self.tolerance_mode not in valid_tolerance_modes:
            raise ValueError(f"Invalid tolerance_mode: {self.tolerance_mode}. Must be one of {valid_tolerance_modes}")

        valid_rotation_modes = {"random", "sequential", "single"}
        if self.rotation_mode not in valid_rotation_modes:
            raise ValueError(f"Invalid rotation_mode: {self.rotation_mode}. Must be one of {valid_rotation_modes}")

    def check_hit(self, current_x: int, current_y: int) -> bool:
        """
        Check if current position hits this departure point based on tolerance mode.

        Args:
            current_x: Current player X coordinate
            current_y: Current player Y coordinate

        Returns:
            True if player has hit this departure point, False otherwise
        """
        if self.tolerance_mode == "y_axis":
            # Check Y-axis within tolerance, X can be anything
            return abs(current_y - self.y) <= self.tolerance_value

        elif self.tolerance_mode == "x_axis":
            # Check X-axis within tolerance, Y can be anything
            return abs(current_x - self.x) <= self.tolerance_value

        elif self.tolerance_mode == "y_greater":
            # Current Y must be greater than saved Y
            return current_y > self.y

        elif self.tolerance_mode == "y_less":
            # Current Y must be less than saved Y
            return current_y < self.y

        elif self.tolerance_mode == "x_greater":
            # Current X must be greater than saved X
            return current_x > self.x

        elif self.tolerance_mode == "x_less":
            # Current X must be less than saved X
            return current_x < self.x

        elif self.tolerance_mode == "both":
            # X-axis uses tolerance_value, Y-axis always uses 4px
            return (abs(current_x - self.x) <= self.tolerance_value and
                    abs(current_y - self.y) <= 4)

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeparturePoint':
        """Create DeparturePoint from dictionary."""
        # Ensure rotation_paths is always a list (data migration for old formats)
        if 'rotation_paths' in data and not isinstance(data['rotation_paths'], list):
            data = data.copy()  # Don't mutate input
            data['rotation_paths'] = []
        return cls(**data)


@dataclass
class MapConfig:
    """
    Represents a saved mini-map detection region configuration.

    Attributes:
        name: User-defined configuration name (unique identifier)
        tl_x: Top-left X coordinate (pixels)
        tl_y: Top-left Y coordinate (pixels)
        width: Region width (pixels)
        height: Region height (pixels)
        created_at: Unix timestamp when config was created
        last_used_at: Unix timestamp when config was last activated
        is_active: Whether this is the currently active configuration
        departure_points: List of departure points (waypoints) for this map
    """
    name: str
    tl_x: int
    tl_y: int
    width: int
    height: int
    created_at: float
    last_used_at: float = 0.0
    is_active: bool = False
    departure_points: List[DeparturePoint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert departure_points to list of dicts
        data['departure_points'] = [point.to_dict() for point in self.departure_points]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MapConfig':
        """Create MapConfig from dictionary."""
        # Extract departure_points and convert them
        points_data = data.pop('departure_points', [])
        departure_points = [DeparturePoint.from_dict(p) for p in points_data]

        # Create MapConfig with remaining data
        config = cls(**data)
        config.departure_points = departure_points
        return config

    def add_departure_point(self, x: int, y: int, name: str = None,
                           tolerance_mode: str = "both", tolerance_value: int = 5) -> DeparturePoint:
        """
        Add a new departure point to this map config.

        Args:
            x: X coordinate relative to minimap top-left
            y: Y coordinate relative to minimap top-left
            name: Optional name for the point (auto-generated if None)
            tolerance_mode: Tolerance checking mode (default: "both")
            tolerance_value: Pixel tolerance value (default: 5)

        Returns:
            The newly created DeparturePoint
        """
        point_id = str(uuid.uuid4())
        order = len(self.departure_points)

        if name is None:
            name = f"Point {order + 1}"

        point = DeparturePoint(
            id=point_id,
            name=name,
            x=x,
            y=y,
            order=order,
            tolerance_mode=tolerance_mode,
            tolerance_value=tolerance_value,
            created_at=time.time()
        )

        self.departure_points.append(point)
        logger.info(f"Added departure point '{name}' at ({x}, {y}) to config '{self.name}'")
        return point

    def remove_departure_point(self, point_id: str) -> bool:
        """
        Remove a departure point by ID.

        Args:
            point_id: ID of the point to remove

        Returns:
            True if removed, False if not found
        """
        for i, point in enumerate(self.departure_points):
            if point.id == point_id:
                self.departure_points.pop(i)
                # Reorder remaining points
                self._reorder_points()
                logger.info(f"Removed departure point '{point.name}' from config '{self.name}'")
                return True
        return False

    def update_departure_point(self, point_id: str, **kwargs) -> bool:
        """
        Update a departure point's attributes.

        Args:
            point_id: ID of the point to update
            **kwargs: Attributes to update (name, tolerance_mode, tolerance_value, etc.)

        Returns:
            True if updated, False if not found
        """
        for point in self.departure_points:
            if point.id == point_id:
                for key, value in kwargs.items():
                    if hasattr(point, key):
                        setattr(point, key, value)
                logger.info(f"Updated departure point '{point.name}' in config '{self.name}'")
                return True
        return False

    def reorder_departure_points(self, ordered_ids: List[str]) -> bool:
        """
        Reorder departure points based on a list of IDs.

        Args:
            ordered_ids: List of point IDs in desired order

        Returns:
            True if reordered successfully, False if IDs don't match
        """
        if len(ordered_ids) != len(self.departure_points):
            return False

        # Create mapping of ID to point
        points_map = {p.id: p for p in self.departure_points}

        # Check all IDs exist
        if not all(pid in points_map for pid in ordered_ids):
            return False

        # Reorder
        self.departure_points = [points_map[pid] for pid in ordered_ids]
        self._reorder_points()
        logger.info(f"Reordered {len(self.departure_points)} departure points in config '{self.name}'")
        return True

    def _reorder_points(self):
        """Update order field for all points based on list position."""
        for i, point in enumerate(self.departure_points):
            point.order = i

    def get_departure_point(self, point_id: str) -> Optional[DeparturePoint]:
        """
        Get a departure point by ID.

        Args:
            point_id: ID of the point to find

        Returns:
            DeparturePoint if found, None otherwise
        """
        for point in self.departure_points:
            if point.id == point_id:
                return point
        return None

    def check_all_departure_hits(self, current_x: int, current_y: int) -> Dict[str, bool]:
        """
        Check hit_departure status for all departure points.

        Args:
            current_x: Current player X coordinate
            current_y: Current player Y coordinate

        Returns:
            Dictionary mapping point ID to hit status
        """
        return {
            point.id: point.check_hit(current_x, current_y)
            for point in self.departure_points
        }

    def link_rotations_to_point(self, point_id: str, rotation_paths: List[str],
                                rotation_mode: str = None, is_teleport_point: bool = None,
                                auto_play: bool = None) -> bool:
        """
        Link rotation files to a departure point.

        Args:
            point_id: ID of the departure point
            rotation_paths: List of rotation file paths to link
            rotation_mode: Optional rotation selection mode ("random", "sequential", "single")
            is_teleport_point: Optional flag to enable Port flow navigation
            auto_play: Optional flag to enable auto-trigger

        Returns:
            True if successful, False if point not found
        """
        point = self.get_departure_point(point_id)
        if not point:
            return False

        point.rotation_paths = rotation_paths

        if rotation_mode is not None:
            point.rotation_mode = rotation_mode

        if is_teleport_point is not None:
            point.is_teleport_point = is_teleport_point

        if auto_play is not None:
            point.auto_play = auto_play

        logger.info(f"Linked {len(rotation_paths)} rotation(s) to point '{point.name}' "
                   f"(mode={point.rotation_mode}, teleport={point.is_teleport_point})")
        return True

    def unlink_rotation_from_point(self, point_id: str, rotation_path: str) -> bool:
        """
        Remove a specific rotation from a departure point's linked rotations.

        Args:
            point_id: ID of the departure point
            rotation_path: Rotation file path to remove

        Returns:
            True if removed, False if point not found or rotation not linked
        """
        point = self.get_departure_point(point_id)
        if not point:
            return False

        if rotation_path in point.rotation_paths:
            point.rotation_paths.remove(rotation_path)
            logger.info(f"Unlinked rotation '{rotation_path}' from point '{point.name}'")
            return True

        return False

    def get_point_rotations(self, point_id: str) -> Optional[List[str]]:
        """
        Get all linked rotation paths for a departure point.

        Args:
            point_id: ID of the departure point

        Returns:
            List of rotation paths if point found, None otherwise
        """
        point = self.get_departure_point(point_id)
        if point:
            return point.rotation_paths.copy()
        return None

    @property
    def tr_x(self) -> int:
        """Top-right X coordinate."""
        return self.tl_x + self.width

    @property
    def tr_y(self) -> int:
        """Top-right Y coordinate (same as top-left)."""
        return self.tl_y

    @property
    def bl_x(self) -> int:
        """Bottom-left X coordinate (same as top-left)."""
        return self.tl_x

    @property
    def bl_y(self) -> int:
        """Bottom-left Y coordinate."""
        return self.tl_y + self.height

    @property
    def br_x(self) -> int:
        """Bottom-right X coordinate."""
        return self.tl_x + self.width

    @property
    def br_y(self) -> int:
        """Bottom-right Y coordinate."""
        return self.tl_y + self.height

    def get_corners(self) -> Dict[str, tuple]:
        """
        Get all four corner coordinates.

        Returns:
            Dict with keys: 'tl', 'tr', 'bl', 'br'
            Values are (x, y) tuples
        """
        return {
            'tl': (self.tl_x, self.tl_y),
            'tr': (self.tr_x, self.tr_y),
            'bl': (self.bl_x, self.bl_y),
            'br': (self.br_x, self.br_y)
        }


class MapConfigManager:
    """
    Manages saving, loading, and activating map configurations.

    Configurations are stored as JSON in the user's data directory.
    Thread-safe for concurrent access from web API and capture loop.
    """

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize the map config manager.

        Args:
            config_file: Path to config file. If None, uses default location.
        """
        if config_file is None:
            # Check for environment variable override
            config_path_env = os.environ.get('MSMACRO_MAP_CONFIG_FILE')
            if config_path_env:
                config_file = Path(config_path_env)
                # Ensure parent directory exists
                config_file.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Using map config file from environment: {config_file}")
            else:
                # Default location: ~/.local/share/msmacro/map_configs.json
                data_dir = Path.home() / '.local' / 'share' / 'msmacro'
                data_dir.mkdir(parents=True, exist_ok=True)
                config_file = data_dir / 'map_configs.json'

        self.config_file = config_file
        self._config_file = config_file  # Expose for diagnostics
        self._configs: Dict[str, MapConfig] = {}
        self._active_config_name: Optional[str] = None
        self._lock = Lock()

        # Load existing configs
        self._load()

    def _load(self) -> None:
        """Load configurations from file."""
        if not self.config_file.exists():
            logger.info(f"No existing config file at {self.config_file}")
            return

        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)

            configs_data = data.get('configs', [])
            active_name = data.get('active_config', None)

            with self._lock:
                self._configs.clear()
                for config_data in configs_data:
                    config = MapConfig.from_dict(config_data)
                    self._configs[config.name] = config

                self._active_config_name = active_name

                # Mark active config
                if active_name and active_name in self._configs:
                    self._configs[active_name].is_active = True

            logger.info(f"Loaded {len(self._configs)} map configs from {self.config_file}")
            if self._active_config_name:
                logger.info(f"Active config: {self._active_config_name}")

        except Exception as e:
            logger.error(f"Failed to load map configs: {e}", exc_info=True)

    def reload(self) -> None:
        """
        Reload configurations from disk.

        This should be called when configs are modified externally (e.g., via web API)
        to sync the in-memory state with the file on disk.
        """
        logger.info(f"Reloading map configs from {self.config_file}...")
        self._load()
        logger.info("Map configs reload complete")

    def _save(self) -> None:
        """Save configurations to file."""
        try:
            with self._lock:
                configs_list = [config.to_dict() for config in self._configs.values()]
                data = {
                    'configs': configs_list,
                    'active_config': self._active_config_name
                }

            # Write atomically (temp file + rename)
            temp_file = self.config_file.with_suffix('.json.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)

            temp_file.replace(self.config_file)
            logger.info(
                f"💾 SAVED {len(configs_list)} configs to {self.config_file} | "
                f"active={self._active_config_name}"
            )
            logger.debug(f"Config file content: {json.dumps(data, indent=2)}")

        except Exception as e:
            logger.error(f"Failed to save map configs: {e}", exc_info=True)
            raise

    def list_configs(self) -> List[MapConfig]:
        """
        Get all saved configurations.

        Returns:
            List of MapConfig objects, sorted by last_used_at (most recent first)
        """
        with self._lock:
            configs = list(self._configs.values())

        # Sort by last_used_at descending, then created_at descending
        configs.sort(key=lambda c: (c.last_used_at, c.created_at), reverse=True)
        return configs

    def get_config(self, name: str) -> Optional[MapConfig]:
        """
        Get a specific configuration by name.

        Args:
            name: Configuration name

        Returns:
            MapConfig if found, None otherwise
        """
        with self._lock:
            return self._configs.get(name)

    def get_active_config(self) -> Optional[MapConfig]:
        """
        Get the currently active configuration.

        Returns:
            Active MapConfig if set, None otherwise
        """
        with self._lock:
            config = self._configs.get(self._active_config_name) if self._active_config_name else None

        logger.debug(
            f"get_active_config() → {config.name if config else None} | "
            f"coords={f'({config.tl_x},{config.tl_y})' if config else 'N/A'}"
        )
        return config

    def save_config(self, config: MapConfig) -> None:
        """
        Save a new or updated configuration.

        Args:
            config: MapConfig to save

        Raises:
            ValueError: If config name is empty or invalid
        """
        if not config.name or not config.name.strip():
            raise ValueError("Config name cannot be empty")

        # Validate dimensions
        if config.width <= 0 or config.height <= 0:
            raise ValueError(f"Invalid dimensions: {config.width}x{config.height}")

        # Validate coordinates
        if config.tl_x < 0 or config.tl_y < 0:
            raise ValueError(f"Invalid coordinates: ({config.tl_x}, {config.tl_y})")

        with self._lock:
            # If updating existing config, preserve created_at
            if config.name in self._configs:
                existing = self._configs[config.name]
                config.created_at = existing.created_at
                logger.info(f"Updating existing map config: {config.name}")
            else:
                config.created_at = time.time()
                logger.info(f"Creating new map config: {config.name}")

            self._configs[config.name] = config

        self._save()

    def delete_config(self, name: str) -> bool:
        """
        Delete a configuration.

        Args:
            name: Configuration name to delete

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if name not in self._configs:
                return False

            # Cannot delete active config
            if name == self._active_config_name:
                logger.warning(f"Cannot delete active config: {name}")
                return False

            del self._configs[name]
            logger.info(f"Deleted map config: {name}")

        self._save()

        # Notify CV Item manager about deletion
        try:
            from .cv_item import get_cv_item_manager
            get_cv_item_manager().handle_map_config_deleted(name)
        except Exception as e:
            logger.warning(f"Failed to notify CV Item manager about map config deletion: {e}")

        return True

    def activate_config(self, name: str) -> Optional[MapConfig]:
        """
        Set a configuration as active.

        Args:
            name: Configuration name to activate

        Returns:
            Activated MapConfig if found, None otherwise
        """
        with self._lock:
            if name not in self._configs:
                logger.warning(f"Config not found: {name}")
                return None

            # Deactivate previous
            if self._active_config_name and self._active_config_name in self._configs:
                self._configs[self._active_config_name].is_active = False

            # Activate new
            config = self._configs[name]
            config.is_active = True
            config.last_used_at = time.time()
            self._active_config_name = name

            logger.info(
                f"✓ ACTIVATED CONFIG: '{name}' | "
                f"coords=({config.tl_x},{config.tl_y}) size={config.width}x{config.height} | "
                f"active_name={self._active_config_name}"
            )

        self._save()
        return config

    def deactivate(self) -> None:
        """Deactivate the current configuration (revert to full-screen detection)."""
        with self._lock:
            if self._active_config_name and self._active_config_name in self._configs:
                self._configs[self._active_config_name].is_active = False

            self._active_config_name = None
            logger.info("Deactivated map config (full-screen detection)")

        self._save()

    def clear_all(self) -> None:
        """Delete all configurations (for testing/reset)."""
        with self._lock:
            self._configs.clear()
            self._active_config_name = None

        self._save()
        logger.warning("Cleared all map configs")


# Global instance (singleton pattern)
_manager: Optional[MapConfigManager] = None
_manager_lock = Lock()


def get_manager() -> MapConfigManager:
    """
    Get the global MapConfigManager instance.

    Returns:
        MapConfigManager singleton
    """
    global _manager

    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = MapConfigManager()

    return _manager
