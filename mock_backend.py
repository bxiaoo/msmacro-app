#!/usr/bin/env python3
"""
Fixed Mock backend server for MSMacro Web UI testing.
This version properly handles tree structure, file operations, and mode changes.
"""

import asyncio
import json
import time
import os
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from aiohttp import web, WSMsgType
import contextlib

# Mock data storage
class MockState:
    def __init__(self):
        self.mode = "BRIDGE"  # BRIDGE, RECORDING, PLAYING, POSTRECORD
        self.recording_start_time = None
        self.last_actions = None
        self.have_last_actions = False
        self.files = self._generate_mock_files()
        self.tree = []
        self.clients = set()  # SSE clients
        self.playback_task = None
        self.current_playing_file = None
        self.skills = {}  # Mock skills storage
        self.skill_counter = 0

        # Build initial tree
        self._rebuild_tree()

        # Initialize with some sample skills
        self._generate_mock_skills()

    def _generate_mock_files(self) -> List[Dict]:
        """Generate mock recording files."""
        base_time = int(time.time()) - 86400  # 1 day ago
        files = []

        mock_files = [
            ("test_macro.json", 1524, 3600),
            ("login_sequence.json", 892, 7200),
            ("quick_commands.json", 445, 1800),
            ("folder1/subfolder/nested_macro.json", 2048, 900),
            ("folder1/another_macro.json", 756, 5400),
            ("folder2/automation.json", 1337, 2700),
            ("folder4/subfolder/nested_macro.json", 2048, 900),
            ("folder5/another_macro.json", 756, 5400),
            ("folder6/automation.json", 1337, 2700),
            ("folder7/subfolder/nested_macro.json", 2048, 900),
            ("folder7/another_macro.json", 756, 5400),
            ("folder7/automation.json", 1337, 2700),
        ]

        for rel_path, size, offset in mock_files:
            files.append({
                "name": Path(rel_path).name,
                "rel": rel_path,  # Add the rel key
                "path": f"/mock/records/{rel_path}",
                "size": size,
                "mtime": base_time + offset
            })

        return files

    def _generate_mock_skills(self):
        """Generate some sample skills for testing."""
        import uuid
        sample_skills = [
            {
                "id": str(uuid.uuid4()),
                "name": "Fireball",
                "keystroke": "f",
                "cooldown": 15.0,
                "after_key_constraints": False,
                "key1": "",
                "key2": "",
                "key3": "",
                "after_keys_seconds": 0.45,
                "frozen_rotation_during_casting": False,
                "is_selected": True
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Ice Blast",
                "keystroke": "i",
                "cooldown": 20.0,
                "after_key_constraints": True,
                "key1": "shift",
                "key2": "ctrl",
                "key3": "",
                "after_keys_seconds": 0.6,
                "frozen_rotation_during_casting": True,
                "is_selected": False
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Lightning Strike",
                "keystroke": "1",
                "cooldown": 8.0,
                "after_key_constraints": False,
                "key1": "",
                "key2": "",
                "key3": "",
                "after_keys_seconds": 0.3,
                "frozen_rotation_during_casting": False,
                "is_selected": True
            }
        ]

        for skill in sample_skills:
            self.skills[skill["id"]] = skill

    def _rebuild_tree(self):
        """Rebuild tree structure from files list."""
        # The real daemon returns a FLAT list from list_recordings_recursive()
        # Each item: { name: 'folder/sub/file' (no .json), path, size, mtime, meta? }
        # The frontend (FileBrowser → buildTree) builds the nested tree from this flat list.
        items = []
        for f in self.files:
            rel = str(f.get("rel", "")).lstrip("/")
            # strip a single .json suffix for the logical name
            name_no_ext = rel[:-5] if rel.lower().endswith(".json") else rel
            items.append({
                "name": name_no_ext,
                "path": f.get("path") or f"/mock/records/{rel}",
                "size": int(f.get("size", 0)),
                "mtime": int(f.get("mtime", 0)),
            })

        # Sort like recorder.list_recordings_recursive: by name
        items.sort(key=lambda x: x.get("name", ""))
        self.tree = items

    def add_file(self, file_data: Dict):
        """Add a new file and rebuild tree."""
        self.files.append(file_data)
        self._rebuild_tree()

    def remove_file(self, rel: str):
        """Remove a file and rebuild tree."""
        self.files = [f for f in self.files if f["rel"] != rel]
        self._rebuild_tree()

    def rename_file(self, old_rel: str, new_rel: str):
        """Rename a file and rebuild tree."""
        for f in self.files:
            if f["rel"] == old_rel:
                f["rel"] = new_rel
                f["name"] = Path(new_rel).name
                f["path"] = f"/mock/records/{new_rel}"
                break
        self._rebuild_tree()

