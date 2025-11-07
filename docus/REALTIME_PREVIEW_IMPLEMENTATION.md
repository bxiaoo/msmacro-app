# Real-Time Preview & Performance Monitoring Implementation Plan

**Document Version**: 1.2
**Created**: 2025-01-07
**Last Updated**: 2025-01-07
**Status**: ✅ Phase 1 Complete (Preview Features) | 📅 Phase 2 Deferred (Performance Stats)
**Purpose**: Real-time preview feedback during map configuration and Pi performance monitoring

## Approved Decisions

✅ **Preview Debounce**: 500ms (updates 0.5s after user stops adjusting)
✅ **Thumbnail Size**: 50% scale (170×43px in list view)
✅ **Performance Stats Location**: Header.jsx (always visible) - **DEFERRED to Phase 2**
✅ **Implementation Priority**: Preview features first, performance stats later

---

## Problem Statement

After initial testing on Raspberry Pi, several UX issues were identified:

### Issues Discovered

1. **No Preview During Configuration**
   - Users can't see what region they're configuring
   - Must save and activate config before seeing detection area
   - Trial-and-error approach is frustrating

2. **Preview Shows Entire Screen**
   - Current preview shows full 1280x720 frame
   - User can't clearly see the cropped detection region
   - Difficult to verify coordinates are correct

3. **No Real-Time Feedback**
   - Adjusting X/Y coordinates doesn't show immediate visual feedback
   - User must guess if coordinates are correct
   - No way to validate before saving

4. **No Preview Confirmation in List**
   - After activating a config, no visual confirmation
   - User can't see what area is actually being detected
   - Requires navigating to separate preview section

5. **No Performance Visibility**
   - Can't verify performance improvements in real-time
   - No CPU/memory usage displayed
   - Difficult to debug performance issues on Pi

---

## Solution Overview

### Feature 1: Real-Time Preview During Configuration

**What**: Show live mini-map preview while creating/editing configuration

**How**:
- New API endpoint: `GET /api/cv/mini-map-preview?x={x}&y={y}&w={w}&h={h}&t={timestamp}`
- Returns cropped region as JPEG image
- Frontend polls this endpoint as user adjusts coordinates
- Debounce API calls (500ms) to avoid overloading Pi

**Benefits**:
- Immediate visual feedback
- User can fine-tune coordinates accurately
- Reduces trial-and-error iterations
- Better user experience

### Feature 2: Cropped Preview (Mini-Map Only)

**What**: Preview shows only the configured region, not entire screen

**How**:
- Backend crops frame to (x, y, width, height) before encoding
- Returns smaller JPEG (e.g., 340x86 instead of 1280x720)
- Reduces bandwidth and improves responsiveness
- Shows exactly what CV system will process

**Benefits**:
- Clearer visualization of detection area
- Faster image loading (smaller size)
- User sees exactly what system detects
- Better for low-bandwidth scenarios

### Feature 3: Preview Thumbnails in List View

**What**: Show mini-map preview thumbnail inside activated config card

**How**:
- When config is activated, fetch mini-map preview
- Display thumbnail (e.g., 170x43 - 50% scale) inside list item
- Auto-refresh every 2 seconds
- Only show for active config to save resources

**Benefits**:
- Visual confirmation of active config
- Quick verification without scrolling
- At-a-glance detection status
- Consolidated information

### Feature 4: Pi Performance Monitoring

**What**: Display real-time CPU, memory, and temperature stats

**How**:
- New API endpoint: `GET /api/system/performance`
- Returns: CPU%, memory%, disk%, temperature (if available)
- Frontend displays stats in compact widget
- Auto-refresh every 5 seconds
- Show comparison: before/after config activation

**Benefits**:
- Verify performance improvements in real-time
- Debug performance issues quickly
- Monitor Pi health (temperature)
- Validate 3-5x improvement claims

---

## Technical Implementation

### Backend Changes

#### 1. Mini-Map Preview Endpoint

**File**: `msmacro/web/handlers.py`

