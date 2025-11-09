# Calibration Sample Collection & Annotation Workflow

## Overview

This document describes how to collect high-quality minimap samples for manual annotation and analysis to improve object detection accuracy. The workflow enables iterative refinement of HSV color ranges, blob filtering parameters, and detection algorithms.

**Last Updated**: 2025-01-09
**Status**: Production Ready

---

## Workflow Summary

```
1. Collect Samples (Web UI) → 2. Review Samples → 3. Annotate (Optional) → 4. Send to Claude → 5. Apply Improvements
     ↓                             ↓                    ↓                        ↓                    ↓
  Save 20-50 PNGs          Verify quality     Mark objects (CLI)      ZIP & upload        Import config
```

---

## Phase 1: Sample Collection

### Using the Web UI

1. **Navigate to CV Configuration Tab**
   - Open web UI: `http://pi-hostname:5050`
   - Go to "CV Configuration" tab

2. **Ensure Active Map Config**
   - If no config exists, create one:
     - Click "Create Configuration"
     - Adjust width/height to match your minimap
     - Save with a descriptive name
   - Activate the config (blue checkmark indicates active)

3. **Verify Live Preview**
   - Scroll to "Live Minimap Preview" section
   - Ensure preview image is updating every 2 seconds
   - If no preview: check CV capture status at top of page

4. **Save Calibration Samples**
   - Click **"Save Sample"** button (top-right of preview)
   - Sample counter badge will increment with each save
   - Success message shows: `Sample sample_YYYYMMDD_HHMMSS.png saved!`
   - Samples are automatically named with timestamps

### Sample Collection Strategy

**Goal**: Collect 20-50 diverse samples covering different scenarios

| Scenario | Sample Count | Examples |
|----------|-------------|----------|
| **Player positions** | 10-15 | Center, edges, corners, moving |
| **Other player counts** | 10-15 | 0, 1, 2, 5+ other players visible |
| **Lighting conditions** | 5-10 | Daytime, nighttime, indoor, outdoor (if applicable) |
| **Map regions** | 5-10 | Different areas (if minimap appearance varies) |
| **Edge cases** | 5 | Overlapping dots, partially visible dots, crowded |

**Tips**:
- Save samples during actual gameplay for realistic conditions
- Avoid duplicate scenarios (similar positions/counts)
- Include challenging cases (crowded minimap, dots near edges)
- Document conditions in a notes file (optional)

---

## Phase 2: Sample Review

### Verify Sample Quality

1. **Navigate to samples directory**:
   ```bash
   cd ~/.local/share/msmacro/calibration/minimap_samples/
   ```

2. **List saved samples**:
   ```bash
   ls -lh *.png
   ```

3. **View samples** (use image viewer):
   ```bash
   # macOS
   open sample_20250109_143022.png

   # Linux (GNOME)
   eog sample_20250109_143022.png

   # Raspberry Pi (X11)
   feh sample_20250109_143022.png
   ```

4. **Check metadata** (optional):
   ```bash
   cat sample_20250109_143022_meta.json
   ```

### Quality Checklist

- ✅ Image is lossless PNG (no JPEG artifacts)
- ✅ Resolution matches map config (e.g., 340×86)
- ✅ Player dot visible (yellow)
- ✅ Other player dots visible if present (red)
- ✅ No duplicate scenarios
- ✅ Diverse sample set (positions, counts, lighting)

**Action**: Delete poor-quality or duplicate samples:
```bash
rm sample_bad_quality.png sample_bad_quality_meta.json
```

---

## Phase 3: Manual Annotation (Optional)

**Note**: This step is optional. You can send raw samples to Claude for analysis without annotation. Annotations improve analysis accuracy but require additional time.

### Using the CLI Annotation Tool

The `annotate_ground_truth.py` script provides an interactive OpenCV window for marking object positions.

#### Setup

```bash
cd /path/to/msmacro-app
python scripts/annotate_ground_truth.py --dataset ~/.local/share/msmacro/calibration/minimap_samples/
```

#### Annotation Instructions

