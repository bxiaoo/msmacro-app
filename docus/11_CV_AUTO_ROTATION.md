# CV-AUTO Rotation System

**Version**: 2.0
**Status**: Production (Enhanced with CV Item System)
**Last Updated**: December 2025

> **🔗 Related Documentation**: For the complete **CV Item System** (including class-based pathfinding), see [12_CV_ITEM_SYSTEM.md](./12_CV_ITEM_SYSTEM.md)

## Overview

The CV-AUTO Rotation System is a comprehensive computer vision-based automation feature that enables automatic rotation playback triggered by player position detection. The system monitors player location on the minimap, automatically plays configured rotations when departure points are reached, and navigates between waypoints using intelligent pathfinding or portal mechanics.

### Key Features

- **Automatic Rotation Playback**: Rotations trigger automatically when player reaches configured departure points
- **Sequential Waypoint Navigation**: Progress through multiple departure points in order (Point 1 → 2 → 3...)
- **✅ CV Item System Integration**: Package map config, pathfinding config, and departure points into reusable items
- **✅ Class-Based Pathfinding**: Character-specific movement (other/magician classes) with skill configurations
- **3-Tier Pathfinding Strategy**: Class-based, recorded sequences, or simple directional (legacy)
- **Port Flow Navigation**: Special handling for MapleStory portal/teleport mechanics
- **Multiple Rotation Modes**: Random, sequential, or single rotation selection per point
- **Loop Support**: Automatically cycle back to first point after completing sequence
- **Real-time Status Monitoring**: Track current point, rotations played, and progress

### 🆕 What's New in Version 2.1 (December 2025)

- ✅ **Configurable Jump Key**: Jump key now configurable via Play Settings (default: "SPACE")
- ✅ **Loop Count System**: Loop parameter changed from boolean to integer (loop N times)
- ✅ **Play Settings Integration**: Full integration with PlaySettingsModal for global configuration

### 🆕 What's New in Version 2.0 (December 2025)

- ✅ **CV Item System**: Complete automation setups now packaged as reusable CV Items
- ✅ **Class-Based Pathfinding**: Replaces distance-based system with character-specific movement logic
- ✅ **Humanlike Timing**: ±10% jitter on all pathfinding movements for natural feel
- ✅ **Skill Configuration**: Rope lift, diagonal movement, teleport, and jump skills
- ✅ **2-Step Creation Wizard**: Intuitive UI for creating CV Items with live preview

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     CV-AUTO System Stack                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Frontend (React)                                            │
│  ├── CVAutoControl.jsx       - Start/stop panel             │
│  ├── RotationPicker.jsx      - Link rotations to points     │
│  └── DeparturePointsManager  - Configure waypoints          │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Web API (aiohttp)                                           │
│  ├── POST /api/cv-auto/start        - Start CV-AUTO mode    │
│  ├── POST /api/cv-auto/stop         - Stop CV-AUTO mode     │
│  ├── GET  /api/cv-auto/status       - Get current state     │
│  └── PUT  /api/.../rotations        - Link rotations        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Daemon Layer (IPC Commands)                                 │
│  └── cv_auto_commands.py                                    │
│      ├── cv_auto_start()                                    │
│      ├── cv_auto_stop()                                     │
│      └── cv_auto_status()                                   │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Core Logic Modules                                          │
│  ├── PointNavigator          - Manage point progression     │
│  ├── PathfindingController   - Select navigation strategy   │
│  ├── PortFlowHandler         - Portal jump logic            │
│  └── MinimapObjectDetector   - Player position detection    │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Data Models                                                 │
│  ├── MapConfig               - Map configuration            │
│  ├── DeparturePoint          - Waypoint with rotations      │
│  └── NavigationState         - Current progress state       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌──────────────────┐
│  Object          │  500ms interval
│  Detection       ├──────────────────┐
│  (Player Pos)    │                  │
└──────────────────┘                  │
                                      ▼
                           ┌────────────────────┐
                           │  CV-AUTO Main Loop │
                           └──────┬─────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
            ┌──────────┐  ┌──────────┐  ┌──────────┐
            │  Check   │  │  Select  │  │ Navigate │
            │   Hit    │  │ Rotation │  │   to     │
            │  Point   │  │          │  │  Point   │
            └──────────┘  └──────────┘  └──────────┘
                    │             │             │
                    │             ▼             │
                    │      ┌──────────┐         │
                    │      │   Play   │         │
                    │      │ Rotation │         │
                    │      └──────────┘         │
                    │             │             │
                    │             ▼             │
                    │      ┌──────────┐         │
                    └─────▶│ Advance  │◀────────┘
                           │   to     │
                           │   Next   │
                           └──────────┘
