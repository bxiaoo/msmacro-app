# 2K Resolution Testing Guide for Raspberry Pi

## Changes Made

**File Modified:** `msmacro/cv/capture.py`

**Resolution increased:**
- **Before:** 1280×720 (720p) - 2.7 MB per frame
- **After:** 2560×1440 (2K/QHD) - 10.6 MB per frame
- **Increase:** 4× pixel count, 3.9× memory usage

**Expected Benefits:**
- Minimap pixel count: 29,240 → 116,960 pixels (4× improvement)
- Sharper minimap details for better object detection
- More accurate HSV color sampling (less JPEG artifacts)
- Better edge detection (clearer ring structures)

**Potential Risks:**
- Increased memory usage (~10.6 MB per frame vs 2.7 MB)
- Higher JPEG encoding time
- USB bandwidth may become bottleneck
- Possible out-of-memory (OOM) errors on Pi

---

## Pre-Test Checklist

Before testing on Raspberry Pi, verify:

1. **Raspberry Pi Model:**
   - ✅ Pi 4 with 4GB RAM (recommended)
   - ⚠️ Pi 4 with 2GB RAM (risky, monitor closely)
   - ❌ Pi 3 or earlier (likely insufficient)

2. **USB Capture Card:**
   - Check if it supports 2560×1440 resolution
   - Verify USB connection (USB 3.0 preferred)
   - Confirm no other heavy processes running

3. **Storage:**
   - Ensure sufficient space on SD card
   - Consider using `/dev/shm` (RAM disk) for frame buffer

---

## Testing Procedure

### Step 1: Monitor System Resources

**Before starting the daemon**, open a separate SSH session and monitor resources:

```bash
# Terminal 1: Monitor memory usage in real-time
watch -n 1 'free -h && echo "---" && ps aux | grep python | grep -v grep'

# OR use htop for interactive monitoring
htop
```

**Key metrics to watch:**
- **Available memory**: Should stay above 500 MB
- **Python process memory**: msmacro daemon should stay below 1 GB
- **Swap usage**: Should remain at 0 (swap = performance death)

### Step 2: Start Daemon with Logging

```bash
# Stop existing daemon if running
python -m msmacro ctl stop

# Start with debug logging to see resolution confirmation
MSMACRO_LOGLEVEL=DEBUG python -m msmacro daemon
```

**Look for these log messages:**
```
Device opened, configuring format parameters...
Successfully read test frame with YUYV format
```

**Check actual resolution achieved:**
The daemon should log the actual frame size. If capture card doesn't support 2K, it may downscale to 1080p automatically.

### Step 3: Enable CV Capture

```bash
# In another terminal, enable CV capture
python -m msmacro ctl cv-enable
```

**Monitor for ~2 minutes:**
- Watch memory usage in htop/watch terminal
- Check for OOM errors in daemon log
- Verify frames are being captured (check web UI)

### Step 4: Enable Object Detection

```bash
python -m msmacro ctl cv-object-detection-enable
```

**Monitor detection performance:**
- Check detection time in logs (target: <15ms)
- Watch for frame drops or timeouts
- Verify player/enemy detection still works

### Step 5: Capture Test Samples

```bash
# Save a few minimap samples for quality comparison
python -m msmacro ctl cv-save-sample
```

Samples saved to: `~/.local/share/msmacro/calibration/minimap_samples/`

**Compare quality:**
```bash
# Check file sizes
ls -lh ~/.local/share/msmacro/calibration/minimap_samples/

# View dimensions
file ~/.local/share/msmacro/calibration/minimap_samples/*.png

# Expected: Minimap should be ~680×172 pixels (2x larger than before)
```

---

## Performance Benchmarks

### Target Metrics (2K Resolution)

| Metric | Target | Warning Threshold | Critical |
|--------|--------|-------------------|----------|
| **Frame capture time** | <50 ms | >100 ms | >200 ms |
| **JPEG encoding time** | <30 ms | >50 ms | >100 ms |
| **Detection time** | <15 ms | >30 ms | >50 ms |
| **Total memory** | <1.5 GB | >2.5 GB | >3.5 GB |
| **Available RAM** | >500 MB | <300 MB | <100 MB |
| **Capture rate** | 2 FPS | <1 FPS | Frames dropping |

### Expected Performance Changes

**Compared to 720p:**

| Operation | 720p | 2K (Expected) | Multiplier |
|-----------|------|---------------|------------|
| Frame size (raw) | 2.7 MB | 10.6 MB | 3.9× |
| JPEG size (q=70) | ~600 KB | ~2 MB | 3.3× |
| Minimap pixels | 29,240 | 116,960 | 4.0× |
| Detection time | ~1 ms | ~3-4 ms | 3-4× |
| JPEG encoding | ~10 ms | ~25-30 ms | 2.5-3× |

---

## Troubleshooting

### Issue 1: Out of Memory (OOM)

**Symptoms:**
- Daemon crashes with "Killed" message
- System becomes unresponsive
- Swap usage increases dramatically

**Solutions:**

1. **Reduce capture rate** (edit `capture.py`):
   ```python
   # Change from 2 FPS to 1 FPS
   await asyncio.sleep(1.0)  # instead of 0.5
   ```

2. **Lower JPEG quality** (reduce file size):
   ```bash
   # Edit capture.py, change jpeg_quality from 70 to 50
   self.jpeg_quality = 50
   ```

