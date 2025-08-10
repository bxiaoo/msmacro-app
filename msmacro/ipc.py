import asyncio, json, os, pathlib
from contextlib import suppress

async def start_server(path, handler, *, mode=0o666):
    p = pathlib.Path(path)
    if p.exists():
        with suppress(FileNotFoundError):
            p.unlink()
    p.parent.mkdir(parents=True, exist_ok=True)
    server = await asyncio.start_unix_server(lambda r, w: _serve_one(r, w, handler), path=path)
    os.chmod(path, mode)  # simple: any local user can control; tighten if needed
    return server

async def _serve_one(reader, writer, handler):
    try:
        data = await reader.readline()
        if not data:
            return
        msg = json.loads(data.decode("utf-8"))
        result = await handler(msg)
        writer.write((json.dumps({"ok": True, "result": result}) + "\n").encode("utf-8"))
        await writer.drain()
    except Exception as e:
        writer.write((json.dumps({"ok": False, "error": str(e)}) + "\n").encode("utf-8"))
        with suppress(Exception):
            await writer.drain()
    finally:
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()

async def send(path, payload: dict, timeout=5.0):
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(path), timeout=timeout)
    writer.write((json.dumps(payload) + "\n").encode("utf-8"))
    await writer.drain()
    line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    if not line:
        raise RuntimeError("no response")
    resp = json.loads(line.decode("utf-8"))
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error", "unknown error"))
    return resp["result"]
