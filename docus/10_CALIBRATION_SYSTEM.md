# Object Detection Calibration System

**Document Version**: 1.0
**Last Updated**: 2025-11-09
**Status**: Production - Comprehensive Technical Documentation

## Overview

The msmacro object detection calibration system allows users to fine-tune HSV color ranges for accurate detection of player (yellow) and other player (red) markers on the minimap. The system uses a wizard-driven interface to collect color samples from actual game frames and automatically calculates optimal detection parameters.

### Key Features

- **Truly Lossless Data**: Uses raw BGR minimap crop captured before JPEG compression
- **5-Sample Collection**: Users click on target colors 5 times across different frames
- **Robust Algorithm**: Percentile-based HSV calculation with automatic margin
- **Live Preview**: Visual mask overlay shows detection results before applying
- **Persistent Storage**: Configuration saved to disk for use across sessions

### System Architecture

```
User Clicks (5x) → Frontend Wizard → API Endpoint → Daemon Handler → HSV Calculation
                                                                           ↓
                    Detection System ← Config Storage ← Apply & Save ← Preview Mask
```

---

## Complete Data Flow

### Step 1: Frontend Loads Raw Frame

**Component**: `webui/src/components/CalibrationWizard.jsx` (Lines 36-80)

**Process**:
1. User clicks "Start Collection" button
2. Frontend requests truly lossless frame via `/api/cv/raw-minimap`
3. Frame is displayed for user to click on target color

**Code**:
```javascript
const loadFrame = async () => {
  setLoading(true);
  setError(null);
  try {
    // Fetch truly lossless raw minimap (before JPEG compression)
    const response = await fetch(`/api/cv/raw-minimap?t=${Date.now()}`);
    if (!response.ok) throw new Error(`Failed to load frame`);

    const blob = await response.blob();
    const dataUrl = await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.readAsDataURL(blob);
    });

    setCurrentFrame(dataUrl);  // base64-encoded PNG
    setPan({ x: 0, y: 0 });
    setFrameTimestamp(Date.now());
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
};
```

**Data Quality**: The frame is truly lossless because it's extracted from the raw BGR capture BEFORE any JPEG encoding occurs.

---

### Step 2: API Serves Raw Minimap

**Endpoint**: `GET /api/cv/raw-minimap`
**Handler**: `msmacro/web/handlers.py` (Lines 1122-1191)

**Process**:
1. HTTP handler receives request
2. Calls daemon via IPC: `cv_get_raw_minimap`
3. Receives base64-encoded PNG
4. Returns PNG to frontend with metadata headers

**Code**:
```python
async def api_cv_raw_minimap(request: web.Request):
    """
    Serve truly lossless raw minimap (captured BEFORE JPEG compression).
    """
    try:
        # Get raw minimap via IPC
        result = await _daemon("cv_get_raw_minimap")

        if not result.get("success", True):
            return _json({"error": result.get("error")}, status=404)

        # Extract PNG data
        minimap_b64 = result.get("minimap")
        metadata = result.get("metadata", {})

        import base64, hashlib
        png_bytes = base64.b64decode(minimap_b64)
        checksum = hashlib.md5(png_bytes).hexdigest()

        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Minimap-X": str(metadata.get("region_x", 0)),
            "X-Minimap-Y": str(metadata.get("region_y", 0)),
            "X-Minimap-Width": str(metadata.get("region_width", 0)),
            "X-Minimap-Height": str(metadata.get("region_height", 0)),
            "X-Minimap-Checksum": checksum,
            "X-Minimap-Source": "raw",
        }

        return web.Response(body=png_bytes, content_type="image/png", headers=headers)
    except Exception as e:
        return web.Response(status=500, text=str(e))
```

---

### Step 3: Daemon Retrieves Raw Minimap Crop

**IPC Command**: `cv_get_raw_minimap`
**Handler**: `msmacro/daemon_handlers/cv_commands.py` (Lines 140-260)

**Process**:
1. Gets capture instance
2. Checks for active map config
3. Waits up to 2 seconds if minimap not immediately available (handles race condition)
4. Retrieves raw BGR crop from frame buffer
5. Encodes as PNG (lossless)
6. Returns base64-encoded data

