# Object Detection Maintenance Guide

**Last Updated**: Nov 9, 2025 (v1.0)
**Target Audience**: System administrators, DevOps engineers, power users
**Maintenance Schedule**: Weekly monitoring, monthly reviews, quarterly re-calibration checks

---

## Overview

This guide covers long-term maintenance of the object detection system, including health monitoring, performance optimization, and when to re-calibrate.

---

## Maintenance Philosophy

**Proactive > Reactive**: Monitor metrics weekly to catch degradation early
**Automate Monitoring**: Set up alerts for detection rate drops
**Document Changes**: Log all calibration updates and parameter tuning
**Test Before Deploy**: Always validate on test dataset before production changes

---

## When to Re-Calibrate

### Immediate Re-Calibration Required

1. **Game Graphics Update**
   - New game patch changes minimap appearance
   - Color scheme modifications
   - UI overlay changes affecting minimap

   **How to Detect**: Visual inspection after game update

   **Action**:
   ```bash
   # Capture new samples after update
   # Run calibration wizard
   # Validate on 20+ frames before deploying
   ```

2. **Detection Rate Drops Below 85%**
   - Sudden drop from 90%+ to <85%
   - Player dots consistently missed

   **How to Detect**: Weekly monitoring (see Health Monitoring section)

   **Action**:
   ```bash
   # Investigate root cause first (see CALIBRATION_TROUBLESHOOTING.md)
   # If HSV drift detected, re-calibrate
   ```

3. **False Positive Rate >10%**
   - System detecting UI elements as player dots
   - Other player count > actual count

   **How to Detect**: False positive logging + manual validation

   **Action**:
   ```bash
   # Tighten HSV ranges via calibration wizard
   # Increase circularity threshold
   # Narrow size bounds
   ```

### Recommended Re-Calibration

4. **Hardware Changes**
   - New Raspberry Pi model
   - Different HDMI capture card
   - New monitor/display (affects HDMI output)

   **Rationale**: Different hardware may have different color profiles

5. **Seasonal/Lighting Changes** (if applicable)
   - Game has day/night cycles affecting minimap
   - Different times of day affect HDMI signal

   **Frequency**: Test quarterly, re-calibrate if drift detected

6. **After 6-12 Months**
   - Even with no changes, gradual drift possible
   - Accumulated game patches, hardware aging

   **Frequency**: Quarterly preventive re-calibration

### Optional Re-Calibration

7. **Performance Optimization**
   - Current detection <15ms but want faster
   - Experimenting with tighter filters

   **Risk**: May reduce recall if over-optimized

8. **New Map/Region**
   - Different maps have different color schemes
   - Some regions may need separate configs

   **Strategy**: Maintain per-map configs if needed

---

## Health Monitoring

### Daily Checks (Automated)

**Setup Cron Job** (on Raspberry Pi):
```bash
# /etc/cron.daily/msmacro-health-check
#!/bin/bash

# Check detection rate over last 24 hours
DETECTIONS=$(grep "player.*detected.*true" /var/log/msmacro.log | wc -l)
TOTAL_FRAMES=$(grep "player.*detected" /var/log/msmacro.log | wc -l)

if [ $TOTAL_FRAMES -gt 0 ]; then
    RATE=$((DETECTIONS * 100 / TOTAL_FRAMES))

    if [ $RATE -lt 85 ]; then
        echo "WARNING: Detection rate dropped to ${RATE}% (target: ≥90%)" | \
            mail -s "MSMacro Detection Alert" admin@example.com
    fi
fi

# Check performance
AVG_TIME=$(grep "detection.*ms" /var/log/msmacro.log | \
    awk '{sum+=$NF; count++} END {print sum/count}')

if (( $(echo "$AVG_TIME > 15" | bc -l) )); then
    echo "WARNING: Average detection time ${AVG_TIME}ms exceeds 15ms target" | \
        mail -s "MSMacro Performance Alert" admin@example.com
fi
```

