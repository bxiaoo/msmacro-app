# Detection Algorithm

## Overview

The white frame detection system provides two complementary approaches:

1. **YUYV-based Detection** (NEW, default): Advanced fixed-point detection using Y (luminance) channel from YUYV color space for MapleStory UI elements
2. **General White Frame Detection**: Flexible contour-based detection for general white regions

Both approaches analyze video frames to identify and locate white or near-white rectangular regions. The YUYV approach is optimized for specific UI elements with known positions, while the general approach works for any white content.

---

## YUYV-Based Detection (Advanced, Default Method)

### Why YUYV?

**YUYV** (also called YUY2) is a packed YUV color format where:
- **Y** = Luminance (brightness), 0-255
- **U, V** = Chrominance (color information)
- Format: 4 bytes represent 2 pixels: `[Y0 U Y1 V]`

**Advantages for White Frame Detection**:
1. Y channel directly represents brightness (white = high Y value ~240-255)
2. More accurate than RGB→Grayscale conversion which uses weighted average
3. Native format for USB capture cards (HDMI input is often YUYV)
4. Faster processing - Y channel extraction vs full color conversion
5. Better for detecting white borders on dark backgrounds

### YUYV Detection Algorithm

#### Step 1: BGR to YUYV Conversion

Since OpenCV's `VideoCapture.read()` automatically converts YUYV to BGR, we convert it back to access the Y channel:

```python
# Convert BGR to YCrCb (OpenCV's YUV equivalent)
ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)

# Pack into YUYV byte format: Y0 U Y1 V
# Y values at byte positions: 0, 2, 4, 6, ...
yuyv_bytes = bgr_to_yuyv_bytes(frame)
```

**Note**: While this is a simulated YUYV conversion, the Y channel values are equivalent to what the camera originally captured.

#### Step 2: Extract Y Channel Region

Extract the luminance (Y) channel for a region around the expected frame location:

```python
y_channel = extract_y_channel_from_yuyv(
    yuyv_bytes,
    frame_width=1280,
    frame_height=720,
    x=38,  # Region start (with margin)
    y=26,
    region_width=560,  # Search area size
    region_height=210
)
```

**Result**: 2D numpy array of brightness values (0-255)

#### Step 3: Fixed-Point Border Detection

Unlike general detection which searches everywhere, this uses a **fixed starting point** where the MapleStory UI frame always appears:

```python
fixed_start_x = 68  # Known X position
fixed_start_y = 56  # Known Y position

# Check if top-left corner has white border
corner_region = y_channel[start_y:start_y+3, start_x:start_x+3]
corner_white_ratio = np.sum(corner_region >= 240) / corner_region.size

if corner_white_ratio < 0.7:
    return None  # No white border at expected position
```

**Detection Strategy**: Known position + variable size

#### Step 4: Scan for Border Edges

From the fixed starting point, scan rightward and downward to find where the white border ends:

**Rightward Scan** (find width):
```python
for x in range(start_x + 10, max_width):
    top_border = y_channel[start_y:start_y+3, x:x+3]
    white_ratio = np.sum(top_border >= 240) / top_border.size

    if white_ratio < 0.5:  # Border ended
        right_edge = x
        break

frame_width = right_edge - start_x
```

**Downward Scan** (find height):
```python
for y in range(start_y + 10, max_height):
    left_border = y_channel[y:y+3, start_x:start_x+3]
    white_ratio = np.sum(left_border >= 240) / left_border.size

    if white_ratio < 0.5:  # Border ended
        bottom_edge = y
        break

frame_height = bottom_edge - start_y
```

**Result**: Bounding box `(68, 56, ~340, ~86)` - variable width/height

#### Step 5: Validate Dark Background

Ensure the white frame is on a dark gray surface (typical of MapleStory UI):

```python
# Sample pixels around the frame
left_bg = y_channel[y:y+height, x-10:x]
left_avg = np.mean(left_bg)

# Dark gray should be Y value 60-130
if not (60 <= left_avg <= 130):
    return False  # Not on expected background
```

**Purpose**: Reduce false positives by validating context

#### Step 6: Analyze Border Quality

Sample all four borders to calculate white border quality:

```python
# Extract border pixels
top_border = y_channel[y:y+3, x:x+width]      # Top 3 rows
left_border = y_channel[y:y+height, x:x+3]    # Left 3 columns
right_border = y_channel[y:y+height, x+width-3:x+width]
bottom_border = y_channel[y+height-3:y+height, x:x+width]

# Calculate whiteness
all_borders = np.concatenate([top, left, right, bottom])
white_border_quality = np.sum(all_borders >= 240) / len(all_borders)
```

