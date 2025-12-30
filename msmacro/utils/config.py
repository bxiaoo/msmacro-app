import os
import platform
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HIDG = "/dev/hidg0"
DEFAULT_RECDIR = Path(
    os.environ.get("MSMACRO_RECDIR", str(Path.home() / ".local/share/msmacro/records"))
)
DEFAULT_SKILLSDIR = Path(
    os.environ.get("MSMACRO_SKILLSDIR", str(Path.home() / ".local/share/msmacro/skills"))
)
DEFAULT_CALIBRATION_DIR = Path(
    os.environ.get("MSMACRO_CALIBRATION_DIR", str(Path.home() / ".local/share/msmacro/calibration"))
)

# Platform-aware socket path: use /tmp on macOS, /run on Linux
if platform.system() == "Darwin":
    _default_socket = "/tmp/msmacro.sock"
else:
    _default_socket = "/run/msmacro.sock"
DEFAULT_SOCKET = os.environ.get("MSMACRO_SOCKET", _default_socket)

# Mac bridge network settings
MAC_BRIDGE_ENABLED = os.environ.get("MSMACRO_MAC_BRIDGE_ENABLED", "false").lower() == "true"
MAC_IP = os.environ.get("MSMACRO_MAC_IP", "10.0.0.1")
MAC_UDP_PORT = int(os.environ.get("MSMACRO_MAC_UDP_PORT", "5001"))
MAC_TCP_PORT = int(os.environ.get("MSMACRO_MAC_TCP_PORT", "5000"))
MAC_EVENTS_PORT = int(os.environ.get("MSMACRO_MAC_EVENTS_PORT", "5002"))

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
    # Mac bridge settings
    mac_bridge_enabled: bool = MAC_BRIDGE_ENABLED
    mac_ip: str = MAC_IP
    mac_udp_port: int = MAC_UDP_PORT
    mac_tcp_port: int = MAC_TCP_PORT
    mac_events_port: int = MAC_EVENTS_PORT

SETTINGS = Settings()
