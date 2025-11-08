import asyncio, json, os, pathlib
from contextlib import suppress

async def start_server(path, handler, *, mode=0o600):
    p = pathlib.Path(path)
    if p.exists():
        with suppress(FileNotFoundError):
            p.unlink()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Set limit to 2MB to support large frame data transfers (base64-encoded JPEGs can be ~300KB)
    server = await asyncio.start_unix_server(lambda r, w: _serve_one(r, w, handler), path=path, limit=2**21)
    os.chmod(path, mode)  # owner-only access for security
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
    # Set limit to 2MB to support large frame data transfers (base64-encoded JPEGs can be ~300KB)
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(path, limit=2**21), timeout=timeout)
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