**New Handler**:
```python
async def api_cv_minimap_preview(request):
    """
    Get cropped mini-map preview image.

    Query params:
    - x: Top-left X coordinate (default: 68)
    - y: Top-left Y coordinate (default: 56)
    - w: Width (default: 340)
    - h: Height (default: 86)
    - t: Timestamp (for cache busting)

    Returns: JPEG image of cropped region
    """
    try:
        x = int(request.query.get('x', 68))
        y = int(request.query.get('y', 56))
        w = int(request.query.get('w', 340))
        h = int(request.query.get('h', 86))

        # Validate bounds
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            return web.Response(status=400, text='Invalid coordinates')

        if x + w > 1280 or y + h > 720:
            return web.Response(status=400, text='Coordinates out of bounds')

        # Get current frame from capture
        capture = get_capture_instance()
        frame_data = capture.get_latest_frame()

        if not frame_data or not frame_data.get('jpeg_data'):
            return web.Response(status=503, text='No frame available')

        # Decode JPEG to numpy array
        import cv2
        import numpy as np
        jpeg_bytes = frame_data['jpeg_data']
        frame = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)

        # Crop to region
        cropped = frame[y:y+h, x:x+w]

        # Draw red border (optional)
        cv2.rectangle(cropped, (0, 0), (w-1, h-1), (0, 0, 255), 2)

        # Encode as JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        _, jpeg_data = cv2.imencode('.jpg', cropped, encode_param)

        return web.Response(
            body=jpeg_data.tobytes(),
            content_type='image/jpeg',
            headers={'Cache-Control': 'no-cache'}
        )

    except Exception as e:
        logger.error(f"Mini-map preview error: {e}")
        return web.Response(status=500, text=str(e))
```

**Route**: `app.router.add_get('/api/cv/mini-map-preview', api_cv_minimap_preview)`

#### 2. System Performance Endpoint

**File**: `msmacro/web/handlers.py`

**New Handler**:
```python
async def api_system_performance(request):
    """
    Get system performance metrics.

    Returns:
    {
      "cpu_percent": 15.3,
      "memory_percent": 42.1,
      "memory_used_mb": 512,
      "memory_total_mb": 1024,
      "disk_percent": 65.2,
      "temperature_c": 58.5,  // if available
      "uptime_seconds": 86400,
      "load_average": [0.5, 0.7, 0.6]  // 1min, 5min, 15min
    }
    """
    try:
        import psutil

        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Memory usage
        mem = psutil.virtual_memory()
        memory_percent = mem.percent
        memory_used_mb = mem.used / (1024 * 1024)
        memory_total_mb = mem.total / (1024 * 1024)

        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent

        # Temperature (Pi specific)
        temperature_c = None
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temperature_c = int(f.read().strip()) / 1000.0
        except:
            pass

        # Uptime
        import time
        uptime_seconds = time.time() - psutil.boot_time()

        # Load average
        load_avg = psutil.getloadavg()

        return web.json_response({
            'cpu_percent': round(cpu_percent, 1),
            'memory_percent': round(memory_percent, 1),
            'memory_used_mb': round(memory_used_mb, 1),
            'memory_total_mb': round(memory_total_mb, 1),
            'disk_percent': round(disk_percent, 1),
            'temperature_c': round(temperature_c, 1) if temperature_c else None,
            'uptime_seconds': int(uptime_seconds),
            'load_average': [round(x, 2) for x in load_avg]
        })

    except Exception as e:
        logger.error(f"Performance metrics error: {e}")
        return web.json_response({'error': str(e)}, status=500)
```

**Route**: `app.router.add_get('/api/system/performance', api_system_performance)`

#### 3. Capture Instance Method

**File**: `msmacro/cv/capture.py`

**Add Method**:
```python
def get_latest_frame(self) -> Dict[str, Any]:
    """
    Get the latest captured frame data.

    Returns:
    {
      'jpeg_data': bytes,  // JPEG encoded frame
      'timestamp': float,
      'width': int,
      'height': int,
      'size_bytes': int
    }
    """
    with self._lock:
        if not self._last_frame:
            return {}

        return {
            'jpeg_data': self._last_frame.get('jpeg_data'),
            'timestamp': self._last_frame.get('timestamp'),
            'width': self._last_frame.get('width'),
            'height': self._last_frame.get('height'),
            'size_bytes': self._last_frame.get('size_bytes')
        }
```

**Note**: Assumes `_last_frame` is already stored in capture loop (may need to add this)

---

### Frontend Changes

#### 1. API Client Functions

**File**: `webui/src/api.js`

