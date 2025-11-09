"""
Computer Vision command handlers for msmacro daemon.

Handles IPC commands for CV capture system operations including
starting/stopping capture and retrieving frames and status.
"""

import asyncio
import base64
import logging
from dataclasses import asdict
from typing import Dict, Any
from ..cv import get_capture_instance, CVCaptureError

logger = logging.getLogger(__name__)

# Import event emitter with fallback
try:
    from ..events import emit
except Exception:
    def emit(*_a, **_kw):
        return


class CVCommandHandler:
    """Handler for computer vision IPC commands."""

    def __init__(self, daemon):
        """
        Initialize the CV command handler.

        Args:
            daemon: Reference to the parent MacroDaemon instance
        """
        self.daemon = daemon

    async def cv_status(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get CV capture device status and latest frame information.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with CV status including:
                - connected: Whether device is connected
                - capturing: Whether capture is active
                - has_frame: Whether a frame is available
                - device: Device information (if connected)
                - capture: Capture settings (if capturing)
                - frame: Frame metadata (if available)
                - frames_captured: Total frames captured
                - frames_failed: Total failed frame captures
        """
        capture = get_capture_instance()
        status = capture.get_status()
        return status

    async def cv_get_frame(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get the latest captured frame as JPEG data.

        Auto-starts capture if not already running.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "frame" key containing base64-encoded JPEG data

        Raises:
            RuntimeError: If capture fails to start or no frame available after timeout
        """
        capture = get_capture_instance()
        status = capture.get_status()

        logger.debug(f"cv_get_frame called: capturing={status.get('capturing')}, has_frame={status.get('has_frame')}")

        # Auto-start capture if not running
        if not status.get('capturing'):
            logger.info("CV capture not running, auto-starting...")
            try:
                await capture.start()
                logger.info("CV capture auto-started successfully")

                # Wait up to 3 seconds for first frame to be captured
                for attempt in range(30):  # 30 x 0.1s = 3 seconds
                    await asyncio.sleep(0.1)
                    frame_result = capture.get_latest_frame()
                    if frame_result is not None:
                        logger.info(f"First frame captured after {(attempt + 1) * 0.1:.1f}s")
                        break
                else:
                    # Timeout waiting for first frame
                    last_error = capture.get_status().get('last_error')
                    error_detail = f": {last_error}" if last_error else ""
                    raise RuntimeError(f"Timed out waiting for first frame after auto-start{error_detail}")

            except CVCaptureError as e:
                logger.error(f"Failed to auto-start CV capture: {e}")
                raise RuntimeError(f"Failed to start CV capture: {e}")
            except Exception as e:
                logger.error(f"Unexpected error auto-starting CV capture: {e}", exc_info=True)
                raise RuntimeError(f"Failed to start CV capture: {e}")

        # Get frame
        frame_result = capture.get_latest_frame()

        if frame_result is None:
            last_error = capture.get_status().get('last_error')
            error_context = f" (last error: {last_error})" if last_error else ""
            logger.warning(f"No frame available{error_context}")
            raise RuntimeError(f"no frame available{error_context}")

        frame_data, metadata = frame_result

        # Encode as base64 for JSON transport
        payload: Dict[str, Any] = {
            "frame": base64.b64encode(frame_data).decode('ascii')
        }
        if metadata is not None:
            # Convert metadata to dict and ensure all numpy types are converted to Python types
            # This is necessary because numpy bool/int/float are not JSON-serializable
            metadata_dict = asdict(metadata)

            # Convert numpy types to Python native types
            for key, value in metadata_dict.items():
                # Handle numpy booleans
                if hasattr(value, 'item'):  # numpy scalar
                    metadata_dict[key] = value.item()  # Convert to Python type
                # Handle numpy floats/ints (also have dtype attribute)
                elif hasattr(value, 'dtype'):
                    metadata_dict[key] = value.item()

            payload["metadata"] = metadata_dict

        logger.debug(f"Returning frame: {len(frame_data)} bytes, {metadata.width}x{metadata.height}")
        return payload

    async def cv_get_raw_minimap(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get the latest raw minimap crop (before JPEG compression).

        This provides truly lossless minimap data for calibration, without
        JPEG compression artifacts. Auto-starts capture if not already running.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "minimap" key containing base64-encoded PNG data
            and metadata about the minimap region

        Raises:
            RuntimeError: If capture fails or no minimap available
        """
        capture = get_capture_instance()
        status = capture.get_status()

        logger.debug(f"cv_get_raw_minimap called: capturing={status.get('capturing')}")

        # Auto-start capture if not running
        if not status.get('capturing'):
            logger.info("CV capture not running, auto-starting for raw minimap...")
            try:
                await capture.start()
                logger.info("CV capture auto-started successfully")

                # Wait up to 3 seconds for first frame
                for attempt in range(30):
                    await asyncio.sleep(0.1)
                    minimap_result = capture.get_raw_minimap()
                    if minimap_result is not None:
                        logger.info(f"First raw minimap captured after {(attempt + 1) * 0.1:.1f}s")
                        break
                else:
                    raise RuntimeError("Timed out waiting for first raw minimap after auto-start")

            except CVCaptureError as e:
                logger.error(f"Failed to auto-start CV capture: {e}")
                raise RuntimeError(f"Failed to start CV capture: {e}")

        # Get raw minimap
        minimap_result = capture.get_raw_minimap()

        # If None but active config exists and capture is running, wait for it to be populated
        # This handles the race condition where user activates config and immediately tries calibration
        if minimap_result is None:
            try:
                from ..cv.map_config import get_manager
                manager = get_manager()
                active_config = manager.get_active_config()

                if active_config and status.get('capturing'):
                    # Active config exists and capture is running
                    # Wait up to 3 seconds for capture loop to populate raw minimap
                    logger.info(f"Active config '{active_config.name}' detected, waiting for raw minimap...")
                    for attempt in range(30):  # 30 x 0.1s = 3 seconds
                        await asyncio.sleep(0.1)

                        # Check if capture is still running (early abort if stopped)
                        current_status = capture.get_status()
                        if not current_status.get('capturing'):
                            logger.warning(
                                f"Capture stopped during auto-wait (attempt {attempt + 1}/30) - "
                                f"aborting minimap wait"
                            )
                            break

                        minimap_result = capture.get_raw_minimap()
                        if minimap_result is not None:
                            logger.info(f"Raw minimap available after {(attempt + 1) * 0.1:.1f}s")
                            break
                    else:
                        # Timeout - gather detailed diagnostic info
                        import time as time_module
                        frame_buffer_state = {
                            "has_frame": capture.frame_buffer.has_frame(),
                            "frames_captured": capture._frames_captured,
                            "frames_failed": capture._frames_failed,
                            "last_frame_time": capture._last_frame_time,
                            "time_since_last_frame": time_module.time() - capture._last_frame_time if capture._last_frame_time > 0 else None,
                        }
                        logger.error(
                            f"⏱️ Timed out waiting for raw minimap after 3 seconds. "
                            f"Config: {active_config.name} ({active_config.width}x{active_config.height}), "
                            f"Buffer state: {frame_buffer_state}"
                        )
            except Exception as e:
                logger.warning(f"Error checking active config during wait: {e}")

        # If still None after waiting, return detailed error
        if minimap_result is None:
            import time as time_module
            details: Dict[str, Any] = {
                "capturing": status.get("capturing", False),
                "region_detected": False,
                "frames_captured": capture._frames_captured,
                "frames_failed": capture._frames_failed,
                "last_frame_time": capture._last_frame_time,
                "time_since_last_frame": time_module.time() - capture._last_frame_time if capture._last_frame_time > 0 else None,
                "has_frame": capture.frame_buffer.has_frame(),
            }
            try:
                from ..cv.map_config import get_manager
                manager = get_manager()
                active_config = manager.get_active_config()
                details["active_config"] = active_config.to_dict() if active_config else None
            except Exception:
                details["active_config"] = None

            # Provide helpful troubleshooting message
            troubleshooting_hints = []
            if not details["active_config"]:
                troubleshooting_hints.append("No active map config - activate one first")
            if not details["capturing"]:
                troubleshooting_hints.append("CV capture not running")
            if details["frames_captured"] == 0:
                troubleshooting_hints.append("No frames captured yet - check camera connection")
            if details["time_since_last_frame"] and details["time_since_last_frame"] > 2.0:
                troubleshooting_hints.append(f"Last frame was {details['time_since_last_frame']:.1f}s ago - capture loop may be stuck")

            message = "Raw minimap not available. "
            if troubleshooting_hints:
                message += "Issues: " + "; ".join(troubleshooting_hints)
            else:
                message += "Config region may be out of frame bounds or capture loop delayed."

            return {
                "success": False,
                "error": "no_minimap",
                "message": message,
                "details": details,
            }

        raw_crop, metadata = minimap_result

        # Encode raw crop as PNG (lossless)
        import cv2
        ret, png_data = cv2.imencode('.png', raw_crop)
        if not ret:
            raise RuntimeError("Failed to encode raw minimap as PNG")

        # Convert numpy array to bytes immediately for consistent handling
        png_bytes = png_data.tobytes()

        # Encode as base64 for JSON transport
        payload: Dict[str, Any] = {
            "success": True,
            "minimap": base64.b64encode(png_bytes).decode('ascii'),
            "format": "png"
        }

        # Add metadata
        if metadata is not None:
            metadata_dict = asdict(metadata)
            # Convert numpy types to Python native types
            for key, value in metadata_dict.items():
                if hasattr(value, 'item'):
                    metadata_dict[key] = value.item()
                elif hasattr(value, 'dtype'):
                    metadata_dict[key] = value.item()
            payload["metadata"] = metadata_dict

        logger.debug(f"Returning raw minimap: shape={raw_crop.shape}, PNG size: {len(png_bytes)} bytes")
        return payload

    async def cv_start(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start the CV capture system.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "started" key set to True and "status" with current state

        Note:
            Emits CV_STARTED event on success
        """
        capture = get_capture_instance()
        await capture.start()
        emit("CV_STARTED")
        return {"started": True, "status": capture.get_status()}

    async def cv_stop(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stop the CV capture system.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "stopped" key set to True

        Note:
            Emits CV_STOPPED event on success
        """
        capture = get_capture_instance()
        await capture.stop()
        emit("CV_STOPPED")
        return {"stopped": True}

    async def cv_reload_config(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reload map configuration from disk.

        Called when map configurations are modified via the web API
        to update the active detection region without restarting capture.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "reloaded" key set to True and current config info

        Note:
            Emits CV_CONFIG_RELOADED event on success
        """
        capture = get_capture_instance()
        logger.info("🔄 CV_RELOAD_CONFIG IPC called - triggering config reload...")
        capture.reload_config()
        emit("CV_CONFIG_RELOADED")

        # Get current config for response
        from ..cv.map_config import get_manager
        manager = get_manager()
        active_config = manager.get_active_config()

        logger.info(
            f"✓ RELOAD COMPLETE | active_config={active_config.name if active_config else None}"
        )

        return {
            "reloaded": True,
            "active_config": active_config.to_dict() if active_config else None
        }
    
    async def object_detection_status(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get object detection status and latest result.
        
        Args:
            msg: IPC message (unused)
        
        Returns:
            Dictionary with:
                - enabled: Boolean, whether detection is active
                - last_result: Latest detection result dict (or None)
        """
        capture = get_capture_instance()
        
        return {
            "enabled": capture._object_detection_enabled,
            "last_result": capture.get_last_detection_result()
        }
    
    async def object_detection_start(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enable object detection with optional configuration.
        
        Args:
            msg: IPC message with optional "config" key containing detector config
        
        Returns:
            Dictionary with "success" key set to True
        
        Note:
            Emits OBJECT_DETECTION_STARTED event on success
        """
        capture = get_capture_instance()
        config = msg.get("config")
        
        try:
            capture.enable_object_detection(config)
            emit("OBJECT_DETECTION_STARTED")
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to start object detection: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def object_detection_stop(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Disable object detection.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "success" key set to True

        Note:
            Emits OBJECT_DETECTION_STOPPED event on success
        """
        capture = get_capture_instance()
        capture.disable_object_detection()
        emit("OBJECT_DETECTION_STOPPED")
        return {"success": True}

    async def cv_get_detection_preview(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get minimap with detection visualization overlays.

        This handler runs entirely in the daemon process where the detector exists.
        It fetches the raw minimap, gets the last detection result, renders the
        visualization, and returns the PNG-encoded image via IPC.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with:
                - success: Boolean
                - preview: Base64-encoded PNG image (if success=True)
                - error: Error code (if success=False)
                - message: Error message (if success=False)
                - timestamp: Detection timestamp (if success=True)
        """
        import base64
        import cv2
        import numpy as np

        capture = get_capture_instance()

        # Check if detection is enabled
        if not capture._object_detection_enabled:
            logger.debug("Detection preview failed: detection not enabled")
            return {
                "success": False,
                "error": "detection_not_enabled",
                "message": "Object detection not enabled. Use object_detection_start to enable."
            }

        # Check if detector exists
        if not capture._object_detector:
            logger.error("Detection preview failed: detector is None despite enabled=True")
            return {
                "success": False,
                "error": "detector_null",
                "message": "Object detector is null (initialization failure)"
            }

        # Get raw minimap
        minimap_data = capture.get_raw_minimap()
        if not minimap_data:
            logger.debug("Detection preview failed: no raw minimap available")
            return {
                "success": False,
                "error": "no_minimap",
                "message": "No raw minimap available. Ensure capture is running with active map config."
            }

        raw_crop, metadata = minimap_data

        # Get last detection result
        last_result_dict = capture.get_last_detection_result()
        if not last_result_dict:
            logger.debug("Detection preview failed: no detection result yet")
            return {
                "success": False,
                "error": "no_result",
                "message": "No detection result available yet. Detection may still be initializing."
            }

        # Reconstruct DetectionResult from dict
        from msmacro.cv.object_detection import DetectionResult, PlayerPosition, OtherPlayersStatus

        player_data = last_result_dict.get("player", {})
        other_players_data = last_result_dict.get("other_players", {})

        # Reconstruct player positions
        player_pos = PlayerPosition(
            detected=player_data.get("detected", False),
            x=player_data.get("x", 0),
            y=player_data.get("y", 0),
            confidence=player_data.get("confidence", 0.0)
        )

        # Reconstruct other players positions
        other_positions = []
        for pos_data in other_players_data.get("positions", []):
            other_positions.append(PlayerPosition(
                detected=True,
                x=pos_data.get("x", 0),
                y=pos_data.get("y", 0),
                confidence=pos_data.get("confidence", 0.0)
            ))

        other_players = OtherPlayersStatus(
            detected=other_players_data.get("detected", False),
            count=other_players_data.get("count", 0),
            positions=other_positions
        )

        result = DetectionResult(
            player=player_pos,
            other_players=other_players,
            timestamp=last_result_dict.get("timestamp", 0.0)
        )

        logger.debug(
            f"Rendering detection preview | "
            f"player.detected={result.player.detected} | "
            f"player.pos=({result.player.x},{result.player.y}) | "
            f"other_players.count={result.other_players.count}"
        )

        # Visualize detection on minimap
        try:
            visualized = capture._object_detector.visualize(raw_crop, result)
            logger.debug(f"Visualization complete | frame_shape={visualized.shape}")
        except Exception as viz_err:
            logger.error(f"Visualization failed: {viz_err}", exc_info=True)
            return {
                "success": False,
                "error": "visualization_failed",
                "message": f"Visualization error: {viz_err}"
            }

        # Encode as PNG
        try:
            ret, png_data = cv2.imencode('.png', visualized)
            if not ret:
                logger.error("PNG encoding failed: cv2.imencode returned False")
                return {
                    "success": False,
                    "error": "encode_failed",
                    "message": "Failed to encode visualization as PNG"
                }

            png_bytes = png_data.tobytes()
            preview_b64 = base64.b64encode(png_bytes).decode('ascii')

            logger.debug(f"Detection preview generated | size={len(png_bytes)} bytes")

            return {
                "success": True,
                "preview": preview_b64,
                "timestamp": result.timestamp
            }

        except Exception as encode_err:
            logger.error(f"PNG encoding exception: {encode_err}", exc_info=True)
            return {
                "success": False,
                "error": "encode_exception",
                "message": f"Encoding error: {encode_err}"
            }
    
    async def object_detection_config(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update object detection configuration.
        
        Args:
            msg: IPC message with "config" key containing new detector config
        
        Returns:
            Dictionary with "success" key set to True
        
        Note:
            Restarts detection with new config if currently enabled
        """
        capture = get_capture_instance()
        config = msg.get("config")
        
        if not config:
            return {"success": False, "error": "No config provided"}
        
        try:
            # Restart detection with new config
            was_enabled = capture._object_detection_enabled
            if was_enabled:
                capture.disable_object_detection()
            
            capture.enable_object_detection(config)
            
            emit("OBJECT_DETECTION_CONFIG_UPDATED")
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to update object detection config: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def object_detection_config_save(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save current object detection config to disk.
        
        Args:
            msg: IPC message with optional "metadata" key
        
        Returns:
            Dictionary with "success" and "path" keys
        """
        from ..cv.detection_config import save_config, get_config_path
        
        capture = get_capture_instance()
        
        if not capture._object_detector:
            return {"success": False, "error": "Object detection not initialized"}
        
        try:
            config = capture._object_detector.config
            metadata = msg.get("metadata", {})
            
            save_config(config, metadata)
            
            return {
                "success": True,
                "path": str(get_config_path())
            }
        except Exception as e:
            logger.error(f"Failed to save config: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def object_detection_config_export(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export current object detection config as dict.
        
        Args:
            msg: IPC message (unused)
        
        Returns:
            Dictionary with "success" and "config" keys
        """
        capture = get_capture_instance()
        
        if not capture._object_detector:
            return {"success": False, "error": "Object detection not initialized"}
        
        try:
            config = capture._object_detector.config
            
            return {
                "success": True,
                "config": {
                    "player_hsv_lower": list(config.player_hsv_lower),
                    "player_hsv_upper": list(config.player_hsv_upper),
                    "other_player_hsv_ranges": [
                        [list(lower), list(upper)]
                        for lower, upper in config.other_player_hsv_ranges
                    ],
                    "min_blob_size": config.min_blob_size,
                    "max_blob_size": config.max_blob_size,
                    "min_circularity": config.min_circularity,
                    "min_circularity_other": config.min_circularity_other,
                    "temporal_smoothing": config.temporal_smoothing,
                    "smoothing_alpha": config.smoothing_alpha
                }
            }
        except Exception as e:
            logger.error(f"Failed to export config: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def object_detection_performance(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get object detection performance statistics.
        
        Args:
            msg: IPC message (unused)
        
        Returns:
            Dictionary with performance stats (avg_ms, max_ms, min_ms, count)
        """
        capture = get_capture_instance()
        
        if not capture._object_detector:
            return {"success": False, "error": "Object detection not initialized"}
        
        try:
            stats = capture._object_detector.get_performance_stats()
            return {"success": True, "stats": stats}
        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def object_detection_calibrate(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Auto-calibrate HSV ranges from user clicks on frames.

        Args:
            msg: IPC message with:
                - color_type: "player" or "other_player"
                - samples: List of {frame_base64, x, y} dicts
                  Note: frame_base64 contains ONLY the minimap region (cropped)
                  Note: x, y are relative to minimap top-left (0, 0)

        Returns:
            Dictionary with calibrated HSV ranges and preview mask
        """
        import base64
        import cv2
        import numpy as np
        import time

        calibration_start = time.perf_counter()

        try:
            color_type = msg.get("color_type", "player")
            samples = msg.get("samples", [])

            logger.info(
                f"🎨 Starting calibration for '{color_type}' with {len(samples)} sample(s)"
            )

            if not samples or len(samples) < 3:
                logger.warning(f"Insufficient samples: need ≥3, got {len(samples)}")
                return {"success": False, "error": "Need at least 3 samples"}

            hsv_samples = []
            sample_coords = []
            skipped_samples = 0

            # Process each sample
            for i, sample in enumerate(samples, 1):
                frame_b64 = sample.get("frame")
                x = sample.get("x")
                y = sample.get("y")

                if not frame_b64 or x is None or y is None:
                    logger.debug(f"Sample {i}/{len(samples)}: skipped (missing data)")
                    skipped_samples += 1
                    continue

                # Decode frame
                img_bytes = base64.b64decode(frame_b64)
                img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                frame_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                if frame_bgr is None:
                    logger.debug(f"Sample {i}/{len(samples)}: skipped (decode failed)")
                    skipped_samples += 1
                    continue

                # Sample 3x3 region around click
                h, w = frame_bgr.shape[:2]
                y1 = max(0, y - 1)
                y2 = min(h, y + 2)
                x1 = max(0, x - 1)
                x2 = min(w, x + 2)

                region = frame_bgr[y1:y2, x1:x2]
                if region.size == 0:
                    logger.debug(f"Sample {i}/{len(samples)}: skipped (empty region at {x},{y})")
                    skipped_samples += 1
                    continue

                hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
                pixels_before = len(hsv_samples)
                hsv_samples.extend(hsv_region.reshape(-1, 3))
                pixels_added = len(hsv_samples) - pixels_before

                sample_coords.append((x, y))
                logger.debug(
                    f"Sample {i}/{len(samples)}: ({x},{y}) frame={w}x{h}, "
                    f"region={x1}:{x2},{y1}:{y2}, pixels={pixels_added}"
                )

            if not hsv_samples:
                logger.error("All samples failed to process - no valid HSV data collected")
                return {"success": False, "error": "No valid samples collected"}

            logger.info(
                f"📊 Collected {len(hsv_samples)} HSV pixels from {len(samples) - skipped_samples}/{len(samples)} samples | "
                f"coords={sample_coords}"
            )

            # Calculate percentile ranges (5th to 95th percentile)
            hsv_array = np.array(hsv_samples)
            hsv_min = np.percentile(hsv_array, 5, axis=0)
            hsv_max = np.percentile(hsv_array, 95, axis=0)

            logger.debug(
                f"Percentiles (5th-95th): H=[{hsv_min[0]:.1f}, {hsv_max[0]:.1f}], "
                f"S=[{hsv_min[1]:.1f}, {hsv_max[1]:.1f}], "
                f"V=[{hsv_min[2]:.1f}, {hsv_max[2]:.1f}]"
            )

            # Add 20% margin for robustness
            margin = (hsv_max - hsv_min) * 0.2
            hsv_lower = np.maximum(hsv_min - margin, [0, 0, 0])
            hsv_upper = np.minimum(hsv_max + margin, [179, 255, 255])

            logger.debug(
                f"Margin (20%): H={margin[0]:.1f}, S={margin[1]:.1f}, V={margin[2]:.1f}"
            )

            # Generate preview mask using latest frame
            preview_b64 = samples[-1].get("frame")
            img_bytes = base64.b64decode(preview_b64)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            preview_frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            hsv_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv_frame, hsv_lower.astype(np.uint8), hsv_upper.astype(np.uint8))

            # Calculate mask coverage
            mask_coverage = (np.count_nonzero(mask) / mask.size) * 100

            # Encode mask as PNG
            _, mask_png = cv2.imencode('.png', mask)
            mask_b64 = base64.b64encode(mask_png.tobytes()).decode('ascii')

            elapsed_ms = (time.perf_counter() - calibration_start) * 1000.0

            logger.info(
                f"✓ Calibrated '{color_type}' in {elapsed_ms:.1f}ms | "
                f"HSV lower={hsv_lower.astype(int).tolist()}, "
                f"upper={hsv_upper.astype(int).tolist()} | "
                f"preview_mask_coverage={mask_coverage:.1f}%"
            )

            return {
                "success": True,
                "color_type": color_type,
                "hsv_lower": hsv_lower.astype(int).tolist(),
                "hsv_upper": hsv_upper.astype(int).tolist(),
                "preview_mask": mask_b64,
                "sample_count": len(samples) - skipped_samples,
                "pixel_count": len(hsv_samples)
            }

        except Exception as e:
            logger.error(f"❌ Calibration failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def cv_save_calibration_sample(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save the current raw minimap as a calibration sample to disk.

        Saves the minimap as a lossless PNG file for manual annotation and
        analysis. Each sample includes metadata (timestamp, map config, user notes).

        Args:
            msg: IPC message with optional keys:
                - filename: Custom filename (without extension)
                - metadata: Dict with user notes, conditions, etc.

        Returns:
            Dictionary with:
                - success: Whether save succeeded
                - filename: Saved filename (auto-generated if not provided)
                - path: Absolute path to saved file
                - checksum: SHA256 of PNG data
                - metadata_path: Path to metadata JSON
                - error: Error code if failed
                - message: Human-readable error message
                - details: Diagnostic information for troubleshooting

        Raises:
            RuntimeError: If capture fails or no minimap available
        """
        import cv2
        import hashlib
        import json
        from datetime import datetime
        from pathlib import Path
        from ..utils.config import DEFAULT_CALIBRATION_DIR

        logger.info("🔵 cv_save_calibration_sample: Starting sample save request")

        try:
            # Step 1: Get capture instance
            try:
                capture = get_capture_instance()
                logger.debug("✅ Capture instance obtained")
            except Exception as e:
                logger.error(f"❌ Failed to get capture instance: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": "capture_instance_failed",
                    "message": "Failed to get CV capture instance. Is the daemon running?",
                    "details": {"exception": str(e)}
                }

            # Step 2: Check CV capture status
            status = capture.get_status()
            logger.debug(f"📊 CV Status: capturing={status.get('capturing')}, connected={status.get('connected')}, has_frame={status.get('has_frame')}")

            # Step 3: Check for active map config
            try:
                from ..cv.map_config import get_manager
                manager = get_manager()
                active_config = manager.get_active_config()

                if not active_config:
                    logger.warning("❌ No active map configuration")
                    return {
                        "success": False,
                        "error": "no_active_config",
                        "message": "No active map configuration. Please activate a map config in CV Configuration tab.",
                        "details": {
                            "capturing": status.get('capturing'),
                            "has_frame": status.get('has_frame'),
                            "action": "Go to CV Configuration → Create/Activate a map config"
                        }
                    }

                logger.debug(f"✅ Active config: {active_config.name} ({active_config.width}×{active_config.height})")
            except Exception as e:
                logger.error(f"❌ Failed to check map config: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": "config_check_failed",
                    "message": f"Failed to verify map configuration: {e}",
                    "details": {"exception": str(e)}
                }

            # Step 4: Try to get raw minimap
            minimap_result = capture.get_raw_minimap()
            logger.debug(f"🖼️ Raw minimap result: {minimap_result is not None}")

            if minimap_result is None:
                # Auto-start capture if not running
                if not status.get('capturing'):
                    logger.info("🔄 Auto-starting capture for calibration sample save...")
                    try:
                        await capture.start()
                        logger.info("✅ Capture started, waiting for first frame...")

                        # Wait for first frame with progress logging
                        for attempt in range(30):
                            await asyncio.sleep(0.1)
                            minimap_result = capture.get_raw_minimap()
                            if minimap_result is not None:
                                logger.info(f"✅ First minimap captured after {(attempt + 1) * 0.1:.1f}s")
                                break
                            if (attempt + 1) % 10 == 0:
                                logger.debug(f"⏳ Still waiting for frame... ({(attempt + 1) * 0.1:.1f}s)")
                        else:
                            logger.error("❌ Timeout waiting for minimap after auto-start (3s)")
                            return {
                                "success": False,
                                "error": "minimap_timeout_after_start",
                                "message": "Timeout waiting for minimap after starting capture. Check camera connection.",
                                "details": {
                                    "waited_seconds": 3.0,
                                    "config": f"{active_config.name} ({active_config.width}×{active_config.height})",
                                    "action": "1. Check camera is connected\n2. Verify camera permissions\n3. Check capture device path"
                                }
                            }
                    except CVCaptureError as e:
                        logger.error(f"❌ Failed to start CV capture: {e}", exc_info=True)
                        return {
                            "success": False,
                            "error": "capture_start_failed",
                            "message": f"Failed to start CV capture: {e}",
                            "details": {
                                "exception": str(e),
                                "action": "Check camera connection and permissions"
                            }
                        }
                else:
                    # Capture is running but no minimap yet
                    logger.info("⏳ Capture running but no minimap yet, waiting...")

                    # Wait for minimap to be populated
                    for attempt in range(30):
                        await asyncio.sleep(0.1)
                        minimap_result = capture.get_raw_minimap()
                        if minimap_result is not None:
                            logger.info(f"✅ Minimap available after {(attempt + 1) * 0.1:.1f}s")
                            break

                        # Check if capture stopped while waiting
                        current_status = capture.get_status()
                        if not current_status.get('capturing'):
                            logger.warning(f"⚠️ Capture stopped during wait (attempt {attempt + 1}/30)")
                            break

                        if (attempt + 1) % 10 == 0:
                            logger.debug(f"⏳ Still waiting for minimap... ({(attempt + 1) * 0.1:.1f}s)")
                    else:
                        # Timeout - gather detailed diagnostic info
                        logger.error("❌ Timeout waiting for minimap (3s)")
                        diagnostic_info = {
                            "status": status,
                            "active_config": {
                                "name": active_config.name,
                                "region": f"({active_config.tl_x}, {active_config.tl_y}) {active_config.width}×{active_config.height}"
                            },
                            "waited_seconds": 3.0
                        }

                        return {
                            "success": False,
                            "error": "minimap_not_available",
                            "message": "Raw minimap not available after 3 seconds. Capture may be delayed or region may be out of bounds.",
                            "details": {
                                **diagnostic_info,
                                "action": "1. Wait a few seconds and try again\n2. Check if map config region is within frame bounds\n3. Verify live preview shows minimap"
                            }
                        }

            if minimap_result is None:
                logger.error("❌ Minimap still None after all attempts")
                return {
                    "success": False,
                    "error": "minimap_unavailable",
                    "message": "Unable to retrieve minimap. Unknown error.",
                    "details": {"status": status}
                }

            # Step 5: Validate minimap data
            raw_crop, frame_metadata = minimap_result
            logger.info(f"✅ Got minimap: shape={raw_crop.shape}, dtype={raw_crop.dtype}")

            # Validate crop dimensions
            if raw_crop.size == 0:
                logger.error("❌ Minimap crop is empty (size=0)")
                return {
                    "success": False,
                    "error": "empty_minimap",
                    "message": "Minimap crop is empty. Map config region may be invalid.",
                    "details": {
                        "shape": raw_crop.shape,
                        "config": f"{active_config.name} ({active_config.width}×{active_config.height})"
                    }
                }

            # Step 6: Generate filename
            filename = msg.get('filename')
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"sample_{timestamp}"

            # Sanitize filename
            filename = filename.replace('.png', '').replace('.jpg', '')
            filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-'))
            logger.debug(f"📝 Filename: {filename}.png")

            # Step 7: Create calibration directory
            try:
                calibration_dir = Path(DEFAULT_CALIBRATION_DIR)
                samples_dir = calibration_dir / "minimap_samples"
                samples_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"📁 Samples directory: {samples_dir}")
            except Exception as e:
                logger.error(f"❌ Failed to create directory: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": "directory_creation_failed",
                    "message": f"Failed to create calibration directory: {e}",
                    "details": {
                        "path": str(calibration_dir),
                        "exception": str(e),
                        "action": "Check filesystem permissions"
                    }
                }

            # Step 8: Encode as PNG
            try:
                ret, png_data = cv2.imencode('.png', raw_crop)
                if not ret:
                    logger.error("❌ PNG encoding failed")
                    return {
                        "success": False,
                        "error": "png_encode_failed",
                        "message": "Failed to encode minimap as PNG",
                        "details": {
                            "shape": raw_crop.shape,
                            "dtype": str(raw_crop.dtype)
                        }
                    }

                png_bytes = png_data.tobytes()
                logger.debug(f"✅ Encoded PNG: {len(png_bytes)} bytes")
            except Exception as e:
                logger.error(f"❌ PNG encoding exception: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": "png_encode_exception",
                    "message": f"Exception during PNG encoding: {e}",
                    "details": {"exception": str(e)}
                }

            # Step 9: Calculate checksum
            checksum = hashlib.sha256(png_bytes).hexdigest()[:16]
            logger.debug(f"🔐 Checksum: {checksum}")

            # Step 10: Save PNG file
            try:
                png_path = samples_dir / f"{filename}.png"
                with open(png_path, 'wb') as f:
                    f.write(png_bytes)
                logger.info(f"✅ Saved calibration sample: {png_path} ({len(png_bytes)} bytes)")
            except Exception as e:
                logger.error(f"❌ Failed to write PNG file: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": "file_write_failed",
                    "message": f"Failed to write PNG file: {e}",
                    "details": {
                        "path": str(png_path),
                        "exception": str(e),
                        "action": "Check disk space and filesystem permissions"
                    }
                }

            # Prepare metadata
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "filename": f"{filename}.png",
                "capture_info": {
                    "resolution": list(raw_crop.shape[:2][::-1]),  # [width, height]
                    "format": "BGR",
                    "channels": raw_crop.shape[2] if len(raw_crop.shape) > 2 else 1,
                    "checksum": checksum
                }
            }

            # Add frame metadata if available
            if frame_metadata:
                metadata_dict = asdict(frame_metadata)
                # Convert numpy types to native Python
                for key, value in metadata_dict.items():
                    if hasattr(value, 'item'):
                        metadata_dict[key] = value.item()
                metadata["frame_metadata"] = metadata_dict

            # Add map config info
            try:
                from ..cv.map_config import get_manager
                manager = get_manager()
                active_config = manager.get_active_config()
                if active_config:
                    metadata["map_config"] = {
                        "name": active_config.name,
                        "tl_x": active_config.tl_x,
                        "tl_y": active_config.tl_y,
                        "width": active_config.width,
                        "height": active_config.height
                    }
            except Exception as e:
                logger.warning(f"Failed to get map config for metadata: {e}")

            # Add user-provided metadata
            user_metadata = msg.get('metadata', {})
            if user_metadata:
                metadata["user_notes"] = user_metadata

            # Step 11: Save metadata JSON
            try:
                meta_path = samples_dir / f"{filename}_meta.json"
                with open(meta_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                logger.info(f"✅ Saved metadata: {meta_path}")
            except Exception as e:
                logger.error(f"❌ Failed to write metadata JSON: {e}", exc_info=True)
                # Don't fail the whole operation if metadata save fails
                logger.warning("⚠️ Continuing without metadata (PNG saved successfully)")
                meta_path = None

            # Step 12: Success!
            logger.info(f"🎉 Sample save complete: {filename}.png ({len(png_bytes)} bytes)")
            return {
                "success": True,
                "filename": f"{filename}.png",
                "path": str(png_path.absolute()),
                "checksum": checksum,
                "metadata_path": str(meta_path.absolute()) if meta_path else None,
                "size_bytes": len(png_bytes),
                "resolution": metadata["capture_info"]["resolution"]
            }

        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"❌ Unexpected error during sample save: {e}", exc_info=True)
            return {
                "success": False,
                "error": "unexpected_error",
                "message": f"Unexpected error: {e}",
                "details": {
                    "exception": str(e),
                    "type": type(e).__name__,
                    "action": "Check daemon logs for full traceback. Try restarting daemon if issue persists."
                }
            }