**Code**:
```python
async def cv_get_raw_minimap(self, msg: Dict[str, Any]) -> Dict[str, Any]:
    capture = get_capture_instance()
    status = capture.get_status()

    # Get raw minimap
    minimap_result = capture.get_raw_minimap()

    # Auto-wait if active config exists but minimap not populated yet
    if minimap_result is None:
        try:
            from ..cv.map_config import get_manager
            manager = get_manager()
            active_config = manager.get_active_config()

            if active_config and status.get('capturing'):
                # Wait up to 2 seconds for capture loop to populate
                logger.info("Waiting for raw minimap to be captured...")
                for attempt in range(20):
                    await asyncio.sleep(0.1)
                    minimap_result = capture.get_raw_minimap()
                    if minimap_result is not None:
                        logger.info(f"Raw minimap available after {(attempt + 1) * 0.1:.1f}s")
                        break
        except Exception as e:
            logger.warning(f"Error checking active config: {e}")

    if minimap_result is None:
        return {
            "success": False,
            "error": "no_minimap",
            "message": "No raw minimap available. Activate a CV map configuration."
        }

    raw_crop, metadata = minimap_result

    # Encode raw crop as PNG (lossless)
    import cv2
    ret, png_data = cv2.imencode('.png', raw_crop)
    if not ret:
        raise RuntimeError("Failed to encode raw minimap as PNG")

    # Convert numpy array to bytes
    png_bytes = png_data.tobytes()

    return {
        "success": True,
        "minimap": base64.b64encode(png_bytes).decode('ascii'),
        "format": "png",
        "metadata": asdict(metadata)
    }
```

**Key Feature**: Auto-wait logic handles race condition where user clicks calibration immediately after activating map config (before capture loop runs).

---

### Step 4: Capture System Stores Raw Minimap

**File**: `msmacro/cv/capture.py` (Lines 494-570)

**Process**:
1. Capture loop runs at 2 FPS (every 0.5 seconds)
2. Gets active map config coordinates
3. **BEFORE JPEG encoding**, extracts minimap region from raw BGR frame
4. Stores separately in frame buffer
5. Continues with JPEG encoding for full frame storage

**Code**:
```python
def _capture_loop(self) -> None:
    while not self._stop_event.is_set():
        ret, frame = self._capture.read()

        # Get user-defined minimap coordinates from active map config
        with self._config_lock:
            active_config = self._active_map_config

        if active_config:
            region_x = active_config.tl_x
            region_y = active_config.tl_y
            region_width = active_config.width
            region_height = active_config.height

            if (region_x + region_width <= frame_width and
                region_y + region_height <= frame_height):
                region_detected = True

        # Extract raw minimap crop BEFORE JPEG encoding
        # This provides truly lossless data for calibration
        raw_minimap_crop = None
        if region_detected:
            raw_minimap_crop = frame[
                region_y:region_y + region_height,
                region_x:region_x + region_width
            ].copy()  # Copy to prevent reference to full frame

        # NOW encode as JPEG (raw_minimap_crop already saved)
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        ret, jpeg_data = cv2.imencode('.jpg', frame, encode_param)
        jpeg_bytes = jpeg_data.tobytes()

        # Store in buffer with BOTH JPEG and raw minimap
        self.frame_buffer.update(
            jpeg_bytes,  # Full frame as JPEG
            width,
            height,
            timestamp=timestamp,
            region_detected=region_detected,
            region_x=region_x,
            region_y=region_y,
            region_width=region_width,
            region_height=region_height,
            raw_minimap_crop=raw_minimap_crop  # Raw minimap (NO JPEG!)
        )

        time.sleep(0.5)  # 2 FPS capture rate
```

**Memory Footprint**: Raw minimap is ~88KB for typical 340x86 region (acceptable overhead for lossless quality).

---

### Step 5: Frame Buffer Storage

**File**: `msmacro/cv/frame_buffer.py` (Lines 39-122)