```

---

## Data Models

### DeparturePoint

Enhanced departure point model with rotation linking:

```python
@dataclass
class DeparturePoint:
    # Position & Identification
    id: str                          # UUID
    name: str                        # User-defined name
    x: int                           # X coordinate (minimap relative)
    y: int                           # Y coordinate (minimap relative)
    order: int                       # Sequential order (0-based)

    # Hit Detection
    tolerance_mode: str = "both"     # "both", "x_axis", "y_axis", etc.
    tolerance_value: int = 5         # Pixel tolerance

    # Rotation Configuration (NEW)
    rotation_paths: List[str] = []   # Linked rotation files
    rotation_mode: str = "random"    # "random", "sequential", "single"
    is_teleport_point: bool = False  # Enable Port flow navigation
    auto_play: bool = True           # Auto-trigger rotations
    pathfinding_sequence: Optional[str] = None  # Pre-recorded path

    created_at: float = 0.0
```

#### Rotation Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| **random** | Randomly select from linked rotations | Farming with variety to avoid detection |
| **sequential** | Cycle through rotations in order | Testing all rotations systematically |
| **single** | Always play first rotation | Consistent single-rotation farming |

#### Tolerance Modes

| Mode | Description | Example |
|------|-------------|---------|
| **both** | Check X and Y within ±tolerance | Exact position match |
| **y_axis** | Check Y only, X can be anywhere | Horizontal platform |
| **x_axis** | Check X only, Y can be anywhere | Vertical ladder |
| **y_greater** | Current Y > saved Y | Falling/descending |
| **y_less** | Current Y < saved Y | Climbing/ascending |

### NavigationState

Current CV-AUTO progress state:

```python
@dataclass
class NavigationState:
    current_point_index: int         # Current target point (0-based)
    total_points: int                # Total departure points
    current_point_name: str          # Name of current point
    last_rotation_played: str        # Last rotation file path
    rotations_played_count: int      # Total rotations played
    cycles_completed: int            # Complete cycles through all points
```

---

## Pathfinding System

### 3-Tier Strategy

#### Tier 1: Simple Directional Pathfinding

- **Best for**: Short distances (<50 pixels), direct line-of-sight
- **Method**: Calculate delta X/Y and press arrow keys
- **Features**:
  - Max 10 navigation attempts
  - Dynamic duration based on distance
  - Position checking every 300ms
  - Automatic retry on failure

**Example**:
```python
# Player at (100, 50), target at (120, 60)
# → Press RIGHT (0.15s), Press DOWN (0.15s)
# → Check position, repeat if needed
```

#### Tier 2: Recorded Pathfinding

- **Best for**: Complex routes requiring specific actions (rope climb, jump, etc.)
- **Method**: Replay pre-recorded movement sequence
- **Features**:
  - Uses same JSON format as rotations
  - Record once, reuse for all farming sessions
  - Precise timing preservation
  - Metadata support for organization

**Recording a Pathfinding Sequence**:
1. Record movement from Point A → Point B as normal rotation
2. Save as `path_to_point2.json`
3. Link to departure point via `pathfinding_sequence` field
4. System auto-plays this sequence when navigating to that point

**JSON Format**:
```json
{
  "t0": 0.0,
  "actions": [
    {"usage": 82, "press": 0.0, "dur": 0.3},    # Press UP (climb rope)
    {"usage": 79, "press": 0.5, "dur": 0.2},    # Press RIGHT (move right)
    {"usage": 44, "press": 1.0, "dur": 0.1}     # Press SPACE (jump)
  ],
  "metadata": {
    "type": "pathfinding",
    "map_name": "Henesys Hunting Ground",
    "purpose": "Navigate to Point 2 via rope"
  }
}
```

#### Tier 3: Waypoint-based (Future)

- **Status**: Planned for future enhancement
- **Method**: A* algorithm with obstacle detection
- **Use case**: Long-distance navigation across complex maps

### Strategy Selection Logic

```python
def select_strategy(distance, target_point):
    # Priority 1: Recorded sequence (if available)
    if target_point.pathfinding_sequence:
        return RecordedPathfinder(target_point.pathfinding_sequence)

    # Priority 2: Simple directional (for close targets)
    if distance < 50:
        return SimplePathfinder()

    # Priority 3: Simple directional (fallback)
    return SimplePathfinder()
