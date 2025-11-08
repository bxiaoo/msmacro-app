import asyncio
import json
import time
import contextlib
import logging
import os
from pathlib import Path
from aiohttp import web

from ..utils.config import SETTINGS
from ..io.ipc import send
from .validation import safe_record_path

# Optional imports for mini-map preview
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    log.warning("cv2/numpy not available - mini-map preview endpoint will be disabled")

log = logging.getLogger(__name__)

_frame_path_env = os.environ.get("MSMACRO_CV_FRAME_PATH", "/dev/shm/msmacro_cv_frame.jpg").strip()
SHARED_FRAME_PATH = Path(_frame_path_env) if _frame_path_env else None
_meta_path_env = os.environ.get("MSMACRO_CV_META_PATH", "").strip()
if _meta_path_env:
    SHARED_META_PATH = Path(_meta_path_env)
elif SHARED_FRAME_PATH is not None:
    SHARED_META_PATH = SHARED_FRAME_PATH.with_suffix(".json")
else:
    SHARED_META_PATH = None

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

            # Check for object detection updates
            try:
                obj_det = await _daemon("object_detection_status")
                if obj_det.get("enabled") and obj_det.get("last_result"):
                    await send_event({
                        "type": "object_detection",
                        "result": obj_det["last_result"]
                    })
            except Exception:
                pass

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


async def api_skills_reorder(request: web.Request):
    """Reorder skills and update grouping information."""
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "invalid json"}, 400)

    # Validate that we have skills data
    if not isinstance(body, list):
        return _json({"error": "expected array of skills"}, 400)

    try:
        resp = await _daemon("reorder_skills", skills_data=body)
        # Extract skills array from response
        skills = resp.get("skills", [])
        return _json(skills)
    except Exception as e:
        return _json({"error": str(e)}, 500)


# ---------- CV (Computer Vision) Management ----------

