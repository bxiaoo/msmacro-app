# Data Flow - Object Detection & Map Configuration

## Overview

This document describes the complete data flow for object detection and minimap configuration, from user interaction in the frontend to backend processing and back to the UI.

**Last Updated**: 2025-11-08  
**Status**: Production - Current Implementation

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Map Configuration Flow](#map-configuration-flow)
3. [Object Detection Flow](#object-detection-flow)
4. [Calibration Flow](#calibration-flow)
5. [API Endpoints Reference](#api-endpoints-reference)
6. [Frontend Components](#frontend-components)
7. [Backend Components](#backend-components)
8. [Data Structures](#data-structures)

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                      │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────┐ │
│  │ CVConfiguration │  │ ObjectDetection  │  │ Calibration│ │
│  │   Component     │  │    Component     │  │   Wizard   │ │
│  └────────┬────────┘  └────────┬─────────┘  └─────┬──────┘ │
│           │                     │                   │        │
│           └─────────────────────┴───────────────────┘        │
│                              │                               │
│                         api.js (Client)                      │
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP/REST
┌──────────────────────────────┴───────────────────────────────┐
│                     BACKEND (Python/aiohttp)                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            web/handlers.py (API Endpoints)           │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │ IPC                                │
│  ┌──────────────────────┴───────────────────────────────┐   │
│  │          daemon_handlers/cv_commands.py              │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│  ┌──────────────────────┴───────────────────────────────┐   │
│  │              cv/capture.py (CVCapture)               │   │
│  │  ┌────────────────┐      ┌────────────────────────┐ │   │
│  │  │  map_config.py │      │  object_detection.py   │ │   │
│  │  │ (MapConfigMgr) │      │ (MinimapObjectDetector)│ │   │
│  │  └────────────────┘      └────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                    │
│  ┌──────────────────────┴───────────────────────────────┐   │
│  │         cv/frame_buffer.py (FrameBuffer)             │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │  HDMI Capture Card  │
                    │   (Video Source)    │
                    └─────────────────────┘
```

---

## Map Configuration Flow

### 1. User Creates Map Configuration

**Frontend → Backend:**

```javascript
// User clicks "Create Configuration" in CVConfiguration.jsx
// Adjusts region size with +/- buttons
// Clicks "Save Configuration"

const response = await createMapConfig(
  "Henesys Mini-Map",  // name
  68,                   // tl_x (fixed)
  56,                   // tl_y (fixed)
  340,                  // width
  86                    // height
);
```

**Request:**
```http
POST /api/cv/map-configs HTTP/1.1
Content-Type: application/json

{
  "name": "Henesys Mini-Map",
  "tl_x": 68,
  "tl_y": 56,
  "width": 340,
  "height": 86
}
```

**Backend Flow:**

1. **`web/handlers.py:api_cv_map_configs_create()`**
   - Validates input (name, coordinates, size)
   - Calls daemon via IPC

2. **`daemon_handlers/cv_commands.py:map_config_save()`**
   - Gets MapConfigManager instance
   - Creates MapConfig object
   - Saves to `~/.local/share/msmacro/map_configs.json`

3. **File System:**
```json
{
  "configs": [
    {
      "name": "Henesys Mini-Map",
      "tl_x": 68,
      "tl_y": 56,
      "width": 340,
      "height": 86,
      "created_at": 1699564800.0,
      "last_used_at": 0.0,
      "is_active": false
    }
  ],
  "active_config": null
}
```

**Response:**
```json
{
  "ok": true,
  "config": {
    "name": "Henesys Mini-Map",
    "tl_x": 68,
    "tl_y": 56,
    "width": 340,
    "height": 86,
    "is_active": false
  }
}
```

### 2. User Activates Configuration

**Frontend → Backend:**

```javascript
// User checks the checkbox next to a configuration
await activateMapConfig("Henesys Mini-Map");
```

**Request:**
```http
POST /api/cv/map-configs/Henesys%20Mini-Map/activate HTTP/1.1
```

**Backend Flow:**

1. **`web/handlers.py:api_cv_map_configs_activate()`**
   - Calls daemon IPC

2. **`daemon_handlers/cv_commands.py:map_config_activate()`**
   - Gets MapConfigManager
   - Activates specified config
   - Deactivates previous active config
   - Updates JSON file
   - Calls `cv.reload_config()`

3. **`cv/capture.py:reload_config()`**
   - Loads active config from manager
   - Updates `_active_map_config` in capture loop
   - **Next frame will use new region**

4. **Capture Loop Changes:**
```python
# In _capture_loop()
with self._config_lock:
    active_config = self._active_map_config

if active_config:
    # Use user-defined coordinates (NO auto-detection)
    region_x = active_config.tl_x      # 68
    region_y = active_config.tl_y      # 56
    region_width = active_config.width  # 340
    region_height = active_config.height # 86
    
    # Draw red rectangle on full frame
    cv2.rectangle(frame, (region_x, region_y), 
                  (region_x + region_width, region_y + region_height),
                  (0, 0, 255), 2)
    
    # Extract minimap region for object detection
    minimap_frame = frame[
        region_y:region_y + region_height,
        region_x:region_x + region_width
    ]
```

### 3. Frontend Displays Live Preview

**Frontend → Backend:**

```javascript
// CVConfiguration.jsx polls for updates every 2 seconds
const url = getMiniMapPreviewURL(68, 56, 340, 86);
// url = "/api/cv/mini-map-preview?x=68&y=56&w=340&h=86&t=1699564800123"

<img src={url} alt="Minimap preview" />
```

**Request:**
```http
GET /api/cv/mini-map-preview?x=68&y=56&w=340&h=86&t=1699564800123 HTTP/1.1
```

**Backend Flow:**

1. **`web/handlers.py:api_cv_minimap_preview()`**
   - Gets latest frame from CVCapture via IPC
   - Extracts region: `frame[y:y+h, x:x+w]`
   - Encodes as JPEG
   - Returns image

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: image/jpeg

[JPEG binary data of 340x86 region]
```

---

## Object Detection Flow

### 1. User Starts Object Detection

**Frontend → Backend:**

```javascript
// ObjectDetection.jsx
await startObjectDetection();
```

**Request:**
```http
POST /api/cv/object-detection/start HTTP/1.1
Content-Type: application/json

{
  "config": null  // Use default config
}
```

**Backend Flow:**

1. **`web/handlers.py:api_object_detection_start()`**
   - Validates request
   - Calls daemon IPC

2. **`daemon_handlers/cv_commands.py:object_detection_start()`**
   - Gets CVCapture instance
   - Calls `capture.enable_object_detection(config)`

3. **`cv/capture.py:enable_object_detection()`**
```python
def enable_object_detection(self, config=None):
    with self._detection_lock:
        if config:
            detector_config = DetectorConfig(**config)
        else:
            detector_config = DetectorConfig()  # Use defaults
        
        self._object_detector = MinimapObjectDetector(detector_config)
        self._object_detection_enabled = True
    
    logger.info("Object detection enabled")
```

4. **Capture Loop Integration:**
```python
# In _capture_loop(), after extracting minimap region
if self._object_detection_enabled and region_detected:
    with self._detection_lock:
        if self._object_detector:
            # Extract minimap region (340x86)
            minimap_frame = frame[
                region_y:region_y + region_height,
                region_x:region_x + region_width
            ]
            
            # Run detection (coordinates relative to minimap)
            detection_result = self._object_detector.detect(minimap_frame)
            self._last_detection_result = detection_result
            
            # Emit SSE event
            emit("OBJECT_DETECTED", detection_result.to_dict())
```

### 2. Detection Processing

**Object Detector Flow:**

```python
# cv/object_detection.py:MinimapObjectDetector.detect()
def detect(self, frame):  # frame is 340x86 minimap region
    # Convert BGR → HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Create color mask for player (yellow)
    mask_player = cv2.inRange(hsv, player_hsv_lower, player_hsv_upper)
    
    # Find circular blobs
    blobs = self._find_circular_blobs(mask_player, ...)
    
    if blobs:
        # Get centroid (relative to minimap 0,0)
        player_x = blobs[0]['center'][0]  # e.g., 170
        player_y = blobs[0]['center'][1]  # e.g., 43
        
        return DetectionResult(
            player=PlayerPosition(
                detected=True,
                x=170,  # Relative to minimap top-left
                y=43,   # Relative to minimap top-left
                confidence=0.85
            ),
            other_players=OtherPlayersStatus(
                detected=True,
                count=2
            ),
            timestamp=time.time()
        )
```

### 3. Frontend Polls for Results

**Frontend → Backend:**

```javascript
// ObjectDetection.jsx polls every 1 second
const data = await getObjectDetectionStatus();
```

**Request:**
```http
GET /api/cv/object-detection/status HTTP/1.1
```

**Backend Flow:**

1. **`web/handlers.py:api_object_detection_status()`**
   - Calls daemon IPC

2. **`daemon_handlers/cv_commands.py:object_detection_status()`**
```python
async def object_detection_status(self, msg):
    capture = get_capture_instance()
    
    return {
        "enabled": capture._object_detection_enabled,
        "last_result": capture.get_last_detection_result()
    }
```

**Response:**
```json
{
  "enabled": true,
  "last_result": {
    "player": {
      "detected": true,
      "x": 170,
      "y": 43,
      "confidence": 0.85
    },
    "other_players": {
      "detected": true,
      "count": 2
    },
    "timestamp": 1699564800.123
  }
}
```

### 4. Frontend Displays Results

```javascript
// ObjectDetection.jsx
if (lastResult?.player?.detected) {
  return (
    <div>
      Player Position: ({lastResult.player.x}, {lastResult.player.y})
      Confidence: {(lastResult.player.confidence * 100).toFixed(0)}%
    </div>
  );
}
```

---

## Calibration Flow

### 1. User Opens Calibration Wizard

**Frontend:**

```javascript
// CalibrationWizard.jsx
// User clicks "Calibrate Player Color"
setColorType("player");
setStep("collect");
await loadFrame();
```

### 2. Load Truly Lossless Frame

**Frontend → Backend:**

```javascript
// NEW 2025-11-08: Use raw-minimap endpoint for truly lossless calibration
// This eliminates JPEG compression artifacts entirely
const response = await fetch(`/api/cv/raw-minimap?t=${Date.now()}`);
const blob = await response.blob();
const dataUrl = URL.createObjectURL(blob);
```

**Request:**
```http
GET /api/cv/raw-minimap?t=1699564800123 HTTP/1.1
```

**Backend Flow:**

1. **`web/handlers.py:api_cv_raw_minimap()`**
   - Calls daemon IPC: `cv_get_raw_minimap`

2. **`daemon_handlers/cv_commands.py:cv_get_raw_minimap()`**
```python
async def cv_get_raw_minimap(self, msg):
    # Get raw minimap from capture
    capture = get_capture_instance()
    minimap_result = capture.get_raw_minimap()

    if minimap_result is None:
        raise RuntimeError("No raw minimap available")

    raw_crop, metadata = minimap_result

    # Encode raw crop as PNG (never went through JPEG!)
    ret, png_data = cv2.imencode('.png', raw_crop)

    return {
        "minimap": base64.b64encode(png_data.tobytes()).decode('ascii'),
        "format": "png",
        "metadata": asdict(metadata)
    }
```

3. **`cv/capture.py:get_raw_minimap()`**
```python
def get_raw_minimap(self):
    # Returns raw BGR minimap crop that was extracted BEFORE JPEG encoding
    # This crop was saved during _capture_loop() before any compression
    return self.frame_buffer.get_raw_minimap()
```

4. **`cv/frame_buffer.py`**
```python
# Raw minimap is stored separately (~88KB for 340x86)
# Captured in _capture_loop BEFORE JPEG encoding:
if region_detected:
    raw_minimap_crop = frame[
        region_y:region_y + region_height,
        region_x:region_x + region_width
    ].copy()  # Copy before full frame is JPEG-encoded

self.frame_buffer.update(
    jpeg_bytes,  # Full frame as JPEG
    ...,
    raw_minimap_crop=raw_minimap_crop  # Raw minimap (no JPEG)
)
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: image/png
X-Minimap-X: 68
X-Minimap-Y: 56
X-Minimap-Width: 340
X-Minimap-Height: 86
X-Minimap-Checksum: a3f2b8c9d1e4f5a6b7c8d9e0f1a2b3c4
X-Minimap-Source: raw

[PNG binary data - 340x86 TRULY lossless, NO JPEG artifacts]
```

**Key Improvement**: Previous `/api/cv/frame-lossless` decoded a JPEG first, so compression artifacts remained. The new `/api/cv/raw-minimap` provides the raw pixels before any JPEG encoding, ensuring perfect color accuracy for calibration.

### 3. User Clicks on Player

**Frontend:**

```javascript
// CalibrationWizard.jsx
const handleFrameClick = (e) => {
  const rect = e.target.getBoundingClientRect();
  const x = Math.round((e.clientX - rect.left) / zoom);
  const y = Math.round((e.clientY - rect.top) / zoom);
  
  // x,y are relative to minimap (0,0 at top-left)
  const sample = {
    frame: currentFrame.split(',')[1], // base64 PNG
    x: x,  // e.g., 170
    y: y   // e.g., 43
  };
  
  setSamples([...samples, sample]);
};
```

### 4. Auto-Calibrate HSV Ranges

**Frontend → Backend:**

After 5 samples collected:

```javascript
const response = await fetch('/api/cv/object-detection/calibrate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    color_type: "player",
    samples: [
      { frame: "iVBORw0K...", x: 170, y: 43 },
      { frame: "iVBORw0K...", x: 165, y: 50 },
      { frame: "iVBORw0K...", x: 180, y: 40 },
      { frame: "iVBORw0K...", x: 172, y: 45 },
      { frame: "iVBORw0K...", x: 168, y: 42 }
    ]
  })
});
```

**Backend Flow:**

1. **`web/handlers.py:api_object_detection_calibrate()`**
   - Forwards to daemon IPC

2. **`daemon_handlers/cv_commands.py:object_detection_calibrate()`**
```python
async def object_detection_calibrate(self, msg):
    color_type = msg.get("color_type", "player")
    samples = msg.get("samples", [])
    
    hsv_samples = []
    
    # Process each sample
    for sample in samples:
        frame_b64 = sample.get("frame")
        x = sample.get("x")  # Relative to minimap
        y = sample.get("y")  # Relative to minimap
        
        # Decode PNG minimap frame
        img_bytes = base64.b64decode(frame_b64)
        frame_bgr = cv2.imdecode(
            np.frombuffer(img_bytes, np.uint8),
            cv2.IMREAD_COLOR
        )
        
        # Sample 3x3 region around click
        region = frame_bgr[y-1:y+2, x-1:x+2]
        hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        hsv_samples.extend(hsv_region.reshape(-1, 3))
    
    # Calculate percentile ranges
    hsv_array = np.array(hsv_samples)
    hsv_min = np.percentile(hsv_array, 5, axis=0)
    hsv_max = np.percentile(hsv_array, 95, axis=0)
    
    # Add 20% margin
    margin = (hsv_max - hsv_min) * 0.2
    hsv_lower = np.maximum(hsv_min - margin, [0, 0, 0])
    hsv_upper = np.minimum(hsv_max + margin, [179, 255, 255])
    
    # Generate preview mask
    preview_frame = decode_last_sample()
    hsv_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv_frame, hsv_lower.astype(np.uint8), 
                       hsv_upper.astype(np.uint8))
    
    _, mask_png = cv2.imencode('.png', mask)
    mask_b64 = base64.b64encode(mask_png.tobytes()).decode('ascii')
    
    return {
        "success": True,
        "color_type": color_type,
        "hsv_lower": hsv_lower.astype(int).tolist(),
        "hsv_upper": hsv_upper.astype(int).tolist(),
        "preview_mask": mask_b64
    }
```

**Response:**
```json
{
  "success": true,
  "color_type": "player",
  "hsv_lower": [18, 75, 95],
  "hsv_upper": [35, 255, 255],
  "preview_mask": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

### 5. User Validates and Applies

**Frontend:**

```javascript
// CalibrationWizard.jsx displays preview mask overlay
// User clicks "Apply" if satisfied
await updateObjectDetectionConfig({
  player_hsv_lower: [18, 75, 95],
  player_hsv_upper: [35, 255, 255]
});
```

---

## API Endpoints Reference

### Map Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cv/map-configs` | List all saved configs |
| POST | `/api/cv/map-configs` | Create new config |
| DELETE | `/api/cv/map-configs/{name}` | Delete config |
| POST | `/api/cv/map-configs/{name}/activate` | Activate config |
| GET | `/api/cv/map-configs/active` | Get active config |
| POST | `/api/cv/map-configs/deactivate` | Deactivate current |

### CV Capture

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cv/status` | Get capture status |
| GET | `/api/cv/screenshot` | Get latest full frame (JPEG) |
| GET | `/api/cv/mini-map-preview` | Get minimap region (JPEG) |
| GET | `/api/cv/frame-lossless` | Get minimap region (PNG) |
| POST | `/api/cv/start` | Start capture |
| POST | `/api/cv/stop` | Stop capture |

### Object Detection

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cv/object-detection/status` | Get detection status & results |
| POST | `/api/cv/object-detection/start` | Enable detection |
| POST | `/api/cv/object-detection/stop` | Disable detection |
| POST | `/api/cv/object-detection/config` | Update config |
| POST | `/api/cv/object-detection/config/save` | Save config to disk |
| GET | `/api/cv/object-detection/config/export` | Export config JSON |
| GET | `/api/cv/object-detection/performance` | Get performance stats |
| POST | `/api/cv/object-detection/calibrate` | Auto-calibrate colors |

---

## Frontend Components

### CVConfiguration.jsx

**Responsibilities:**
- Map config CRUD operations
- Live minimap preview
- Coordinate adjustment UI
- Config activation/deactivation

**Key State:**
```javascript
{
  mapConfigs: [],              // All saved configs
  activeConfig: null,          // Currently active config
  isCreating: false,           // Create mode
  coords: { tl_x, tl_y, width, height },
  miniMapPreviewUrl: "/api/cv/mini-map-preview?..."
}
```

**API Calls:**
- `listMapConfigs()` - Poll every 2s when active
- `createMapConfig()` - On save
- `activateMapConfig()` - On checkbox change
- `deleteMapConfig()` - On delete button
- `getMiniMapPreviewURL()` - For live preview

### ObjectDetection.jsx

**Responsibilities:**
- Start/stop detection
- Display detection results
- Show live position
- Performance metrics

**Key State:**
```javascript
{
  enabled: false,
  lastResult: {
    player: { detected, x, y, confidence },
    other_players: { detected, count }
  }
}
```

**API Calls:**
- `getObjectDetectionStatus()` - Poll every 1s
- `startObjectDetection()` - On toggle
- `stopObjectDetection()` - On toggle

### CalibrationWizard.jsx

**Responsibilities:**
- HSV color calibration
- Sample collection (click 5 times)
- Preview mask validation
- Config export

**Key State:**
```javascript
{
  step: "intro" | "collect" | "preview",
  samples: [],  // Collected samples
  calibrationResult: { hsv_lower, hsv_upper, preview_mask }
}
```

**API Calls:**
- `fetch('/api/cv/frame-lossless')` - Load frames
- `fetch('/api/cv/object-detection/calibrate')` - Auto-calibrate

---

## Backend Components

### web/handlers.py

**Responsibilities:**
- HTTP request handling
- Input validation
- Response formatting
- IPC delegation

**Key Functions:**
- `api_cv_map_configs_*()` - Map config endpoints
- `api_object_detection_*()` - Detection endpoints
- `api_cv_frame_lossless()` - Calibration frame endpoint

### daemon_handlers/cv_commands.py

**Responsibilities:**
- IPC command handling
- Business logic coordination
- CVCapture interaction
- Config management

**Key Functions:**
- `map_config_*()` - Map config operations
- `object_detection_*()` - Detection operations
- `object_detection_calibrate()` - Auto-calibration logic

### cv/capture.py (CVCapture)

**Responsibilities:**
- Video capture loop
- Frame processing
- Region extraction
- Object detection integration
- Frame buffering

**Key Methods:**
- `_capture_loop()` - Main capture thread
- `reload_config()` - Reload map config
- `enable_object_detection()` - Start detection
- `get_latest_frame()` - Get frame with metadata

### cv/object_detection.py (MinimapObjectDetector)

**Responsibilities:**
- Color-based blob detection
- Player position extraction
- Other players detection
- Temporal smoothing

**Key Methods:**
- `detect()` - Main detection function
- `_detect_player()` - Yellow blob detection
- `_detect_other_players()` - Red blob detection
- `_find_circular_blobs()` - Blob filtering

### cv/map_config.py (MapConfigManager)

**Responsibilities:**
- Config persistence (JSON file)
- CRUD operations
- Active config tracking
- Thread-safe access

**Key Methods:**
- `save_config()` - Create/update config
- `activate_config()` - Set active
- `get_active_config()` - Get current active
- `list_configs()` - List all

---

## Data Structures

### MapConfig

```python
@dataclass
class MapConfig:
    name: str
    tl_x: int                 # Top-left X (fixed at 68)
    tl_y: int                 # Top-left Y (fixed at 56)
    width: int                # Region width (adjustable)
    height: int               # Region height (adjustable)
    created_at: float         # Unix timestamp
    last_used_at: float = 0.0
    is_active: bool = False
```

### DetectionResult

```python
@dataclass
class DetectionResult:
    player: PlayerPosition
    other_players: OtherPlayersStatus
    timestamp: float

@dataclass
class PlayerPosition:
    detected: bool
    x: int = 0  # Relative to minimap top-left
    y: int = 0  # Relative to minimap top-left
    confidence: float = 0.0

@dataclass
class OtherPlayersStatus:
    detected: bool
    count: int = 0
    positions: List[Tuple[int, int]] = []  # NEW 2025-11-08: [(x, y), ...] for visualization
```

### FrameMetadata

```python
@dataclass
class FrameMetadata:
    timestamp: float
    width: int
    height: int
    size_bytes: int
    region_detected: bool = False
    region_x: int = 0
    region_y: int = 0
    region_width: int = 0
    region_height: int = 0
```

---

## Key Insights

### Coordinate Systems

**Full Screen Coordinates:**
- Origin (0, 0) at top-left of 1280x720 frame
- Used for map config definition (tl_x=68, tl_y=56)

**Minimap Coordinates:**
- Origin (0, 0) at top-left of minimap region
- Used for object detection results
- Example: Player at (170, 43) means 170px right, 43px down from minimap top-left

**Conversion:**
```python
# Minimap to full screen
full_x = map_config.tl_x + minimap_x  # 68 + 170 = 238
full_y = map_config.tl_y + minimap_y  # 56 + 43 = 99
```

### Performance Optimizations

1. **Minimap Extraction First:** Crop before any processing
2. **Frame Polling:** 2 FPS for capture (500ms intervals)
3. **Detection Intervals:** Runs every frame (500ms)
4. **Frontend Polling:** 2s for previews, 1s for detection status

### Error Handling

- **404:** No active map config (required for calibration)
- **500:** Internal errors (device failure, IPC timeout)
- **Validation:** Input validation at API layer
- **Fallbacks:** Graceful degradation if detection fails

---

**Related Documents:**
- `06_MAP_CONFIGURATION.md` - Map config user guide
- `08_OBJECT_DETECTION.md` - Object detection implementation
- `05_API_REFERENCE.md` - API endpoints reference
- `docs/MINIMAP_LOGIC_FIX.md` - Recent logic fixes
