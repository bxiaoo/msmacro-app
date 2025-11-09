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
    Save detector configuration to file with comprehensive validation.

    Args:
        config: DetectorConfig to save
        metadata: Optional metadata (e.g., calibration_source, timestamp)

    Raises:
        ValueError: If config validation fails
        IOError: If file write fails
    """
    config_path = get_config_path()

    # === VALIDATION PHASE ===
    validation_errors = []

    # Validate player HSV ranges
    try:
        _validate_hsv_range(
            config.player_hsv_lower,
            config.player_hsv_upper,
            "player"
        )
    except ValueError as e:
        validation_errors.append(f"Player HSV: {e}")

    # Validate other_player HSV ranges
    if config.other_player_hsv_ranges:
        for i, (lower, upper) in enumerate(config.other_player_hsv_ranges):
            try:
                _validate_hsv_range(lower, upper, f"other_player[{i}]")
            except ValueError as e:
                validation_errors.append(f"Other player [{i}] HSV: {e}")
    else:
        validation_errors.append("other_player_hsv_ranges cannot be empty")

    # Validate blob size parameters
    if config.min_blob_size <= 0:
        validation_errors.append(f"min_blob_size must be > 0 (got {config.min_blob_size})")
    if config.max_blob_size <= 0:
        validation_errors.append(f"max_blob_size must be > 0 (got {config.max_blob_size})")
    if config.min_blob_size >= config.max_blob_size:
        validation_errors.append(
            f"min_blob_size ({config.min_blob_size}) must be < "
            f"max_blob_size ({config.max_blob_size})"
        )

    # Validate circularity parameters
    if not (0.0 <= config.min_circularity <= 1.0):
        validation_errors.append(
            f"min_circularity must be 0.0-1.0 (got {config.min_circularity})"
        )
    if not (0.0 <= config.min_circularity_other <= 1.0):
        validation_errors.append(
            f"min_circularity_other must be 0.0-1.0 (got {config.min_circularity_other})"
        )

    # Validate smoothing alpha
    if not (0.0 <= config.smoothing_alpha <= 1.0):
        validation_errors.append(
            f"smoothing_alpha must be 0.0-1.0 (got {config.smoothing_alpha})"
        )

    # If validation failed, raise error with all issues
    if validation_errors:
        error_msg = "Config validation failed:\n" + "\n".join(f"  - {e}" for e in validation_errors)
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)

    # === SAVE PHASE ===
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
        config_dict["metadata"] = metadata

    try:
        # Atomic write (temp file + rename)
        temp_path = config_path.with_suffix('.json.tmp')
        with open(temp_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
        temp_path.replace(config_path)

        logger.info(
            f"✓ Saved object detection config to {config_path} | "
            f"player_hsv={config.player_hsv_lower}-{config.player_hsv_upper} | "
            f"blob_size={config.min_blob_size}-{config.max_blob_size}"
        )
    except Exception as e:
        logger.error(f"Failed to save config to {config_path}: {e}", exc_info=True)
        raise IOError(f"Failed to save config: {e}") from e


def _validate_hsv_range(
    lower: Tuple[int, int, int],
    upper: Tuple[int, int, int],
    name: str
) -> None:
    """
    Validate HSV color range values.

    Args:
        lower: (h_min, s_min, v_min)
        upper: (h_max, s_max, v_max)
        name: Range name for error messages

    Raises:
        ValueError: If validation fails
    """
    if len(lower) != 3:
        raise ValueError(f"{name} hsv_lower must have 3 values (got {len(lower)})")
    if len(upper) != 3:
        raise ValueError(f"{name} hsv_upper must have 3 values (got {len(upper)})")

    h_min, s_min, v_min = lower
    h_max, s_max, v_max = upper

    # Hue: 0-179 (OpenCV uses 0-179, not 0-360)
    if not (0 <= h_min <= 179):
        raise ValueError(f"h_min must be 0-179 (got {h_min})")
    if not (0 <= h_max <= 179):
        raise ValueError(f"h_max must be 0-179 (got {h_max})")

    # Saturation: 0-255
    if not (0 <= s_min <= 255):
        raise ValueError(f"s_min must be 0-255 (got {s_min})")
    if not (0 <= s_max <= 255):
        raise ValueError(f"s_max must be 0-255 (got {s_max})")

    # Value: 0-255
    if not (0 <= v_min <= 255):
        raise ValueError(f"v_min must be 0-255 (got {v_min})")
    if not (0 <= v_max <= 255):
        raise ValueError(f"v_max must be 0-255 (got {v_max})")

    # Range checks (lower < upper), except for hue which can wrap around
    if s_min > s_max:
        raise ValueError(f"s_min ({s_min}) must be <= s_max ({s_max})")
    if v_min > v_max:
        raise ValueError(f"v_min ({v_min}) must be <= v_max ({v_max})")


def _flatten_config(nested: Dict[str, Any]) -> Dict[str, Any]:
    """Convert nested config dict to flat dict for DetectorConfig."""
    flat = {}

    # Player config
    if "player" in nested:
        player = nested["player"]
        if "color_range" in player:
            cr = player["color_range"]
            flat["player_hsv_lower"] = tuple(cr.get("hsv_lower", (10, 55, 55)))     # Calibrated defaults (Nov 9, 2025)
            flat["player_hsv_upper"] = tuple(cr.get("hsv_upper", (40, 240, 255)))   # Calibrated defaults (Nov 9, 2025)
        flat["min_blob_size"] = player.get("blob_size_min", 4)
        flat["max_blob_size"] = player.get("blob_size_max", 100)
        flat["min_circularity"] = player.get("circularity_min", 0.60)
    
    # Other players config
    if "other_players" in nested:
        other = nested["other_players"]
        if "color_ranges" in other:
            flat["other_player_hsv_ranges"] = [
                (tuple(r["hsv_lower"]), tuple(r["hsv_upper"]))
                for r in other["color_ranges"]
            ]
        flat["min_circularity_other"] = other.get("circularity_min", 0.50)
        flat["max_blob_size_other"] = other.get("blob_size_max", 80)
    
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
        player_hsv_lower=config_dict.get("player_hsv_lower", (10, 55, 55)),      # Calibrated defaults (Nov 9, 2025)
        player_hsv_upper=config_dict.get("player_hsv_upper", (40, 240, 255)),    # Calibrated defaults (Nov 9, 2025)
        other_player_hsv_ranges=config_dict.get("other_player_hsv_ranges", None),
        min_blob_size=config_dict.get("min_blob_size", 4),
        max_blob_size=config_dict.get("max_blob_size", 100),
        max_blob_size_other=config_dict.get("max_blob_size_other", 80),
        min_circularity=config_dict.get("min_circularity", 0.60),
        min_circularity_other=config_dict.get("min_circularity_other", 0.50),
        min_aspect_ratio=config_dict.get("min_aspect_ratio", 0.5),
        max_aspect_ratio=config_dict.get("max_aspect_ratio", 2.0),
        enable_contrast_validation=config_dict.get("enable_contrast_validation", False),
        min_contrast_ratio=config_dict.get("min_contrast_ratio", 1.15),
        temporal_smoothing=config_dict.get("temporal_smoothing", True),
        smoothing_alpha=config_dict.get("smoothing_alpha", 0.3)
    )