**Add Functions**:
```javascript
export function getMiniMapPreviewURL(x, y, w, h) {
  // Return URL with cache busting
  return `/api/cv/mini-map-preview?x=${x}&y=${y}&w=${w}&h=${h}&t=${Date.now()}`;
}

export function getSystemPerformance() {
  return API("/api/system/performance");
}
```

#### 2. CVConfiguration Component Updates

**File**: `webui/src/components/CVConfiguration.jsx`

**Changes**:

1. **Add State for Preview**:
```javascript
const [previewCoords, setPreviewCoords] = useState(null)
const [miniMapPreviewUrl, setMiniMapPreviewUrl] = useState(null)
```

2. **Add Debounced Preview Update**:
```javascript
import { useEffect, useRef, useCallback } from 'react'

const debounceTimer = useRef(null)

const updatePreview = useCallback((x, y, w, h) => {
  // Debounce to avoid spamming API
  if (debounceTimer.current) {
    clearTimeout(debounceTimer.current)
  }

  debounceTimer.current = setTimeout(() => {
    setMiniMapPreviewUrl(getMiniMapPreviewURL(x, y, w, h))
  }, 500) // 500ms delay
}, [])

// Update preview when coords change
useEffect(() => {
  if (isCreating) {
    updatePreview(coords.x, coords.y, coords.width, coords.height)
  }
}, [coords, isCreating, updatePreview])
```

3. **Update Create Form with Preview**:
```javascript
const renderCreateForm = () => (
  <div className="bg-gray-50 rounded-lg p-6 space-y-4">
    {/* ... existing controls ... */}

    {/* Real-time Preview */}
    <div className="bg-white rounded-lg p-4 border border-gray-200">
      <h4 className="text-sm font-medium text-gray-700 mb-2">Preview</h4>
      {miniMapPreviewUrl ? (
        <img
          src={miniMapPreviewUrl}
          alt="Mini-map preview"
          className="w-full h-auto rounded border border-gray-300"
          onError={() => setMiniMapPreviewUrl(null)}
        />
      ) : (
        <div className="flex items-center justify-center py-8 text-gray-400">
          <Camera size={32} />
          <p className="text-sm ml-2">Loading preview...</p>
        </div>
      )}
      <p className="text-xs text-gray-500 mt-2">
        Position: ({coords.x}, {coords.y}) · Size: {coords.width}×{coords.height}
      </p>
    </div>

    {/* ... existing save button ... */}
  </div>
)
```

4. **Update Config List with Thumbnail**:
```javascript
const [activeThumbnailUrl, setActiveThumbnailUrl] = useState(null)

useEffect(() => {
  if (activeConfig) {
    // Update thumbnail every 2 seconds
    const updateThumbnail = () => {
      setActiveThumbnailUrl(getMiniMapPreviewURL(
        activeConfig.tl_x,
        activeConfig.tl_y,
        activeConfig.width,
        activeConfig.height
      ))
    }

    updateThumbnail()
    const interval = setInterval(updateThumbnail, 2000)
    return () => clearInterval(interval)
  } else {
    setActiveThumbnailUrl(null)
  }
}, [activeConfig])

const renderConfigList = () => (
  <div className="space-y-2">
    {mapConfigs.map((config) => (
      <div key={config.name} className="bg-gray-50 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Checkbox
              checked={config.is_active}
              onChange={() => handleActivateConfig(config)}
            />
            <div>
              <div className="text-sm font-medium text-gray-900">{config.name}</div>
              <div className="text-xs text-gray-500">
                Position: ({config.tl_x}, {config.tl_y}) · Size: {config.width}×{config.height}
              </div>
            </div>
          </div>
          <Button onClick={() => handleDeleteConfig(config.name)} variant="ghost" size="sm" disabled={config.is_active}>
            <Trash2 size={16} />
          </Button>
        </div>

        {/* Thumbnail for active config */}
        {config.is_active && activeThumbnailUrl && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <img
              src={activeThumbnailUrl}
              alt="Active mini-map preview"
              className="w-full h-auto rounded border border-gray-300"
              style={{ maxHeight: '100px' }}
            />
            <p className="text-xs text-gray-500 mt-1">Live preview (updates every 2s)</p>
          </div>
        )}
      </div>
    ))}
  </div>
)
```

#### 3. Performance Stats Component

**File**: `webui/src/components/CVConfiguration.jsx`

