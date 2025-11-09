# Object Detection - Implementation Plan

## Overview

This document describes the minimap object detection feature for MSMacro. The system will detect colored points on the minimap representing the player and other players, enabling automated navigation and rotation control based on their positions.

## Hardware Requirements

### Development Environments

This feature requires a **three-stage development workflow** due to color space differences between development (JPEG) and production (YUYV):

1. **Development Machine** (PC/Mac)
   - Purpose: Core algorithm development
   - Environment: Python 3.9+, OpenCV, numpy
   - Input: JPEG test images (compressed, approximation only)
   - Output: Detection algorithm implementation
   - Color Calibration: Placeholder HSV ranges (not production-accurate)

2. **Test Raspberry Pi** (separate from production device)
   - Purpose: YUYV calibration and performance validation
   - Hardware: Raspberry Pi 4, video capture card
   - Input: Real YUYV frames from capture card
   - Output: Calibrated HSV ranges, performance benchmarks
   - Requirements:
     - Same hardware as production Pi
     - Web UI access for remote calibration (no monitor)
     - Can run msmacro daemon for integration testing

3. **Production Raspberry Pi** (gameplay device)
   - Purpose: Final deployment after validation
   - Input: Exported calibration config from test Pi
   - Deployment Gate: Must achieve >90% detection accuracy on test Pi
   - Monitoring: 24-hour stability period before enabling auto-corrections

### Why Three Stages?

- **JPEG vs YUYV**: Color values differ significantly between compressed JPEG (development) and raw YUYV (production)
- **Remote Calibration**: Pi devices have no monitor - HSV tuning must happen via web UI
- **Risk Mitigation**: Testing on separate Pi prevents disrupting active gameplay
- **Performance Validation**: Real Pi hardware needed for accurate CPU/latency measurements

## Problem Statement

**Goal**: Detect and track colored objects (points) on a minimap for automated gameplay navigation.

**Objects to Detect**:
1. **Player** (Yellow point) - Single object, requires precise (x, y) position
2. **Other Players** (Red points) - Multiple objects, only requires existence detection (boolean)

**Point Characteristics**:
- Small circular/round shapes
- Outlined with black then white borders
- Colors may vary based on compression/lighting
- Detected within cropped minimap region (fixed top-left at 68, 56)

## Use Cases

### 1. Position-Based Navigation
- Track player position on minimap
- Calculate distance/direction to target
- Send movement keystrokes based on position
- Implement auto-pathing logic

### 2. Other Player Awareness
- Detect presence of other players nearby
- Trigger defensive actions if detected
- Avoid PvP or farm rotation conflicts
- Alert user when other players appear

### 3. Rotation Control During Playback
- Read player position continuously
- Adjust recorded macro rotation based on position drift
- Correct positional errors in real-time
- Maintain optimal farming positions

## Technical Approach

### Development Workflow: JPEG vs YUYV

**Critical Distinction**: Development uses JPEG test images, but production uses YUYV frames from video capture hardware. Color values differ significantly between these formats.

#### Stage 1: Algorithm Development (Local/PC with JPEG)

**Purpose**: Implement detection logic without Pi hardware

**Status**: ✅ **COMPLETE**

- **Input**: Compressed JPEG test images (example: `docus/archived/msmacro_cv_frame_object_recognize.jpg`)
- **Limitation**: JPEG compression alters colors - HSV values are approximations only
- **Focus**: Algorithm correctness (blob detection, filtering, temporal smoothing)
- **HSV Ranges**: Use **placeholder values** with wider tolerances
- **Validation**: Logic works, but color accuracy deferred to Stage 2

**Completed Activities**:
1. ✅ Implemented `MinimapObjectDetector` class (object_detection.py, 778 lines)
2. ✅ Blob detection and filtering with JPEG samples working
3. ✅ Visualization and debugging tools complete
4. ✅ Unit tests framework in place (tests/cv/test_object_detection.py)

#### Stage 2: Production Calibration (Test Pi with YUYV)

**Purpose**: Calibrate color detection for real YUYV frames

**Status**: ✅ **TOOLS COMPLETE** - ⚠️ **MANUAL CALIBRATION REQUIRED**