1. **Window Controls**:
   - Click on **player dot** (yellow) → marks player position
   - Click on **other player dots** (red) → marks multiple other players
   - Press **`n`** → next image
   - Press **`p`** → previous image
   - Press **`s`** → save annotations
   - Press **`q`** → quit

2. **Marking Process**:
   - First click: Player position (x, y)
   - Subsequent clicks: Other player positions (can mark multiple)
   - Click **outside dots** to undo last mark
   - Press **`n`** to move to next image (saves automatically)

3. **Output**:
   - Saves to: `~/.local/share/msmacro/calibration/minimap_samples/ground_truth.json`
   - Format:
     ```json
     {
       "sample_20250109_143022.png": {
         "player": {"x": 120, "y": 45},
         "other_players": [
           {"x": 200, "y": 30},
           {"x": 250, "y": 60}
         ]
       }
     }
     ```

#### Example Session

```bash
$ python scripts/annotate_ground_truth.py --dataset ~/.local/share/msmacro/calibration/minimap_samples/

Loading dataset...
Found 25 images

Image 1/25: sample_20250109_143022.png
Click player position: (120, 45)
Click other player 1: (200, 30)
Click other player 2: (250, 60)
Press 'n' for next image...

Annotations saved to ground_truth.json
```

---

## Phase 4: Send Samples to Claude

### Prepare Dataset

1. **Create ZIP archive**:
   ```bash
   cd ~/.local/share/msmacro/calibration/
   zip -r minimap_samples_$(date +%Y%m%d).zip minimap_samples/
   ```

2. **Verify archive contents**:
   ```bash
   unzip -l minimap_samples_20250109.zip
   ```

   Expected contents:
   ```
   minimap_samples/
   ├── sample_20250109_143022.png
   ├── sample_20250109_143022_meta.json
   ├── sample_20250109_143055.png
   ├── sample_20250109_143055_meta.json
   ├── ...
   └── ground_truth.json (if annotated)
   ```

### Send to Claude

**Option 1: Claude Code (recommended)**
```bash
# Upload in chat
# Attach: minimap_samples_20250109.zip
# Prompt: "Analyze these minimap samples and suggest improved detection parameters"
```

**Option 2: Claude Desktop**
- Drag ZIP file into chat window
- Same prompt as above

**Option 3: claude.ai (Web)**
- Upload ZIP via attachment button
- Same prompt as above

### Analysis Request Template

```
Please analyze these minimap object detection samples and help improve accuracy.

**Context**:
- Game: [Your game name]
- Minimap size: 340×86 pixels
- Current detection accuracy: ~70% (estimated)
- Issues: [Describe problems, e.g., "yellow player dot not detected in bright areas"]

**Samples included**:
- 25 PNG images (lossless)
- Metadata JSON for each sample
- Ground truth annotations (if available)

**Request**:
1. Analyze HSV color distributions for player (yellow) and other players (red)
2. Recommend optimal HSV ranges (min/max for H, S, V)
3. Suggest improvements to blob filtering (size, circularity thresholds)
4. Identify patterns in false positives/negatives
5. Provide updated detection config JSON

**Current HSV ranges** (for reference):
- Player: H(15-40), S(60-255), V(80-255) [too wide?]
- Other Players: H(0-12, 168-180), S(70-255), V(70-255)
```

---

## Phase 5: Apply Improvements

### Claude's Response Format

Claude will provide:
1. **Analysis Summary**: Color distribution insights, problem areas
2. **New HSV Ranges**: Optimized min/max values
3. **Config JSON**: Ready-to-use configuration file
4. **Additional Recommendations**: Preprocessing, morphology adjustments

### Example Claude Response

```json
{
  "player": {
    "hsv_lower": [18, 100, 150],
    "hsv_upper": [35, 255, 255]
  },
  "other_players": {
    "color_ranges": [
      {"hsv_lower": [0, 120, 100], "hsv_upper": [10, 255, 255]},
      {"hsv_lower": [170, 120, 100], "hsv_upper": [180, 255, 255]}
    ]
  },
  "blob_size_min": 4,
  "blob_size_max": 12,
  "circularity_min_player": 0.65,
  "circularity_min_other": 0.55
}
```

