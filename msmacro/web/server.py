from __future__ import annotations

import os
from pathlib import Path
from aiohttp import web

from .handlers import (
    api_status,
    api_list_files,
    api_events,
    api_record_start,
    api_record_stop,
    api_post_save,
    api_post_preview,
    api_post_discard,
    api_play,
    api_stop,
    api_files_rename,
    api_files_delete,
    api_folders_delete,  # Added this import
)

# ---- Config ----
STATIC_DIR = Path(os.environ.get("MSMACRO_WEB_STATIC", "/opt/msmacro-app/msmacro/web/static")).resolve()
INDEX_FILE = STATIC_DIR / "index.html"
WEB_HOST = os.environ.get("MSMACRO_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("MSMACRO_WEB_PORT", "8787"))

@web.middleware
async def spa_fallback_mw(request: web.Request, handler):
    # API paths go to handlers
    if request.path.startswith("/api/"):
        return await handler(request)

    # Serve static if file exists
    p = STATIC_DIR / request.path.lstrip("/")
    if p.is_file():
        return web.FileResponse(path=p)

    # SPA fallback
    if INDEX_FILE.is_file():
        return web.FileResponse(path=INDEX_FILE)

    return web.Response(status=404, text="not found")

def make_app() -> web.Application:
    app = web.Application(middlewares=[spa_fallback_mw])

    # API Routes
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

        # Health check
        web.get("/api/ping", lambda r: web.json_response({"ok": True})),
    ])

    # Static assets (optional redundancy)
    if STATIC_DIR.exists():
        app.router.add_static("/static/", str(STATIC_DIR), show_index=False)

    return app

def main():
    app = make_app()
    print(f"Starting MSMacro web server on {WEB_HOST}:{WEB_PORT}")
    print(f"Static dir: {STATIC_DIR}")
    print(f"Index file: {INDEX_FILE}")
    web.run_app(app, host=WEB_HOST, port=WEB_PORT)

if __name__ == "__main__":
    main()
