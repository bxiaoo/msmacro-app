# /opt/msmacro-app/msmacro/daemon.py
from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Optional, Dict, Any

from evdev import InputDevice, ecodes  # for hotkey watcher

from .config import SETTINGS
from .keyboard import find_keyboard_event
from .bridge import Bridge
from .player import Player
from .recorder import Recorder
from .ipc import start_server
from .keymap import parse_hotkey, usage_from_ecode, is_modifier, mod_bit

# events are optional; make emit() a no-op if events module is absent
try:
    from .events import emit  # type: ignore
except Exception:  # pragma: no cover
    def emit(*_args, **_kwargs):  # type: ignore
        return


# ---------- utility: wait for a hotkey press->release (e.g., LCTL+Q) ----------
async def _wait_hotkey_release(evdev_path: str, spec: str) -> None:
    """Return when MOD+KEY is pressed and then released (edge-triggered)."""
    mod_ec, key_ec = parse_hotkey(spec)
    key_usage = usage_from_ecode(key_ec)
    dev = InputDevice(evdev_path)
    try:
        with contextlib.suppress(Exception):
            dev.grab()
        modmask = 0
        down = set()
        armed = False
        async for ev in dev.async_read_loop():
            if ev.type != ecodes.EV_KEY:
                continue
            code, val = ev.code, ev.value
            if val == 2:  # auto-repeat
                continue
            is_down = (val == 1)
            # update simple state
            if is_modifier(code):
                bit = mod_bit(code)
                if is_down:
                    modmask |= bit
                else:
                    modmask &= (~bit) & 0xFF
            else:
                u = usage_from_ecode(code)
                if is_down:
                    down.add(u)
                else:
                    down.discard(u)
            mod_down = (modmask & mod_bit(mod_ec)) != 0
            curr = mod_down and (key_usage in down)
            if (not armed) and curr:
                armed = True
                continue
            if armed and (not curr) and (code in (mod_ec, key_ec)) and (val == 0):
                return
    finally:
        with contextlib.suppress(Exception):
            dev.ungrab()
        with contextlib.suppress(Exception):
            dev.close()


