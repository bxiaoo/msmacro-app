# API Reference

## HTTP Endpoints

**Last Updated:** 2025-11-08  
**Status:** Current Production API

### Map Configuration Endpoints

#### GET /api/cv/map-configs

List all saved map configurations.

**Request:**
```http
GET /api/cv/map-configs HTTP/1.1
```

**Response:**
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
      "last_used_at": 1699565000.0,
      "is_active": true
    }
  ]
}
```

#### POST /api/cv/map-configs

Create a new map configuration.

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

#### DELETE /api/cv/map-configs/{name}

Delete a map configuration (must be inactive).

**Request:**
```http
DELETE /api/cv/map-configs/Henesys%20Mini-Map HTTP/1.1
```

**Response:**
```json
{
  "ok": true,
  "message": "Configuration deleted"
}
```

#### POST /api/cv/map-configs/{name}/activate

Activate a map configuration.

**Request:**
```http
POST /api/cv/map-configs/Henesys%20Mini-Map/activate HTTP/1.1
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
    "is_active": true
  }
}
```

#### GET /api/cv/map-configs/active

Get the currently active configuration.

**Response:**
```json
{
  "config": {
    "name": "Henesys Mini-Map",
    "tl_x": 68,
    "tl_y": 56,
    "width": 340,
    "height": 86,
    "is_active": true
  }
}
```

#### POST /api/cv/map-configs/deactivate

Deactivate the current configuration.

**Response:**
```json
{
  "ok": true,
  "message": "Configuration deactivated"
}
```

---

### CV Capture Endpoints

### GET /api/cv/screenshot

Retrieves the latest captured frame as JPEG with region detection metadata.

#### Request

```http
GET /api/cv/screenshot HTTP/1.1
Host: localhost:8787
```

```bash
curl http://localhost:8787/api/cv/screenshot -o screenshot.jpg
```

#### Response

**Status**: 200 OK (on success), 404 (no frame), 503 (capture not running)

**Content-Type**: image/jpeg

**Response Body**: JPEG-encoded image data

#### Response Headers

**Frame Metadata Headers**:

```
X-CV-Frame-Width: 640              # Image width in pixels
X-CV-Frame-Height: 480             # Image height in pixels
X-CV-Frame-Size-Bytes: 45230       # JPEG file size in bytes
X-CV-Frame-Timestamp: 1699564800.123  # Unix timestamp
```

**Region Detection Headers** (NEW):

```
X-CV-Region-Detected: true         # "true" or "false"
X-CV-Region-X: 120                 # Left edge coordinate (pixels)
X-CV-Region-Y: 80                  # Top edge coordinate (pixels)
X-CV-Region-Width: 640             # Region width (pixels)
X-CV-Region-Height: 480            # Region height (pixels)
X-CV-Region-Confidence: 0.95        # Confidence score (0.0-1.0)
X-CV-Region-White-Ratio: 0.92      # Whiteness ratio (0.0-1.0)
```

#### Example Response

```http
HTTP/1.1 200 OK
Content-Type: image/jpeg
X-CV-Frame-Width: 640
X-CV-Frame-Height: 480
X-CV-Frame-Size-Bytes: 45230
X-CV-Frame-Timestamp: 1699564800.123
X-CV-Region-Detected: true
X-CV-Region-X: 120
X-CV-Region-Y: 80
X-CV-Region-Width: 640
X-CV-Region-Height: 480
X-CV-Region-Confidence: 0.95
X-CV-Region-White-Ratio: 0.92

[JPEG binary data...]
```

#### Usage Examples

**Python**:
```python
import requests

response = requests.get('http://localhost:8787/api/cv/screenshot')

# Check if successful
if response.status_code != 200:
    print(f"Error: {response.status_code}")
    exit(1)

# Extract frame metadata
frame_meta = {
    'width': int(response.headers['X-CV-Frame-Width']),
    'height': int(response.headers['X-CV-Frame-Height']),
    'size': int(response.headers['X-CV-Frame-Size-Bytes']),
    'timestamp': float(response.headers['X-CV-Frame-Timestamp']),
}

