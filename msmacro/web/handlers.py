import asyncio, json, os, time
from pathlib import Path
from aiohttp import web

from ..config import SETTINGS
from ..ipc import send
from ..events import path as events_path
from .validation import safe_record_path

def _rec_dir() -> Path:
    d = Path(SETTINGS.record_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d

async def api_status(request: web.Request):
    try:
        st = await send(SETTINGS.socket_path, {"cmd": "status"})
    except Exception as e:
        raise web.HTTPServiceUnavailable(text=f"daemon: {e}")
    files = []
    for f in sorted(_rec_dir().glob("*.json")):
        try:
            stat = f.stat()
            files.append({"name": f.name, "size": stat.st_size, "mtime": int(stat.st_mtime)})
        except FileNotFoundError:
            pass
    st["files"] = files
    st["web_record_dir"] = str(_rec_dir())
    return web.json_response(st)

async def api_record_start(request: web.Request):
    await send(SETTINGS.socket_path, {"cmd": "record_start"})
    return web.json_response({"ok": True})

async def api_record_stop(request: web.Request):
    payload = await request.json()
    action = payload.get("action", "discard")
    name = payload.get("name")
    res = await send(SETTINGS.socket_path, {"cmd": "record_stop", "action": action, "name": name})
    return web.json_response({"ok": True, "result": res})

async def api_play(request: web.Request):
    payload = await request.json()
    file = payload.get("file")
    if not file:
        raise web.HTTPBadRequest(text="missing file")
    args = {
        "cmd": "play",
        "file": file,
        "speed": float(payload.get("speed", 1.0)),
        "jitter_time": float(payload.get("jitter_time", 0.0)),
        "jitter_hold": float(payload.get("jitter_hold", 0.0)),
        "loop": int(payload.get("loop", 1)),
    }
    res = await send(SETTINGS.socket_path, args)
    return web.json_response({"ok": True, "result": res})

async def api_stop(request: web.Request):
    res = await send(SETTINGS.socket_path, {"cmd": "stop"})
    return web.json_response({"ok": True, "result": res})

async def api_rename(request: web.Request):
    payload = await request.json()
    old = payload.get("old"); new = payload.get("new")
    if not old or not new:
        raise web.HTTPBadRequest(text="missing names")
    src = safe_record_path(_rec_dir(), old)
    dst = safe_record_path(_rec_dir(), new)
    if not src.exists():
        raise web.HTTPNotFound(text="source missing")
    if dst.exists():
        raise web.HTTPConflict(text="destination exists")
    src.rename(dst)
    return web.jsonResponse({"ok": True, "result": {"renamed": [src.name, dst.name]}})

async def api_delete(request: web.Request):
    name = request.match_info["name"]
    p = safe_record_path(_rec_dir(), name)
    try:
        p.unlink()
    except FileNotFoundError:
        pass
    return web.json_response({"ok": True, "result": {"deleted": p.name}})

# Server-Sent Events: stream daemon events file
async def api_events(request: web.Request):
    resp = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
    await resp.prepare(request)

    path = events_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).touch(exist_ok=True)

    try:
        with open(path, "r") as f:
            f.seek(0, os.SEEK_END)
            ticks = 0
            while True:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.25)
                    ticks += 1
                    if ticks % 40 == 0:
                        try:
                            await resp.write(b": hb\n\n")
                        except (asyncio.CancelledError, ConnectionResetError, RuntimeError):
                            break
                    continue
                payload = line.strip().encode()
                try:
                    await resp.write(b"data: " + payload + b"\n\n")
                except (asyncio.CancelledError, ConnectionResetError, RuntimeError):
                    break
    finally:
        pass

    return resp
