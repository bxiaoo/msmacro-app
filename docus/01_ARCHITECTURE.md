# System Architecture

## Overview

The CV region detection system extends the existing capture pipeline to automatically detect white frame regions using YUYV luminance-based detection. It provides visual feedback with overlay indicators and optionally crops frames to the detected region.

**Key Features:**
- **YUYV-based Detection**: Uses Y (luminance) channel for accurate brightness detection
- **Fixed-Point Detection**: Optimized for known UI element positions (MapleStory)
- **Visual Indicators**: Red rectangle overlay + confidence badge in preview
- **Dark Background Validation**: Reduces false positives by validating context
- **Real-time Performance**: <15ms detection overhead at 2 FPS capture rate

## Data Flow

```
Video Device (YUYV→BGR via OpenCV)
    ↓
[CVCapture._capture_loop]
    ↓
    ├─→ Raw Frame (BGR numpy array, 1280x720)
    ↓
[bgr_to_yuyv_bytes]
    ├─→ Convert BGR to YCrCb
    ├─→ Extract Y, Cr, Cb channels
    └─→ Pack into YUYV byte format: [Y0 U Y1 V]
    ↓
[detect_white_frame_yuyv]
    ├─→ Extract Y channel region (luminance)
    ├─→ Check fixed starting point (68, 56)
    ├─→ Scan borders to find variable size
    ├─→ Validate dark background (Y: 60-130)
    ├─→ Analyze border quality (white ratio)
    ├─→ Calculate confidence score
    └─→ Return: detection result dict
    ↓
[Visual Overlay Rendering] (if detected)
    ├─→ Draw red rectangle: cv2.rectangle(...)
    ├─→ Draw confidence badge: cv2.putText(...)
    └─→ Frame with visual indicators
    ↓
[Optional: Crop to Region]
    └─→ If enabled & detected: frame[y:y+h, x:x+w]
    ↓
[JPEG Encode]
    ├─→ Quality: 70 (balanced)
    └─→ ~50-600KB per frame
    ↓
[Update Frame Buffer]
    ├─→ Store JPEG bytes (in-memory)
    └─→ Store metadata (with region info)
    ↓
[Write Shared Frame]
    ├─→ Write JPEG to /dev/shm/msmacro_cv_frame.jpg
    └─→ Write JSON metadata to /dev/shm/msmacro_cv_frame.json
    ↓
[HTTP API]
    └─→ /api/cv/screenshot endpoint
        ├─→ Read JPEG from shared memory
        ├─→ Read metadata from JSON
        ├─→ Add region info to HTTP headers
        └─→ Return image with metadata
    ↓
[Frontend Preview]
    ├─→ Fetch screenshot (2-second polling)
    ├─→ Display image with burned-in overlays
    ├─→ See red rectangle + confidence badge
    └─→ Extract region metadata from headers
```

## Component Changes

### 1. Detection Functions (`region_analysis.py`)

#### **Primary: `detect_white_frame_yuyv()` (YUYV-based)**

```
Input: YUYV bytes, frame dimensions, fixed start point
  ↓
Extract Y channel region around expected location
  ↓
Check fixed starting point (68, 56) for white border
  ↓
Scan rightward to find right edge (variable width)
  ↓
Scan downward to find bottom edge (variable height)
  ↓
Validate dark background (Y: 60-130)
  ↓
Analyze border quality (top, left, right, bottom)
  ↓
Calculate confidence score (border quality + context)
  ↓
Output: {
  detected: bool
  x: 68, y: 56 (fixed)
  width, height: int (variable, ~340x86)
  confidence: float (0.0-1.0)
  white_border_quality: float
  dark_background: bool
  method: "yuyv"
}
```

**Key features**:
- Uses Y (luminance) channel for accurate white detection
- Fixed starting point for known UI elements
- Variable size detection by edge scanning
- Background context validation
- Higher accuracy, lower false positives

#### **Helper: `bgr_to_yuyv_bytes()`**

```
Input: BGR frame from OpenCV
  ↓
Convert BGR to YCrCb (Y, Cr, Cb channels)
  ↓
Pack into YUYV format: [Y0 U Y1 V] per 2 pixels
  ↓
Output: bytes (2 bytes per pixel)
```

**Purpose**: Simulates YUYV format for luminance-based detection

#### **Helper: `extract_y_channel_from_yuyv()`**

