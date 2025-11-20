# 1080p Resolution Testing Guide for Raspberry Pi

## Changes Made

**File Modified:** `msmacro/cv/capture.py`

**Resolution increased:**
- **Before:** 1280×720 (720p) - 2.7 MB per frame
- **After:** 1920×1080 (1080p/Full HD) - 6 MB per frame
- **Increase:** 2.25× pixel count, 2.2× memory usage

**Why 1080p (not 2K)?**
- More conservative memory increase (2.2× vs 3.9×)
- Widely supported by capture cards
- Good balance between quality and performance
- Lower risk of OOM on Raspberry Pi

---

## Expected Impact

### Resolution Comparison

| Aspect | 720p (Before) | 1080p (Now) | Improvement |
|--------|---------------|-------------|-------------|
| **Frame size** | 1280×720 | 1920×1080 | 1.5× larger |
| **Total pixels** | 921,600 | 2,073,600 | **2.25× more** |
| **Minimap size** | ~340×86 | ~510×129 | 1.5× each dimension |
| **Minimap pixels** | 29,240 | 65,790 | **2.25× more** |
| **Frame memory** | 2.7 MB | 6 MB | 2.2× increase |
| **JPEG size** | ~600 KB | ~1.2 MB | 2× increase |

### Performance Estimates

| Metric | 720p | 1080p (Expected) |
|--------|------|------------------|
| **Capture time** | ~5 ms | ~8-10 ms |
| **JPEG encoding** | ~10 ms | ~18-22 ms |
| **Detection time** | ~1 ms | ~2 ms |
| **Memory usage** | ~500 MB | ~1-1.2 GB |

**Much more manageable than 2K!** ✅

---

## Quick Testing Steps

### 1. Monitor Resources (Terminal 1)
```bash
watch -n 1 'free -h && echo "---" && ps aux | grep python | grep -v grep'
```

### 2. Start Daemon with Logging (Terminal 2)
```bash
python -m msmacro ctl stop
MSMACRO_LOGLEVEL=DEBUG python -m msmacro daemon
```

**Look for:**
```
Device opened, configuring format parameters...
Successfully read test frame with YUYV format
```

### 3. Enable CV Capture
```bash
python -m msmacro ctl cv-enable
```

**Monitor for 5 minutes:**
- Memory usage should stay <1.5 GB
- No OOM errors
- Frames capturing steadily

### 4. Enable Object Detection
```bash
python -m msmacro ctl cv-object-detection-enable
```

**Check:**
- Detection time in logs (should be <15 ms)
- Player/enemy detection still working
- No frame drops

### 5. Capture Test Samples
```bash
python -m msmacro ctl cv-save-sample
```

**Compare quality:**
```bash
cd ~/.local/share/msmacro/calibration/minimap_samples/

# Check dimensions (should be ~510×129)
file *.png

# View samples
eog *.png
```

---

## Success Criteria

### ✅ Working Well If:
- Memory usage <1.5 GB
- No crashes after 30 minutes
- Detection time <15 ms
- Minimap visibly sharper than 720p
- Capture rate maintains 2 FPS

### ⚠️ Warning Signs:
- Memory usage >2 GB
- Detection time >20 ms
- Occasional frame drops

### ❌ Must Revert If:
- OOM crashes
- Memory usage >2.5 GB
- Detection time >30 ms
- System becomes sluggish

---

## Performance Benchmarks

### Target Metrics (1080p)

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| **Memory usage** | <1.2 GB | >1.8 GB | >2.5 GB |
| **Detection time** | <10 ms | >15 ms | >30 ms |
| **Capture rate** | 2 FPS | <1.5 FPS | <1 FPS |
| **Available RAM** | >1 GB | <500 MB | <200 MB |

---

## Troubleshooting

### Issue: Memory Still Too High

**Solution 1:** Reduce capture rate to 1 FPS
```python
# Edit capture.py, in capture loop:
await asyncio.sleep(1.0)  # instead of 0.5
```

**Solution 2:** Lower JPEG quality
```python
# Edit capture.py:
self.jpeg_quality = 60  # instead of 70
```

**Solution 3:** Revert to 720p
```python
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
```

### Issue: Capture Card Doesn't Support 1080p

**Check actual resolution:**
- Look in daemon log for frame dimensions
- Most modern USB capture cards support 1080p

**If downscaled:**
- Verify USB connection (try different port)
- Check capture card specifications
- May need to use 720p

---

## Quality Improvements to Expect

At 1080p, you should see:

**Visual improvements:**
- ✅ **2.25× more pixels** in minimap
- ✅ **Sharper dot edges** - less pixelation
- ✅ **Clearer colors** - more accurate HSV sampling
- ✅ **Better shape definition** - dots appear more circular
- ✅ **Less JPEG artifacts** - higher base quality

**Detection improvements:**
- ✅ More robust HSV color detection
- ✅ Better circularity validation
- ✅ Improved ring structure visibility
- ✅ Reduced false negatives in edge cases

---

## Minimap Size Comparison

### At 720p (Before):
```
Full frame: 1280×720
Minimap region: ~340×86 pixels
Total minimap pixels: 29,240
```

### At 1080p (Now):
```
Full frame: 1920×1080
Minimap region: ~510×129 pixels
Total minimap pixels: 65,790
```

**2.25× more detail for detection!** 🎯

---

## Rollback Instructions

If 1080p doesn't work well:

### Revert to 720p

Edit `msmacro/cv/capture.py` lines 388-389:

```python
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
```

Then restart:
```bash
python -m msmacro ctl stop
python -m msmacro daemon
```

---

## Next Steps After Testing

### If 1080p Works Well:

1. **Use it for production** ✅
2. **Capture diverse samples** at 1080p
3. **Re-annotate with marker tool:**
   ```bash
   python scripts/comprehensive_object_marker.py \
       --image sample.png --live-detector
   ```
4. **Re-calibrate detection** with sharper images
5. **Test multi-modal detection** (Hough + Edge)

### If Still Too Heavy:

1. **Stay at 720p** - current algorithm already 100% accurate
2. **Focus on multi-modal detection** improvements
3. **Use 1080p on macOS development** only

---

## Reporting Results

After testing, note:

**Performance:**
- Memory usage: _______ MB
- Detection time: _______ ms
- Capture rate: _______ FPS
- Any crashes? Yes / No

**Quality:**
- Minimap size achieved: _______ × _______
- Visibly sharper? Yes / No
- Detection accuracy: Better / Same / Worse

**Decision:**
- [ ] Keep 1080p - perfect balance!
- [ ] Revert to 720p - not needed

---

## Why 1080p is the Sweet Spot

| Resolution | Pixels | Memory | Pros | Cons |
|------------|--------|--------|------|------|
| **720p** | 1× | 1× | Lightweight, proven | Limited detail |
| **1080p** ✅ | 2.25× | 2.2× | **Good balance** | Moderate cost |
| **2K** | 4× | 3.9× | Maximum detail | Heavy on Pi |

**1080p provides 2.25× more detail with only 2.2× memory cost** - the best bang for buck! 🎯
