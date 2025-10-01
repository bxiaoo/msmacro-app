import asyncio
import json
import time
import contextlib
from pathlib import Path
from aiohttp import web

from ..utils.config import SETTINGS
from ..io.ipc import send
from .validation import safe_record_path

# ---------- helpers ----------

def _rec_dir() -> Path:
    d = Path(getattr(SETTINGS, "record_dir", "./records"))
    d.mkdir(parents=True, exist_ok=True)
    return d

async def _daemon(cmd: str, **payload):
    return await send(getattr(SETTINGS, "socket_path", "/run/msmacro.sock"), {"cmd": cmd, **payload})

def _json(data, status=200):
    return web.json_response(data, status=status)


# ---------- API handlers ----------

async def api_status(request: web.Request):
    """Get current daemon status and file tree."""
    try:
        st = await _daemon("status")
    except Exception as e:
        return _json({"error": f"ipc: {e}"}, 500)

    # Get recursive tree for UI
    try:
        tree = await _daemon("list_recursive")
    except Exception:
        tree = {"items": []}

    st["tree"] = tree.get("items", [])
    return _json(st)


async def api_list_files(request: web.Request):
    """List all recording files."""
    try:
        resp = await _daemon("list")
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_record_start(request: web.Request):
    """Start recording keystrokes."""
    try:
        resp = await _daemon("record_start")
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_record_stop(request: web.Request):
    """Stop recording with optional save/discard action."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    action = (body.get("action") or "").lower()
    name = body.get("name")

    stop_err = None
    try:
        await _daemon("stop")
    except Exception as e:
        stop_err = str(e)

    # Wait a bit for mode transition
    await asyncio.sleep(0.5)

    save_info = None
    if action == "save" and name:
        # Wait for daemon to have last_actions ready
        for _ in range(10):
            try:
                st = await _daemon("status")
                if st.get("have_last_actions"):
                    break
            except Exception:
                pass
            await asyncio.sleep(0.2)
        
        try:
            save_info = await _daemon("save_last", name=name)
        except Exception as e:
            save_info = {"error": str(e)}
            
    elif action == "discard":
        try:
            await _daemon("discard_last")
        except Exception:
            pass

    out = {"ok": True, "stopped": True}
    if save_info:
        out.update(save_info)
    if stop_err:
        out["warning"] = stop_err
    return _json(out)


# PostRecord endpoints
async def api_post_save(request: web.Request):
    """Save the last recording (POSTRECORD mode)."""
    try:
        body = await request.json()
        name = body.get("name")
        if not name:
            return _json({"error": "name required"}, 400)
        
        resp = await _daemon("save_last", name=name)
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_post_preview(request: web.Request):
    """Preview play the last recording once."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    try:
        resp = await _daemon("preview_last",
                            speed=float(body.get("speed", 1.0)),
                            jitter_time=float(body.get("jitter_time", 0.0)),
                            jitter_hold=float(body.get("jitter_hold", 0.0)),
                            ignore_keys=body.get("ignore_keys", []),
                            ignore_tolerance=float(body.get("ignore_tolerance", 0.0)))
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_post_discard(request: web.Request):
    """Discard the last recording and return to BRIDGE mode."""
    try:
        resp = await _daemon("discard_last")
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_play(request: web.Request):
    """Play one or more recordings (playlist support)."""
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "invalid json"}, 400)

    speed = float(body.get("speed", 1.0))
    jitter_time = float(body.get("jitter_time", 0.0))
    jitter_hold = float(body.get("jitter_hold", 0.0))
    loop = int(body.get("loop", 1))
    ignore_keys = body.get("ignore_keys", [])
    ignore_tolerance = float(body.get("ignore_tolerance", 0.0))
    active_skills = body.get("active_skills", [])

    # Handle playlist (multiple files)
    if "names" in body:
        names = body.get("names") or []
        if not isinstance(names, list) or not names:
            return _json({"error": "empty names"}, 400)
        try:
            resp = await _daemon(
                "play_selection",
                names=names,
                speed=speed,
                jitter_time=jitter_time,
                jitter_hold=jitter_hold,
                loop=loop,
                ignore_keys=ignore_keys,
                ignore_tolerance=ignore_tolerance,
                active_skills=active_skills,
            )
            return _json(resp)
        except Exception as e:
            return _json({"error": str(e)}, 500)

    # Handle single file
    file = body.get("file")
    if not file:
        return _json({"error": "missing file or names"}, 400)
    try:
        resp = await _daemon("play",
                           file=file,
                           speed=speed,
                           jitter_time=jitter_time,
                           jitter_hold=jitter_hold,
                           loop=loop,
                           ignore_keys=ignore_keys,
                           ignore_tolerance=ignore_tolerance,
                           active_skills=active_skills)
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_stop(request: web.Request):
    """Stop current recording or playback."""
    try:
        resp = await _daemon("stop")
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_files_rename(request: web.Request):
    """Rename a recording file."""
    try:
        body = await request.json()
        old = body.get("old")
        new = body.get("new")
    except Exception:
        return _json({"error": "invalid json"}, 400)

    if not old or not new:
        return _json({"error": "missing old/new"}, 400)

    try:
        resp = await _daemon("rename_recording", old=old, new=new)
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_files_delete(request: web.Request):
    """Delete a recording file."""
    name = request.match_info.get("name")
    if not name:
        return _json({"error": "missing name"}, 400)
    
    try:
        p = safe_record_path(_rec_dir(), name)
    except Exception as e:
        return _json({"error": f"invalid name: {e}"}, 400)

    if not p.exists():
        return _json({"error": "file not found"}, 404)

    try:
        p.unlink()
        return _json({"ok": True, "deleted": str(p)})
    except Exception as e:
        return _json({"error": f"delete failed: {e}"}, 500)