**Add Performance Display**:
```javascript
const [performance, setPerformance] = useState(null)

useEffect(() => {
  const loadPerformance = async () => {
    try {
      const data = await getSystemPerformance()
      setPerformance(data)
    } catch (err) {
      console.error('Failed to load performance:', err)
    }
  }

  loadPerformance()
  const interval = setInterval(loadPerformance, 5000) // Every 5 seconds
  return () => clearInterval(interval)
}, [])

const renderPerformanceStats = () => {
  if (!performance) return null

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-700 mb-3">System Performance</h3>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-gray-600">CPU Usage</div>
          <div className={`text-lg font-mono ${performance.cpu_percent > 80 ? 'text-red-600' : 'text-gray-900'}`}>
            {performance.cpu_percent}%
          </div>
        </div>

        <div>
          <div className="text-gray-600">Memory</div>
          <div className={`text-lg font-mono ${performance.memory_percent > 80 ? 'text-red-600' : 'text-gray-900'}`}>
            {performance.memory_percent}%
          </div>
        </div>

        {performance.temperature_c && (
          <div>
            <div className="text-gray-600">Temperature</div>
            <div className={`text-lg font-mono ${performance.temperature_c > 70 ? 'text-red-600' : 'text-gray-900'}`}>
              {performance.temperature_c}°C
            </div>
          </div>
        )}

        <div>
          <div className="text-gray-600">Load Avg (1m)</div>
          <div className="text-lg font-mono text-gray-900">
            {performance.load_average ? performance.load_average[0] : 'N/A'}
          </div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500">
        Memory: {performance.memory_used_mb}MB / {performance.memory_total_mb}MB ·
        Disk: {performance.disk_percent}%
      </div>
    </div>
  )
}

// In main JSX, add after Map Configuration Section:
{renderPerformanceStats()}
```

---

## Implementation Phases

### Phase 1: Preview Features (✅ COMPLETE)

**Backend**:
- ✅ Add `api_cv_minimap_preview()` handler in handlers.py (lines 565-666)
- ✅ Register route in server.py (line 107)
- ⏳ Test endpoint with curl/browser (ready for testing)

**Frontend**:
- ✅ Add `getMiniMapPreviewURL()` to api.js (lines 217-220)
- ✅ Add preview state and debounce logic to CVConfiguration.jsx (lines 37-39, 188-235)
- ✅ Update create form with real-time preview display (lines 461-485)
- ✅ Add thumbnail state for active config (line 38)
- ✅ Update config list rendering with thumbnail (lines 411-428)
- ✅ Add auto-refresh every 2s for thumbnail (lines 213-235)
- ⏳ Test on Raspberry Pi (ready for testing)

**Documentation**:
- ✅ Update this document with implementation details
- ✅ Update 06_MAP_CONFIGURATION.md user guide

## Implementation Summary

### What Was Implemented

#### Backend (handlers.py)
- **New endpoint**: `GET /api/cv/mini-map-preview?x={x}&y={y}&w={w}&h={h}`
- Reads latest frame from shared memory (`/dev/shm/msmacro_cv_frame.jpg`)
- Decodes JPEG using cv2
- Crops to specified region using numpy slicing
- Draws red 2px border on cropped region
- Re-encodes as JPEG (quality 85)
- Returns cropped image (~10-20KB vs ~100-200KB full frame)
- Validates coordinates (bounds checking, positive dimensions)
- Error handling: 400 (invalid), 404 (no frame), 500 (processing error), 503 (not available)

#### Frontend (CVConfiguration.jsx)
1. **Real-Time Preview During Creation**:
   - Debounced 500ms (updates 0.5s after user stops adjusting)
   - Preview shows cropped mini-map only with red border
   - Coordinates displayed below preview
   - Loading state while preview loads

2. **Thumbnail in List View**:
   - Appears inside active config card
   - Auto-refreshes every 2 seconds
   - Max height: 100px, object-fit: contain
   - Caption: "Live preview (updates every 2s)"
   - Only shown for active configuration

### Files Modified

**Backend**:
- `msmacro/web/handlers.py` - Added 102 lines (api_cv_minimap_preview function + imports)
- `msmacro/web/server.py` - Added 1 import + 1 route

