# White Frame Detection Removal - Migration Guide

**Date**: 2025-11-08  
**Status**: Completed

## Summary

Legacy white frame auto-detection has been removed from the MSMacro CV system. All minimap region configuration is now **manual** via the web UI.

---

## What Changed

### Removed Features

1. **Auto-detection logic**:
   - `detect_top_left_white_frame()` - YUYV-based white border detection
   - `detect_white_frame_yuyv()` - Advanced fixed-point detection
   - `detect_and_crop_white_frame()` - General contour-based detection

2. **Environment variables**:
   - `MSMACRO_CV_DETECT_WHITE_FRAME`
   - `MSMACRO_CV_WHITE_THRESHOLD`
   - `MSMACRO_CV_WHITE_MIN_PIXELS`
   - `MSMACRO_CV_WHITE_SCAN_REGION`

3. **Documentation**:
   - 600+ lines of white frame detection algorithm documentation
   - Configuration reference for white frame env vars

### Preserved Features

✅ **Manual map configuration** (web UI) - unchanged  
✅ **Object detection** (HSV-based) - unchanged  
✅ **Calibration wizard** - unchanged  
✅ **REST API** - unchanged  
✅ **Frontend components** - unchanged

---

## Migration Path

### If You Were Using Auto-Detection

**Before** (deprecated):
```bash
export MSMACRO_CV_DETECT_WHITE_FRAME=true
export MSMACRO_CV_WHITE_THRESHOLD=240
# System auto-detected minimap region
```

**After** (current):
1. Open web UI: `http://localhost:5050`
2. Navigate to **CV Configuration** tab
3. Click **Create Configuration**
4. Adjust width/height (top-left fixed at 68, 56)
5. Click **Save Configuration**, enter name
6. Check checkbox to activate

### If You Were Using Web UI

✅ **No changes required** - you were already using manual configuration.

### If You Have Scripts Using Env Vars

**Update your scripts**:
```bash
# Remove these lines
-export MSMACRO_CV_DETECT_WHITE_FRAME=true
-export MSMACRO_CV_WHITE_THRESHOLD=240

# Use web UI or API instead
curl -X POST http://localhost:8787/api/cv/map-configs \
  -H "Content-Type: application/json" \
  -d '{"name": "My Map", "tl_x": 68, "tl_y": 56, "width": 340, "height": 86}'
```

---

## Why This Change?

### Problems with Auto-Detection

1. **Unreliable** - Depended on white borders being present and clean
2. **Fragile** - Game UI changes broke detection
3. **Complex** - 600+ lines of detection algorithms to maintain
4. **Confusing** - Users didn't understand when/why it worked or failed

### Benefits of Manual Configuration

1. **Predictable** - Users explicitly define region, no surprises
2. **Flexible** - Works with any game/UI, not just white-bordered elements
3. **Simple** - Clean codebase, easier to maintain and debug
4. **User-friendly** - Visual preview shows exactly what will be captured

---

## Files Modified

### Code
- `msmacro/cv/capture.py` - Removed auto-detection imports and deprecated attributes

### Documentation
- `docus/00_OVERVIEW.md` - Removed white frame references, updated features list
- `docus/03_CONFIGURATION.md` - Removed white frame env vars section (replaced)
- `docus/04_DETECTION_ALGORITHM.md` - Removed 600+ lines of white frame algorithm (replaced)

### Archived
- `docus/archived/03_CONFIGURATION_OLD.md` - Original configuration doc
- `docus/archived/04_DETECTION_ALGORITHM_OLD.md` - Original detection algorithm doc

---

## Testing

### Verification Tests

Run these to verify the migration:

```bash
# 1. Test imports
python3 -c "from msmacro.cv.capture import CVCapture; print('✓ OK')"

# 2. Test map config API
curl http://localhost:8787/api/cv/map-configs

# 3. Test preview endpoint
curl "http://localhost:8787/api/cv/mini-map-preview?x=68&y=56&w=340&h=86" -o test.png

# 4. Test object detection still works
curl http://localhost:8787/api/cv/object-detection/status
```

### Expected Results

- ✅ No import errors
- ✅ Map config API returns saved configurations
- ✅ Preview endpoint returns PNG image
- ✅ Object detection status returns normally

---

## Rollback (if needed)

If issues arise, rollback by:

1. **Restore old documentation**:
   ```bash
   cp docus/archived/03_CONFIGURATION_OLD.md docus/03_CONFIGURATION.md
   cp docus/archived/04_DETECTION_ALGORITHM_OLD.md docus/04_DETECTION_ALGORITHM.md
   ```

2. **Restore capture.py imports**:
   ```python
   from .region_analysis import (
       detect_and_crop_white_frame,
       detect_top_left_white_frame,
       detect_white_frame_yuyv,
   )
   ```

3. **Re-add deprecated attributes**:
   ```python
   self._detect_white_frame = os.environ.get("MSMACRO_CV_DETECT_WHITE_FRAME", "false").lower() in ("true", "1", "yes")
   ```

**Note**: Rollback not recommended - manual configuration is superior in all aspects.

---

## Support

If you encounter issues:

1. Check **06_MAP_CONFIGURATION.md** for manual configuration guide
2. Review **08_OBJECT_DETECTION.md** for detection details
3. Test with provided verification commands above
4. Report issues with detailed logs and reproduction steps

---

**Migration completed successfully. All tests passing.**