class MacroDaemon:
    """
    Modes:
      INIT → BRIDGE ↔ (RECORDING → POSTRECORD) / PLAYING → BRIDGE

    A single bridge task owns the keyboard in BRIDGE/POSTRECORD. Before PLAY/RECORD,
    the daemon cancels the bridge, performs the action, then restarts the bridge.

    Control socket path: SETTINGS.socket_path (printed on start).
    """

    def __init__(self, evdev_path: Optional[str] = None):
        self.evdev_path: Optional[str] = evdev_path
        self.mode: str = "INIT"

        # long-lived tasks
        self._bridge_task: Optional[asyncio.Task] = None
        self._play_task: Optional[asyncio.Task] = None
        self._record_task: Optional[asyncio.Task] = None

        # per-playback stop event (shared by hotkey watcher and IPC "stop")
        self._stop_event: Optional[asyncio.Event] = None

        # last captured actions (kept through POSTRECORD)
        self._last_actions: Optional[list] = None

        # lifetime blocker
        self._alive = asyncio.Event()

    # -------- lifecycle --------

    async def start(self):
        print(f"[daemon] control socket: {SETTINGS.socket_path}")
        server = await start_server(SETTINGS.socket_path, self.handle)
        Path(SETTINGS.record_dir).mkdir(parents=True, exist_ok=True)
        await self._ensure_bridge_started()
        try:
            await self._alive.wait()  # never set; keeps daemon alive
        finally:
            server.close()
            await server.wait_closed()

    async def _wait_for_keyboard(self):
        while True:
            try:
                if self.evdev_path and Path(self.evdev_path).exists():
                    return
                self.evdev_path = find_keyboard_event()
                emit("KEYBOARD", path=self.evdev_path)
                return
            except SystemExit:
                pass
            except Exception as e:
                print(f"[daemon] keyboard probe error: {e}")
            await asyncio.sleep(0.5)

    # -------- bridge supervision --------

    async def _ensure_bridge_started(self):
        """Start the live bridge loop if not running."""
        if self._bridge_task and not self._bridge_task.done():
            return
        await self._wait_for_keyboard()
        self.mode = "BRIDGE"
        emit("MODE", mode=self.mode)

        b = Bridge(
            self.evdev_path,
            SETTINGS.hidg_path,
            stop_hotkey=SETTINGS.stop_hotkey,
            record_hotkey=SETTINGS.record_hotkey,  # allow hotkey record in BRIDGE
            grab=True,
        )

        async def _loop():
            while True:
                try:
                    result = await b.run_bridge()
                except asyncio.CancelledError:
                    break
                if result == "RECORD":
                    # Cancel bridge and run record flow as its own task
                    await self._ensure_bridge_stopped()
                    self._record_task = asyncio.create_task(self._do_record())
                    try:
                        await self._record_task
                    finally:
                        self._record_task = None
                # else continue bridging

        self._bridge_task = asyncio.create_task(_loop())

    async def _ensure_bridge_stopped(self):
        """Cancel the live bridge loop, releasing the keyboard grab."""
        t = self._bridge_task
        if not t or t.done():
            self._bridge_task = None
            return
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
        self._bridge_task = None

    # -------- post-record choice window --------

    async def _choice_window(self, timeout_sec: float = 8.0) -> Optional[str]:
        """
        Show Save/Play/Discard menu using a temporary bridge instance that
        listens only for extra hotkeys. Returns selected label or None on timeout.
        """
        choices: Dict[str, str] = {
            "LCTL+S": "CHOICE_SAVE",
            "LCTL+P": "CHOICE_PLAY",
            "LCTL+D": "CHOICE_DISCARD",
        }

        b = Bridge(
            self.evdev_path,
            SETTINGS.hidg_path,
            stop_hotkey=SETTINGS.stop_hotkey,
            record_hotkey=None,
            grab=True,
            extra_hotkeys=choices,
        )
        emit("CHOICE_MENU", keys=list(choices.keys()))
        self.mode = "POSTRECORD"
        emit("MODE", mode=self.mode)

        task = asyncio.create_task(b.run_bridge())
        try:
            label = await asyncio.wait_for(task, timeout=timeout_sec)
            if label:
                emit("CHOICE_SELECTED", label=label)
            else:
                emit("CHOICE_SELECTED", label="STOP")
            return label
        except asyncio.TimeoutError:
            emit("CHOICE_TIMEOUT")
            with contextlib.suppress(asyncio.CancelledError):
                task.cancel()
                await task
            return None

    # -------- record / save / play primitives --------

    async def _do_record(self):
        """Record actions until stop chord; then show the post-record choices."""
        self.mode = "RECORDING"
        emit("MODE", mode=self.mode)
        emit("RECORD_START")

        # Dedicated recorder bridge (no record hotkey inside record mode)
        b = Bridge(
            self.evdev_path,
            SETTINGS.hidg_path,
            stop_hotkey=SETTINGS.stop_hotkey,
            record_hotkey=None,
            grab=True,
        )

        actions = await b.run_record()
        self._last_actions = actions or []
        emit("RECORD_STOP", count=len(self._last_actions))

        # Post-record loop: Save / Play (then loop) / Discard / timeout→exit
        while True:
            label = await self._choice_window(timeout_sec=8.0)
            if label == "CHOICE_SAVE":
                await self._save_last_timestamped()
                break
            elif label == "CHOICE_PLAY":
                await self._play_last_once()
                continue  # re-open the choice window after playing
            elif label == "CHOICE_DISCARD":
                self._last_actions = None
                emit("DISCARDED")
                break
            # timeout or STOP → end postrecord
            break

        self.mode = "BRIDGE"
        emit("MODE", mode=self.mode)
        await self._ensure_bridge_started()

    async def _save_last_timestamped(self):
        if not self._last_actions:
            return
        from datetime import datetime
        name = datetime.utcnow().strftime("rec_%Y%m%d_%H%M%S")
        rec = Recorder()
        rec.actions = self._last_actions
        rec.t0 = 0
        p = Path(SETTINGS.record_dir) / f"{name}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        rec.save(p)
        emit("SAVED", path=str(p))

    async def _play_last_once(self):
        if not self._last_actions:
            return
        tmp = Path(SETTINGS.record_dir) / "_temp_play.json"
        rec = Recorder()
        rec.actions = self._last_actions
        rec.t0 = 0
        tmp.parent.mkdir(parents=True, exist_ok=True)
        rec.save(tmp)
        await self._do_play(str(tmp))

    async def _do_play(self, path: str, *, speed=1.0, jt=0.0, jh=0.0, loop=1):
        """Play a recording; supports both hotkey stop and IPC stop."""
        await self._ensure_bridge_stopped()  # release keyboard grab for watcher

        self.mode = "PLAYING"
        emit("MODE", mode=self.mode)
        emit("PLAY_START", file=str(path))

        self._stop_event = asyncio.Event()
        player = Player(SETTINGS.hidg_path)

        if not self.evdev_path or not Path(self.evdev_path).exists():
            await self._wait_for_keyboard()

        # Hotkey watcher (e.g., LCTL+Q)
        watcher = asyncio.create_task(_wait_hotkey_release(self.evdev_path, SETTINGS.stop_hotkey))

        async def _trip():
            await watcher
            self._stop_event.set()

        trip = asyncio.create_task(_trip())

        try:
            await player.play(
                path,
                speed=speed,
                jitter_time=jt,
                jitter_hold=jh,
                min_hold_s=SETTINGS.min_hold_s,
                min_repeat_same_key_s=SETTINGS.min_repeat_same_key_s,
                loop=loop,
                stop_event=self._stop_event,
            )
        finally:
            for t in (trip, watcher):
                if t and not t.done():
                    t.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await t

        emit("PLAY_STOP")
        self.mode = "BRIDGE"
        emit("MODE", mode=self.mode)
        await self._ensure_bridge_started()

    # -------- control socket handler --------

    async def handle(self, msg: Dict[str, Any]):
        """Handle a single JSON command coming from CLI/Web."""
        cmd = (msg.get("cmd") or "").strip()

        if cmd == "status":
            return {
                "mode": self.mode,
                "record_dir": str(SETTINGS.record_dir),
                "socket": SETTINGS.socket_path,
                "keyboard": self.evdev_path,
                "have_last_actions": bool(self._last_actions),
            }

        if cmd == "list":
            p = Path(SETTINGS.record_dir)
            files = sorted(x.name for x in p.glob("*.json")) if p.exists() else []
            return {"files": files}

        if cmd == "play":
            if self.mode not in ("BRIDGE",):
                raise RuntimeError(f"cannot play from mode {self.mode}")
            name = msg.get("file")
            if not name:
                raise RuntimeError("missing file")
            p = Path(name)
            if not p.exists():
                alt = Path(SETTINGS.record_dir) / (name if name.endswith(".json") else name + ".json")
                if not alt.exists():
                    raise RuntimeError(f"not found: {name}")
                p = alt
            kwargs = {
                "speed": float(msg.get("speed", 1.0)),
                "jt": float(msg.get("jitter_time", 0.0)),
                "jh": float(msg.get("jitter_hold", 0.0)),
                "loop": int(msg.get("loop", 1)),
            }
            asyncio.create_task(self._do_play(str(p), **kwargs))
            return {"playing": str(p), **kwargs}

        if cmd == "stop":
            # Stop PLAY or RECORD from any controller (web/cli/hotkey)
            if self.mode == "PLAYING" and self._stop_event:
                self._stop_event.set()
                return {"stopping": "playback"}
            if self.mode == "RECORDING" and self._record_task and not self._record_task.done():
                self._record_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._record_task
                self._record_task = None
                self.mode = "BRIDGE"
                emit("MODE", mode=self.mode)
                await self._ensure_bridge_started()
                return {"stopping": "recording"}
            return {"mode": self.mode}

        if cmd == "record_start":
            if self.mode not in ("BRIDGE",):
                raise RuntimeError(f"cannot start record from mode {self.mode}")
            await self._ensure_bridge_stopped()
            self._record_task = asyncio.create_task(self._do_record())
            return {"recording": True}

        if cmd == "save_last":
            if not self._last_actions:
                raise RuntimeError("no last recording")
            name = msg.get("name")
            if not name:
                raise RuntimeError("missing name")
            rec = Recorder()
            rec.actions = self._last_actions
            rec.t0 = 0
            path = Path(SETTINGS.record_dir) / f"{name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            rec.save(path)
            emit("SAVED", path=str(path))
            return {"saved": str(path)}

        raise RuntimeError(f"unknown cmd: {cmd}")


# -------- CLI entry point --------

__all__ = ["MacroDaemon", "run_daemon"]

async def run_daemon(evdev_path: Optional[str] = None):
    """
    Entry point used by cli.py: asyncio.run(run_daemon(args.device))
    evdev_path may be 'auto' (case-insensitive) to probe automatically.
    """
    if isinstance(evdev_path, str) and evdev_path.lower() == "auto":
        evdev_path = None
    d = MacroDaemon(evdev_path=evdev_path)
    await d.start()