**Storage**:
```python
class FrameBuffer:
    def __init__(self):
        self._lock = threading.Lock()
        self._frame_data: Optional[bytes] = None  # JPEG full frame
        self._metadata: Optional[FrameMetadata] = None
        # Raw minimap crop (BGR numpy array) for lossless calibration
        self._raw_minimap_crop: Optional['numpy.ndarray'] = None

    def update(self, jpeg_data, ..., raw_minimap_crop=None):
        with self._lock:
            self._frame_data = jpeg_data
            self._metadata = metadata
            # Store raw minimap crop copy
            self._raw_minimap_crop = raw_minimap_crop.copy() if raw_minimap_crop is not None else None

    def get_raw_minimap(self) -> Optional[Tuple['numpy.ndarray', FrameMetadata]]:
        with self._lock:
            if self._raw_minimap_crop is None or self._metadata is None:
                return None
            return (self._raw_minimap_crop.copy(), self._metadata)
```

**Thread Safety**: All access protected by lock to prevent race conditions.

---

## Five-Sample Color Collection

### User Clicks on Image (5 Times)

**Component**: `webui/src/components/CalibrationWizard.jsx` (Lines 90-132)

**Process**:
1. User clicks on player/other player marker
2. Click coordinates transformed from display space to image space (accounting for zoom/pan)
3. Coordinates clamped to image boundaries
4. Sample stored with base64 frame data
5. Next frame loaded automatically
6. After 5 samples, calibration starts

**Code**:
```javascript
const handleFrameClick = async (e) => {
  if (step !== "collect" || samples.length >= REQUIRED_SAMPLES) return;
  if (didDragRef.current) {
    didDragRef.current = false;
    return;
  }

  const rect = containerRef.current.getBoundingClientRect();
  const displayX = e.clientX - rect.left;
  const displayY = e.clientY - rect.top;

  // Convert screen point → image space (account for pan + zoom)
  const x = Math.round((displayX - pan.x) / zoom);
  const y = Math.round((displayY - pan.y) / zoom);

  const clampedX = Math.max(0, Math.min(naturalSize.width - 1, x));
  const clampedY = Math.max(0, Math.min(naturalSize.height - 1, y));

  // Add sample
  const newSample = {
    frame: currentFrame.split(',')[1], // Remove data:image/png;base64, prefix
    x: clampedX,
    y: clampedY,
    timestamp: Date.now()
  };

  const newSamples = [...samples, newSample];
  setSamples(newSamples);

  // Load next frame if more samples needed
  if (newSamples.length < REQUIRED_SAMPLES) {
    await loadFrame();
  } else {
    // All samples collected, perform calibration
    await performCalibration(newSamples);
  }
};
```

**Coordinate Transformation**:
- Accounts for pan (image translation)
- Accounts for zoom (image scaling)
- Formula: `imageX = (displayX - pan.x) / zoom`

---

### Sending Samples to Backend

**Component**: `webui/src/components/CalibrationWizard.jsx` (Lines 135-162)

**API Call**:
```javascript
const performCalibration = async (sampleList) => {
  setLoading(true);
  setError(null);
  try {
    const response = await fetch('/api/cv/object-detection/calibrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        color_type: colorType,  // "player" or "other_player"
        samples: sampleList
      })
    });

    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || "Calibration failed");
    }

    setCalibrationResult(result);
    setStep("preview");
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
};
```

**POST Body Format**:
```json
{
  "color_type": "player",
  "samples": [
    {"frame": "iVBORw0KGgo...", "x": 170, "y": 43, "timestamp": 1699564800123},
    {"frame": "iVBORw0KGgo...", "x": 172, "y": 44, "timestamp": 1699564801456},
    {"frame": "iVBORw0KGgo...", "x": 168, "y": 42, "timestamp": 1699564802789},
    {"frame": "iVBORw0KGgo...", "x": 171, "y": 43, "timestamp": 1699564804012},
    {"frame": "iVBORw0KGgo...", "x": 169, "y": 44, "timestamp": 1699564805345}
  ]
}
```

---

## HSV Calculation Algorithm

### Backend Processing