# Global state
mock_state = MockState()

def json_response(data: Any, status: int = 200) -> web.Response:
    """Helper for JSON responses."""
    return web.json_response(data, status=status)

async def broadcast_event(event_type: str, data: Dict[str, Any]):
    """Broadcast event to all SSE clients."""
    if not mock_state.clients:
        return

    event_data = {"type": event_type, **data}
    message = f"data: {json.dumps(event_data, separators=(',', ':'))}\n\n"

    dead_clients = set()
    for response in mock_state.clients:
        try:
            await response.write(message.encode())
        except Exception:
            dead_clients.add(response)

    # Clean up dead clients
    mock_state.clients -= dead_clients

# API Handlers
async def api_ping(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return json_response({"ok": True})

async def api_status(request: web.Request) -> web.Response:
    """Get current daemon status and file tree."""
    status_data = {
        "mode": mock_state.mode,
        "record_dir": "/mock/records",
        "socket": "/mock/msmacro.sock",
        "keyboard": "/dev/input/event0",
        "have_last_actions": mock_state.have_last_actions,
        "files": mock_state.files,
        "tree": mock_state.tree,
        "current_playing_file": mock_state.current_playing_file
    }
    return json_response(status_data)

async def api_list_files(request: web.Request) -> web.Response:
    """List all recording files."""
    return json_response({"files": mock_state.files})

async def api_record_start(request: web.Request) -> web.Response:
    """Start recording keystrokes."""
    if mock_state.mode not in ("BRIDGE", "POSTRECORD"):
        return json_response({"error": f"Cannot start recording from mode {mock_state.mode}"}, 400)

    mock_state.mode = "RECORDING"
    mock_state.recording_start_time = time.time()
    mock_state.have_last_actions = False

    # Broadcast mode change
    await broadcast_event("mode", {"mode": mock_state.mode})

    return json_response({"recording": True, "mode": mock_state.mode})

async def api_record_stop(request: web.Request) -> web.Response:
    """Stop recording with optional save/discard action."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    action = (body.get("action") or "").lower()
    name = body.get("name")

    if mock_state.mode == "RECORDING":
        mock_state.mode = "POSTRECORD"
        mock_state.have_last_actions = True
        mock_state.last_actions = [
            {"usage": 4, "press": 0.0, "dur": 0.1},  # 'a' key
            {"usage": 5, "press": 0.15, "dur": 0.08}, # 'b' key
        ]

    response_data = {"ok": True, "stopped": True}

    if action == "save" and name:
        # Simulate saving
        await asyncio.sleep(0.1)

        rel_name = name if name.endswith(".json") else f"{name}.json"
        new_file = {
            "name": rel_name,
            "rel": rel_name,
            "path": f"/mock/records/{rel_name}",
            "size": random.randint(400, 2000),
            "mtime": int(time.time())
        }

        mock_state.add_file(new_file)

        response_data.update({
            "saved": True,
            "file": new_file["name"],
            "path": new_file["path"]
        })

        # Broadcast changes
        await broadcast_event("files", {"files": mock_state.files})
        await broadcast_event("tree", {"tree": mock_state.tree})

        mock_state.mode = "BRIDGE"
        mock_state.have_last_actions = False

    elif action == "discard":
        mock_state.mode = "BRIDGE"
        mock_state.have_last_actions = False
        response_data["discarded"] = True
    else:
        # Just stop, keep in POSTRECORD
        pass

    # Broadcast mode change
    await broadcast_event("mode", {"mode": mock_state.mode})

    return json_response(response_data)

async def api_post_save(request: web.Request) -> web.Response:
    """Save the last recording (POSTRECORD mode)."""
    if mock_state.mode != "POSTRECORD":
        return json_response({"error": "Not in POSTRECORD mode"}, 400)

    if not mock_state.have_last_actions:
        return json_response({"error": "No last recording"}, 400)

    try:
        body = await request.json()
        name = body.get("name")
    except Exception:
        return json_response({"error": "Invalid JSON"}, 400)

    if not name:
        return json_response({"error": "Missing name"}, 400)

    # Simulate save
    await asyncio.sleep(0.1)

    rel_name = name if name.endswith(".json") else f"{name}.json"
    new_file = {
        "name": rel_name,
        "rel": rel_name,
        "path": f"/mock/records/{rel_name}",
        "size": random.randint(400, 2000),
        "mtime": int(time.time())
    }

    mock_state.add_file(new_file)
    mock_state.mode = "BRIDGE"
    mock_state.have_last_actions = False

    # Broadcast changes
    await broadcast_event("files", {"files": mock_state.files})
    await broadcast_event("tree", {"tree": mock_state.tree})
    await broadcast_event("mode", {"mode": mock_state.mode})

    return json_response({
        "ok": True,
        "saved": True,
        "file": new_file["name"],
        "path": new_file["path"]
    })

async def api_post_preview(request: web.Request) -> web.Response:
    """Preview play the last recording once."""
    if mock_state.mode != "POSTRECORD":
        return json_response({"error": "Not in POSTRECORD mode"}, 400)

    if not mock_state.have_last_actions:
        return json_response({"error": "No last recording"}, 400)

    # Simulate brief playback
    old_mode = mock_state.mode
    mock_state.mode = "PLAYING"
    await broadcast_event("mode", {"mode": mock_state.mode})

    # Start async playback task
    async def preview_playback():
        await asyncio.sleep(1.5)  # Simulate playback duration
        mock_state.mode = old_mode
        await broadcast_event("mode", {"mode": mock_state.mode})

    asyncio.create_task(preview_playback())

    return json_response({"ok": True, "preview_played": True})

async def api_post_discard(request: web.Request) -> web.Response:
    """Discard the last recording."""
    if mock_state.mode != "POSTRECORD":
        return json_response({"error": "Not in POSTRECORD mode"}, 400)

    mock_state.mode = "BRIDGE"
    mock_state.have_last_actions = False

    await broadcast_event("mode", {"mode": mock_state.mode})

    return json_response({"ok": True, "discarded": True})

async def api_play(request: web.Request) -> web.Response:
    """Play selected files."""
    try:
        body = await request.json()
    except Exception:
        return json_response({"error": "Invalid JSON"}, 400)

    names = body.get("names", [])
    if not names:
        return json_response({"error": "No files specified"}, 400)

    speed = body.get("speed", 1.0)
    loop = body.get("loop", 1)
    active_skills = body.get("active_skills", [])

    # Log skills for testing
    if active_skills:
        print(f"🎯 Playing with {len(active_skills)} active skills:")
        for skill in active_skills:
            print(f"   - {skill.get('name', 'Unknown')} (cooldown: {skill.get('cooldown', 0)}s)")
    else:
        print("🎯 Playing without skills")

    if mock_state.mode not in ("BRIDGE", "POSTRECORD"):
        return json_response({"error": f"Cannot play from mode {mock_state.mode}"}, 400)

    # Validate files exist
    existing_rels = {f["rel"] for f in mock_state.files}
    missing = [name for name in names if name not in existing_rels]
    if missing:
        return json_response({"error": f"Files not found: {', '.join(missing)}"}, 400)

    # Cancel existing playback if any
    if mock_state.playback_task and not mock_state.playback_task.done():
        mock_state.playback_task.cancel()

    # Start playing
    old_mode = mock_state.mode
    mock_state.mode = "PLAYING"
    await broadcast_event("mode", {"mode": mock_state.mode})

    # Simulate playback in background with file progression
    async def simulate_playback():
        try:
            # Shuffle files to match daemon behavior
            shuffled_names = names.copy()
            random.shuffle(shuffled_names)
            
            file_duration = max(1.0, 2.0 / speed)  # Time per file
            
            for _ in range(loop):
                for file_name in shuffled_names:
                    if mock_state.mode != "PLAYING":
                        break
                    
                    # Set current playing file with full path for consistency
                    mock_state.current_playing_file = f"/mock/records/{file_name}"
                    await asyncio.sleep(file_duration)
                
                if mock_state.mode != "PLAYING":
                    break

            # Clear current file and reset mode when done
            mock_state.current_playing_file = None
            if mock_state.mode == "PLAYING":
                mock_state.mode = old_mode
                await broadcast_event("mode", {"mode": mock_state.mode})
        except asyncio.CancelledError:
            # Playback was cancelled
            mock_state.current_playing_file = None
            if mock_state.mode == "PLAYING":
                mock_state.mode = old_mode
                await broadcast_event("mode", {"mode": mock_state.mode})

    mock_state.playback_task = asyncio.create_task(simulate_playback())

    return json_response({
        "ok": True,
        "playing": names,
        "speed": speed,
        "loop": loop
    })

async def api_stop(request: web.Request) -> web.Response:
    """Stop playback."""
    if mock_state.mode == "PLAYING":
        # Cancel playback task
        if mock_state.playback_task and not mock_state.playback_task.done():
            mock_state.playback_task.cancel()

        # Clear current playing file
        mock_state.current_playing_file = None
        mock_state.mode = "BRIDGE"
        await broadcast_event("mode", {"mode": mock_state.mode})
        return json_response({"ok": True, "stopped": "playback"})

    elif mock_state.mode == "RECORDING":
        mock_state.mode = "POSTRECORD"
        mock_state.have_last_actions = True
        await broadcast_event("mode", {"mode": mock_state.mode})
        return json_response({"ok": True, "stopped": "recording"})

    else:
        return json_response({"ok": True, "nothing_to_stop": True, "mode": mock_state.mode})

async def api_files_rename(request: web.Request) -> web.Response:
    """Rename a recording file."""
    try:
        body = await request.json()
        old = body.get("old")
        new = body.get("new")
    except Exception:
        return json_response({"error": "Invalid JSON"}, 400)

    if not old or not new:
        return json_response({"error": "Missing old/new names"}, 400)

    # Check if file exists
    if not any(f["rel"] == old for f in mock_state.files):
        return json_response({"error": "File not found"}, 404)

    new_name = new if new.endswith(".json") else f"{new}.json"

    # Rename file
    mock_state.rename_file(old, new_name)

    # Broadcast changes
    await broadcast_event("files", {"files": mock_state.files})
    await broadcast_event("tree", {"tree": mock_state.tree})

    return json_response({
        "ok": True,
        "renamed": True,
        "old": old,
        "new": new_name
    })

async def api_files_delete(request: web.Request) -> web.Response:
    """Delete a recording file."""
    name = request.match_info.get("name")
    if not name:
        return json_response({"error": "Missing filename"}, 400)

    # Check if file exists
    deleted_file = None
    for f in mock_state.files:
        if f["rel"] == name:
            deleted_file = f
            break

    if not deleted_file:
        return json_response({"error": "File not found"}, 404)

    # Remove file
    mock_state.remove_file(name)

    # Broadcast changes
    await broadcast_event("files", {"files": mock_state.files})
    await broadcast_event("tree", {"tree": mock_state.tree})

    return json_response({
        "ok": True,
        "deleted": deleted_file["path"]
    })

async def api_folders_delete(request: web.Request) -> web.Response:
    """Delete a folder."""
    path = request.match_info.get("path")
    recurse = request.query.get("recurse", "").lower() in ("1", "true", "yes")

    if not path:
        return json_response({"error": "Missing path"}, 400)

    # Find files in this folder
    folder_files = []
    for f in mock_state.files:
        if f["rel"].startswith(f"{path}/"):
            folder_files.append(f["rel"])

    if not folder_files:
        return json_response({"error": "Folder not found or empty"}, 404)

    if not recurse and folder_files:
        return json_response({"error": "Folder not empty"}, 400)

    # Remove all files in folder if recursive
    if recurse:
        for file_rel in folder_files:
            mock_state.remove_file(file_rel)

        # Broadcast changes
        await broadcast_event("files", {"files": mock_state.files})
        await broadcast_event("tree", {"tree": mock_state.tree})

        return json_response({
            "ok": True,
            "deleted": path,
            "recursive": True,
            "removed_files": folder_files
        })

    return json_response({"error": "Folder operations not fully implemented"}, 400)

async def api_events(request: web.Request) -> web.Response:
    """Server-Sent Events stream for real-time status updates."""
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
        }
    )
    await response.prepare(request)

    # Add to clients
    mock_state.clients.add(response)

    async def send_event(event_type: str, data: Dict[str, Any]):
        try:
            event_data = {"type": event_type, **data}
            message = f"data: {json.dumps(event_data, separators=(',', ':'))}\n\n"
            await response.write(message.encode())
        except Exception:
            pass

    # Send initial state
    await send_event("mode", {"mode": mock_state.mode})
    await send_event("files", {"files": mock_state.files})
    await send_event("tree", {"tree": mock_state.tree})

    try:
        # Keep connection alive with periodic heartbeats
        while True:
            await asyncio.sleep(5.0)
            try:
                await response.write(b": heartbeat\n\n")
            except Exception:
                break
    except (asyncio.CancelledError, ConnectionResetError, RuntimeError):
        pass
    finally:
        mock_state.clients.discard(response)
        try:
            await response.write_eof()
        except Exception:
            pass

    return response

@web.middleware
async def spa_fallback_mw(request: web.Request, handler):
    """Middleware to serve static files and SPA fallback."""
    # API paths go to handlers
    if request.path.startswith("/api/"):
        return await handler(request)

    # For non-API paths, just return a simple message
    # In real setup, this would serve the built frontend
    if request.path == "/":
        return web.Response(
            text="""
            <html>
            <head><title>Mock MSMacro Backend</title></head>
            <body>
                <h1>Mock MSMacro Backend Server</h1>
                <p>This is a mock backend server for testing the MSMacro frontend.</p>
                <p>API endpoints:</p>
                <ul>
                    <li>GET /api/status - Get daemon status</li>
                    <li>GET /api/files - List files</li>
                    <li>GET /api/events - SSE event stream</li>
                    <li>POST /api/record/start - Start recording</li>
                    <li>POST /api/record/stop - Stop recording</li>
                    <li>POST /api/play - Play files</li>
                    <li>POST /api/stop - Stop playback</li>
                </ul>
                <p>Point your frontend to this server for testing.</p>
            </body>
            </html>
            """,
            content_type="text/html"
        )

    return web.Response(status=404, text="Not found")

def make_app() -> web.Application:
    """Create the mock application."""
    app = web.Application(middlewares=[spa_fallback_mw])

    # Add API routes
    app.add_routes([
        # Status and files
        web.get("/api/status", api_status),
        web.get("/api/files", api_list_files),
        web.get("/api/events", api_events),

        # Recording
        web.post("/api/record/start", api_record_start),
        web.post("/api/record/stop", api_record_stop),

        # PostRecord mode actions
        web.post("/api/post/save", api_post_save),
        web.post("/api/post/preview", api_post_preview),
        web.post("/api/post/discard", api_post_discard),

        # Playback
        web.post("/api/play", api_play),
        web.post("/api/stop", api_stop),

        # File management
        web.post("/api/files/rename", api_files_rename),
        web.delete("/api/files/{name:.*}", api_files_delete),

        # Folder management
        web.delete("/api/folders/{path:.*}", api_folders_delete),

        # CD Skills management
        web.get("/api/skills", api_skills_list),
        web.post("/api/skills/save", api_skills_save),
        web.put("/api/skills/{id}", api_skills_update),
        web.delete("/api/skills/{id}", api_skills_delete),
        web.get("/api/skills/selected", api_skills_selected),

        # Health check
        web.get("/api/ping", api_ping),
    ])

    return app

# ============= Skills API Handlers =============

async def api_skills_list(request: web.Request) -> web.Response:
    """List all skills."""
    skills_list = list(mock_state.skills.values())
    return json_response(skills_list)

async def api_skills_save(request: web.Request) -> web.Response:
    """Save a new skill."""
    try:
        body = await request.json()
    except Exception:
        return json_response({"error": "Invalid JSON"}, 400)

    # Validate required fields
    if not body.get("name") or not body.get("keystroke"):
        return json_response({"error": "name and keystroke are required"}, 400)

    # Generate new skill ID
    import uuid
    skill_id = str(uuid.uuid4())

    # Create skill with defaults
    skill = {
        "id": skill_id,
        "name": body.get("name"),
        "keystroke": body.get("keystroke"),
        "cooldown": float(body.get("cooldown", 10.0)),
        "after_key_constraints": bool(body.get("afterKeyConstraints", False)),
        "key1": body.get("key1", ""),
        "key2": body.get("key2", ""),
        "key3": body.get("key3", ""),
        "after_keys_seconds": float(body.get("afterKeysSeconds", 0.45)),
        "frozen_rotation_during_casting": bool(body.get("frozenRotationDuringCasting", False)),
        "is_selected": bool(body.get("isSelected", False))
    }

    # Save skill
    mock_state.skills[skill_id] = skill

    # Broadcast update
    await broadcast_event("skills", {"skills": list(mock_state.skills.values())})

    return json_response(skill)

async def api_skills_update(request: web.Request) -> web.Response:
    """Update an existing skill."""
    skill_id = request.match_info["id"]

    if skill_id not in mock_state.skills:
        return json_response({"error": "Skill not found"}, 404)

    try:
        body = await request.json()
    except Exception:
        return json_response({"error": "Invalid JSON"}, 400)

    # Update skill
    skill = mock_state.skills[skill_id].copy()
    skill.update(body)

    # Ensure boolean fields are properly converted
    if "afterKeyConstraints" in body:
        skill["after_key_constraints"] = bool(body["afterKeyConstraints"])
    if "frozenRotationDuringCasting" in body:
        skill["frozen_rotation_during_casting"] = bool(body["frozenRotationDuringCasting"])
    if "isSelected" in body:
        skill["is_selected"] = bool(body["isSelected"])
    if "afterKeysSeconds" in body:
        skill["after_keys_seconds"] = float(body["afterKeysSeconds"])

    mock_state.skills[skill_id] = skill

    # Broadcast update
    await broadcast_event("skills", {"skills": list(mock_state.skills.values())})

    return json_response(skill)

async def api_skills_delete(request: web.Request) -> web.Response:
    """Delete a skill."""
    skill_id = request.match_info["id"]

    if skill_id not in mock_state.skills:
        return json_response({"error": "Skill not found"}, 404)

    del mock_state.skills[skill_id]

    # Broadcast update
    await broadcast_event("skills", {"skills": list(mock_state.skills.values())})

    return json_response({"success": True})

async def api_skills_selected(request: web.Request) -> web.Response:
    """Get all selected skills."""
    selected_skills = [skill for skill in mock_state.skills.values() if skill.get("is_selected", False)]
    return json_response(selected_skills)

def main():
    """Run the mock server."""
    import argparse

    parser = argparse.ArgumentParser(description="Mock MSMacro Backend Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8787, help="Port to bind to")

    args = parser.parse_args()

    app = make_app()
    print(f"🚀 Starting Mock MSMacro Backend Server on {args.host}:{args.port}")
    print(f"📁 Mock record directory: /mock/records")
    print(f"🌐 Test the API at: http://{args.host}:{args.port}/")
    print(f"📡 SSE events at: http://{args.host}:{args.port}/api/events")
    print(f"🛑 Press Ctrl+C to stop")

    web.run_app(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
