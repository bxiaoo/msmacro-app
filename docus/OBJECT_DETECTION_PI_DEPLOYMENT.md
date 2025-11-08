# Object Detection - Raspberry Pi Deployment Guide

Complete workflow for deploying object detection from development → test Pi → production Pi.

---

## Deployment Overview

```
Development (PC/Mac)     Test Pi (Validation)      Production Pi (Live)
==================       ===================       ====================
  Phase 1: Core            Phase 0: Dataset          Config Import
  Algorithm Dev            Creation
                          ↓                          ↓
  JPEG Testing            Phase 2: YUYV             Enable Detection
  (Placeholder HSV)        Calibration
                          ↓                          ↓
  Unit Tests Pass         Phase 3: Validation       Monitor 24hrs
                           (>90% accuracy)
                          ↓                          ↓
                          Phase 4: Export           Production Use
                           Calibrated Config
```

**Key Principle**: Never deploy to production without validation on test Pi first.

---

## Environment Setup

### Required Hardware

| Environment | Hardware | Purpose |
|------------|----------|---------|
| **Development** | PC/Mac | Algorithm development, JPEG testing |
| **Test Pi** | Raspberry Pi 4 + Video Capture | YUYV calibration, validation |
| **Production Pi** | Raspberry Pi 4 + Video Capture | Live gameplay detection |

**Note**: Test Pi and Production Pi should have **identical hardware** to ensure consistent performance.

### Software Requirements

All Pis need:
- Raspberry Pi OS (32-bit or 64-bit)
- Python 3.9+
- msmacro installed (`pip install -e .`)
- OpenCV with YUYV support
- Video capture device drivers

---

## Phase 0: Test Pi Dataset Creation

### Step 1: Deploy Code to Test Pi

```bash
# On development machine
git push origin main  # Push latest object detection code

# SSH into test Pi
ssh pi@test-pi.local

# Pull latest code
cd ~/msmacro-app
git pull origin main

# Install/update
pip install -e .

# Verify installation
python -c "from msmacro.cv.object_detection import MinimapObjectDetector; print('✓ OK')"
```

### Step 2: Start Test Pi Services

```bash
# Start msmacro daemon
python -m msmacro daemon &

# Or use systemd if configured
sudo systemctl start msmacro

# Verify daemon is running
python -m msmacro ctl status
```

### Step 3: Start Game and CV Capture

```bash
# Start CV capture via CLI
python -m msmacro ctl cv-start

# Or via web UI
# Navigate to http://test-pi.local:5050
# Enable CV capture
```

**Verify:**
- CV capture shows live frames
- Minimap region is detected (white frame detection working)
- Frame rate stable at ~2 FPS

### Step 4: Capture YUYV Test Dataset

```bash
# Create dataset directory
mkdir -p data/yuyv_test_set

# Run capture script
python scripts/capture_yuyv_dataset.py --output data/yuyv_test_set/ --count 60
```

**Follow Scenario Guide:**
1. **Player Alone (15 frames)**: Move player to various positions
2. **Player at Edges (10 frames)**: Position player near boundaries
3. **Player + 1 Other (10 frames)**: Single other player visible
4. **Player + 2-3 Others (10 frames)**: Small group
5. **Player + 5+ Others (5 frames)**: Crowded scenario
6. **Different Lighting (10 frames)**: Day/night if applicable

**Output**: 60 `.npy` files in `data/yuyv_test_set/`

### Step 5: Annotate Ground Truth

**Option A: On Test Pi (if you have monitor/GUI)**

```bash
# Run annotation tool directly
python scripts/annotate_ground_truth.py --dataset data/yuyv_test_set/
```

**Option B: On Development Machine (recommended)**

```bash
# Copy dataset to dev machine
scp -r pi@test-pi.local:~/msmacro-app/data/yuyv_test_set ./data/

# Annotate locally
python scripts/annotate_ground_truth.py --dataset data/yuyv_test_set/

# Copy ground truth back to Pi
scp data/yuyv_test_set/ground_truth.json pi@test-pi.local:~/msmacro-app/data/yuyv_test_set/
```

