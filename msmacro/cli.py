import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from evdev import InputDevice, ecodes

from .config import SETTINGS
from .keyboard import find_keyboard_event
from .bridge import Bridge
from .player import Player
from .keymap import is_modifier, mod_bit, usage_from_ecode, parse_hotkey
from .daemon import run_daemon
from .ipc import send


# ---------- helpers for non-daemon hotkey stop during local playback ----------

async def wait_hotkey_release(evdev_path: str, hotkey_spec: str) -> None:
    """Return when MOD+KEY chord is pressed and then released."""
    mod_ec, key_ec = parse_hotkey(hotkey_spec)
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
            if val == 2:
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


async def play_with_hotkey(evdev_path: str, path: str, stop_hotkey: str):
    """Run playback until it completes, or stop-hotkey is hit.
       If stopped, prompt to Replay/Stop; 'Stop' returns to caller."""
    while True:
        stop_ev = asyncio.Event()

        watcher = asyncio.create_task(wait_hotkey_release(evdev_path, stop_hotkey))

        async def _watch():
            await watcher
            stop_ev.set()

        watch_task = asyncio.create_task(_watch())

        p = Player(SETTINGS.hidg_path)
        play_task = asyncio.create_task(
            p.play(
                path,
                speed=1.0,
                jitter_time=0.0,
                jitter_hold=0.0,
                min_hold_s=SETTINGS.min_hold_s,
                min_repeat_same_key_s=SETTINGS.min_repeat_same_key_s,
                loop=1,
                stop_event=stop_ev,
            )
        )

        done, pending = await asyncio.wait(
            {play_task, watch_task}, return_when=asyncio.FIRST_COMPLETED
        )

        # tidy up tasks deterministically
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

        completed = (
            play_task.done() and (play_task.exception() is None) and play_task.result() is True
        )
        if completed:
            print("[play] completed.")
            return
        else:
            print("[play] stopped by hotkey.")
            while True:
                ans = input("[R]eplay or [S]top to bridge? ").strip().lower()
                if ans in ("r", "s"):
                    break
            if ans == "r":
                print("[play] replaying from beginning…")
                continue
            print("[play] leaving play mode → bridge.")
            return


# ---------- non-daemon live/record entrypoints (still handy for manual runs) ----------

async def live_loop(evdev_path: str, stop_hotkey: str, record_hotkey: str):
    """Bridge mode that can start recordings with LALT+R and end with LALT+Q."""
    while True:
        b = Bridge(
            evdev_path,
            SETTINGS.hidg_path,
            stop_hotkey=stop_hotkey,
            record_hotkey=record_hotkey,
            grab=True,
        )
        result = await b.run_bridge()
        if result == "STOP":
            print("[live] stop hotkey → exiting live session.")
            break
        if result == "RECORD":
            print("[live] record hotkey → starting recording.")
            b = Bridge(
                evdev_path,
                SETTINGS.hidg_path,
                stop_hotkey=stop_hotkey,
                record_hotkey=record_hotkey,
                grab=True,
            )
            actions = await b.run_record()
            print(f"[record] captured {len(actions)} actions.")
            from .recorder import Recorder

            rec = Recorder()
            rec.actions = actions
            rec.t0 = 0
            while True:
                choice = input("[S]ave, [P]lay now, [D]iscard? ").strip().lower()
                if choice in ("s", "p", "d"):
                    break
            if choice == "s":
                name = input("File name (no spaces, no extension): ").strip()
                if not name:
                    from datetime import datetime

                    name = datetime.utcnow().strftime("rec_%Y%m%d_%H%M%S")
                path = Path(SETTINGS.record_dir) / f"{name}.json"
                rec.save(path)
                print(f"Saved → {path}")
            elif choice == "p":
                tmp = Path(SETTINGS.record_dir) / "_temp_play.json"
                rec.save(tmp)
                await play_with_hotkey(evdev_path, str(tmp), stop_hotkey)
            else:
                print("Discarded.")
            print("[live] returning to bridge mode…")