```

### Jump Key Configuration

**New in December 2025**: Jump key is now configurable via Play Settings instead of being hardcoded.

#### Key Concepts

- **Jump Key**: The key used for jumping actions in pathfinding (double jump, vertical movement, etc.)
- **Arrow Keys**: Directional input keys (UP, DOWN, LEFT, RIGHT) remain hardcoded for map navigation
- **Key Aliases**: Use human-readable string aliases instead of HID usage IDs

#### Configuration

**Default**: `"SPACE"` (HID usage ID: 44)

**Supported Aliases**:
- Letters: `"A"` through `"Z"`
- Special keys: `"SPACE"`, `"Q"`, `"ALT"`, `"SHIFT"`, `"CTRL"`
- Function keys: `"F1"` through `"F12"`
- Arrow keys: `"UP"`, `"DOWN"`, `"LEFT"`, `"RIGHT"` (though UP arrow is for directional input)

**Configuration Method**:
1. Click Settings icon in Header
2. Open PlaySettingsModal
3. Set "Jump Key" field to desired key alias
4. Key is applied globally to all CV-AUTO pathfinding

#### Usage in Pathfinding

**ClassBasedPathfinder** uses the configured jump key for:
- Double jump horizontal movement
- Double jump UP movement (jump action, not directional UP)
- Y-axis jump with skill
- Jump down movement
- Diagonal jump with skill

**Directional uses of arrow keys** (unchanged):
- UP arrow in double jump UP (as directional modifier)
- UP arrow in magician teleport (directional input)
- DOWN arrow in all down movements
- LEFT/RIGHT arrows in all horizontal movements

---

## Port Flow Navigation

### Overview

Port Flow is a specialized navigation system for MapleStory portal mechanics. When `is_teleport_point=True`, the system uses UP key presses to activate portals, with automatic X-position adjustment for portal alignment.

### Port Flow Algorithm

```
┌─────────────────────────────────────────┐
│ 1. Press UP key                         │
│    └─▶ Activate portal                  │
└──────────────┬──────────────────────────┘
               │
               ▼
        ┌──────────────┐
        │ Wait 500ms   │ (for teleport animation)
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │ Check if hit │
        │ target point │
        └──────┬───────┘
               │
        ┌──────┴────────┐
        │               │
     Success          Fail
        │               │
        │               ▼
        │        ┌─────────────────┐
        │        │ Adjust X:       │
        │        │ If X < target:  │
        │        │   Press RIGHT   │
        │        │ If X > target:  │
        │        │   Press LEFT    │
        │        └────────┬────────┘
        │                 │
        │                 ▼
        │          ┌────────────┐
        │          │ Press UP   │
        │          └─────┬──────┘
        │                │
        │                ▼
        │         ┌─────────────┐
        │         │ Check again │
        │         └──────┬──────┘
        │                │
        │         (Retry up to 3 times)
        │                │
        ▼                ▼
     ┌──────────────────────┐
     │  Return Success/Fail │
     └──────────────────────┘
