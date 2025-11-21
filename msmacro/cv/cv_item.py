"""
CV Item data model and manager.

CVItem packages map configuration, pathfinding rotations, and departure points
into a single reusable entity for CV automation workflows.
"""

import json
import logging
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from threading import Lock

from .map_config import DeparturePoint, get_manager as get_map_manager

logger = logging.getLogger(__name__)


@dataclass
class CVItem:
    """
    Represents a complete CV automation setup.

    Attributes:
        name: Unique identifier for this CV Item
        map_config_name: Reference to a saved MapConfig (not embedded)
        pathfinding_rotations: DEPRECATED - Dict with 4 distance-based rotation lists
            This field is kept for backward compatibility but is no longer used.
            Use pathfinding_config instead for class-based pathfinding.
            {
                "near": List[str],     # Rotations for 0-50 pixel distance
                "medium": List[str],   # Rotations for 50-150 pixel distance
                "far": List[str],      # Rotations for 150-300 pixel distance
                "very_far": List[str]  # Rotations for 300+ pixel distance
            }
        pathfinding_config: Class-based pathfinding configuration
            {
                "class_type": "other" | "magician",
                "rope_lift_key": str (optional),
                "diagonal_movement_key": str (other class only),
                "double_jump_up_allowed": bool (other class, default True),
                "y_axis_jump_skill": str (other class only),
                "teleport_skill": str (magician class only)
            }
        departure_points: List of DeparturePoint objects
        created_at: Unix timestamp when CV Item was created
        last_used_at: Unix timestamp when CV Item was last activated
        is_active: Whether this CV Item is currently active
        description: Optional user description
        tags: Optional list of tags for organization
    """
    name: str
    map_config_name: Optional[str]  # Can be null if map config deleted
    pathfinding_rotations: Dict[str, List[str]]
    departure_points: List[DeparturePoint]
    created_at: float
    pathfinding_config: Dict[str, Any] = field(default_factory=dict)
    last_used_at: float = 0.0
    is_active: bool = False
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate pathfinding_rotations structure and enforce rotation_mode."""
        required_keys = {"near", "medium", "far", "very_far"}
        if not isinstance(self.pathfinding_rotations, dict):
            raise ValueError("pathfinding_rotations must be a dict")

        # Ensure all required keys exist
        for key in required_keys:
            if key not in self.pathfinding_rotations:
                self.pathfinding_rotations[key] = []

        # Validate each value is a list
        for key, value in self.pathfinding_rotations.items():
            if not isinstance(value, list):
                raise ValueError(f"pathfinding_rotations['{key}'] must be a list")

        # Enforce rotation_mode = "random" for all departure points
        # This prevents memory leaks from sequential mode counters and simplifies logic
        for point in self.departure_points:
            if point.rotation_mode != "random":
                logger.info(
                    f"Forcing rotation_mode to 'random' for point '{point.name}' "
                    f"(was '{point.rotation_mode}')"
                )
                point.rotation_mode = "random"

    def validate(self) -> Tuple[bool, str]:
        """
        Validate CV Item for saving.

        Returns:
            (is_valid, error_message)
        """
        if not self.name or not self.name.strip():
            return False, "CV Item name cannot be empty"

        # Validate map_config_name is set
        if not self.map_config_name:
            return False, "CV Item must have a map configuration assigned"

        if not self.departure_points:
            return False, "CV Item must have at least one departure point"

        # Check that at least one departure point has rotations
        has_rotations = any(point.rotation_paths for point in self.departure_points)
        if not has_rotations:
            return False, "At least one departure point must have linked rotations"

        # Validate pathfinding_config if present
        if self.pathfinding_config:
            class_type = self.pathfinding_config.get('class_type', 'other')
            if class_type not in ('other', 'magician'):
                return False, f"Invalid pathfinding class_type: {class_type}"

        return True, ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "map_config_name": self.map_config_name,
            "pathfinding_rotations": self.pathfinding_rotations,
            "pathfinding_config": self.pathfinding_config,
            "departure_points": [point.to_dict() for point in self.departure_points],
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "is_active": self.is_active,
            "description": self.description,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CVItem':
        """Create CVItem from dictionary."""
        # Extract departure_points and convert them
        points_data = data.pop('departure_points', [])
        departure_points = [DeparturePoint.from_dict(p) for p in points_data]

        # Create CVItem with remaining data
        # Use dict unpacking with defaults for optional fields
        item_data = {
            'name': data['name'],
            'map_config_name': data.get('map_config_name'),
            'pathfinding_rotations': data.get('pathfinding_rotations', {
                'near': [], 'medium': [], 'far': [], 'very_far': []
            }),
            'pathfinding_config': data.get('pathfinding_config', {}),
            'departure_points': departure_points,
            'created_at': data['created_at'],
            'last_used_at': data.get('last_used_at', 0.0),
            'is_active': data.get('is_active', False),
            'description': data.get('description', ''),
            'tags': data.get('tags', [])
        }

        return cls(**item_data)


class CVItemManager:
    """
    Manages CV Item CRUD operations and persistence.

    Thread-safe singleton similar to MapConfigManager.
    Storage location: ~/.local/share/msmacro/cv_items.json
    """

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize the CV Item manager.

        Args:
            config_file: Path to config file. If None, uses default location.
        """
        if config_file is None:
            data_dir = Path.home() / '.local' / 'share' / 'msmacro'
            data_dir.mkdir(parents=True, exist_ok=True)
            config_file = data_dir / 'cv_items.json'

        self.config_file = config_file
        self._items: Dict[str, CVItem] = {}
        self._active_item_name: Optional[str] = None
        self._lock = Lock()

        # Load existing items
        self._load()

    def _load(self) -> None:
        """Load CV Items from file."""
        if not self.config_file.exists():
            logger.info(f"No existing CV Items file at {self.config_file}")
            return

        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)

            items_data = data.get('cv_items', [])
            active_name = data.get('active_item', None)

            with self._lock:
                self._items.clear()
                for item_data in items_data:
                    item = CVItem.from_dict(item_data)
                    self._items[item.name] = item

                self._active_item_name = active_name

                # Mark active item
                if active_name and active_name in self._items:
                    self._items[active_name].is_active = True

            logger.info(f"Loaded {len(self._items)} CV Items from {self.config_file}")
            if self._active_item_name:
                logger.info(f"Active CV Item: {self._active_item_name}")

        except Exception as e:
            logger.error(f"Failed to load CV Items: {e}", exc_info=True)

    def reload(self) -> None:
        """
        Reload CV Items from disk.

        This should be called when items are modified externally.
        """
        logger.info(f"Reloading CV Items from {self.config_file}...")
        self._load()
        logger.info("CV Items reload complete")

    def _save(self) -> None:
        """Save CV Items to file."""
        try:
            with self._lock:
                items_list = [item.to_dict() for item in self._items.values()]
                data = {
                    'cv_items': items_list,
                    'active_item': self._active_item_name
                }

            # Write atomically (temp file + rename)
            temp_file = self.config_file.with_suffix('.json.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)

            temp_file.replace(self.config_file)
            logger.info(
                f"💾 SAVED {len(items_list)} CV Items to {self.config_file} | "
                f"active={self._active_item_name}"
            )
            logger.debug(f"CV Items file content: {json.dumps(data, indent=2)}")

        except Exception as e:
            logger.error(f"Failed to save CV Items: {e}", exc_info=True)
            raise

    def list_items(self) -> List[CVItem]:
        """
        Get all saved CV Items.

        Returns:
            List of CVItem objects, sorted by last_used_at (most recent first)
        """
        with self._lock:
            items = list(self._items.values())

        # Sort by last_used_at descending, then created_at descending
        items.sort(key=lambda i: (i.last_used_at, i.created_at), reverse=True)
        return items

    def get_item(self, name: str) -> Optional[CVItem]:
        """
        Get a specific CV Item by name.

        Args:
            name: CV Item name

        Returns:
            CVItem if found, None otherwise
        """
        with self._lock:
            return self._items.get(name)

    def get_active_item(self) -> Optional[CVItem]:
        """
        Get the currently active CV Item.

        Returns:
            Active CVItem if set, None otherwise
        """
        with self._lock:
            item = self._items.get(self._active_item_name) if self._active_item_name else None

        logger.debug(
            f"get_active_item() → {item.name if item else None}"
        )
        return item

    def create_item(self, item: CVItem) -> None:
        """
        Create a new CV Item.

        Args:
            item: CVItem to create

        Raises:
            ValueError: If validation fails or name already exists
        """
        # Validate
        is_valid, error_msg = item.validate()
        if not is_valid:
            raise ValueError(error_msg)

        with self._lock:
            if item.name in self._items:
                raise ValueError(f"CV Item '{item.name}' already exists")

            # Set timestamps
            item.created_at = time.time()
            item.last_used_at = 0.0
            item.is_active = False

            self._items[item.name] = item
            logger.info(f"Created new CV Item: {item.name}")

        self._save()

    def update_item(self, name: str, updated_item: CVItem) -> None:
        """
        Update an existing CV Item (modify in-place).

        Args:
            name: Current name of the CV Item to update
            updated_item: Updated CVItem object

        Raises:
            ValueError: If validation fails or item not found
        """
        # Validate
        is_valid, error_msg = updated_item.validate()
        if not is_valid:
            raise ValueError(error_msg)

        with self._lock:
            if name not in self._items:
                raise ValueError(f"CV Item '{name}' not found")

            # Preserve created_at and active status
            existing = self._items[name]
            updated_item.created_at = existing.created_at
            updated_item.is_active = existing.is_active

            # Handle name change
            if updated_item.name != name:
                # Check new name doesn't conflict
                if updated_item.name in self._items:
                    raise ValueError(f"CV Item '{updated_item.name}' already exists")

                # Remove old name, add new name
                del self._items[name]
                self._items[updated_item.name] = updated_item

                # Update active item name if this was active
                if self._active_item_name == name:
                    self._active_item_name = updated_item.name

                logger.info(f"Updated CV Item: renamed '{name}' → '{updated_item.name}'")
            else:
                # Same name, just update
                self._items[name] = updated_item
                logger.info(f"Updated CV Item: {name}")

        self._save()

    def delete_item(self, name: str) -> bool:
        """
        Delete a CV Item.

        Args:
            name: CV Item name to delete

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If trying to delete active item
        """
        with self._lock:
            if name not in self._items:
                return False

            # Cannot delete active item
            if name == self._active_item_name:
                raise ValueError(f"Cannot delete active CV Item '{name}'. Deactivate first.")

            del self._items[name]
            logger.info(f"Deleted CV Item: {name}")

        self._save()
        return True

    def activate_item(self, name: str) -> Optional[CVItem]:
        """
        Activate a CV Item.

        Steps:
        1. Deactivate current item
        2. Load CV Item
        3. Validate map config exists
        4. Activate map config via MapConfigManager
        5. Mark CV Item as active
        6. Update last_used_at
        7. Save state

        Args:
            name: CV Item name to activate

        Returns:
            Activated CVItem if successful, None if map config not found or item not found
        """
        with self._lock:
            if name not in self._items:
                logger.warning(f"CV Item not found: {name}")
                return None

            # Deactivate previous item
            if self._active_item_name and self._active_item_name in self._items:
                self._items[self._active_item_name].is_active = False

            # Get item to activate
            item = self._items[name]

            # Check if map config exists
            if not item.map_config_name:
                logger.error(f"CV Item '{name}' has no map config assigned")
                return None

            # Activate map config
            map_manager = get_map_manager()
            activated_config = map_manager.activate_config(item.map_config_name)

            if not activated_config:
                logger.error(
                    f"Failed to activate map config '{item.map_config_name}' "
                    f"for CV Item '{name}'"
                )
                return None

            # Sync departure points from map config to ensure CV Item has latest data
            if activated_config.departure_points:
                points_changed = False

                # Check if departure points need syncing
                if len(item.departure_points) != len(activated_config.departure_points):
                    points_changed = True
                    logger.warning(
                        f"CV Item '{name}' has {len(item.departure_points)} departure points, "
                        f"but map config has {len(activated_config.departure_points)}. Syncing..."
                    )
                else:
                    # Compare each departure point for changes
                    for cv_point, map_point in zip(item.departure_points, activated_config.departure_points):
                        if (cv_point.x != map_point.x or cv_point.y != map_point.y or
                            cv_point.rotation_paths != map_point.rotation_paths or
                            cv_point.name != map_point.name):
                            points_changed = True
                            logger.warning(
                                f"CV Item '{name}' departure point '{cv_point.name}' differs from "
                                f"map config. Syncing..."
                            )
                            break

                # Sync if changes detected
                if points_changed:
                    logger.info(
                        f"🔄 SYNCING departure points from map config '{item.map_config_name}' "
                        f"to CV Item '{name}'"
                    )
                    item.departure_points = activated_config.departure_points
                    logger.info(
                        f"✓ Synced {len(item.departure_points)} departure points to CV Item '{name}'"
                    )

            # Mark item as active
            item.is_active = True
            item.last_used_at = time.time()
            self._active_item_name = name

            logger.info(
                f"✓ ACTIVATED CV ITEM: '{name}' | "
                f"map_config={item.map_config_name} | "
                f"departure_points={len(item.departure_points)}"
            )

        self._save()
        return item

    def deactivate(self) -> None:
        """Deactivate the current CV Item and its map config."""
        with self._lock:
            if self._active_item_name and self._active_item_name in self._items:
                self._items[self._active_item_name].is_active = False

            self._active_item_name = None

        # Also deactivate map config
        map_manager = get_map_manager()
        map_manager.deactivate()

        logger.info("Deactivated CV Item")
        self._save()

    def sync_departure_points(self, name: str) -> Dict[str, Any]:
        """
        Manually sync a CV Item's departure points from its map config.

        Useful for refreshing CV Item data after map config modifications.

        Args:
            name: CV Item name to sync

        Returns:
            Dict with sync results: {
                "synced": bool,
                "changes": str,
                "departure_points_count": int
            }
        """
        with self._lock:
            if name not in self._items:
                return {"synced": False, "error": f"CV Item '{name}' not found"}

            item = self._items[name]

            if not item.map_config_name:
                return {"synced": False, "error": f"CV Item '{name}' has no map config assigned"}

            # Get map config
            map_manager = get_map_manager()
            map_config = map_manager.get_config(item.map_config_name)

            if not map_config:
                return {
                    "synced": False,
                    "error": f"Map config '{item.map_config_name}' not found"
                }

            if not map_config.departure_points:
                return {
                    "synced": False,
                    "error": f"Map config '{item.map_config_name}' has no departure points"
                }

            # Check for changes
            old_count = len(item.departure_points)
            new_count = len(map_config.departure_points)

            changes = []
            if old_count != new_count:
                changes.append(f"Point count: {old_count} → {new_count}")

            # Compare points
            for i, (old_point, new_point) in enumerate(zip(item.departure_points, map_config.departure_points)):
                if old_point.name != new_point.name:
                    changes.append(f"Point {i} name: {old_point.name} → {new_point.name}")
                if (old_point.x, old_point.y) != (new_point.x, new_point.y):
                    changes.append(f"Point {i} position: ({old_point.x},{old_point.y}) → ({new_point.x},{new_point.y})")
                if old_point.rotation_paths != new_point.rotation_paths:
                    changes.append(f"Point {i} rotations changed")

            # Sync
            item.departure_points = map_config.departure_points

            logger.info(
                f"🔄 Manually synced departure points for CV Item '{name}' from "
                f"map config '{item.map_config_name}' ({len(changes)} changes)"
            )

        self._save()

        return {
            "synced": True,
            "changes": "; ".join(changes) if changes else "No changes",
            "departure_points_count": len(item.departure_points)
        }

    def handle_map_config_deleted(self, map_config_name: str) -> None:
        """
        Called when a map config is deleted.

        Sets map_config_name to None for all CV Items referencing it.
        Does NOT delete the CV Items (user decision per design).

        Args:
            map_config_name: Name of the deleted map config
        """
        affected_items = []

        with self._lock:
            for item in self._items.values():
                if item.map_config_name == map_config_name:
                    item.map_config_name = None
                    affected_items.append(item.name)

        if affected_items:
            logger.warning(
                f"Map config '{map_config_name}' deleted. "
                f"Affected CV Items: {', '.join(affected_items)}"
            )
            self._save()


# Global singleton
_cv_item_manager: Optional[CVItemManager] = None
_manager_lock = Lock()


def get_cv_item_manager() -> CVItemManager:
    """
    Get the global CVItemManager instance.

    Returns:
        CVItemManager singleton
    """
    global _cv_item_manager

    if _cv_item_manager is None:
        with _manager_lock:
            if _cv_item_manager is None:
                _cv_item_manager = CVItemManager()

    return _cv_item_manager
