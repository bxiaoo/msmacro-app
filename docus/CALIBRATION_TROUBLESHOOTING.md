# Object Detection Calibration Troubleshooting

**Last Updated**: Nov 9, 2025 (v1.0)

This guide helps diagnose and fix common calibration issues with the object detection system.

---

## Quick Diagnostic Checklist

Before diving into specific issues, run this quick diagnostic:

```bash
# 1. Check current configuration
python3 -c "
from msmacro.cv.detection_config import load_config
config = load_config()
print(f'Player HSV: {config.player_hsv_lower} to {config.player_hsv_upper}')
print(f'Size: {config.min_blob_size}-{config.max_blob_size}px')
print(f'Circularity: {config.min_circularity}')
"

# 2. Test on known-good sample
python3 -m msmacro.cv.object_detection /tmp/sample_test.png

# 3. Check detection rate
ls /tmp/sample_*.png | while read f; do
    python3 -m msmacro.cv.object_detection "$f" | grep "detected"
done | grep "true" | wc -l
```

**Expected**: Detection rate ≥90% on test samples

---

## Issue 1: Low Player Recall (<90%)

### Symptoms
- Player dots missed in many frames
- Detection works in some positions but not others
- "detected: false" for frames where player is clearly visible

### Root Causes & Solutions

#### Cause 1.1: HSV Hue Range Too Narrow

**Diagnosis**:
```bash
# Sample HSV values at ground truth positions
python3 <<EOF
import cv2
import numpy as np

img = cv2.imread('/tmp/sample_test.png')
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# Click position or use ground truth (e.g., x=100, y=50)
x, y = 100, 50
h, s, v = hsv[y, x]
print(f'HSV at player: H={h}, S={s}, V={v}')
print(f'Current range: H=26-85')
print(f'In range? {26 <= h <= 85}')
EOF
```

**Solution** (if H value outside range):
```python
# In detection_config.py or via config file
# Widen hue range to capture actual values
player_hsv_lower = (20, 67, 64)  # Lower H min from 26 to 20
player_hsv_upper = (90, 255, 255)  # Raise H max from 85 to 90

# Or use calibration wizard to auto-detect ranges
```

#### Cause 1.2: Saturation/Value Thresholds Too Strict

**Diagnosis**:
```bash
# Check if S or V values below threshold
python3 <<EOF
import cv2
img = cv2.imread('/tmp/sample_test.png')
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
x, y = 100, 50  # Player position
h, s, v = hsv[y, x]
print(f'Player S={s} (threshold: S≥67)')
print(f'Player V={v} (threshold: V≥64)')
print(f'S pass? {s >= 67}, V pass? {v >= 64}')
EOF
```

**Solution** (if S or V below threshold):
```python
# Lower S/V thresholds
player_hsv_lower = (26, 50, 50)  # Reduced from (26, 67, 64)

# Note: May increase false positives - validate carefully
```

#### Cause 1.3: Size Threshold Excluding Small Dots

**Diagnosis**:
```bash
# Check detected blob sizes
python3 -c "
from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig
import cv2
config = DetectorConfig()
config.min_blob_size = 1  # Disable size filter temporarily
detector = MinimapObjectDetector(config)
img = cv2.imread('/tmp/sample_test.png')
result = detector.detect(img)
print(f'Detected with size filter disabled: {result.player.detected}')
"
```

**Solution** (if detected with filter disabled):
```python
# Lower minimum size threshold
min_blob_size = 2  # Reduced from 4
```

#### Cause 1.4: Circularity Threshold Too Strict

**Diagnosis**:
```bash
# Manually inspect blob shapes
# If player dots appear circular but not detected, circularity may be too strict
```

**Solution**:
```python
# Lower circularity threshold
min_circularity = 0.65  # Reduced from 0.71

# Warning: May increase false positives from non-circular UI elements
```

---

## Issue 2: High False Positive Rate (>10%)

### Symptoms
- UI elements detected as player dots
- Detection at incorrect positions (far from actual player)
- Multiple detections when only one player present

### Root Causes & Solutions

#### Cause 2.1: HSV Range Too Wide

**Diagnosis**:
```bash
# Check what's being detected
python3 <<EOF
from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig
import cv2
detector = MinimapObjectDetector(DetectorConfig())
img = cv2.imread('/tmp/sample_test.png')
masks = detector.get_debug_masks(img)
cv2.imwrite('/tmp/debug_player_mask.png', masks['player_mask'])
print('Check /tmp/debug_player_mask.png for what HSV filter captures')
EOF
```

**Solution** (if mask shows too many elements):
```python
# Tighten HSV range
player_hsv_lower = (30, 80, 80)  # Narrower than (26, 67, 64)
player_hsv_upper = (80, 255, 255)  # Narrower than (85, 255, 255)
```