```

### Port Flow Failure Handling

If port flow fails after 3 attempts:
- **Action**: CV-AUTO mode stops automatically
- **Reason**: Prevents infinite loops and resource waste
- **User notification**: SSE event `CV_AUTO_ERROR` emitted
- **Recovery**: User can restart CV-AUTO manually after repositioning

### Port Detection

Automatic detection of unexpected teleports/map changes:

**Detection Criteria**:
1. **Abrupt position change**: Player jumps >50 pixels in single frame
2. **Detection timeout**: No position detected for >2 seconds

**Response**:
- Reset PointNavigator to first point
- Emit `CV_AUTO_PORT_DETECTED` event
- Wait 1 second for player stabilization
- Resume monitoring from Point 1

---

## CV-AUTO Main Loop

### Loop Flow

```python
while mode == "CV_AUTO":
    # 1. Get player position (500ms interval)
    player_pos = await get_player_position()
    if not player_pos:
        continue  # Retry

    # 2. Check for port/teleport
    if port_detector.check_port(player_pos):
        navigator.reset()
        continue

    # 3. Get current target point
    current_point = navigator.get_current_point()

    # 4. Check if player hit current point
    if current_point.check_hit(player_pos):
        # Select and play rotation
        rotation = navigator.select_rotation(current_point)
        if rotation and current_point.auto_play:
            await play_rotation(rotation)

        # Advance to next point
        has_next = navigator.advance()
        if not has_next:
            break  # End of sequence (no loop)

        next_point = navigator.get_current_point()

        # Navigate to next point
        if next_point.is_teleport_point:
            success = await port_flow.execute(player_pos, next_point)
            if not success:
                stop_cv_auto("Port flow failed")
                break
        else:
            await pathfinder.navigate_to(player_pos, next_point)

    else:
        # Not at current point, try to navigate there
        await navigate_to_current_point()

    # 5. Emit status update
    emit("CV_AUTO_STATUS", ...)

    await asyncio.sleep(0.5)
```

### State Transitions

```
┌──────────┐  cv_auto_start   ┌──────────┐
│          ├─────────────────▶│          │
│  BRIDGE  │                  │ CV_AUTO  │
│          │◀─────────────────┤          │
└──────────┘  cv_auto_stop    └────┬─────┘
              port flow fail        │
              sequence end          │
                                    │ rotation play
                                    │
                              ┌─────▼─────┐
                              │           │
                              │  PLAYING  │ (temporary)
                              │           │
                              └───────────┘
```

---

## API Reference

### Start CV-AUTO Mode

```http
POST /api/cv-auto/start
Content-Type: application/json

{
  "loop": 1,              # Loop count (repeat entire sequence N times)
  "speed": 1.0,           # Rotation playback speed multiplier
  "jitter_time": 0.05,    # Time jitter for human-like playback
  "jitter_hold": 0.02,    # Hold duration jitter
  "jump_key": "SPACE"     # Jump key alias (default: "SPACE")
}
```

**Response (Success)**:
```json
{"ok": true}
```

**Response (Error)**:
```json
{
  "error": "No active map config selected"
}
```

**Error Cases**:
- No active map config
- No departure points configured
- Object detection not enabled
- CV-AUTO already running

---

### Stop CV-AUTO Mode

```http
POST /api/cv-auto/stop
```

**Response**:
```json
{"ok": true}
```

---

### Get CV-AUTO Status

```http
GET /api/cv-auto/status
```

**Response**:
```json
{
  "enabled": true,
  "current_point_index": 2,
  "current_point_name": "Farming Spot 2",
  "total_points": 5,
  "last_rotation_played": "rotation_1.json",
  "rotations_played_count": 47,
  "cycles_completed": 3,
  "player_position": {"x": 120, "y": 45}
}
```

---

### Link Rotations to Departure Point

```http
PUT /api/cv/map-configs/{map_name}/departure-points/{point_id}/rotations
Content-Type: application/json