3. **Revert to 1080p** (less drastic than going back to 720p):
   ```python
   cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
   cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
   ```

### Issue 2: Capture Card Doesn't Support 2K

**Symptoms:**
- Log shows "Successfully read test frame" but resolution is wrong
- Actual frame size is 1920×1080 instead of 2560×1440

**Check actual resolution:**
```python
# In daemon log, look for frame dimensions
# Or add debug print in capture.py after frame capture:
logger.info(f"Captured frame size: {frame.shape}")
```

**Solutions:**
- Use 1920×1080 (1080p) instead of 2K
- Check capture card specifications
- Try different USB port (USB 3.0 if available)

### Issue 3: Slow Detection Performance

**Symptoms:**
- Detection takes >30 ms per frame
- High CPU usage (>80%)
- Frame drops or stuttering

**Solutions:**

1. **Detection is CPU-bound** - this is expected with 4× more pixels
   - Acceptable if <15 ms (within budget)
   - Consider disabling contrast validation if enabled

2. **Optimize detection** (if needed):
   - Reduce morphology kernel size
   - Disable optional validation steps
   - Consider region-of-interest (ROI) cropping

### Issue 4: USB Bandwidth Issues

**Symptoms:**
- Frames arrive slowly
- Capture time >100 ms
- Intermittent black frames

**Solutions:**
- Use USB 3.0 port if available (blue port on Pi 4)
- Disconnect other USB devices
- Try MJPEG format instead of YUYV (already in fallback)
- Reduce frame rate to 1 FPS

---

## Rollback Instructions

If 2K doesn't work well, revert to previous resolution:

### Option 1: Revert to 720p (Original)

```bash
# Edit capture.py, lines 388-389
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
```

### Option 2: Try 1080p (Middle Ground)

```bash
# Edit capture.py, lines 388-389
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
```

**After changes:**
```bash
# Restart daemon
python -m msmacro ctl stop
python -m msmacro daemon
```

---

## Success Criteria

**✅ 2K resolution is working well if:**
- Memory usage stays below 2 GB
- No OOM crashes after 30 minutes
- Detection time <15 ms consistently
- Minimap samples are visibly sharper
- Object detection accuracy improves or stays same

**⚠️ Consider reverting if:**
- Frequent OOM crashes
- Memory usage >3 GB
- Detection time >30 ms
- Frame capture rate drops below 1 FPS
- System becomes sluggish

**❌ Must revert if:**
- System crashes/freezes
- Swap thrashing (continuous swap I/O)
- Detection completely fails
- Capture rate <0.5 FPS

---

## Quality Comparison

### How to Compare Minimap Sharpness

1. **Capture samples at both resolutions:**
   ```bash
   # With 720p (before change)
   python -m msmacro ctl cv-save-sample

   # With 2K (after change)
   python -m msmacro ctl cv-save-sample
   ```

2. **Compare side-by-side:**
   ```bash
   # View in image viewer
   eog ~/.local/share/msmacro/calibration/minimap_samples/*.png

   # Or use the marker tool to zoom in
   python scripts/comprehensive_object_marker.py --image <sample>.png
   ```

3. **Check pixel counts:**
   ```bash
   # 720p minimap: ~340×86 = 29,240 pixels
   # 2K minimap: ~680×172 = 116,960 pixels

   identify -format "%wx%h\n" sample.png
   ```

4. **Visual quality improvements to look for:**
   - ✅ Sharper dot edges (less pixelated)
   - ✅ Clearer color boundaries
   - ✅ More visible ring structure (dark + white rings)
   - ✅ Better shape definition (more circular dots)
   - ✅ Less JPEG compression artifacts

---

## Reporting Results

After testing, please note:

**Hardware:**
- Pi model and RAM: _______________
- Capture card model: _______________
- USB version: 2.0 / 3.0

**Performance:**
- Memory usage (steady state): _______ MB
- Detection time (average): _______ ms
- Capture rate achieved: _______ FPS
- Any crashes/OOM? Yes / No

**Quality:**
- Minimap resolution achieved: _______ × _______
- Visibly sharper? Yes / No / Marginal
- Detection accuracy: Better / Same / Worse

**Decision:**
- [ ] Keep 2K - works great!
- [ ] Downgrade to 1080p - 2K too heavy
- [ ] Revert to 720p - not worth the cost

---

## Next Steps After Testing

### If 2K Works Well:

1. **Capture diverse samples** at 2K resolution
2. **Use comprehensive marker tool** to annotate with improved detail
3. **Re-calibrate detection** with sharper images
4. **Test multi-modal detection** (Hough circles, edge validation)

### If 2K Doesn't Work:

1. **Try 1080p** as middle ground (2.25× pixels, 2.2× memory)
2. **Optimize current 720p algorithm** instead
3. **Focus on multi-modal detection** rather than resolution
4. **Consider 2K for macOS development** only, keep Pi at 720p

---

## Contact & Support

If you encounter issues not covered here:
1. Check daemon logs: `journalctl -u msmacro -f`
2. Monitor system: `dmesg | tail -50`
3. Check USB devices: `lsusb -v | grep -A 5 "Video"`

**Remember:** Higher resolution doesn't always = better detection. The current 720p algorithm achieves 100% accuracy. Only upgrade if you see tangible benefit!