**Threshold**: >70% of border pixels must be white (Y ≥ 240)

#### Step 7: Calculate Confidence Score

```python
confidence = 0.0

if white_border_quality > 0.7 and width > 100 and height > 30:
    confidence = white_border_quality

    if dark_background_validated:
        confidence = min(1.0, confidence * 1.2)  # Boost for correct context

detected = (confidence > 0.7)
```

**Confidence Factors**:
- Border quality (primary)
- Minimum size validation
- Background validation (bonus)

#### Step 8: Return Detection Result

```python
return {
    "detected": True,
    "x": 68,
    "y": 56,
    "width": 340,
    "height": 86,
    "confidence": 0.95,
    "white_border_quality": 0.92,
    "dark_background": True,
    "method": "yuyv"
}
```

### Visual Overlay Indicators

When a frame is detected, visual indicators are drawn on the preview:

#### Red Rectangle Overlay

```python
cv2.rectangle(
    frame,
    (x, y),
    (x + width, y + height),
    (0, 0, 255),  # Red in BGR
    2  # 2-pixel thickness
)
```

#### Confidence Badge

```python
confidence_text = f"{confidence:.0%}"  # e.g., "95%"

# Positioned at top-right of detected frame
cv2.putText(
    frame,
    confidence_text,
    (x + width - text_width - 8, y + text_height + 8),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.6,  # Font scale
    (255, 255, 255),  # White text
    2  # Thickness
)
```

**Visual Result**: Red box around detected frame with "95%" badge

### Performance Analysis

For 1280x720 frame with YUYV detection:

```
BGR→YUYV conversion:   ~3-5ms
Y channel extraction:  ~1-2ms
Border scanning:       ~2-3ms
Quality analysis:      ~1-2ms
Overlay rendering:     ~1-2ms
─────────────────────
Total:                 ~8-14ms per frame
```

**Capture rate**: 2 FPS (500ms interval), so 8-14ms is negligible (< 3% overhead)

### Comparison: YUYV vs Grayscale Detection

| Aspect | YUYV Method | Grayscale Method |
|--------|-------------|------------------|
| Starting point | Fixed (68, 56) | Searches entire region |
| Size detection | Variable (scans edges) | Contour-based |
| Color space | Y channel (luminance) | RGB weighted average |
| Background validation | Yes (dark gray check) | No |
| Border quality | Yes (samples all edges) | No (contour area only) |
| Performance | ~8-14ms | ~5-10ms |
| Accuracy | High for known positions | General purpose |
| False positives | Very low (context aware) | Medium |

### When to Use YUYV Detection

**Best for**:
- ✓ Fixed UI elements (MapleStory party/quest frames)
- ✓ Known starting positions
- ✓ White-bordered frames on dark backgrounds
- ✓ Need high confidence scores
- ✓ Need visual feedback (overlays)

**Not suitable for**:
- ✗ Unknown frame positions
- ✗ Frames that move around
- ✗ Multiple white regions
- ✗ Non-white borders

For general white frame detection, use the contour-based method below.

---

## General White Frame Detection (Legacy Method)

This is the original contour-based approach, still useful for detecting arbitrary white regions.

## Algorithm Steps

### Step 1: Convert to Grayscale

```python
if len(frame.shape) == 3:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
else:
    gray = frame
```

**Purpose**: Reduce computation from 3 channels to 1
**Input**: RGB or BGR frame
**Output**: Grayscale image (values 0-255)

### Step 2: Extract Search Region

```python
search_width = min(max_region_width, frame_width - edge_margin)
search_height = min(max_region_height, frame_height - edge_margin)

top_left = gray[
    edge_margin:edge_margin + search_height,
    edge_margin:edge_margin + search_width
]
```

**Purpose**: Limit detection to top-left area of interest
**Parameters**:
- `max_region_width`: Maximum search width (default: 800)
- `max_region_height`: Maximum search height (default: 600)
- `edge_margin`: Pixels to exclude from edges (default: 20)

**Example**:
- Frame: 1280x720
- max_region_width: 800, max_region_height: 600
- edge_margin: 20
- Search area: From (20,20) to (820,620) = 800x600 region

### Step 3: Create Binary Mask

```python
_, white_mask = cv2.threshold(
    top_left,
    threshold,
    255,
    cv2.THRESH_BINARY
)
```

