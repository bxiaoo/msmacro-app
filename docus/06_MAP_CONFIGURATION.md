# Map Configuration Guide

## Overview

Map Configuration allows you to define and save specific detection regions for **mini-map** CV processing instead of analyzing the entire screen. This **dramatically improves performance** on Raspberry Pi by reducing the amount of data that needs to be processed each frame.

**Important**: These configurations are designed for **mini-map navigation only**, not for quest trackers or other UI elements.

**Key Benefits:**
- **Detection disabled by default** - Saves resources until you create a config
- **3-5x faster detection** - Process only the configured region
- **Lower CPU usage** - Reduced computational load on Raspberry Pi
- **Lower memory usage** - Smaller regions require less processing memory
- **Multiple saved configs** - Switch between different mini-map positions
- **Manual adjustment** - Fine-tune detection area with ±10px increments

## Quick Start

### 1. Access CV Configuration Tab

Navigate to the **CV** tab in the web UI to access map configuration.

**Empty State (No Saved Configs):**
- You'll see a message: "No saved mini-map configurations"
- Subtitle: "CV detection is disabled. Create a config to enable mini-map detection."
- Click the **Create Configuration** button to create your first configuration

**With Saved Configs:**
- All saved configurations appear as a list
- Each shows: name, active status, settings, delete button
- Click the **+** button to create a new configuration

### 2. Create a New Configuration

When you click the **Create Configuration** or **New** button:

1. **Create Form Appears**
   - Shows coordinate adjustment controls
   - Default starting position: (68, 56)
   - Default size: 340×86 pixels (optimized for mini-maps)
   - **Real-time preview** appears below controls

2. **Adjust Detection Area with Live Feedback**
   - **Height Control**: Adjust vertical size (detection region height)
     - Click **-** button to decrease by 10 pixels
     - Click **+** button to increase by 10 pixels
     - Or type exact height value in the center input
   - **Width Control**: Adjust horizontal size (detection region width)
     - Click **-** button to decrease by 10 pixels
     - Click **+** button to increase by 10 pixels
     - Or type exact width value in the center input
   - **Fixed Position**: Top-left corner stays at (68, 56)
   - **Preview Updates**: After you stop adjusting (0.5s delay)
     - Shows **cropped mini-map region only** (not entire screen)
     - Region grows/shrinks from the fixed top-left anchor point
     - Red border indicates detection boundary
     - Coordinates displayed below preview
     - Allows you to verify size before saving

3. **Save Configuration**
   - Click **Save Configuration** (blue button)
   - Enter a descriptive name in the dialog (e.g., "Henesys Mini-Map")
   - Click **Save** to confirm
   - Configuration is now saved and appears in the list

### 3. Activate a Configuration

To enable mini-map detection:

1. Find the config in the list
2. Check the checkbox next to its name
3. **Live thumbnail appears** inside the config card
   - Shows cropped mini-map region (not entire screen)
   - Updates every 2 seconds automatically
   - Red border shows detection boundary
   - Caption: "Live preview (updates every 2s)"
4. **Camera preview section appears** at the bottom (if scrolled down)
   - Shows full detection view
   - Updates every 2 seconds with active config name

**Performance Impact:**
- Detection now processes only your configured region
- CPU usage drops significantly (from ~50% to ~10-15%)
- Frame rate may improve on Raspberry Pi
- Thumbnail and preview show mini-map area only

### 4. Deactivate Configuration

To disable mini-map detection:

1. Uncheck the active configuration
2. **CV detection stops** - camera preview is hidden
3. CPU usage drops to minimal (no processing)
4. System waits for you to activate a config before detecting again

**Note**: Detection is completely disabled when no config is active. This prevents Raspberry Pi from being overloaded with continuous full-screen processing.

## Configuration Management

### Saved Configurations

Each configuration includes:
- **Name**: User-defined identifier
- **Position**: Top-left (X, Y) coordinates
- **Size**: Width and height in pixels
- **Created**: Timestamp when saved
- **Last Used**: When it was last activated

### Editing Configurations

**Current Version**: Editing existing configurations is not yet supported in the UI.

**Workaround**: To change a configuration's coordinates:
1. Delete the old configuration (must deactivate it first)
2. Create a new configuration with the desired coordinates
3. Activate the new configuration

**Future Enhancement**: In-place editing will be added in a future update.

### Deleting Configurations

To delete a configuration:

1. **Important**: Deactivate the config first if it's active (uncheck the checkbox)
2. Click the **delete icon** (trash can) next to the config
3. Confirm deletion in the browser dialog
4. **Safety**: The delete button is disabled for the active configuration

## Coordinate System

### Understanding Coordinates

```
Screen (1280x720)
┌─────────────────────────────────────┐
│ (0,0)                               │
│   ↓                                 │
│   → (tl_x, tl_y) ┌────────┐        │
│                   │ Region │        │
│                   │  Area  │        │
│                   └────────┘        │
│              (br_x, br_y)           │
│                                     │
└─────────────────────────────────────┘
```

