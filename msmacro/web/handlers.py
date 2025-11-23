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

async def _daemon(cmd: str, timeout: float = 5.0, **payload):
    """
    Send IPC command to daemon.

    Args:
        cmd: Command name
        timeout: IPC timeout in seconds (default 5.0, use higher for CV operations)
        **payload: Additional command parameters
    """
    return await send(getattr(SETTINGS, "socket_path", "/run/msmacro.sock"), {"cmd": cmd, **payload}, timeout=timeout)

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

            # Check for CV-AUTO status updates
            try:
                cv_auto = await _daemon("cv_auto_status")
                if cv_auto.get("enabled"):
                    await send_event({
                        "type": "cv_auto_status",
                        "current_index": cv_auto.get("current_point_index"),
                        "current_point": cv_auto.get("current_point_name"),
                        "total_points": cv_auto.get("total_points"),
                        "player_position": cv_auto.get("player_position"),
                        "state": cv_auto.get("state"),
                        "is_at_point": cv_auto.get("is_at_point")
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
    - overlay: Optional overlay mode ("border" currently supported) - draws legacy red border
    - t: Cache busting timestamp (ignored)

    Behavior changes (2025-11-08):
    - Default response is raw crop with NO overlays
    - Image is now served as PNG to avoid double JPEG compression in calibration flows
    - Red border only drawn when overlay=border
    """
    if not CV2_AVAILABLE:
        return _json({"error": "cv2/numpy not available"}, 503)

    if SHARED_FRAME_PATH is None:
        log.error("Shared frame path not configured; set MSMACRO_CV_FRAME_PATH")
        return _json({"error": "shared frame path not configured"}, 503)

    try:
        x = int(request.query.get('x', 68))
        y = int(request.query.get('y', 56))
        w = int(request.query.get('w', 340))
        h = int(request.query.get('h', 86))
    except (ValueError, TypeError):
        return _json({"error": "invalid coordinate parameters"}, 400)

    if x < 0 or y < 0 or w <= 0 or h <= 0:
        return _json({"error": "coordinates must be non-negative and dimensions positive"}, 400)
    if x + w > 1280 or y + h > 720:
        return _json({"error": "coordinates out of bounds (max 1280x720)"}, 400)

    overlay_mode = request.query.get('overlay')

    try:
        status = await _daemon("cv_status")
    except Exception as e:
        log.warning("Failed to fetch CV status for mini-map preview: %s", e)
        return _json({"error": str(e)}, 503)

    if not status.get("capturing") or not status.get("has_frame"):
        return _json({"error": "no frame available"}, 404)

    try:
        jpeg_data = SHARED_FRAME_PATH.read_bytes()
    except FileNotFoundError:
        return _json({"error": "no frame available"}, 404)
    except Exception as e:
        log.warning("Failed to read shared CV frame for mini-map preview: %s", e)
        return _json({"error": "failed to read frame"}, 500)

    try:
        nparr = np.frombuffer(jpeg_data, dtype=np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return _json({"error": "failed to decode frame"}, 500)
        cropped = frame[y:y+h, x:x+w]
        if cropped.size == 0:
            return _json({"error": "invalid crop region"}, 400)

        if overlay_mode == 'border':
            cv2.rectangle(cropped, (0, 0), (w-1, h-1), (0, 0, 255), 2)

        success, png_encoded = cv2.imencode('.png', cropped, [int(cv2.IMWRITE_PNG_COMPRESSION), 3])
        if not success:
            return _json({"error": "failed to encode cropped frame"}, 500)

        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-MiniMap-X": str(x),
            "X-MiniMap-Y": str(y),
            "X-MiniMap-Width": str(w),
            "X-MiniMap-Height": str(h),
            "X-MiniMap-Overlay": overlay_mode or "none",
        }
        return web.Response(body=png_encoded.tobytes(), content_type="image/png", headers=headers)
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

        # Parse JSON with error handling
        try:
            data = await request.json()
        except Exception as e:
            log.warning(f"Invalid JSON in map config create request: {e}")
            return _json({"error": "Invalid JSON in request body"}, 400)

        # Validate request body is not empty
        if not data:
            log.warning("Empty request body in map config create")
            return _json({"error": "Request body cannot be empty"}, 400)

        # Validate required fields
        required_fields = ["name", "tl_x", "tl_y", "width", "height"]
        for field in required_fields:
            if field not in data:
                log.warning(f"Map config create request missing field: {field}")
                return _json({"error": f"Missing required field: {field}"}, 400)

        # Validate name is not empty
        name = str(data["name"]).strip()
        if not name:
            log.warning("Map config create request has empty name")
            return _json({"error": "Map config name cannot be empty"}, 400)

        # Validate numeric fields
        try:
            tl_x = int(data["tl_x"])
            tl_y = int(data["tl_y"])
            width = int(data["width"])
            height = int(data["height"])
        except (ValueError, TypeError) as e:
            log.warning(f"Map config create request has invalid numeric values: {e}")
            return _json({"error": "Coordinate values must be valid integers"}, 400)

        # Validate coordinate ranges
        if tl_x < 0 or tl_y < 0:
            log.warning(f"Map config '{name}' has negative coordinates: tl_x={tl_x}, tl_y={tl_y}")
            return _json({"error": "Top-left coordinates cannot be negative"}, 400)

        if width <= 0 or height <= 0:
            log.warning(f"Map config '{name}' has invalid dimensions: width={width}, height={height}")
            return _json({"error": "Width and height must be greater than 0"}, 400)

        if tl_x + width > 1280 or tl_y + height > 720:
            log.warning(f"Map config '{name}' exceeds frame bounds: ({tl_x + width}, {tl_y + height}) > (1280, 720)")
            return _json({"error": f"Region exceeds frame bounds. Max position: ({tl_x + width}, {tl_y + height}), allowed: (1280, 720)"}, 400)

        # Create config object
        try:
            config = MapConfig(
                name=name,
                tl_x=tl_x,
                tl_y=tl_y,
                width=width,
                height=height,
                created_at=time.time(),
                last_used_at=0.0,
                is_active=False
            )
        except (TypeError, ValueError) as e:
            log.warning(f"Map config '{name}' construction failed: {e}")
            return _json({"error": f"Invalid map config data: {str(e)}"}, 400)

        # Save config
        manager = get_manager()
        try:
            manager.save_config(config)
            log.info(f"✓ Created map config: {name} ({tl_x}, {tl_y}, {width}x{height})")
        except ValueError as e:
            # Config already exists or validation error
            log.warning(f"Map config '{name}' save failed: {e}")
            return _json({"error": str(e)}, 400)

        return _json({
            "success": True,
            "config": config.to_dict()
        })

    except Exception as e:
        log.error(f"Failed to create map config: {e}", exc_info=True)
        return _json({"error": "Internal server error"}, 500)


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
            reload_result = await _daemon("cv_reload_config")
            if not reload_result.get("reloaded"):
                log.error(f"Daemon failed to reload config: {reload_result}")
                return _json({
                    "error": "Failed to reload config in daemon",
                    "details": reload_result
                }, 500)
        except Exception as e:
            log.error(f"Failed to notify daemon of config change: {e}", exc_info=True)
            return _json({
                "error": "Failed to notify daemon of config change",
                "message": str(e)
            }, 500)

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


async def api_save_calibration_sample(request: web.Request):
    """
    Save the current raw minimap as a calibration sample to disk.

    Saves the minimap as a lossless PNG file for manual annotation and analysis.
    Auto-generates filename with timestamp if not provided.

    JSON Body (optional):
        filename: Custom filename (without extension, auto-generated if omitted)
        metadata: Dict with user notes, lighting conditions, etc.

    Returns:
        JSON with:
            success: bool
            filename: Saved filename
            path: Absolute path to saved file
            checksum: SHA256 checksum
            metadata_path: Path to metadata JSON
            size_bytes: Size of PNG file
            resolution: [width, height]
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    filename = body.get("filename")
    metadata = body.get("metadata", {})

    try:
        result = await _daemon("cv_save_calibration_sample", filename=filename, metadata=metadata)
        return _json(result)
    except Exception as e:
        log.error(f"Failed to save calibration sample: {e}", exc_info=True)
        return _json({"error": str(e), "success": False}, 500)


async def api_list_calibration_samples(request: web.Request):
    """
    List all calibration samples with metadata.

    Returns:
        JSON with:
            samples: List of sample objects with:
                - filename: Sample PNG filename
                - path: Absolute path
                - size_bytes: File size
                - timestamp: Creation timestamp
                - metadata: Sample metadata if available
    """
    from pathlib import Path
    from ..utils.config import DEFAULT_CALIBRATION_DIR
    import json
    import os

    try:
        samples_dir = Path(DEFAULT_CALIBRATION_DIR) / "minimap_samples"
        if not samples_dir.exists():
            return _json({"samples": []})

        samples = []
        for png_file in sorted(samples_dir.glob("*.png")):
            meta_file = png_file.with_suffix("").with_suffix(".png").parent / f"{png_file.stem}_meta.json"

            sample_info = {
                "filename": png_file.name,
                "path": str(png_file.absolute()),
                "size_bytes": png_file.stat().st_size,
                "timestamp": png_file.stat().st_mtime
            }

            # Load metadata if available
            if meta_file.exists():
                try:
                    with open(meta_file, 'r') as f:
                        sample_info["metadata"] = json.load(f)
                except Exception as e:
                    log.warning(f"Failed to load metadata for {png_file.name}: {e}")
                    sample_info["metadata"] = None

            samples.append(sample_info)

        return _json({"samples": samples})
    except Exception as e:
        log.error(f"Failed to list calibration samples: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_get_calibration_sample(request: web.Request):
    """
    Download a specific calibration sample PNG.

    URL Parameter:
        filename: Sample filename (e.g., sample_20250109_143022.png)

    Returns:
        PNG file with appropriate headers
    """
    from pathlib import Path
    from ..utils.config import DEFAULT_CALIBRATION_DIR

    filename = request.match_info.get('filename')
    if not filename:
        return _json({"error": "Filename required"}, 400)

    # Security: prevent directory traversal
    if '..' in filename or '/' in filename:
        return _json({"error": "Invalid filename"}, 400)

    try:
        samples_dir = Path(DEFAULT_CALIBRATION_DIR) / "minimap_samples"
        sample_path = samples_dir / filename

        if not sample_path.exists():
            return _json({"error": "Sample not found"}, 404)

        # Read PNG file
        with open(sample_path, 'rb') as f:
            png_data = f.read()

        return web.Response(
            body=png_data,
            content_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(png_data))
            }
        )
    except Exception as e:
        log.error(f"Failed to get calibration sample: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_download_all_calibration_samples(request: web.Request):
    """
    Download all calibration samples as a ZIP file.

    Returns:
        ZIP file containing all PNGs and metadata JSONs
    """
    from pathlib import Path
    from ..utils.config import DEFAULT_CALIBRATION_DIR
    import zipfile
    import io
    from datetime import datetime

    try:
        samples_dir = Path(DEFAULT_CALIBRATION_DIR) / "minimap_samples"
        if not samples_dir.exists():
            return _json({"error": "No samples directory found"}, 404)

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add all PNGs and metadata JSONs
            for file in samples_dir.glob("*"):
                if file.suffix in ['.png', '.json']:
                    zf.write(file, arcname=file.name)

        zip_buffer.seek(0)
        zip_data = zip_buffer.read()

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"calibration_samples_{timestamp}.zip"

        return web.Response(
            body=zip_data,
            content_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{zip_filename}"',
                "Content-Length": str(len(zip_data))
            }
        )
    except Exception as e:
        log.error(f"Failed to create ZIP: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_delete_calibration_sample(request: web.Request):
    """
    Delete a specific calibration sample (PNG + metadata).

    URL Parameter:
        filename: Sample filename (e.g., sample_20250109_143022.png)

    Returns:
        JSON with success status
    """
    from pathlib import Path
    from ..utils.config import DEFAULT_CALIBRATION_DIR

    filename = request.match_info.get('filename')
    if not filename:
        return _json({"error": "Filename required"}, 400)

    # Security: prevent directory traversal
    if '..' in filename or '/' in filename:
        return _json({"error": "Invalid filename"}, 400)

    try:
        samples_dir = Path(DEFAULT_CALIBRATION_DIR) / "minimap_samples"
        sample_path = samples_dir / filename

        if not sample_path.exists():
            return _json({"error": "Sample not found"}, 404)

        # Delete PNG
        sample_path.unlink()

        # Delete metadata JSON if exists
        meta_file = sample_path.with_suffix("").with_suffix(".png").parent / f"{sample_path.stem}_meta.json"
        if meta_file.exists():
            meta_file.unlink()

        return _json({"success": True, "message": f"Deleted {filename}"})
    except Exception as e:
        log.error(f"Failed to delete calibration sample: {e}", exc_info=True)
        return _json({"error": str(e), "success": False}, 500)


async def api_cv_frame_lossless(request: web.Request):
    """
    Serve latest minimap frame as PNG.

    Improvements (2025-11-08):
    - Accept optional manual crop query params (x,y,w,h) even if no active map config
    - Returns 404 only when neither active config nor manual coordinates supplied
    - Adds checksum header (MD5 of PNG) and echo region headers

    NOTE: Underlying source frame is currently JPEG-compressed upstream; this
    endpoint avoids an additional JPEG generation step by emitting PNG.
    """
    log.debug(f"🔵 api_cv_frame_lossless called with params: {dict(request.query)}")
    try:
        manual = False
        try:
            q = request.query
            manual_params = {k: q.get(k) for k in ("x", "y", "w", "h") if q.get(k) is not None}
            if manual_params:
                manual = True
                x = int(q.get("x", 0))
                y = int(q.get("y", 0))
                w = int(q.get("w", 0))
                h = int(q.get("h", 0))
                log.debug(f"📐 Manual crop requested: x={x}, y={y}, w={w}, h={h}")
        except (ValueError, TypeError) as e:
            log.warning(f"❌ Invalid manual crop parameters: {e}")
            return web.Response(status=400, text="Invalid manual crop parameters")

        # Use 30s timeout for CV operations (camera initialization can take 3-4s on macOS)
        log.debug("📡 Calling _daemon('cv_get_frame', timeout=30.0)...")
        try:
            result = await _daemon("cv_get_frame", timeout=30.0)
            log.debug("✅ _daemon returned successfully")
        except asyncio.TimeoutError as e:
            log.error(f"⏱️ IPC timeout after 30s waiting for cv_get_frame: {e}")
            return web.Response(status=504, text="Gateway timeout - daemon took too long to respond (>30s). Camera may be initializing.")
        if "error" in result:
            return web.Response(status=500, text=result["error"])

        metadata = result.get("metadata") or {}
        if not manual:
            if not metadata.get("region_detected"):
                return web.Response(status=404, text="No active map configuration. Provide x,y,w,h to preview manually.")
            x = int(metadata.get("region_x", 0))
            y = int(metadata.get("region_y", 0))
            w = int(metadata.get("region_width", 0))
            h = int(metadata.get("region_height", 0))

        import base64, hashlib, cv2, numpy as np

        frame_b64 = result.get("frame")
        if not frame_b64:
            return web.Response(status=500, text="No frame data")
        img_bytes = base64.b64decode(frame_b64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if frame is None:
            return web.Response(status=500, text="Failed to decode frame")

        # Bounds validation
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
            return web.Response(status=400, text="Crop out of bounds")

        minimap_frame = frame[y:y+h, x:x+w]
        if minimap_frame.size == 0:
            return web.Response(status=500, text="Failed to extract minimap region")

        success, png_bytes = cv2.imencode('.png', minimap_frame)
        if not success:
            return web.Response(status=500, text="PNG encoding failed")

        data_bytes = png_bytes.tobytes()
        checksum = hashlib.md5(data_bytes).hexdigest()
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Minimap-X": str(x),
            "X-Minimap-Y": str(y),
            "X-Minimap-Width": str(w),
            "X-Minimap-Height": str(h),
            "X-Minimap-Manual": str(manual).lower(),
            "X-Minimap-Checksum": checksum,
        }
        return web.Response(body=data_bytes, content_type="image/png", headers=headers)
    except Exception as e:
        log.error(f"Failed to serve lossless frame: {e}", exc_info=True)
        return web.Response(status=500, text=str(e))


async def api_cv_raw_minimap(request: web.Request):
    """
    Serve truly lossless raw minimap (captured before JPEG compression).

    This endpoint returns the raw BGR minimap crop that was extracted BEFORE
    JPEG encoding in the capture loop, eliminating all compression artifacts.
    Perfect for calibration where color accuracy is critical.

    Unlike /api/cv/frame-lossless which decodes a JPEG and re-encodes as PNG,
    this endpoint serves the raw minimap pixels that never went through JPEG
    compression.

    Returns:
        PNG image of the raw minimap region (no JPEG artifacts)
        Headers include region coordinates and checksum

    Status Codes:
        200: Success
        404: No active map config or raw minimap not available
        500: Server error
    """
    try:
        # Get raw minimap via IPC (use 30s timeout for CV operations)
        result = await _daemon("cv_get_raw_minimap", timeout=30.0)

        if not result.get("success", True):
            error_code = result.get("error", "unknown")
            status_code = 404 if error_code == "no_minimap" else 503
            return _json(
                {
                    "error": error_code,
                    "message": result.get("message", "Unable to load raw minimap."),
                    "details": result.get("details"),
                },
                status=status_code,
            )

        # Extract PNG data
        minimap_b64 = result.get("minimap")
        if not minimap_b64:
            return _json(
                {
                    "error": "no_minimap",
                    "message": "No raw minimap available (missing data).",
                },
                status=404,
            )

        metadata = result.get("metadata", {})

        import base64, hashlib
        png_bytes = base64.b64decode(minimap_b64)
        checksum = hashlib.md5(png_bytes).hexdigest()

        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Minimap-X": str(metadata.get("region_x", 0)),
            "X-Minimap-Y": str(metadata.get("region_y", 0)),
            "X-Minimap-Width": str(metadata.get("region_width", 0)),
            "X-Minimap-Height": str(metadata.get("region_height", 0)),
            "X-Minimap-Checksum": checksum,
            "X-Minimap-Source": "raw",  # Indicates this is pre-JPEG data
        }

        log.debug(f"Serving raw minimap: {metadata.get('region_width')}x{metadata.get('region_height')}, {len(png_bytes)} bytes")
        return web.Response(body=png_bytes, content_type="image/png", headers=headers)

    except Exception as e:
        log.error(f"Failed to serve raw minimap: {e}", exc_info=True)
        return web.Response(status=500, text=str(e))


async def api_cv_detection_preview(request: web.Request):
    """
    Serve minimap with detection overlays (player, other players, masks).

    This endpoint returns a PNG image with visual overlays showing:
    - Player position (yellow crosshair + circle)
    - Other players positions (red circles + crosshairs)
    - Detection confidence
    - Frame count

    Perfect for debugging detection accuracy in the web UI.

    ARCHITECTURE NOTE: This handler uses ONLY IPC to communicate with the daemon process
    where the detector actually runs. It does NOT directly access any capture instance,
    avoiding the process boundary issue where web server and daemon are separate processes.

    Returns:
        PNG image with detection visualization overlays

    Status Codes:
        200: Success
        404: No active detection or minimap not available
        500: Server error
    """
    log.debug("🖼️ Detection preview requested")
    try:
        # Get detection preview via IPC (runs entirely in daemon process, use 30s timeout)
        result = await _daemon("cv_get_detection_preview", timeout=30.0)

        # Handle errors
        if not result.get("success"):
            error_code = result.get("error", "unknown")
            error_msg = result.get("message", "Detection preview failed")

            log.debug(f"Detection preview failed: {error_code} - {error_msg}")

            # Map error codes to appropriate HTTP status codes
            if error_code == "detection_not_enabled":
                return web.Response(status=404, text=error_msg)
            elif error_code == "no_minimap":
                return web.Response(status=404, text=error_msg)
            elif error_code == "no_result":
                return web.Response(status=404, text=error_msg)
            elif error_code == "detector_null":
                return web.Response(status=500, text=error_msg)
            elif error_code in ("visualization_failed", "encode_failed", "encode_exception"):
                return web.Response(status=500, text=error_msg)
            else:
                return web.Response(status=500, text=f"Unknown error: {error_code}")

        # Success - decode PNG and return
        import base64
        preview_b64 = result.get("preview")
        if not preview_b64:
            log.error("Success response but no preview data")
            return web.Response(status=500, text="No preview data in response")

        png_bytes = base64.b64decode(preview_b64)
        log.debug(f"✓ Serving detection preview | size={len(png_bytes)} bytes")

        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
        }

        return web.Response(body=png_bytes, content_type="image/png", headers=headers)

    except Exception as e:
        log.error(f"Failed to serve detection preview: {e}", exc_info=True)
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


