"""
Configuration persistence for object detection.

Handles loading/saving detector config from:
1. Config file (~/.local/share/msmacro/object_detection_config.json)
2. Environment variables (MSMACRO_PLAYER_COLOR_*)
3. Runtime updates via API
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from .object_detection import DetectorConfig


logger = logging.getLogger(__name__)


def get_config_path() -> Path:
    """Get path to object detection config file."""
    config_dir = Path(os.environ.get(
        "MSMACRO_CONFIG_DIR",
        str(Path.home() / ".local/share/msmacro")
    ))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "object_detection_config.json"


def load_config() -> DetectorConfig:
    """
    Load detector configuration from file and environment.
    
    Priority: runtime > config file > environment > defaults
    
    Returns:
        DetectorConfig instance
    """
    config_dict = {}
    
    # 1. Try loading from config file
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path) as f:
                file_config = json.load(f)
                config_dict = _flatten_config(file_config)
                logger.info(f"Loaded object detection config from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config file {config_path}: {e}")
    
    # 2. Override with environment variables
    env_config = _load_from_env()
    config_dict.update(env_config)
    
    # 3. Create DetectorConfig instance
    return _dict_to_config(config_dict)


def save_config(config: DetectorConfig, metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    Save detector configuration to file.
    
    Args:
        config: DetectorConfig to save
        metadata: Optional metadata (e.g., calibration_source, timestamp)
    """
    config_path = get_config_path()
    
    # Build config dict with nested structure
    config_dict = {
        "enabled": True,  # If we're saving config, assume detection should be enabled
        "player": {
            "color_range": {
                "hsv_lower": list(config.player_hsv_lower),
                "hsv_upper": list(config.player_hsv_upper)
            },
            "blob_size_min": config.min_blob_size,
            "blob_size_max": config.max_blob_size,
            "circularity_min": config.min_circularity
        },
        "other_players": {
            "color_ranges": [
                {
                    "hsv_lower": list(lower),
                    "hsv_upper": list(upper)
                }
                for lower, upper in config.other_player_hsv_ranges
            ],
            "circularity_min": config.min_circularity_other
        },
        "temporal_smoothing": {
            "enabled": config.temporal_smoothing,
            "alpha": config.smoothing_alpha
        }
    }
    
    # Add metadata if provided
    if metadata:
        config_dict.update(metadata)
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
        logger.info(f"Saved object detection config to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save config to {config_path}: {e}", exc_info=True)
        raise


def _flatten_config(nested: Dict[str, Any]) -> Dict[str, Any]:
    """Convert nested config dict to flat dict for DetectorConfig."""
    flat = {}
    
    # Player config
    if "player" in nested:
        player = nested["player"]
        if "color_range" in player:
            cr = player["color_range"]
            flat["player_hsv_lower"] = tuple(cr.get("hsv_lower", (20, 100, 100)))
            flat["player_hsv_upper"] = tuple(cr.get("hsv_upper", (30, 255, 255)))
        flat["min_blob_size"] = player.get("blob_size_min", 3)
        flat["max_blob_size"] = player.get("blob_size_max", 15)
        flat["min_circularity"] = player.get("circularity_min", 0.6)
    
    # Other players config
    if "other_players" in nested:
        other = nested["other_players"]
        if "color_ranges" in other:
            flat["other_player_hsv_ranges"] = [
                (tuple(r["hsv_lower"]), tuple(r["hsv_upper"]))
                for r in other["color_ranges"]
            ]
        flat["min_circularity_other"] = other.get("circularity_min", 0.5)
    
    # Temporal smoothing
    if "temporal_smoothing" in nested:
        ts = nested["temporal_smoothing"]
        flat["temporal_smoothing"] = ts.get("enabled", True)
        flat["smoothing_alpha"] = ts.get("alpha", 0.3)
    
    return flat


def _load_from_env() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    config = {}
    
    # Player color range
    if "MSMACRO_PLAYER_COLOR_H_MIN" in os.environ:
        h_min = int(os.environ["MSMACRO_PLAYER_COLOR_H_MIN"])
        h_max = int(os.environ.get("MSMACRO_PLAYER_COLOR_H_MAX", 30))
        s_min = int(os.environ.get("MSMACRO_PLAYER_COLOR_S_MIN", 100))
        v_min = int(os.environ.get("MSMACRO_PLAYER_COLOR_V_MIN", 100))
        config["player_hsv_lower"] = (h_min, s_min, v_min)
        config["player_hsv_upper"] = (h_max, 255, 255)
    
    # Other player color ranges
    if "MSMACRO_OTHER_PLAYER_COLOR_RANGES" in os.environ:
        ranges_str = os.environ["MSMACRO_OTHER_PLAYER_COLOR_RANGES"]
        ranges = []
        for range_str in ranges_str.split(";"):
            parts = [int(x) for x in range_str.split(",")]
            if len(parts) == 6:
                ranges.append((
                    tuple(parts[0:3]),
                    tuple(parts[3:6])
                ))
        if ranges:
            config["other_player_hsv_ranges"] = ranges
    
    # Blob filtering
    if "MSMACRO_BLOB_MIN_SIZE" in os.environ:
        config["min_blob_size"] = int(os.environ["MSMACRO_BLOB_MIN_SIZE"])
    if "MSMACRO_BLOB_MAX_SIZE" in os.environ:
        config["max_blob_size"] = int(os.environ["MSMACRO_BLOB_MAX_SIZE"])
    if "MSMACRO_BLOB_MIN_CIRCULARITY" in os.environ:
        config["min_circularity"] = float(os.environ["MSMACRO_BLOB_MIN_CIRCULARITY"])
    
    return config


def _dict_to_config(config_dict: Dict[str, Any]) -> DetectorConfig:
    """Convert flat dict to DetectorConfig instance."""
    return DetectorConfig(
        player_hsv_lower=config_dict.get("player_hsv_lower", (20, 100, 100)),
        player_hsv_upper=config_dict.get("player_hsv_upper", (30, 255, 255)),
        other_player_hsv_ranges=config_dict.get("other_player_hsv_ranges", None),
        min_blob_size=config_dict.get("min_blob_size", 3),
        max_blob_size=config_dict.get("max_blob_size", 15),
        min_circularity=config_dict.get("min_circularity", 0.6),
        min_circularity_other=config_dict.get("min_circularity_other", 0.5),
        temporal_smoothing=config_dict.get("temporal_smoothing", True),
        smoothing_alpha=config_dict.get("smoothing_alpha", 0.3)
    )
