# Map Configuration Testing Guide

## Overview

This guide provides manual testing instructions for the map configuration feature fix. The fix changes the behavior of the x/y axis controls from adjusting the detection region position to adjusting the region size.

**Issue Fixed**: Detection region configuration now correctly adjusts width/height while keeping the top-left point fixed, instead of moving the region around with fixed dimensions.

## What Changed

### Before (Incorrect Behavior)
- **X/Y Axis inputs** → Adjusted Top-Left position (moved region around)
- **Width/Height** → Fixed at 340×86 (not adjustable)
- **Result**: Detection region moved around the screen with fixed size

### After (Correct Behavior)
- **Top-Left position** → Fixed at (68, 56) - stays in place
- **Width input** → Adjusts horizontal size (detection region width)
- **Height input** → Adjusts vertical size (detection region height)
- **Result**: Detection region grows/shrinks from the same top-left origin point

## Test Environment Setup

### Prerequisites

1. **Raspberry Pi with msmacro installed**
   ```bash
   # Verify installation
   python3 -m msmacro --version
   ```

2. **HDMI capture device connected**
   - USB HDMI capture card plugged in
   - Video source (game console, PC) connected

3. **Network access to Pi**
   - Web UI accessible at `http://<pi-ip>:8787`

4. **Fresh build deployed**
   ```bash
   cd ~/msmacro-app
   git pull
   cd webui
   npm run build
   ```

## Manual Test Cases

### Test 1: Create Configuration with Size Adjustment

**Objective**: Verify that width/height controls adjust the detection region size, not position.

**Steps**:

1. **Access CV Configuration Page**
   - Open browser: `http://<pi-ip>:8787`
   - Navigate to **CV** tab

2. **Create New Configuration**
   - Click **Create Configuration** button
   - Observe the form with:
     - "Height (Vertical Size)" label with -/+10 buttons
     - "Width (Horizontal Size)" label with -/+10 buttons
     - Real-time preview showing cropped region

3. **Test Height Adjustment**
   - **Initial state**: Preview shows region at (68, 56) with size 340×86
   - Click **Height +** button 3 times
   - **Expected**: 
     - Height increases to 116 (86 + 30)
     - Top-left corner stays at (68, 56)
     - Bottom edge moves down
     - Preview caption shows: "Position: (68, 56) · Size: 340×116"
   - **NOT expected**: Region moving vertically

4. **Test Width Adjustment**
   - Click **Width +** button 2 times
   - **Expected**:
     - Width increases to 360 (340 + 20)
     - Top-left corner stays at (68, 56)
     - Right edge extends further
     - Preview caption shows: "Position: (68, 56) · Size: 360×116"
   - **NOT expected**: Region moving horizontally

5. **Test Decrease**
   - Click **Height -** button 2 times
   - Click **Width -** button 1 time
   - **Expected**:
     - Size changes to 350×96
     - Top-left still at (68, 56)
     - Preview updates accordingly

6. **Test Manual Input**
   - Type `400` in Width input field
   - Type `120` in Height input field
   - **Expected**:
     - Preview updates after 0.5s delay (debounced)
     - Shows size 400×120
     - Top-left remains (68, 56)

7. **Save Configuration**
   - Click **Save Configuration**
   - Enter name: "Test Size Adjustment"
   - Click **Save**
   - **Expected**: Config saved with correct dimensions

8. **Verify in List**
   - Config appears in saved list
   - Shows: "Position: (68, 56) · Size: 400×120"

**Pass Criteria**:
- ✅ Top-left position stays at (68, 56) throughout all adjustments
- ✅ Width/Height inputs control the size, not position
- ✅ Preview updates correctly show region growing/shrinking from same origin
- ✅ Saved config has correct dimensions

---

### Test 2: Activate Configuration and Verify Detection

**Objective**: Verify that the configured region is correctly used for detection.

**Steps**:

1. **Activate Configuration**
   - Check the checkbox next to saved config
   - **Expected**:
     - Live thumbnail appears inside config card
     - Updates every 2 seconds
     - Shows cropped mini-map region

2. **Verify Live Preview**
   - Scroll down to "Live Preview" section
   - **Expected**:
     - Full camera preview visible
     - Caption shows: "Active: Test Size Adjustment"
     - Updates every 2 seconds

3. **Check Detection Region**
   - Observe the preview with game running
   - **Expected**:
     - Detection focuses on configured region (68, 56, 400×120)
     - Not analyzing entire screen
     - CPU usage lower than full-screen detection

4. **Test Different Sizes**
   - Create another config with different size:
     - Width: 250, Height: 100
   - Activate new config
   - **Expected**:
     - Detection switches to new region size
     - Top-left still at (68, 56)
     - Smaller region visible in preview

