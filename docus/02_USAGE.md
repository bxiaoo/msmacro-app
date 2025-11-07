# Usage Guide

## Quick Start

### 1. Enable White Frame Detection

```bash
# Set environment variable to enable detection
export MSMACRO_CV_DETECT_WHITE_FRAME=true

# Start the daemon
python -m msmacro daemon
```

### 2. Access Screenshots with Region Data

```bash
# Get screenshot with region metadata in headers
curl -i http://localhost:8787/api/cv/screenshot

# Extract region from headers
curl -s -i http://localhost:8787/api/cv/screenshot | grep "X-CV-Region"
```

### 3. Test with Improved Demo Script

```bash
# Run detector with visualization
python scripts/cv_detect_improved.py --start-capture
```

## Basic Integration

### Python - Get Screenshot with Region

```python
import requests
import json

# Fetch screenshot
response = requests.get('http://localhost:8787/api/cv/screenshot')

# Extract region metadata from headers
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
with open('/tmp/screenshot.jpg', 'wb') as f:
    f.write(response.content)

# Use region data
if region['detected'] and region['confidence'] > 0.8:
    print(f"High confidence detection at: ({region['x']},{region['y']})")
    print(f"Size: {region['width']}x{region['height']}")
    print(f"Confidence: {region['confidence']:.1%}")
```

### JavaScript/Frontend - Fetch and Display

```javascript
// Fetch screenshot with region metadata
async function getScreenshotWithRegion() {
    const response = await fetch('/api/cv/screenshot');

    if (!response.ok) {
        console.error('Failed to fetch screenshot');
        return null;
    }

    // Extract region from response headers
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

    return { imageUrl, region };
}

// Use in component
async function displayScreenshot() {
    const result = await getScreenshotWithRegion();

    if (!result) return;

    // Display image
    const img = document.getElementById('screenshot');
    img.src = result.imageUrl;

    // Show region info
    const info = document.getElementById('region-info');
    if (result.region.detected) {
        info.innerHTML = `
            <p>Region detected with ${(result.region.confidence * 100).toFixed(1)}% confidence</p>
            <p>Position: (${result.region.x}, ${result.region.y})</p>
            <p>Size: ${result.region.width}x${result.region.height}</p>
        `;
    } else {
        info.innerHTML = '<p>No region detected</p>';
    }
}

// Draw region overlay on canvas
function drawRegionOverlay(imageUrl, region) {
    const img = new Image();
    img.onload = () => {
        const canvas = document.getElementById('preview');
        const ctx = canvas.getContext('2d');

        // Draw image
        ctx.drawImage(img, 0, 0);

        // Draw region rectangle if detected
        if (region.detected) {
            ctx.strokeStyle = `rgb(0, 255, 0)`;
            ctx.lineWidth = 3;
            ctx.strokeRect(region.x, region.y, region.width, region.height);

            // Draw label
            ctx.fillStyle = 'rgba(0, 255, 0, 0.5)';
            ctx.fillRect(region.x, region.y - 25, 200, 25);
            ctx.fillStyle = 'white';
            ctx.font = '14px monospace';
            ctx.fillText(
                `Confidence: ${(region.confidence * 100).toFixed(0)}%`,
                region.x + 5,
                region.y - 8
            );
        }
    };
    img.src = imageUrl;
}
```

## Common Usage Patterns

### Pattern 1: Automatic Cropping Enabled

```bash
# Configuration
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=240
python -m msmacro daemon

# Result:
# - Frames are automatically cropped to detected region
# - Region metadata still preserved in headers
# - Smaller JPEG files (reduced bandwidth)
```

### Pattern 2: Detection Only (No Cropping)

```bash
# Configuration
export MSMACRO_CV_DETECT_WHITE_FRAME=false  # or unset
python -m msmacro daemon

# Result:
# - Full frames captured
# - Region metadata in headers
# - Frontend can crop/draw overlay if needed
# - Useful for manual control in frontend
```

### Pattern 3: Strict Detection

```bash
# Configuration
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=250      # Very strict
export MSMACRO_CV_WHITE_MIN_PIXELS=500     # Larger minimum
python -m msmacro daemon

# Result:
# - Only very clean white frames detected
# - Lower false positives
# - May miss some valid frames
```

### Pattern 4: Lenient Detection

```bash
# Configuration
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=200      # More lenient
python -m msmacro daemon

# Result:
# - Detects off-white frames
# - More detections, potential false positives
# - Better for varied lighting conditions
```

## Testing Detection

### Test 1: Run Detection Script

```bash
# Basic test
python scripts/cv_detect_improved.py --start-capture

# Output: Live monitoring with detection statistics
# [12:34:56] 🟦 WHITE FRAME DETECTED (#1)
# Region: x=120, y=80, 640x480 pixels
# Confidence: 0.95
```

### Test 2: Save Visualizations