{
  "rotation_paths": [
    "henesys/rotation1.json",
    "henesys/rotation2.json",
    "henesys/rotation3.json"
  ],
  "rotation_mode": "random",
  "is_teleport_point": false,
  "auto_play": true
}
```

**Response**:
```json
{"ok": true}
```

---

## SSE Events

CV-AUTO mode emits real-time events via Server-Sent Events:

| Event | Payload | Description |
|-------|---------|-------------|
| `CV_AUTO_STARTED` | `{map_name, total_points}` | CV-AUTO mode activated |
| `CV_AUTO_STOPPED` | `{}` | CV-AUTO mode stopped |
| `CV_AUTO_STATUS` | `{current_index, current_point, total_points, player_position}` | Real-time progress update (every 500ms) |
| `CV_AUTO_ROTATION_START` | `{point, rotation}` | Rotation playback started |
| `CV_AUTO_ROTATION_END` | `{point, rotation}` | Rotation playback completed |
| `CV_AUTO_PORT_DETECTED` | `{}` | Unexpected port/teleport detected |
| `CV_AUTO_ERROR` | `{reason}` | Error occurred (e.g., "Port flow failed") |

---

## Usage Guide

### Setup Workflow

#### 1. Configure Map and Departure Points

```bash
# Navigate to Map Config in Web UI
1. Click "CV Configuration" tab
2. Create/activate map config for your farming map
3. Click "Capture Departure Points"
4. Position player at first farming spot
5. Click "Save Current Position" → Name it "Point 1"
6. Move to second farming spot
7. Click "Save Current Position" → Name it "Point 2"
8. Repeat for all farming spots
9. Reorder points if needed (drag and drop)
```

#### 2. Record Rotations

```bash
# Navigate to Recordings tab
1. Click "Start Recording" (or press CTRL+R)
2. Execute your farming rotation (skills, movement, etc.)
3. Click "Stop Recording" (or press CTRL+Q)
4. Name rotation (e.g., "henesys_rotation1")
5. Save rotation
6. Repeat for multiple rotations (for random mode)
```

#### 3. Link Rotations to Departure Points

```bash
# Navigate to Departure Points Manager
1. Select a departure point from the list
2. Click "Link Rotations" button
3. Multi-select rotations from your recordings
4. Choose rotation mode (Random/Sequential/Single)
5. Toggle "Is Teleport Point" if portal needed
6. Toggle "Auto-play" (usually keep enabled)
7. Save configuration
8. Repeat for each departure point
```

#### 4. (Optional) Record Pathfinding Sequences

For complex navigation between points:

```bash
1. Position player at Point 1
2. Start recording (as normal rotation)
3. Navigate to Point 2 using required actions (rope, jump, etc.)
4. Stop recording
5. Save as "path_to_point2"
6. In Departure Points Manager:
   - Edit Point 2
   - Set "Pathfinding Sequence" = "path_to_point2.json"
   - Save
```

#### 5. Start CV-AUTO Mode

```bash
# Navigate to CV-AUTO Control Panel
1. Ensure Object Detection is enabled
2. Ensure active map config is selected
3. Configure settings (via Settings icon in Header):
   - Loop: 1 (play once), or N (repeat N times)
   - Speed: 1.0 (normal speed)
   - Jitter: Default values (human-like)
   - Jump Key: "SPACE" (or custom key like "Q", "ALT")
4. Click "Start CV-AUTO"
5. Monitor status: current point, rotations played, cycles
6. Click "Stop CV-AUTO" when done
```

---

## Configuration Examples

### Example 1: Simple Farming (3 Points, Random Rotations)

**Map**: Henesys Hunting Ground
**Points**: 3 farming spots in a triangle
**Rotations**: 2 rotations per point for variety

```json
{
  "name": "Henesys Hunting Ground",
  "departure_points": [
    {
      "id": "uuid-1",
      "name": "Top Platform",
      "x": 100, "y": 30,
      "order": 0,
      "tolerance_mode": "both",
      "tolerance_value": 5,
      "rotation_paths": [
        "henesys/rotation_top_1.json",
        "henesys/rotation_top_2.json"
      ],
      "rotation_mode": "random",
      "is_teleport_point": false,
      "auto_play": true
    },
    {
      "id": "uuid-2",
      "name": "Middle Platform",
      "x": 150, "y": 50,
      "order": 1,
      "rotation_paths": [
        "henesys/rotation_mid_1.json",
        "henesys/rotation_mid_2.json"
      ],
      "rotation_mode": "random"
    },
    {
      "id": "uuid-3",
      "name": "Bottom Platform",
      "x": 100, "y": 70,
      "order": 2,
      "rotation_paths": [
        "henesys/rotation_bot_1.json",
        "henesys/rotation_bot_2.json"
      ],
      "rotation_mode": "random"
    }
  ]
}
```

**Flow**:
```
Point 1 (Top) → Play random rotation → Pathfind to Point 2 (Middle)
  → Play random rotation → Pathfind to Point 3 (Bottom)
  → Play random rotation → Loop back to Point 1