**Annotation Tips:**
- Use 2x zoom (default) for precise clicking
- Focus on quality over quantity (30 good annotations > 60 poor ones)
- Double-check player position accuracy (impacts validation)

**Output**: `ground_truth.json` with annotated positions

---

## Phase 2: YUYV Calibration on Test Pi

### Step 1: Initial Validation (Baseline)

```bash
# Run validation with default (JPEG) HSV ranges
python scripts/validate_detection.py --dataset data/yuyv_test_set/ --output baseline_results.json
```

**Expected Result**: Validation likely **FAILS** because JPEG placeholder HSV ranges don't match YUYV colors.

Example output:
```
❌ VALIDATION FAILED
  ✗ FAIL  Player Precision ≥90%   = 45.2%  (too low!)
  ✗ FAIL  Player Recall ≥85%      = 38.5%  (too low!)
```

This is **expected** - it confirms calibration is needed.

### Step 2: Access Web UI Calibration Wizard

1. Open browser: `http://test-pi.local:5050`
2. Navigate to **Object Detection** tab
3. Click **Calibrate** button
4. Select calibration type: **Player** (yellow dot)

### Step 3: Click-to-Calibrate Workflow

**Player Calibration:**
1. Web UI displays live YUYV frame (lossless PNG)
2. Use zoom controls (200-400%) for precision
3. Click on player dot in 5 different frames:
   - Click 1: Player centered
   - Click 2: Player at edge
   - Click 3: Player with others nearby
   - Click 4: Player in different lighting
   - Click 5: Player in another position
4. System analyzes pixel colors and generates HSV ranges
5. Preview detection mask overlay
6. **Verify**: mask highlights player dot cleanly
7. Click **Apply** to save

**Other Players Calibration** (repeat for red dots):
1. Select calibration type: **Other Players**
2. Click on red dots in 5 frames
3. System generates HSV ranges for red
4. Preview and apply

### Step 4: Export Calibrated Config

```bash
# Via web UI
# Object Detection → Config → Export
# Downloads: object_detection_config.json

# Or via API
curl http://test-pi.local:5050/api/cv/object-detection/config/export > calibrated_config.json
```

**Config includes:**
- Calibrated HSV ranges for player (yellow)
- Calibrated HSV ranges for other players (red)
- Blob filtering parameters
- Calibration metadata (timestamp, device ID)

---

## Phase 3: Validation on Test Pi

### Step 1: Re-run Validation with Calibrated Config

```bash
# Reload detection with calibrated config
python -m msmacro ctl object-detection-stop
python -m msmacro ctl object-detection-start

# Re-run validation
python scripts/validate_detection.py --dataset data/yuyv_test_set/ --output calibrated_results.json
```

**Expected Result**: Validation **PASSES** all gates

```
✅ VALIDATION PASSED - Ready for production deployment

  ✓ PASS  Player Precision ≥90%           = 92.5%
  ✓ PASS  Player Recall ≥85%              = 90.2%
  ✓ PASS  Avg Position Error <5px         = 2.34px
  ✓ PASS  Other Players Precision ≥85%    = 88.0%
  ✓ PASS  Other Players Recall ≥80%       = 84.6%
  ✓ PASS  Performance <15ms                = 12.45ms
```

### Step 2: 24-Hour Stability Test (Optional but Recommended)

```bash
# Enable detection
python -m msmacro ctl object-detection-start

# Monitor logs for 24 hours
tail -f /var/log/msmacro.log | grep "object_detection"

# Check for:
# - No memory leaks (RSS stable)
# - No excessive warnings
# - Detection rate stable
# - No crashes
```

**Monitoring Commands:**
```bash
# Memory usage
watch -n 60 'ps aux | grep msmacro | grep -v grep'

# Detection performance stats
curl http://test-pi.local:5050/api/cv/object-detection/performance | jq
```

### Step 3: Export Final Config for Production

