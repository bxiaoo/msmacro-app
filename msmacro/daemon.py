import asyncio
from pathlib import Path
from typing import Optional

from evdev import InputDevice, ecodes

from .config import SETTINGS
from .keyboard import find_keyboard_event
from .bridge import Bridge
from .player import Player
from .recorder import Recorder
from .ipc import start_server
from .events import emit
from .keymap import parse_hotkey, usage_from_ecode, is_modifier, mod_bit


# --- internal: wait for a MOD+KEY chord to be pressed and then released ---
async def _wait_hotkey_release(evdev_path: str, spec: str) -> None:
    """
    Watch evdev device for a hotkey (e.g., 'LCTL+Q'); return when chord is released.
    Used to stop playback started from Web/CLI.
    """
    mod_ec, key_ec = parse_hotkey(spec)
    key_usage = usage_from_ecode(key_ec)
    dev = InputDevice(evdev_path)
    try:
        try:
            dev.grab()
        except Exception:
            pass
        modmask = 0
        down = set()
        armed = False
        async for ev in dev.async_read_loop():
            if ev.type != ecodes.EV_KEY:
                continue
            code, val = ev.code, ev.value
            if val == 2:  # repeat
                continue
            is_down = (val == 1)
            if is_modifier(code):
                bit = mod_bit(code)
                if is_down:
                    modmask |= bit
                else:
                    modmask &= (~bit) & 0xFF
            else:
                usage = usage_from_ecode(code)
                if is_down:
                    down.add(usage)
                else:
                    down.discard(usage)
            mod_down = (modmask & mod_bit(mod_ec)) != 0
            curr = mod_down and (key_usage in down)
            if (not armed) and curr:
                armed = True
                continue
            if armed and (not curr) and (code in (mod_ec, key_ec)) and (val == 0):
                return
    finally:
        try:
            dev.ungrab()
        except Exception:
            pass
        try:
            dev.close()
        except Exception:
            pass