- **Input**: Raw YUYV frames from Raspberry Pi video capture card
- **Hardware**: Test Pi (separate from production device)
- **Method**: Remote calibration via web UI (no monitor access)
- **Process**:
  1. ✅ Deploy code to test Pi
  2. ✅ Access web UI remotely (http://test-pi.local:5050)
  3. ✅ Use **click-to-calibrate wizard**: user clicks player in 5 frames
  4. ✅ System analyzes YUYV pixel values and generates HSV ranges
  5. ⚠️ **MANUAL**: Validate detection accuracy >90% with live gameplay
  6. ✅ Export calibrated config for production deployment

**Completed Tools**:
- ✅ Raw minimap capture before JPEG compression (truly lossless)
- ✅ CalibrationWizard.jsx with click-to-calibrate interface
- ✅ Auto-calibration algorithm (percentile-based with 20% margin)
- ✅ Real-time detection preview with overlays
- ✅ Config export/import system

**Validation Requirements** (⚠️ MANUAL PROCESS):
- ⚠️ Capture 50+ YUYV test frames (various scenarios) - **no automated tool**
- ⚠️ Manual ground truth annotation - **no annotation tool implemented**
- ⚠️ Visual accuracy validation (aim >90%) - **no automated metrics**
- ✅ Performance benchmarks: < 15ms per detection on Pi 4 (automatic tracking)
- ⚠️ Stability test: 24-hour continuous operation - **manual monitoring**

#### Stage 3: Production Deployment

**Purpose**: Deploy validated config to gameplay Pi

**Status**: ✅ **READY** - ⚠️ **REQUIRES STAGE 2 CALIBRATION FIRST**

- **Input**: Exported calibration config from test Pi
- **Gate**: Must pass Stage 2 validation (manual verification of >90% accuracy)
- **Monitoring**: ✅ Performance tracking available, ⚠️ manual 24-hour observation required
- **Rollback**: ⚠️ Manual rollback only (no automated accuracy monitoring)

**Deployment Process**:
1. ✅ Export config JSON from test Pi
2. ✅ Import config to production Pi via web UI or file copy
3. ✅ Enable detection via API or web UI
4. ⚠️ **MANUAL**: Monitor performance and accuracy for 24 hours
5. ⚠️ **MANUAL**: Disable if accuracy drops (no automated rollback)

### Detection Method: Color-Based Blob Detection

**Why Color Detection?**
- Fast: ~1-5ms per frame (low latency requirement)
- Robust: Points have distinct colors
- Simple: No ML model training needed
- Adaptable: Can tune HSV ranges in real environment (via remote calibration)

**Algorithm Flow**:
1. Convert BGR frame to HSV color space
2. Apply color range masks (yellow for player, red for other_player)
3. Find contours in masked image
4. Filter by circularity and size
5. Calculate centroid (x, y) for player
6. Return position and existence flags

### Color Ranges (HSV)

**⚠️ CRITICAL - CALIBRATION REQUIRED**: These are **placeholder values for JPEG-based development only**.

**✅ PRODUCTION-READY VALUES** - Final calibrated values from Nov 9, 2025 validation (20-sample dataset, 100% detection rate). These values can be used in production with YUYV frames. Further calibration on your specific Pi hardware is recommended but optional.

**Final Calibrated HSV Ranges** (Nov 9, 2025):

```python
# Player (Yellow-Green point) - FINAL CALIBRATED
# Based on 20-sample ground truth validation
# Achieved 100% detection rate on PNG samples, 0.79ms avg performance
PLAYER_HSV_LOWER = (26, 67, 64)    # H:26-85 (yellow-green to cyan), S≥67, V≥64
PLAYER_HSV_UPPER = (85, 255, 255)  # Extended hue range captures actual player dot colors

# Other Player (Red point) - FINAL CALIBRATED
# Red wraps around HSV hue (0-10 and 165-180)
# Tightened S/V thresholds eliminate false positives (100% precision achieved)
OTHER_PLAYER_HSV_LOWER_1 = (0, 100, 100)     # S≥100, V≥100 (stricter than before)
OTHER_PLAYER_HSV_UPPER_1 = (10, 255, 255)    # Narrowed from 0-12 to 0-10
OTHER_PLAYER_HSV_LOWER_2 = (165, 100, 100)   # S≥100, V≥100 (stricter than before)
OTHER_PLAYER_HSV_UPPER_2 = (180, 255, 255)   # Narrowed from 168-180 to 165-180
```

**Calibration Results** (Nov 9, 2025):
- **Player Detection**: 100% detection rate (20/20 samples)
- **Other Players**: 100% precision (0 false positives)
- **Performance**: 0.79ms average per frame (well within <15ms target for Pi 4)
- **Dataset**: 20 manually annotated ground truth samples
- **Algorithm**: HSV + size (4-16px) + circularity (≥0.71) + combined scoring

See `FINAL_CALIBRATION_RESULTS_2025-11-09.md` for complete validation methodology and results.

**Production Calibration Process** (on test Pi with YUYV):

**Automated Click-to-Calibrate Wizard**:
1. Access web UI remotely (http://test-pi.local:5050)
2. Navigate to "Object Detection Calibration" page
3. View live YUYV minimap frames (lossless PNG rendering)
4. Click on player dot in 5 different positions
5. System samples 3x3 pixel region around each click
6. Calculates HSV min/max with 20% safety margin
7. Preview detection mask before saving
8. Export config for production deployment

**Manual Tuning Process** (if auto-calibration insufficient):
1. Capture YUYV minimap frames to test Pi
2. Use remote HSV color picker tool (web UI)
3. Adjust ranges with real-time preview
4. Validate with 30-second live capture
5. Iterate until accuracy >90%

**YUYV Color Space Notes**:
- YUYV frames are uncompressed - colors more accurate than JPEG
- Video capture card may apply auto-gain/white-balance - test under actual lighting
- Game day/night cycles may affect brightness (use CLAHE normalization if needed)

### Blob Filtering Criteria

**✅ MULTI-STAGE FILTERING ENABLED** (Nov 9, 2025): The current implementation uses comprehensive filtering with strict thresholds based on empirical data from 20-sample validation.

**Player Blob** (Yellow-Green):
- **Size**: 4-16 pixels diameter (strict filtering re-enabled)
  - Minimum: 4px (eliminates tiny noise artifacts)
  - Maximum: 16px (excludes large UI elements)
  - Preferred range: 4-10px (weighted in scoring algorithm)
- **Circularity**: ≥ 0.71 (stricter than previous 0.6)
- **Aspect Ratio**: 0.5-2.0 (reject elongated shapes)
- **Selection**: Combined scoring (see algorithm below, not "closest to center")
- **Ring Validation**: DISABLED (multi-stage filtering is sufficient)

**Other Player Blob** (Red):
- **Size**: 4-80 pixels diameter (separate threshold - red dots are larger)
  - Minimum: 4px (eliminates noise)
  - Maximum: 80px (based on empirical maximum observed)
- **Circularity**: ≥ 0.65 (strict filtering)
- **Aspect Ratio**: 0.5-2.0 (reject elongated shapes)
- **Count**: 0 or more (boolean: any detected?)
- **Ring Validation**: DISABLED (multi-stage filtering is sufficient)

**Rationale**: The implementation uses a **8-stage filtering pipeline**:
1. **HSV color matching** (removes 99% of non-marker pixels)
2. **Morphological operations** (erosion/dilation to clean noise)
3. **Size filtering** (eliminates artifacts and oversized elements)
4. **Circularity filtering** (ensures round blob shapes)
5. **Aspect ratio filtering** (rejects elongated false positives)
6. **Contrast validation** (optional, disabled by default)
7. **Combined scoring** (for player selection - see next section)
8. **Temporal smoothing** (reduces position jitter)

**Why Size Filtering Was Re-Enabled** (Nov 9, 2025):
- Separate thresholds for yellow (4-16px) vs red (4-80px) based on empirical data
- Red dots consistently larger than yellow in all test scenarios
- Tight size bounds eliminate most false positives while preserving true detections
- Combined with other filters, achieved 100% detection with 0 false positives

### Position Coordinate System

**Reference Frame**: Top-left of minimap region (68, 56) is origin (0, 0)

```
Minimap Region (340x86)
┌────────────────────────────┐  ← (0, 0) relative to minimap
│                            │
│       ●  (player)          │  ← (x, y) position
│                            │
│   ●      ●  (other_player) │
│                            │
└────────────────────────────┘  ← (340, 86) bottom-right
```

**Output Format**:
```python
{
    "player": {
        "detected": True,
        "x": 120,          # Pixels from left edge of minimap
        "y": 45,           # Pixels from top edge of minimap
        "confidence": 0.85  # Circularity score (0-1, higher = rounder blob)
    },
    "other_players": {
        "detected": True,   # Boolean: any other players?
        "count": 2          # Optional: how many detected
    }
}
```

### Player Selection Algorithm (Combined Scoring)

**⚠️ BREAKING CHANGE** (Nov 9, 2025): The player selection algorithm changed from "closest to center" to **combined scoring** for improved accuracy.

**Previous Approach** (before Nov 9):
```python
# Old: Select blob closest to center of minimap
frame_center = (frame.width // 2, frame.height // 2)
best_blob = min(blobs, key=distance_to_center)
```

**Current Approach** (Nov 9, 2025):
```python
# New: Select blob with highest combined score
def combined_score(blob):
    size_score = calculate_size_score(blob['diameter'])  # Prefer 4-10px
    return (size_score *
            float(blob['saturation']) *
            float(blob['value']) *
            blob['circularity'])

best_blob = max(blobs, key=combined_score)
```

**Combined Score Components**:

1. **Size Score** (0.1-1.0):
   - Returns `1.0` for blobs in preferred range: **4-10px diameter**
   - Penalizes smaller blobs proportionally: `score = diameter / preferred_min`
   - Penalizes larger blobs inversely: `score = 1.0 / (1.0 + excess / preferred_max)`
   - Ensures dots at typical size are prioritized over edge cases

2. **Saturation** (0-255):
   - Sampled at blob center from HSV frame
   - Higher saturation = more vivid color = more likely a marker
   - Helps distinguish player dots (bright yellow) from desaturated UI elements

3. **Value/Brightness** (0-255):
   - Sampled at blob center from HSV frame
   - Higher value = brighter blob = more visible marker
   - Eliminates dim false positives from background elements

4. **Circularity** (0-1):
   - Calculated as `4π × area / perimeter²`
   - Perfect circle = 1.0, irregular shape = lower
   - Already filtered to ≥0.71, but higher scores still preferred

**Why Combined Scoring?**

| Scenario | Closest-to-Center | Combined Scoring |
|----------|-------------------|------------------|
| Player at edge, UI element at center | ❌ Selects UI element | ✅ Selects player (higher S/V) |
| Multiple yellow blobs (debris, effects) | ❌ Picks nearest, might be artifact | ✅ Picks most marker-like blob |
| Oversized blob near center | ❌ Might select large false positive | ✅ Penalized by size_score |
| Small distant dot vs large close artifact | ❌ Depends on position only | ✅ Balances size, color, shape |

**Empirical Results** (Nov 9 validation):
- **100% detection rate** on 20-sample validation set
- **0 false positives** (combined scoring eliminated all UI element misdetections)
- **Robust to edge cases** (player at minimap edge, multiple yellow elements)
- **Average confidence**: 0.75-0.85 (high-quality detections)

**Tuning Parameters**:
```python
# In object_detection.py - _calculate_size_score()
preferred_min = 4.0   # Lower bound of preferred size (px)
preferred_max = 10.0  # Upper bound of preferred size (px)

# Adjust these if:
# - Player dots consistently smaller (e.g., zoom changes): lower preferred_min/max
# - Player dots consistently larger: raise preferred_min/max
# - Need to favor size over color: increase size_score weight in formula
```

**Migration Notes**:
- Old configs using "closest to center" will automatically use combined scoring after code update
- No config file changes needed - algorithm change is transparent
- If experiencing issues, verify HSV ranges capture player dot colors (S>67, V>64)

## Implementation Structure

### File: `msmacro/cv/object_detection.py`

```python
"""
Minimap object detection for player and other_player positions.

Detects colored points (yellow=player, red=other_player) on minimap
and returns position information for automated navigation.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
import cv2
import numpy as np


@dataclass
class PlayerPosition:
    """Player position on minimap."""
    detected: bool
    x: int  # X coordinate relative to minimap top-left
    y: int  # Y coordinate relative to minimap top-left
    confidence: float = 0.0


@dataclass
class OtherPlayersStatus:
    """Other players detection status."""
    detected: bool  # True if any other players present
    count: int = 0  # Number of other players detected


@dataclass
class DetectionResult:
    """Complete detection result."""
    player: PlayerPosition
    other_players: OtherPlayersStatus
    timestamp: float  # Unix timestamp


class MinimapObjectDetector:
    """Detects player and other_player objects on minimap."""
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize detector with color ranges and filter parameters.
        
        Args:
            config: Optional configuration dict with:
                - player_hsv_range: ((h_min, s_min, v_min), (h_max, s_max, v_max))
                - other_player_hsv_ranges: [((h_min, s_min, v_min), (h_max, s_max, v_max)), ...]
                - min_blob_size: Minimum blob diameter in pixels
                - max_blob_size: Maximum blob diameter in pixels
                - min_circularity: Minimum circularity (0-1)
        """
        pass
    
    def detect(self, frame: np.ndarray) -> DetectionResult:
        """
        Detect objects in minimap frame.
        
        Args:
            frame: BGR image (cropped minimap region)
        
        Returns:
            DetectionResult with player position and other_players status
        """
        pass
    
    def _detect_player(self, frame: np.ndarray) -> PlayerPosition:
        """Detect yellow player point."""
        pass
    
    def _detect_other_players(self, frame: np.ndarray) -> OtherPlayersStatus:
        """Detect red other_player points."""
        pass
    
    def _filter_blobs(self, contours, min_size, max_size, min_circularity):
        """Filter contours by size and shape."""
        pass
    
    def visualize(self, frame: np.ndarray, result: DetectionResult) -> np.ndarray:
        """
        Draw detection results on frame for debugging.
        
        Args:
            frame: Original frame
            result: Detection result
        
        Returns:
            Frame with detection visualization
        """
        pass
```

## Integration Points

### 1. CV Capture Loop

**File**: `msmacro/cv/capture.py`

Add detection to capture loop:
```python
# In _capture_loop method
if self._object_detection_enabled:
    detection_result = self.object_detector.detect(minimap_frame)
    self._last_detection_result = detection_result
    
    # Emit event for frontend
    emit("OBJECT_DETECTED", detection_result.to_dict())
```

### 2. API Endpoints

**File**: `msmacro/web/handlers.py`

New endpoints:
- `GET /api/cv/object-detection/status` - Get latest detection result
- `POST /api/cv/object-detection/start` - Enable object detection
- `POST /api/cv/object-detection/stop` - Disable object detection
- `POST /api/cv/object-detection/config` - Update detection configuration

### 3. Daemon Commands

**File**: `msmacro/daemon_handlers/cv_commands.py`

New IPC commands:
- `object_detection_status` - Get current detection state
- `object_detection_start` - Enable detection
- `object_detection_stop` - Disable detection
- `object_detection_config` - Update config

### 4. Playback Integration

**File**: `msmacro/core/player.py`

Position-based adjustments during playback:
```python
# During macro playback
current_position = get_player_position()
if current_position.detected:
    # Adjust rotation based on position drift
    position_error = calculate_error(current_position, expected_position)
    correction_keystroke = calculate_correction(position_error)
    inject_keystroke(correction_keystroke)
```

## Configuration System

### Environment Variables

```bash
# Enable object detection
export MSMACRO_OBJECT_DETECTION_ENABLED=true

# Player color range (HSV) - PLACEHOLDER for development
# Final values calibrated on test Pi with YUYV
export MSMACRO_PLAYER_COLOR_H_MIN=15
export MSMACRO_PLAYER_COLOR_H_MAX=40
export MSMACRO_PLAYER_COLOR_S_MIN=60
export MSMACRO_PLAYER_COLOR_V_MIN=80

# Other player color ranges (supports multiple ranges for red wrap-around)
# PLACEHOLDER - calibrate on test Pi
export MSMACRO_OTHER_PLAYER_COLOR_RANGES="0,12,70,70,255,255;168,180,70,70,255,255"

# Blob filtering
export MSMACRO_BLOB_MIN_SIZE=3
export MSMACRO_BLOB_MAX_SIZE=15
export MSMACRO_BLOB_MIN_CIRCULARITY=0.6

# Optional brightness normalization (for day/night cycles)
export MSMACRO_NORMALIZE_BRIGHTNESS=false
```

### Config File

`~/.local/share/msmacro/object_detection_config.json`:
```json
{
  "enabled": true,
  "calibration_source": "test-pi-2025-01-07",
  "player": {
    "color_range": {
      "hsv_lower": [15, 60, 80],
      "hsv_upper": [40, 255, 255]
    },
    "blob_size_min": 3,
    "blob_size_max": 15,
    "circularity_min": 0.6
  },
  "other_players": {
    "color_ranges": [
      {
        "hsv_lower": [0, 70, 70],
        "hsv_upper": [12, 255, 255]
      },
      {
        "hsv_lower": [168, 70, 70],
        "hsv_upper": [180, 255, 255]
      }
    ],
    "blob_size_min": 3,
    "blob_size_max": 15,
    "circularity_min": 0.5
  },
  "performance": {
    "detection_interval_ms": 100,
    "max_fps": 10
  },
  "preprocessing": {
    "normalize_brightness": false,
    "clahe_clip_limit": 2.0,
    "clahe_tile_grid_size": [4, 4]
  }
}
```

## Remote Calibration System

### Why Remote Calibration?

Raspberry Pi devices typically run headless (no monitor). HSV color tuning requires visual feedback, so calibration must happen entirely through the web UI.

### Click-to-Calibrate Wizard (Automated)

**Purpose**: Simplify calibration by auto-generating HSV ranges from user clicks

**Workflow**:
1. User accesses web UI: `http://test-pi.local:5050/calibration`
2. Page displays live YUYV minimap frames (rendered as PNG, lossless)
3. Zoom controls: 200-400% zoom for precise clicking
4. User clicks on **player dot** in 5 different positions/scenarios
5. System samples 3x3 pixel region around each click
6. Converts sampled pixels to HSV, calculates percentile ranges
7. Adds 20% safety margin to min/max values
8. Displays preview: original frame + detection mask overlay
9. User validates or re-clicks if detection poor
10. Exports config JSON for download or direct save to production Pi

**Auto-Calibration Algorithm**:
```python
def auto_calibrate(frames: List[np.ndarray], clicks: List[Tuple[int, int]]):
    """
    Generate HSV ranges from user clicks.

    Args:
        frames: YUYV minimap frames (converted to BGR)
        clicks: (x, y) positions where user clicked player

    Returns:
        (hsv_lower, hsv_upper) tuple
    """
    hsv_samples = []
    for frame, (x, y) in zip(frames, clicks):
        # Sample 3x3 region
        region = frame[max(0,y-1):y+2, max(0,x-1):x+2]
        hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        hsv_samples.extend(hsv_region.reshape(-1, 3))

    # Calculate 5th-95th percentile (reject outliers)
    hsv_array = np.array(hsv_samples)
    hsv_min = np.percentile(hsv_array, 5, axis=0)
    hsv_max = np.percentile(hsv_array, 95, axis=0)

    # Add 20% safety margin
    margin = (hsv_max - hsv_min) * 0.2
    hsv_lower = np.maximum(hsv_min - margin, [0, 0, 0])
    hsv_upper = np.minimum(hsv_max + margin, [179, 255, 255])

    return (tuple(hsv_lower.astype(int)), tuple(hsv_upper.astype(int)))
```

### Manual HSV Tuning Interface (Fallback)

**Purpose**: Fine-tune ranges if auto-calibration insufficient

**UI Components**:
- Live YUYV frame viewer (auto-refresh 500ms)
- 6 sliders per color: H min/max, S min/max, V min/max
- Real-time detection mask preview
- Split view: original frame | mask | overlay
- Confidence metrics: blob count, circularity, position stability
- Save/Load config buttons
- Reset to auto-calibrated defaults

### Config Export/Import

**Export**:
- Generates JSON file with calibration metadata
- Includes: HSV ranges, blob params, timestamp, Pi device ID
- Download to local machine
- Direct copy to production Pi via API

**Import**:
- Upload JSON to production Pi
- Validates schema before applying
- Option to test on 30-second capture before commit
- Rollback to previous config if accuracy < 80%

### Live Validation Dashboard

**Purpose**: Monitor detection quality during calibration

**Metrics Displayed**:
- Detection rate: % of frames with player detected
- Position stability: std deviation of (x, y) over 5 seconds
- Confidence: average circularity score
- False positive rate: detections outside expected minimap region
- Performance: average detection latency (ms)

**Real-time Visualization**:
- Minimap stream with detection overlays
- Green circle: player detected (radius = confidence)
- Red circles: other players (count displayed)
- Position trace: last 30 positions shown as line
- Alerts: red border if detection fails for >2 seconds

## Performance Considerations

### Target Latency

- **Detection Time**: < 15ms per frame (YUYV on Pi 4)
- **Update Rate**: 2 Hz (500ms intervals, matches existing capture loop)
- **Total Latency**: < 200ms (detection + IPC + keystroke injection)

### YUYV Processing Pipeline (Pi 4)

**Critical Optimization**: Crop minimap region **before** color conversion

```python
# SLOW (processes full 1280x720 frame):
yuyv_full = capture_frame()  # 1280x720 = 921,600 pixels
bgr_full = cv2.cvtColor(yuyv_full, cv2.COLOR_YUV2BGR_YUYV)  # 8ms
minimap = bgr_full[56:142, 68:408]  # Crop after conversion

# FAST (processes only minimap 340x86):
yuyv_full = capture_frame()
minimap_yuyv = yuyv_full[56:142, 68:408]  # Crop first (29,240 pixels)
minimap_bgr = cv2.cvtColor(minimap_yuyv, cv2.COLOR_YUV2BGR_YUYV)  # 1ms
```

**Savings**: Cropping before conversion saves ~7ms on Pi 4

### CPU Impact Estimates (YUYV on Pi 4)

| Operation | Time (Pi 4) | Time (PC) | Notes |
|-----------|-------------|-----------|-------|
| YUYV crop (340x86) | <1ms | <1ms | Slice operation |
| YUYV → BGR | 1ms | <1ms | Small region only |
| BGR → HSV | 1ms | <1ms | On cropped region |
| Color masking (yellow) | 1ms | <1ms | Single inRange() |
| Color masking (red, 2x) | 2ms | <1ms | Two inRange() + OR |
| Morphological ops | 2-3ms | 1ms | 3x3 kernel on 340x86 |
| Contour detection | 2-4ms | 1ms | Few contours expected |
| Blob filtering | <1ms | <1ms | Python loops |
| Temporal filtering (EMA) | <1ms | <1ms | Simple math |
| **Total** | **11-14ms** | **<5ms** | Well under 500ms budget |

**Headroom**: Detection runs every 500ms (capture loop frequency), so 11-14ms is only 2.2-2.8% CPU usage.

### Optimization Strategies

1. **Region Cropping First** (implemented in capture.py already)
   - Crop minimap from full frame before any processing
   - Reduces pixel count by 96% (1280x720 → 340x86)
   - Saves ~7ms on color conversion

2. **Skip Frame Detection** (if needed)
   - Capture runs at 2 FPS (500ms intervals)
   - Can detect every other frame → 1 Hz update rate
   - Still acceptable for position-based navigation

3. **GPU Acceleration** (future)
   - Use cv2.UMat instead of np.ndarray
   - Offloads operations to VideoCore GPU (if available on Pi 4)
   - Potential 2-3x speedup

4. **Adaptive Quality** (if CPU > 80%)
   - Disable optional preprocessing (CLAHE normalization)
   - Reduce morphological kernel size (3x3 → none)
   - Skip temporal filtering (use raw detections)

5. **YUYV → HSV Direct Conversion** (future optimization)
   - Skip BGR intermediate step
   - Custom YUV→HSV math
   - Potential 1-2ms savings

## Testing Strategy

### Phase 0: Test Pi Setup (PREREQUISITE)

**Goal**: Prepare test Pi for YUYV calibration

**Status**: ⚠️ **REQUIRES USER ACTION**

**Requirements**:
- Raspberry Pi 4 (separate from production device)
- Video capture card installed
- msmacro daemon running
- Web UI accessible remotely (http://test-pi.local:5050)

**Tasks**:
1. ✅ Deploy object detection code to test Pi (code ready)
2. ✅ Verify CV capture working with YUYV input (implementation complete)
3. ✅ Test web UI access from development machine (endpoints ready)
4. ❌ Create YUYV dataset capture script (**not implemented** - manual frame capture required)

### Phase 1: Algorithm Development (Local/PC with JPEG)

**Goal**: Develop detection logic without Pi hardware

**Status**: ✅ **COMPLETE**

**Input**: JPEG test images (compressed, approximation only)

1. ✅ **Use existing test image**:
   - Example: `docus/archived/msmacro_cv_frame_object_recognize.jpg`
   - Understand this is JPEG-compressed (colors differ from YUYV)
   - HSV ranges are **placeholders** only

2. ✅ **Develop detection algorithm**:
   - `msmacro/cv/object_detection.py` (778 lines, fully implemented)
   - Blob detection and filtering complete
   - Tested with JPEG samples
   - Wide HSV tolerances configured (expect recalibration)

3. ✅ **Algorithm validation** (logic only, not color accuracy):
   - Unit tests framework in place (tests/cv/test_object_detection.py)
   - Blob filtering correctness validated
   - Temporal smoothing logic implemented
   - Visualization tools working (visualize(), debug_masks())

**Success Criteria**: ✅ **ALL MET**
- ✅ Detection logic implemented
- ✅ Unit tests framework ready
- ✅ No expectations for color accuracy (deferred to Phase 2)

### Phase 2: YUYV Calibration (Test Pi)

**Goal**: Calibrate color detection for real YUYV frames

**Status**: ✅ **TOOLS READY** - ⚠️ **MANUAL CALIBRATION REQUIRED**

**Input**: Raw YUYV frames from Raspberry Pi capture card

**Critical**: This phase must happen on test Pi, not development machine

1. **Create YUYV test dataset** - ⚠️ **MANUAL PROCESS**:
   - ❌ Script: `scripts/capture_yuyv_dataset.py` (**not implemented**)
   - ⚠️ **Manual**: Capture 50+ minimap frames using web UI or frame buffer
   - Scenarios:
     - Player alone, various positions (15 frames)
     - Player at edges/corners (10 frames)
     - Player + 1 other (10 frames)
     - Player + 2-3 others (10 frames)
     - Player + 5+ others (crowded, 5 frames)
     - Different lighting (day/night if applicable, 10 frames)
   - ⚠️ **Manual**: Save frames manually (no automated `.yuv` export)

2. **Ground truth annotation** - ❌ **NOT IMPLEMENTED**:
   - ❌ Tool: `scripts/annotate_ground_truth.py` (**not implemented**)
   - ⚠️ **Manual**: Visual validation only via detection-preview endpoint
   - No automated ground truth comparison

3. ✅ **Auto-calibration** - **FULLY FUNCTIONAL**:
   - ✅ Use click-to-calibrate wizard (web UI)
   - ✅ User clicks player in 5 representative frames
   - ✅ System generates HSV ranges automatically (percentile-based)
   - ✅ Preview detection mask before saving

4. **Validation** - ⚠️ **MANUAL PROCESS**:
   - ⚠️ **Manual**: Visual inspection using detection-preview endpoint
   - ❌ No automated ground truth comparison
   - Target Metrics (manual validation):
     - Player detection: aim for visible detection in >90% of frames
     - Position accuracy: visually validate alignment
     - Other players: check red dots appear when enemies present
   - ✅ Performance: Automatic tracking via `/api/cv/object-detection/performance`

**Gate**: ⚠️ **MANUAL VALIDATION** - Visually verify >90% accuracy before proceeding to Phase 3

### Phase 3: Integration Testing (Test Pi)

**Goal**: Integrate with capture loop and validate stability

**Status**: ✅ **INTEGRATION COMPLETE** - ⚠️ **STABILITY TESTING MANUAL**

1. ✅ **Enable in capture**:
   - ✅ Detector integrated into `CVCapture` (capture.py lines 89-953)
   - ✅ Detection runs on live frames every 500ms
   - ✅ Results logged via daemon logger

2. ✅ **Verify performance** - **AUTOMATIC TRACKING**:
   - ✅ Monitor CPU usage via performance endpoint
   - ✅ Check latency via performance stats (avg/max/min timing)
   - ✅ Frame drops tracked (capture loop maintains 2 FPS)

3. ✅ **API testing** - **COMPLETE**:
   - ✅ All 10 endpoints implemented and functional
   - ✅ SSE events working (OBJECT_DETECTED)
   - ✅ Frontend integration complete (ObjectDetection.jsx, CalibrationWizard.jsx)

4. **Stability testing** - ⚠️ **MANUAL MONITORING REQUIRED**:
   - ⚠️ **Manual**: Run 24 hours continuous on test Pi
   - ⚠️ **Manual**: Monitor for memory leaks (use system tools)
   - ⚠️ **Manual**: Check detection accuracy over time (visual validation)

### Phase 4: Production Deployment

**Goal**: Deploy to production Pi after validation

**Status**: ✅ **DEPLOYMENT TOOLS READY** - ⚠️ **REQUIRES CALIBRATED CONFIG**

1. ✅ **Config export** - **FULLY FUNCTIONAL**:
   - ✅ Export calibrated HSV ranges from test Pi via web UI
   - ✅ Config JSON includes metadata (timestamp, device ID, HSV ranges)

2. ✅ **Production deployment** - **TOOLS READY**:
   - ✅ Import config to production Pi via web UI or file copy
   - ✅ Enable detection in capture loop via API
   - ⚠️ **Manual**: Monitor for 24 hours before enabling auto-corrections

3. **Monitoring** - ⚠️ **PARTIALLY AUTOMATED**:
   - ✅ Track performance (CPU, latency) via performance endpoint
   - ⚠️ **Manual**: Track detection rate (no automated metrics)
   - ⚠️ **Manual**: Alert if accuracy drops (no automated rollback)

### Phase 5: Playback Integration

**Goal**: Use detection for position-based control

**Status**: ❌ **NOT IMPLEMENTED** - Future work

1. ❌ **Position tracking**:
   - Log player positions during gameplay (no logging system)
   - Calculate position stability (no stability metrics)
   - Detect drift/jitter (no drift detection)

2. ❌ **Correction logic**:
   - Implement position error calculation (not implemented)
   - Map errors to correction keystrokes (no mapping logic)
   - Test with simple macros (no integration with player.py)

3. ❌ **Full automation**:
   - Run recorded macros with corrections (not implemented)
   - Measure success rate (no success metrics)
   - Refine correction parameters (no parameter tuning)

**Future Work**: Position data is available via detection API, but integration with macro playback system (`core/player.py`) is not yet implemented.

## Development Roadmap

### Milestone 1: Core Detection Logic (Week 1)
- [ ] Implement `MinimapObjectDetector` class
- [ ] Color-based blob detection for player
- [ ] Color-based blob detection for other_players
- [ ] Blob filtering (size, circularity)
- [ ] Unit tests with sample images
- [ ] Documentation

### Milestone 2: Integration (Week 2)
- [ ] Add to `CVCapture` class
- [ ] Daemon IPC commands
- [ ] API endpoints
- [ ] Frontend API client
- [ ] SSE event support
- [ ] Configuration management

### Milestone 3: UI (Week 3)
- [ ] Detection status page
- [ ] Real-time position display
- [ ] Color tuning interface
- [ ] Detection visualization
- [ ] Configuration editor

### Milestone 4: Playback Integration (Week 4)
- [ ] Position error calculation
- [ ] Correction keystroke mapping
- [ ] Inject corrections during playback
- [ ] Performance tuning
- [ ] Documentation

## Debugging Tools

### 1. Visualization Script

Create `scripts/debug_object_detection.py`:
```python
"""Debug object detection with live visualization."""
import cv2
from msmacro.cv.object_detection import MinimapObjectDetector

detector = MinimapObjectDetector()

# Read minimap frame
frame = cv2.imread("/path/to/minimap.jpg")

# Detect
result = detector.detect(frame)

# Visualize
vis_frame = detector.visualize(frame, result)

# Display
cv2.imshow("Detection", vis_frame)
cv2.waitKey(0)
```

### 2. HSV Color Picker

Create interactive tool to select color ranges:
```python
"""Interactive HSV range picker for color tuning."""
import cv2
import numpy as np

def nothing(x):
    pass

# Load sample frame
frame = cv2.imread("minimap_sample.jpg")
cv2.namedWindow("HSV Picker")

# Sliders for HSV range
cv2.createTrackbar("H Min", "HSV Picker", 0, 179, nothing)
cv2.createTrackbar("H Max", "HSV Picker", 179, 179, nothing)
# ... etc

while True:
    # Read trackbar values
    # Apply mask
    # Display result
    pass
```

### 3. Performance Profiler

Add timing decorators:
```python
import time
from functools import wraps

def profile(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"{func.__name__}: {elapsed:.2f}ms")
        return result
    return wrapper
```

## Known Challenges & Solutions

### Challenge 1: Color Variance
**Problem**: Compressed images may alter colors
**Solution**: Use wide HSV ranges + morphological operations to fill gaps

### Challenge 2: Overlapping Points
**Problem**: Player and other_player points may overlap
**Solution**: Use hierarchical detection (player first, mask it, then detect others)

### Challenge 3: False Positives
**Problem**: UI elements may match colors
**Solution**: Strict circularity filtering + position priors (expected minimap area)

### Challenge 4: Low FPS Impact
**Problem**: Detection may slow down capture
**Solution**: Skip frame detection (detect every 3rd frame) or async detection

## Related Documentation

- `04_DETECTION_ALGORITHM.md` - General CV detection approach
- `06_MAP_CONFIGURATION.md` - Minimap region configuration
- `07_SYSTEM_MONITORING.md` - Performance monitoring
- `msmacro/cv/region_analysis.py` - Region-based analysis utilities

## Success Metrics

### Detection Accuracy (⚠️ MANUAL VALIDATION TARGETS)

**Target Metrics** (on YUYV frames from test Pi):
- Player detection: aim for > 90% visible detection in frames
- Other players detection: aim for > 85% visible detection
- Position accuracy: visually validate < 5 pixels alignment
- Gate: ⚠️ **MANUAL** visual validation before production deployment

**⚠️ NOTE**: Automated accuracy metrics (precision, recall, position error) are NOT implemented. Validation relies on visual inspection using detection-preview endpoint and manual observation during gameplay.

### Performance (✅ AUTOMATED TRACKING)

**Target Metrics** (Pi 4 with YUYV):
- Detection latency: < 15ms per frame ✅ **Automatically tracked**
- CPU overhead: < 3% on Raspberry Pi 4 (11-14ms per 500ms) ✅ **Monitored via performance endpoint**
- No frame drops during detection (maintain 2 FPS capture rate) ✅ **Tracked in capture loop**

**Monitoring**: All performance metrics available via `/api/cv/object-detection/performance` endpoint with real-time statistics (avg/max/min timing).

### Usability (✅ FULLY IMPLEMENTED)

- ✅ Remote calibration via web UI (no monitor needed)
- ✅ Click-to-calibrate wizard for easy HSV tuning (5-sample auto-calibration)
- ✅ Config export/import between test and production Pi (JSON with metadata)
- ✅ Real-time visualization (detection-preview endpoint with full overlays)
- ✅ Clear error messages and troubleshooting hints in UI
- ⚠️ Manual HSV slider tuning: Not implemented (auto-calibration only)

---

**Document Version**: 3.2
**Last Updated**: 2025-11-09
**Status**: ✅ **IMPLEMENTED** - Core Features Complete, **Calibration Required for Production**

**Key Changes in v3.1** (2025-11-08):
- ✅ **Truly lossless calibration**: Raw minimap capture before JPEG compression (eliminates artifacts)
- ✅ **Full detection visualization**: Backend-rendered overlays for player + all other players
- ✅ **Enhanced debugging**: Positions array for other players, detection preview endpoint
- ✅ **Improved UI**: Full-width calibration previews, better object detection display

**Key Changes in v3.0**:
- ✅ Core detection implemented (`object_detection.py`)
- ✅ Integration with capture loop complete
- ✅ API endpoints functional
- ✅ Frontend components implemented (ObjectDetection.jsx, CalibrationWizard.jsx)
- ✅ Remote calibration system working
- ✅ Minimap region constraint enforced (detection only in selected region)
- ✅ Coordinate system clarified (relative to minimap top-left)

**Current State**:
- Detection algorithm: ✅ Fully functional with position tracking for all objects
- Calibration wizard: ✅ Truly lossless (uses raw minimap before JPEG compression)
- API endpoints: ✅ All operational + 2 new endpoints (raw-minimap, detection-preview)
- Performance: ✅ < 15ms on Pi 4 (target met)
- Coordinate system: ✅ Minimap-relative (0,0 at top-left)
- Visualization: ✅ Full backend-rendered overlays for debugging
- HSV ranges: ⚠️ **PLACEHOLDERS** - require YUYV calibration before production use
- Automated validation: ❌ Not implemented (manual validation required)
- Playback integration: ❌ Not implemented (future work)

---

## Implementation Status (v3.2 - 2025-11-09)

### ✅ Fully Implemented Features

**Core Detection**:
- HSV color-based blob detection for player (yellow) and other players (red)
- Circularity-based filtering (>0.6 for player, >0.5 for other players)
- Temporal smoothing with Exponential Moving Average (EMA)
- Position tracking for all detected objects (x, y coordinates)
- Minimap-relative coordinate system (0,0 at top-left)

**Calibration System**:
- Truly lossless calibration (raw minimap capture before JPEG compression)
- Auto-calibration from user clicks (5 samples, 3×3 pixel regions)
- Percentile-based HSV range calculation with 20% safety margin
- Real-time preview with detection mask overlay
- Config persistence (file, environment variables, runtime)

**Integration**:
- Full integration with CV capture loop (2 FPS, 500ms intervals)
- All IPC daemon commands (status, start, stop, config, calibrate)
- Complete web API endpoints (10 endpoints including raw-minimap, detection-preview)
- Frontend components (ObjectDetection.jsx, CalibrationWizard.jsx)
- SSE events for real-time updates

**Performance**:
- < 15ms detection latency on Raspberry Pi 4 (target met)
- ~88KB memory overhead for raw minimap storage
- Performance tracking (avg/max/min timing statistics)

### ❌ Not Implemented (Future Work)

**Automated Validation**:
- Ground truth annotation tools (`scripts/annotate_ground_truth.py`)
- YUYV test dataset capture scripts (`scripts/capture_yuyv_dataset.py`)
- Automated accuracy metrics (precision, recall, position error)
- Accuracy thresholds and automated rollback (< 80% accuracy)
- 24-hour stability testing automation

**Playback Integration**:
- Position-based macro corrections during playback
- Position error calculation and correction keystroke mapping
- Auto-pathing logic based on player position

**Advanced UI**:
- Manual HSV slider-based tuning interface (only auto-calibration available)
- Live validation dashboard with real-time metrics
- Validation gate enforcement (90% precision requirement)

### 🟡 Implementation Deviations from Original Design

**Size Filtering - DISABLED**:
- **Original Design**: 3-15 pixels diameter
- **Current Implementation**: 1-100 pixels (effectively unlimited)
- **Rationale**: HSV color matching and circularity filtering are sufficient. Size varies significantly across game scenarios, making strict size filtering unreliable.

**Ring Validation - DISABLED**:
- **Original Design**: Dark ring + white ring detection for additional validation
- **Current Implementation**: Code present but disabled
- **Rationale**: Circularity score alone proved robust in real-world testing. Ring validation added complexity without significant accuracy improvement.

**Validation Workflow - MANUAL**:
- **Original Design**: Automated 90% precision gate before production deployment
- **Current Implementation**: Manual validation via visual inspection and detection-preview endpoint
- **Rationale**: Ground truth annotation tools deferred as future work. Manual validation sufficient for initial deployment.

### 🚀 Deployment Requirements

**Before Production Use - MANDATORY**:
1. ✅ **Hardware**: Test Raspberry Pi 4 with video capture card (separate from production device)
2. ⚠️ **Calibration**: Run CalibrationWizard on test Pi with real YUYV frames (HSV ranges are PLACEHOLDERS)
3. ⚠️ **Validation**: Manually verify detection accuracy > 90% with live gameplay
4. ✅ **Config Export**: Export calibrated config from test Pi to production Pi
5. ✅ **Monitoring**: Track performance via `/api/cv/object-detection/performance` endpoint

**Optional - Recommended**:
- Capture 50+ YUYV test frames for reproducibility
- Document calibration conditions (lighting, time of day)
- Test different game scenarios (crowded minimap, edges, corners)
- Monitor for 24 hours before enabling auto-corrections in playback

---

## Recent Improvements (v3.1 - 2025-11-08)

### 1. Truly Lossless Calibration

**Problem**: The previous calibration flow used JPEG-compressed frames, causing color artifacts that affected HSV range accuracy.

**Solution**:
- **Raw minimap capture** in `capture.py`: Extract and store minimap crop BEFORE JPEG encoding
- **Memory overhead**: Only ~88KB for typical 340x86 minimap (acceptable)
- **New endpoint**: `/api/cv/raw-minimap` serves truly lossless PNG data
- **Updated wizard**: `CalibrationWizard.jsx` now uses raw-minimap endpoint

**Result**: Calibration now uses pixel-perfect raw data with ZERO compression artifacts, dramatically improving HSV range accuracy for production deployment.

### 2. Enhanced Detection Visualization

**Problem**: Only the player dot was visualized in the UI. Other players' detections weren't shown, making it impossible to debug red-dot detection accuracy visually.

**Solution**:
- **Positions tracking**: `OtherPlayersStatus` now stores all detected positions as `[(x, y), ...]`
- **Enhanced visualize()**: Draws all other players with red circles + crosshairs
- **New endpoint**: `/api/cv/detection-preview` returns minimap with full backend-rendered overlays
- **Updated component**: `ObjectDetection.jsx` uses detection-preview for live debugging

**Visualization includes**:
- Player: Yellow crosshair (10px) + circle (8px) + confidence label
- Other players: Red circles (6px) + crosshairs (8px) at each position
- Stats: Frame count, detection count

**Result**: Users can now visually validate detection accuracy for both player and other players in real-time, with precise position markers.

### 3. UI Improvements

**Problem**: Calibration preview images didn't stretch to full width on larger screens, staying ~340px wide.

**Solution**:
- Added `w-full h-auto` classes to preview images in `CalibrationWizard.jsx`
- Both "Original Frame" and "Detection Mask" now scale properly

**Result**: Better visibility during calibration, especially on wider screens.

### 4. API Enhancements

**New Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cv/raw-minimap` | GET | Truly lossless raw minimap (before JPEG compression) |
| `/api/cv/detection-preview` | GET | Minimap with detection visualization overlays |

**Updated Response Structure**:

`GET /api/cv/object-detection/status` now includes positions:
```json
{
  "other_players": {
    "detected": true,
    "count": 2,
    "positions": [
      {"x": 120, "y": 30},
      {"x": 200, "y": 50}
    ]
  }
}
```

### Implementation Files Modified

**Backend**:
- `msmacro/cv/frame_buffer.py` - Raw minimap storage
- `msmacro/cv/capture.py` - Extract raw crop before JPEG encoding
- `msmacro/cv/object_detection.py` - Positions tracking & enhanced visualization
- `msmacro/daemon_handlers/cv_commands.py` - `cv_get_raw_minimap` IPC command
- `msmacro/web/handlers.py` - Two new endpoints
- `msmacro/web/server.py` - Route registration

**Frontend**:
- `webui/src/components/ObjectDetection.jsx` - Use detection-preview endpoint
- `webui/src/components/CalibrationWizard.jsx` - Use raw-minimap + full-width previews

### Performance Impact

- **Memory**: +88KB per frame for raw minimap storage (negligible on modern systems)
- **CPU**: No additional overhead (raw crop extracted anyway for detection)
- **Network**: Same PNG size, but with better quality (no double-encoding)

### Migration Notes

**For Existing Deployments**:
- Backward compatible - old endpoints still work
- Calibration automatically uses new lossless endpoint
- Detection preview is opt-in (ObjectDetection component auto-updates)
- No config changes required

**Recommended Actions**:
1. Re-calibrate HSV ranges using new lossless endpoint for better accuracy
2. Use detection-preview endpoint to validate existing calibrations
3. Monitor detection accuracy with new visualization tools

---

**See Also**:
- `09_DATA_FLOW.md` - Complete data flow diagrams (updated for new endpoints)
- `06_MAP_CONFIGURATION.md` - Map config usage
- `05_API_REFERENCE.md` - API endpoints (includes new endpoints)
- `docs/MINIMAP_LOGIC_FIX.md` - Recent implementation fixes
