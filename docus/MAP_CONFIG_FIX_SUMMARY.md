# Map Configuration Logic Fix - Summary

## Issue Description

The map configuration UI had incorrect behavior where x/y axis inputs were adjusting the detection region's position (top-left point) instead of its size (width/height). This was not the intended behavior.

## What Was Wrong

**Incorrect Behavior:**
- User adjusts "Y Axis" → Detection region moves up/down (changes tl_y)
- User adjusts "X Axis" → Detection region moves left/right (changes tl_x)
- Width/Height → Fixed at 340×86, not adjustable
- **Result**: Detection region moves around the screen with fixed dimensions

## What Was Fixed

**Correct Behavior:**
- Top-Left position → Fixed at (68, 56) as the anchor point
- User adjusts "Height" → Detection region height changes (taller/shorter)
- User adjusts "Width" → Detection region width changes (wider/narrower)
- **Result**: Detection region grows/shrinks from the same origin point

## Changes Made

### 1. Frontend Changes (`webui/src/components/CVConfiguration.jsx`)

#### State Object Keys
```javascript
// Before
const [coords, setCoords] = useState({ x: 68, y: 56, width: 340, height: 86 })

// After
const [coords, setCoords] = useState({ tl_x: 68, tl_y: 56, width: 340, height: 86 })
```

#### UI Labels
```javascript
// Before
<label>Y Axis (Vertical)</label>
<label>X Axis (Horizontal)</label>

// After
<label>Height (Vertical Size)</label>
<label>Width (Horizontal Size)</label>
```

#### Control Bindings
```javascript
// Before - adjusting position
adjustCoord('y', -10)  // moves region up
adjustCoord('x', 10)   // moves region right

// After - adjusting size
adjustCoord('height', -10)  // makes region shorter
adjustCoord('width', 10)    // makes region wider
```

#### Input Fields
```javascript
// Before
value={coords.y}
onChange={(e) => setCoords({ ...coords, y: parseInt(e.target.value) || 0 })}

// After
value={coords.height}
onChange={(e) => setCoords({ ...coords, height: Math.max(1, parseInt(e.target.value) || 1) })}
```

#### Minimum Value Validation
```javascript
// Before - allowed 0
Math.max(0, prev[axis] + delta)

// After - minimum 1 pixel
Math.max(1, prev[axis] + delta)
```

### 2. Documentation Updates

#### `docus/06_MAP_CONFIGURATION.md`
- Updated "Adjust Detection Area" section to reflect size adjustment instead of position adjustment
- Changed "Y/X Axis" terminology to "Height/Width"
- Added note about fixed top-left anchor point at (68, 56)
- Updated examples to show size changes instead of position changes

#### `docus/MAP_CONFIG_TESTING_GUIDE.md` (New)
- Comprehensive manual testing guide for Raspberry Pi deployment
- Step-by-step test cases
- Verification checklist
- Troubleshooting section
- Expected results documentation

## Technical Details

### Backend Compatibility
No backend changes required. The backend API already expects:
```json
{
  "name": "Config Name",
  "tl_x": int,    // Top-left X
  "tl_y": int,    // Top-left Y
  "width": int,   // Region width
  "height": int   // Region height
}
```

The frontend now correctly sends `tl_x` and `tl_y` instead of `x` and `y`.

### Data Flow
1. User adjusts Width/Height controls
2. Frontend state updates: `{ tl_x: 68, tl_y: 56, width: <new>, height: <new> }`
3. Preview API called with updated dimensions
4. On save, POST request with correct structure
5. Backend stores configuration
6. Detection uses fixed top-left (68, 56) with adjustable dimensions

## Testing Requirements

### Automated Testing
Not applicable - requires visual verification on actual hardware with HDMI capture device.

### Manual Testing (Required)
See `docus/MAP_CONFIG_TESTING_GUIDE.md` for complete testing instructions.

**Key Test Points:**
1. Create configuration - verify width/height controls adjust size
2. Verify top-left stays at (68, 56) during adjustments
3. Save and activate - verify detection uses correct region
4. Test edge cases - minimum values, large values
5. Verify preview updates correctly

### Test on Raspberry Pi
This feature is designed for Raspberry Pi deployment with HDMI capture. Testing requires:
- Raspberry Pi hardware
- HDMI capture device
- Video source (game console/PC)
- Web browser to access UI

## Deployment Steps

1. **Pull latest code**
   ```bash
   cd ~/msmacro-app
   git pull origin main
   ```

2. **Rebuild frontend**
   ```bash
   cd webui
   npm run build
   ```

3. **Restart daemon** (if running)
   ```bash
   python3 -m msmacro ctl stop
   python3 -m msmacro daemon &
   ```

4. **Clear browser cache**
   - Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)

5. **Run manual tests**
   - Follow `MAP_CONFIG_TESTING_GUIDE.md`

## Files Changed

```
docus/06_MAP_CONFIGURATION.md             (documentation update)
docus/MAP_CONFIG_TESTING_GUIDE.md         (new - testing guide)
docus/MAP_CONFIG_FIX_SUMMARY.md           (new - this file)
webui/src/components/CVConfiguration.jsx  (frontend fix)
msmacro/web/static/                       (built assets - auto-generated)
```

## Verification Checklist

After deployment, verify:

- [ ] UI shows "Height" and "Width" labels, not "Y Axis" and "X Axis"
- [ ] Adjusting height changes vertical size only
- [ ] Adjusting width changes horizontal size only  
- [ ] Preview shows region growing/shrinking from (68, 56)
- [ ] Preview caption shows "Position: (68, 56)"
- [ ] Saved config has tl_x=68, tl_y=56 in backend storage
- [ ] Detection uses correct region when config is active

## Related Documentation

- `docus/06_MAP_CONFIGURATION.md` - User guide for map configuration
- `docus/MAP_CONFIG_TESTING_GUIDE.md` - Manual testing procedures
- `docus/CV_CONFIGURATION_SYSTEM.md` - Technical implementation details
- `AGENTS.md` - Repository guidelines

## Questions or Issues

If the fix doesn't work as expected:

1. Check browser console for JavaScript errors
2. Verify frontend build was deployed (check file timestamps)
3. Clear browser cache completely
4. Check backend logs: `journalctl -u msmacro-daemon -f`
5. Review `MAP_CONFIG_TESTING_GUIDE.md` troubleshooting section

---

**Fix Version**: 1.0  
**Date**: 2025-01-07  
**Impact**: Low risk - improves usability, no breaking changes to API