```bash
# Export via web UI or API
curl http://test-pi.local:5050/api/cv/object-detection/config/export > production_config.json

# Add production metadata
echo '{
  "calibration_source": "test-pi-validation-2025-01-08",
  "validation_passed": true,
  "player_precision": 0.925,
  "player_recall": 0.902,
  "avg_position_error": 2.34,
  "validation_date": "2025-01-08T15:30:00Z"
}' | jq -s '.[0] * .[1]' - production_config.json > production_config_final.json
```

---

## Phase 4: Production Pi Deployment

### Prerequisites Checklist

Before deploying to production:

- [ ] Validation passed on test Pi (all gates ✓)
- [ ] 24-hour stability test completed (optional)
- [ ] Calibrated config exported
- [ ] Production Pi hardware identical to test Pi
- [ ] Backup of production Pi config exists
- [ ] Rollback plan ready

### Step 1: Prepare Production Pi

```bash
# SSH into production Pi
ssh pi@production-pi.local

# Pull latest code
cd ~/msmacro-app
git pull origin main
pip install -e .

# Verify object detection module
python -c "from msmacro.cv.object_detection import MinimapObjectDetector; print('✓ OK')"
```

### Step 2: Import Calibrated Config

**Option A: Via Web UI**

1. Navigate to http://production-pi.local:5050
2. Object Detection → Config → Import
3. Upload `production_config_final.json`
4. Click **Apply**

**Option B: Via API**

```bash
# Copy config to production Pi
scp production_config_final.json pi@production-pi.local:~/

# Import via API
curl -X POST http://production-pi.local:5050/api/cv/object-detection/config \
  -H "Content-Type: application/json" \
  -d @production_config_final.json
```

**Option C: Manual File Copy**

```bash
# Copy to config location
scp production_config_final.json pi@production-pi.local:~/.local/share/msmacro/object_detection_config.json

# Restart daemon to load config
ssh pi@production-pi.local 'sudo systemctl restart msmacro'
```

### Step 3: Enable Detection (Monitoring Mode)

```bash
# Enable detection but DO NOT enable auto-corrections yet
python -m msmacro ctl object-detection-start

# Verify status
python -m msmacro ctl object-detection-status
```

**Monitor for Issues:**
- Check logs every hour for first 24 hours
- Verify detection rate remains high (>85%)
- Ensure performance stays under 15ms
- Watch for false positives/negatives

```bash
# Real-time monitoring
tail -f /var/log/msmacro.log | grep -E "(object_detection|OBJECT_DETECTED)"

# Performance check every 5 minutes
watch -n 300 'curl -s http://localhost:5050/api/cv/object-detection/performance | jq ".avg_ms"'
```

### Step 4: Gate Check (24 Hours Later)

After 24 hours of monitoring, verify:

- [ ] No crashes or errors in logs
- [ ] Detection rate stable (check SSE event frequency)
- [ ] Performance stable (avg < 15ms)
- [ ] Memory usage stable (no leaks)
- [ ] No user complaints (if applicable)

**If ANY gate fails**: Disable detection and troubleshoot on test Pi.

### Step 5: Enable Auto-Corrections (Optional - Future)

⚠️ **ONLY after successful 24-hour monitoring**

```python
# This is for future Phase 5 (Playback Integration)
# Not implemented yet - placeholder for when position-based
# corrections are added to macro playback

# Enable position-based macro corrections
python -m msmacro ctl playback-enable-position-correction
```

---

## Rollback Procedure

If issues occur in production:

### Immediate Rollback

```bash
# Disable object detection
python -m msmacro ctl object-detection-stop

# Verify disabled
python -m msmacro ctl object-detection-status
```

### Restore Previous Config

```bash
# If you have backup config
scp backup_config.json pi@production-pi.local:~/.local/share/msmacro/object_detection_config.json

# Restart daemon
ssh pi@production-pi.local 'sudo systemctl restart msmacro'
```

### Investigate Issues

```bash
# Check logs for errors
ssh pi@production-pi.local 'grep -i "object_detection" /var/log/msmacro.log | tail -100'

# Get performance stats
curl http://production-pi.local:5050/api/cv/object-detection/performance | jq

# Check validation results
python scripts/validate_detection.py --dataset data/yuyv_test_set/
```