```

---

### Example 2: Portal-based Farming (2 Maps)

**Map**: Victoria Road (with portal to Sleepywood)
**Points**: Farm in two different maps connected by portal
**Special**: Uses Port flow for portal navigation

```json
{
  "name": "Victoria Road + Sleepywood",
  "departure_points": [
    {
      "id": "uuid-1",
      "name": "Victoria Road Farming Spot",
      "x": 120, "y": 45,
      "order": 0,
      "rotation_paths": ["victoria_rotation.json"],
      "rotation_mode": "single",
      "is_teleport_point": false
    },
    {
      "id": "uuid-2",
      "name": "Portal Entry Point",
      "x": 200, "y": 45,
      "order": 1,
      "rotation_paths": [],  # No rotation, just portal
      "auto_play": false,    # Don't play rotation
      "is_teleport_point": true  # Use Port flow
    },
    {
      "id": "uuid-3",
      "name": "Sleepywood Farming Spot",
      "x": 80, "y": 60,
      "order": 2,
      "rotation_paths": ["sleepywood_rotation.json"],
      "rotation_mode": "single",
      "is_teleport_point": false
    }
  ]
}
```

**Flow**:
```
Point 1 (Victoria Road) → Play rotation → Pathfind to Point 2 (Portal)
  → Port Flow (UP key to enter portal) → Arrive at Point 3 (Sleepywood)
  → Play rotation → Loop back to Point 1 (via Return Scroll or reverse portal)
