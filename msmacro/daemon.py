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


# --- watch for MOD+KEY pressed+released (for stopping PLAY with hotkey) ---
async def _wait_hotkey_release(evdev_path: str, spec: str) -> None:
    mod_ec, key_ec = parse_hotkey(spec)
    key_usage = usage_from_ecode(key_ec)
    dev = InputDevice(evdev_path)
    try:
        try: dev.grab()
        except Exception: pass
        modmask = 0; down = set(); armed = False
        async for ev in dev.async_read_loop():
            if ev.type != ecodes.EV_KEY: continue
            code, val = ev.code, ev.value
            if val == 2: continue  # repeat
            is_down = (val == 1)
            if is_modifier(code):
                bit = mod_bit(code)
                if is_down: modmask |= bit
                else:       modmask &= (~bit) & 0xFF
            else:
                usage = usage_from_ecode(code)
                if is_down: down.add(usage)
                else:       down.discard(usage)
            mod_down = (modmask & mod_bit(mod_ec)) != 0
            curr = mod_down and (key_usage in down)
            if (not armed) and curr:
                armed = True; continue
            if armed and (not curr) and (code in (mod_ec, key_ec)) and (val == 0):
                return
    finally:
        try: dev.ungrab()
        except Exception: pass
        try: dev.close()
        except Exception: pass


