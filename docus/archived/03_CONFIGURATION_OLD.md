# Configuration Reference

## Environment Variables

All white frame detection configuration is controlled via environment variables.

### MSMACRO_CV_DETECT_WHITE_FRAME

**Type**: Boolean (true/false)
**Default**: false
**Description**: Enable automatic white frame detection and cropping

```bash
# Enable detection and automatic cropping
export MSMACRO_CV_DETECT_WHITE_FRAME=true

# Disable (only detection analysis, no cropping)
export MSMACRO_CV_DETECT_WHITE_FRAME=false
```

**Behavior**:
- `true`: Frames automatically cropped to detected region
- `false`: Full frames captured, region metadata still available

**Use Case**:
- `true`: Reduce bandwidth, focus on content area
- `false`: Keep full frame, let frontend decide cropping

### MSMACRO_CV_WHITE_THRESHOLD

**Type**: Integer (0-255)
**Default**: 240
**Description**: Minimum pixel value to consider "white"

```bash
# Very strict - only pure white
export MSMACRO_CV_WHITE_THRESHOLD=250

# Default - high quality white
export MSMACRO_CV_WHITE_THRESHOLD=240

# Moderate - includes light gray
export MSMACRO_CV_WHITE_THRESHOLD=220

# Lenient - includes gray
export MSMACRO_CV_WHITE_THRESHOLD=200
```

**Impact on Detection**:

| Threshold | Result |
|-----------|--------|
| 255 | Only pure white, very strict, may miss frames |
| 250 | Very strict, excellent false negative prevention |
| 240 | Balanced (recommended), clean white detection |
| 230 | Moderate, handles slight discoloration |
| 220 | Lenient, includes light grays |
| 200 | Very lenient, includes grays |
| <200 | Too permissive, high false positive rate |

**Tuning Tips**:
- Start at 240 (default)
- Increase if detecting too much noise
- Decrease if missing valid frames
- Monitor with `cv_detect_improved.py` script

**Example**:
```bash
# For light colored but not pure white content
export MSMACRO_CV_WHITE_THRESHOLD=230
```

### MSMACRO_CV_WHITE_MIN_PIXELS

**Type**: Integer (≥0)
**Default**: 100
**Description**: Minimum number of white pixels required for detection

```bash
# Very lenient - tiny white regions count
export MSMACRO_CV_WHITE_MIN_PIXELS=10

# Moderate - small regions count
export MSMACRO_CV_WHITE_MIN_PIXELS=100

# Strict - require meaningful region
export MSMACRO_CV_WHITE_MIN_PIXELS=500

# Very strict - large regions only
export MSMACRO_CV_WHITE_MIN_PIXELS=10000
```

**Impact**:
- Lower values: More detections, potential false positives
- Higher values: Fewer detections, high confidence

**Calculation**:
- 100 pixels ≈ 10x10 area
- 1000 pixels ≈ 30x30 area
- 10000 pixels ≈ 100x100 area

**Use Case Examples**:
- UI dialog (typically 200x150+) → 100-500 pixels
- Large content area (500x400+) → 500-2000 pixels
- Whole screen region → 5000+ pixels

### MSMACRO_CV_WHITE_SCAN_REGION

**Type**: String "x,y,width,height"
**Default**: Not set (uses function default: top-left 800x600)
**Description**: Custom scan region for detection

```bash
# Default behavior (not set) - uses 800x600 top-left
unset MSMACRO_CV_WHITE_SCAN_REGION

# Top-left 600x400 pixels
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,600,400"

# Top-left 1000x800 pixels (larger area)
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,1000,800"

# Custom offset region (offset 100,50, size 500x300)
export MSMACRO_CV_WHITE_SCAN_REGION="100,50,500,300"

# Full frame scanning
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,1920,1080"
```

**Format**: `"x,y,width,height"` where:
- `x`: Left offset (pixels from left)
- `y`: Top offset (pixels from top)
- `width`: Region width (pixels)
- `height`: Region height (pixels)

**Performance**:
- Larger regions: Slower detection, more coverage
- Smaller regions: Faster detection, limited coverage

**Use Cases**:
- Standard UI dialogs: 600x400
- Large content window: 1000x800
- Full frame: 1920x1080 (slower)
- Top bar only: 0,0,1920,100 (very fast)

### MSMACRO_CV_FRAME_PATH

**Type**: String (file path)
**Default**: /dev/shm/msmacro_cv_frame.jpg
**Description**: Location of shared frame file

```bash
# Default - shared memory (fast)
export MSMACRO_CV_FRAME_PATH=/dev/shm/msmacro_cv_frame.jpg

# Persistent storage
export MSMACRO_CV_FRAME_PATH=/tmp/msmacro_cv_frame.jpg

# Custom location
export MSMACRO_CV_FRAME_PATH=/var/cache/msmacro_frame.jpg
```

### MSMACRO_CV_META_PATH

**Type**: String (file path)
**Default**: Auto (same as frame path with .json extension)
**Description**: Location of shared metadata file