**Endpoint**: `POST /api/cv/object-detection/calibrate`
**Handler**: `msmacro/daemon_handlers/cv_commands.py` (Lines 514-611)

**Algorithm Steps**:

#### Step 1: Decode Frames and Sample 3x3 Regions
```python
async def object_detection_calibrate(self, msg: Dict[str, Any]) -> Dict[str, Any]:
    color_type = msg.get("color_type", "player")
    samples = msg.get("samples", [])

    if not samples or len(samples) < 1:
        return {"success": False, "error": "No samples provided"}

    hsv_samples = []

    # Process each sample
    for sample in samples:
        frame_b64 = sample.get("frame")
        x = sample.get("x")
        y = sample.get("y")

        # Decode frame (PNG → BGR)
        img_bytes = base64.b64decode(frame_b64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        frame_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        # Sample 3x3 region around click
        h, w = frame_bgr.shape[:2]
        y1 = max(0, y - 1)
        y2 = min(h, y + 2)
        x1 = max(0, x - 1)
        x2 = min(w, x + 2)

        region = frame_bgr[y1:y2, x1:x2]
        if region.size == 0:
            continue

        # Convert region to HSV and collect all pixels
        hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        hsv_samples.extend(hsv_region.reshape(-1, 3))
```

**Why 3x3 Region?**
- Provides 9 pixels per click (up to 45 pixels total from 5 clicks)
- Handles minor click inaccuracies
- Captures slight color variations in target area

#### Step 2: Calculate Percentile-Based Ranges
```python
    # Calculate percentile ranges (5th to 95th percentile)
    hsv_array = np.array(hsv_samples)
    hsv_min = np.percentile(hsv_array, 5, axis=0)
    hsv_max = np.percentile(hsv_array, 95, axis=0)

    # Add 20% margin for robustness
    margin = (hsv_max - hsv_min) * 0.2
    hsv_lower = np.maximum(hsv_min - margin, [0, 0, 0])
    hsv_upper = np.minimum(hsv_max + margin, [179, 255, 255])
```

**Why Percentiles?**
- Robust to outliers (ignores extreme 5% on each end)
- Better than min/max which are sensitive to single bad pixels
- 20% margin provides tolerance for lighting variations

**Example Calculation**:
```
Collected HSV values for H channel: [18, 19, 20, 21, 22, 23, 24, 25, 26, 27, ...]
5th percentile: 19
95th percentile: 26
Range: 26 - 19 = 7
Margin: 7 * 0.2 = 1.4
Final: [19 - 1.4, 26 + 1.4] = [17.6, 27.4] → [18, 27] (rounded, clamped)
```

#### Step 3: Generate Preview Mask
```python
    # Generate preview mask using latest frame
    preview_b64 = samples[-1].get("frame")
    img_bytes = base64.b64decode(preview_b64)
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    preview_frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    # Apply calculated HSV range to create mask
    hsv_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv_frame,
                      hsv_lower.astype(np.uint8),
                      hsv_upper.astype(np.uint8))

    # Encode mask as PNG
    _, mask_png = cv2.imencode('.png', mask)
    mask_b64 = base64.b64encode(mask_png.tobytes()).decode('ascii')
```

**Preview Mask**: Shows which pixels in the last frame match the calculated HSV range (white = match, black = no match).

#### Step 4: Return Results
```python
    return {
        "success": True,
        "color_type": color_type,
        "hsv_lower": hsv_lower.astype(int).tolist(),
        "hsv_upper": hsv_upper.astype(int).tolist(),
        "preview_mask": mask_b64,
        "sample_count": len(samples),
        "pixel_count": len(hsv_samples)
    }
```

**Response Example**:
```json
{
  "success": true,
  "color_type": "player",
  "hsv_lower": [18, 75, 95],
  "hsv_upper": [35, 255, 255],
  "preview_mask": "iVBORw0KGgoAAAANSUhEUgAA...",
  "sample_count": 5,
  "pixel_count": 45
}
```

---

## Configuration Storage and Usage

### Applying Calibration

**Component**: `webui/src/components/CalibrationWizard.jsx` (Lines 165-207)