class MacroDaemon:
    """
    States: INIT → BRIDGE ↔ (RECORDING → POSTRECORD) / PLAYING → BRIDGE
    Exposes a UNIX socket (ipc.start_server) handled by self.handle()
    Emits JSON lines via events.emit() to /run/msmacro.events
    """
    def __init__(self, evdev_path: Optional[str] = None):
        self.evdev_path = evdev_path
        self.mode = "INIT"
        self._stop_event = asyncio.Event()
        self._last_actions = None  # last recording in memory

    async def start(self):
        # Create control socket first so CLI/Web can reach us even before kbd is ready
        print(f"[daemon] socket: {SETTINGS.socket_path}")
        server = await start_server(SETTINGS.socket_path, self.handle)
        Path(SETTINGS.record_dir).mkdir(parents=True, exist_ok=True)
        try:
            await self._bridge_forever()
        finally:
            server.close()
            await server.wait_closed()

    async def _wait_for_keyboard(self):
        while True:
            try:
                if self.evdev_path and Path(self.evdev_path).exists():
                    return
                self.evdev_path = find_keyboard_event()
                print(f"[daemon] keyboard: {self.evdev_path}")
                return
            except SystemExit:
                pass
            except Exception as e:
                print(f"[daemon] keyboard probe error: {e}")
            await asyncio.sleep(0.5)

    async def _bridge_forever(self):
        while True:
            await self._wait_for_keyboard()
            self.mode = "BRIDGE"; emit("MODE", mode=self.mode)
            b = Bridge(self.evdev_path, SETTINGS.hidg_path,
                       stop_hotkey=SETTINGS.stop_hotkey,
                       record_hotkey=SETTINGS.record_hotkey,
                       grab=True)
            result = await b.run_bridge()
            if result == "RECORD":
                await self._do_record()
            # "STOP" from bridge → just loop and stay in BRIDGE

    async def _choice_window(self, timeout_sec: float = 8.0) -> Optional[str]:
        # Post-record choices (LCTL/LCTRL allowed via keymap aliases)
        choices = {"LCTL+S":"CHOICE_SAVE","LCTL+P":"CHOICE_PLAY","LCTL+D":"CHOICE_DISCARD"}
        emit("CHOICE_MENU", keys=list(choices.keys()))
        self.mode = "POSTRECORD"; emit("MODE", mode=self.mode)
        b = Bridge(self.evdev_path, SETTINGS.hidg_path,
                   stop_hotkey=SETTINGS.stop_hotkey,
                   record_hotkey=SETTINGS.record_hotkey,
                   grab=True, extra_hotkeys=choices)
        try:
            label = await asyncio.wait_for(b.run_bridge(), timeout=timeout_sec)
            emit("CHOICE_SELECTED", label=label)
            return label
        except asyncio.TimeoutError:
            emit("CHOICE_TIMEOUT"); return None

    async def _do_record(self):
        self.mode = "RECORDING"; emit("MODE", mode=self.mode); emit("RECORD_START")
        b = Bridge(self.evdev_path, SETTINGS.hidg_path,
                   stop_hotkey=SETTINGS.stop_hotkey,
                   record_hotkey=SETTINGS.record_hotkey,
                   grab=True)
        actions = await b.run_record()
        self._last_actions = actions or []
        emit("RECORD_STOP", count=len(self._last_actions))

        while True:
            label = await self._choice_window(timeout_sec=8.0)
            if label == "CHOICE_SAVE":
                await self._save_last_timestamped(); break
            if label == "CHOICE_PLAY":
                await self._play_last_once(); continue
            if label == "CHOICE_DISCARD":
                self._last_actions = None; emit("DISCARDED"); break
            # timeout → back to bridge; keep last_actions
            break

        self.mode = "BRIDGE"; emit("MODE", mode=self.mode)

    async def _save_last_timestamped(self):
        if self._last_actions is None: return
        from datetime import datetime
        name = datetime.utcnow().strftime("rec_%Y%m%d_%H%M%S")
        rec = Recorder(); rec.actions = self._last_actions; rec.t0 = 0
        p = Path(SETTINGS.record_dir) / f"{name}.json"
        rec.save(p); emit("SAVED", path=str(p))
        self._last_actions = None

    async def _play_last_once(self):
        if self._last_actions is None: return
        tmp = Path(SETTINGS.record_dir) / "_temp_play.json"
        rec = Recorder(); rec.actions = self._last_actions; rec.t0 = 0
        rec.save(tmp)
        await self._do_play(str(tmp))

    async def _do_play(self, path, *, speed=1.0, jt=0.0, jh=0.0, loop=1):
        self.mode = "PLAYING"; emit("MODE", mode=self.mode); emit("PLAY_START", file=str(path))
        self._stop_event = asyncio.Event()
        p = Player(SETTINGS.hidg_path)

        if not self.evdev_path or not Path(self.evdev_path).exists():
            await self._wait_for_keyboard()

        watcher = asyncio.create_task(_wait_hotkey_release(self.evdev_path, SETTINGS.stop_hotkey))
        async def _trip(): await watcher; self._stop_event.set()
        trip = asyncio.create_task(_trip())

        try:
            await p.play(path, speed=speed, jitter_time=jt, jitter_hold=jh,
                         min_hold_s=SETTINGS.min_hold_s,
                         min_repeat_same_key_s=SETTINGS.min_repeat_same_key_s,
                         loop=loop, stop_event=self._stop_event)
        finally:
            for t in (trip, watcher):
                if not t.done():
                    t.cancel()
                    try: await t
                    except asyncio.CancelledError: pass

        emit("PLAY_STOP")
        self.mode = "BRIDGE"; emit("MODE", mode=self.mode)

    # --------- UNIX socket handler (THIS WAS MISSING) ----------
    async def handle(self, msg: dict):
        cmd = msg.get("cmd")

        if cmd == "status":
            return {"mode": self.mode,
                    "record_dir": str(SETTINGS.record_dir),
                    "socket": SETTINGS.socket_path,
                    "keyboard": self.evdev_path,
                    "have_last_actions": bool(self._last_actions)}

        if cmd == "record_start":
            if self.mode != "BRIDGE":
                raise RuntimeError(f"cannot start record from mode {self.mode}")
            asyncio.create_task(self._do_record())
            return "recording"

        if cmd == "record_stop":
            which = msg.get("action", "discard"); name = msg.get("name")
            if self._last_actions is None: self._last_actions = []
            rec = Recorder(); rec.actions = self._last_actions; rec.t0 = 0
            Path(SETTINGS.record_dir).mkdir(parents=True, exist_ok=True)
            if which == "save":
                if not name: raise RuntimeError("missing name")
                p = Path(SETTINGS.record_dir) / f"{name}.json"
                rec.save(p); self._last_actions = None; emit("SAVED", path=str(p)); return {"saved": str(p)}
            if which == "play_now":
                tmp = Path(SETTINGS.record_dir) / "_temp_play.json"
                rec.save(tmp)  # keep _last_actions so user can still save/discard after playback
                asyncio.create_task(self._do_play(str(tmp))); return {"playing": str(tmp)}
            self._last_actions = None; emit("DISCARDED"); return {"discarded": True}

        if cmd == "play":
            if self.mode != "BRIDGE":
                raise RuntimeError(f"cannot play from mode {self.mode}")
            name = msg.get("file")
            if not name: raise RuntimeError("missing file")
            p = Path(name)
            if not p.exists():
                alt = Path(SETTINGS.record_dir) / (name if name.endswith(".json") else name + ".json")
                if not alt.exists(): raise RuntimeError(f"not found: {name}")
                p = alt
            kwargs = {"speed": float(msg.get("speed", 1.0)),
                      "jt": float(msg.get("jitter_time", 0.0)),
                      "jh": float(msg.get("jitter_hold", 0.0)),
                      "loop": int(msg.get("loop", 1))}
            asyncio.create_task(self._do_play(str(p), **kwargs))
            return {"playing": str(p), **kwargs}

        if cmd == "stop":
            if self.mode == "PLAYING":
                self._stop_event.set(); return {"stopping": "playback"}
            return {"mode": self.mode}

        if cmd == "list":
            p = Path(SETTINGS.record_dir)
            files = sorted(str(x.name) for x in p.glob("*.json")) if p.exists() else []
            return {"files": files}

        if cmd == "save_last":
            if not self._last_actions: raise RuntimeError("no last recording")
            name = msg.get("name"); 
            if not name: raise RuntimeError("missing name")
            rec = Recorder(); rec.actions = self._last_actions; rec.t0 = 0
            path = Path(SETTINGS.record_dir) / f"{name}.json"
            rec.save(path); self._last_actions = None; emit("SAVED", path=str(path))
            return {"saved": str(path)}

        raise RuntimeError(f"unknown cmd: {cmd}")


# entry point used by cli.py
async def run_daemon(evdev_path: Optional[str] = None):
    d = MacroDaemon(evdev_path=evdev_path)
    await d.start()