**Frontend**:
- `webui/src/api.js` - Added getMiniMapPreviewURL function (4 lines)
- `webui/src/components/CVConfiguration.jsx` - Added 80+ lines:
  - Preview state variables (3 lines)
  - Two useEffect hooks for preview updates (48 lines)
  - Preview display in create form (24 lines)
  - Thumbnail display in list view (18 lines)

**Documentation**:
- `docus/REALTIME_PREVIEW_IMPLEMENTATION.md` - This document (implementation plan + summary)
- `docus/06_MAP_CONFIGURATION.md` - Updated Quick Start section with preview descriptions

### Phase 2: Performance Stats (📅 DEFERRED)

**Backend**:
- [ ] Add `api_system_performance()` handler
- [ ] Test endpoint

**Frontend**:
- [ ] Add `getSystemPerformance()` to api.js
- [ ] Create PerformanceStats component
- [ ] Integrate in Header.jsx (always visible)
- [ ] Add auto-refresh every 5s
- [ ] Color-code warnings (CPU/memory >80%)
- [ ] Test on Raspberry Pi

**Documentation**:
- [ ] Update FRONTEND_IMPLEMENTATION.md with performance component pattern
- [ ] Update 05_API_REFERENCE.md with new endpoint

---

## Performance Considerations

### API Load
- **Mini-map preview**: Debounced 500ms = Max 2 requests/second
- **Thumbnail refresh**: Every 2s = 0.5 requests/second
- **Performance stats**: Every 5s = 0.2 requests/second
- **Total**: ~3 requests/second max (acceptable for Pi)

### Image Size Optimization
- **Full frame**: 1280x720 JPEG = ~100-200KB
- **Mini-map crop**: 340x86 JPEG = ~10-20KB (10x smaller!)
- **Thumbnail scale**: 50% = ~2-5KB
- **Bandwidth saved**: 90% reduction

### CPU Impact
- **Preview crop**: <5ms (numpy array slicing)
- **JPEG encode**: ~10ms (small region)
- **Performance stats**: <1ms (psutil)
- **Total overhead**: <20ms per request (negligible)

---

## Testing Checklist

### Backend Testing
- [ ] `/api/cv/mini-map-preview` returns cropped JPEG
- [ ] Query params (x, y, w, h) work correctly
- [ ] Bounds validation rejects invalid coords
- [ ] Returns 503 when no frame available
- [ ] `/api/system/performance` returns all metrics
- [ ] Temperature reading works on Pi
- [ ] Performance overhead is acceptable

### Frontend Testing
- [ ] Preview appears during config creation
- [ ] Adjusting X/Y updates preview in real-time
- [ ] Debounce prevents API spam
- [ ] Thumbnail appears in active config item
- [ ] Thumbnail auto-refreshes every 2s
- [ ] Performance stats display correctly
- [ ] Performance stats auto-refresh every 5s
- [ ] CPU/memory/temp color coding works

### Integration Testing
- [ ] Create config with live preview feedback
- [ ] Activate config → thumbnail appears
- [ ] Deactivate config → thumbnail disappears
- [ ] Performance stats show improvement
- [ ] Multiple configs switch correctly
- [ ] Works on both dev machine and Pi

---

## Rollback Plan

If implementation causes issues:

1. **Backend**: Comment out new route registrations
2. **Frontend**: Hide preview/thumbnail components with feature flag
3. **Graceful Degradation**: Frontend checks if endpoints exist before calling

---

## Future Enhancements

1. **Zoom Preview**: Allow users to zoom into preview for fine-tuning
2. **Drag-to-Position**: Visual drag-and-drop instead of numeric inputs
3. **Performance History**: Chart showing CPU/memory over time
4. **Comparison Mode**: Side-by-side before/after activation
5. **Auto-Positioning**: AI-powered mini-map detection
6. **Multi-Region**: Support detecting multiple regions simultaneously

---

## Success Criteria

- ✅ Users can see preview while configuring coordinates
- ✅ Preview updates within 500ms of coordinate change
- ✅ Cropped preview is clear and accurate
- ✅ Thumbnail confirms active config visually
- ✅ Performance stats prove 3-5x improvement
- ✅ Pi remains responsive during preview updates
- ✅ Documentation is complete and accurate

---

**Status**: 📋 Ready for Implementation
**Est. Time**: 4-6 hours
**Priority**: High (blocking user testing)