async def api_cv_status(request: web.Request):
    """Get CV capture device status and frame information."""
    try:
        resp = await _daemon("cv_status")
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_cv_screenshot(request: web.Request):
    """Get the latest captured frame as JPEG image via shared memory frame file."""
    if SHARED_FRAME_PATH is None:
        log.error("Shared frame path not configured; set MSMACRO_CV_FRAME_PATH")
        return _json({"error": "shared frame path not configured"}, 503)

    try:
        status = await _daemon("cv_status")
    except Exception as e:
        log.warning("Failed to fetch CV status for screenshot: %s", e)
        return _json({"error": str(e)}, 503)

    if not status.get("capturing") or not status.get("has_frame"):
        log.debug("Screenshot requested but capture inactive or no recent frame")
        return _json({"error": "no frame available"}, 404)

    try:
        jpeg_data = SHARED_FRAME_PATH.read_bytes()
    except FileNotFoundError:
        log.debug("Shared CV frame missing at %s", SHARED_FRAME_PATH)
        return _json({"error": "no frame available"}, 404)
    except Exception as e:
        log.warning("Failed to read shared CV frame: %s", e)
        return _json({"error": "failed to read frame"}, 500)

    metadata = status.get("frame") or {}
    if SHARED_META_PATH and SHARED_META_PATH.exists():
        try:
            metadata = json.loads(SHARED_META_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            log.debug("Failed to parse shared CV metadata: %s", e)

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    if isinstance(metadata, dict):
        for key in ("width", "height", "size_bytes", "timestamp"):
            if key in metadata:
                header_key = f"X-CV-Frame-{key.replace('_', '-').title()}"
                headers[header_key] = str(metadata[key])

        # Add region detection metadata to headers
        # Note: region_confidence and region_white_ratio are deprecated (always 0.0)
        # With map_config, the region is user-defined, not auto-detected
        region_keys = (
            "region_detected",
            "region_x",
            "region_y",
            "region_width",
            "region_height",
            "region_confidence",  # Deprecated: always 0.0
            "region_white_ratio"  # Deprecated: always 0.0
        )
        for key in region_keys:
            if key in metadata:
                header_key = f"X-CV-Region-{key.replace('_', '-').title()}"
                headers[header_key] = str(metadata[key])

    return web.Response(body=jpeg_data, content_type="image/jpeg", headers=headers)


async def api_cv_minimap_preview(request: web.Request):
    """
    Get cropped mini-map preview image for configuration.

    Query parameters:
    - x: Top-left X coordinate (default: 68)
    - y: Top-left Y coordinate (default: 56)
    - w: Width (default: 340)
    - h: Height (default: 86)
    - t: Timestamp for cache busting (ignored)

    Returns: Cropped JPEG image with red border
    """
    if not CV2_AVAILABLE:
        return _json({"error": "cv2/numpy not available"}, 503)

    if SHARED_FRAME_PATH is None:
        log.error("Shared frame path not configured; set MSMACRO_CV_FRAME_PATH")
        return _json({"error": "shared frame path not configured"}, 503)

    # Parse query parameters
    try:
        x = int(request.query.get('x', 68))
        y = int(request.query.get('y', 56))
        w = int(request.query.get('w', 340))
        h = int(request.query.get('h', 86))
    except (ValueError, TypeError):
        return _json({"error": "invalid coordinate parameters"}, 400)

    # Validate coordinates
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        return _json({"error": "coordinates must be non-negative and dimensions positive"}, 400)

    if x + w > 1280 or y + h > 720:
        return _json({"error": "coordinates out of bounds (max 1280x720)"}, 400)

    # Get CV status
    try:
        status = await _daemon("cv_status")
    except Exception as e:
        log.warning("Failed to fetch CV status for mini-map preview: %s", e)
        return _json({"error": str(e)}, 503)

    if not status.get("capturing") or not status.get("has_frame"):
        log.debug("Mini-map preview requested but capture inactive or no recent frame")
        return _json({"error": "no frame available"}, 404)

    # Read shared frame
    try:
        jpeg_data = SHARED_FRAME_PATH.read_bytes()
    except FileNotFoundError:
        log.debug("Shared CV frame missing at %s", SHARED_FRAME_PATH)
        return _json({"error": "no frame available"}, 404)
    except Exception as e:
        log.warning("Failed to read shared CV frame for mini-map preview: %s", e)
        return _json({"error": "failed to read frame"}, 500)

    try:
        # Decode JPEG to numpy array
        nparr = np.frombuffer(jpeg_data, dtype=np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return _json({"error": "failed to decode frame"}, 500)

        # Crop to region
        cropped = frame[y:y+h, x:x+w]

        if cropped.size == 0:
            return _json({"error": "invalid crop region"}, 400)

        # Draw red border (2px thick)
        cv2.rectangle(cropped, (0, 0), (w-1, h-1), (0, 0, 255), 2)

        # Encode as JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        success, jpeg_encoded = cv2.imencode('.jpg', cropped, encode_param)

        if not success:
            return _json({"error": "failed to encode cropped frame"}, 500)

        # Return cropped JPEG
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-MiniMap-X": str(x),
            "X-MiniMap-Y": str(y),
            "X-MiniMap-Width": str(w),
            "X-MiniMap-Height": str(h),
        }

        return web.Response(
            body=jpeg_encoded.tobytes(),
            content_type="image/jpeg",
            headers=headers
        )

    except Exception as e:
        log.error("Mini-map preview processing error: %s", e)
        return _json({"error": f"processing failed: {str(e)}"}, 500)


async def api_cv_start(request: web.Request):
    """Start CV capture system."""
    try:
        resp = await _daemon("cv_start")
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_cv_stop(request: web.Request):
    """Stop CV capture system."""
    try:
        resp = await _daemon("cv_stop")
        return _json(resp)
    except Exception as e:
        return _json({"error": str(e)}, 500)


async def api_cv_map_configs_list(request: web.Request):
    """
    Get all saved map configurations.

    Returns:
        List of map configs with all details
    """
    try:
        from msmacro.cv.map_config import get_manager

        manager = get_manager()
        configs = manager.list_configs()

        return _json({
            "configs": [config.to_dict() for config in configs]
        })
    except Exception as e:
        log.error(f"Failed to list map configs: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_cv_map_configs_create(request: web.Request):
    """
    Create a new map configuration.

    Request body (JSON):
        {
            "name": "My Map",
            "tl_x": 68,
            "tl_y": 56,
            "width": 340,
            "height": 86
        }

    Returns:
        Created config object
    """
    try:
        from msmacro.cv.map_config import get_manager, MapConfig
        import time

        data = await request.json()

        # Validate required fields
        required_fields = ["name", "tl_x", "tl_y", "width", "height"]
        for field in required_fields:
            if field not in data:
                return _json({"error": f"Missing required field: {field}"}, 400)

        # Create config object
        config = MapConfig(
            name=data["name"],
            tl_x=int(data["tl_x"]),
            tl_y=int(data["tl_y"]),
            width=int(data["width"]),
            height=int(data["height"]),
            created_at=time.time(),
            last_used_at=0.0,
            is_active=False
        )

        manager = get_manager()
        manager.save_config(config)

        return _json({
            "success": True,
            "config": config.to_dict()
        })

    except ValueError as e:
        return _json({"error": str(e)}, 400)
    except Exception as e:
        log.error(f"Failed to create map config: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_cv_map_configs_delete(request: web.Request):
    """
    Delete a map configuration.

    URL parameter:
        name: Config name to delete

    Returns:
        Success status
    """
    try:
        from msmacro.cv.map_config import get_manager

        name = request.match_info.get("name")
        if not name:
            return _json({"error": "Config name required"}, 400)

        manager = get_manager()
        deleted = manager.delete_config(name)

        if not deleted:
            return _json({"error": "Config not found or cannot be deleted (is active)"}, 404)

        return _json({"success": True})

    except Exception as e:
        log.error(f"Failed to delete map config: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_cv_map_configs_activate(request: web.Request):
    """
    Activate a map configuration.

    URL parameter:
        name: Config name to activate

    Returns:
        Activated config object
    """
    try:
        from msmacro.cv.map_config import get_manager

        name = request.match_info.get("name")
        if not name:
            return _json({"error": "Config name required"}, 400)

        manager = get_manager()
        config = manager.activate_config(name)

        if not config:
            return _json({"error": "Config not found"}, 404)

        # Notify daemon to reload config
        try:
            await _daemon("cv_reload_config")
        except Exception as e:
            log.warning(f"Failed to notify daemon of config change: {e}")

        return _json({
            "success": True,
            "config": config.to_dict()
        })

    except Exception as e:
        log.error(f"Failed to activate map config: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_cv_map_configs_get_active(request: web.Request):
    """
    Get the currently active map configuration.

    Returns:
        Active config object or null if none active
    """
    try:
        from msmacro.cv.map_config import get_manager

        manager = get_manager()
        config = manager.get_active_config()

        return _json({
            "config": config.to_dict() if config else None
        })

    except Exception as e:
        log.error(f"Failed to get active map config: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_cv_map_configs_deactivate(request: web.Request):
    """
    Deactivate the current map configuration (revert to full-screen detection).

    Returns:
        Success status
    """
    try:
        from msmacro.cv.map_config import get_manager

        manager = get_manager()
        manager.deactivate()

        # Notify daemon to reload config
        try:
            await _daemon("cv_reload_config")
        except Exception as e:
            log.warning(f"Failed to notify daemon of config change: {e}")

        return _json({"success": True})

    except Exception as e:
        log.error(f"Failed to deactivate map config: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_system_stats(request: web.Request):
    """
    Get system performance statistics (CPU, RAM, disk, temperature).

    Returns:
        System stats including:
        - cpu_percent: Overall CPU usage percentage
        - cpu_count: Number of CPU cores
        - memory_percent: RAM usage percentage
        - memory_available_mb: Available RAM in MB
        - memory_total_mb: Total RAM in MB
        - disk_percent: Disk usage percentage
        - disk_free_gb: Free disk space in GB
        - temperature: CPU temperature in Celsius (Pi only)
        - uptime_seconds: System uptime in seconds
    """
    try:
        stats = await _daemon("system_stats")
        return _json(stats)
    except Exception as e:
        log.error(f"Failed to get system stats: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_object_detection_status(request: web.Request):
    """
    Get object detection status and latest result.
    
    Returns:
        Object detection status with:
        - enabled: Boolean
        - last_result: Latest detection result (or null)
    """
    try:
        result = await _daemon("object_detection_status")
        return _json(result)
    except Exception as e:
        log.error(f"Failed to get object detection status: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_object_detection_start(request: web.Request):
    """
    Start object detection.
    
    JSON Body (optional):
        config: Detector configuration dict
    
    Returns:
        Success status
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    config = body.get("config")
    
    try:
        result = await _daemon("object_detection_start", config=config)
        return _json(result)
    except Exception as e:
        log.error(f"Failed to start object detection: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_object_detection_stop(request: web.Request):
    """
    Stop object detection.
    
    Returns:
        Success status
    """
    try:
        result = await _daemon("object_detection_stop")
        return _json(result)
    except Exception as e:
        log.error(f"Failed to stop object detection: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_object_detection_config(request: web.Request):
    """
    Update object detection configuration.
    
    JSON Body:
        config: New detector configuration dict
    
    Returns:
        Success status
    """
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "Invalid JSON body"}, 400)
    
    config = body.get("config")
    
    if not config:
        return _json({"error": "config field required"}, 400)
    
    try:
        result = await _daemon("object_detection_config", config=config)
        return _json(result)
    except Exception as e:
        log.error(f"Failed to update object detection config: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_object_detection_config_save(request: web.Request):
    """
    Save current object detection config to disk.
    
    JSON Body (optional):
        metadata: Optional metadata dict (e.g., calibration_source)
    
    Returns:
        Success status and config file path
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    metadata = body.get("metadata", {})
    
    try:
        result = await _daemon("object_detection_config_save", metadata=metadata)
        return _json(result)
    except Exception as e:
        log.error(f"Failed to save object detection config: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_object_detection_config_export(request: web.Request):
    """
    Export current object detection config as JSON.
    
    Returns:
        Config dictionary
    """
    try:
        result = await _daemon("object_detection_config_export")
        return _json(result)
    except Exception as e:
        log.error(f"Failed to export object detection config: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_object_detection_performance(request: web.Request):
    """
    Get object detection performance statistics.
    
    Returns:
        Performance stats (avg_ms, max_ms, min_ms, count)
    """
    try:
        result = await _daemon("object_detection_performance")
        return _json(result)
    except Exception as e:
        log.error(f"Failed to get object detection performance: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_cv_frame_lossless(request: web.Request):
    """
    Serve latest CV frame as lossless PNG (not JPEG).
    For calibration UI to avoid compression artifacts.
    
    Returns:
        PNG image of minimap region (340x86)
    """
    try:
        # Get frame via IPC
        result = await _daemon("cv_get_frame")
        
        if "error" in result:
            return web.Response(status=500, text=result["error"])
        
        # Frame is base64-encoded JPEG from daemon
        # Decode and re-encode as PNG for lossless quality
        import base64
        import cv2
        import numpy as np
        
        frame_b64 = result.get("frame")
        if not frame_b64:
            return web.Response(status=500, text="No frame data")
        
        # Decode JPEG
        img_bytes = base64.b64decode(frame_b64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if frame is None:
            return web.Response(status=500, text="Failed to decode frame")
        
        # Encode as PNG (lossless)
        success, png_bytes = cv2.imencode('.png', frame)
        
        if not success:
            return web.Response(status=500, text="PNG encoding failed")
        
        return web.Response(
            body=png_bytes.tobytes(),
            content_type="image/png",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except Exception as e:
        log.error(f"Failed to serve lossless frame: {e}", exc_info=True)
        return web.Response(status=500, text=str(e))


async def api_object_detection_calibrate(request: web.Request):
    """
    Auto-calibrate HSV color ranges from user click samples.
    
    Request body:
        {
            "color_type": "player" | "other_player",
            "samples": [
                {"frame": "base64_png", "x": int, "y": int},
                ...
            ]
        }
    
    Returns:
        {
            "success": bool,
            "hsv_lower": [h, s, v],
            "hsv_upper": [h, s, v],
            "preview_mask": "base64_png"
        }
    """
    try:
        body = await request.json()
        result = await _daemon("object_detection_calibrate", **body)
        return _json(result)
    except Exception as e:
        log.error(f"Failed to calibrate: {e}", exc_info=True)
        return _json({"success": False, "error": str(e)}, 500)