**Four Corner Points:**
- **Top-Left (TL)**: (tl_x, tl_y) - Fixed anchor point at (68, 56)
- **Top-Right (TR)**: (tl_x + width, tl_y)
- **Bottom-Left (BL)**: (tl_x, tl_y + height)
- **Bottom-Right (BR)**: (tl_x + width, tl_y + height)

### Adjustment Increments

- **Height**: Vertical size adjustment, 10-pixel increments
- **Width**: Horizontal size adjustment, 10-pixel increments

**Example:**
- Start: Top-left (68, 56), Size 340×86
- Click Height+ 3 times: Size becomes 340×116 (height +30px)
- Click Width+ 2 times: Size becomes 360×116 (width +20px)
- Top-left corner remains at (68, 56) throughout

## Performance Guidelines

### Optimal Region Size

**Recommended Sizes:**
- **Small Region** (200x100): Fastest, use for small UI elements
- **Medium Region** (400x200): Balanced, good for most UI frames
- **Large Region** (800x400): Slower, use only if necessary

**Performance Impact by Size:**

| Region Size | CPU Usage | Detection Speed |
|-------------|-----------|-----------------|
| 200x100     | ~5%       | <5ms            |
| 400x200     | ~10%      | <10ms           |
| 800x400     | ~20%      | <20ms           |
| Full Screen | ~50%+     | >50ms           |

### Best Practices

1. **Use smallest region possible** that captures your UI element
2. **Position precisely** to minimize excess area
3. **Test multiple sizes** to find optimal balance
4. **Save multiple configs** for different maps/locations
5. **Monitor CPU usage** in system stats

## Example Configurations

### MapleStory Party Quest Tracker

```
Name: "Henesys PQ Tracker"
Position: (68, 56)
Size: 340x86
Use Case: Tracks party quest progress UI
```

### MapleStory Minimap

```
Name: "Minimap Region"
Position: (30, 30)
Size: 250x250
Use Case: Monitors minimap for navigation
```

**Note**: The examples above are optimized for mini-map navigation. Quest Log and other UI elements are not supported in the current version.

## Troubleshooting

### No Camera Preview Visible

**Symptoms**: Camera preview not showing after activating config

**Solutions:**
1. Verify an HDMI capture device is connected
2. Check that CV capture service is running
3. Ensure a configuration is activated (checkbox checked)
4. Wait 2-3 seconds for the preview to appear
5. Check browser console for errors

### Detection Rectangle Not Visible

**Symptoms**: Camera preview shows but no red rectangle appears

**Solutions:**
1. Verify the mini-map is visible in the game
2. Check that coordinates are within screen bounds (1280x720)
3. Adjust coordinates to match actual mini-map position
4. Brightness may be too low - increase game brightness

### Low Confidence (<30%)

**Symptoms**: Detection works but shows low confidence percentage

**Solutions:**
1. Mini-map may be obscured or partially hidden
2. Background color may be too similar to mini-map border
3. Adjust coordinates to fully contain the mini-map area
4. Ensure mini-map is visible and not minimized

### Can't Delete Configuration

**Symptoms**: Delete button is disabled or grayed out

**Solution**: Deactivate the configuration first (uncheck the checkbox), then the delete button will become enabled

### Performance Still Poor

**Symptoms**: CPU usage still high even with config active

**Solutions:**
1. Verify only one configuration is active (only one checkbox should be checked)
2. Try using a smaller detection region if possible
3. Check that daemon is properly reloading config (check logs)
4. Restart the msmacro daemon: `python -m msmacro ctl stop` then start again

## API Reference

For programmatic access to map configurations, see `docus/CV_CONFIGURATION_SYSTEM.md`.

### REST API Endpoints

```
GET    /api/cv/map-configs           # List all configs
POST   /api/cv/map-configs           # Create new config
DELETE /api/cv/map-configs/{name}    # Delete config
POST   /api/cv/map-configs/{name}/activate  # Activate config
GET    /api/cv/map-configs/active    # Get active config
POST   /api/cv/map-configs/deactivate  # Deactivate current
```

## Advanced Topics

### Configuration File Location

Configurations are stored at:
```
~/.local/share/msmacro/map_configs.json
```

### Manual Editing

You can manually edit the JSON file (advanced users only):

```json
{
  "configs": [
    {
      "name": "My Map",
      "tl_x": 68,
      "tl_y": 56,
      "width": 340,
      "height": 86,
      "created_at": 1699564800.0,
      "last_used_at": 1699565000.0,
      "is_active": true
    }
  ],
  "active_config": "My Map"
}
```

### Backup Configurations

To backup your configurations:
```bash
cp ~/.local/share/msmacro/map_configs.json ~/map_configs_backup.json
```

To restore:
```bash
cp ~/map_configs_backup.json ~/.local/share/msmacro/map_configs.json
python -m msmacro ctl cv-reload-config
```

## Related Documentation

- `01_ARCHITECTURE.md` - System architecture with map config flow
- `04_DETECTION_ALGORITHM.md` - Detection algorithm details
- `CV_CONFIGURATION_SYSTEM.md` - Technical implementation details
- `02_USAGE.md` - General usage guide

---

**Questions or Issues?**
See `07_TROUBLESHOOTING.md` or open an issue on GitHub.