```

---

### Example 3: Complex Multi-Level Farming

**Map**: Kerning City Construction Site
**Points**: 5 platforms requiring rope climbing
**Special**: Uses recorded pathfinding sequences

```json
{
  "name": "Kerning Construction Site",
  "departure_points": [
    {
      "id": "uuid-1",
      "name": "Ground Floor",
      "x": 100, "y": 80,
      "order": 0,
      "rotation_paths": ["construction/ground.json"],
      "rotation_mode": "single"
    },
    {
      "id": "uuid-2",
      "name": "Level 2",
      "x": 150, "y": 60,
      "order": 1,
      "rotation_paths": ["construction/level2.json"],
      "rotation_mode": "single",
      "pathfinding_sequence": "construction/path_to_level2.json"  # Rope climb
    },
    {
      "id": "uuid-3",
      "name": "Level 3",
      "x": 100, "y": 40,
      "order": 2,
      "rotation_paths": ["construction/level3.json"],
      "rotation_mode": "single",
      "pathfinding_sequence": "construction/path_to_level3.json"  # Rope + jump
    }
  ]
}
```

**Pathfinding Sequence Example** (`path_to_level2.json`):
```json
{
  "t0": 0.0,
  "actions": [
    {"usage": 79, "press": 0.0, "dur": 0.2},   # RIGHT (move to rope)
    {"usage": 82, "press": 0.3, "dur": 0.5},   # UP (climb rope)
    {"usage": 79, "press": 0.9, "dur": 0.1}    # RIGHT (step onto platform)
  ],
  "metadata": {
    "type": "pathfinding",
    "map_name": "Kerning Construction Site",
    "purpose": "Navigate from Ground Floor to Level 2"
  }
}
```

---

## Troubleshooting

### CV-AUTO Won't Start

**Error**: "No active map config selected"
- **Fix**: Go to CV Configuration → Select and activate a map config

**Error**: "No departure points configured"
- **Fix**: Add at least one departure point to the active map

**Error**: "Object detection must be enabled first"
- **Fix**: Click "Start Object Detection" before starting CV-AUTO

---

### Rotation Not Playing

**Symptom**: Point is hit but no rotation plays
- **Check 1**: Verify `auto_play` is enabled for that point
- **Check 2**: Verify rotations are linked to the point
- **Check 3**: Check rotation files exist in recordings directory
- **Check 4**: Review daemon logs for rotation playback errors

---

### Navigation Failing

**Symptom**: Player gets stuck, doesn't move to next point
- **Check 1**: Verify tolerance settings (increase `tolerance_value` if too strict)
- **Check 2**: For `is_teleport_point=true`, ensure portal is accessible
- **Check 3**: For complex routes, record a pathfinding sequence
- **Check 4**: Check for obstacles blocking simple directional movement

---

### Port Flow Failing

**Error**: "Port flow failed after 3 attempts"
- **Fix 1**: Verify portal is at the correct coordinates
- **Fix 2**: Increase tolerance for portal entry point
- **Fix 3**: Manually test portal is accessible (not blocked, correct map state)
- **Fix 4**: Record pathfinding sequence to approach portal from correct angle

---

### Unexpected Teleports Detected

**Symptom**: Navigator keeps resetting to Point 1
- **Cause**: Return Scrolls, manual ports, or other map changes
- **Fix**: Expected behavior - system detects port and resets for safety
- **Workaround**: If intentional, disable auto-reset (future feature)

---

## Performance Considerations

### Recommended Settings

| Setting | Recommended Value | Rationale |
|---------|-------------------|-----------|
| **Object Detection Interval** | 500ms | Balance accuracy vs. CPU usage |
| **Tolerance Value** | 5-10 pixels | Too low = missed hits, too high = early triggers |
| **Loop Count** | 1-10 | 1 = play once, higher values for repeated farming |
| **Speed** | 1.0 | Normal playback, reduce for slower machines |
| **Jitter Time** | 0.05s | Human-like timing variation |
| **Jitter Hold** | 0.02s | Prevents detection as bot |
| **Jump Key** | "SPACE" | Default jump key, change if character uses different key |

### Resource Usage

| Component | CPU Usage | Memory | Disk I/O |
|-----------|-----------|--------|----------|
| Object Detection | ~15-25% (Pi 4) | ~50MB | Minimal |
| CV-AUTO Loop | ~5-10% | ~20MB | Low (rotation loading) |
| Pathfinding | <5% | ~10MB | None |
| Port Flow | <5% | <10MB | None |

### Optimization Tips

1. **Reduce Loop Frequency**: Increase `asyncio.sleep(0.5)` to `1.0` for lower CPU usage
2. **Use Single Rotation Mode**: Faster loading than random selection
3. **Pre-load Rotations**: (Future feature) Load all rotations at start
4. **Minimize Departure Points**: Fewer points = less checking overhead
5. **Use Simple Pathfinding**: Avoid recorded sequences unless necessary

---

## Implementation Details

### File Locations

```
msmacro-app/
├── msmacro/
│   ├── cv/
│   │   ├── map_config.py          # DeparturePoint data model
│   │   ├── pathfinding.py         # 3-tier pathfinding system
│   │   ├── port_flow.py           # Port flow & detection
│   │   └── object_detection.py    # Player position detection
│   ├── daemon/
│   │   └── point_navigator.py     # PointNavigator class
│   ├── daemon_handlers/
│   │   ├── cv_auto_commands.py    # CV-AUTO IPC handlers
│   │   └── cv_commands.py         # Rotation linking handler
│   └── web/
│       ├── handlers.py            # API endpoints
│       └── server.py              # Route registration
├── webui/
│   └── src/
│       └── components/
│           ├── CVAutoControl.jsx  # Frontend control panel
│           ├── RotationPicker.jsx # Rotation linking UI
│           └── DeparturePointsManager.jsx  # Updated with rotation picker
└── docus/
    └── 11_CV_AUTO_ROTATION.md    # This documentation
