import re
from pathlib import Path

SAFE_NAME = re.compile(r'^[A-Za-z0-9._-]+$')

def safe_record_path(record_dir: Path, name: str) -> Path:
    """Return a safe path inside record_dir for a given name (adds .json if missing)."""
    if not name.endswith(".json"):
        name += ".json"
    leaf = Path(name).name  # basename only
    if not SAFE_NAME.match(leaf):
        raise ValueError("Invalid filename")
    p = (record_dir / leaf).resolve()
    if p.parent != record_dir.resolve():
        raise ValueError("Invalid path")
    return p
