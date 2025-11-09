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
     - Optional border (use preview endpoint with overlay=border); default is raw for accurate calibration
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
   - Border optional (add overlay=border when requesting preview); raw image recommended for calibration
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

## Departure Points (Waypoints)

### Overview

Departure Points allow you to mark specific positions on the minimap as waypoints. When the player's detected position approaches a saved departure point, the system can trigger a "hit_departure" event. This feature is useful for:

- **Position-based navigation**: Verify when player reaches specific map locations
- **Route planning**: Mark sequential waypoints for automated farming routes
- **Debugging**: Monitor player movement and verify detection accuracy
- **Trigger points**: Set up location-based actions for future automation

### How It Works

1. **Enable Object Detection**: Ensure object detection is running (CV tab → Object Detection section)
2. **Create/Activate Map Config**: Create and activate a map configuration for your minimap
3. **Navigate to Departure Points Section**: Scroll down to "Departure Points" in the CV tab
4. **Position Your Player**: Move your character to the desired waypoint location
5. **Capture Position**: Click "Capture Current Position" button
6. **Configure Tolerance**: Adjust how precisely the player must match the waypoint

### Tolerance Modes

Departure points support 7 different tolerance modes to handle various navigation scenarios:

#### 1. **Both X & Y ±** (default)
- Player must be within tolerance in **both** X and Y directions
- Best for: Precise position matching, static waypoints
- Example: Player at (100, 100) with 5px tolerance hits when at (98-102, 98-102)

#### 2. **Y-axis ±**
- Only checks Y coordinate (horizontal line)
- X coordinate can be anywhere
- Best for: Detecting when player crosses a horizontal threshold
- Example: Detect when player reaches a specific floor/platform

#### 3. **X-axis ±**
- Only checks X coordinate (vertical line)
- Y coordinate can be anywhere
- Best for: Detecting when player crosses a vertical threshold
- Example: Detect when player reaches left/right side of map

#### 4. **Y >** (Y Greater)
- Triggers when current Y is **greater than** saved Y value
- Best for: Detecting movement downward (in screen coordinates)
- Example: Detect when player moves below a certain point

#### 5. **Y <** (Y Less)
- Triggers when current Y is **less than** saved Y value
- Best for: Detecting movement upward (in screen coordinates)
- Example: Detect when player moves above a certain point

#### 6. **X >** (X Greater)
- Triggers when current X is **greater than** saved X value
- Best for: Detecting movement to the right
- Example: Detect when player passes a certain X coordinate

#### 7. **X <** (X Less)
- Triggers when current X is **less than** saved X value
- Best for: Detecting movement to the left
- Example: Detect when player passes a certain X coordinate

### Managing Departure Points

#### Adding Points

1. Ensure player is detected (green indicator shows "Player Detected")
2. Move character to desired position in game
3. Click **"Capture Current Position"** button
4. Point is added with auto-generated name ("Point 1", "Point 2", etc.)

#### Editing Points

Click **"Edit"** on any departure point to modify:
- **Name**: Descriptive label for the waypoint
- **Tolerance Mode**: Choose from 7 tolerance modes (see above)
- **Tolerance (px)**: Pixel tolerance value (1-50px, default: 5px)

Click **"Save"** to apply changes or **"Cancel"** to discard.

#### Removing Points

Click **"Remove"** button (trash icon) on any departure point to delete it. Points are automatically reordered after removal.

### Hit Departure Indicator

When a player approaches a departure point within its tolerance:
- The point card **highlights in green** with a **green border**
- An animated **"HIT!"** badge appears in green
- The order number badge turns **green**
- The entire card background becomes **green**

This provides real-time visual feedback for debugging navigation and verifying detection accuracy.

### Use Cases

#### 1. Farming Route Verification
```
Create multiple departure points along your farming route:
1. Point 1: Starting position (100, 50) - both ±5px
2. Point 2: Monster spawn area (200, 100) - both ±10px
3. Point 3: Return point (100, 50) - both ±5px

Monitor hit_departure status to verify your character follows the intended route.
```

#### 2. Platform Detection
```
Detect when player jumps to a higher platform:
1. Point 1: Lower platform (150, 200) - Y < mode
2. Point 2: Upper platform (150, 100) - Y > mode

Use Y-axis thresholds to trigger when player changes vertical position.
```

#### 3. Map Edge Detection
```
Detect when player reaches map boundaries:
1. Left Edge: (10, 100) - X < mode
2. Right Edge: (300, 100) - X > mode

Useful for preventing player from going out of bounds during automation.
```

### Sequential vs Independent Points

**Current Implementation**: Departure points work **independently**
- Each point continuously checks if player is nearby
- Multiple points can trigger simultaneously
- Order field indicates sequence but doesn't enforce it

**Future Enhancement**: Sequential mode (coming soon)
- Points will only check after previous point is hit
- Enforces ordered navigation through waypoints
- Useful for multi-step farming routes

### Performance Considerations

- **Polling Rate**: Status updates every 500ms
- **CPU Impact**: Minimal (<1% per point)
- **Recommended Limit**: Up to 20 departure points per map config
- **Detection Requirements**: Object detection must be running

### Data Persistence

Departure points are saved in the map configuration file:
```json
{
  "configs": [
    {
      "name": "My Map",
      "departure_points": [
        {
          "id": "uuid-123",
          "name": "Point 1",
          "x": 100,
          "y": 50,
          "order": 0,
          "tolerance_mode": "both",
          "tolerance_value": 5,
          "created_at": 1699564800.0
        }
      ]
    }
  ]
}
```

**Note**: `hit_departure` is calculated in real-time and not stored in the file.

### API Endpoints

```
POST   /api/cv/map-configs/{name}/departure-points           # Add point
DELETE /api/cv/map-configs/{name}/departure-points/{id}      # Remove point
PUT    /api/cv/map-configs/{name}/departure-points/{id}      # Update point
POST   /api/cv/map-configs/{name}/departure-points/reorder   # Reorder points
GET    /api/cv/departure-points/status                       # Get status
```

### Troubleshooting

**"No Player Detected" Message**
- Ensure object detection is running (enable in Object Detection section)
- Verify player (yellow dot) is visible on minimap
- Check that calibration is accurate (see OBJECT_DETECTION.md)

**Capture Button Disabled**
- Player detection must be active (green indicator)
- Check that active map config exists
- Verify minimap region is configured correctly

**Hit Departure Not Triggering**
- Check tolerance mode is appropriate for your use case
- Increase tolerance value if player position is unstable
- Verify coordinates are correct (check minimap preview)
- Ensure object detection is continuously running

**Points Not Saving**
- Check browser console for API errors
- Verify map config is properly activated
- Restart web server if persistence fails

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