Make executable:
```bash
chmod +x /etc/cron.daily/msmacro-health-check
```

### Weekly Monitoring

**Run Weekly Report Script**:

Save as `weekly_report.sh`:
```bash
#!/bin/bash
# Generate weekly detection health report

echo "=== MSMacro Object Detection Weekly Report ==="
echo "Week Ending: $(date)"
echo ""

# Detection rate
echo "Detection Rate:"
DETECTED=$(grep "player.*detected.*true" /var/log/msmacro.log.1 /var/log/msmacro.log | wc -l)
TOTAL=$(grep "player.*detected" /var/log/msmacro.log.1 /var/log/msmacro.log | wc -l)
RATE=$((DETECTED * 100 / TOTAL))
echo "  $DETECTED / $TOTAL frames ($RATE%)"
echo "  Target: ≥90%"
echo "  Status: $([ $RATE -ge 90 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo ""

# False positives
echo "False Positive Check:"
FP=$(grep "other_players.*count.*[^0]" /var/log/msmacro.log.1 /var/log/msmacro.log | \
     grep -v "sample_20251109_163144\|sample_20251109_163909" | wc -l)
echo "  $FP unexpected other player detections"
echo "  Target: <10% of frames"
echo "  Status: $([ $FP -lt $((TOTAL / 10)) ] && echo '✅ PASS' || echo '⚠️  REVIEW')"
echo ""

# Performance
echo "Performance:"
AVG=$(grep "detection.*ms" /var/log/msmacro.log.1 /var/log/msmacro.log | \
      awk '{sum+=$NF; count++} END {printf "%.2f", sum/count}')
MAX=$(grep "detection.*ms" /var/log/msmacro.log.1 /var/log/msmacro.log | \
      awk 'BEGIN{max=0} {if($NF>max) max=$NF} END{print max}')
echo "  Average: ${AVG}ms"
echo "  Max: ${MAX}ms"
echo "  Target: <15ms"
echo "  Status: $(awk -v avg="$AVG" 'BEGIN{print (avg<15)?"✅ PASS":"❌ FAIL"}')  "
echo ""

# Recommendations
echo "Recommendations:"
if [ $RATE -lt 90 ]; then
    echo "  ⚠️  Detection rate below target - investigate and re-calibrate if needed"
fi
if (( $(echo "$AVG > 15" | bc -l) )); then
    echo "  ⚠️  Performance degraded - check CPU load and optimize filters"
fi
if [ $RATE -ge 90 ] && (( $(echo "$AVG < 15" | bc -l) )); then
    echo "  ✅ System healthy - continue monitoring"
fi
```

**Run Weekly**:
```bash
chmod +x weekly_report.sh
./weekly_report.sh > /tmp/msmacro_weekly_$(date +%Y%m%d).txt
```

### Monthly Review

**Checklist**:
- [ ] Review 4 weekly reports
- [ ] Check trend: Is detection rate stable or declining?
- [ ] Check trend: Is performance stable or degrading?
- [ ] Review any alerts/anomalies from past month
- [ ] Capture 20 new validation samples
- [ ] Run validation script on current config
- [ ] Document any findings in maintenance log

**Validation Script** (monthly):
```bash
# Capture 20 diverse samples
mkdir /tmp/monthly_validation_$(date +%Y%m)

# ... capture samples during various game scenarios ...

# Run validation
python3 /tmp/test_final_algorithm.py
```

**Expected**: ≥90% detection rate

**If <90%**: Schedule re-calibration

---

## Performance Optimization

### Target Performance

| Platform | Target | Typical | Warning Threshold |
|----------|--------|---------|-------------------|
| Pi 4 Model B | <15ms | 8-12ms | >15ms |
| Pi 5 | <10ms | 4-8ms | >10ms |
| Development (x86) | <5ms | 0.5-2ms | >5ms |

### Monitoring Performance

**Real-Time via API**:
```bash
curl http://localhost:5050/api/cv/object-detection/performance
```

