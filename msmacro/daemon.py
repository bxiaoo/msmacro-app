from __future__ import annotations

import json
import asyncio
import contextlib
import logging
import time
import random
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

from evdev import InputDevice, ecodes

from .config import SETTINGS
from .keyboard import find_keyboard_event
from .bridge import Bridge
from .player import Player
from .recorder import Recorder, list_recordings_recursive, resolve_record_path
from .ipc import start_server
from .keymap import parse_hotkey, usage_from_ecode, is_modifier, mod_bit
from .hidio import HIDWriter

try:
    from .events import emit  # type: ignore
except Exception:  # pragma: no cover
    def emit(*_a, **_kw):  # type: ignore
        return


def _setup_logger() -> logging.Logger:
    lvl_name = (getattr(SETTINGS, "log_level", None) or os.environ.get("MSMACRO_LOGLEVEL", "INFO")).upper()
    level = getattr(logging, lvl_name, logging.INFO)
    logger = logging.getLogger("msmacro.daemon")
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


log = _setup_logger()


def _events_to_actions(events: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    """Convert raw keyboard events to action format with press/duration."""
    actions: List[Dict[str, float]] = []
    down_time: Dict[int, float] = {}
    cursor = 0.0
    
    for ev in sorted(events, key=lambda e: float(e.get("t", 0.0))):
        try:
            t = float(ev.get("t", 0.0))
            typ = str(ev.get("type", "")).lower()
            usage = int(ev.get("usage", 0))
        except (KeyError, ValueError, TypeError):
            continue
            
        if typ in ("down", "press"):
            down_time[usage] = t
        elif typ in ("up", "release"):
            t0 = down_time.pop(usage, None)
            if t0 is not None:
                press = max(0.0, t0 - cursor)
                dur = max(0.0, t - t0)
                actions.append({"usage": usage, "press": press, "dur": dur})
                cursor = t
    
    # Handle any keys still held down
    for usage, t0 in down_time.items():
        press = max(0.0, t0 - cursor)
        actions.append({"usage": int(usage), "press": press, "dur": 0.05})
        cursor = t0 + 0.05
    
    return actions

class MacroDaemon:
    def __init__(self, evdev_path: Optional[str] = None):
        self.evdev_path = evdev_path or find_keyboard_event()
        self.mode = "BRIDGE"

        self._stop_event: Optional[asyncio.Event] = None
        self._last_actions: Optional[List[Dict[str, float]]] = None
        self._last_recorder: Optional[Recorder] = None

        self._runner_task: Optional[asyncio.Task] = None
        self._record_task: Optional[asyncio.Task] = None
        self._play_task: Optional[asyncio.Task] = None
        self._post_task: Optional[asyncio.Task] = None

        self.rec_dir = Path(getattr(SETTINGS, "record_dir", "./records"))
        self.rec_dir.mkdir(parents=True, exist_ok=True)

        log.info("Daemon init: keyboard=%s  record_dir=%s", self.evdev_path, self.rec_dir)
        log.info("Hotkeys: record=%s  stop=%s",
                 getattr(SETTINGS, "record_hotkey", "LCTRL+R"),
                 getattr(SETTINGS, "stop_hotkey", "LCTRL+Q"))
        log.info("POST hotkeys: save=%s  play=%s  discard=%s",
                 getattr(SETTINGS, "post_save_hotkey", "LCTRL+S"),
                 getattr(SETTINGS, "post_play_hotkey", "LCTRL+P"),
                 getattr(SETTINGS, "post_discard_hotkey", getattr(SETTINGS, "stop_hotkey", "LCTRL+Q")))
        log.info("IPC socket: %s", getattr(SETTINGS, "socket_path", "/run/msmacro.sock"))

    async def start(self):
        log.info("Starting IPC server…")
        server = await start_server(getattr(SETTINGS, "socket_path", "/run/msmacro.sock"), self.handle)
        await self._ensure_runner_started()
        try:
            log.info("Daemon ready (mode=%s) — waiting.", self.mode)
            await asyncio.Event().wait()
        finally:
            log.info("Shutting down…")
            await self._pause_runner()
            server.close()
            await server.wait_closed()
            log.info("Shutdown complete.")

    # ---------- bridge supervisor ----------

    async def _ensure_runner_started(self):
        if self._runner_task and not self._runner_task.done():
            return

        async def runner():
            while True:
                grab = (self.mode != "POSTRECORD")  # allow POSTRECORD hotkey watcher to read events
                b = Bridge(
                    evdev_path=self.evdev_path,
                    hidg_path=getattr(SETTINGS, "hidg_path", "/dev/hidg0"),
                    stop_hotkey=getattr(SETTINGS, "stop_hotkey", "LCTRL+Q"),
                    record_hotkey=getattr(SETTINGS, "record_hotkey", "LCTRL+R"),
                    grab=grab,
                )
                if self.mode != "POSTRECORD":
                    self.mode = "BRIDGE"
                    emit("MODE", mode=self.mode)
                log.debug("Bridge.run_bridge() starting… (grab=%s)", grab)
                try:
                    result = await b.run_bridge()
                    log.debug("Bridge.run_bridge() returned: %r", result)
                except asyncio.CancelledError:
                    log.debug("Bridge.run_bridge() cancelled (pausing bridge).")
                    break
                except Exception:
                    log.exception("Bridge.run_bridge() crashed; retrying shortly.")
                    await asyncio.sleep(0.2)
                    continue

                if result == "RECORD":
                    if self.mode == "POSTRECORD":
                        log.debug("Ignoring RECORD chord while in POSTRECORD.")
                        continue
                    await asyncio.sleep(0.05)
                    log.info("Recording (hotkey) starting via daemon recorder…")
                    try:
                        await self._do_record(source="hotkey")
                    except Exception:
                        log.exception("Recording (hotkey) crashed in daemon.")
                    continue

                await asyncio.sleep(0)

        self._runner_task = asyncio.create_task(runner())
        log.info("Bridge supervisor started (task=%s).", self._runner_task.get_name())

    async def _pause_runner(self):
        if self._runner_task and not self._runner_task.done():
            log.debug("Pausing bridge supervisor…")
            self._runner_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._runner_task
        self._runner_task = None
        log.debug("Bridge supervisor paused.")

    # ---------- POSTRECORD hotkey watcher ----------

    async def _post_hotkeys(self):
        """Listen for save/play/discard while in POSTRECORD."""
        if not self.evdev_path or not Path(self.evdev_path).exists():
            self.evdev_path = find_keyboard_event()

        save_spec = getattr(SETTINGS, "post_save_hotkey", "LCTRL+S")
        play_spec = getattr(SETTINGS, "post_play_hotkey", "LCTRL+P")
        # Fixed typo: SETINGS -> SETTINGS
        disc_spec = getattr(SETTINGS, "post_discard_hotkey", getattr(SETTINGS, "stop_hotkey", "LCTRL+Q"))

        try:
            s_mod, s_key = parse_hotkey(save_spec)
        except Exception:
            s_mod = s_key = None
        try:
            p_mod, p_key = parse_hotkey(play_spec)
        except Exception:
            p_mod = p_key = None
        try:
            d_mod, d_key = parse_hotkey(disc_spec)
        except Exception:
            d_mod = d_key = None

        try:
            dev = InputDevice(self.evdev_path)
        except Exception as e:
            log.warning("POST hotkeys: cannot open %s: %s", self.evdev_path, e)
            return

        log.debug("POST hotkeys watcher running (save=%s play=%s discard=%s)", save_spec, play_spec, disc_spec)

        s_mod_dn = s_key_dn = s_armed = False
        p_mod_dn = p_key_dn = p_armed = False
        d_mod_dn = d_key_dn = d_armed = False

        try:
            async for ev in dev.async_read_loop():
                if self.mode != "POSTRECORD":
                    break
                if ev.type != ecodes.EV_KEY:
                    continue
                code, val = ev.code, ev.value
                if val == 2:
                    continue

                # Save chord
                if s_mod is not None and s_key is not None:
                    if code == s_mod:
                        s_mod_dn = (val != 0)
                        if s_mod_dn and s_key_dn: s_armed = True
                        if s_armed and not s_mod_dn and not s_key_dn:
                            log.info("POST hotkey: SAVE")
                            await self._save_last_default()
                            break
                    elif code == s_key:
                        s_key_dn = (val != 0)
                        if s_mod_dn and s_key_dn: s_armed = True
                        if s_armed and not s_mod_dn and not s_key_dn:
                            log.info("POST hotkey: SAVE")
                            await self._save_last_default()
                            break

                # Play preview chord
                if p_mod is not None and p_key is not None:
                    if code == p_mod:
                        p_mod_dn = (val != 0)
                        if p_mod_dn and p_key_dn: p_armed = True
                        if p_armed and not p_mod_dn and not p_key_dn:
                            log.info("POST hotkey: PREVIEW")
                            await self._preview_last_once()
                            p_armed = False
                    elif code == p_key:
                        p_key_dn = (val != 0)
                        if p_mod_dn and p_key_dn: p_armed = True
                        if p_armed and not p_mod_dn and not p_key_dn:
                            log.info("POST hotkey: PREVIEW")
                            await self._preview_last_once()
                            p_armed = False

                # Discard chord
                if d_mod is not None and d_key is not None:
                    if code == d_mod:
                        d_mod_dn = (val != 0)
                        if d_mod_dn and d_key_dn: d_armed = True
                        if d_armed and not d_mod_dn and not d_key_dn:
                            log.info("POST hotkey: DISCARD")
                            await self._discard_last()
                            break
                    elif code == d_key:
                        d_key_dn = (val != 0)
                        if d_mod_dn and d_key_dn: d_armed = True
                        if d_armed and not d_mod_dn and not d_key_dn:
                            log.info("POST hotkey: DISCARD")
                            await self._discard_last()
                            break

        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("POST hotkeys watcher crashed.")
        finally:
            with contextlib.suppress(Exception):
                dev.close()
            log.debug("POST hotkeys watcher stopped.")

    # --- PLAYING stop hotkey watcher (based on old daemon) ---

    async def _play_hotkeys(self):
        """Listen for the stop chord while PLAYING and set self._stop_event."""
        stop_spec = getattr(SETTINGS, "stop_hotkey", "LCTRL+Q")
        try:
            mod_ec, key_ec = parse_hotkey(stop_spec)
        except Exception:
            mod_ec = key_ec = None

        # Resolve keyboard device
        if not self.evdev_path or not Path(self.evdev_path).exists():
            self.evdev_path = find_keyboard_event()

        try:
            dev = InputDevice(self.evdev_path)
        except Exception as e:
            log.warning("PLAY hotkeys: cannot open %s: %s", self.evdev_path, e)
            return

        log.debug("PLAY hotkeys watcher running (stop=%s)", stop_spec)

        mod_dn = key_dn = armed = False
        try:
            async for ev in dev.async_read_loop():
                if self.mode != "PLAYING" or not self._stop_event:
                    log.debug("PLAY watcher: mode changed or no stop event, exiting")
                    break
                if ev.type != ecodes.EV_KEY:
                    continue
                code, val = ev.code, ev.value
                if val == 2:  # repeat
                    continue

                if val == 1:
                    log.debug("PLAY watcher: key DOWN code=%d", code)
                elif val == 0:
                    log.debug("PLAY watcher: key UP code=%d", code)
                

                if mod_ec is not None and key_ec is not None:
                    if code == mod_ec:
                        mod_dn = (val != 0)
                        if mod_dn and key_dn: 
                            armed = True
                            log.debug("PLAY watcher: stop chord ARMED")
                        if armed and not mod_dn and not key_dn:
                            log.info("PLAY hotkey: STOP")
                            if self._stop_event:
                                self._stop_event.set()
                                log.info("Stop event SET")
                            break
                            # with contextlib.suppress(Exception):
                            #     self._stop_event.set()
                            # break
                    elif code == key_ec:
                        key_dn = (val != 0)
                        if mod_dn and key_dn: 
                            armed = True
                            log.debug("PLAY watcher: stop chord ARMED")
                        if armed and not mod_dn and not key_dn:
                            log.info("PLAY hotkey: STOP")
                            if self._stop_event:
                                self._stop_event.set()
                                log.info("Stop event SET")
                            break
                            # with contextlib.suppress(Exception):
                            #     self._stop_event.set()
                            # break
        except asyncio.CancelledError:
            log.debug("PLAY hotkeys watcher cancelled")
        except Exception:
            log.exception("PLAY hotkeys watcher crashed.")
        finally:
            with contextlib.suppress(Exception):
                dev.close()
            log.debug("PLAY hotkeys watcher stopped.")

    async def _start_play_hotkeys(self):
        if getattr(self, "_play_task", None) and not self._play_task.done():
            return
        if self.mode != "PLAYING":
            return
        self._play_task = asyncio.create_task(self._play_hotkeys())

    async def _stop_play_hotkeys(self):
        t = getattr(self, "_play_task", None)
        if t and not t.done():
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t
        self._play_task = None


    async def _start_post_hotkeys(self):
        if self._post_task and not self._post_task.done():
            return
        if self.mode != "POSTRECORD":
            return
        self._post_task = asyncio.create_task(self._post_hotkeys())

    async def _stop_post_hotkeys(self):
        if self._post_task and not self._post_task.done():
            self._post_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._post_task
        self._post_task = None

    # ---------- recording (pass-through) ----------

    async def _do_record(self, *, source: str = "web"):
        """Enhanced recording with improved accuracy and timing."""
        if source == "web":
            await self._pause_runner()

        if not self.evdev_path or not Path(self.evdev_path).exists():
            self.evdev_path = find_keyboard_event()

        stop_spec = getattr(SETTINGS, "stop_hotkey", "LCTRL+Q")
        rec_spec = getattr(SETTINGS, "record_hotkey", "LCTRL+R")
        try:
            stop_mod_ec, stop_key_ec = parse_hotkey(stop_spec)
        except Exception:
            stop_mod_ec = stop_key_ec = None
        try:
            rec_mod_ec, rec_key_ec = parse_hotkey(rec_spec)
        except Exception:
            rec_mod_ec = rec_key_ec = None

        try:
            dev = InputDevice(self.evdev_path)
            log.debug("Recording: opened %s (%s)", self.evdev_path, getattr(dev, "name", "?"))
        except Exception as e:
            log.error("Recording failed: cannot open input device %s: %s", self.evdev_path, e)
            if source == "web":
                await self._ensure_runner_started()
            return

        hid = HIDWriter(getattr(SETTINGS, "hidg_path", "/dev/hidg0"))
        modmask = 0
        down_usages: set[int] = set()

        record_grab = str(os.environ.get("MSMACRO_RECORD_GRAB", "0")).lower() in ("1","true","yes","on")
        cfg_val = getattr(SETTINGS, "record_grab", None)
        if cfg_val is not None:
            record_grab = bool(cfg_val)

        grabbed = False
        if record_grab:
            try:
                dev.grab()
                grabbed = True
            except Exception as e:
                log.warning("Recording: grab() failed (%s). Continuing without exclusive grab.", e)

        self.mode = "RECORDING"
        emit("MODE", mode=self.mode)
        emit("RECORD_START")
        log.info("Recording started (source=%s, stop_hotkey=%s, grabbed=%s)",
                 source, stop_spec, grabbed)

        # Initialize Recorder for high-precision timing
        start_t = time.perf_counter()
        recorder = Recorder(t0=start_t)
        self._last_recorder = recorder

        stop_mod_down = stop_key_down = stop_armed = False
        rec_mod_down = rec_key_down = rec_armed = False

        self._record_task = asyncio.current_task()

        def forward_update(code: int, val: int):
            nonlocal modmask
            if is_modifier(code):
                bit = mod_bit(code)
                if val:
                    modmask |= bit
                else:
                    modmask &= ~bit
                hid.send(modmask, down_usages)
                return
            usage = usage_from_ecode(code)
            if usage == 0:
                return
            if val:
                down_usages.add(usage)
            else:
                down_usages.discard(usage)
            hid.send(modmask, down_usages)

        try:
            async for ev in dev.async_read_loop():
                if ev.type != ecodes.EV_KEY:
                    continue
                code, val = ev.code, ev.value
                if val == 2:  # key repeat
                    continue

                suppress = False
                # Check stop hotkey
                if stop_mod_ec is not None and stop_key_ec is not None:
                    if code == stop_mod_ec:
                        stop_mod_down = (val != 0)
                        if stop_mod_down and stop_key_down:
                            stop_armed = True
                            suppress = True
                        if stop_armed and not stop_mod_down and not stop_key_down:
                            log.debug("Stop chord released -> ending recording.")
                            break
                    elif code == stop_key_ec:
                        stop_key_down = (val != 0)
                        if stop_mod_down and stop_key_down:
                            stop_armed = True
                            suppress = True
                        if stop_armed and not stop_mod_down and not stop_key_down:
                            log.debug("Stop chord released -> ending recording.")
                            break

                # Check record hotkey (to stop if pressed again)
                if rec_mod_ec is not None and rec_key_ec is not None:
                    if code == rec_mod_ec:
                        rec_mod_down = (val != 0)
                        if rec_mod_down and rec_key_down:
                            rec_armed = True
                            suppress = True
                        if rec_armed and not rec_mod_down and not rec_key_down:
                            log.debug("Record chord released (2nd time) -> ending recording.")
                            break
                    elif code == rec_key_ec:
                        rec_key_down = (val != 0)
                        if rec_mod_down and rec_key_down:
                            rec_armed = True
                            suppress = True
                        if rec_armed and not rec_mod_down and not rec_key_down:
                            log.debug("Record chord released (2nd time) -> ending recording.")
                            break

                if not suppress:
                    forward_update(code, 1 if val else 0)

                # Record the event with high precision timing
                usage = usage_from_ecode(code)
                if usage != 0 and not suppress:
                    now = time.perf_counter()  # Use perf_counter
                if val == 1:  # key down
                    recorder.on_down(usage, now)
                    log.debug("key %d DOWN at %.3f", usage, now - start_t)
                elif val == 0:  # key up
                    recorder.on_up(usage, now)
                    log.debug("key %d UP at %.3f", usage, now - start_t)


        except asyncio.CancelledError:
            log.info("Recording cancelled by /api/stop.")
        except Exception:
            log.exception("Recording loop crashed.")
        finally:
            # Finalize recording
            recorder.finalize(time.monotonic())
            
            with contextlib.suppress(Exception):
                hid.all_up()
                hid.close()
            with contextlib.suppress(Exception):
                if grabbed:
                    dev.ungrab()
            with contextlib.suppress(Exception):
                dev.close()
            self._record_task = None

        # Store the recorded actions
        self._last_actions = recorder.to_dict(prefer="actions").get("actions", [])
        self.mode = "POSTRECORD"
        emit("MODE", mode=self.mode)
        emit("RECORD_END", actions=len(self._last_actions))
        log.info("Recording finished: %d actions (mode=POSTRECORD)", len(self._last_actions))

        await self._ensure_runner_started()
        await self._start_post_hotkeys()

    # Add missing _record_direct method
    async def _record_direct(self):
        """Direct recording initiated from web UI."""
        await self._do_record(source="web")

    # ---------- helpers for POSTRECORD actions ----------

    async def _save_last_default(self):
        """Save last actions with a timestamped name and return to BRIDGE."""
        if not self._last_actions:
            log.warning("save_last_default: no last actions")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        name = f"rec_{ts}.json"
        items = self._last_actions
        
        # Convert if needed
        if items and isinstance(items[0], dict):
            if 't' in items[0] or 'type' in items[0]:
                if 'press' not in items[0]:
                    items = _events_to_actions(items)
        
        # Create recorder and save
        path = (self.rec_dir / name).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save using Recorder format
        data = {"t0": 0.0, "actions": items}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        
        emit("SAVED", path=str(path))
        log.info("Saved recording: %s (%d actions)", path, len(items))
        self._last_actions = None
        await self._stop_post_hotkeys()
        self.mode = "BRIDGE"
        emit("MODE", mode=self.mode)
        await self._ensure_runner_started()

    async def _discard_last(self):
        self._last_actions = None
        await self._stop_post_hotkeys()
        self.mode = "BRIDGE"
        emit("MODE", mode=self.mode)
        await self._ensure_runner_started()

    async def _preview_last_once(self, *, speed=1.0, jt=0.0, jh=0.0):
        """Play last actions once but return to POSTRECORD."""
        if not self._last_actions:
            log.warning("preview_last_once: no last actions")
            return

        self.rec_dir.mkdir(parents=True, exist_ok=True)
        tmp = (self.rec_dir / ".__preview__.json").resolve()

        data = {"t0": 0.0, "actions": self._last_actions}
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")

        await self._stop_post_hotkeys()
        try:
            await self._do_play(str(tmp), speed=speed, jt=jt, jh=jh, loop=1, restore_mode="POSTRECORD")
        finally:
            # Always clean the temp file; also remove any legacy stray root file.
            with contextlib.suppress(Exception):
                tmp.unlink()
            with contextlib.suppress(Exception):
                Path("/.__preview__").unlink()

        if self.mode == "POSTRECORD":
            await self._start_post_hotkeys()


    # ---------- playback ----------

    async def _do_play(self, path: str, *, speed=1.0, jt=0.0, jh=0.0, loop=1, restore_mode="BRIDGE"):
        log.info("Playback starting: path=%s speed=%.3f jt=%.3f jh=%.3f loop=%s",
                 path, speed, jt, jh, loop)

        # Store task reference for cancellation
        self._play_task = asyncio.current_task()

        await self._pause_runner()

        self.mode = "PLAYING"
        emit("MODE", mode=self.mode)
        emit("PLAY_START", file=str(path))

        self._stop_event = asyncio.Event()
        await self._start_play_hotkeys()

        player = Player(getattr(SETTINGS, "hidg_path", "/dev/hidg0"))


        try:
            ok = await player.play(
                path, speed=speed, jitter_time=jt, jitter_hold=jh,
                min_hold_s=getattr(SETTINGS, "min_hold_s", 0.083),
                min_repeat_same_key_s=getattr(SETTINGS, "min_repeat_same_key_s", 0.134),
                loop=loop, stop_event=self._stop_event,
            )
            log.info("Playback finished: ok=%s", ok)
        except asyncio.CancelledError:
            log.info("Playback cancelled")
            ok = False
        except Exception:
            log.exception("Playback crashed.")
            ok = False
        finally:
            await self._stop_play_hotkeys()
            self._stop_event = None
            self._play_task = None
            self.mode = restore_mode
            emit("MODE", mode=self.mode)
            emit("PLAY_END")
            await self._ensure_runner_started()
            if self.mode == "POSTRECORD":
                await self._start_post_hotkeys()

    async def _do_play_selection(self, paths: List[str], *, speed=1.0, jt=0.0, jh=0.0, loop=1):
        """Play multiple recordings in random order."""
        log.info("Playlist starting: n=%d speed=%.3f jt=%.3f jh=%.3f loop=%s",
                 len(paths), speed, jt, jh, loop)

        await self._pause_runner()
        await asyncio.sleep(0.03)
        
        self.mode = "PLAYING"
        emit("MODE", mode=self.mode)
        emit("PLAY_START", playlist=len(paths))
        self._stop_event = asyncio.Event()

        await self._stop_post_hotkeys()
        await self._start_play_hotkeys()

        player = Player(getattr(SETTINGS, "hidg_path", "/dev/hidg0"))
        try:
            for _ in range(max(1, int(loop))):
                order = list(paths)
                random.shuffle(order)
                for p in order:
                    if self._stop_event.is_set():
                        break
                    ok = await player.play(
                        p, speed=speed, jitter_time=jt, jitter_hold=jh,
                        min_hold_s=getattr(SETTINGS, "min_hold_s", 0.010),
                        min_repeat_same_key_s=getattr(SETTINGS, "min_repeat_same_key_s", 0.050),
                        loop=1, stop_event=self._stop_event,
                    )
                    if not ok:  # Stopped by user
                        break
                if self._stop_event.is_set():
                    break
        except Exception:
            log.exception("Playlist crashed.")
        finally:
            await self._stop_play_hotkeys()
            self._stop_event = None
            self._play_task = None
            self.mode = "BRIDGE"
            emit("MODE", mode=self.mode)
            emit("PLAY_END")
            await self._ensure_runner_started()

    # ---------- IPC handler ----------
    async def handle(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Handle IPC messages from web server."""
        cmd = (msg.get("cmd") or "").strip()
        # log.debug("IPC cmd: %s", cmd)

        try:
            if cmd == "status":
                top_files = sorted([p.name for p in self.rec_dir.glob("*.json")])

                def meta(name: str) -> Dict[str, Any]:
                    p = self.rec_dir / name
                    try:
                        st = p.stat()
                        return {"name": name, "path": str(p), "size": st.st_size, "mtime": int(st.st_mtime)}
                    except Exception:
                        return {"name": name, "path": str(p), "size": 0, "mtime": 0}

                resp = {
                    "mode": self.mode,
                    "record_dir": str(self.rec_dir),
                    "socket": getattr(SETTINGS, "socket_path", ""),
                    "keyboard": self.evdev_path,
                    "have_last_actions": bool(self._last_actions),
                    "files": [meta(n) for n in top_files],
                }
                return resp

            if cmd == "list_recursive":
                items = list_recordings_recursive(self.rec_dir)
                return {"items": items}

            if cmd == "play":
                if self.mode not in ("BRIDGE", "POSTRECORD"):
                    raise RuntimeError(f"cannot play from mode {self.mode}")
                name = msg.get("file")
                if not name:
                    raise RuntimeError("missing file")
                p = Path(name)
                if not p.exists():
                    alt = self.rec_dir / (name if str(name).endswith(".json") else f"{name}.json")
                    if not alt.exists():
                        raise RuntimeError(f"not found: {name}")
                    p = alt
                kwargs = {
                    "speed": float(msg.get("speed", 1.0)),
                    "jt": float(msg.get("jitter_time", 0.0)),
                    "jh": float(msg.get("jitter_hold", 0.0)),
                    "loop": int(msg.get("loop", 1)),
                }
                # asyncio.create_task(self._do_play(str(p), **kwargs))
                self._play_task = asyncio.create_task(self._do_play(str(p), **kwargs))
                return {"playing": str(p), **kwargs}

            if cmd == "play_selection":
                names = msg.get("names") or []
                if not isinstance(names, list) or not names:
                    raise RuntimeError("empty selection")
                paths = []
                for n in names:
                    p = resolve_record_path(self.rec_dir, n)
                    if p.exists():
                        paths.append(str(p))
                if not paths:
                    raise RuntimeError("no valid files")
                kwargs = {
                    "speed": float(msg.get("speed", 1.0)),
                    "jt": float(msg.get("jitter_time", 0.0)),
                    "jh": float(msg.get("jitter_hold", 0.0)),
                    "loop": int(msg.get("loop", 1)),
                }
                self._play_task = asyncio.create_task(self._do_play_selection(paths, **kwargs))
                return {"playlist": paths, **kwargs}

            if cmd == "preview_last":
                speed = float(msg.get("speed", 1.0))
                jt = float(msg.get("jitter_time", 0.0))
                jh = float(msg.get("jitter_hold", 0.0))
                await self._preview_last_once(speed=speed, jt=jt, jh=jh)
                return {"previewed": True}

            if cmd == "stop":
                log.info("IPC: stop command received (mode=%s)", self.mode)
                
                if self.mode == "PLAYING" and self._stop_event:
                    log.info("Setting stop event for playback")
                    self._stop_event.set()
                    
                    # Also try to cancel the play task if it exists
                    if hasattr(self, '_play_task') and self._play_task and not self._play_task.done():
                        log.info("Cancelling play task")
                        self._play_task.cancel()
                    
                    # Wait a moment for the mode to change
                    await asyncio.sleep(0.1)
                    return {"stopping": "playback", "mode": self.mode}
                    
                if self.mode == "RECORDING" and self._record_task and not self._record_task.done():
                    log.info("Cancelling recording task")
                    self._record_task.cancel()
                    return {"stopping": "recording"}
        
                return {"mode": self.mode, "nothing_to_stop": True}

            if cmd == "record_start":
                if self.mode not in ("BRIDGE", "POSTRECORD"):
                    raise RuntimeError(f"cannot start record from mode {self.mode}")
                if not (self._record_task and not self._record_task.done()):
                    self._record_task = asyncio.create_task(self._record_direct())
                return {"recording": True}

            if cmd == "save_last":
                if not self._last_actions:
                    raise RuntimeError("no last recording")
                name = msg.get("name")
                if not name:
                    raise RuntimeError("missing name")
                items = self._last_actions or []
                if items and isinstance(items[0], dict) and ('t' in items[0] or 'type' in items[0]) and 'press' not in items[0]:
                    items = _events_to_actions(items)
                
                path = (self.rec_dir / (name if str(name).endswith(".json") else f"{name}.json")).resolve()
                path.parent.mkdir(parents=True, exist_ok=True)
                
                data = {"t0": 0.0, "actions": items}
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                
                emit("SAVED", path=str(path))
                log.info("Saved recording: %s (%d actions)", path, len(items))
                self._last_actions = None
                await self._stop_post_hotkeys()
                self.mode = "BRIDGE"
                emit("MODE", mode=self.mode)
                await self._ensure_runner_started()
                return {"saved": str(path)}

            if cmd == "discard_last":
                await self._discard_last()
                return {"discarded": True}

            if cmd == "rename_recording":
                old = msg.get("old")
                new = msg.get("new")
                if not old or not new:
                    raise RuntimeError("missing old/new")
                oldp = resolve_record_path(self.rec_dir, old)
                newp = resolve_record_path(self.rec_dir, new)
                newp.parent.mkdir(parents=True, exist_ok=True)
                if not oldp.exists():
                    raise RuntimeError(f"not found: {old}")
                oldp.rename(newp)
                log.info("Renamed recording: %s -> %s", oldp, newp)
                return {"renamed": {"from": str(oldp), "to": str(newp)}}

            if cmd == "list":
                files = sorted(x.name for x in self.rec_dir.glob("*.json")) if self.rec_dir.exists() else []
                return {"files": files}

            raise RuntimeError(f"unknown cmd: {cmd}")

        except Exception as e:
            log.exception("IPC error on cmd=%s", cmd)
            return {"error": str(e)}

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