---

## Configuration Management

### Config File Locations

| Pi | Config Path |
|----|-------------|
| Test | `~/.local/share/msmacro/object_detection_config.json` |
| Production | `~/.local/share/msmacro/object_detection_config.json` |

### Config Backup Strategy

```bash
# Backup before changes
cp ~/.local/share/msmacro/object_detection_config.json \
   ~/.local/share/msmacro/object_detection_config.json.backup-$(date +%Y%m%d-%H%M%S)

# List backups
ls -lh ~/.local/share/msmacro/object_detection_config.json.backup-*
```

### Version Control

```bash
# Track configs in git (optional)
mkdir -p configs/object_detection/
cp ~/.local/share/msmacro/object_detection_config.json \
   configs/object_detection/production-$(date +%Y%m%d).json

git add configs/object_detection/
git commit -m "feat: object detection config for production $(date +%Y-%m-%d)"
```

---

## Troubleshooting Production Issues

### Issue: Detection Rate Drops

**Symptoms**: Fewer `OBJECT_DETECTED` events than expected

**Diagnostics:**
```bash
# Check detection status
curl http://production-pi.local:5050/api/cv/object-detection/status | jq

# Check if CV capture is running
curl http://production-pi.local:5050/api/cv/status | jq

# Review recent detection results
grep "OBJECT_DETECTED" /var/log/msmacro.log | tail -20
```

**Possible Causes & Solutions:**
- **Game lighting changed**: Recalibrate HSV ranges
- **Minimap moved**: Reconfigure region detection
- **CV capture stopped**: Restart CV capture

### Issue: Performance Degradation

**Symptoms**: Detection time > 15ms consistently

**Diagnostics:**
```bash
# Get detailed performance stats
curl http://production-pi.local:5050/api/cv/object-detection/performance | jq

# Check CPU usage
ssh pi@production-pi.local 'top -bn1 | grep msmacro'
```

**Solutions:**
- Check for other CPU-intensive processes
- Verify minimap region is cropped (not processing full frame)
- Disable optional preprocessing in config

### Issue: False Positives/Negatives

**Symptoms**: Detects player when not present, or misses player

**Diagnostics:**
```bash
# Re-run validation on production Pi
python scripts/validate_detection.py --dataset data/yuyv_test_set/

# Check if HSV ranges are correct
curl http://production-pi.local:5050/api/cv/object-detection/config | jq '.player'
```

**Solutions:**
- Recalibrate HSV ranges using wizard
- Adjust blob size/circularity thresholds
- Re-validate before deploying updated config

---

## Maintenance & Updates

### Monthly Checklist

- [ ] Review detection logs for errors/warnings
- [ ] Check performance stats (should remain < 15ms)
- [ ] Verify detection accuracy (spot check with validation script)
- [ ] Update config backup
- [ ] Update msmacro to latest version if available

### After Game Updates

If game updates and minimap changes:

1. Disable detection on production
2. Recalibrate on test Pi with new game version
3. Re-validate (must pass all gates)
4. Export new config
5. Import to production
6. Monitor for 24 hours

---

## Success Criteria

### Production Deployment Considered Successful When:

- ✅ Validation passed on test Pi (>90% precision, >85% recall)
- ✅ 24-hour stability test completed with no issues
- ✅ Detection enabled on production Pi
- ✅ Monitored for 24+ hours with stable performance
- ✅ No crashes, memory leaks, or errors
- ✅ Detection rate consistent with test Pi
- ✅ User confirms detection is working as expected

---

## Related Documentation

- [08_OBJECT_DETECTION.md](./08_OBJECT_DETECTION.md) - Feature specification
- [OBJECT_DETECTION_TESTING.md](./OBJECT_DETECTION_TESTING.md) - Testing guide
- [OBJECT_DETECTION_IMPLEMENTATION_PLAN.md](./testing/OBJECT_DETECTION_IMPLEMENTATION_PLAN.md) - Implementation details

---

**Document Version**: 1.0
**Last Updated**: 2025-01-08
**Status**: Ready for Test Pi Deployment