**Expected Response**:
```json
{
  "avg_ms": 11.23,
  "max_ms": 14.56,
  "min_ms": 9.87,
  "count": 1000
}
```

### Performance Degradation Troubleshooting

#### Symptom: Average >15ms on Pi 4

**Step 1: Check CPU/Temperature**
```bash
# On Raspberry Pi
vcgencmd measure_temp
vcgencmd measure_clock arm

# Check if throttling
vcgencmd get_throttled
# 0x0 = not throttled, anything else = throttled
```

**Solution** (if throttling):
- Add heatsink/active cooling
- Reduce overclock if applicable
- Lower camera resolution if possible

**Step 2: Check Background Processes**
```bash
top -b -n 1 | head -20
```

**Solution** (if high CPU from other processes):
- Stop unnecessary services
- Move background tasks to off-hours
- Consider dedicated Pi for msmacro

**Step 3: Optimize Filters**

```python
# In object_detection.py or config

# Option 1: Disable optional filters
enable_contrast_validation = False  # Saves ~2-3ms

# Option 2: Reduce morphological kernel
kernel = np.ones((2, 2), np.uint8)  # Reduce from 3x3, saves ~1-2ms

# Option 3: Disable temporal smoothing (last resort)
temporal_smoothing = False  # Saves ~0.5ms, but increases jitter
```

**Step 4: Profile Bottlenecks**

```python
# Add to object_detection.py detect() method
import time

t1 = time.perf_counter()
player = self._detect_player(frame)
t2 = time.perf_counter()
other_players = self._detect_other_players(frame)
t3 = time.perf_counter()

logger.debug(f"Timings: player={t2-t1:.3f}s, other={t3-t2:.3f}s")
```

Identify slowest component and optimize specifically.

---

## Long-Term Stability

### 4-Hour Stability Test

**Run quarterly** to ensure no memory leaks or performance degradation:

```bash
# Save as stability_test.sh
#!/bin/bash

python3 -c "
import sys, time, csv
sys.path.insert(0, '/Users/boweixiao/msmacro-app')

from msmacro.cv.camera import capture_frame
from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig

detector = MinimapObjectDetector(DetectorConfig())
results_file = '/tmp/stability_test_results_$(date +%Y%m%d).csv'

with open(results_file, 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['timestamp', 'detected', 'x', 'y', 'confidence', 'time_ms'])

    for i in range(14400):  # 4 hours at 1 detection/second
        start = time.time()
        frame = capture_frame()
        result = detector.detect(frame)
        elapsed_ms = (time.time() - start) * 1000

        writer.writerow([
            time.time(),
            result.player.detected,
            result.player.x if result.player.detected else -1,
            result.player.y if result.player.detected else -1,
            result.player.confidence if result.player.detected else 0,
            elapsed_ms
        ])

        if i % 100 == 0:
            print(f'Progress: {i/144:.1f}% ({i}/14400 frames)', flush=True)

        time.sleep(1)

print(f'Test complete. Results: {results_file}')
"

# Analyze results
python3 -c "
import pandas as pd
df = pd.read_csv('/tmp/stability_test_results_$(date +%Y%m%d).csv')

print('=== 4-Hour Stability Test Results ===')
print(f'Detection rate: {df[\"detected\"].mean()*100:.1f}%')
print(f'Average time: {df[\"time_ms\"].mean():.2f}ms')
print(f'Max time: {df[\"time_ms\"].max():.2f}ms')
print(f'Time std dev: {df[\"time_ms\"].std():.2f}ms')

# Check for degradation over time
df['hour'] = pd.to_datetime(df['timestamp'], unit='s').dt.hour
hourly = df.groupby('hour')['time_ms'].mean()
print(f'\\nHourly performance trend:')
print(hourly)

if hourly.max() - hourly.min() > 5:
    print('⚠️  WARNING: Performance degradation detected (>5ms variance)')
else:
    print('✅ Performance stable over 4-hour period')
"
```

