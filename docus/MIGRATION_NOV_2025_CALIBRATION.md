# Migration Guide: Nov 9, 2025 Calibration Update

**Target Audience**: Users upgrading from pre-Nov 9, 2025 calibration to new algorithm
**Breaking Changes**: Yes (HSV ranges, size filtering, selection algorithm)
**Estimated Migration Time**: 30-60 minutes
**Rollback Difficulty**: Easy (config file restore)

---

## Executive Summary

The Nov 9, 2025 calibration update brings significant improvements to object detection accuracy:

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Player Detection Rate | 80-95% | 100% | ⬆ +5-20% |
| Other Players Precision | 88% | 100% | ⬆ +12% |
| False Positive Rate | ~12% | 0% | ⬇ -100% |
| Detection Performance | 12.45ms avg | 0.79ms avg | ⬆ 15.7x faster |

**Key Algorithm Changes**:
1. HSV ranges expanded and tightened (player H:26-85 vs old 15-40)
2. Size filtering re-enabled with strict thresholds (4-16px vs disabled)
3. Combined scoring replaces "closest to center" selection
4. Stricter circularity filtering (0.71 vs 0.6)

---

## Breaking Changes

### 1. HSV Color Ranges Updated

**Impact**: HIGH - Affects which pixels are detected as markers

| Object | Old Range | New Range | Change |
|--------|-----------|-----------|--------|
| Player Hue (H) | 15-40 | **26-85** | Extended upper range (+45) |
| Player Sat (S) | ≥60 | **≥67** | Slightly stricter (+7) |
| Player Val (V) | ≥80 | **≥64** | More permissive (-16) |
| Red Sat (S) | ≥70 | **≥100** | Much stricter (+30) |
| Red Val (V) | ≥70 | **≥100** | Much stricter (+30) |
| Red Hue (H) | 0-12, 168-180 | **0-10, 165-180** | Narrowed ranges |

**Why This Matters**:
- Old range (H=15-40) missed yellow-green player dots with H>40
- New range (H=26-85) captures actual player dot colors (yellow-green to cyan)
- Tighter red S/V eliminates orange/brown false positives

**Compatibility**:
- Old configs will still load but may have reduced accuracy
- **Recommendation**: Full re-calibration for best results

### 2. Size Filtering Re-Enabled

**Impact**: CRITICAL - Changes which blobs pass filtering

| Setting | Old Value | New Value | Change |
|---------|-----------|-----------|--------|
| Player Min Size | 1-2px (disabled) | **4px** | Enforced minimum |
| Player Max Size | 100px (disabled) | **16px** | Strict maximum |
| Red Min Size | 1-2px (disabled) | **4px** | Enforced minimum |
| Red Max Size | 100px (disabled) | **80px** | Strict maximum |

**Why This Matters**:
- Old "disabled" state (1-100px) let through oversized UI elements
- New strict bounds eliminate most false positives
- Separate thresholds for player (4-16px) vs red (4-80px) based on empirical data

**Compatibility**:
- Old configs have no size thresholds in file
- New defaults will apply automatically after code update
- **Risk**: May exclude legitimate detections if dots unusually small/large

### 3. Selection Algorithm Changed

**Impact**: MEDIUM - Affects which blob is selected when multiple candidates exist

| Aspect | Old Algorithm | New Algorithm |
|--------|---------------|---------------|
| Method | Distance-based | **Combined scoring** |
| Formula | `min(distance_to_center)` | **`max(size_score × S × V × circularity)`** |
| Preferred Size | N/A | **4-10px** (weighted) |
| Uses Saturation | No | **Yes** (0-255) |
| Uses Brightness | No | **Yes** (0-255) |

**Why This Matters**:
- Old method picked nearest blob to center, even if low quality
- New method picks most marker-like blob (size, color, shape)
- Handles edge cases (player at edge, UI element at center)

**Compatibility**:
- Algorithm change is code-only, no config needed
- **Risk**: None - new algorithm empirically superior

### 4. Stricter Circularity Thresholds

**Impact**: LOW - Fine-tunes shape filtering

| Object | Old Threshold | New Threshold | Change |
|--------|---------------|---------------|--------|
| Player | ≥0.6 | **≥0.71** | Stricter (+0.11) |
| Red | ≥0.5 | **≥0.65** | Stricter (+0.15) |

**Why This Matters**:
- Rejects elongated false positives (rectangles, ovals)
- Combined with other filters, achieved 100% precision

**Compatibility**:
- Old configs may have old thresholds
- New defaults apply if not specified in config

---

## Migration Paths

### Option A: Quick Migration (Use Pre-Calibrated Values)

**Best For**: Standard hardware setup, want quick upgrade
**Time Required**: 15-30 minutes
**Risk**: Low (Nov 9 values validated on 20 samples)

#### Steps:

1. **Backup Current Config** (important for rollback):
   ```bash
   # Backup config file
   cp ~/.local/share/msmacro/object_detection_config.json \
      ~/.local/share/msmacro/object_detection_config_pre_nov9_backup.json

   # Backup code (if modified locally)
   cd ~/msmacro-app
   git stash save "Pre-Nov 9 local changes"
   ```