```bash
# Auto (frame_path with .json) - default
unset MSMACRO_CV_META_PATH

# Custom location
export MSMACRO_CV_META_PATH=/dev/shm/msmacro_cv_meta.json
```

## Configuration Profiles

### Profile 1: Default (Balanced)

```bash
# Recommended starting point
export MSMACRO_CV_DETECT_WHITE_FRAME=false   # Manual control
export MSMACRO_CV_WHITE_THRESHOLD=240
unset MSMACRO_CV_WHITE_MIN_PIXELS            # Uses default: 100
unset MSMACRO_CV_WHITE_SCAN_REGION           # Uses default: 800x600
```

**Characteristics**:
- Reliable detection
- No automatic cropping
- Full frame available
- Region metadata for frontend

### Profile 2: Auto-Crop Clean Frames

```bash
# For clean white UI frames
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=245        # Very strict
export MSMACRO_CV_WHITE_MIN_PIXELS=500       # Larger region
unset MSMACRO_CV_WHITE_SCAN_REGION
```

**Characteristics**:
- High confidence detections
- Automatic cropping
- Reduced file size
- Only clean white frames

### Profile 3: Aggressive Detection

```bash
# For varied content, more detections
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=200        # Lenient
export MSMACRO_CV_WHITE_MIN_PIXELS=50        # Small regions OK
unset MSMACRO_CV_WHITE_SCAN_REGION
```

**Characteristics**:
- More detections
- Potential false positives
- Catches off-white content
- Smaller cropped files

### Profile 4: Custom Region Focus

```bash
# For known content area
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=240
export MSMACRO_CV_WHITE_SCAN_REGION="100,50,600,400"  # Specific area
```

**Characteristics**:
- Focused detection
- Fast processing
- Custom region size
- Optimized for known layout

## Tuning Guide

### Step 1: Enable Detection Without Cropping

```bash
export MSMACRO_CV_DETECT_WHITE_FRAME=false
python -m msmacro daemon

# Test with script
python scripts/cv_detect_improved.py --start-capture
```

Observe detection behavior without affecting frame output.

### Step 2: Adjust Threshold

```bash
# If detecting too much:
export MSMACRO_CV_WHITE_THRESHOLD=245

# If missing frames:
export MSMACRO_CV_WHITE_THRESHOLD=220

# Re-test
python scripts/cv_detect_improved.py \
    --threshold $MSMACRO_CV_WHITE_THRESHOLD \
    --start-capture
```

### Step 3: Adjust Min Pixels

```bash
# If too many false positives:
export MSMACRO_CV_WHITE_MIN_PIXELS=500

# If missing real content:
export MSMACRO_CV_WHITE_MIN_PIXELS=50

# Re-test
python scripts/cv_detect_improved.py \
    --start-capture \
    --save-viz /tmp/test_
```

### Step 4: Optimize Scan Region

```bash
# If detecting unwanted background:
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,600,400"

# If missing content outside area:
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,1000,800"

# Re-test
python scripts/cv_detect_improved.py --start-capture
```

### Step 5: Enable Auto-Cropping

```bash
# Once tuned, enable cropping
export MSMACRO_CV_DETECT_WHITE_FRAME=true

# Verify frames are cropped correctly
curl -i http://localhost:8787/api/cv/screenshot | grep "X-CV-Region"
```

## Example Configurations

### Configuration A: Terminal Output

```bash
# For terminal/console content
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=200      # Light gray text on white
export MSMACRO_CV_WHITE_MIN_PIXELS=100
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,800,600"
```

### Configuration B: Document Reader

```bash
# For document scanning/reading
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=235      # Near-white pages
export MSMACRO_CV_WHITE_MIN_PIXELS=5000    # Large document area
unset MSMACRO_CV_WHITE_SCAN_REGION         # Full frame search
```

### Configuration C: Web Content

```bash
# For website/web app content
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=240      # Standard white
export MSMACRO_CV_WHITE_MIN_PIXELS=200     # Medium regions
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,800,600"
```

### Configuration D: High Precision

```bash
# For highest quality, no false positives
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=250      # Very strict
export MSMACRO_CV_WHITE_MIN_PIXELS=1000    # Large regions only
export MSMACRO_CV_WHITE_SCAN_REGION="0,0,600,400"
```

## Verification

### Check Current Configuration

```bash
echo "Detection enabled: $MSMACRO_CV_DETECT_WHITE_FRAME"
echo "Threshold: $MSMACRO_CV_WHITE_THRESHOLD"
echo "Min pixels: $MSMACRO_CV_WHITE_MIN_PIXELS"
echo "Scan region: $MSMACRO_CV_WHITE_SCAN_REGION"
```

### Test Configuration

```bash
# Run detection with current settings
python scripts/cv_detect_improved.py --once

# Or with explicit settings
python scripts/cv_detect_improved.py \
    --threshold 240 \
    --ratio 0.85 \
    --once
```

### Monitor Live

```bash
# Watch detection in real-time
python scripts/cv_detect_improved.py \
    --interval 0.5 \
    --start-capture
```

---

See related documents:
- **02_USAGE.md** - Usage examples
- **07_TROUBLESHOOTING.md** - Solving configuration issues
