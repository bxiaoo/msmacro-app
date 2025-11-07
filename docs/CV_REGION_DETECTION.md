# CV Region Detection Guide

This guide shows how to detect white frames (or any other pattern) in specific regions of your captured screen.

## Quick Start

### 1. Capture a Screenshot and Send to Your Host

On your Raspberry Pi:

```bash
# Capture screenshot (daemon must be running)
python scripts/cv_screenshot.py

# Or start capture automatically
python scripts/cv_screenshot.py --start-capture

# Screenshot saved to /tmp/cv_screenshot.jpg
```

Transfer to your host machine:

```bash
# Replace with your actual username and IP
scp /tmp/cv_screenshot.jpg you@192.168.1.100:~/Desktop/

# If you're on your host machine, pull from Pi:
scp pi@192.168.1.50:/tmp/cv_screenshot.jpg ~/Desktop/
```

### 2. Detect White Frame in Top-Left Corner

On your Raspberry Pi:

```bash
# Monitor for white frame (default: top-left 200x100 pixels)
python scripts/cv_detect_white_frame.py --start-capture

# Custom region size
python scripts/cv_detect_white_frame.py --width 300 --height 150

# Adjust sensitivity
python scripts/cv_detect_white_frame.py --threshold 230 --ratio 0.9

# Save screenshot when detected
python scripts/cv_detect_white_frame.py --save-on-detect /tmp/white_detected.jpg
```

Output:
```
White Frame Detector
============================================================
Region: Top-left 200x100 pixels
Threshold: 240 (0-255)
Min white ratio: 95.0%
Check interval: 0.5s
============================================================

Monitoring for white frame... (Ctrl+C to stop)

[14:32:15] Monitoring... White:  12.3% | Brightness: 145.2 | Detections: 0
[14:32:47] 🟦 WHITE FRAME DETECTED!
  Detection #1
  White pixels: 97.2%
  Avg brightness: 248.5
```

## Understanding the Parameters

### Region Definition

A **Region** defines a rectangular area to analyze:

```python
from msmacro.cv.region_analysis import Region

# Absolute coordinates (pixels)
region = Region(x=0, y=0, width=200, height=100)
# Top-left corner, 200x100 pixels

# Relative coordinates (0.0 to 1.0)
region = Region(x=0.0, y=0.0, width=0.2, height=0.1, relative=True)
# Top-left corner, 20% of width × 10% of height
```

### White Detection Parameters

- **threshold** (0-255): Minimum brightness to consider a pixel "white"
  - `240` = Very white (default, strict)
  - `220` = Light gray is acceptable
  - `200` = Medium gray is acceptable

- **ratio** (0.0-1.0): Minimum percentage of white pixels required
  - `0.95` = 95% of pixels must be white (default, strict)
  - `0.80` = 80% white is enough (looser)
  - `0.50` = Half the region white (very loose)

## Python API Usage

### Basic Example

```python
import asyncio
import cv2
import numpy as np
from msmacro.cv import get_capture_instance
from msmacro.cv.region_analysis import Region, is_white_region

async def detect_white():
    # Get capture instance
    capture = get_capture_instance()
    await capture.start()

    # Wait for first frame
    await asyncio.sleep(2)

    # Define top-left corner region
    region = Region(x=0, y=0, width=200, height=100)

    # Get latest frame
    frame_result = capture.get_latest_frame()
    if not frame_result:
        print("No frame available")
        return

    jpeg_bytes, metadata = frame_result

    # Decode JPEG to numpy array
    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Check if region is white
    is_white, stats = is_white_region(frame, region)

    if is_white:
        print("✓ White frame detected!")
        print(f"  White pixels: {stats['white_ratio']:.1%}")
        print(f"  Avg brightness: {stats['avg_brightness']:.1f}")
    else:
        print("✗ No white frame")
        print(f"  White pixels: {stats['white_ratio']:.1%}")

# Run
asyncio.run(detect_white())
```

### Detect Specific Colors

```python
from msmacro.cv.region_analysis import detect_color_in_region

# Detect red color (in BGR: blue=0, green=0, red=255)
red_bgr = (0, 0, 255)
detected, stats = detect_color_in_region(
    frame,
    region,
    color_bgr=red_bgr,
    tolerance=30,  # Allow slight variations
    min_color_ratio=0.8  # 80% of region must be red
)

if detected:
    print("Red detected!")
```

### Multiple Regions

```python
from msmacro.cv.region_analysis import REGIONS

# Use predefined regions
top_left = REGIONS["top_left_corner"]
top_right = REGIONS["top_right_corner"]
center = REGIONS["center"]

# Check multiple regions
regions_to_check = {
    "Top-Left": top_left,
    "Top-Right": top_right,
    "Center": center,
}

for name, region in regions_to_check.items():
    is_white, stats = is_white_region(frame, region)
    print(f"{name}: {'✓' if is_white else '✗'} {stats['white_ratio']:.1%}")
```