2. **Update Code**:
   ```bash
   cd ~/msmacro-app
   git pull origin main  # Or deploy updated files manually
   ```

3. **Verify New Defaults Loaded**:
   ```bash
   python3 -c "
   from msmacro.cv.object_detection import DetectorConfig
   config = DetectorConfig()
   print(f'Player HSV: {config.player_hsv_lower} to {config.player_hsv_upper}')
   print(f'Size: {config.min_blob_size}-{config.max_blob_size}px')
   print(f'Circularity: {config.min_circularity}')
   print('Expected: (26,67,64)-(85,255,255), 4-16px, 0.71')
   "
   ```

   **Expected Output**:
   ```
   Player HSV: (26, 67, 64) to (85, 255, 255)
   Size: 4-16px
   Circularity: 0.71
   ```

4. **Test on Sample Images**:
   ```bash
   # Capture 5-10 test frames from your setup
   # Run detection test
   python3 /tmp/test_final_algorithm.py
   ```

   **Expected**: ≥90% detection rate

5. **Deploy to Production**:
   ```bash
   # Restart daemon to load new code
   python3 -m msmacro ctl stop
   python3 -m msmacro daemon &

   # Or restart systemd service
   sudo systemctl restart msmacro
   ```

6. **Monitor for 24 Hours**:
   - Check detection logs for errors
   - Verify false positive rate <10%
   - Confirm detection rate >90%

**Rollback If Needed**:
```bash
cd ~/msmacro-app
git checkout <previous-commit-hash>
cp ~/.local/share/msmacro/object_detection_config_pre_nov9_backup.json \
   ~/.local/share/msmacro/object_detection_config.json
python3 -m msmacro ctl stop && python3 -m msmacro daemon &
```

---

### Option B: Full Re-Calibration (Recommended for Custom Setups)

**Best For**: Custom hardware, different game version, want optimal accuracy
**Time Required**: 45-60 minutes
**Risk**: Very low (validates on your specific setup)

#### Steps:

1. **Backup (same as Option A Step 1)**

2. **Update Code (same as Option A Step 2)**

3. **Delete Old Config** (force re-calibration):
   ```bash
   # Remove old config to start fresh
   mv ~/.local/share/msmacro/object_detection_config.json \
      ~/.local/share/msmacro/object_detection_config_old.json
   ```

4. **Run Calibration Wizard**:
   ```bash
   # Start daemon
   python3 -m msmacro daemon

   # Open web UI
   open http://localhost:5050  # Or http://raspberrypi.local:5050

   # Navigate to: CV Configuration → Object Detection → Calibration Wizard
   # Click player dot in 5-10 different positions
   # Preview detection mask
   # Save calibration
   ```

5. **Validate Calibration**:
   ```bash
   # Capture 20 test frames
   mkdir /tmp/validation_set
   # ... capture frames to /tmp/validation_set/

   # Run validation
   python3 <<EOF
   from pathlib import Path
   from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig
   import cv2

   detector = MinimapObjectDetector(DetectorConfig())
   samples = list(Path('/tmp/validation_set').glob('*.png'))
   detected = sum(1 for s in samples if detector.detect(cv2.imread(str(s))).player.detected)

   print(f'Detection rate: {detected}/{len(samples)} ({100*detected/len(samples):.1f}%)')
   print(f'Target: ≥90%')
   EOF
   ```

   **Expected**: ≥90% detection rate

6. **Fine-Tune If Needed**:
   - If recall <90%: See CALIBRATION_TROUBLESHOOTING.md, Issue 1
   - If precision <90%: See CALIBRATION_TROUBLESHOOTING.md, Issue 2

7. **Deploy & Monitor (same as Option A Steps 5-6)**

---

### Option C: Gradual Migration (Lowest Risk)

**Best For**: Production systems, want to test before full rollout
**Time Required**: 2-3 days (including monitoring)
**Risk**: Minimal (parallel testing)

#### Steps:

1. **Setup Parallel Test Environment**:
   ```bash
   # Clone to test directory
   cp -r ~/msmacro-app ~/msmacro-app-nov9-test
   cd ~/msmacro-app-nov9-test
   git pull origin main  # Get Nov 9 updates
   ```

2. **Run Parallel Detection**:
   ```bash
   # Terminal 1: Old system (keep running)
   cd ~/msmacro-app
   python3 -m msmacro daemon

   # Terminal 2: New system (testing)
   cd ~/msmacro-app-nov9-test
   MSMACRO_SOCKET=/run/msmacro-test.sock python3 -m msmacro daemon
   ```

3. **Compare Results for 48 Hours**:
   ```bash
   # Check old system logs
   grep "OBJECT_DETECTED" /var/log/msmacro.log | wc -l

   # Check new system logs
   grep "OBJECT_DETECTED" /var/log/msmacro-test.log | wc -l

   # Compare detection rates, false positives
   ```