```

### Code Statistics

| Module | Lines of Code | Description |
|--------|---------------|-------------|
| `map_config.py` | ~80 | DeparturePoint enhancements |
| `pathfinding.py` | 378 | 3-tier pathfinding system |
| `port_flow.py` | 212 | Port flow handler |
| `point_navigator.py` | 270 | Point progression logic |
| `cv_auto_commands.py` | 360 | IPC command handlers |
| `cv_commands.py` | +68 | Rotation linking endpoint |
| `handlers.py` | +97 | Web API endpoints |
| **Total** | **~1,465** | **Backend implementation** |

---

## Future Enhancements

### Planned Features

1. **Waypoint-based Pathfinding (Tier 3)**
   - A* algorithm implementation
   - Obstacle detection and avoidance
   - Long-distance navigation optimization

2. **Skill Injection Integration**
   - Auto-cast buff skills between rotations
   - Cooldown tracking and management
   - Skill priority system

3. **Advanced Port Detection**
   - Map ID comparison (vs. position-only)
   - Intentional vs. unexpected port differentiation
   - Auto-recovery from unintended ports

4. **Rotation Preloading**
   - Load all rotations at CV-AUTO start
   - Reduce playback latency
   - Memory caching for faster access

5. **Conditional Departure Points**
   - Skip points based on conditions (e.g., player level, buff status)
   - Dynamic point reordering
   - Event-based triggers

6. **Multi-Map Support**
   - Seamless farming across multiple maps
   - Automatic map switching
   - Map-specific rotation sets

7. **Analytics Dashboard**
   - Farming efficiency metrics
   - Rotation success rates
   - Point hit statistics
   - Performance graphs

---

## Contributing

To contribute to CV-AUTO development:

1. **Report Issues**: https://github.com/your-repo/issues
2. **Documentation**: Update this file with new features
3. **Testing**: Test on Raspberry Pi 4 and report performance
4. **Code Style**: Follow existing Python conventions

---

## Changelog

### v2.1.0 (December 2025)

#### Added
- ✅ **Configurable Jump Key**: Jump key now configurable via Play Settings (default: "SPACE")
  - Supports string key aliases (e.g., "SPACE", "Q", "ALT")
  - Global configuration applies to all CV-AUTO pathfinding
  - Converted via `name_to_usage()` keymap utility
- ✅ **Loop Count**: Loop parameter changed from boolean to integer
  - `loop=N` means repeat entire CV-AUTO sequence N times
  - Tracks completed cycles and stops after N loops
  - Default: 1 (play once)

#### Changed
- 🔄 ClassBasedPathfinder uses configurable jump key instead of hardcoded ARROW_UP
- 🔄 PathfindingController accepts jump_key parameter (HID usage ID)
- 🔄 CV-AUTO handler tracks loop counter and implements N-cycle logic
- 🔄 PlaySettingsModal updated with jump_key input field
- 🔄 API documentation updated to reflect loop count and jump_key parameters

#### Technical Details
- Jump key configuration stored globally in play settings
- Arrow keys (UP, DOWN, LEFT, RIGHT) remain hardcoded for directional input
- Jump key used for: double jump, vertical movement, diagonal jump
- Backward compatible: defaults to SPACE if not configured

---

### v1.0.0 (November 2025)

#### Added
- ✅ Core CV-AUTO rotation system
- ✅ 3-tier pathfinding (Simple, Recorded, placeholder for Waypoint)
- ✅ Port flow navigation for MapleStory portals
- ✅ Point navigator with rotation mode support (random/sequential/single)
- ✅ Departure point rotation linking (data model + API)
- ✅ Web API endpoints for CV-AUTO control
- ✅ SSE events for real-time status updates
- ✅ Port detection and auto-recovery
- ✅ IPC command handlers
- ✅ Comprehensive documentation

#### Changed
- 🔄 DeparturePoint model extended with 5 new fields
- 🔄 MapConfig API to support rotation linking

#### Migrations
- ✅ Existing map configs compatible (new fields have defaults)
- ✅ No database schema changes required

---

## License

This feature is part of the msmacro project and follows the same license.

---

## Support

For questions or support:
- **Documentation**: This file (`11_CV_AUTO_ROTATION.md`)
- **API Reference**: See [API Reference](#api-reference) section
- **Troubleshooting**: See [Troubleshooting](#troubleshooting) section
- **Issues**: GitHub Issues (if available)
