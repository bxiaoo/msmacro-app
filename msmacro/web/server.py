from pathlib import Path
from aiohttp import web

from ..config import SETTINGS
from .handlers import (
    api_status, api_record_start, api_record_stop, api_play, api_stop,
    api_rename, api_delete, api_events
)

def make_app() -> web.Application:
    app = web.Application()

    # --- API routes ---
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

    # --- Static frontend (Vite build) ---
    static_dir = Path(__file__).with_name("static")
    static_dir.mkdir(parents=True, exist_ok=True)
    index_html = static_dir / "index.html"

    # 1) Serve the root as index.html
    async def index(_request: web.Request):
        if index_html.exists():
            return web.FileResponse(index_html)
        return web.Response(
            text="<h1>MS Macro Web UI</h1><p>Build the frontend to populate static/</p>",
            content_type="text/html"
        )
    app.router.add_get("/", index)

    # 2) Serve built assets (Vite puts hashed files under /assets)
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.router.add_static("/assets", str(assets_dir), follow_symlinks=True, show_index=False)

    # Optional common files (serve if present)
    for name in ("favicon.ico", "manifest.webmanifest", "robots.txt"):
        p = static_dir / name
        if p.exists():
            app.router.add_get(f"/{name}", lambda req, _p=p: web.FileResponse(_p))

    # 3) SPA fallback: for any non-API GET that would 404, serve index.html
    @web.middleware
    async def spa_fallback(request: web.Request, handler):
        try:
            return await handler(request)
        except web.HTTPNotFound:
            if request.method != "GET":
                raise
            if request.path.startswith("/api"):
                raise
            # If asset requested under /assets and missing, keep 404
            if request.path.startswith("/assets/"):
                raise
            if index_html.exists():
                return web.FileResponse(index_html)
            raise

    app.middlewares.append(spa_fallback)

    return app


def main(host="0.0.0.0", port=8787):
    app = make_app()
    try:
        web.run_app(app, host=host, port=port)
    except OSError as e:
        if getattr(e, "errno", None) == 98:  # EADDRINUSE
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
