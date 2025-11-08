# Object Detection Algorithm

## Overview

The MSMacro CV system uses **HSV color-based blob detection** to track player and other players on the game minimap. 

**Important**: Minimap region configuration is now **manual** (user-defined via web UI at fixed top-left 68,56). This document focuses only on detecting colored dots (player/other players) within that manually-configured region.

---

## Manual Map Configuration

### How It Works

Users manually configure the minimap region via the web UI:

1. Navigate to **CV Configuration** tab
2. Click **Create Configuration**
3. Adjust width/height with +/- buttons (top-left fixed at 68, 56)
4. Preview shows cropped region in real-time
5. Save and activate the configuration

**Storage**: `~/.local/share/msmacro/map_configs.json`

**No Auto-Detection**: All region coordinates are user-defined.

---

## Object Detection (HSV Color-Based)

### Detected Objects

1. **Player** (yellow dot) - Single object, precise (x, y) coordinates
2. **Other Players** (red dots) - Multiple objects, boolean detection + count

### Detection Steps

1. **Get Minimap**: Crop full frame using active map config
2. **Convert to HSV**: BGR → HSV color space
3. **Create Masks**: Apply HSV range filters for yellow/red
4. **Morphology**: Clean noise with erosion/dilation
5. **Find Blobs**: Detect contours in masks
6. **Filter**: Size (3-15px) + circularity (>0.6 player, >0.5 others)
7. **Extract Position**: Calculate centroid of valid blobs
8. **Smooth** (optional): Temporal EMA to reduce jitter

### Calibration

HSV ranges calibrated via web UI wizard:
- User clicks player dot in 5 frames
- System samples 3×3 region, calculates percentile ranges
- Adds 20% safety margin
- Returns validated ranges for production use

**Default ranges are placeholders** - must calibrate on Pi with real YUYV frames.

---

## Performance (Raspberry Pi 4)

```
Detection time:     < 15ms per frame
Update rate:        2 FPS (500ms intervals)
CPU overhead:       < 3%
Minimap size:       340×86 pixels (~88KB memory)
```

---

## Coordinate System

All coordinates are **minimap-relative** (0,0 = minimap top-left).

To convert to screen: `screen_x = config.tl_x + minimap_x`

---

## Related Documentation

- **06_MAP_CONFIGURATION.md** - Manual region configuration guide
- **08_OBJECT_DETECTION.md** - Implementation details
- **OBJECT_DETECTION_TESTING.md** - Validation and deployment