### Apply New Configuration

**Method 1: Via CalibrationWizard (Recommended)**
1. Navigate to CV Configuration → Object Detection tab
2. Click "Calibrate" button
3. Paste Claude's config JSON into wizard (if supported)
4. Or manually enter HSV ranges via sliders (if manual tuning available)

**Method 2: Direct Config File Edit**
```bash
# Edit detection config
nano ~/.local/share/msmacro/object_detection_config.json

# Paste Claude's JSON
# Save and restart msmacro daemon

sudo systemctl restart msmacro
```

**Method 3: Via API (curl)**
```bash
curl -X POST http://localhost:5050/api/cv/object-detection/config \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "player_hsv_range": [[18, 100, 150], [35, 255, 255]],
      "other_player_hsv_ranges": [
        [[0, 120, 100], [10, 255, 255]],
        [[170, 120, 100], [180, 255, 255]]
      ]
    }
  }'
```

### Validate Improvements

1. **Enable object detection**:
   ```bash
   curl -X POST http://localhost:5050/api/cv/object-detection/start
   ```

2. **Check live detection**:
   - Navigate to Object Detection tab in web UI
   - View detection preview (player + other players marked)
   - Verify improved accuracy

3. **Test with saved samples** (manual validation):
   - Run detection on saved samples
   - Compare detected positions with ground truth
   - Calculate accuracy: correct detections / total samples

4. **Collect new samples** (optional):
   - Save 10 new samples with new config
   - Repeat analysis if accuracy still < 90%

---

## Troubleshooting

### Common Error Codes & Solutions

#### Error: `no_active_config`
**Message**: "No active map configuration. Please activate a map config in CV Configuration tab."

**Solution**:
1. Navigate to CV Configuration tab
2. If no configs exist: Click "Create Configuration"
3. Set width/height (e.g., 340×86)
4. Save configuration
5. Click config name to activate (blue checkmark appears)
6. Wait 2-3 seconds for capture loop to process
7. Try saving sample again

**Root cause**: No map config is activated, so the system doesn't know which region to crop.

---

#### Error: `minimap_not_available` or `minimap_timeout_after_start`
**Message**: "Raw minimap not available after 3 seconds" or "Timeout waiting for minimap"

**Possible causes**:
1. Capture just started and first frame hasn't arrived yet
2. Camera is disconnected
3. Map config region is out of frame bounds
4. Capture loop is stuck

**Solutions**:
1. **Wait and retry**: Click "Save Sample" again after 5 seconds
2. **Check camera connection**:
   ```bash
   ls /dev/video*  # Should show video device
   v4l2-ctl --list-devices  # List capture devices
   ```
3. **Verify capture is running**:
   - Check CV status at top of page
   - If stopped: Click "Start CV Capture"
4. **Check live preview**:
   - Scroll to "Live Minimap Preview"
   - If no image: capture is not working
   - If black screen: map config region may be out of bounds
5. **Restart capture**:
   ```bash
   sudo systemctl restart msmacro
   ```

**Root cause**: Camera not connected, capture delayed, or config region invalid.

---

#### Error: `capture_start_failed`
**Message**: "Failed to start CV capture"

**Solution**:
1. **Check camera permissions**:
   ```bash
   ls -l /dev/video0  # Check permissions
   sudo chmod 666 /dev/video0  # Grant access (temporary)
   ```
2. **Check camera is not in use**:
   ```bash
   lsof /dev/video0  # Shows processes using camera
   ```
3. **Verify camera works**:
   ```bash
   ffplay /dev/video0  # Test camera feed
   ```
4. **Check daemon logs**:
   ```bash
   journalctl -u msmacro -n 50  # Last 50 log lines
   ```

**Root cause**: Camera device inaccessible due to permissions or hardware issue.

---

#### Error: `empty_minimap`
**Message**: "Minimap crop is empty. Map config region may be invalid."

**Solution**:
1. **Check map config dimensions**:
   - Ensure width > 0 and height > 0
   - Typical: 340×86
