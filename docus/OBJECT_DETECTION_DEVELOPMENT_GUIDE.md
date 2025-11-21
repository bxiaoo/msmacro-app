# Object Detection Development Guide

## Overview

This guide explains how to use the new comprehensive development tools for improving the minimap object detection algorithm through multi-modal detection and higher resolution capture.

## Tools Created

### 1. High Resolution Capture Testing (`scripts/test_high_resolution_capture.py`)

Tests capture card capabilities at various resolutions (720p, 1080p, 2K, 4K).

**Features:**
- Tests multiple resolutions automatically
- Measures memory usage and processing time
- Calculates minimap pixel count improvements
- Saves sample images at each resolution
- Provides recommendations based on hardware capabilities

**Usage:**
```bash
# Auto-detect capture device and test all resolutions
python scripts/test_high_resolution_capture.py

# Specify device index
python scripts/test_high_resolution_capture.py --device 0

# Save sample images for inspection
python scripts/test_high_resolution_capture.py --save-samples samples/resolution_test/



















```

**Output:**
- Console report with metrics for each resolution
- Comparison table showing memory/performance trade-offs
- Recommendations for optimal resolution
- (Optional) Sample images at each resolution

**Example Output:**
```
Resolution           Frame       JPEG        Minimap          Capture
                     (MB)        (KB)        (pixels)         (ms)
----------------------------------------------------------------------
1280x720             2.70 (1.0x)  600.0 (1.0x)     29,240 (1.0x)    5.2
1920x1080            6.00 (2.2x)  1200 (2.0x)      65,790 (2.3x)    8.1
2560x1440           10.60 (3.9x)  2000 (3.3x)     116,960 (4.0x)   12.5
3840x2160           23.80 (8.8x)  4000 (6.7x)     263,160 (9.0x)   28.3
```

### 2. Comprehensive Object Marker (`scripts/comprehensive_object_marker.py`)

Interactive GUI tool for annotating minimap objects with comprehensive characteristics and testing multi-modal detection.

**Features:**
- **Multi-mode marking**: Position, Region, Comprehensive characteristics
- **Real-time HSV sampling**: Click to sample color values at any point
- **Multiple detection previews**: HSV color, Hough circles, edge detection
- **Auto-calibration**: Generate HSV ranges from marked positions
- **Ground truth export**: Save annotations for validation
- **Side-by-side comparison**: Manual markers vs auto-detection

**Usage:**
```bash
# Mark objects on a saved minimap image
python scripts/comprehensive_object_marker.py --image minimap.png

# Load NumPy array file
python scripts/comprehensive_object_marker.py --image minimap.npy

# Enable live HSV detector preview
python scripts/comprehensive_object_marker.py --image minimap.png --live-detector
```

**Keyboard Controls:**
- **Tab**: Cycle marking modes (Position → Region → Comprehensive)
- **Left-click**: Mark player/object
- **Right-click**: Mark enemy
- **Space**: Sample HSV values at cursor position
- **Delete/Backspace**: Remove nearest marker
- **'r'**: Reset all markers
- **'s'**: Save annotations to JSON
- **'c'**: Auto-calibrate HSV ranges from markers
- **'h'**: Toggle Hough circle detection overlay
- **'e'**: Toggle edge detection overlay
- **'t'**: Cycle detection methods (HSV → Hough → Edge → Combined)
- **'q'/Esc**: Quit

**Output Files:**
- `<image_name>.annotations.json`: Ground truth annotations with full characteristics

**Annotation JSON Format:**
```json
{
  "image": "minimap.png",
  "image_size": {"width": 340, "height": 86},
  "mode": "Comprehensive",
  "annotations": [
    {
      "type": "player",
      "id": 1,
      "x": 170,
      "y": 43,
      "hsv_h": 45,
      "hsv_s": 180,
      "hsv_v": 200,
      "shape": "circle",
      "radius": 5.0,
      "circularity": 0.87
    }
  ],
  "count": {
    "player": 1,
    "enemy": 2,
    "total": 3
  }
}
```

## Development Workflow

### Workflow 1: Resolution Testing and Optimization

**Goal**: Determine if higher resolution improves detection accuracy.

**Steps:**

1. **Test hardware capabilities**:
   ```bash
   python scripts/test_high_resolution_capture.py --save-samples samples/resolution_test/
   ```

2. **Review results**:
   - Check if 1080p or 2K is supported
   - Note memory and performance metrics
   - Examine saved sample images

3. **Decision**:
   - **Stay at 720p** if:
     - Current detection is 100% accurate
     - Higher resolution causes memory issues
     - No visible quality improvement

   - **Upgrade to 1080p** if:
     - Detection accuracy needs improvement
     - Hardware supports it comfortably
     - Minimap detail visibly better

   - **Upgrade to 2K** if:
     - Detection has significant failures
     - macOS development only (not for Pi deployment)
     - Need maximum detail for algorithm development

4. **If upgrading, make resolution configurable**:
   - Edit `msmacro/cv/capture.py` lines 387-388
   - Add configuration option for resolution
   - Test with new resolution

### Workflow 2: Multi-Modal Detection Development

**Goal**: Improve detection robustness using multiple detection methods.

**Steps:**

1. **Capture calibration samples** (if not already available):
   - Run the daemon in CV-AUTO mode
   - Use web UI to save minimap samples
   - Samples stored in `~/.local/share/msmacro/calibration/minimap_samples/`

2. **Manual annotation with comprehensive characteristics**:
   ```bash
   python scripts/comprehensive_object_marker.py \
       --image ~/.local/share/msmacro/calibration/minimap_samples/sample_001.png \
       --live-detector
   ```

