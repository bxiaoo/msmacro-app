"""Protocol constants and helpers for Mac bridge communication.

Defines message types, ports, and encoding/decoding helpers for
communication between Pi daemon and Mac controller.
"""

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Protocol version - increment when breaking changes are made
PROTOCOL_VERSION = 2

# Default network configuration
DEFAULT_MAC_IP = "10.0.0.1"
DEFAULT_UDP_PORT = 5001      # Injection commands from Mac
DEFAULT_TCP_PORT = 5000      # Control plane
DEFAULT_EVENTS_PORT = 5002   # Keyboard events to Mac

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 1.0


@dataclass
class Message:
    """Protocol message wrapper."""
    type: str
    ts: float
    payload: Dict[str, Any]

    def to_json(self) -> bytes:
        """Serialize to JSON bytes."""
        return json.dumps({
            "type": self.type,
            "ts": self.ts,
            "payload": self.payload,
        }, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_json(cls, data: bytes) -> "Message":
        """Deserialize from JSON bytes."""
        d = json.loads(data.decode("utf-8"))
        return cls(
            type=d.get("type", "unknown"),
            ts=d.get("ts", 0),
            payload=d.get("payload", {}),
        )


def make_ack(ok: bool = True, **extra) -> Message:
    """Create an acknowledgment message."""
    return Message(
        type="ack",
        ts=time.perf_counter(),
        payload={"ok": ok, **extra},
    )


def make_pong(ping_ts: float, seq: int = 0) -> Message:
    """Create a pong response message."""
    return Message(
        type="pong",
        ts=time.perf_counter(),
        payload={"ping_ts": ping_ts, "seq": seq},
    )


def make_status(
    mode: str,
    uptime: float,
    stats: Dict[str, Any],
    keyboard_connected: bool = True,
    hid_ready: bool = True,
) -> Message:
    """Create a status response message."""
    return Message(
        type="status_response",
        ts=time.perf_counter(),
        payload={
            "version": PROTOCOL_VERSION,
            "mode": mode,
            "uptime": uptime,
            "keyboard_connected": keyboard_connected,
            "hid_ready": hid_ready,
            "stats": stats,
        },
    )