async def api_folders_delete(request: web.Request):
    """Delete a folder (optionally recursive)."""
    path = request.match_info.get("path")
    recurse = request.query.get("recurse", "").lower() in ("1", "true", "yes")
    
    if not path:
        return _json({"error": "missing path"}, 400)
    
    # Sanitize path
    base_dir = _rec_dir()
    try:
        # Remove any leading/trailing slashes and resolve
        clean_path = Path(str(path).strip("/"))
        if ".." in clean_path.parts:
            raise ValueError("Invalid path")
        
        folder_path = (base_dir / clean_path).resolve()
        
        # Ensure it's within base_dir
        if not str(folder_path).startswith(str(base_dir)):
            raise ValueError("Path outside base directory")
    except Exception as e:
        return _json({"error": f"invalid path: {e}"}, 400)
    
    if not folder_path.exists():
        return _json({"error": "folder not found"}, 404)
    
    if not folder_path.is_dir():
        return _json({"error": "not a directory"}, 400)
    
    try:
        if recurse:
            import shutil
            shutil.rmtree(folder_path)
        else:
            folder_path.rmdir()  # Will fail if not empty
        return _json({"ok": True, "deleted": str(folder_path), "recursive": recurse})
    except OSError as e:
        if not recurse and "not empty" in str(e).lower():
            return _json({"error": "folder not empty"}, 400)
        return _json({"error": f"delete failed: {e}"}, 500)


async def api_events(request: web.Request):
    """Server-Sent Events stream for real-time status updates."""
    resp = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
        }
    )
    await resp.prepare(request)

    async def send_event(obj: dict):
        data = json.dumps(obj, separators=(',', ':')).encode()
        await resp.write(b"data: " + data + b"\n\n")

    # Get initial state
    try:
        st = await _daemon("status")
    except Exception:
        st = {"mode": "UNKNOWN", "files": []}
    
    last_mode = st.get("mode")
    last_files_msum = sum(int(f.get("mtime", 0)) for f in st.get("files", []))

    # Send initial state
    await send_event({"type": "mode", "mode": last_mode})
    await send_event({"type": "files", "files": st.get("files", [])})

    try:
        while True:
            await asyncio.sleep(1.0)
            
            # Poll daemon status
            try:
                st = await _daemon("status")
            except Exception:
                # Keep streaming heartbeats even if daemon is down
                with contextlib.suppress(Exception):
                    await resp.write(b": hb\n\n")
                continue

            # Check for mode changes
            mode = st.get("mode")
            if mode != last_mode:
                last_mode = mode
                await send_event({"type": "mode", "mode": mode})

            # Check for file changes
            files = st.get("files", [])
            msum = sum(int(f.get("mtime", 0)) for f in files)
            if msum != last_files_msum:
                last_files_msum = msum
                await send_event({"type": "files", "files": files})

            # Send heartbeat
            with contextlib.suppress(Exception):
                await resp.write(b": hb\n\n")

    except (asyncio.CancelledError, ConnectionResetError, RuntimeError):
        pass
    finally:
        with contextlib.suppress(Exception):
            await resp.write_eof()
    return resp


# ---------- CD Skills Management ----------

async def api_skills_list(request: web.Request):
    """List all skill configurations."""
    try:
        resp = await _daemon("list_skills")
        # Extract skills array from response
        skills = resp.get("skills", [])
        return _json(skills)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_skills_save(request: web.Request):
    """Save a new skill configuration."""
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "invalid json"}, 400)

    # Validate required fields
    if not body.get("name") or not body.get("keystroke"):
        return _json({"error": "name and keystroke are required"}, 400)

    try:
        resp = await _daemon("save_skill", skill_data=body)
        # Extract skill object from response
        skill = resp.get("skill", {})
        return _json(skill)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_skills_update(request: web.Request):
    """Update an existing skill configuration."""
    skill_id = request.match_info.get("id")
    if not skill_id:
        return _json({"error": "missing skill id"}, 400)

    try:
        body = await request.json()
    except Exception:
        return _json({"error": "invalid json"}, 400)

    try:
        resp = await _daemon("update_skill", skill_id=skill_id, skill_data=body)
        # Extract skill object from response
        skill = resp.get("skill", {})
        return _json(skill)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_skills_delete(request: web.Request):
    """Delete a skill configuration."""
    skill_id = request.match_info.get("id")
    if not skill_id:
        return _json({"error": "missing skill id"}, 400)

    try:
        resp = await _daemon("delete_skill", skill_id=skill_id)
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_skills_selected(request: web.Request):
    """Get skills marked as selected for active use."""
    try:
        resp = await _daemon("get_selected_skills")
        # Extract skills array from response
        skills = resp.get("skills", [])
        return _json(skills)
    except Exception as e:
        return _json({"error": str(e)}, 500)