3. **Mark all objects**:
   - Left-click on player position
   - Right-click on enemy positions
   - Press Space to sample HSV at interesting points
   - Press 'h' to see Hough circle detection
   - Press 'e' to see edge detection

4. **Auto-calibrate HSV ranges**:
   - After marking all objects, press 'c'
   - Review calibrated HSV ranges in console
   - Compare with current config values

5. **Save annotations**:
   - Press 's' to save ground truth
   - File saved as `<image_name>.annotations.json`

6. **Test detection methods**:
   - Press 't' to cycle through detection methods
   - Compare HSV vs Hough vs Edge vs Combined
   - Note which method works best

7. **Iterate**:
   - Adjust detector parameters based on observations
   - Re-test with multiple samples
   - Use different lighting conditions

### Workflow 3: Comprehensive Characteristic Analysis

**Goal**: Understand what makes objects detectable beyond just color.

**Steps:**

1. **Collect diverse samples**:
   - Different lighting conditions
   - Different map locations
   - Different times of day
   - With/without motion blur

2. **Analyze each sample**:
   ```bash
   for sample in samples/*.png; do
       python scripts/comprehensive_object_marker.py --image "$sample" --live-detector
       # Mark objects and save annotations
   done
   ```

3. **Extract patterns from annotations**:
   - What HSV ranges work across all samples?
   - What size range do player dots have?
   - What circularity threshold separates dots from noise?
   - Do borders (dark/white rings) always exist?

4. **Document findings**:
   - Record optimal parameter ranges
   - Note failure cases
   - Identify which characteristics are most reliable

5. **Update detector configuration**:
   - Adjust HSV ranges in `detection_config.json`
   - Update size filters
   - Tune circularity thresholds
   - Consider adding Hough circle validation

## Multi-Modal Detection Methods

### Current Method: HSV Color Filtering

**How it works:**
1. Convert BGR to HSV
2. Apply color mask (yellow for player, red for enemies)
3. Find contours in masked image
4. Filter by size, circularity, aspect ratio
5. Score by combined metrics

**Strengths:**
- Fast (<5ms)
- Simple to understand
- Works well with good lighting

**Weaknesses:**
- Sensitive to lighting changes
- Color alone may not be distinctive enough
- JPEG artifacts can affect color accuracy

### New Method 1: Hough Circle Detection

**How it works:**
1. Convert to grayscale
2. Apply Hough circle transform
3. Detect circles of expected radius (2-16px)
4. Validate detected circles with color check

**Strengths:**
- Shape-based, not just color
- Robust to lighting variations
- Validates circular structure

**Weaknesses:**
- Parameter tuning needed
- Can miss partial circles
- Slightly slower (~2-3ms additional)

**When to use:**
- When color detection has false positives
- When objects have clear circular shape
- As secondary validation after HSV

### New Method 2: Edge-Based Ring Validation

**How it works:**
1. Detect edges with Canny
2. Check for dark ring around detected blob
3. Validate white ring outside dark ring
4. Confirm ring structure matches player dot pattern

**Strengths:**
- Exploits known marker structure
- Very distinctive (reduces false positives)
- Robust to color shifts

**Weaknesses:**
- Requires sharp edges (sensitive to blur)
- JPEG compression can degrade edges
- Slightly slower (~1-2ms additional)

**When to use:**
- When false positives are a problem
- When images are high quality (low compression)
- As final validation stage

### Hybrid Approach: Multi-Modal Scoring

**How it works:**
1. Run all detection methods
2. Weight each method's confidence
3. Combine scores: `score = 0.4×HSV + 0.3×Hough + 0.2×Edge + 0.1×Contrast`
4. Select candidates above threshold

**Strengths:**
- Most robust
- Leverages strengths of each method
- Configurable weights

**Weaknesses:**
- Slower (sum of all methods)
- More complex to tune
- Overkill if single method already works

**When to use:**
- When detection must be extremely robust
- When operating in variable conditions
- For production deployment after development

## Next Steps

### Immediate Tasks

1. **Test resolution capabilities**:
   ```bash
   python scripts/test_high_resolution_capture.py
   ```

2. **Annotate sample images**:
   ```bash
   python scripts/comprehensive_object_marker.py --image minimap.png
   ```

3. **Analyze results**:
   - Review HSV ranges from auto-calibration
   - Check if Hough circles match manual markers
   - Validate edge detection shows expected rings

### Future Enhancements

1. **Implement Hough circle detection** in `object_detection.py`
2. **Re-enable edge-based ring validation** (currently disabled)
3. **Create multi-modal scoring system**
4. **Add resolution configuration** in `capture.py`
5. **Build validation framework** comparing detection vs ground truth

## Troubleshooting

### Issue: "No suitable capture device found"

**Solution**:
- Check USB capture card is connected
- Grant camera permissions in System Settings
- Try specifying device index manually: `--device 0`

### Issue: "Resolution not supported"

**Solution**:
- Capture card may not support 2K/4K
- Test with lower resolutions first
- Check capture card specifications

### Issue: "Detector import failed"

**Solution**:
- Ensure msmacro package is installed: `pip install -e .`
- Check Python path includes project root
- Run from project root directory

### Issue: "HSV values inconsistent"

**Solution**:
- JPEG compression affects color accuracy
- Use PNG format for calibration samples
- Sample from multiple pixels (3×3 region) for averaging
- Higher resolution reduces JPEG artifacts

## References

- Main detector implementation: `msmacro/cv/object_detection.py`
- Configuration: `msmacro/cv/detection_config.py`
- Capture system: `msmacro/cv/capture.py`
- Existing documentation: `docus/08_OBJECT_DETECTION.md`