```bash
# Save images when detection occurs
python scripts/cv_detect_improved.py \
    --start-capture \
    --save-viz /tmp/detection_

# Creates:
# /tmp/detection_1699564800_full.jpg  (full frame with box)
# /tmp/detection_1699564800_crop.jpg  (cropped region)
```

### Test 3: Custom Parameters

```bash
# Test with different threshold
python scripts/cv_detect_improved.py \
    --threshold 220 \
    --ratio 0.80 \
    --start-capture
```

### Test 4: API Test

```bash
# Get screenshot and show headers
curl -v http://localhost:8787/api/cv/screenshot 2>&1 | grep "X-CV-Region"

# Output:
# X-CV-Region-Detected: true
# X-CV-Region-X: 120
# X-CV-Region-Y: 80
# X-CV-Region-Width: 640
# X-CV-Region-Height: 480
# X-CV-Region-Confidence: 0.95
```

## Troubleshooting Common Issues

### Issue: Detection Never Triggers

**Cause**: Threshold too high or no white content in top-left

**Solutions**:
```bash
# Lower threshold
export MSMACRO_CV_WHITE_THRESHOLD=200

# Lower min white ratio
export MSMACRO_CV_WHITE_MIN_PIXELS=50

# Expand scan region
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,1000,800"
```

**Debug**: Run test script with visualization
```bash
python scripts/cv_detect_improved.py \
    --threshold 220 \
    --ratio 0.75 \
    --save-viz /tmp/ \
    --start-capture
```

### Issue: Too Many False Positives

**Cause**: Threshold too low or capturing unwanted background

**Solutions**:
```bash
# Raise threshold (stricter)
export MSMACRO_CV_WHITE_THRESHOLD=245

# Raise min white ratio
export MSMACRO_CV_WHITE_MIN_PIXELS=500

# Reduce scan region (focus area)
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,600,400"
```

### Issue: Cropped Frames Wrong Size

**Cause**: Detection working but crop region incorrect

**Solutions**:
```bash
# Check actual region being detected
python scripts/cv_detect_improved.py --once --save-viz /tmp/

# Verify environment variables
echo $MSMACRO_CV_WHITE_THRESHOLD
echo $MSMACRO_CV_DETECT_WHITE_FRAME

# Try without cropping first
unset MSMACRO_CV_DETECT_WHITE_FRAME
```

## Advanced Usage

### Custom Region Analysis

```python
from msmacro.cv.region_analysis import detect_top_left_white_frame
import cv2
import numpy as np

# Load a test frame
frame = cv2.imread('/path/to/screenshot.jpg')

# Run detection with custom parameters
result = detect_top_left_white_frame(
    frame,
    max_region_width=1000,
    max_region_height=700,
    threshold=230,
    min_white_ratio=0.80,
    edge_margin=30
)

if result['detected']:
    print(f"Detected region: ({result['x']},{result['y']}) "
          f"{result['width']}x{result['height']}")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"White pixels: {result['region_white_ratio']:.1%}")

    # Crop frame
    x, y, w, h = result['x'], result['y'], result['width'], result['height']
    cropped = frame[y:y+h, x:x+w]
    cv2.imwrite('/tmp/cropped.jpg', cropped)
```

### Batch Processing

```python
import os
from pathlib import Path
from msmacro.cv.region_analysis import detect_top_left_white_frame
import cv2

# Process directory of images
input_dir = Path('/data/screenshots')
output_dir = Path('/data/cropped')
output_dir.mkdir(exist_ok=True)

for image_file in input_dir.glob('*.jpg'):
    frame = cv2.imread(str(image_file))
    result = detect_top_left_white_frame(frame)

    if result['detected']:
        x, y, w, h = result['x'], result['y'], result['width'], result['height']
        cropped = frame[y:y+h, x:x+w]
        output_file = output_dir / image_file.name
        cv2.imwrite(str(output_file), cropped)
        print(f"✓ {image_file.name}")
    else:
        print(f"✗ {image_file.name} (no detection)")
```

### Real-time Monitoring

```python
import asyncio
import requests
from time import time

async def monitor_detection():
    """Monitor detection metrics over time."""
    detections = []
    no_detections = 0

    while True:
        try:
            response = requests.get('http://localhost:8787/api/cv/screenshot')

            detected = response.headers.get('X-CV-Region-Detected') == 'true'
            confidence = float(response.headers.get('X-CV-Region-Confidence', 0))

            if detected:
                detections.append({'time': time(), 'confidence': confidence})
                no_detections = 0
            else:
                no_detections += 1

                if no_detections > 5:
                    print("⚠ No detections for 5 checks - may need tuning")

        except Exception as e:
            print(f"Error: {e}")

        await asyncio.sleep(2)

asyncio.run(monitor_detection())
```

---

See related documents:
- **03_CONFIGURATION.md** - Configuration reference
- **06_EXAMPLES.md** - More code examples
- **07_TROUBLESHOOTING.md** - Common problems and solutions