# Extract region metadata
region = {
    'detected': response.headers.get('X-CV-Region-Detected') == 'true',
    'x': int(response.headers.get('X-CV-Region-X', 0)),
    'y': int(response.headers.get('X-CV-Region-Y', 0)),
    'width': int(response.headers.get('X-CV-Region-Width', 0)),
    'height': int(response.headers.get('X-CV-Region-Height', 0)),
    'confidence': float(response.headers.get('X-CV-Region-Confidence', 0)),
    'white_ratio': float(response.headers.get('X-CV-Region-White-Ratio', 0)),
}

# Save image
with open('/tmp/frame.jpg', 'wb') as f:
    f.write(response.content)

print(f"Frame: {frame_meta['width']}x{frame_meta['height']}")
if region['detected']:
    print(f"Region: ({region['x']},{region['y']}) {region['width']}x{region['height']}")
    print(f"Confidence: {region['confidence']:.1%}")
```

**JavaScript**:
```javascript
async function getScreenshot() {
    const response = await fetch('/api/cv/screenshot');

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    // Extract metadata from headers
    const frameMeta = {
        width: parseInt(response.headers.get('X-CV-Frame-Width')),
        height: parseInt(response.headers.get('X-CV-Frame-Height')),
        size: parseInt(response.headers.get('X-CV-Frame-Size-Bytes')),
        timestamp: parseFloat(response.headers.get('X-CV-Frame-Timestamp')),
    };

    const region = {
        detected: response.headers.get('X-CV-Region-Detected') === 'true',
        x: parseInt(response.headers.get('X-CV-Region-X') || '0'),
        y: parseInt(response.headers.get('X-CV-Region-Y') || '0'),
        width: parseInt(response.headers.get('X-CV-Region-Width') || '0'),
        height: parseInt(response.headers.get('X-CV-Region-Height') || '0'),
        confidence: parseFloat(response.headers.get('X-CV-Region-Confidence') || '0'),
        whiteRatio: parseFloat(response.headers.get('X-CV-Region-White-Ratio') || '0'),
    };

    // Get image blob
    const blob = await response.blob();
    const imageUrl = URL.createObjectURL(blob);

    return { imageUrl, frameMeta, region };
}
```

**cURL**:
```bash
# Get screenshot with all headers
curl -i http://localhost:8787/api/cv/screenshot

# Save to file
curl http://localhost:8787/api/cv/screenshot -o screenshot.jpg

# Show only region headers
curl -s -i http://localhost:8787/api/cv/screenshot | grep "X-CV-Region"
```

#### GET /api/cv/mini-map-preview

Get minimap region preview (PNG, raw by default).

2025-11 Update:
- Default: raw crop, no overlays, PNG (prevents quality loss in calibration)
- Optional: `overlay=border` draws legacy red 2px border for older UI components

**Query Parameters:**
- `x`: Region left coordinate
- `y`: Region top coordinate  
- `w`: Region width
- `h`: Region height
- `overlay`: (optional) `border` to draw red border (else omitted)
- `t`: Cache-busting timestamp

**Request:**
```http
GET /api/cv/mini-map-preview?x=68&y=56&w=340&h=86&overlay=border&t=1699564800123 HTTP/1.1
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: image/png
X-MiniMap-X: 68
X-MiniMap-Y: 56
X-MiniMap-Width: 340
X-MiniMap-Height: 86
X-MiniMap-Overlay: border

[PNG binary data]
```

#### GET /api/cv/frame-lossless

Get minimap region as PNG for calibration & overlays.

2025-11 Improvements:
- Accepts manual crop params (x,y,w,h) even without active map config
- Returns 404 only if no active config AND no manual params
- Adds checksum header for cache validation

**Query Parameters (all optional):**
- `x`,`y`,`w`,`h`: Manual crop (override active config)
- `t`: Cache bust

**Request (active config)**:
```http
GET /api/cv/frame-lossless?t=1699564800123 HTTP/1.1
```
**Request (manual)**:
```http
GET /api/cv/frame-lossless?x=68&y=56&w=340&h=86&t=1699564800456 HTTP/1.1
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: image/png
X-Minimap-X: 68
X-Minimap-Y: 56
X-Minimap-Width: 340
X-Minimap-Height: 86
X-Minimap-Manual: true|false
X-Minimap-Checksum: d41d8cd98f00b204e9800998ecf8427e

