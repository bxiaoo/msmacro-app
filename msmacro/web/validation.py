from __future__ import annotations
from pathlib import Path


def safe_record_path(base_dir: Path, name: str) -> Path:
    """Safely resolve a recording path, preventing directory traversal."""
    base = Path(base_dir).resolve()
    
    # Clean the name
    name = str(name).strip().strip("/")
    if not name:
        raise ValueError("Empty name")
    
    # Check for dangerous patterns
    if ".." in name or name.startswith("/"):
        raise ValueError(f"Invalid path: {name}")
    
    # Add .json extension if missing
    if not name.endswith(".json"):
        name = f"{name}.json"
    
    # Resolve the full path
    full_path = (base / name).resolve()
    
    # Ensure it's within base_dir
    if not str(full_path).startswith(str(base)):
        raise ValueError(f"Path outside base directory: {name}")
    
    return full_path


def validate_play_payload(data):
    """Validate play API payload."""
    if not isinstance(data, dict):
        return False, "payload must be an object"
    
    # Check for either names (playlist) or file (single)
    has_names = "names" in data
    has_file = "file" in data
    
    if not has_names and not has_file:
        return False, "either 'names' or 'file' required"
    
    if has_names:
        if not isinstance(data["names"], list):
            return False, "'names' must be a list"
        if not data["names"]:
            return False, "'names' cannot be empty"
        for name in data["names"]:
            if not isinstance(name, str):
                return False, "all names must be strings"
    
    if has_file:
        if not isinstance(data["file"], str):
            return False, "'file' must be a string"
    
    # Validate optional parameters
    if "speed" in data:
        try:
            speed = float(data["speed"])
            if speed <= 0 or speed > 10:
                return False, "speed must be between 0 and 10"
        except (ValueError, TypeError):
            return False, "speed must be a number"
    
    if "loop" in data:
        try:
            loop = int(data["loop"])
            if loop < 1 or loop > 1000:
                return False, "loop must be between 1 and 1000"
        except (ValueError, TypeError):
            return False, "loop must be an integer"
    
    return True, None


def validate_rename_payload(data):
    """Validate rename API payload."""
    if not isinstance(data, dict):
        return False, "payload must be an object"
    
    if not data.get("old"):
        return False, "'old' name required"
    
    if not data.get("new"):
        return False, "'new' name required"
    
    old = str(data["old"]).strip()
    new = str(data["new"]).strip()
    
    if not old or not new:
        return False, "names cannot be empty"
    
    # Check for dangerous patterns
    for name in [old, new]:
        if ".." in name or name.startswith("/"):
            return False, f"invalid path: {name}"
    
    return True, None


def validate_record_stop_payload(data):
    """Validate record stop API payload."""
    if not isinstance(data, dict):
        data = {}  # Allow empty payload
    
    action = data.get("action", "").lower()
    if action and action not in ("save", "discard", ""):
        return False, "action must be 'save', 'discard', or empty"
    
    if action == "save":
        name = data.get("name", "").strip()
        if not name:
            return False, "name required when action is 'save'"
        if ".." in name or name.startswith("/"):
            return False, f"invalid name: {name}"
    
    return True, None