2. **Verify region is within frame bounds**:
   - If frame is 1280×720, region must fit within
   - Top-left: (68, 56), Bottom-right: (408, 142) fits
3. **Check full-screen capture**:
   - View full screenshot via API: `/api/cv/screenshot`
   - Verify minimap is visible at configured location
4. **Recreate map config**:
   - Delete current config
   - Create new one with correct dimensions

**Root cause**: Map config region is outside the frame bounds or has zero dimensions.

---

#### Error: `directory_creation_failed` or `file_write_failed`
**Message**: "Failed to create calibration directory" or "Failed to write PNG file"

**Solution**:
1. **Check disk space**:
   ```bash
   df -h ~/.local/share/msmacro/
   ```
2. **Check permissions**:
   ```bash
   ls -ld ~/.local/share/msmacro/
   chmod 755 ~/.local/share/msmacro/  # Grant write access
   ```
3. **Check filesystem**:
   ```bash
   touch ~/.local/share/msmacro/test.txt  # Test write
   rm ~/.local/share/msmacro/test.txt
   ```
4. **Check SELinux/AppArmor** (if on Linux):
   ```bash
   getenforce  # Check SELinux status
   sudo setenforce 0  # Temporarily disable (if needed)
   ```

**Root cause**: Insufficient permissions or disk space.

---

#### Error: `png_encode_failed`
**Message**: "Failed to encode minimap as PNG"

**Solution**:
1. **Check OpenCV installation**:
   ```bash
   python3 -c "import cv2; print(cv2.__version__)"
   ```
2. **Reinstall OpenCV**:
   ```bash
   pip install --upgrade opencv-python
   ```
3. **Check minimap data**:
   - Daemon logs will show shape/dtype
   - Should be: shape=(86, 340, 3), dtype=uint8

**Root cause**: OpenCV issue or corrupted minimap data.

---

#### Error: `capture_instance_failed`
**Message**: "Failed to get CV capture instance. Is the daemon running?"

**Solution**:
1. **Check daemon status**:
   ```bash
   sudo systemctl status msmacro
   ```
2. **Restart daemon**:
   ```bash
   sudo systemctl restart msmacro
   ```
3. **Check daemon is listening**:
   ```bash
   curl http://localhost:5050/api/status
   ```

**Root cause**: Daemon not running or not responding.

---

### General Troubleshooting Steps

#### Step 1: Check Daemon Logs (Always start here)
```bash
# View recent logs with color
journalctl -u msmacro -n 100 --no-pager

# Follow logs in real-time
journalctl -u msmacro -f

# Filter for errors only
journalctl -u msmacro -p err -n 50
```

Look for:
- 🔵 "cv_save_calibration_sample: Starting sample save request"
- ✅ "Sample save complete"
- ❌ Any error messages

#### Step 2: Check Browser Console
1. Press F12 to open DevTools
2. Click "Console" tab
3. Look for red errors
4. Check "Network" tab → "save-calibration-sample" request

#### Step 3: Verify System State
```bash
# Check CV capture status
curl http://localhost:5050/api/cv/status | jq

# Check active map config
curl http://localhost:5050/api/cv/map-configs | jq

# Test raw minimap endpoint
curl http://localhost:5050/api/cv/raw-minimap | jq
```

#### Step 4: Full System Restart
```bash
# Stop daemon
sudo systemctl stop msmacro

# Clear any stuck processes
pkill -f msmacro

# Restart
sudo systemctl start msmacro

# Check status
sudo systemctl status msmacro
```

---

### Quick Diagnostic Checklist

Before reporting an issue, verify:

- [ ] Daemon is running: `systemctl status msmacro`
- [ ] Camera connected: `ls /dev/video*`
- [ ] CV capture active: Check status in web UI
- [ ] Map config activated: Blue checkmark visible
- [ ] Live preview working: Image updates every 2s
- [ ] Disk space available: `df -h`
- [ ] Permissions OK: `ls -ld ~/.local/share/msmacro/`
- [ ] Daemon logs reviewed: `journalctl -u msmacro -n 50`
- [ ] Browser console checked: F12 → Console tab