**Purpose**: Convert to binary (white/not-white)
**Parameter**: `threshold` (0-255)
**Result**: Binary image where:
- Pixel ≥ threshold → 255 (white)
- Pixel < threshold → 0 (black)

**Example**:
- Threshold: 240
- Pixel value 250 → becomes 255 (white)
- Pixel value 235 → becomes 0 (black)

### Step 4: Count White Pixels

```python
white_pixels = np.sum(white_mask > 0)
total_pixels = white_mask.size
white_ratio = white_pixels / total_pixels
```

**Purpose**: Calculate whiteness percentage of search region
**Output**: white_ratio (0.0-1.0)

### Step 5: Find Contours

```python
contours, _ = cv2.findContours(
    white_mask,
    cv2.RETR_EXTERNAL,
    cv2.CHAIN_APPROX_SIMPLE
)
```

**Purpose**: Find connected white pixel regions
**Output**: List of contours (edges of white regions)

### Step 6: Select Largest Contour

```python
if contours:
    largest_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest_contour)
```

**Purpose**: Find the bounding box of largest white region
**Assumption**: Largest white region is the content area
**Output**: (x, y, width, height) in search region coordinates

### Step 7: Convert to Frame Coordinates

```python
# Search region has offset due to edge_margin
abs_x = edge_margin + x
abs_y = edge_margin + y

# Clamp to frame boundaries
abs_x = max(0, min(abs_x, frame_width - 1))
abs_y = max(0, min(abs_y, frame_height - 1))
w = max(1, min(w, frame_width - abs_x))
h = max(1, min(h, frame_height - abs_y))
```

**Purpose**: Convert local search coordinates to absolute frame coordinates
**Ensures**: Region stays within frame bounds

### Step 8: Analyze Detected Region

```python
region_roi = gray[abs_y:abs_y + h, abs_x:abs_x + w]
_, region_mask = cv2.threshold(region_roi, threshold, 255, cv2.THRESH_BINARY)
region_white_ratio = np.sum(region_mask > 0) / region_mask.size
```

**Purpose**: Measure actual whiteness of detected region
**Separate from**: Search region whiteness (may include noise)

### Step 9: Calculate Confidence

```python
confidence = min(1.0, region_white_ratio)
```

**Purpose**: Confidence score (0.0-1.0) indicates detection quality
- 1.0: Entire region is white
- 0.9: 90% of region is white
- 0.5: Only 50% of region is white

### Step 10: Return Result

```python
return {
    "detected": region_white_ratio >= min_white_ratio,
    "x": int(abs_x),
    "y": int(abs_y),
    "width": int(w),
    "height": int(h),
    "confidence": float(confidence),
    "region_white_ratio": float(region_white_ratio),
    "white_ratio": float(white_ratio),  # Search region whiteness
    "white_pixels": int(white_pixels),
    "avg_brightness": float(np.mean(top_left)),
}
```

## Visual Example

```
Input Frame (1280x720):
┌─────────────────────────────────────────────────┐
│ (0,0)                                           │
│                                                 │
│   ┌─────────────────────────────────────┐      │
│   │ Edge margin (20px)                  │      │
│   │                                     │      │
│   │  ┌─────────────────────────────┐    │      │
│   │  │ Search region (800x600)    │    │      │
│   │  │                            │    │      │
│   │  │  ┌────────────────────┐   │    │      │
│   │  │  │ White frame      │   │    │      │
│   │  │  │ (detected)       │   │    │      │
│   │  │  │ Region: (x,y,w,h)│   │    │      │
│   │  │  └────────────────────┘   │    │      │
│   │  │                            │    │      │
│   │  └─────────────────────────────┘    │      │
│   │                                     │      │
│   └─────────────────────────────────────┘      │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Decision Tree

```
Frame → Grayscale
    ↓
Extract top-left region
    ↓
Create white mask
    ↓
White pixels in search? ─NO→ Return detected=False
    ↓ YES
Find contours
    ↓
Contours exist? ─NO→ Return detected=False
    ↓ YES
Get largest contour
    ↓
Get bounding rectangle
    ↓
Analyze region whiteness
    ↓
Region whiteness ≥ min_white_ratio? ─NO→ Return detected=False
    ↓ YES
Return detected=True with region info
```

## Parameter Impact

### Threshold Impact

```
Pixel Values:  0 ───── 150 ───── 200 ───── 240 ───── 255
               Black   Gray     Light Gray  White    Pure White

