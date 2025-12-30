"""Non-blocking UDP event streamer to Mac controller.

Sends keyboard events via UDP with fire-and-forget semantics:
- Non-blocking socket operations
- Drops packets if would block (latency > reliability)
- JSON-encoded messages with timestamps
- Periodic heartbeats with Pi-side statistics
"""

import json
import logging
import socket
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Connection recovery settings
MAX_CONSECUTIVE_ERRORS = 10  # Recreate socket after this many errors


@dataclass
class KeyEvent:
    """Keyboard event data."""
    code: int       # evdev key code
    value: int      # 0=up, 1=down, 2=repeat
    usage: int      # HID usage ID
    modmask: int    # Current modifier state
    timestamp: float  # Event timestamp


class UDPEventStreamer:
    """Non-blocking UDP event sender to Mac controller."""

    def __init__(
        self,
        mac_ip: str = "10.0.0.1",
        mac_port: int = 5002,
    ):
        """Initialize UDP streamer.

        Args:
            mac_ip: Mac controller IP address
            mac_port: UDP port for key events
        """
        self.addr = (mac_ip, mac_port)
        self._sock: Optional[socket.socket] = None
        self._packets_sent = 0
        self._packets_dropped = 0
        self._first_send_logged = False
        self._last_stats_log = 0

        # Heartbeat tracking
        self._heartbeat_seq = 0
        self._heartbeats_sent = 0
        self._first_heartbeat_logged = False

        # Connection recovery tracking
        self._consecutive_errors = 0
        self._socket_recreations = 0

    def start(self) -> None:
        """Initialize the UDP socket."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        logger.info(
            f"UDP streamer started: sending key events to {self.addr[0]}:{self.addr[1]} (UDP). "
            f"Waiting for keyboard events to forward..."
        )

    def stop(self) -> None:
        """Close the UDP socket."""
        if self._sock:
            self._sock.close()
            self._sock = None
        logger.info(
            f"UDP streamer stopped. Sent: {self._packets_sent}, "
            f"Dropped: {self._packets_dropped}"
        )

    def send_event(
        self,
        code: int,
        value: int,
        usage: int,
        modmask: int,
    ) -> bool:
        """Send key event to Mac (non-blocking).

        Args:
            code: evdev key code
            value: 0=up, 1=down, 2=repeat
            usage: HID usage ID
            modmask: Current modifier bit mask

        Returns:
            True if packet was sent, False if dropped
        """
        if self._sock is None:
            logger.warning("UDP streamer not started")
            return False

        msg = {
            "type": "key_event",
            "ts": time.perf_counter(),
            "payload": {
                "code": code,
                "value": value,
                "usage": usage,
                "modmask": modmask,
            },
        }

        try:
            data = json.dumps(msg, separators=(",", ":")).encode("utf-8")
            self._sock.sendto(data, self.addr)
            self._packets_sent += 1
            self._consecutive_errors = 0  # Reset on success

            # Log first successful send
            if not self._first_send_logged:
                self._first_send_logged = True
                logger.info(
                    f"First UDP packet sent to {self.addr[0]}:{self.addr[1]} - "
                    f"keyboard events are being streamed to Mac"
                )

            # Log stats every 100 packets
            if self._packets_sent % 100 == 0:
                logger.info(
                    f"UDP streamer stats: sent={self._packets_sent}, "
                    f"dropped={self._packets_dropped}, target={self.addr[0]}:{self.addr[1]}"
                )

            logger.debug(
                f"UDP sent: code={code} value={value} usage={usage} mod=0x{modmask:02x}"
            )
            return True

        except BlockingIOError:
            # Would block - drop packet (latency > reliability)
            self._packets_dropped += 1
            self._consecutive_errors += 1
            if self._packets_dropped == 1:
                logger.warning(
                    f"First UDP packet dropped (socket would block) - "
                    f"target: {self.addr[0]}:{self.addr[1]}"
                )
            logger.debug(f"UDP packet dropped (would block)")
            self._check_and_recover()
            return False

        except OSError as e:
            self._packets_dropped += 1
            self._consecutive_errors += 1
            logger.warning(f"UDP send error to {self.addr[0]}:{self.addr[1]}: {e}")
            self._check_and_recover()
            return False

    def send_raw_event(self, event: KeyEvent) -> bool:
        """Send a KeyEvent object.

        Args:
            event: KeyEvent to send

        Returns:
            True if packet was sent
        """
        return self.send_event(
            code=event.code,
            value=event.value,
            usage=event.usage,
            modmask=event.modmask,
        )

    def send_heartbeat(
        self,
        uptime: float,
        mode: str,
        extra_stats: Optional[Dict] = None,
    ) -> bool:
        """Send heartbeat with Pi stats to Mac.

        Args:
            uptime: Pi bridge uptime in seconds
            mode: Current bridge mode (BRIDGE, RECORDING, etc.)
            extra_stats: Additional stats to include (events_processed, hid_writes, etc.)

        Returns:
            True if heartbeat was sent, False if dropped
        """
        if self._sock is None:
            logger.warning("UDP streamer not started - cannot send heartbeat")
            return False

        self._heartbeat_seq += 1
        msg = {
            "type": "heartbeat",
            "ts": time.perf_counter(),
            "payload": {
                "seq": self._heartbeat_seq,
                "uptime": uptime,
                "stats": {
                    "packets_sent": self._packets_sent,
                    "packets_dropped": self._packets_dropped,
                    "mode": mode,
                    **(extra_stats or {}),
                },
            },
        }

        try:
            data = json.dumps(msg, separators=(",", ":")).encode("utf-8")
            self._sock.sendto(data, self.addr)
            self._heartbeats_sent += 1
            self._consecutive_errors = 0  # Reset on success

            # Log first successful heartbeat
            if not self._first_heartbeat_logged:
                self._first_heartbeat_logged = True
                logger.info(
                    f"First heartbeat sent to {self.addr[0]}:{self.addr[1]} - "
                    f"Mac controller can now track Pi connectivity"
                )

            logger.debug(f"Heartbeat #{self._heartbeat_seq} sent (uptime={uptime:.1f}s)")
            return True

        except BlockingIOError:
            self._consecutive_errors += 1
            logger.debug("Heartbeat dropped (would block)")
            self._check_and_recover()
            return False

        except OSError as e:
            self._consecutive_errors += 1
            logger.warning(f"Heartbeat send error: {e}")
            self._check_and_recover()
            return False

    def send_mode_change(self, new_mode: str) -> bool:
        """Send mode change notification to Mac.

        Args:
            new_mode: New mode name (BRIDGE, RECORDING, PLAYING, etc.)

        Returns:
            True if notification was sent
        """
        if self._sock is None:
            return False

        msg = {
            "type": "mode_change",
            "ts": time.perf_counter(),
            "payload": {
                "mode": new_mode,
            },
        }

        try:
            data = json.dumps(msg, separators=(",", ":")).encode("utf-8")
            self._sock.sendto(data, self.addr)
            self._consecutive_errors = 0
            logger.info(f"Mode change notification sent to Mac: {new_mode}")
            return True
        except (BlockingIOError, OSError) as e:
            self._consecutive_errors += 1
            logger.warning(f"Failed to send mode change notification: {e}")
            self._check_and_recover()
            return False

    def _check_and_recover(self) -> None:
        """Check if socket needs recreation after consecutive errors."""
        if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            logger.warning(
                f"Recreating UDP socket after {self._consecutive_errors} consecutive errors"
            )
            self._recreate_socket()

    def _recreate_socket(self) -> None:
        """Recreate the UDP socket to recover from network issues."""
        try:
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass

            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setblocking(False)
            self._consecutive_errors = 0
            self._socket_recreations += 1
            logger.info(
                f"UDP socket recreated successfully (total recreations: {self._socket_recreations})"
            )
        except Exception as e:
            logger.error(f"Failed to recreate UDP socket: {e}")

    @property
    def stats(self) -> dict:
        """Get streamer statistics."""
        return {
            "packets_sent": self._packets_sent,
            "packets_dropped": self._packets_dropped,
            "heartbeats_sent": self._heartbeats_sent,
            "consecutive_errors": self._consecutive_errors,
            "socket_recreations": self._socket_recreations,
            "target": f"{self.addr[0]}:{self.addr[1]}",
        }
