"""Mac Bridge - Network integration with Mac controller (msmacro-core).

Provides:
- UDP server on port 5001 for injection commands from Mac
- TCP server on port 5000 for control plane
- UDP event streaming to Mac on port 5002
- Mode synchronization and heartbeats
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from .protocol import (
    PROTOCOL_VERSION,
    DEFAULT_MAC_IP,
    DEFAULT_UDP_PORT,
    DEFAULT_TCP_PORT,
    DEFAULT_EVENTS_PORT,
    HEARTBEAT_INTERVAL,
    make_ack,
    make_pong,
    make_status,
)
from .udp_streamer import UDPEventStreamer

if TYPE_CHECKING:
    from ..io.hidio import LinuxHIDWriter

logger = logging.getLogger(__name__)


@dataclass
class BridgeStats:
    """Statistics for Mac bridge."""
    start_time: float = field(default_factory=time.monotonic)
    udp_packets_received: int = 0
    udp_packets_sent: int = 0
    tcp_connections: int = 0
    tcp_messages: int = 0
    hid_writes: int = 0

    @property
    def uptime(self) -> float:
        return time.monotonic() - self.start_time

    def to_dict(self) -> dict:
        return {
            "uptime": self.uptime,
            "udp_packets_received": self.udp_packets_received,
            "udp_packets_sent": self.udp_packets_sent,
            "tcp_connections": self.tcp_connections,
            "tcp_messages": self.tcp_messages,
            "hid_writes": self.hid_writes,
        }


class MacBridge:
    """Network bridge to Mac controller.

    Handles UDP/TCP communication with Mac's msmacro-core,
    enabling keyboard event streaming and HID injection.
    """

    def __init__(
        self,
        hid_writer: Optional["LinuxHIDWriter"] = None,
        mac_ip: str = DEFAULT_MAC_IP,
        udp_port: int = DEFAULT_UDP_PORT,
        tcp_port: int = DEFAULT_TCP_PORT,
        events_port: int = DEFAULT_EVENTS_PORT,
        mode_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize Mac bridge.

        Args:
            hid_writer: HID writer for injection (can be set later)
            mac_ip: Mac controller IP address
            udp_port: UDP port for injection commands
            tcp_port: TCP port for control plane
            events_port: UDP port for event streaming to Mac
            mode_callback: Callback when Mac requests mode change
        """
        self.hid_writer = hid_writer
        self.mac_ip = mac_ip
        self.udp_port = udp_port
        self.tcp_port = tcp_port
        self.events_port = events_port
        self.mode_callback = mode_callback

        self._stats = BridgeStats()
        self._current_mode = "BRIDGE"
        self._running = False

        # Servers
        self._udp_transport = None
        self._tcp_server = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Event streamer to Mac
        self._event_streamer = UDPEventStreamer(mac_ip, events_port)

    async def start(self) -> None:
        """Start the Mac bridge servers."""
        if self._running:
            logger.warning("Mac bridge already running")
            return

        self._running = True
        loop = asyncio.get_event_loop()

        # Start event streamer
        self._event_streamer.start()

        # Start UDP server
        self._udp_transport, _ = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self),
            local_addr=("0.0.0.0", self.udp_port),
        )
        logger.info(f"Mac bridge UDP server listening on port {self.udp_port}")

        # Start TCP server
        self._tcp_server = await asyncio.start_server(
            self._handle_tcp_client,
            "0.0.0.0",
            self.tcp_port,
        )
        logger.info(f"Mac bridge TCP server listening on port {self.tcp_port}")

        # Start heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(
            f"Mac bridge started: UDP={self.udp_port}, TCP={self.tcp_port}, "
            f"events -> {self.mac_ip}:{self.events_port}"
        )

    async def stop(self) -> None:
        """Stop the Mac bridge servers."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping Mac bridge...")

        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Stop event streamer
        self._event_streamer.stop()

        # Stop UDP server
        if self._udp_transport:
            self._udp_transport.close()

        # Stop TCP server
        if self._tcp_server:
            self._tcp_server.close()
            await self._tcp_server.wait_closed()

        logger.info(f"Mac bridge stopped. Stats: {self._stats.to_dict()}")

    def set_hid_writer(self, hid_writer: "LinuxHIDWriter") -> None:
        """Set or update the HID writer."""
        self.hid_writer = hid_writer
        logger.info("Mac bridge HID writer updated")

    def set_mode(self, mode: str) -> None:
        """Update current mode (called by daemon)."""
        self._current_mode = mode
        # Notify Mac of mode change
        self._event_streamer.send_mode_change(mode)

    def send_key_event(
        self,
        code: int,
        value: int,
        usage: int,
        modmask: int,
    ) -> bool:
        """Forward keyboard event to Mac (called by bridge).

        Args:
            code: evdev key code
            value: 0=up, 1=down, 2=repeat
            usage: HID usage ID
            modmask: Current modifier mask

        Returns:
            True if event was sent
        """
        return self._event_streamer.send_event(code, value, usage, modmask)

    @property
    def stats(self) -> dict:
        """Get combined statistics."""
        return {
            **self._stats.to_dict(),
            "streamer": self._event_streamer.stats,
        }

    # ---------- Internal methods ----------

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to Mac."""
        while self._running:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                self._event_streamer.send_heartbeat(
                    uptime=self._stats.uptime,
                    mode=self._current_mode,
                    extra_stats={
                        "hid_writes": self._stats.hid_writes,
                        "tcp_connections": self._stats.tcp_connections,
                    },
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def _handle_udp_message(
        self,
        msg: Dict[str, Any],
        addr: tuple,
        send_response: Callable[[bytes], None],
    ) -> None:
        """Handle incoming UDP message from Mac."""
        self._stats.udp_packets_received += 1
        msg_type = msg.get("type", "unknown")

        if msg_type == "ping":
            # Respond with pong for latency measurement
            response = make_pong(
                ping_ts=msg.get("ts", 0),
                seq=msg.get("payload", {}).get("seq", 0),
            )
            send_response(response.to_json())
            self._stats.udp_packets_sent += 1

        elif msg_type == "mode_change":
            # Mac requests mode change
            payload = msg.get("payload", {})
            new_mode = payload.get("mode", "BRIDGE")
            old_mode = self._current_mode
            self._current_mode = new_mode
            logger.info(f"Mode change from Mac: {old_mode} -> {new_mode}")

            # Notify daemon via callback
            if self.mode_callback:
                try:
                    self.mode_callback(new_mode)
                except Exception as e:
                    logger.error(f"Mode callback error: {e}")

            response = make_ack(ok=True, mode=new_mode)
            send_response(response.to_json())
            self._stats.udp_packets_sent += 1

        elif msg_type == "hid_report":
            # HID report injection from Mac
            payload = msg.get("payload", {})
            report_data = payload.get("report", [])
            ok = False

            if self.hid_writer and len(report_data) == 8:
                try:
                    self.hid_writer._write_with_retry(bytes(report_data))
                    ok = True
                    self._stats.hid_writes += 1
                    logger.debug(f"HID report injected: {report_data}")
                except Exception as e:
                    logger.error(f"HID injection failed: {e}")
            elif not self.hid_writer:
                logger.warning("HID writer not available for injection")
            else:
                logger.warning(f"Invalid HID report length: {len(report_data)}")

            response = make_ack(ok=ok)
            send_response(response.to_json())
            self._stats.udp_packets_sent += 1

        elif msg_type == "key_inject":
            # Legacy key injection (mod + keys)
            payload = msg.get("payload", {})
            logger.debug(f"Key inject: mod={payload.get('mod')}, keys={payload.get('keys')}")
            response = make_ack(ok=True)
            send_response(response.to_json())
            self._stats.udp_packets_sent += 1

        else:
            # Unknown message type - echo back
            send_response(json.dumps(msg, separators=(",", ":")).encode("utf-8"))
            self._stats.udp_packets_sent += 1

    async def _handle_tcp_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle TCP control plane connection."""
        addr = writer.get_extra_info("peername")
        logger.info(f"TCP connection from {addr[0]}:{addr[1]}")
        self._stats.tcp_connections += 1

        try:
            while True:
                data = await asyncio.wait_for(reader.readline(), timeout=60.0)
                if not data:
                    break

                self._stats.tcp_messages += 1

                try:
                    msg = json.loads(data.decode("utf-8"))
                    msg_type = msg.get("type", "unknown")

                    if msg_type == "ping":
                        response = make_pong(
                            ping_ts=msg.get("ts", 0),
                            seq=msg.get("payload", {}).get("seq", 0),
                        )

                    elif msg_type == "status":
                        response = make_status(
                            mode=self._current_mode,
                            uptime=self._stats.uptime,
                            stats=self._stats.to_dict(),
                            keyboard_connected=True,  # TODO: Check actual device
                            hid_ready=self.hid_writer is not None,
                        )

                    elif msg_type == "set_mode":
                        mode = msg.get("payload", {}).get("mode", "BRIDGE")
                        self._current_mode = mode
                        logger.info(f"Mode change via TCP: {mode}")
                        if self.mode_callback:
                            try:
                                self.mode_callback(mode)
                            except Exception as e:
                                logger.error(f"Mode callback error: {e}")
                        response = make_ack(ok=True, mode=mode)

                    else:
                        # Echo unknown messages
                        response_data = data
                        writer.write(response_data)
                        await writer.drain()
                        continue

                    writer.write(response.to_json() + b"\n")
                    await writer.drain()

                except json.JSONDecodeError:
                    writer.write(data)
                    await writer.drain()

        except asyncio.TimeoutError:
            logger.debug(f"TCP timeout from {addr[0]}:{addr[1]}")
        except ConnectionResetError:
            logger.debug(f"TCP connection reset from {addr[0]}:{addr[1]}")
        except Exception as e:
            logger.error(f"TCP error from {addr[0]}:{addr[1]}: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.debug(f"TCP disconnected from {addr[0]}:{addr[1]}")


class _UDPProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for Mac bridge."""

    def __init__(self, bridge: MacBridge):
        self.bridge = bridge
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple):
        try:
            msg = json.loads(data.decode("utf-8"))
            self.bridge._handle_udp_message(
                msg,
                addr,
                lambda resp: self.transport.sendto(resp, addr),
            )
        except json.JSONDecodeError:
            # Echo raw data back
            self.transport.sendto(data, addr)
        except Exception as e:
            logger.error(f"UDP error: {e}")

    def error_received(self, exc):
        logger.error(f"UDP error received: {exc}")