**Process**:
```javascript
const applyCalibration = async () => {
  setLoading(true);
  setError(null);
  try {
    let config;
    if (colorType === "player") {
      config = {
        player_hsv_lower: calibrationResult.hsv_lower,
        player_hsv_upper: calibrationResult.hsv_upper,
      };
    } else {
      config = {
        other_player_hsv_ranges: [
          [calibrationResult.hsv_lower, calibrationResult.hsv_upper],
        ],
      };
    }

    const response = await fetch('/api/cv/object-detection/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config })
    });

    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || "Failed to apply config");
    }

    setStep("apply");
    onComplete(calibrationResult);
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
};
```

---

### Config Update Handler

**Endpoint**: `POST /api/cv/object-detection/config`
**Handler**: `msmacro/daemon_handlers/cv_commands.py` (Lines 389-420)

**Process**:
1. Receives new config
2. Stops detection if running
3. Updates detector config
4. Restarts detection
5. Emits update event

**Code**:
```python
async def object_detection_config(self, msg: Dict[str, Any]) -> Dict[str, Any]:
    capture = get_capture_instance()
    config = msg.get("config")

    if not config:
        return {"success": False, "error": "No config provided"}

    # Restart detection with new config
    was_enabled = capture._object_detection_enabled
    if was_enabled:
        capture.disable_object_detection()

    capture.enable_object_detection(config)

    try:
        from ...events import emit
        emit("OBJECT_DETECTION_CONFIG_UPDATED", {
            "config": config,
            "timestamp": time.time()
        })
    except Exception:
        pass

    logger.info(f"Object detection config updated: {config.keys()}")
    return {"success": True}
```

---

### Persistent Storage

**Endpoint**: `POST /api/cv/object-detection/config/save`
**Handler**: `msmacro/daemon_handlers/cv_commands.py` (Lines 422-451)

**Config File**: `~/.local/share/msmacro/object_detection_config.json`

**Save Function**: `msmacro/cv/detection_config.py` (Lines 62-111)

**Format**:
```json
{
  "enabled": true,
  "player": {
    "color_range": {
      "hsv_lower": [18, 75, 95],
      "hsv_upper": [35, 255, 255]
    },
    "blob_size_min": 3,
    "blob_size_max": 15,
    "circularity_min": 0.6
  },
  "other_players": {
    "color_ranges": [
      {
        "hsv_lower": [0, 100, 100],
        "hsv_upper": [10, 255, 255]
      },
      {
        "hsv_lower": [170, 100, 100],
        "hsv_upper": [179, 255, 255]
      }
    ],
    "circularity_min": 0.4
  },
  "temporal_smoothing": true,
  "smoothing_alpha": 0.3,
  "metadata": {
    "calibration_source": "wizard",
    "calibration_timestamp": "2025-11-09T12:34:56Z",
    "color_type": "player",
    "sample_count": 5
  }
}
```

---

### Config Loading Priority

**File**: `msmacro/cv/detection_config.py` (Lines 32-60)

**Priority Chain**:
1. **Runtime config** (passed to `enable_object_detection()`)
2. **Config file** (`~/.local/share/msmacro/object_detection_config.json`)
3. **Environment variables** (`MSMACRO_PLAYER_COLOR_LOWER`, etc.)
4. **Defaults** (placeholder HSV ranges)

**Load Function**:
```python
def load_config() -> DetectorConfig:
    config_dict = {}

    # 1. Try loading from config file
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path) as f:
            file_config = json.load(f)
            config_dict = _flatten_config(file_config)

    # 2. Override with environment variables
    env_config = _load_from_env()
    config_dict.update(env_config)

    # 3. Apply defaults for missing values
    defaults = _get_defaults()
    for key, value in defaults.items():
        if key not in config_dict:
            config_dict[key] = value

    # 4. Create DetectorConfig instance
    return _dict_to_config(config_dict)
```

---

### Usage in Object Detection

**File**: `msmacro/cv/object_detection.py` (Lines 267-323)