# ========== Departure Points Handlers ==========

async def api_departure_points_add(request: web.Request):
    """
    Add a departure point to a map configuration.

    URL parameter:
        map_name: Name of the map config

    Request body:
        {
            "x": int,  # X coordinate (required)
            "y": int,  # Y coordinate (required)
            "name": str,  # Optional name (auto-generated if not provided)
            "tolerance_mode": str,  # Optional (default: "both")
            "tolerance_value": int  # Optional (default: 5)
        }

    Returns:
        Created departure point object
    """
    try:
        from msmacro.cv.map_config import get_manager

        map_name = request.match_info.get("map_name")
        if not map_name:
            return _json({"error": "Map config name required"}, 400)

        data = await request.json()

        # Validate required fields
        if "x" not in data or "y" not in data:
            return _json({"error": "x and y coordinates are required"}, 400)

        manager = get_manager()
        config = manager.get_config(map_name)

        if not config:
            return _json({"error": f"Map config '{map_name}' not found"}, 404)

        # Add departure point
        point = config.add_departure_point(
            x=int(data["x"]),
            y=int(data["y"]),
            name=data.get("name"),
            tolerance_mode=data.get("tolerance_mode", "both"),
            tolerance_value=int(data.get("tolerance_value", 5))
        )

        # Save config
        manager.save_config(config)

        return _json({
            "success": True,
            "point": point.to_dict()
        })

    except ValueError as e:
        return _json({"error": str(e)}, 400)
    except Exception as e:
        log.error(f"Failed to add departure point: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_departure_points_remove(request: web.Request):
    """
    Remove a departure point from a map configuration.

    URL parameters:
        map_name: Name of the map config
        point_id: ID of the departure point to remove

    Returns:
        Success status
    """
    try:
        from msmacro.cv.map_config import get_manager

        map_name = request.match_info.get("map_name")
        point_id = request.match_info.get("point_id")

        if not map_name or not point_id:
            return _json({"error": "Map name and point ID required"}, 400)

        manager = get_manager()
        config = manager.get_config(map_name)

        if not config:
            return _json({"error": f"Map config '{map_name}' not found"}, 404)

        # Remove departure point
        removed = config.remove_departure_point(point_id)

        if not removed:
            return _json({"error": "Departure point not found"}, 404)

        # Save config
        manager.save_config(config)

        return _json({"success": True})

    except Exception as e:
        log.error(f"Failed to remove departure point: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_departure_points_update(request: web.Request):
    """
    Update a departure point's properties.

    URL parameters:
        map_name: Name of the map config
        point_id: ID of the departure point to update

    Request body:
        {
            "name": str,  # Optional
            "tolerance_mode": str,  # Optional
            "tolerance_value": int  # Optional
        }

    Returns:
        Updated departure point object
    """
    try:
        from msmacro.cv.map_config import get_manager

        map_name = request.match_info.get("map_name")
        point_id = request.match_info.get("point_id")

        if not map_name or not point_id:
            return _json({"error": "Map name and point ID required"}, 400)

        data = await request.json()

        manager = get_manager()
        config = manager.get_config(map_name)

        if not config:
            return _json({"error": f"Map config '{map_name}' not found"}, 404)

        # Update departure point
        updated = config.update_departure_point(point_id, **data)

        if not updated:
            return _json({"error": "Departure point not found"}, 404)

        # Save config
        manager.save_config(config)

        # Get updated point
        point = config.get_departure_point(point_id)

        return _json({
            "success": True,
            "point": point.to_dict()
        })

    except ValueError as e:
        return _json({"error": str(e)}, 400)
    except Exception as e:
        log.error(f"Failed to update departure point: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_departure_points_reorder(request: web.Request):
    """
    Reorder departure points in a map configuration.

    URL parameter:
        map_name: Name of the map config

    Request body:
        {
            "ordered_ids": [str, ...]  # List of point IDs in desired order
        }

    Returns:
        Success status with updated points list
    """
    try:
        from msmacro.cv.map_config import get_manager

        map_name = request.match_info.get("map_name")
        if not map_name:
            return _json({"error": "Map config name required"}, 400)

        data = await request.json()
        ordered_ids = data.get("ordered_ids", [])

        if not ordered_ids:
            return _json({"error": "ordered_ids list required"}, 400)

        manager = get_manager()
        config = manager.get_config(map_name)

        if not config:
            return _json({"error": f"Map config '{map_name}' not found"}, 404)

        # Reorder points
        success = config.reorder_departure_points(ordered_ids)

        if not success:
            return _json({"error": "Failed to reorder points (IDs don't match)"}, 400)

        # Save config
        manager.save_config(config)

        return _json({
            "success": True,
            "points": [point.to_dict() for point in config.departure_points]
        })

    except Exception as e:
        log.error(f"Failed to reorder departure points: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_departure_points_status(request: web.Request):
    """
    Get current hit_departure status for all departure points.

    Returns:
        {
            "player_detected": bool,
            "player_position": {"x": int, "y": int} | null,
            "active_map": str | null,
            "points": [
                {
                    "id": str,
                    "name": str,
                    "x": int,
                    "y": int,
                    "order": int,
                    "tolerance_mode": str,
                    "tolerance_value": int,
                    "hit_departure": bool
                },
                ...
            ]
        }
    """
    try:
        from msmacro.cv.map_config import get_manager

        # Get active map config
        manager = get_manager()
        config = manager.get_active_config()

        if not config:
            return _json({
                "player_detected": False,
                "player_position": None,
                "active_map": None,
                "points": []
            })

        # Get current player position from daemon
        try:
            detection_result = await _daemon("object_detection_status")
            last_result = detection_result.get("last_result") or {}
            player_data = last_result.get("player") or {}
            player_detected = player_data.get("detected", False)
            current_x = player_data.get("x", 0)
            current_y = player_data.get("y", 0)
        except Exception as e:
            log.warning(f"Failed to get player position: {e}")
            player_detected = False
            current_x = 0
            current_y = 0

        # Check hit_departure for all points
        points_status = []
        for point in config.departure_points:
            point_dict = point.to_dict()
            point_dict["hit_departure"] = point.check_hit(current_x, current_y) if player_detected else False
            points_status.append(point_dict)

        return _json({
            "player_detected": player_detected,
            "player_position": {"x": current_x, "y": current_y} if player_detected else None,
            "active_map": config.name,
            "points": points_status
        })

    except Exception as e:
        log.error(f"Failed to get departure points status: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


# ---------- CV-AUTO Mode Handlers ----------

async def api_cv_auto_start(request: web.Request):
    """
    Start CV-AUTO mode for automatic rotation playback.

    Body (JSON):
    {
        "loop": 1,                 # Loop count (repeat entire sequence N times)
        "speed": 1.0,              # Rotation playback speed
        "jitter_time": 0.05,       # Time jitter for human-like playback
        "jitter_hold": 0.02,       # Hold duration jitter
        "jump_key": "SPACE",       # Jump key alias (default: "SPACE")
        "ignore_keys": [],         # List of keys to randomly ignore (e.g., ["s", "w"])
        "ignore_tolerance": 0.0    # Probability (0.0-1.0) to ignore each key
    }
    """
    log.info("=" * 60)
    log.info("🎮 Backend: CV-AUTO start request received")

    try:
        body = await request.json()
    except Exception:
        body = {}

    log.info(f"Request params: {body}")

    try:
        log.info("Sending IPC command 'cv_auto_start' to daemon...")
        resp = await _daemon("cv_auto_start", **body)
        log.info(f"✅ Daemon response: {resp}")
        log.info("=" * 60)
        return _json(resp)
    except Exception as e:
        log.error(f"❌ Failed to start CV-AUTO mode: {e}", exc_info=True)
        log.error("=" * 60)
        return _json({"error": str(e)}, 500)


async def api_cv_auto_stop(request: web.Request):
    """Stop CV-AUTO mode."""
    try:
        resp = await _daemon("cv_auto_stop")
        return _json(resp)
    except Exception as e:
        log.error(f"Failed to stop CV-AUTO mode: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_cv_auto_status(request: web.Request):
    """
    Get CV-AUTO mode status.

    Returns:
    {
        "enabled": bool,
        "current_point_index": int,
        "current_point_name": str,
        "total_points": int,
        "last_rotation_played": str,
        "rotations_played_count": int,
        "cycles_completed": int,
        "player_position": {"x": int, "y": int}
    }
    """
    try:
        resp = await _daemon("cv_auto_status")
        return _json(resp)
    except Exception as e:
        log.error(f"Failed to get CV-AUTO status: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_link_rotations_to_point(request: web.Request):
    """
    Link rotation files to a departure point.

    Path params:
    - map_name: Map configuration name
    - point_id: Departure point ID

    Body (JSON):
    {
        "rotation_paths": ["rotation1.json", "rotation2.json"],
        "rotation_mode": "random",       # Optional: "random", "sequential", "single"
        "is_teleport_point": false,      # Optional: Enable port flow
        "auto_play": true                # Optional: Enable auto-trigger
    }
    """
    map_name = request.match_info.get("map_name")
    point_id = request.match_info.get("point_id")

    try:
        body = await request.json()
    except Exception:
        body = {}

    try:
        resp = await _daemon(
            "link_rotations_to_point",
            map_name=map_name,
            point_id=point_id,
            **body
        )
        return _json(resp)
    except Exception as e:
        log.error(f"Failed to link rotations: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


# ========== CV Item Endpoints ==========

async def api_cv_items_list(request: web.Request):
    """
    GET /api/cv-items - List all CV Items

    Returns:
    {
        "items": [CVItem, ...],
        "active_item": str | null
    }
    """
    try:
        from ..cv.cv_item import get_cv_item_manager
        manager = get_cv_item_manager()
        items = manager.list_items()
        active = manager.get_active_item()

        return _json({
            "items": [item.to_dict() for item in items],
            "active_item": active.name if active else None
        })
    except Exception as e:
        log.error(f"Failed to list CV Items: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_cv_items_create(request: web.Request):
    """
    POST /api/cv-items - Create new CV Item

    Body (JSON):
    {
        "name": str,
        "map_config_name": str | null,
        "pathfinding_rotations": {
            "near": List[str],
            "medium": List[str],
            "far": List[str],
            "very_far": List[str]
        },
        "pathfinding_config": {
            "class_type": "other" | "magician",
            "rope_lift_key": str,
            "diagonal_movement_key": str (other class only),
            "double_jump_up_allowed": bool (other class only),
            "y_axis_jump_skill": str (other class only),
            "teleport_skill": str (magician class only)
        } (optional),
        "departure_points": List[DeparturePoint],
        "description": str (optional),
        "tags": List[str] (optional)
    }
    """
    try:
        from ..cv.cv_item import get_cv_item_manager, CVItem
        from ..cv.map_config import DeparturePoint

        # Parse JSON with error handling
        try:
            data = await request.json()
        except Exception:
            log.warning("Invalid JSON in CV Item create request")
            return _json({"error": "Invalid JSON in request body"}, 400)

        # Validate request body is not empty
        if not data:
            log.warning("Empty request body in CV Item create")
            return _json({"error": "Request body cannot be empty"}, 400)

        # Validate required field: name
        name = data.get('name')
        if not name:
            log.warning("CV Item create request missing 'name' field")
            return _json({"error": "Field 'name' is required"}, 400)

        name = name.strip()
        if not name:
            log.warning("CV Item create request has empty 'name' field")
            return _json({"error": "Field 'name' cannot be empty"}, 400)

        # Validate required field: map_config_name
        map_config_name = data.get('map_config_name')
        if not map_config_name:
            log.warning(f"CV Item '{name}' create request missing 'map_config_name'")
            return _json({"error": "Field 'map_config_name' is required. A CV Item must reference a map configuration."}, 400)

        # Validate pathfinding_rotations structure
        pathfinding_rotations = data.get('pathfinding_rotations', {
            'near': [], 'medium': [], 'far': [], 'very_far': []
        })
        if not isinstance(pathfinding_rotations, dict):
            log.warning(f"CV Item '{name}' has invalid pathfinding_rotations type")
            return _json({"error": "Field 'pathfinding_rotations' must be an object"}, 400)

        required_rotation_keys = {'near', 'medium', 'far', 'very_far'}
        if not all(k in pathfinding_rotations for k in required_rotation_keys):
            log.warning(f"CV Item '{name}' pathfinding_rotations missing required keys")
            return _json({"error": "Field 'pathfinding_rotations' must have keys: near, medium, far, very_far"}, 400)

        for key in required_rotation_keys:
            if not isinstance(pathfinding_rotations[key], list):
                log.warning(f"CV Item '{name}' pathfinding_rotations['{key}'] is not a list")
                return _json({"error": f"Field 'pathfinding_rotations.{key}' must be a list"}, 400)

        # Validate pathfinding_config structure
        pathfinding_config = data.get('pathfinding_config', {})
        if not isinstance(pathfinding_config, dict):
            log.warning(f"CV Item '{name}' has invalid pathfinding_config type")
            return _json({"error": "Field 'pathfinding_config' must be an object"}, 400)

        class_type = pathfinding_config.get('class_type', 'other')
        if class_type not in ('other', 'magician'):
            log.warning(f"CV Item '{name}' has invalid class_type: {class_type}")
            return _json({"error": "Field 'pathfinding_config.class_type' must be 'other' or 'magician'"}, 400)

        # Validate departure_points structure
        points_data = data.get('departure_points', [])
        if not isinstance(points_data, list):
            log.warning(f"CV Item '{name}' has invalid departure_points type")
            return _json({"error": "Field 'departure_points' must be a list"}, 400)

        # Parse departure points with validation
        departure_points = []
        for i, point_data in enumerate(points_data):
            if not isinstance(point_data, dict):
                log.warning(f"CV Item '{name}' departure_point[{i}] is not an object")
                return _json({"error": f"Departure point at index {i} must be an object"}, 400)

            # Check required fields
            required_point_fields = ['id', 'name', 'x', 'y', 'order']
            for field in required_point_fields:
                if field not in point_data:
                    log.warning(f"CV Item '{name}' departure_point[{i}] missing field '{field}'")
                    return _json({"error": f"Departure point at index {i} missing required field '{field}'"}, 400)

            try:
                departure_points.append(DeparturePoint.from_dict(point_data))
            except (TypeError, KeyError, ValueError) as e:
                log.warning(f"CV Item '{name}' departure_point[{i}] construction failed: {e}")
                return _json({"error": f"Invalid departure point at index {i}: {str(e)}"}, 400)

        # Create CV Item
        try:
            item = CVItem(
                name=name,
                map_config_name=map_config_name,
                pathfinding_rotations=pathfinding_rotations,
                pathfinding_config=pathfinding_config,
                departure_points=departure_points,
                created_at=time.time(),
                description=data.get('description', ''),
                tags=data.get('tags', [])
            )
        except (TypeError, ValueError) as e:
            log.warning(f"CV Item '{name}' construction failed: {e}")
            return _json({"error": f"Invalid CV Item data: {str(e)}"}, 400)

        # Validate
        is_valid, error_msg = item.validate()
        if not is_valid:
            log.warning(f"CV Item '{name}' validation failed: {error_msg}")
            return _json({"error": error_msg}, 400)

        # Save
        manager = get_cv_item_manager()
        try:
            manager.create_item(item)
            log.info(f"✓ Created CV Item: {name}")
        except ValueError as e:
            # Item already exists or validation error
            log.warning(f"CV Item '{name}' creation failed: {e}")
            return _json({"error": str(e)}, 400)

        return _json({"ok": True, "item": item.to_dict()})

    except Exception as e:
        log.error(f"Failed to create CV Item: {e}", exc_info=True)
        return _json({"error": "Internal server error"}, 500)


async def api_cv_items_get(request: web.Request):
    """
    GET /api/cv-items/{name} - Get specific CV Item
    """
    # Validate URL parameter
    name = request.match_info.get('name')
    if not name:
        log.warning("CV Item get request missing URL parameter 'name'")
        return _json({"error": "URL parameter 'name' is required"}, 400)

    try:
        from ..cv.cv_item import get_cv_item_manager
        manager = get_cv_item_manager()
        item = manager.get_item(name)

        if not item:
            log.info(f"CV Item not found: {name}")
            return _json({"error": "CV Item not found"}, 404)

        return _json(item.to_dict())
    except Exception as e:
        log.error(f"Failed to get CV Item '{name}': {e}", exc_info=True)
        return _json({"error": "Internal server error"}, 500)


async def api_cv_items_update(request: web.Request):
    """
    PUT /api/cv-items/{name} - Update CV Item

    Body (JSON): Complete CVItem object
    """
    # Validate URL parameter
    name = request.match_info.get('name')
    if not name:
        log.warning("CV Item update request missing URL parameter 'name'")
        return _json({"error": "URL parameter 'name' is required"}, 400)

    try:
        from ..cv.cv_item import get_cv_item_manager, CVItem
        from ..cv.map_config import DeparturePoint

        # Parse JSON with error handling
        try:
            data = await request.json()
        except Exception:
            log.warning(f"Invalid JSON in CV Item update request for '{name}'")
            return _json({"error": "Invalid JSON in request body"}, 400)

        # Validate request body is not empty
        if not data:
            log.warning(f"Empty request body in CV Item update for '{name}'")
            return _json({"error": "Request body cannot be empty"}, 400)

        # Validate required field: name
        new_name = data.get('name')
        if not new_name:
            log.warning(f"CV Item update request for '{name}' missing 'name' field")
            return _json({"error": "Field 'name' is required"}, 400)

        new_name = new_name.strip()
        if not new_name:
            log.warning(f"CV Item update request for '{name}' has empty 'name' field")
            return _json({"error": "Field 'name' cannot be empty"}, 400)

        # Validate required field: map_config_name
        map_config_name = data.get('map_config_name')
        if not map_config_name:
            log.warning(f"CV Item '{name}' update request missing 'map_config_name'")
            return _json({"error": "Field 'map_config_name' is required. A CV Item must reference a map configuration."}, 400)

        # Validate pathfinding_rotations structure
        pathfinding_rotations = data.get('pathfinding_rotations', {
            'near': [], 'medium': [], 'far': [], 'very_far': []
        })
        if not isinstance(pathfinding_rotations, dict):
            log.warning(f"CV Item '{name}' update has invalid pathfinding_rotations type")
            return _json({"error": "Field 'pathfinding_rotations' must be an object"}, 400)

        required_rotation_keys = {'near', 'medium', 'far', 'very_far'}
        if not all(k in pathfinding_rotations for k in required_rotation_keys):
            log.warning(f"CV Item '{name}' update pathfinding_rotations missing required keys")
            return _json({"error": "Field 'pathfinding_rotations' must have keys: near, medium, far, very_far"}, 400)

        for key in required_rotation_keys:
            if not isinstance(pathfinding_rotations[key], list):
                log.warning(f"CV Item '{name}' update pathfinding_rotations['{key}'] is not a list")
                return _json({"error": f"Field 'pathfinding_rotations.{key}' must be a list"}, 400)

        # Validate pathfinding_config structure
        pathfinding_config = data.get('pathfinding_config', {})
        if not isinstance(pathfinding_config, dict):
            log.warning(f"CV Item '{name}' update has invalid pathfinding_config type")
            return _json({"error": "Field 'pathfinding_config' must be an object"}, 400)

        class_type = pathfinding_config.get('class_type', 'other')
        if class_type not in ('other', 'magician'):
            log.warning(f"CV Item '{name}' update has invalid class_type: {class_type}")
            return _json({"error": "Field 'pathfinding_config.class_type' must be 'other' or 'magician'"}, 400)

        # Validate departure_points structure
        points_data = data.get('departure_points', [])
        if not isinstance(points_data, list):
            log.warning(f"CV Item '{name}' update has invalid departure_points type")
            return _json({"error": "Field 'departure_points' must be a list"}, 400)

        # Parse departure points with validation
        departure_points = []
        for i, point_data in enumerate(points_data):
            if not isinstance(point_data, dict):
                log.warning(f"CV Item '{name}' update departure_point[{i}] is not an object")
                return _json({"error": f"Departure point at index {i} must be an object"}, 400)

            # Check required fields
            required_point_fields = ['id', 'name', 'x', 'y', 'order']
            for field in required_point_fields:
                if field not in point_data:
                    log.warning(f"CV Item '{name}' update departure_point[{i}] missing field '{field}'")
                    return _json({"error": f"Departure point at index {i} missing required field '{field}'"}, 400)

            try:
                departure_points.append(DeparturePoint.from_dict(point_data))
            except (TypeError, KeyError, ValueError) as e:
                log.warning(f"CV Item '{name}' update departure_point[{i}] construction failed: {e}")
                return _json({"error": f"Invalid departure point at index {i}: {str(e)}"}, 400)

        # Create updated item
        try:
            updated_item = CVItem(
                name=new_name,
                map_config_name=map_config_name,
                pathfinding_rotations=pathfinding_rotations,
                pathfinding_config=pathfinding_config,
                departure_points=departure_points,
                created_at=data.get('created_at', time.time()),
                last_used_at=data.get('last_used_at', 0.0),
                is_active=data.get('is_active', False),
                description=data.get('description', ''),
                tags=data.get('tags', [])
            )
        except (TypeError, ValueError) as e:
            log.warning(f"CV Item '{name}' update construction failed: {e}")
            return _json({"error": f"Invalid CV Item data: {str(e)}"}, 400)

        # Validate
        is_valid, error_msg = updated_item.validate()
        if not is_valid:
            log.warning(f"CV Item '{name}' update validation failed: {error_msg}")
            return _json({"error": error_msg}, 400)

        # Update
        manager = get_cv_item_manager()
        try:
            manager.update_item(name, updated_item)
            log.info(f"✓ Updated CV Item: {name} → {new_name}")
        except ValueError as e:
            # Item not found, name conflict, or validation error
            log.warning(f"CV Item '{name}' update failed: {e}")
            return _json({"error": str(e)}, 400)

        return _json({"ok": True})

    except Exception as e:
        log.error(f"Failed to update CV Item '{name}': {e}", exc_info=True)
        return _json({"error": "Internal server error"}, 500)


async def api_cv_items_delete(request: web.Request):
    """
    DELETE /api/cv-items/{name} - Delete CV Item
    """
    # Validate URL parameter
    name = request.match_info.get('name')
    if not name:
        log.warning("CV Item delete request missing URL parameter 'name'")
        return _json({"error": "URL parameter 'name' is required"}, 400)

    try:
        from ..cv.cv_item import get_cv_item_manager
        manager = get_cv_item_manager()

        try:
            success = manager.delete_item(name)
        except ValueError as e:
            # Handle "Cannot delete active CV Item" error
            log.warning(f"CV Item '{name}' deletion blocked: {e}")
            return _json({"error": str(e)}, 400)

        if not success:
            log.info(f"CV Item not found for deletion: {name}")
            return _json({"error": "CV Item not found"}, 404)

        log.info(f"✓ Deleted CV Item: {name}")
        return _json({"ok": True})

    except Exception as e:
        log.error(f"Failed to delete CV Item '{name}': {e}", exc_info=True)
        return _json({"error": "Internal server error"}, 500)


async def api_cv_items_activate(request: web.Request):
    """
    POST /api/cv-items/{name}/activate - Activate CV Item

    This will:
    1. Deactivate current CV Item
    2. Activate the CV Item's map config
    3. Load departure points
    4. Mark CV Item as active
    """
    # DIAGNOSTIC: Confirm function is being called
    log.info("=" * 70)
    log.info("🔍 API_CV_ITEMS_ACTIVATE CALLED")
    log.info("=" * 70)

    # Validate URL parameter
    name = request.match_info.get('name')
    if not name:
        log.warning("CV Item activate request missing URL parameter 'name'")
        return _json({"error": "URL parameter 'name' is required"}, 400)

    try:
        from ..cv.cv_item import get_cv_item_manager
        manager = get_cv_item_manager()

        # Check if item exists first
        item_check = manager.get_item(name)
        if not item_check:
            log.warning(f"CV Item not found for activation: {name}")
            return _json({"error": "CV Item not found"}, 404)

        # Check if map config is assigned
        if not item_check.map_config_name:
            log.warning(f"CV Item '{name}' has no map config assigned")
            return _json({"error": "CV Item has no map config assigned. Please edit the item and select a map configuration."}, 400)

        # DIAGNOSTIC: About to activate item
        log.info(f"🔍 CHECKPOINT: About to activate item '{name}'")

        # Attempt activation
        try:
            item = manager.activate_item(name)
        except ValueError as e:
            # Map config not found or other validation error
            log.warning(f"CV Item '{name}' activation failed: {e}")
            return _json({"error": str(e)}, 400)

        if not item:
            # This shouldn't happen given the checks above, but handle it
            log.error(f"CV Item '{name}' activation returned None unexpectedly")
            return _json({"error": "Failed to activate CV Item. Map configuration may not exist."}, 400)

        log.info(f"✓ Activated CV Item: {name}")

        # Reload config in daemon/capture to sync changes
        log.info(f"🔄 RELOAD STARTING for CV Item '{name}'")
        log.info(f"   Checking CV capture status...")

        try:
            # Check if CV is running first
            import asyncio
            cv_status = await _daemon("cv_status", timeout=5.0)
            log.info(f"   CV status: capturing={cv_status.get('capturing', False)}")

            if not cv_status.get("capturing"):
                log.warning("   ⚠️  CV not capturing yet - config will load on first frame")
            else:
                log.info("   CV is capturing - proceeding with reload...")
                log.info("   Calling cv_reload_config IPC...")

                reload_result = await _daemon("cv_reload_config", timeout=10.0)

                if reload_result.get("reloaded"):
                    active_name = reload_result.get('active_config', {}).get('name', 'unknown')
                    log.info(f"   ✅ Config reloaded successfully: {active_name}")
                else:
                    log.error(f"   ❌ Reload failed: {reload_result}")

        except asyncio.TimeoutError:
            log.error("   ❌ RELOAD TIMEOUT: cv_reload_config took >10s", exc_info=True)
        except Exception as reload_err:
            log.error(f"   ❌ RELOAD EXCEPTION: {reload_err}", exc_info=True)

        # Auto-start CV system (capture + object detection)
        try:
            log.info("Ensuring CV capture is running...")

            # Step 1: Check if CV capture is running
            cv_status = await _daemon("cv_status", timeout=5.0)

            if not cv_status.get("capturing", False):
                log.info("CV not capturing, starting CV capture...")
                await _daemon("cv_start", device_index=0, timeout=10.0)

                # Wait for first frame
                import asyncio
                await asyncio.sleep(0.5)
                log.info("✓ CV capture started")
            else:
                log.info("✓ CV already capturing")

            # Step 2: Start object detection
            log.info("Starting object detection...")
            await _daemon("object_detection_start", timeout=10.0)
            log.info(f"✓ Object detection started for CV Item '{name}'")

        except Exception as init_err:
            log.error(f"Failed to initialize CV system: {init_err}", exc_info=True)
            # Don't fail activation, but warn user
            log.warning(f"CV Item '{name}' is activated, but CV system may not be ready")

        return _json({
            "ok": True,
            "item": item.to_dict(),
            "map_config_activated": True
        })

    except Exception as e:
        log.error(f"Failed to activate CV Item '{name}': {e}", exc_info=True)
        return _json({"error": "Internal server error"}, 500)


async def api_cv_items_get_active(request: web.Request):
    """
    GET /api/cv-items/active - Get active CV Item

    Returns:
        CVItem dict if active, {"active_item": null} otherwise
    """
    try:
        from ..cv.cv_item import get_cv_item_manager
        manager = get_cv_item_manager()
        item = manager.get_active_item()

        if item:
            return _json(item.to_dict())
        else:
            return _json({"active_item": None})
    except Exception as e:
        log.error(f"Failed to get active CV Item: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)


async def api_cv_items_deactivate(request: web.Request):
    """
    POST /api/cv-items/deactivate - Deactivate current CV Item

    This will:
    1. Deactivate current CV Item
    2. Deactivate map config
    """
    try:
        from ..cv.cv_item import get_cv_item_manager
        manager = get_cv_item_manager()
        manager.deactivate()

        return _json({"ok": True})
    except Exception as e:
        log.error(f"Failed to deactivate CV Item: {e}", exc_info=True)
        return _json({"error": str(e)}, 500)