```
Input: YUYV bytes, region coordinates
  ↓
Extract Y values at positions: 0, 2, 4, 6, ...
  ↓
Build 2D array of luminance values
  ↓
Output: numpy array (uint8, region_height × region_width)
```

**Purpose**: Extracts brightness data from YUYV packed format

#### **Legacy: `detect_top_left_white_frame()` (Grayscale-based)**

```
Input: BGR/grayscale frame
  ↓
Convert to grayscale
  ↓
Extract top-left search region
  ↓
Create binary white mask (threshold)
  ↓
Find contours
  ↓
Calculate region statistics
  ↓
Output: {
  detected: bool
  x, y, width, height: int
  confidence: float (0.0-1.0)
  region_white_ratio: float
  white_pixels, total_pixels: int
  avg_brightness: float
}
```

**Use case**: General white frame detection (arbitrary positions)

### 2. Frame Buffer (`frame_buffer.py`)

**Extended FrameMetadata**

```python
@dataclass
class FrameMetadata:
    # Existing fields
    timestamp: float
    width: int
    height: int
    size_bytes: int

    # NEW: Region detection fields
    region_detected: bool = False
    region_x: int = 0
    region_y: int = 0
    region_width: int = 0
    region_height: int = 0
    region_confidence: float = 0.0
    region_white_ratio: float = 0.0
```

All region fields have sensible defaults, maintaining backward compatibility.

### 3. Capture Pipeline (`capture.py`)

**Enhanced Capture Loop**

```python
# In _capture_loop():

# Step 1: Capture raw frame
ret, frame = self._capture.read()

# Step 2: Detect white frame region
detection_result = detect_top_left_white_frame(frame, threshold=...)

# Step 3: Extract region info
if detection_result['detected']:
    region_detected = True
    region_x = detection_result['x']
    region_y = detection_result['y']
    region_width = detection_result['width']
    region_height = detection_result['height']
    region_confidence = detection_result['confidence']
    region_white_ratio = detection_result['region_white_ratio']

    # Step 4: Optionally crop frame
    if self._detect_white_frame:  # env: MSMACRO_CV_DETECT_WHITE_FRAME
        frame = frame[region_y:region_y+region_height,
                      region_x:region_x+region_width]

# Step 5: Encode to JPEG
jpeg_bytes = cv2.imencode('.jpg', frame)

# Step 6: Update buffer with metadata
self.frame_buffer.update(
    jpeg_bytes,
    width,
    height,
    region_detected=region_detected,
    region_x=region_x,
    # ... etc
)

# Step 7: Write to shared memory with metadata
self._write_shared_frame(jpeg_bytes, width, height,
    region_detected=region_detected, region_x=region_x, ...)
```

### 4. Shared Metadata (`capture.py`)

**Enhanced `_write_shared_frame()`**

Persists frame and metadata to shared memory for inter-process access:

```
/dev/shm/msmacro_cv_frame.jpg         ← JPEG image data (binary)
/dev/shm/msmacro_cv_frame.json        ← Metadata (JSON)

{
  "width": 640,
  "height": 480,
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

### 5. HTTP API (`web/handlers.py`)

**Enhanced `/api/cv/screenshot` Endpoint**

```python
@handler
async def api_cv_screenshot(request):
    # 1. Get status from daemon
    status = await _daemon("cv_status")

    # 2. Read JPEG from shared memory
    jpeg_data = SHARED_FRAME_PATH.read_bytes()

    # 3. Read metadata (including region info)
    metadata = json.loads(SHARED_META_PATH.read_text())

    # 4. Build response headers
    headers = {
        'X-CV-Frame-Width': str(metadata['width']),
        'X-CV-Frame-Height': str(metadata['height']),
        'X-CV-Frame-Timestamp': str(metadata['timestamp']),

        # NEW: Region headers
        'X-CV-Region-Detected': str(metadata['region_detected']),
        'X-CV-Region-X': str(metadata['region_x']),
        'X-CV-Region-Y': str(metadata['region_y']),
        'X-CV-Region-Width': str(metadata['region_width']),
        'X-CV-Region-Height': str(metadata['region_height']),
        'X-CV-Region-Confidence': str(metadata['region_confidence']),
        'X-CV-Region-White-Ratio': str(metadata['region_white_ratio']),
    }

    # 5. Return JPEG with headers
    return web.Response(body=jpeg_data,
                       content_type='image/jpeg',
                       headers=headers)