**Player Detection**:
```python
def _detect_player(self, frame: np.ndarray) -> PlayerPosition:
    # Create color mask using calibrated HSV values
    mask = self._create_color_mask(
        frame,
        self.config.player_hsv_lower,  # From calibration
        self.config.player_hsv_upper   # From calibration
    )

    # Find circular blobs in mask
    blobs = self._find_circular_blobs(
        mask,
        self.config.min_blob_size,
        self.config.max_blob_size,
        self.config.min_circularity
    )

    # Select best blob (largest + most circular)
    if blobs:
        best_blob = max(blobs, key=lambda b: b['circularity'] * b['area'])
        return PlayerPosition(
            detected=True,
            x=int(best_blob['center'][0]),
            y=int(best_blob['center'][1]),
            confidence=best_blob['circularity']
        )

    return PlayerPosition(detected=False)
```

**Color Mask Creation**: `msmacro/cv/object_detection.py` (Lines 173-201)
```python
def _create_color_mask(self,
                      frame: np.ndarray,
                      hsv_lower: Tuple[int, int, int],
                      hsv_upper: Tuple[int, int, int]) -> np.ndarray:
    # Convert BGR to HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Apply calibrated range
    lower = np.array(hsv_lower, dtype=np.uint8)
    upper = np.array(hsv_upper, dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)

    return mask
```

---

## Current Issues

### Issue 1: Image Display Not Auto-Sizing

**Severity**: Medium (UI/UX issue, does not affect functionality)

**Location**: `webui/src/components/CalibrationWizard.jsx` (Lines 336-338)

**Problem**:
- Image displays at native pixel size (e.g., 340x86 pixels)
- Does not scale to fill parent container
- On large screens, image appears tiny
- On small screens, image may overflow

**Current Code**:
```javascript
style={{
  width: naturalSize.width,      // e.g., 340 (pixels)
  height: naturalSize.height,    // e.g., 86 (pixels)
  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
  transformOrigin: "top left",
  userSelect: "none",
}}
```

**Impact**:
- Poor user experience on non-standard displays
- Hard to see details on small images
- Inconsistent sizing across devices

**Recommended Fix**:
```javascript
style={{
  width: "100%",
  height: "auto",
  maxWidth: `${naturalSize.width}px`,
  maxHeight: `${naturalSize.height}px`,
  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
  transformOrigin: "top left",
  userSelect: "none",
}}
```

---

**📋 STATUS UPDATE (Nov 9, 2025)**: Despite the known issues below, a successful production-ready calibration was completed on Nov 9, 2025, achieving 100% detection rate on 20-sample validation dataset. The calibration results have been manually documented and integrated into the codebase defaults. See `FINAL_CALIBRATION_RESULTS_2025-11-09.md` for details.

The issues below remain open but did not prevent successful calibration in practice.

---

### Issue 2: Calibration Not Auto-Saved to Disk

**Severity**: HIGH (data loss on daemon restart)
**Status as of Nov 9**: ⚠️ UNVERIFIED - Nov 9 calibration was manually saved/integrated into code defaults

**Location**: `webui/src/components/CalibrationWizard.jsx` (After line 194)

**Problem**:
- User completes calibration
- Config applied to running detector (in-memory)
- Config NOT automatically saved to disk
- On daemon restart, calibration is lost
- User must recalibrate

**Current Code**:
```javascript
const response = await fetch('/api/cv/object-detection/config', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ config })
});

const result = await response.json();
// Config applied but NOT saved to disk!

setStep("apply");
```

**Impact**:
- User frustration (lost work)
- Production deployment issue (config resets)
- Calibration process must be repeated

**Recommended Fix**:
```javascript
const result = await response.json();
if (!result.success) {
  throw new Error(result.error || "Failed to apply config");
}

// Auto-save config to disk for persistence
const saveResponse = await fetch('/api/cv/object-detection/config/save', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    metadata: {
      calibration_source: "wizard",
      calibration_timestamp: new Date().toISOString(),
      color_type: colorType,
      sample_count: samples.length
    }
  })
});

const saveResult = await saveResponse.json();
if (!saveResult.success) {
  console.warn("Config applied but not saved to disk:", saveResult.error);
  // Still proceed - config is active for current session
}

setStep("apply");
```

