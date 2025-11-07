# System Monitoring

## Overview

MSMacro provides real-time system performance monitoring displayed in the web UI header. This helps with debugging and performance optimization, especially on resource-constrained Raspberry Pi devices.

## Features

The system stats display shows:

- **CPU Usage**: Overall CPU utilization percentage
- **RAM Usage**: Memory consumption percentage  
- **Temperature**: CPU temperature (Raspberry Pi only)

Stats are updated every 3 seconds and displayed in the header of all pages.

## Visual Indicators

### CPU Usage Colors

- **Green** (< 60%): Normal operation
- **Yellow** (60-79%): Moderate load
- **Red** (≥ 80%): High load - may affect performance

### RAM Usage Colors

- **Green** (< 70%): Normal operation
- **Yellow** (70-84%): Moderate usage
- **Red** (≥ 85%): High usage - may cause issues

### Temperature Colors (Pi only)

- **Green** (< 60°C): Normal operating temperature
- **Yellow** (60-69°C): Warm - consider cooling
- **Red** (≥ 70°C): Hot - check ventilation

## API Reference

### Get System Stats

```
GET /api/system/stats
```

**Response:**

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

**Fields:**

- `cpu_percent` (float): CPU usage percentage (0-100)
- `cpu_count` (int): Number of CPU cores
- `memory_percent` (float): RAM usage percentage (0-100)
- `memory_available_mb` (float): Available RAM in megabytes
- `memory_total_mb` (float): Total RAM in megabytes
- `disk_percent` (float): Disk usage percentage (0-100)
- `disk_free_gb` (float): Free disk space in gigabytes
- `temperature` (float|null): CPU temperature in Celsius (null if unavailable)
- `uptime_seconds` (int): System uptime in seconds

## Performance Optimization

### High CPU Usage

If CPU consistently > 80%:

1. **Check active processes**: `top` or `htop`
2. **Review map configuration**: Use smaller detection regions
3. **Reduce recording frequency**: Adjust playback/recording settings
4. **Check CV detection**: May be processing too large of an area

### High RAM Usage

If RAM consistently > 85%:

1. **Check memory usage**: `free -m`
2. **Review skill configurations**: Large skill sets consume more memory
3. **Restart daemon**: May help clear memory leaks
4. **Reduce frame buffer**: Check CV configuration

### High Temperature

If temperature > 70°C:

1. **Improve cooling**: Add heatsink or fan
2. **Check CPU load**: Reduce workload if possible
3. **Verify ventilation**: Ensure air flow around Pi
4. **Monitor throttling**: Check `vcgencmd get_throttled`

## Troubleshooting

### Stats Not Displaying

**Symptom**: No system stats visible in header

**Solutions**:

1. **Check API endpoint**:
   ```bash
   curl http://localhost:8787/api/system/stats
   ```

2. **Verify daemon is running**:
   ```bash
   ps aux | grep msmacro
   ```

3. **Check browser console**: Look for JavaScript errors

4. **Verify psutil installed**:
   ```bash
   python3 -c "import psutil; print(psutil.__version__)"
   ```

### Temperature Shows Null

**Symptom**: Temperature field is `null` in response

**Cause**: Not running on Raspberry Pi, or thermal zone not available

**Note**: Temperature monitoring is Pi-specific. On other platforms, this field will be `null`.

### Inaccurate Stats

**Symptom**: Stats seem incorrect or stale

**Solutions**:

1. **Clear browser cache**: Hard refresh (Ctrl+Shift+R)
2. **Check update interval**: Should poll every 3 seconds
3. **Verify system load**: Compare with `top` command
4. **Restart daemon**: May resolve stale data

## Implementation Details

### Backend

System stats are collected using the `psutil` library:

- CPU: `psutil.cpu_percent(interval=0.1)`
- Memory: `psutil.virtual_memory()`
- Disk: `psutil.disk_usage('/')`
- Temperature: `/sys/class/thermal/thermal_zone0/temp` (Linux/Pi only)

### Frontend

Stats are displayed in the Header component:

- Auto-refreshes every 3 seconds
- Color-coded indicators based on thresholds
- Graceful fallback if API unavailable

### IPC Command

Daemon command: `system_stats`

Handler: `msmacro/daemon_handlers/system_commands.py`

## Development

### Adding New Metrics

To add new system metrics:

1. **Update backend handler** (`system_commands.py`):
   ```python
   # Add new metric collection
   new_metric = get_new_metric()
   return {
       ...,
       "new_metric": new_metric
   }
   ```

2. **Update frontend** (`Header.jsx`):
   ```javascript
   {stats.new_metric && (
     <div className="flex items-center gap-1">
       <span>{stats.new_metric}</span>
     </div>
   )}
   ```

3. **Document thresholds**: Update this guide with appropriate warnings

### Testing

Test system stats endpoint:

```bash
# Get current stats
curl http://localhost:8787/api/system/stats | jq

# Monitor continuously
watch -n 3 'curl -s http://localhost:8787/api/system/stats | jq'
```

## Related Documentation

- `01_ARCHITECTURE.md` - System architecture
- `05_API_REFERENCE.md` - Complete API reference
- `06_MAP_CONFIGURATION.md` - Performance optimization via map configuration

---

**Version**: 1.0  
**Last Updated**: 2025-01-07  
**Dependencies**: psutil library (added to pyproject.toml)
