# Object Detection Algorithm

## Overview

The MSMacro CV system uses **HSV color-based blob detection** to track player and other players on the game minimap.

**Status**: ✅ **Core Algorithm Complete** - ⚠️ **Calibration Required for Production**

**Important**: Minimap region configuration is now **manual** (user-defined via web UI at fixed top-left 68,56). This document focuses only on detecting colored dots (player/other players) within that manually-configured region.

**Last Updated**: 2025-11-09 (v1.1 - Updated to reflect implementation status)

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
6. **Filter**: Circularity (>0.6 player, >0.5 others) - **size filtering disabled**
7. **Extract Position**: Calculate centroid of valid blobs
8. **Smooth**: Temporal EMA to reduce jitter

**⚠️ IMPLEMENTATION NOTE**: Size filtering (originally 3-15px) has been **disabled** (accepts 1-100px). Detection relies on HSV color matching and circularity filtering only, which proved sufficient in real-world testing.

### Calibration

**Status**: ✅ **Tools Complete** - ⚠️ **Manual Calibration Required**

HSV ranges calibrated via web UI wizard:
- ✅ User clicks player dot in 5 frames (CalibrationWizard.jsx)
- ✅ System samples 3×3 region, calculates percentile ranges
- ✅ Adds 20% safety margin
- ✅ Truly lossless calibration (raw minimap before JPEG compression)
- ✅ Returns validated ranges with preview for production use

**⚠️ CRITICAL**: Default ranges in code are **JPEG placeholders** - MUST calibrate on Pi with real YUYV frames before production use. JPEG compression significantly alters color values.

---

## Performance (Raspberry Pi 4)

**Status**: ✅ **Automatic Tracking Implemented**

```
Detection time:     < 15ms per frame (tracked via performance endpoint)
Update rate:        2 FPS (500ms intervals)
CPU overhead:       < 3% (11-14ms per 500ms)
Minimap size:       340×86 pixels (~88KB memory overhead)
Memory:             Raw minimap stored before JPEG (lossless calibration)
```

**Monitoring**: Real-time performance statistics available via `/api/cv/object-detection/performance` endpoint (avg/max/min timing).

---

## Coordinate System

All coordinates are **minimap-relative** (0,0 = minimap top-left).

To convert to screen: `screen_x = config.tl_x + minimap_x`

---

## Implementation Summary

### ✅ Implemented Features
- HSV color-based blob detection (player + other players)
- Circularity-based filtering (size filtering disabled)
- Temporal smoothing with EMA
- Auto-calibration wizard (5-sample, percentile-based)
- Truly lossless calibration (raw minimap before JPEG)
- Full API integration (10 endpoints)
- Performance tracking (automatic timing statistics)
- Frontend components (ObjectDetection.jsx, CalibrationWizard.jsx)

### ⚠️ Required Before Production
- **MUST calibrate HSV ranges** on test Pi with real YUYV frames
- Default values are JPEG placeholders only
- Manual validation required (aim for >90% accuracy)

### ❌ Not Implemented (Future Work)
- Automated accuracy metrics (precision, recall)
- Ground truth annotation tools
- Playback integration (position-based corrections)
- Auto-rollback on accuracy drops

---

## Related Documentation

- **06_MAP_CONFIGURATION.md** - Manual region configuration guide
- **08_OBJECT_DETECTION.md** - Comprehensive implementation details and deployment guide
- **OBJECT_DETECTION_TESTING.md** - Validation and deployment (if exists)