---

## Recommendations

### Priority 1: CRITICAL

#### 1. Auto-Save Calibration
**Importance**: HIGH
**Effort**: Low (5 lines of code)
**Impact**: Prevents data loss on restart

**Implementation**: See Issue 2 fix above

---

#### 2. Fix Image Auto-Sizing
**Importance**: MEDIUM
**Effort**: Low (2 lines of code)
**Impact**: Better UX across all devices

**Implementation**: See Issue 1 fix above

---

### Priority 2: ENHANCEMENTS

#### 1. Add Sample Quality Feedback
**Importance**: MEDIUM
**Effort**: Medium

**Features**:
- Show HSV values of each sample
- Display variance/standard deviation
- Warn if samples are too different
- Visual indicator of sample quality

**Benefits**:
- User knows if samples are good
- Early detection of calibration issues
- Better final results

---

#### 2. Improve Preview Visualization
**Importance**: MEDIUM
**Effort**: Medium

**Features**:
- Overlay mask on original image (semi-transparent)
- Show detected blobs with bounding boxes
- Side-by-side comparison view
- Adjustable transparency slider

**Benefits**:
- Clearer understanding of what will be detected
- Easier to spot issues before applying
- Better confidence in calibration

---

#### 3. Add Calibration History
**Importance**: LOW
**Effort**: High

**Features**:
- Store last 10 calibrations with timestamps
- Show success metrics for each
- Allow rollback to previous calibration
- Export/import calibration profiles

**Benefits**:
- Easy rollback if new calibration is worse
- Shareable calibration profiles
- Experiment tracking

---

#### 4. Add Detection Test Mode
**Importance**: MEDIUM
**Effort**: Medium

**Features**:
- Test detection on multiple frames before applying
- Show success rate (X% of frames detected)
- Live preview with detection overlays
- "Test for 30 seconds" button

**Benefits**:
- Validate calibration before committing
- Catch edge cases
- More confidence in results

---

## Code References

### Frontend Components

**CalibrationWizard.jsx** (456 lines total)
- Lines 1-34: Component setup, state management
- Lines 36-80: `loadFrame()` - Fetch raw minimap
- Lines 82-89: `startCollection()` - Begin wizard
- Lines 91-132: `handleFrameClick()` - Sample collection
- Lines 134-162: `performCalibration()` - Send to backend
- Lines 164-207: `applyCalibration()` - Apply config
- Lines 209-250: Rendering logic
- Lines 252-315: Preview step UI
- Lines 317-370: Collection step UI (IMAGE SIZING ISSUE HERE)
- Lines 372-428: Intro step UI

**Key Methods**:
- `loadFrame()`: Fetches `/api/cv/raw-minimap`
- `handleFrameClick()`: Transforms coordinates, adds sample
- `performCalibration()`: POSTs to `/api/cv/object-detection/calibrate`
- `applyCalibration()`: POSTs to `/api/cv/object-detection/config` (MISSING AUTO-SAVE)

---

### Backend API Handlers

**handlers.py**
- Lines 1122-1191: `api_cv_raw_minimap()` - Serve lossless PNG
- Lines 1314-1342: `api_object_detection_calibrate()` - Calibration endpoint
- Lines 958-983: `api_object_detection_config()` - Apply config
- Lines 986-1009: `api_object_detection_config_save()` - Persist config

---

### Daemon IPC Handlers

**cv_commands.py**
- Lines 140-260: `cv_get_raw_minimap()` - Retrieve raw crop with auto-wait
- Lines 514-611: `object_detection_calibrate()` - HSV calculation algorithm
- Lines 389-420: `object_detection_config()` - Update detector config
- Lines 422-451: `object_detection_config_save()` - Save to JSON file

---

### CV System Core

**capture.py**
- Lines 454-498: Map config loading and region setup
- Lines 494-512: Raw minimap extraction (BEFORE JPEG)
- Lines 633-654: `get_raw_minimap()` method
- Lines 745-807: `enable_object_detection()` - Load config