4. **Switch to New System If Better**:
   ```bash
   # Stop old system
   cd ~/msmacro-app
   python3 -m msmacro ctl stop

   # Promote new system
   mv ~/msmacro-app ~/msmacro-app-old-backup
   mv ~/msmacro-app-nov9-test ~/msmacro-app

   # Restart with new system
   python3 -m msmacro daemon
   ```

---

## Migration Checklist

Use this checklist to track migration progress:

### Pre-Migration
- [ ] Backup current config file
- [ ] Backup current code (git stash or commit hash noted)
- [ ] Document current detection performance (baseline metrics)
- [ ] Capture 10+ test samples from current setup

### Migration Execution
- [ ] Update code to Nov 9 version
- [ ] Verify new defaults loaded OR run calibration wizard
- [ ] Test on sample images (≥90% detection target)
- [ ] Deploy to production (restart daemon/service)

### Post-Migration Validation
- [ ] Monitor logs for 24 hours
- [ ] Verify detection rate >90%
- [ ] Verify false positive rate <10%
- [ ] Check performance <15ms on Pi 4
- [ ] Document any custom tuning needed

### Sign-Off
- [ ] Migration successful (YES/NO)
- [ ] Detection quality improved (YES/NO)
- [ ] No regressions observed (YES/NO)
- [ ] Rollback plan tested (if needed)

**Migration Completed**: ________ (Date)
**Migrated By**: ________ (Name)
**Notes**: _________________________________

---

## Common Migration Issues

### Issue 1: Detection Rate Drops After Migration

**Symptoms**: Was 90% before, now 60-70%

**Likely Cause**: YUYV vs PNG color space differences

**Solution**:
```bash
# Re-calibrate using YUYV frames, not PNG samples
# Use web UI calibration wizard with live camera feed
```

**See**: CALIBRATION_TROUBLESHOOTING.md, Issue 6

### Issue 2: False Positive Rate Increases

**Symptoms**: Detecting UI elements that weren't detected before

**Likely Cause**: HSV range too wide for your specific setup

**Solution**:
```bash
# Tighten HSV ranges via config or re-calibration
# Increase circularity threshold to 0.75
```

**See**: CALIBRATION_TROUBLESHOOTING.md, Issue 2

### Issue 3: Performance Regression

**Symptoms**: Detection time increases from <5ms to >15ms

**Likely Cause**: Size filtering overhead on slower hardware

**Solution**:
```bash
# Temporarily disable contrast validation
# Reduce morphological kernel size from 3x3 to 2x2
```

**See**: CALIBRATION_TROUBLESHOOTING.md, Issue 4

---

## FAQ

**Q: Do I HAVE to migrate?**
A: No, but highly recommended. Old algorithm has known issues (false positives, H>40 missed). Nov 9 algorithm achieves 100% detection with 0 false positives.

**Q: Will my old config still work?**
A: Yes, it will load, but may have reduced accuracy. Old HSV ranges (15-40) miss dots with H>40. Old "disabled" size filtering lets through false positives.

**Q: How long does migration take?**
A: Quick migration (Option A): 15-30 min. Full re-calibration (Option B): 45-60 min. Gradual migration (Option C): 2-3 days with testing.

**Q: What if migration fails?**
A: Easy rollback - restore backup config and checkout old code. See rollback instructions in Option A.

**Q: Can I keep my old calibration?**
A: Not recommended. Old algorithm has known limitations. However, if you must, you can manually edit config to restore old values (not officially supported).

**Q: Do I need to recalibrate for each Pi?**
A: Recommended but not required. Nov 9 defaults work well on standard hardware. Re-calibrate if: different camera, different game version, detection rate <90%.

**Q: What about backward compatibility?**
A: New code reads old configs (graceful degradation). Old code can't use new config format. If you need to rollback, restore both code and config.

---

## Validation Criteria

After migration, your system should meet these criteria:

| Metric | Target | How to Check |
|--------|--------|--------------|
| Player Detection Rate | ≥90% | Run test on 20+ samples |
| Other Players Precision | ≥85% | Check false positive logs |
| Detection Performance | <15ms on Pi 4 | Check `/api/cv/object-detection/performance` |
| Position Stability | <5px jitter | Monitor coords when stationary |
| No Errors in Logs | 0 exceptions | Check logs for 24 hours |

**All Green?** Migration successful! 🎉

**Any Red?** See CALIBRATION_TROUBLESHOOTING.md for diagnostics.

---

## Support Resources

- **Troubleshooting**: CALIBRATION_TROUBLESHOOTING.md
- **Maintenance**: OBJECT_DETECTION_MAINTENANCE.md
- **Implementation**: 08_OBJECT_DETECTION.md
- **Calibration Results**: FINAL_CALIBRATION_RESULTS_2025-11-09.md
- **Testing Guide**: OBJECT_DETECTION_TESTING.md

---

**Document Version**: 1.0 (Nov 9, 2025)
**Migration Target**: Nov 9, 2025 Calibration (HSV + Size + Circularity + Combined Scoring)
**Success Rate**: 100% detection on 20-sample validation dataset