### Visualize Regions

```python
from msmacro.cv.region_analysis import visualize_region

# Draw region on frame
vis_frame = visualize_region(
    frame,
    region,
    color=(0, 255, 0),  # Green rectangle
    thickness=2,
    label="Top-Left Corner"
)

# Save visualization
cv2.imwrite("/tmp/visualization.jpg", vis_frame)
```

## Common Use Cases

### 1. Game State Detection

Detect loading screens (often white or black):

```python
# Detect white loading screen
region = Region(x=0.0, y=0.0, width=1.0, height=1.0, relative=True)  # Full screen
is_loading, stats = is_white_region(frame, region, min_white_ratio=0.9)

if is_loading:
    print("Loading screen detected, waiting...")
```

### 2. Health Bar Monitoring

Detect low health (red bar):

```python
# Health bar usually at top-left
health_region = Region(x=10, y=10, width=200, height=20)
red_color = (0, 0, 255)  # BGR

is_low_health, stats = detect_color_in_region(
    frame,
    health_region,
    red_color,
    tolerance=40,
    min_color_ratio=0.7
)

if is_low_health:
    print("⚠️ Low health!")
```

### 3. Button State Detection

Check if a button is active (green) or inactive (gray):

```python
button_region = Region(x=800, y=600, width=100, height=40)

green_color = (0, 255, 0)  # BGR
is_active, _ = detect_color_in_region(
    frame,
    button_region,
    green_color,
    tolerance=30,
    min_color_ratio=0.6
)

if is_active:
    print("✓ Button is active")
else:
    print("✗ Button is inactive")
```

## Predefined Regions

The following regions are available in `REGIONS`:

| Region Name | Description |
|-------------|-------------|
| `top_left_corner` | Top-left 200x100 pixels |
| `top_left_relative` | Top-left 15% × 10% (scales with resolution) |
| `top_right_corner` | Top-right corner (relative) |
| `bottom_left_corner` | Bottom-left corner (relative) |
| `bottom_right_corner` | Bottom-right corner (relative) |
| `center` | Center 20% × 20% |
| `top_bar` | Full width, 50 pixels high at top |
| `bottom_bar` | Full width, 50 pixels high at bottom |

Usage:
```python
from msmacro.cv.region_analysis import REGIONS

region = REGIONS["top_left_corner"]
is_white, stats = is_white_region(frame, region)
```

## Troubleshooting

### "No frame available"

**Problem**: Capture system isn't running.

**Solution**:
```bash
# Check daemon status
python -m msmacro ctl status

# Or start capture manually
python scripts/cv_detect_white_frame.py --start-capture
```

### Detection Too Sensitive / Not Sensitive Enough

**Problem**: Getting false positives or missing detections.

**Solution**: Adjust threshold and ratio:

```bash
# More strict (fewer false positives)
python scripts/cv_detect_white_frame.py --threshold 245 --ratio 0.98

# More lenient (catch more cases)
python scripts/cv_detect_white_frame.py --threshold 220 --ratio 0.85
```

### Wrong Region Size

**Problem**: Region doesn't cover the area you need.

**Solution**: Capture a screenshot first to determine coordinates:

```bash
# 1. Capture screenshot
python scripts/cv_screenshot.py --output /tmp/test.jpg

# 2. Transfer to your machine
scp pi@192.168.1.50:/tmp/test.jpg ~/Desktop/

# 3. Open in image viewer, note pixel coordinates
# 4. Adjust region size:
python scripts/cv_detect_white_frame.py --width 300 --height 150
```

## Performance

Region analysis is very fast:
- **CPU usage**: ~1-2% per region check
- **Memory**: Minimal (only analyzes small region, not full frame)
- **Latency**: <5ms per region check

You can easily check 10+ regions per frame without performance issues.

## Next Steps

1. **Integrate with macros**: Use region detection to trigger macro playback
2. **Template matching**: Detect specific images/icons in regions
3. **OCR**: Read text from regions (future feature)
4. **Color tracking**: Track health/mana bars by color changes

## Example: Integration with Macro Playback

```python
# Pseudo-code for future integration
async def play_macro_on_white_frame():
    capture = get_capture_instance()
    await capture.start()

    region = Region(x=0, y=0, width=200, height=100)

    while True:
        frame = get_current_frame()  # Get decoded frame
        is_white, stats = is_white_region(frame, region)

        if is_white:
            print("White frame detected! Playing macro...")
            await play_macro("my_recording.json")
            break

        await asyncio.sleep(0.5)
```

---

**Questions?** Check the main CV documentation at `.claude/docs/cv-feature.md`
