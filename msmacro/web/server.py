from pathlib import Path
from aiohttp import web

from ..config import SETTINGS
from .handlers import (
    api_status, api_record_start, api_record_stop, api_play, api_stop,
    api_rename, api_delete, api_events
)

def make_app() -> web.Application:
    app = web.Application()
    # API
    app.add_routes([
        web.get("/api/status", api_status),
        web.post("/api/record/start", api_record_start),
        web.post("/api/record/stop", api_record_stop),
        web.post("/api/play", api_play),
        web.post("/api/stop", api_stop),
        web.post("/api/files/rename", api_rename),
        web.delete("/api/files/{name}", api_delete),
        web.get("/api/events", api_events),
    ])

    # Static frontend (built React app lives here)
    static_dir = Path(__file__).with_suffix("").parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.add_routes([web.static("/", str(static_dir), show_index=True)])

    # Fallback / -> index.html (if exists)
    async def index(_: web.Request):
        idx = static_dir / "index.html"
        if idx.exists():
            return web.FileResponse(idx)
        # minimal fallback
        return web.Response(text="<h1>MS Macro Web UI</h1><p>Build the frontend to populate static/</p>", content_type="text/html")

    app.add_routes([web.get("/", index)])
    return app

def main(host="0.0.0.0", port=8787):
    app = make_app()
    try:
        web.run_app(app, host=host, port=port)
    except OSError as e:
        if getattr(e, "errno", None) == 98:
            print(f"[web] Port {port} already in use. Is msmacro-web service running?")
        else:
            raise

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    main(args.host, args.port)