def cmd_live(args):
    dev = args.device or find_keyboard_event()
    print(f"[live] {dev} → {SETTINGS.hidg_path}")
    asyncio.run(live_loop(dev, args.stop_hotkey, args.record_hotkey))


def cmd_record(args):
    # One-shot record with interactive prompt (manual mode)
    from .recorder import Recorder

    dev = args.device or find_keyboard_event()
    print(f"[record] {dev} → {SETTINGS.hidg_path}\nStop hotkey: {args.stop_hotkey}")
    b = Bridge(
        dev,
        SETTINGS.hidg_path,
        stop_hotkey=args.stop_hotkey,
        record_hotkey=args.record_hotkey,
        grab=True,
    )
    actions = asyncio.run(b.run_record())
    print(f"Recorded {len(actions)} actions.")
    rec = Recorder()
    rec.actions = actions
    rec.t0 = 0
    while True:
        choice = input("[S]ave, [P]lay now, [D]iscard? ").strip().lower()
        if choice in ("s", "p", "d"):
            break
    if choice == "s":
        name = input("File name (no spaces, no extension): ").strip() or None
        if not name:
            from datetime import datetime

            name = datetime.utcnow().strftime("rec_%Y%m%d_%H%M%S")
        path = Path(SETTINGS.record_dir) / f"{name}.json"
        rec.save(path)
        print(f"Saved → {path}")
    elif choice == "p":
        tmp = Path(SETTINGS.record_dir) / "_temp_play.json"
        rec.save(tmp)
        asyncio.run(play_with_hotkey(dev, str(tmp), args.stop_hotkey))
    else:
        print("Discarded.")


def cmd_list(args):
    p = Path(SETTINGS.record_dir)
    if not p.exists():
        print("(no recordings directory)")
        return
    files = sorted(p.glob("*.json"))
    if not files:
        print("(no recordings yet)")
        return
    for i, f in enumerate(files, 1):
        print(f"{i:2d}. {f.name}")


def cmd_play(args):
    dev = args.device or find_keyboard_event()
    if args.pick:
        p = Path(SETTINGS.record_dir)
        files = sorted(p.glob("*.json"))
        if not files:
            print("(no recordings)")
            return
        for i, f in enumerate(files, 1):
            print(f"{i:2d}. {f.name}")
        idx = int(input("Pick #: "))
        path = files[idx - 1]
    else:
        name = args.file
        if not name:
            raise SystemExit("Provide a file or use --pick")
        path = Path(name)
        if not path.exists():
            alt = Path(SETTINGS.record_dir) / (
                name if name.endswith(".json") else name + ".json"
            )
            if not alt.exists():
                raise SystemExit(f"Not found: {name}")
            path = alt
    print(f"[play] {path}")
    asyncio.run(play_with_hotkey(dev, str(path), args.stop_hotkey))


# ---------- daemon & ctl (remote control) ----------

def cmd_daemon(args):
    """Run the background daemon with control socket (for systemd)."""
    dev = None if args.device in (None, "auto") else args.device
    print(f"[daemon] socket: {SETTINGS.socket_path}")
    asyncio.run(run_daemon(dev))


def cmd_ctl(args):
    """Client for the daemon's UNIX socket control API."""
    # watch mode: stream events file
    if args.action == "watch":
        path = os.environ.get("MSMACRO_EVENTS", "/run/msmacro.events")
        print(f"[watch] {path} (Ctrl+C to stop)")
        while not os.path.exists(path):
            time.sleep(0.2)
        with open(path, "r") as f:
            f.seek(0, os.SEEK_END)
            try:
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.2)
                        continue
                    print(line.strip())
            except KeyboardInterrupt:
                return

    payload = {}
    if args.action == "status":
        payload = {"cmd": "status"}
    elif args.action == "record-start":
        payload = {"cmd": "record_start"}
    elif args.action == "record-stop":
        which = "discard"
        if args.save:
            which = "save"
        if args.play_now:
            which = "play_now"
        payload = {"cmd": "record_stop", "action": which, "name": args.name}
    elif args.action == "play":
        payload = {
            "cmd": "play",
            "file": args.file,
            "speed": args.speed,
            "jitter_time": args.jitter_time,
            "jitter_hold": args.jitter_hold,
            "loop": args.loop,
        }
    elif args.action == "stop":
        payload = {"cmd": "stop"}
    elif args.action == "list":
        payload = {"cmd": "list"}
    elif args.action == "save-last":
        payload = {"cmd": "save_last", "name": args.name}
    else:
        # 'watch' returns above
        if args.action != "watch":
            raise SystemExit("unknown ctl action")
        return

    result = asyncio.run(send(SETTINGS.socket_path, payload))
    print(json.dumps(result, indent=2))