**Expected Results**:
- Detection rate: >90% throughout
- Performance: <15ms average, <20ms max
- No degradation over time (hourly averages within 5ms)
- No memory leaks (check with `htop` during test)

### Memory Leak Check

**Monitor during stability test**:
```bash
# In separate terminal
watch -n 60 'ps aux | grep msmacro | grep -v grep | awk "{print \$6}"'
```

**Expected**: Memory usage stable (not increasing over time)

**If increasing >10MB/hour**: Investigate for leaks (likely in image processing or logging)

---

## Configuration Management

### Version Control

**Track calibration changes**:
```bash
# Create calibration history directory
mkdir -p ~/.local/share/msmacro/calibration_history

# Backup config after each calibration
cp ~/.local/share/msmacro/object_detection_config.json \
   ~/.local/share/msmacro/calibration_history/config_$(date +%Y%m%d_%H%M%S).json

# Document reason
echo "$(date): Re-calibrated due to game update 1.2.3" >> \
   ~/.local/share/msmacro/calibration_history/CHANGELOG.txt
```

### Recommended Configurations

**Keep these on hand for quick rollback**:

1. **Known-Good Baseline** (Nov 9, 2025):
   ```json
   {
     "player": {
       "color_range": {
         "hsv_lower": [26, 67, 64],
         "hsv_upper": [85, 255, 255]
       },
       "blob_size_min": 4,
       "blob_size_max": 16,
       "circularity_min": 0.71
     }
   }
   ```

2. **High Recall** (if missing detections):
   ```json
   {
     "player": {
       "color_range": {
         "hsv_lower": [20, 50, 50],  // Wider HSV
         "hsv_upper": [90, 255, 255]
       },
       "blob_size_min": 2,  // Smaller min
       "blob_size_max": 20,  // Larger max
       "circularity_min": 0.65  // Less strict
     }
   }
   ```

3. **High Precision** (if false positives):
   ```json
   {
     "player": {
       "color_range": {
         "hsv_lower": [30, 80, 80],  // Tighter HSV
         "hsv_upper": [80, 255, 255]
       },
       "blob_size_min": 4,
       "blob_size_max": 12,  // Stricter max
       "circularity_min": 0.75  // More strict
     }
   }
   ```

---

## Maintenance Log Template

**Keep a log** at `~/.local/share/msmacro/MAINTENANCE_LOG.md`:

```markdown
# MSMacro Object Detection Maintenance Log

## 2025-11-09: Initial Deployment
- Deployed Nov 9 calibration (100% detection rate)
- HSV: (26,67,64)-(85,255,255)
- Size: 4-16px, Circularity: 0.71
- Performance: 0.79ms avg on dev, 11ms on Pi 4
- Validation: 20/20 samples

## 2025-11-16: Weekly Check
- Detection rate: 98% (target: ≥90%) ✅
- Performance: 12ms avg (target: <15ms) ✅
- No issues

## 2025-12-01: Monthly Review
- Reviewed 4 weekly reports - all passing
- Ran validation on 20 new samples - 19/20 (95%)
- One missed detection in low-light scenario
- Decision: Monitor for another month

## 2026-01-15: Game Update 1.2.3
- Game patch changed minimap slightly
- Detection rate dropped to 82%
- Re-calibrated via web UI wizard
- New HSV: (28,70,65)-(88,255,255) (slightly adjusted)
- Validation: 20/20 (100%)
- Deployed to production

[Continue logging all significant events...]
```

---

## Alerting Setup

### Email Alerts (Simple)

**Install mailutils**:
```bash
sudo apt-get install mailutils
```

**Configure in cron scripts** (see Daily Checks section above)

### Monitoring Dashboard (Advanced)

**Option 1: Grafana + InfluxDB**

Export metrics to InfluxDB:
```python
# In object_detection.py
from influxdb_client import InfluxDBClient, Point

def log_to_influx(result, elapsed_ms):
    client = InfluxDBClient(url="http://localhost:8086", token="...", org="msmacro")
    point = Point("detection") \
        .tag("type", "player") \
        .field("detected", 1 if result.player.detected else 0) \
        .field("confidence", result.player.confidence) \
        .field("time_ms", elapsed_ms)

    write_api = client.write_api()
    write_api.write(bucket="msmacro", record=point)
```

