"""
Map configuration management for CV region detection.

Allows users to save and manage multiple mini-map detection regions
for performance optimization on Raspberry Pi.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)


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
    """
    name: str
    tl_x: int
    tl_y: int
    width: int
    height: int
    created_at: float
    last_used_at: float = 0.0
    is_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MapConfig':
        """Create MapConfig from dictionary."""
        return cls(**data)

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
            logger.debug(f"Saved {len(configs_list)} map configs to {self.config_file}")

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
            if self._active_config_name:
                return self._configs.get(self._active_config_name)
        return None

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

            logger.info(f"Activated map config: {name}")

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