# ---------- arg parsing ----------

def build_parser():
    ap = argparse.ArgumentParser(
        prog="msmacro", description="Pi HID keyboard bridge/recorder/player/daemon"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # manual/foreground modes
    a = sub.add_parser("live", help="Bridge keyboard → target (record with hotkey)")
    a.add_argument("--device", help="evdev device path")
    a.add_argument("--stop-hotkey", default=SETTINGS.stop_hotkey)
    a.add_argument("--record-hotkey", default=SETTINGS.record_hotkey)
    a.set_defaults(func=cmd_live)

    r = sub.add_parser("record", help="One-shot record; in live you can press the record hotkey")
    r.add_argument("--device", help="evdev device path")
    r.add_argument("--stop-hotkey", default=SETTINGS.stop_hotkey)
    r.add_argument("--record-hotkey", default=SETTINGS.record_hotkey)
    r.set_defaults(func=cmd_record)

    l = sub.add_parser("list", help="List recordings")
    l.set_defaults(func=cmd_list)

    p = sub.add_parser("play", help="Play a saved recording (stop with hotkey)")
    p.add_argument("file", nargs="?", help="file name or path (with/without .json)")
    p.add_argument("--pick", action="store_true", help="choose interactively from records dir")
    p.add_argument("--device", help="evdev device path for hotkey watching")
    p.add_argument("--stop-hotkey", default=SETTINGS.stop_hotkey)
    p.set_defaults(func=cmd_play)

    # daemon (for systemd)
    d = sub.add_parser("daemon", help="Run background daemon with control socket")
    d.add_argument("--device", default="auto", help='"auto" (default) or explicit /dev/input/eventX')
    d.set_defaults(func=cmd_daemon)

    # ctl (remote control)
    c = sub.add_parser("ctl", help="Control a running msmacro daemon")
    c_sub = c.add_subparsers(dest="action", required=True)

    c1 = c_sub.add_parser("status")
    c1.set_defaults(func=cmd_ctl)

    c2 = c_sub.add_parser("record-start")
    c2.set_defaults(func=cmd_ctl)

    c3 = c_sub.add_parser("record-stop")
    c3.add_argument("--save", action="store_true")
    c3.add_argument("--play-now", action="store_true")
    c3.add_argument("--name", help="file name when saving")
    c3.set_defaults(func=cmd_ctl)

    c4 = c_sub.add_parser("play")
    c4.add_argument("file")
    c4.add_argument("--speed", type=float, default=1.0)
    c4.add_argument("--jitter-time", type=float, default=0.0)
    c4.add_argument("--jitter-hold", type=float, default=0.0)
    c4.add_argument("--loop", type=int, default=1)
    c4.set_defaults(func=cmd_ctl)

    c5 = c_sub.add_parser("stop")  # stop playback → bridge
    c5.set_defaults(func=cmd_ctl)

    c6 = c_sub.add_parser("list")
    c6.set_defaults(func=cmd_ctl)

    c7 = c_sub.add_parser("save-last")
    c7.add_argument("--name", required=True)
    c7.set_defaults(func=cmd_ctl)

    c8 = c_sub.add_parser("watch")
    c8.set_defaults(func=cmd_ctl)

    return ap


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
