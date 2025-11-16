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
    api_folders_delete,
    # CD Skills handlers
    api_skills_list,
    api_skills_save,
    api_skills_update,
    api_skills_delete,
    api_skills_selected,
    api_skills_reorder,
    # CV handlers
    api_cv_status,
    api_cv_screenshot,
    api_cv_minimap_preview,
    api_cv_start,
    api_cv_stop,
    # CV map config handlers
    api_cv_map_configs_list,
    api_cv_map_configs_create,
    api_cv_map_configs_delete,
    api_cv_map_configs_activate,
    api_cv_map_configs_get_active,
    api_cv_map_configs_deactivate,
    # Object detection handlers
    api_object_detection_status,
    api_object_detection_start,
    api_object_detection_stop,
    api_object_detection_config,
    api_object_detection_config_save,
    api_object_detection_config_export,
    api_object_detection_performance,
    api_save_calibration_sample,
    api_list_calibration_samples,
    api_get_calibration_sample,
    api_download_all_calibration_samples,
    api_delete_calibration_sample,
    api_cv_frame_lossless,
    api_cv_raw_minimap,
    api_cv_detection_preview,
    api_object_detection_calibrate,
    # Departure points handlers
    api_departure_points_add,
    api_departure_points_remove,
    api_departure_points_update,
    api_departure_points_reorder,
    api_departure_points_status,
    # CV-AUTO mode handlers
    api_cv_auto_start,
    api_cv_auto_stop,
    api_cv_auto_status,
    api_link_rotations_to_point,
    # CV Item handlers
    api_cv_items_list,
    api_cv_items_create,
    api_cv_items_get,
    api_cv_items_update,
    api_cv_items_delete,
    api_cv_items_activate,
    api_cv_items_get_active,
    api_cv_items_deactivate,
    # System handlers
    api_system_stats,
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

        # CD Skills management
        web.get("/api/skills", api_skills_list),
        web.post("/api/skills/save", api_skills_save),
        web.put("/api/skills/{id}", api_skills_update),
        web.delete("/api/skills/{id}", api_skills_delete),
        web.get("/api/skills/selected", api_skills_selected),
        web.put("/api/skills/reorder", api_skills_reorder),

        # CV (Computer Vision) management
        web.get("/api/cv/status", api_cv_status),
        web.get("/api/cv/screenshot", api_cv_screenshot),
        web.get("/api/cv/mini-map-preview", api_cv_minimap_preview),
        web.post("/api/cv/start", api_cv_start),
        web.post("/api/cv/stop", api_cv_stop),

        # CV Map Configuration management
        web.get("/api/cv/map-configs", api_cv_map_configs_list),
        web.post("/api/cv/map-configs", api_cv_map_configs_create),
        web.delete("/api/cv/map-configs/{name}", api_cv_map_configs_delete),
        web.post("/api/cv/map-configs/{name}/activate", api_cv_map_configs_activate),
        web.get("/api/cv/map-configs/active", api_cv_map_configs_get_active),
        web.post("/api/cv/map-configs/deactivate", api_cv_map_configs_deactivate),

        # Departure Points management
        web.post("/api/cv/map-configs/{map_name}/departure-points", api_departure_points_add),
        web.delete("/api/cv/map-configs/{map_name}/departure-points/{point_id}", api_departure_points_remove),
        web.put("/api/cv/map-configs/{map_name}/departure-points/{point_id}", api_departure_points_update),
        web.post("/api/cv/map-configs/{map_name}/departure-points/reorder", api_departure_points_reorder),
        web.get("/api/cv/departure-points/status", api_departure_points_status),

        # Object Detection management
        web.get("/api/cv/object-detection/status", api_object_detection_status),
        web.post("/api/cv/object-detection/start", api_object_detection_start),
        web.post("/api/cv/object-detection/stop", api_object_detection_stop),
        web.post("/api/cv/object-detection/config", api_object_detection_config),
        web.post("/api/cv/object-detection/config/save", api_object_detection_config_save),
        web.get("/api/cv/object-detection/config/export", api_object_detection_config_export),
        web.get("/api/cv/object-detection/performance", api_object_detection_performance),
        web.post("/api/cv/save-calibration-sample", api_save_calibration_sample),
        web.get("/api/cv/calibration-samples", api_list_calibration_samples),
        web.get("/api/cv/calibration-sample/{filename}", api_get_calibration_sample),
        web.get("/api/cv/calibration-samples/download-zip", api_download_all_calibration_samples),
        web.delete("/api/cv/calibration-sample/{filename}", api_delete_calibration_sample),
        web.get("/api/cv/frame-lossless", api_cv_frame_lossless),
        web.get("/api/cv/raw-minimap", api_cv_raw_minimap),
        web.get("/api/cv/detection-preview", api_cv_detection_preview),
        web.post("/api/cv/object-detection/calibrate", api_object_detection_calibrate),

        # System information
        web.get("/api/system/stats", api_system_stats),

        # CV-AUTO mode control
        web.post("/api/cv-auto/start", api_cv_auto_start),
        web.post("/api/cv-auto/stop", api_cv_auto_stop),
        web.get("/api/cv-auto/status", api_cv_auto_status),

        # Rotation linking
        web.put("/api/cv/map-configs/{map_name}/departure-points/{point_id}/rotations", api_link_rotations_to_point),

        # CV Item management
        web.get("/api/cv-items", api_cv_items_list),
        web.post("/api/cv-items", api_cv_items_create),
        web.get("/api/cv-items/{name}", api_cv_items_get),
        web.put("/api/cv-items/{name}", api_cv_items_update),
        web.delete("/api/cv-items/{name}", api_cv_items_delete),
        web.post("/api/cv-items/{name}/activate", api_cv_items_activate),
        web.get("/api/cv-items/active", api_cv_items_get_active),
        web.post("/api/cv-items/deactivate", api_cv_items_deactivate),

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