[PNG binary data]
```

**Note**: This endpoint still starts from the JPEG stream (cv_get_frame → base64 JPEG → decode → re-encode PNG), so compression artifacts from the original JPEG remain. For truly lossless calibration, use `/api/cv/raw-minimap` instead.

---

#### GET /api/cv/raw-minimap

**NEW 2025-11-08**: Get truly lossless raw minimap (captured BEFORE JPEG compression).

This endpoint serves the raw BGR minimap crop that was extracted from the capture card BEFORE any JPEG encoding. This eliminates ALL compression artifacts, making it perfect for color calibration where accuracy is critical.

**Key Differences from /api/cv/frame-lossless:**
- `/api/cv/frame-lossless`: JPEG → decode → crop → PNG (has JPEG artifacts)
- `/api/cv/raw-minimap`: Raw BGR → crop → PNG (**no JPEG artifacts**)

**Memory Footprint**: ~88KB for typical 340x86 minimap (acceptable overhead)

**Query Parameters:**
- `t`: Cache-busting timestamp (recommended)

**Request:**
```http
GET /api/cv/raw-minimap?t=1699564800123 HTTP/1.1
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: image/png
Cache-Control: no-cache, no-store, must-revalidate
X-Minimap-X: 68
X-Minimap-Y: 56
X-Minimap-Width: 340
X-Minimap-Height: 86
X-Minimap-Checksum: a3f2b8c9d1e4f5a6b7c8d9e0f1a2b3c4
X-Minimap-Source: raw

[PNG binary data - truly lossless]
```

**Status Codes:**
- `200 OK`: Success
- `404 Not Found`: No active map config or raw minimap not available
- `500 Internal Server Error`: Capture error

**Usage Example (JavaScript):**
```javascript
// Load truly lossless frame for calibration
async function loadLosslessFrame() {
  const response = await fetch(`/api/cv/raw-minimap?t=${Date.now()}`);
  if (!response.ok) {
    throw new Error('No active map config - create one first');
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);

  // Use for color calibration - NO JPEG artifacts!
  return url;
}
```

---

#### GET /api/cv/detection-preview

**NEW 2025-11-08**: Get minimap with detection visualization overlays.

This endpoint returns a PNG image with visual overlays showing all detected objects:
- **Player**: Yellow crosshair + circle with confidence label
- **Other players**: Red circles + crosshairs at each detected position
- **Stats**: Frame count, detection confidence

Perfect for debugging detection accuracy in the web UI.

**Query Parameters:**
- `t`: Cache-busting timestamp (recommended)

**Request:**
```http
GET /api/cv/detection-preview?t=1699564800123 HTTP/1.1
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: image/png
Cache-Control: no-cache, no-store, must-revalidate
X-Minimap-X: 68
X-Minimap-Y: 56
X-Minimap-Width: 340
X-Minimap-Height: 86

[PNG binary data with visualization overlays]
```

**Status Codes:**
- `200 OK`: Success
- `404 Not Found`: Object detection not enabled or no results available
- `500 Internal Server Error`: Detection or rendering error

**Visualization Elements:**
- Player dot: Yellow crosshair (10px) + circle (8px radius) + label with coordinates & confidence
- Other player dots: Red circles (6px radius) + crosshairs (8px)
- Count label: "Other Players: N" in top-left
- Frame counter: Bottom-left

**Usage Example (React):**
```javascript
function DetectionPreview({ lastResult, enabled }) {
  const [imgUrl, setImgUrl] = useState(null);

  useEffect(() => {
    if (!enabled) return;
    // Auto-refresh when detection updates
    const url = `/api/cv/detection-preview?t=${Date.now()}`;
    setImgUrl(url);
  }, [lastResult?.timestamp, enabled]);

  return <img src={imgUrl} alt="Detection Preview" />;
}
```

---

### Object Detection Endpoints

#### GET /api/cv/object-detection/status

Get detection status and latest result.

**Request:**
```http
GET /api/cv/object-detection/status HTTP/1.1
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
      "count": 2,
      "positions": [
        {"x": 120, "y": 30},
        {"x": 200, "y": 50}
      ]
    },
    "timestamp": 1699564800.123
  }
}
```

**Note**: As of 2025-11-08, `other_players.positions` array is included for visualization and debugging. Each position contains `{x, y}` coordinates relative to minimap top-left.

#### POST /api/cv/object-detection/start

Enable object detection.

**Request:**
```http
POST /api/cv/object-detection/start HTTP/1.1
Content-Type: application/json

