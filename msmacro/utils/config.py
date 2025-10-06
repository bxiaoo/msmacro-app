import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HIDG = "/dev/hidg0"
DEFAULT_RECDIR = Path(
    os.environ.get("MSMACRO_RECDIR", str(Path.home() / ".local/share/msmacro/records"))
)
DEFAULT_SKILLSDIR = Path(
    os.environ.get("MSMACRO_SKILLSDIR", str(Path.home() / ".local/share/msmacro/skills"))
)
DEFAULT_SOCKET = os.environ.get("MSMACRO_SOCKET", "/run/msmacro.sock")

@dataclass
class Settings:
    hidg_path: str = DEFAULT_HIDG
    record_dir: Path = DEFAULT_RECDIR
    skills_dir: Path = DEFAULT_SKILLSDIR
    stop_hotkey: str = "LCTRL+Q"
    record_hotkey: str = "LCTRL+R"
    min_hold_s: float = 0.083
    min_repeat_same_key_s: float = 0.09
    socket_path: str = DEFAULT_SOCKET

SETTINGS = Settings()
