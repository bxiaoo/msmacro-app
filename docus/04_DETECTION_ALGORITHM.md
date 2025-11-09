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

**8-Stage Filtering Pipeline** (updated Nov 9, 2025):

1. **Get Minimap**: Crop full frame using active map config
2. **Convert to HSV**: BGR → HSV color space for robust color detection
3. **Create Masks**: Apply HSV range filters (H=26-85, S≥67, V≥64 for player)
4. **Morphology**: Clean noise with 3×3 kernel erosion/dilation
5. **Find Blobs**: Detect contours in binary masks
6. **Filter - Size**: Strict diameter bounds (4-16px player, 4-80px others)
7. **Filter - Circularity**: Round shapes only (≥0.71 player, ≥0.65 others)
8. **Filter - Aspect Ratio**: Reject elongated shapes (0.5-2.0 ratio)
9. **Score & Select**: Combined scoring for player (size × S × V × circularity)
10. **Extract Position**: Calculate centroid of best-scoring blob
11. **Smooth**: Temporal EMA to reduce position jitter (alpha=0.3)

**✅ SIZE FILTERING RE-ENABLED** (Nov 9, 2025): After empirical validation, strict size filtering with separate thresholds (4-16px player, 4-80px red) achieved 100% detection with 0 false positives. Previous "disabled" state has been superseded.

### Calibration

**Status**: ✅ **PRODUCTION-READY VALUES AVAILABLE** (Nov 9, 2025)

**Latest Calibration Results** (Nov 9, 2025):
- ✅ **100% player detection** on 20-sample validation dataset
- ✅ **0 false positives** for other players (100% precision)
- ✅ **0.79ms average** performance (well within <15ms Pi 4 target)
- ✅ HSV ranges: Player (26,67,64)-(85,255,255), Red S/V≥100
- ✅ Validated algorithm: HSV + size (4-16px) + circularity (0.71) + combined scoring

**Calibration Tools Available**:
- ✅ Web UI wizard (CalibrationWizard.jsx) - User clicks player dot in 5 frames
- ✅ Automated sampling (3×3 region, percentile ranges, 20% safety margin)
- ✅ Lossless calibration (raw minimap before JPEG compression)
- ✅ Real-time preview before saving
- ✅ Export validated ranges for production

**Using Pre-Calibrated Values**:
```python
# Default values in code are now PRODUCTION-READY (Nov 9, 2025)
PLAYER_HSV_LOWER = (26, 67, 64)    # Validated on 20 samples
PLAYER_HSV_UPPER = (85, 255, 255)  # 100% detection rate
```

**Re-Calibration Recommended If**:
- Different Pi hardware (camera variations)
- Different game version (graphics updates)
- Different lighting conditions (monitor/HDMI variations)
- Detection rate drops below 90%

**See**: `FINAL_CALIBRATION_RESULTS_2025-11-09.md` for complete validation methodology

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