**Pass Criteria**:
- ✅ Detection region matches configured size
- ✅ Top-left anchor point correct at (68, 56)
- ✅ Live preview updates correctly
- ✅ CPU usage reflects smaller detection region

---

### Test 3: Edge Cases and Validation

**Objective**: Verify input validation and edge cases.

**Steps**:

1. **Test Minimum Values**
   - Try to set Width to 0
   - **Expected**: Value clamped to 1 (minimum)
   - Try to set Height to -10
   - **Expected**: Value clamped to 1

2. **Test Large Values**
   - Set Width to 1200 (close to screen width)
   - Set Height to 700 (close to screen height)
   - **Expected**:
     - Preview shows large region
     - Still anchored at (68, 56)
     - May exceed screen bounds (acceptable for now)

3. **Test Rapid Changes**
   - Click +/- buttons rapidly
   - **Expected**:
     - Preview updates debounced (0.5s delay)
     - Final value reflected correctly
     - No crashes or freezes

4. **Test Configuration Management**
   - Create multiple configs with different sizes
   - Delete one config (must deactivate first)
   - **Expected**: All operations work correctly

**Pass Criteria**:
- ✅ Minimum value enforcement works (≥1)
- ✅ Large values handled gracefully
- ✅ Rapid input changes handled smoothly
- ✅ CRUD operations work correctly

---

## Verification Checklist

Use this checklist to confirm the fix is working correctly:

### UI Labels and Layout
- [ ] Form shows "Height (Vertical Size)" not "Y Axis"
- [ ] Form shows "Width (Horizontal Size)" not "X Axis"
- [ ] Preview caption displays correct position and size
- [ ] +/- buttons adjust size values, not position

### Behavior
- [ ] Top-left corner always stays at (68, 56)
- [ ] Width adjustment changes horizontal size only
- [ ] Height adjustment changes vertical size only
- [ ] Preview region grows/shrinks from same origin
- [ ] Saved config has correct tl_x=68, tl_y=56

### API Integration
- [ ] POST /api/cv/map-configs receives correct payload:
  ```json
  {
    "name": "Config Name",
    "tl_x": 68,
    "tl_y": 56,
    "width": <adjustable>,
    "height": <adjustable>
  }
  ```
- [ ] Activation uses correct coordinates for detection
- [ ] Detection processes only configured region

### Performance
- [ ] Smaller regions → lower CPU usage
- [ ] Larger regions → higher CPU usage (but less than full screen)
- [ ] Preview updates smoothly every 2 seconds

---

## Troubleshooting

### Issue: Preview not updating
**Solution**: 
- Check HDMI capture device is connected
- Verify CV capture service is running: `ps aux | grep msmacro`
- Check browser console for errors

### Issue: Changes not reflected
**Solution**:
- Clear browser cache (Ctrl+Shift+R)
- Verify frontend build was deployed: `ls -la ~/msmacro-app/msmacro/web/static/`
- Restart web server: `python3 -m msmacro ctl stop && python3 -m msmacro daemon`

### Issue: Position still moving instead of size changing
**Solution**:
- Verify latest code is deployed: `git log -1 --oneline`
- Rebuild frontend: `cd webui && npm run build`
- Hard refresh browser

---

## Expected Results Summary

After testing, you should observe:

1. **Fixed Position**: Top-left corner always at (68, 56)
2. **Adjustable Size**: Width and height controlled by inputs
3. **Correct Labeling**: UI clearly shows "Width" and "Height" not "X/Y Axis"
4. **Working Preview**: Real-time updates show region changes
5. **Proper Detection**: Active config applies correct region for CV processing

---

## Reporting Issues

If tests fail, collect this information:

1. **Browser Console Logs**
   - Open DevTools (F12)
   - Check Console tab for errors
   - Screenshot any errors

2. **Network Requests**
   - Check Network tab
   - Look for `/api/cv/map-configs` POST request
   - Verify request payload

3. **Backend Logs**
   ```bash
   journalctl -u msmacro-daemon -f
   ```

4. **Screenshots**
   - Configuration form with coordinates
   - Preview showing detection region
   - Saved config in list

5. **Environment Info**
   ```bash
   python3 -m msmacro --version
   uname -a
   cat ~/.local/share/msmacro/map_configs.json | jq
   ```

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-07  
**Related Files**: 
- `webui/src/components/CVConfiguration.jsx` (frontend implementation)
- `msmacro/cv/map_config.py` (backend data model)
- `docus/06_MAP_CONFIGURATION.md` (user guide)