Visualize in Grafana:
- Detection rate over time
- Performance trend
- Confidence score distribution

**Option 2: Prometheus + Grafana**

Export metrics endpoint:
```python
# In web.py
from prometheus_client import Counter, Histogram, generate_latest

detection_counter = Counter('msmacro_detections_total', 'Total detections')
detection_time = Histogram('msmacro_detection_seconds', 'Detection time')

@app.route('/metrics')
async def metrics(request):
    return web.Response(text=generate_latest(), content_type='text/plain')
```

---

## Disaster Recovery

### Backup Strategy

**What to Backup**:
1. Config file: `~/.local/share/msmacro/object_detection_config.json`
2. Calibration history: `~/.local/share/msmacro/calibration_history/`
3. Maintenance log: `~/.local/share/msmacro/MAINTENANCE_LOG.md`
4. Validation samples: `~/msmacro-validation-dataset/`

**Backup Script** (run weekly):
```bash
#!/bin/bash
BACKUP_DIR="/backup/msmacro/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

cp ~/.local/share/msmacro/object_detection_config.json $BACKUP_DIR/
cp -r ~/.local/share/msmacro/calibration_history $BACKUP_DIR/
cp ~/.local/share/msmacro/MAINTENANCE_LOG.md $BACKUP_DIR/

tar -czf $BACKUP_DIR/validation_samples.tar.gz ~/msmacro-validation-dataset/

# Keep only last 4 weeks
find /backup/msmacro/ -type d -mtime +28 -exec rm -rf {} \;
```

### Restore Procedure

**If config corrupted**:
```bash
# Restore from latest backup
cp /backup/msmacro/20251109/object_detection_config.json \
   ~/.local/share/msmacro/object_detection_config.json

# Restart daemon
python3 -m msmacro ctl stop
python3 -m msmacro daemon &
```

**If complete system failure**:
```bash
# Restore all configs
cp -r /backup/msmacro/20251109/* ~/.local/share/msmacro/

# Re-deploy code
cd ~/msmacro-app
git checkout <last-known-good-commit>

# Restart
python3 -m msmacro daemon &
```

---

## Summary: Monthly Maintenance Routine

**Time Required**: 30-60 minutes/month

1. **Review Weekly Reports** (10 min)
   - Check detection rate trend
   - Check performance trend
   - Note any anomalies

2. **Run Validation** (15 min)
   - Capture 20 new diverse samples
   - Run test_final_algorithm.py
   - Document results in maintenance log

3. **Performance Check** (5 min)
   - Query `/api/cv/object-detection/performance`
   - Compare to baseline (0.79ms dev, 11ms Pi4)
   - Flag if >25% degradation

4. **Re-Calibration Decision** (5 min)
   - Detection rate <90%? → Re-calibrate
   - False positive rate >10%? → Re-calibrate
   - Game update? → Re-calibrate
   - Hardware change? → Re-calibrate
   - Otherwise → Monitor for another month

5. **Backup** (5 min)
   - Run backup script
   - Verify backups readable

6. **Update Log** (10 min)
   - Document findings in MAINTENANCE_LOG.md
   - Note any configuration changes
   - Flag any concerns for next month

**Decision Tree**:
```
Detection ≥90% AND Performance <15ms?
├─ YES: System healthy, continue monitoring
└─ NO:
   ├─ Detection <90%? → Re-calibrate
   ├─ Performance >15ms? → Optimize (see Performance section)
   └─ Both issues? → Re-calibrate first, then optimize
```

---

**Document Version**: 1.0 (Nov 9, 2025)
**Maintenance Target**: ≥90% detection rate, <15ms performance on Pi 4
**Review Frequency**: Weekly monitoring, monthly validation, quarterly deep-dive
