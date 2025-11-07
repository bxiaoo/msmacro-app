# CV Region Detection - Complete Documentation

This folder contains comprehensive documentation of the improved CV (Computer Vision) white frame detection system.

## What's New

The msmacro-app CV capture system has been enhanced to:

1. **Automatically detect white frame regions** in the top-left corner of screenshots
2. **Crop frames to detected regions** (optional, via environment variable)
3. **Track region metadata** through the entire pipeline
4. **Expose region data** via HTTP headers for frontend integration
5. **Provide confidence scoring** to assess detection quality

## Documentation Structure

- **00_OVERVIEW.md** (this file) - Quick overview and navigation
- **01_ARCHITECTURE.md** - Deep dive into system design and changes
- **02_USAGE.md** - Practical usage examples and API reference
- **03_CONFIGURATION.md** - Environment variables and tuning parameters
- **04_DETECTION_ALGORITHM.md** - How the detection algorithm works
- **05_API_REFERENCE.md** - HTTP endpoints and response formats
- **06_EXAMPLES.md** - Real-world code examples (Python, JavaScript)
- **07_TROUBLESHOOTING.md** - Common issues and solutions
- **08_PERFORMANCE.md** - Performance metrics and optimization

## Quick Start

### Enable Auto-Cropping

```bash
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=240
python -m msmacro daemon
```

### Test Detection

```bash
python scripts/cv_detect_improved.py --start-capture --save-viz /tmp/test_
```

### Use in Frontend

```javascript
const response = await fetch('/api/cv/screenshot');
const region = {
    detected: response.headers.get('X-CV-Region-Detected') === 'true',
    x: parseInt(response.headers.get('X-CV-Region-X') || '0'),
    y: parseInt(response.headers.get('X-CV-Region-Y') || '0'),
    width: parseInt(response.headers.get('X-CV-Region-Width') || '0'),
    height: parseInt(response.headers.get('X-CV-Region-Height') || '0'),
};
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