#### Cause 2.2: Size Filter Too Loose

**Diagnosis**:
```bash
# Check if large UI elements passing size filter
# Look at detected blob diameters in logs
```

**Solution**:
```python
# Tighten maximum size
max_blob_size = 12  # Reduced from 16
```

#### Cause 2.3: Circularity Threshold Too Loose

**Solution**:
```python
# Increase circularity threshold
min_circularity = 0.75  # Increased from 0.71
```

#### Cause 2.4: Combined Scoring Weights Incorrect

**Solution**:
```python
# In object_detection.py - _calculate_size_score()
# Narrow preferred size range to penalize outliers more
preferred_min = 6.0   # Increased from 4.0
preferred_max = 8.0   # Decreased from 10.0
```

---

## Issue 3: Red Dot False Positives

### Symptoms
- Orange/brown UI elements detected as red player dots
- Cyan/purple elements detected as red
- Detection count >> actual number of other players

### Root Causes & Solutions

#### Cause 3.1: Red HSV Range Too Wide

**Diagnosis**:
```bash
# Check false positive colors
python3 <<EOF
import cv2
img = cv2.imread('/tmp/sample_test.png')
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
# Click false positive position
x, y = 150, 60
h, s, v = hsv[y, x]
print(f'False positive HSV: H={h}, S={s}, V={v}')
print(f'Current red ranges: 0-10, 165-180')
print(f'Matches? {(0 <= h <= 10) or (165 <= h <= 180)}')
EOF
```

**Solution**:
```python
# For Nov 9 calibration, red ranges already tightened:
# Lower red: (0, 100, 100) - (10, 255, 255)
# Upper red: (165, 100, 100) - (180, 255, 255)

# If still issues, further tighten:
other_player_hsv_ranges = [
    ((0, 120, 120), (8, 255, 255)),    # Stricter S≥120, V≥120, H 0-8
    ((170, 120, 120), (180, 255, 255)) # Stricter S≥120, V≥120, H 170-180
]
```

#### Cause 3.2: Size Threshold Too Loose for Red

**Solution**:
```python
# Tighten red dot size threshold
min_blob_size_other = 6   # Increased from 4
max_blob_size_other = 60  # Decreased from 80
```

---

## Issue 4: Performance >15ms (Too Slow)

### Symptoms
- Detection time exceeds 15ms target on Pi 4
- Frame drops during detection
- Warnings in logs about slow detection

### Root Causes & Solutions

#### Cause 4.1: CPU Throttling (Pi Overheating)

**Diagnosis**:
```bash
# On Raspberry Pi
vcgencmd measure_temp
vcgencmd measure_clock arm
```

**Solution**:
- Add heatsink/cooling
- Reduce CPU load from other processes
- Lower camera capture resolution if possible

#### Cause 4.2: Morphological Operations Too Large

**Solution**:
```python
# In object_detection.py - _create_color_mask()
# Reduce kernel size from 3x3 to 2x2
kernel = np.ones((2, 2), np.uint8)  # Smaller kernel = faster
```

#### Cause 4.3: Optional Filters Enabled

**Solution**:
```python
# Disable optional contrast validation
enable_contrast_validation = False
```

#### Cause 4.4: Temporal Smoothing Overhead

**Solution** (if absolutely necessary):
```python
# Disable temporal smoothing
temporal_smoothing = False

# Warning: Will increase position jitter
```

---

## Issue 5: Position Jitter/Instability

### Symptoms
- Player position jumps around when stationary
- Coordinates vary by >5px between frames
- Unstable tracking during movement

### Root Causes & Solutions

#### Cause 5.1: Temporal Smoothing Disabled

**Solution**:
```python
# Enable temporal smoothing
temporal_smoothing = True
smoothing_alpha = 0.3  # Lower = more smoothing (0.1-0.5)
```

#### Cause 5.2: Multiple Blobs with Similar Scores

**Diagnosis**:
```bash
# Enable debug logging
MSMACRO_LOGLEVEL=DEBUG python3 -m msmacro daemon

# Check logs for "blobs={count}" messages
# If count > 1 consistently, multiple candidates competing
```

**Solution**:
```python
# Tighten filters to reduce candidate count
min_circularity = 0.75      # Stricter (from 0.71)
player_hsv_lower = (30, 80, 80)  # Tighter HSV (from 26,67,64)
```

#### Cause 5.3: Edge Artifacts from Morphology

**Solution**:
```python
# Reduce morphological operations
# In _create_color_mask(), use only one operation:
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # Remove OPEN
```

---

## Issue 6: Detection Works on PNG but Fails on YUYV

### Symptoms
- 100% detection on PNG test samples
- <50% detection on live YUYV captures from Pi

