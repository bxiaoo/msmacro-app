"""Network bridge module for Mac controller communication.

This module provides network integration with the Mac controller (msmacro-core),
enabling:
- UDP event streaming (keyboard events to Mac)
- UDP/TCP command server (injection commands from Mac)
- Mode synchronization between Pi and Mac
"""

from .mac_bridge import MacBridge
from .udp_streamer import UDPEventStreamer

__all__ = ["MacBridge", "UDPEventStreamer"]
