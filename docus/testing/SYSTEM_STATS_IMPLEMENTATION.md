# System Stats Implementation Summary

## Overview

Added real-time system performance monitoring to the web UI header, displaying CPU usage, RAM usage, and CPU temperature (Raspberry Pi only). This helps with debugging and performance optimization.

## Implementation

### 1. Backend Changes

#### Dependencies (`pyproject.toml`)
Added `psutil` library for system metrics collection.

#### New Handler (`msmacro/daemon_handlers/system_commands.py`)
Created `SystemCommandHandler` with `system_stats()` method that collects:
- CPU usage percentage
- CPU core count
- Memory usage and availability
- Disk usage and free space
- CPU temperature (Pi-specific)
- System uptime

#### Dispatcher (`msmacro/daemon_handlers/command_dispatcher.py`)
- Added `SystemCommandHandler` import
- Registered `system_handler` instance
- Added `system_stats` command routing

#### Web API (`msmacro/web/handlers.py`)
Created `api_system_stats()` endpoint that calls daemon IPC command.

#### Server (`msmacro/web/server.py`)
- Added `api_system_stats` import
- Registered route: `GET /api/system/stats`

### 2. Frontend Changes

#### API Client (`webui/src/api.js`)
Added `getSystemStats()` function that calls `/api/system/stats`.

#### Header Component (`webui/src/components/Header.jsx`)
Added `SystemStats` component that:
- Fetches stats every 3 seconds
- Displays CPU and RAM usage with color-coded indicators
- Shows CPU temperature (if available)
- Auto-refreshes in background

### 3. Documentation

#### User Documentation
- **docus/07_SYSTEM_MONITORING.md** - Complete user guide
  - Visual indicators and thresholds
  - API reference
  - Performance optimization tips
  - Troubleshooting guide

#### Documentation Organization
- **docus/README.md** - Documentation index and organization
- Moved implementation notes to `docus/archived/`
- Moved testing guides to `docus/testing/`

## Files Changed

```
pyproject.toml                                      (added psutil)
msmacro/daemon_handlers/system_commands.py          (new - system stats handler)
msmacro/daemon_handlers/command_dispatcher.py       (registered handler)
msmacro/web/handlers.py                             (new endpoint)
msmacro/web/server.py                               (registered route)
webui/src/api.js                                    (added API client function)
webui/src/components/Header.jsx                     (added system stats display)
docus/07_SYSTEM_MONITORING.md                       (new - user documentation)
docus/README.md                                     (new - documentation index)
docus/testing/                                      (new directory)
docus/archived/                                     (new directory)
```

## API Usage

### Endpoint

```
GET /api/system/stats
```

### Response

```json
{
  "cpu_percent": 45.2,
  "cpu_count": 4,
  "memory_percent": 62.5,
  "memory_available_mb": 1024.3,
  "memory_total_mb": 2048.0,
  "disk_percent": 35.8,
  "disk_free_gb": 12.45,
  "temperature": 55.3,
  "uptime_seconds": 86400
}
```

## UI Display

Stats appear in the header on all pages:

```
MS Macro   [CPU: 45%] [RAM: 62%] [55°C]   [Settings] [Debug]
```

**Color Indicators:**
- Green: Normal (CPU < 60%, RAM < 70%, Temp < 60°C)
- Yellow: Warning (CPU 60-79%, RAM 70-84%, Temp 60-69°C)
- Red: Critical (CPU ≥ 80%, RAM ≥ 85%, Temp ≥ 70°C)

## Testing

### Manual Testing

1. **Deploy to Pi**:
   ```bash
   cd ~/msmacro-app
   git pull
   pip3 install -e .  # Install psutil
   cd webui
   npm run build
   ```

2. **Restart daemon**:
   ```bash
   python3 -m msmacro ctl stop
   python3 -m msmacro daemon &
   ```

3. **Verify API**:
   ```bash
   curl http://localhost:8787/api/system/stats | jq
   ```

4. **Check UI**:
   - Open web browser to Pi IP
   - Verify stats in header
   - Check color coding
   - Monitor auto-refresh (every 3s)

### Stress Testing

1. **CPU Load Test**:
   ```bash
   # Generate CPU load
   stress-ng --cpu 4 --timeout 60s
   ```
   - Verify stats turn yellow/red
   - Check temperature increases

2. **Memory Load Test**:
   ```bash
   # Generate memory pressure
   stress-ng --vm 2 --vm-bytes 512M --timeout 60s
   ```
   - Verify memory percentage increases
   - Check color indicators

### Error Testing

1. **Missing psutil**:
   ```bash
   pip3 uninstall psutil
   ```
   - API should return error
   - UI should handle gracefully (no display)

2. **Daemon not running**:
   ```bash
   python3 -m msmacro ctl stop
   ```
   - API request should timeout
   - UI should not crash

## Performance Impact

- **Backend**: Negligible (~0.1s CPU for collection)
- **Frontend**: Minimal (3s polling interval)
- **Network**: ~300 bytes per request

## Deployment Checklist

- [ ] Install psutil: `pip3 install -e .`
- [ ] Build frontend: `cd webui && npm run build`
- [ ] Restart daemon
- [ ] Test API endpoint
- [ ] Verify UI display
- [ ] Check color indicators
- [ ] Monitor for 5 minutes (auto-refresh)
- [ ] Test on actual Pi hardware
- [ ] Verify temperature reading (Pi-specific)

## Known Limitations

1. **Temperature**: Only available on Raspberry Pi (Linux thermal zone)
2. **Update Rate**: 3-second intervals (balance between freshness and load)
3. **Precision**: CPU percent uses 0.1s interval (trade-off for responsiveness)

## Future Enhancements

Possible improvements:

- **Historical graphs**: Chart stats over time
- **Alerts**: Notify when thresholds exceeded
- **Detailed view**: Expandable panel with more metrics
- **Process list**: Top processes by CPU/RAM
- **Network stats**: Bandwidth usage
- **Disk I/O**: Read/write rates

---

**Version**: 1.0  
**Date**: 2025-01-07  
**Impact**: Low risk - additive feature, no breaking changes