### Root Causes & Solutions

#### Cause 6.1: Color Space Differences

**Diagnosis**:
```bash
# Capture YUYV frame and inspect HSV values
# Compare to PNG samples
```

**Solution**:
```bash
# Re-calibrate using YUYV frames, not PNG
# Use web UI calibration wizard with live camera feed
```

#### Cause 6.2: Compression Artifacts

**Explanation**: PNG samples may have been post-processed or compressed differently than raw YUYV

**Solution**:
- Always validate on actual YUYV captures before production
- Use calibration wizard with live YUYV feed

---

## General Calibration Best Practices

### 1. Iterative Tuning Process

```
1. Start with Nov 9 defaults (known good)
2. Test on your specific hardware/setup
3. If recall <90%, widen HSV ranges first
4. If precision <90%, tighten size/circularity next
5. Re-test after each change
6. Document what works for your setup
```

### 2. Validation Dataset

- Capture ≥20 diverse samples (different positions, lighting, scenarios)
- Manually annotate ground truth positions
- Run validation script after each calibration change
- Aim for ≥90% recall AND ≥90% precision

### 3. Hardware-Specific Considerations

**Raspberry Pi Model Differences**:
- Pi 3: May need larger morphology kernels (more noise)
- Pi 4: Can handle stricter filters (faster processing)
- Pi 5: Consider using hardware acceleration

**Camera Variations**:
- Different HDMI capture cards may have different color profiles
- Auto-gain/white-balance settings affect HSV values
- Always calibrate on your specific capture hardware

### 4. Game-Specific Considerations

**Different Maps**:
- Some maps have different minimap color schemes
- May need separate configs per map
- Test on all maps player uses

**Day/Night Cycles**:
- If game has dynamic lighting affecting minimap
- Capture samples at different times of day
- May need adaptive HSV ranges or CLAHE normalization

**UI Overlays**:
- New game patches may add UI elements
- Re-calibrate after major game updates
- Monitor false positive rate weekly

---

## Diagnostic Scripts

### Script 1: HSV Value Inspector

Save as `inspect_hsv.py`:
```python
#!/usr/bin/env python3
import cv2
import sys

img = cv2.imread(sys.argv[1])
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        h, s, v = hsv[y, x]
        print(f'Position ({x},{y}): H={h}, S={s}, V={v}')

cv2.namedWindow('image')
cv2.setMouseCallback('image', mouse_callback)
cv2.imshow('image', img)
print('Click on player dot to see HSV values')
cv2.waitKey(0)
```

Usage: `python3 inspect_hsv.py /tmp/sample.png`

### Script 2: Blob Size Distribution

Save as `check_blob_sizes.py`:
```python
#!/usr/bin/env python3
from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig
import cv2, sys, numpy as np

config = DetectorConfig()
config.min_blob_size = 1  # Accept all sizes
config.min_circularity = 0.1  # Accept all shapes

detector = MinimapObjectDetector(config)
img = cv2.imread(sys.argv[1])
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
mask = detector._create_color_mask(img, config.player_hsv_lower, config.player_hsv_upper)

blobs = detector._find_circular_blobs(mask, img, hsv, min_size=1, max_size=1000, min_circularity=0.1)
diameters = [b['diameter'] for b in blobs]

if diameters:
    print(f'Found {len(blobs)} blobs')
    print(f'Diameter range: {min(diameters):.1f} - {max(diameters):.1f}px')
    print(f'Median: {np.median(diameters):.1f}px')
    print(f'Mean: {np.mean(diameters):.1f}px')
else:
    print('No blobs found')
```

Usage: `python3 check_blob_sizes.py /tmp/sample.png`

---

## Getting Help

If you've tried all troubleshooting steps and still experiencing issues:

1. **Gather diagnostics**:
   ```bash
   # Run diagnostic script
   python3 /tmp/test_final_algorithm.py > diagnostics.txt 2>&1

   # Capture sample images
   cp /tmp/sample_*.png /tmp/debug_samples/

   # Export current config
   cat ~/.local/share/msmacro/object_detection_config.json > config_backup.json
   ```

2. **Check documentation**:
   - FINAL_CALIBRATION_RESULTS_2025-11-09.md (reference calibration)
   - 08_OBJECT_DETECTION.md (implementation details)
   - OBJECT_DETECTION_MAINTENANCE.md (ongoing monitoring)

3. **Report issue** with:
   - Diagnostics output
   - Sample images showing failure
   - Current configuration
   - Hardware details (Pi model, camera type)
   - Game version and map

---

**Document Version**: 1.0 (Nov 9, 2025)
**Algorithm Version**: Combined Scoring (HSV + Size + Circularity + Scoring)
**Last Validated**: Nov 9, 2025 (100% detection on 20-sample dataset)
