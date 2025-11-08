# MSMacro CV System - Complete Documentation

This folder contains comprehensive documentation of the MSMacro Computer Vision system.

**Last Updated**: 2025-11-08  
**Status**: Production Ready

## What's Implemented

The msmacro-app CV capture system provides:

### ✅ Map Configuration System
1. **User-defined minimap regions** - Fixed top-left position with adjustable width/height
2. **Multiple saved configurations** - Switch between different game locations
3. **Live preview** - Real-time minimap region display in web UI
4. **Performance optimization** - Process only the configured region, not entire screen
5. **No auto-detection** - Region is manually defined by user, not detected by CV

### ✅ Object Detection System
1. **Player position tracking** - Detect yellow player dot on minimap
2. **Other players detection** - Detect red enemy/other player dots
3. **Minimap-relative coordinates** - All positions relative to minimap top-left (0,0)
4. **Auto-calibration** - Click-to-calibrate wizard for HSV color tuning
5. **Performance optimized** - < 15ms detection time on Raspberry Pi 4

### ✅ Web UI Integration
1. **CVConfiguration component** - Map config management
2. **ObjectDetection component** - Detection status and results
3. **CalibrationWizard component** - HSV color calibration
4. **Live previews** - Real-time frame updates (2 FPS)
5. **API client** - Full REST API integration

## Documentation Structure

- **00_OVERVIEW.md** (this file) - Quick overview and navigation
- **01_ARCHITECTURE.md** - System architecture and design
- **02_USAGE.md** - Usage guide and basic operations
- **03_CONFIGURATION.md** - Environment variables and configuration
- **04_DETECTION_ALGORITHM.md** - CV detection algorithm details
- **05_API_REFERENCE.md** - HTTP endpoints and REST API reference
- **06_MAP_CONFIGURATION.md** - Map configuration user guide
- **07_SYSTEM_MONITORING.md** - System stats and performance monitoring
- **08_OBJECT_DETECTION.md** - Object detection implementation details
- **09_DATA_FLOW.md** - Complete data flow diagrams (frontend ↔ backend)

## Quick Start

### 1. Create Map Configuration

Access the web UI and navigate to **CV Configuration**:

1. Click **Create Configuration**
2. Adjust width and height with +/- buttons
3. See live preview of minimap region
4. Click **Save Configuration** and enter a name
5. Check the checkbox to activate

### 2. Enable Object Detection

Navigate to **Object Detection**:

1. Click **Enable Detection** toggle
2. See live player position updates
3. Use **Calibrate** to tune colors if needed

### 3. Use Detection in Code

```javascript
// Get detection status and results
const data = await getObjectDetectionStatus();

if (data.last_result?.player?.detected) {
  const { x, y, confidence } = data.last_result.player;
  console.log(`Player at (${x}, ${y}) confidence ${confidence}`);
  // Coordinates are relative to minimap top-left
}
```

## Modified Files

### Core Detection
- `msmacro/cv/region_analysis.py` - New `detect_top_left_white_frame()` function
- `msmacro/cv/capture.py` - Integration of detection into capture pipeline
- `msmacro/cv/frame_buffer.py` - Extended metadata with region fields

### API Layer
- `msmacro/web/handlers.py` - Region metadata in HTTP headers

### Demo Scripts
- `scripts/cv_detect_improved.py` - New improved detection demo script

## Key Classes and Functions

### `detect_top_left_white_frame()`
Optimized detection for white frames in top-left corner. Returns dict with:
- `detected` (bool) - Whether white frame was found
- `x`, `y`, `width`, `height` (int) - Region coordinates
- `confidence` (float) - Detection confidence 0.0-1.0
- `region_white_ratio` (float) - Whiteness of detected region
- Other stats for debugging

### `FrameMetadata`
Extended dataclass with region fields:
- `region_detected` - Whether region was detected
- `region_x`, `region_y` - Top-left coordinates
- `region_width`, `region_height` - Dimensions
- `region_confidence` - Confidence score
- `region_white_ratio` - Whiteness ratio

## Common Tasks

**See which document for...**

| Task | Document |
|------|----------|
| Understand how detection works | 04_DETECTION_ALGORITHM.md |
| Tune detection parameters | 03_CONFIGURATION.md |
| Use region data in frontend | 06_EXAMPLES.md |
| Integrate with existing code | 02_USAGE.md |
| Troubleshoot detection issues | 07_TROUBLESHOOTING.md |
| Optimize for performance | 08_PERFORMANCE.md |
| Full API reference | 05_API_REFERENCE.md |

## Environment Variables

```bash
# Enable white frame detection and auto-cropping
MSMACRO_CV_DETECT_WHITE_FRAME=true

# White pixel threshold (0-255, default: 240)
MSMACRO_CV_WHITE_THRESHOLD=240

# Minimum white pixels for detection (default: 100)
MSMACRO_CV_WHITE_MIN_PIXELS=100

# Custom scan region (format: "x,y,width,height")
MSMACRO_CV_WHITE_SCAN_REGION="0,0,800,600"
```

## Testing

```bash
# Run improved detection demo
python scripts/cv_detect_improved.py --start-capture

# With custom settings
python scripts/cv_detect_improved.py \
    --threshold 230 \
    --ratio 0.85 \
    --save-viz /tmp/detection_ \
    --start-capture

# Test API
curl -i http://localhost:8787/api/cv/screenshot | grep "X-CV-Region"
```

## Key Improvements

1. **Smart Detection** - Focuses on top-left corner where UI content typically appears
2. **Confidence Scoring** - Know how reliable each detection is
3. **Memory Efficient** - Cropped frames reduce JPEG size and bandwidth
4. **Backward Compatible** - All features are optional, existing code unaffected
5. **Well-Integrated** - Region data flows through capture → buffer → API → frontend
6. **Configurable** - Multiple parameters for different scenarios

## Next Steps

1. Read **01_ARCHITECTURE.md** to understand the system design
2. Check **03_CONFIGURATION.md** to tune parameters for your use case
3. Look at **06_EXAMPLES.md** for implementation patterns
4. Review **07_TROUBLESHOOTING.md** for common issues

---

**For detailed information, see the other documentation files in this folder.**