class MacroDaemon:
    """
    Background controller:
      - Exposes a UNIX control socket (SETTINGS.socket_path)
      - Emits JSON event lines via msmacro.events.emit() to /run/msmacro.events
      - States: INIT → BRIDGE ↔ (RECORDING → POSTRECORD) / PLAYING → BRIDGE
    """

    def __init__(self, evdev_path: Optional[str] = None):
        self.evdev_path = evdev_path
        self.mode = "INIT"
        self._stop_event = asyncio.Event()  # for stopping playback
        self._last_actions = None           # last recording kept until Save/Discard

    # ---- lifecycle ---------------------------------------------------------

    async def start(self):
        # Create control socket immediately so ctl works even before keyboard is ready
        server = await start_server(SETTINGS.socket_path, self.handle)
        print(f"[daemon] control socket: {SETTINGS.socket_path}")
        Path(SETTINGS.record_dir).mkdir(parents=True, exist_ok=True)
        try:
            await self._bridge_forever()
        finally:
            server.close()
            await server.wait_closed()

    async def _wait_for_keyboard(self):
        """Resolve a keyboard evdev device; retry until available."""
        while True:
            try:
                if self.evdev_path and Path(self.evdev_path).exists():
                    return
                self.evdev_path = find_keyboard_event()
                print(f"[daemon] keyboard: {self.evdev_path}")
                return
            except SystemExit:
                # no keyboard yet
                pass
            except Exception as e:
                print(f"[daemon] keyboard probe error: {e}")
            await asyncio.sleep(0.5)

    async def _bridge_forever(self):
        """Main loop: sit in BRIDGE, respond to hotkeys, never exit."""
        while True:
            await self._wait_for_keyboard()
            self.mode = "BRIDGE"
            emit("MODE", mode=self.mode)
            b = Bridge(
                self.evdev_path,
                SETTINGS.hidg_path,
                stop_hotkey=SETTINGS.stop_hotkey,
                record_hotkey=SETTINGS.record_hotkey,
                grab=True,
            )
            result = await b.run_bridge()
            if result == "RECORD":
                await self._do_record()
            # If result == "STOP": ignore → remain in daemon, continue bridging

    # ---- post-record choice window ----------------------------------------

    async def _choice_window(self, timeout_sec: float = 8.0) -> Optional[str]:
        """
        Open a short 'choice window' where:
          LCTL+S -> 'CHOICE_SAVE'
          LCTL+P -> 'CHOICE_PLAY'
          LCTL+D -> 'CHOICE_DISCARD'
        Returns the label, or None on timeout.
        """
        choices = {
            "LCTRL+S": "CHOICE_SAVE",
            "LCTRL+P": "CHOICE_PLAY",
            "LCTRL+D": "CHOICE_DISCARD",
        }
        emit("CHOICE_MENU", keys=list(choices.keys()))
        self.mode = "POSTRECORD"
        emit("MODE", mode=self.mode)
        b = Bridge(
            self.evdev_path,
            SETTINGS.hidg_path,
            stop_hotkey=SETTINGS.stop_hotkey,
            record_hotkey=SETTINGS.record_hotkey,
            grab=True,
            extra_hotkeys=choices,
        )
        try:
            label = await asyncio.wait_for(b.run_bridge(), timeout=timeout_sec)
            emit("CHOICE_SELECTED", label=label)
            return label
        except asyncio.TimeoutError:
            emit("CHOICE_TIMEOUT")
            return None

    # ---- actions -----------------------------------------------------------

    async def _do_record(self):
        """Record until stop hotkey; then present Save/Play/Discard loop."""
        self.mode = "RECORDING"
        emit("MODE", mode=self.mode)
        emit("RECORD_START")
        b = Bridge(
            self.evdev_path,
            SETTINGS.hidg_path,
            stop_hotkey=SETTINGS.stop_hotkey,
            record_hotkey=SETTINGS.record_hotkey,
            grab=True,
        )
        actions = await b.run_record()
        self._last_actions = actions or []
        emit("RECORD_STOP", count=len(self._last_actions))

        # Keep offering Save/Play/Discard until Save/Discard or a timeout
        while True:
            label = await self._choice_window(timeout_sec=8.0)
            if label == "CHOICE_SAVE":
                await self._save_last_timestamped()
                break
            elif label == "CHOICE_PLAY":
                # Play once; keep last_actions so we can save/discard after playback
                await self._play_last_once()
                continue
            elif label == "CHOICE_DISCARD":
                self._last_actions = None
                emit("DISCARDED")
                break
            else:
                # Timeout → return to bridge; keep last_actions in RAM (can save via CLI/web)
                break

        self.mode = "BRIDGE"
        emit("MODE", mode=self.mode)

    async def _save_last_timestamped(self):
        """Save last recording with a timestamped filename and clear it."""
        if self._last_actions is None:
            return
        from datetime import datetime

        name = datetime.utcnow().strftime("rec_%Y%m%d_%H%M%S")
        rec = Recorder()
        rec.actions = self._last_actions
        rec.t0 = 0
        path = Path(SETTINGS.record_dir) / f"{name}.json"
        rec.save(path)
        emit("SAVED", path=str(path))
        self._last_actions = None

    async def _play_last_once(self):
        """Play the last recording once; keep it in RAM for another choice."""
        if self._last_actions is None:
            return
        tmp = Path(SETTINGS.record_dir) / "_temp_play.json"
        rec = Recorder()
        rec.actions = self._last_actions
        rec.t0 = 0
        rec.save(tmp)
        await self._do_play(str(tmp))

    async def _do_play(self, path, *, speed=1.0, jt=0.0, jh=0.0, loop=1):
        """Enter PLAYING; allow LCTL+Q to stop; return to BRIDGE afterwards."""
        self.mode = "PLAYING"
        emit("MODE", mode=self.mode)
        emit("PLAY_START", file=str(path))
        self._stop_event = asyncio.Event()
        p = Player(SETTINGS.hidg_path)

        # Watcher that trips stop on the stop hotkey (e.g., LCTL+Q)
        watcher = asyncio.create_task(_wait_hotkey_release(self.evdev_path, SETTINGS.stop_hotkey))

        async def _trip():
            await watcher
            self._stop_event.set()

        trip = asyncio.create_task(_trip())

        try:
            await p.play(
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
                if not t.done():
                    t.cancel()
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass

        emit("PLAY_STOP")
        self.mode = "BRIDGE"
        emit("MODE", mode=self.mode)

    # ---- control API (daemon socket) --------------------------------------

    async def handle(self, msg: dict):
        """UNIX socket API handler (used by CLI/Web)."""
        cmd = msg.get("cmd")

        if cmd == "status":
            return {
                "mode": self.mode,
                "record_dir": str(SETTINGS.record_dir),
                "socket": SETTINGS.socket_path,
                "keyboard": self.evdev_path,
                "have_last_actions": bool(self._last_actions),
            }

        if cmd == "record_start":
            if self.mode != "BRIDGE":
                raise RuntimeError(f"cannot start record from mode {self.mode}")
            asyncio.create_task(self._do_record())
            return "recording"

        if cmd == "record_stop":
            # Post-process the last recording in RAM
            which = msg.get("action", "discard")
            name = msg.get("name")
            if self._last_actions is None:
                self._last_actions = []
            rec = Recorder()
            rec.actions = self._last_actions
            rec.t0 = 0
            Path(SETTINGS.record_dir).mkdir(parents=True, exist_ok=True)
            if which == "save":
                if not name:
                    raise RuntimeError("missing name")
                p = Path(SETTINGS.record_dir) / f"{name}.json"
                rec.save(p)
                self._last_actions = None
                emit("SAVED", path=str(p))
                return {"saved": str(p)}
            if which == "play_now":
                tmp = Path(SETTINGS.record_dir) / "_temp_play.json"
                rec.save(tmp)
                # keep last_actions so user can still save/discard afterwards
                asyncio.create_task(self._do_play(str(tmp)))
                return {"playing": str(tmp)}
            # default: discard
            self._last_actions = None
            emit("DISCARDED")
            return {"discarded": True}

        if cmd == "play":
            if self.mode != "BRIDGE":
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

    # stop playback (or no-op in bridge)
        if cmd == "stop":
            if self.mode == "PLAYING":
                self._stop_event.set()
                return {"stopping": "playback"}
            return {"mode": self.mode}

        if cmd == "list":
            p = Path(SETTINGS.record_dir)
            files = sorted(str(x.name) for x in p.glob("*.json")) if p.exists() else []
            return {"files": files}

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
            rec.save(path)
            self._last_actions = None
            emit("SAVED", path=str(path))
            return {"saved": str(path)}

        raise RuntimeError(f"unknown cmd: {cmd}")


# entry point for cli.py
async def run_daemon(evdev_path: Optional[str] = None):
    d = MacroDaemon(evdev_path=evdev_path)
    await d.start()