**frame_buffer.py**
- Lines 39-45: Raw minimap storage field
- Lines 47-95: `update()` - Store raw minimap
- Lines 111-122: `get_raw_minimap()` - Retrieve raw crop

**detection_config.py**
- Lines 32-60: `load_config()` - Priority chain loading
- Lines 62-111: `save_config()` - Persist to JSON
- Lines 113-145: Environment variable loading
- Lines 147-175: Default values

**object_detection.py**
- Lines 173-201: `_create_color_mask()` - Apply HSV range
- Lines 267-323: `_detect_player()` - Use calibrated values
- Lines 325-359: `_detect_other_players()` - Use calibrated ranges

---

## Testing Checklist

### Calibration Wizard Flow
- [ ] Open Object Detection tab
- [ ] Click "Calibrate Player Color"
- [ ] Wizard opens, loads first frame
- [ ] Click on yellow player dot 5 times
- [ ] Preview shows HSV ranges and mask
- [ ] Click "Apply Calibration"
- [ ] Success message shown
- [ ] Config persisted to disk (after fix)

### Data Quality Verification
- [ ] Frames are lossless PNG (no JPEG artifacts)
- [ ] Coordinate mapping is accurate (zoom/pan work)
- [ ] HSV values are reasonable (check console logs)
- [ ] Preview mask matches expected areas

### Persistence Verification
- [ ] Apply calibration
- [ ] Restart daemon
- [ ] Check `~/.local/share/msmacro/object_detection_config.json`
- [ ] Config file contains calibrated values (after fix)
- [ ] Object detection uses saved values

### Edge Cases
- [ ] Click on edge pixels (coordinates clamped correctly)
- [ ] Activate map config, immediately calibrate (auto-wait works)
- [ ] Calibrate with zoom/pan active (coordinates transformed)
- [ ] Cancel wizard mid-flow (no errors)

---

## Performance Metrics

### Memory Footprint
- **Raw minimap storage**: ~88KB (340x86x3 bytes)
- **Base64 transport**: ~120KB (PNG encoded)
- **Per sample storage**: ~125KB × 5 = 625KB during calibration
- **Total overhead**: Negligible on modern systems

### Network Traffic
- **Frame fetch**: ~80-120KB per frame (PNG)
- **Calibration POST**: ~625KB (5 samples)
- **Response**: ~10KB (HSV values + preview mask)
- **Total for calibration**: ~1.4MB

### Processing Time
- **HSV calculation**: < 50ms (45 pixels, simple percentile)
- **Preview mask generation**: < 100ms (340x86 image)
- **Total calibration**: < 200ms server-side
- **User experience**: < 1 second end-to-end

---

## Conclusion

### What Works Exceptionally Well

1. **Data Quality**: Truly lossless calibration using raw BGR before JPEG
2. **Algorithm**: Robust percentile-based HSV calculation with margin
3. **User Experience**: Simple 5-click workflow
4. **Coordinate Mapping**: Accurate transformation accounting for zoom/pan
5. **Thread Safety**: Proper locking prevents race conditions
6. **Storage System**: Clear priority chain for config loading

### Critical Issues Requiring Immediate Fix

1. **Auto-Save Missing**: Calibration lost on daemon restart (HIGH priority)
2. **Image Sizing**: Poor responsiveness across devices (MEDIUM priority)

### Overall Assessment

The calibration system is **well-architected and functionally sound**. The core algorithm is robust, data quality is excellent, and the user workflow is intuitive. The only critical issue is the missing auto-save functionality, which can be fixed with 10 lines of code. Once fixed, the system is production-ready.

### Future Enhancements

Consider adding:
- Sample quality feedback
- Enhanced preview visualization
- Calibration history/rollback
- Detection test mode before committing

These enhancements would improve the user experience but are not required for core functionality.

---

**Document Maintained By**: msmacro development team
**Last Review**: 2025-11-09
**Next Review**: As needed for feature updates

For implementation details of the object detection algorithm itself, see `08_OBJECT_DETECTION.md`.
For API reference, see `05_API_REFERENCE.md`.
For data flow diagrams, see `09_DATA_FLOW.md`.