---

### Still Having Issues?

If errors persist after trying above solutions:

1. **Capture full diagnostic info**:
   ```bash
   # Save system info to file
   {
     echo "=== System Info ==="
     uname -a
     echo ""
     echo "=== Daemon Status ==="
     systemctl status msmacro
     echo ""
     echo "=== Recent Logs ==="
     journalctl -u msmacro -n 100 --no-pager
     echo ""
     echo "=== CV Status ==="
     curl -s http://localhost:5050/api/cv/status
     echo ""
     echo "=== Disk Space ==="
     df -h ~/.local/share/msmacro/
   } > ~/msmacro_diagnostic.txt
   ```

2. **Share diagnostic file** with maintainer or in issue tracker

3. **Workaround**: Use manual frame capture:
   - Take screenshots of minimap region
   - Save manually to `~/.local/share/msmacro/calibration/minimap_samples/`
   - Name files: `sample_001.png`, `sample_002.png`, etc.

---

### Legacy Issues (Fixed in Latest Version)

#### Problem: Samples are all identical
- **Fixed**: Gallery now shows unique timestamps
- **If still occurs**: Ensure sufficient time between saves (~2-5 seconds)

#### Problem: Sample counter doesn't increment
- **Fixed**: Counter now increments immediately on success
- **If still occurs**: Check browser console for JavaScript errors

#### Problem: Annotation tool crashes
- **Fixed**: Improved error handling in annotation script
- **If still occurs**:
  ```bash
  pip install --upgrade opencv-python numpy
  ```

---

## Storage Locations

### Sample Files

```
~/.local/share/msmacro/calibration/
├── minimap_samples/
│   ├── sample_20250109_143022.png       (raw PNG, ~88KB)
│   ├── sample_20250109_143022_meta.json (metadata, ~1KB)
│   ├── sample_20250109_143055.png
│   ├── sample_20250109_143055_meta.json
│   └── ground_truth.json                (annotations, if created)
└── sessions/
    └── session_20250109.json             (batch metadata, future)
```

### Disk Usage

- Per sample: ~90KB (PNG + metadata)
- 50 samples: ~4.5MB
- 100 samples: ~9MB

**Cleanup** (delete old samples):
```bash
# Delete samples older than 30 days
find ~/.local/share/msmacro/calibration/minimap_samples/ -name "*.png" -mtime +30 -delete
find ~/.local/share/msmacro/calibration/minimap_samples/ -name "*_meta.json" -mtime +30 -delete
```

---

## Advanced Usage

### Batch Collection Script

Automate sample collection at intervals:

```bash
#!/bin/bash
# save_samples_batch.sh

for i in {1..20}; do
  echo "Saving sample $i/20..."
  curl -X POST http://localhost:5050/api/cv/save-calibration-sample \
    -H "Content-Type: application/json" \
    -d "{\"metadata\": {\"batch\": \"auto_$i\"}}"
  sleep 10  # Wait 10 seconds between saves
done

echo "✅ Saved 20 samples"
```

### Export Samples to External System

```bash
# Copy samples to external drive
rsync -av ~/.local/share/msmacro/calibration/minimap_samples/ /mnt/usb/msmacro_samples/

# Upload to cloud storage (example: rclone)
rclone sync ~/.local/share/msmacro/calibration/minimap_samples/ remote:msmacro/samples/
```

---

## Related Documentation

- **08_OBJECT_DETECTION.md** - Full implementation details
- **04_DETECTION_ALGORITHM.md** - Algorithm overview
- **06_MAP_CONFIGURATION.md** - Minimap region setup
- **scripts/annotate_ground_truth.py** - Annotation tool source code

---

## Summary

✅ **Easy Collection**: One-click save from web UI
✅ **Lossless Quality**: Raw minimap before JPEG compression
✅ **Rich Metadata**: Timestamp, map config, checksum
✅ **Flexible Workflow**: Optional annotation, iterative improvement
✅ **Claude Analysis**: AI-powered HSV range optimization

**Expected Outcome**: Detection accuracy improved from ~70% → 90%+ after 2-3 iterations.