Threshold 200:  BLACK         │ WHITE (everything ≥200)
Threshold 240:  BLACK   GRAY  │ WHITE (only ≥240)
Threshold 255:  BLACK   GRAY  │ WHITE (only pure white)

Result: Higher threshold → Stricter, fewer detections
```

### Edge Margin Impact

```
Frame: 1280x720
Without margin:  Search [0:800, 0:600]
With 20px margin: Search [20:820, 20:620]

Result: Margin avoids window borders/UI chrome
```

### Search Region Impact

```
Small region (400x300):  Fast, limited coverage
Large region (1000x800): Slow, comprehensive coverage

Performance: Larger region = longer detection time
```

### Min White Ratio Impact

```
min_white_ratio = 0.95:  Very strict (99%+ whiteness)
min_white_ratio = 0.85:  Balanced (85%+ whiteness)
min_white_ratio = 0.70:  Lenient (70%+ whiteness)

Result: Lower ratio → More detections (more false positives)
```

## Computational Complexity

### Time Complexity

```
Grayscale conversion:    O(W × H)
Thresholding:           O(W × H)
Contour finding:        O(W × H)
Bounding rectangle:     O(N) where N = pixels in largest contour

Total:                  O(W × H) where W×H = frame size
```

### Practical Performance

For 1280x720 frame with 800x600 search region:

```
Grayscale:      ~1-2ms
Threshold:      ~1-2ms
Contour find:   ~2-4ms
Analysis:       ~1-2ms
─────────────
Total:          ~5-10ms (per frame)
```

Capture is 2 FPS (500ms between frames), so 5-10ms detection is negligible.

## Accuracy Considerations

### What It Detects Well

- ✓ Large white rectangles (UI content)
- ✓ Documents on white background
- ✓ Web page content
- ✓ Dialog boxes with white background
- ✓ Clean, uniform white regions

### What It Struggles With

- ✗ Off-white (cream, light gray)
- ✗ Partially visible frames
- ✗ Frames with non-white borders
- ✗ Noisy/textured white areas
- ✗ Multiple separate white regions

### Mitigation Strategies

**For off-white content**:
```bash
# Lower threshold
export MSMACRO_CV_WHITE_THRESHOLD=220
```

**For noisy white**:
```bash
# Raise min white ratio
export MSMACRO_CV_WHITE_MIN_PIXELS=500
```

**For partial frames**:
```bash
# Expand search region
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,1000,800"
```

## Comparison with Alternative Approaches

### Approach 1: Adaptive Threshold

```python
# Instead of fixed threshold
_, mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 11, 2)
```

**Pros**: Handles varying lighting
**Cons**: Slower, may detect edges instead of regions

### Approach 2: Color Detection

```python
# Detect by specific white color
white_color = np.array([255, 255, 255])
lower = white_color - tolerance
upper = white_color + tolerance
mask = cv2.inRange(frame, lower, upper)
```

**Pros**: More specific
**Cons**: Requires HSV space, complex tuning

### Approach 3: Machine Learning

```python
# Train model on white/not-white regions
model.predict(features)
```

**Pros**: Highly accurate
**Cons**: Requires training data, complex

### Why Current Approach?

- **Simple**: Easy to understand and debug
- **Fast**: ~5-10ms per frame
- **Tunable**: Single threshold parameter
- **Effective**: Works for most UI content

## Testing the Algorithm

### Synthetic Test Case

```python
import numpy as np
import cv2
from msmacro.cv.region_analysis import detect_top_left_white_frame

# Create test frame
frame = np.ones((480, 640, 3), dtype=np.uint8) * 50  # Dark background
frame[50:300, 50:400] = 255  # White region

result = detect_top_left_white_frame(frame, threshold=240)

assert result['detected'] == True
assert result['x'] == 50
assert result['y'] == 50
assert result['width'] == 350
assert result['height'] == 250
```

### Real Frame Test

```python
import cv2
from msmacro.cv.region_analysis import detect_top_left_white_frame

# Load real screenshot
frame = cv2.imread('/tmp/screenshot.jpg')

result = detect_top_left_white_frame(
    frame,
    threshold=240,
    min_white_ratio=0.85
)

if result['detected']:
    print(f"Region: ({result['x']},{result['y']}) {result['width']}x{result['height']}")
    print(f"Confidence: {result['confidence']:.1%}")
```

---

See related documents:
- **03_CONFIGURATION.md** - Parameter tuning
- **07_TROUBLESHOOTING.md** - Handling detection issues