{
  "config": {
    "player_hsv_lower": [18, 75, 95],
    "player_hsv_upper": [35, 255, 255],
    "min_blob_size": 3,
    "max_blob_size": 15,
    "min_circularity": 0.6
  }
}
```

**Response:**
```json
{
  "success": true
}
```

#### POST /api/cv/object-detection/stop

Disable object detection.

**Response:**
```json
{
  "success": true
}
```

#### POST /api/cv/object-detection/config

Update detection configuration.

**Request:**
```http
POST /api/cv/object-detection/config HTTP/1.1
Content-Type: application/json

{
  "config": {
    "player_hsv_lower": [18, 75, 95],
    "player_hsv_upper": [35, 255, 255]
  }
}
```

**Response:**
```json
{
  "success": true
}
```

#### POST /api/cv/object-detection/calibrate

Auto-calibrate HSV ranges from user clicks.

**Request:**
```http
POST /api/cv/object-detection/calibrate HTTP/1.1
Content-Type: application/json

{
  "color_type": "player",
  "samples": [
    {
      "frame": "iVBORw0KGgo...",
      "x": 170,
      "y": 43
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "color_type": "player",
  "hsv_lower": [18, 75, 95],
  "hsv_upper": [35, 255, 255],
  "preview_mask": "iVBORw0KGgo..."
}
```

#### GET /api/cv/object-detection/performance

Get detection performance statistics.

**Response:**
```json
{
  "success": true,
  "stats": {
    "avg_ms": 12.5,
    "max_ms": 18.2,
    "min_ms": 10.1,
    "count": 1234
  }
}
```

---

### GET /api/cv/status

Retrieves current CV capture system status.

#### Request

```http
GET /api/cv/status HTTP/1.1
Host: localhost:8787
```

```bash
curl http://localhost:8787/api/cv/status
```

#### Response

**Status**: 200 OK, 500 (error)

**Content-Type**: application/json

```json
{
    "connected": true,
    "capturing": true,
    "has_frame": true,
    "frames_captured": 1234,
    "frames_failed": 2,
    "last_error": null,
    "device": {
        "path": "/dev/video0",
        "index": 0,
        "name": "HDMI Capture"
    },
    "frame": {
        "width": 1280,
        "height": 720,
        "timestamp": 1699564800.123,
        "age_seconds": 0.42,
        "size_bytes": 45230,
        "region_detected": true,
        "region_x": 120,
        "region_y": 80,
        "region_width": 640,
        "region_height": 480,
        "region_confidence": 0.95,
        "region_white_ratio": 0.92
    },
    "capture": {
        "fps": 30.0,
        "width": 1280,
        "height": 720
    }
}
```

### POST /api/cv/start

Starts the CV capture system.

#### Request

```bash
curl -X POST http://localhost:8787/api/cv/start
```

#### Response

```json
{
    "ok": true,
    "message": "Capture started"
}
```

### POST /api/cv/stop

Stops the CV capture system.

#### Request

```bash
curl -X POST http://localhost:8787/api/cv/stop
```

#### Response

```json
{
    "ok": true,
    "message": "Capture stopped"
}
```

## Function API

### `detect_top_left_white_frame()`

Detects white frame regions in top-left corner of frame.

#### Signature

```python
def detect_top_left_white_frame(
    frame: np.ndarray,
    max_region_width: int = 800,
    max_region_height: int = 600,
    threshold: int = 240,
    min_white_ratio: float = 0.85,
    edge_margin: int = 20
) -> Optional[Dict[str, Any]]:
```

#### Parameters

- `frame` (ndarray): Input frame (BGR or grayscale)
- `max_region_width` (int): Maximum search width (pixels)
- `max_region_height` (int): Maximum search height (pixels)
- `threshold` (int): White pixel threshold (0-255)
- `min_white_ratio` (float): Minimum whiteness (0.0-1.0)
- `edge_margin` (int): Margin from edges (pixels)

#### Return Value

Dict with keys (or None on error):

```python
{
    "detected": bool,           # Region detected
    "x": int,                   # Left coordinate
    "y": int,                   # Top coordinate
    "width": int,               # Region width
    "height": int,              # Region height
    "confidence": float,        # Confidence (0.0-1.0)
    "region_white_ratio": float,  # Whiteness in region
    "white_ratio": float,       # Whiteness in search area
    "white_pixels": int,        # Count of white pixels
    "total_pixels": int,        # Total pixels in search area
    "avg_brightness": float,    # Average brightness
    "threshold": int,           # Threshold used
}
```

#### Example

```python
import cv2
from msmacro.cv.region_analysis import detect_top_left_white_frame

# Load frame
frame = cv2.imread('screenshot.jpg')

# Run detection
result = detect_top_left_white_frame(
    frame,
    threshold=240,
    min_white_ratio=0.85
)

if result and result['detected']:
    print(f"Region at ({result['x']},{result['y']})")
    print(f"Size: {result['width']}x{result['height']}")
    print(f"Confidence: {result['confidence']:.1%}")

    # Crop to region
    x, y, w, h = result['x'], result['y'], result['width'], result['height']
    cropped = frame[y:y+h, x:x+w]
    cv2.imwrite('/tmp/cropped.jpg', cropped)
```

## Shared Memory Files

### /dev/shm/msmacro_cv_frame.jpg

Latest captured frame as JPEG.

- **Type**: Binary JPEG file
- **Written by**: Capture thread
- **Read by**: API handlers, other processes
- **Thread-safe**: Atomic write with rename

### /dev/shm/msmacro_cv_frame.json

Metadata for latest frame (JSON).

```json
{
    "width": 1280,
    "height": 720,
    "timestamp": 1699564800.123,
    "size_bytes": 45230,
    "region_detected": true,
    "region_x": 120,
    "region_y": 80,
    "region_width": 640,
    "region_height": 480,
    "region_confidence": 0.95,
    "region_white_ratio": 0.92
}
```

- **Type**: JSON text file
- **Written by**: Capture thread
- **Read by**: API handlers
- **Updated**: Every frame capture

## Python Module: `msmacro.cv.region_analysis`

### Exported Functions

#### `is_white_region()`

Check if region is mostly white.

```python
is_white, stats = is_white_region(
    frame,
    region,
    threshold=240,
    min_white_ratio=0.95
)

if is_white:
    print(f"White region: {stats['white_ratio']:.1%} white")
```

#### `detect_color_in_region()`

Detect specific color in region.

```python
detected, stats = detect_color_in_region(
    frame,
    region,
    color_bgr=(255, 255, 255),  # White in BGR
    tolerance=20
)
```

#### `extract_region()`

Extract rectangular region from frame.

```python
roi = extract_region(frame, region)
```

#### `visualize_region()`

Draw region box on frame.

```python
vis_frame = visualize_region(
    frame,
    region,
    color=(0, 255, 0),
    thickness=2,
    label="White Frame"
)
cv2.imshow('visualization', vis_frame)
```

### Region Class

Define rectangular regions.

```python
from msmacro.cv.region_analysis import Region

# Absolute pixels
region = Region(x=100, y=50, width=200, height=100)

# Relative (0.0-1.0)
region = Region(x=0.0, y=0.0, width=0.2, height=0.1, relative=True)

# Convert to absolute
x, y, w, h = region.to_absolute(frame_width, frame_height)
```

## Environment Variables

### CV Capture Configuration

```bash
MSMACRO_CV_DETECT_WHITE_FRAME=true|false
MSMACRO_CV_WHITE_THRESHOLD=0-255
MSMACRO_CV_WHITE_MIN_PIXELS=0+
MSMACRO_CV_WHITE_SCAN_REGION="x,y,width,height"
MSMACRO_CV_FRAME_PATH=/path/to/frame.jpg
MSMACRO_CV_META_PATH=/path/to/meta.json
```

See **03_CONFIGURATION.md** for details.

## Error Codes

### HTTP Status Codes

- **200**: Success, frame available
- **404**: No frame available (capture not running)
- **500**: Internal error (device failure, parsing error)
- **503**: Service unavailable (capture disabled, path not configured)

### Daemon Response Format

```json
{
    "ok": true,           # Success
    "error": null,        # Error message if !ok
    "message": "...",     # Status message
    "detected": true,     # For detection endpoints
    "region": {}          # Region data if applicable
}
```

---

See related documents:
- **02_USAGE.md** - Usage examples
- **06_EXAMPLES.md** - Integration code samples
