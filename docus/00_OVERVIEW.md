# MSMacro CV System - Complete Documentation

This folder contains comprehensive documentation of the MSMacro Computer Vision system.

**Last Updated**: 2025-11-08  
**Status**: Production Ready

## What's Implemented

The msmacro-app CV capture system provides:

### ✅ Map Configuration System
1. **Manual minimap regions** - User-defined regions via web UI (fixed top-left at 68,56 with adjustable width/height)
2. **Multiple saved configurations** - Switch between different game maps/locations
3. **Live preview** - Real-time minimap region display with optional overlays
4. **Performance optimization** - Process only the configured region, not entire screen
5. **No auto-detection** - All regions manually configured by user

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

### Core Modules
- `msmacro/cv/capture.py` - Frame capture with manual map config support
- `msmacro/cv/frame_buffer.py` - Thread-safe frame storage with metadata
- `msmacro/cv/map_config.py` - Map configuration persistence
- `msmacro/cv/object_detection.py` - HSV-based player/other-player detection

### API Layer
- `msmacro/web/handlers.py` - REST API for config, preview, detection

### Web UI
- `webui/src/components/CVConfiguration.jsx` - Map config management
- `webui/src/components/ObjectDetection.jsx` - Detection UI with live preview
- `webui/src/components/CalibrationWizard.jsx` - HSV color calibration

## Key Classes and Functions

### `MapConfigManager`
Manages saved map configurations:
- `create_config()` - Save new minimap region
- `activate_config()` - Switch active region
- `list_configs()` - Get all saved configs

### `FrameMetadata`
Dataclass with region fields (from active map config):
- `region_detected` - Whether map config is active
- `region_x`, `region_y` - Top-left coordinates (e.g., 68, 56)
- `region_width`, `region_height` - Dimensions (e.g., 340, 86)

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
# Shared frame paths
MSMACRO_CV_FRAME_PATH=/dev/shm/msmacro_cv_frame.jpg
MSMACRO_CV_META_PATH=/dev/shm/msmacro_cv_frame.json

# Map config storage
MSMACRO_CONFIG_DIR=~/.local/share/msmacro

# Object detection (HSV ranges calibrated via web UI)
MSMACRO_PLAYER_COLOR_H_MIN=15
MSMACRO_PLAYER_COLOR_H_MAX=40
```

## Testing

```bash
# Start daemon
python -m msmacro daemon

# Test map config API
curl http://localhost:8787/api/cv/map-configs

# Test preview endpoint
curl http://localhost:8787/api/cv/mini-map-preview?x=68&y=56&w=340&h=86 -o preview.png

# Test lossless frame (requires active config)
curl http://localhost:8787/api/cv/frame-lossless -o minimap.png
```

## Key Features

1. **Manual Configuration** - User defines minimap region via web UI, no auto-detection
2. **Multiple Configs** - Save and switch between different game maps
3. **Live Preview** - Real-time PNG preview with optional overlays
4. **Object Detection** - HSV-based player/other-player tracking with calibration wizard
5. **Performance** - <15ms detection on Raspberry Pi 4, 2 FPS capture rate
6. **API-Driven** - Full REST API for all config and detection operations

## Next Steps

1. Read **01_ARCHITECTURE.md** to understand the system design
2. Check **03_CONFIGURATION.md** to tune parameters for your use case
3. Look at **06_MAP_CONFIGURATION.md** for manual region configuration
4. Review **08_OBJECT_DETECTION.md** for detection implementation

## Recent Changes (2025-11-08)

### ✅ White Frame Detection Removal
- Removed legacy white frame auto-detection logic (600+ lines)
- All minimap regions now manually configured via web UI
- Simplified codebase: removed deprecated env vars
- See **WHITE_FRAME_REMOVAL_MIGRATION.md** for migration details

### ✅ Preview & Calibration Enhancements  
- Mini-map preview now PNG by default (optional overlay)
- Responsive calibration wizard with full-width preview
- Object Detection UI with live player marker overlay
- Fixed `other_player_hsv_ranges` config bug

---

**For detailed information, see the other documentation files in this folder.**
