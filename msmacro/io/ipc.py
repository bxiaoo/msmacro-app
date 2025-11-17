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
    """
    Send IPC command to daemon and wait for response.

    Args:
        path: Unix socket path
        payload: Command dict to send
        timeout: Total timeout for both connection and response (default 5.0s)

    Raises:
        asyncio.TimeoutError: If connection or response takes too long
        RuntimeError: If no response or daemon returns error
    """
    # Set limit to 2MB to support large frame data transfers (base64-encoded JPEGs can be ~300KB)
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(path, limit=2**21), timeout=timeout)
    try:
        writer.write((json.dumps(payload) + "\n").encode("utf-8"))
        await writer.drain()

        # CRITICAL FIX: Add timeout to readline to prevent indefinite hangs
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)

        if not line:
            raise RuntimeError("no response")
        resp = json.loads(line.decode("utf-8"))
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error", "unknown error"))
        return resp["result"]
    finally:
        writer.close()
        await writer.wait_closed()