```

## Threading Model

```
Main Thread (aiohttp)
    ↓
    ├→ [Event Loop]
    │   ├→ /api/cv/screenshot requests
    │   ├→ /api/cv/status
    │   └→ Other endpoints
    ↓
Capture Thread (_capture_loop)
    ├→ Read frames continuously (2 FPS)
    ├→ Detect regions (~5-10ms per frame)
    ├→ Encode JPEG
    ├→ Update frame buffer (thread-safe with lock)
    ├→ Write shared memory
    └→ Loop: sleep 0.5s (500ms interval)

Monitor Task (asyncio)
    └→ Device reconnection (~5s interval)
```

**Thread Safety**:
- `FrameBuffer` uses `threading.Lock()` for atomic updates
- JPEG encoding to memory before writing
- Shared file writes use atomic rename (tmp → actual)

## Memory Management

```
Raw Frame:        ~6MB (1920x1080 BGR)
  ↓
Grayscale:        ~2MB (converted, original freed)
  ↓
White Mask:       ~1MB (binary)
  ↓
JPEG Encoded:     ~50KB (compression)
  ↓
Final Frame:      600KB (1280x720 JPEG at quality 70)
```

**Optimization Strategy**:
1. Frame processed in capture thread (not copied)
2. Immediately delete after detection
3. Encode only final frame (cropped if enabled)
4. Store only JPEG bytes in buffer
5. Delete intermediate arrays immediately

## Configuration Hierarchy

```
Environment Variables (highest priority)
    ├─ MSMACRO_CV_DETECT_WHITE_FRAME → enable cropping
    ├─ MSMACRO_CV_WHITE_THRESHOLD → detection threshold
    ├─ MSMACRO_CV_WHITE_MIN_PIXELS → min white pixels
    ├─ MSMACRO_CV_WHITE_SCAN_REGION → scan area
    └─ MSMACRO_CV_FRAME_PATH → shared frame location

Function Defaults (lower priority)
    ├─ max_region_width: 800
    ├─ max_region_height: 600
    ├─ edge_margin: 20
    └─ min_white_ratio: 0.85
```

## Error Handling

```
Detection Phase:
    Frame decode fails → skip frame, log warning
    Detection returns None → no region detected
    Cropping fails → use full frame, log debug

Encoding Phase:
    JPEG encode fails → increment error counter

Metadata Phase:
    JSON parse fails → use status info, log debug
    File write fails → continue capture (non-blocking)

API Phase:
    File missing → return 404 "no frame available"
    Parse fails → return 500 "failed to read frame"
```

## Backward Compatibility

All changes are additive and optional:

1. **FrameMetadata**: New fields have defaults (False, 0, 0.0)
2. **Frame Buffer Update**: Region parameters optional
3. **Capture Loop**: Detection always runs, cropping is optional
4. **Shared Metadata**: New keys in JSON, old keys still present
5. **HTTP Headers**: Additional headers, no breaking changes
6. **Environment Variables**: All optional, sensible defaults

Existing code continues working if region features are not enabled.

## Performance Impact

**CPU**:
- Detection: ~5-10ms per frame (in capture thread)
- Capture baseline: 2 FPS (500ms sleep) → negligible impact
- Actual detection overhead: <2% of available time

**Memory**:
- Metadata overhead: ~100 bytes per frame
- Cropped frames may reduce JPEG size
- No additional buffers (in-place operations)

**Network**:
- HTTP headers: ~100 bytes additional
- Cropped frames reduce bandwidth if white frame is small
- Shared metadata file: ~200 bytes

## Testing Strategy

```
Unit Tests:
    ✓ detect_top_left_white_frame() with synthetic frames
    ✓ Region metadata serialization
    ✓ FrameMetadata dataclass fields

Integration Tests:
    ✓ Full capture pipeline with detection enabled
    ✓ API endpoint returns region headers
    ✓ Shared metadata file contains region data

Manual Tests:
    ✓ cv_detect_improved.py script
    ✓ curl to /api/cv/screenshot endpoint
    ✓ Frontend display of region overlay
```

---

See related documents:
- **02_USAGE.md** - How to use the system
- **03_CONFIGURATION.md** - Configuration details
- **04_DETECTION_ALGORITHM.md** - Algorithm details
