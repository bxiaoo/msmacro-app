# Object Detection Implementation Plan

## Executive Summary

Implement minimap object detection to track player position (yellow point) and detect other players (red points) for automated navigation and position-based macro corrections.

**Timeline**: 5 weeks (5 phases)
**Risk**: Low - Isolated module, no breaking changes
**Dependencies**: OpenCV, NumPy (already installed), Test Raspberry Pi (separate from production)

**Critical Requirement**: Two-stage development due to YUYV production environment:
- Stage 1: Algorithm development with JPEG test images (placeholder HSV values)
- Stage 2: Calibration on test Pi with real YUYV frames (final HSV values)

## Phase 0: Test Pi Setup & YUYV Dataset Creation (Week 1)

### Overview

**Goal**: Prepare test Pi infrastructure and create YUYV test dataset before algorithm development

**Why First**: Cannot calibrate color detection without real YUYV frames from Pi hardware. Development with JPEG images uses placeholder HSV ranges that **will not** work in production.

### Deliverables

1. **Test Pi deployment** - Object detection code running on test Pi
2. **YUYV dataset** - 50+ raw frames covering various scenarios
3. **Ground truth annotations** - Manual labels for validation
4. **Validation script** - Automated accuracy measurement

### Phase 0 Task Breakdown

#### Task 0.1: Deploy to Test Pi

**File**: Deploy existing msmacro codebase to test Pi

**Steps**:
1. Clone msmacro repo to test Pi
2. Install dependencies (`pip install -e .`)
3. Verify CV capture working with YUYV input
4. Test web UI access from dev machine: http://test-pi.local:5050
5. Verify IPC socket communication

**Time**: 2 hours
**Test**: Run `python -m msmacro daemon`, access web UI, capture frame via API

#### Task 0.2: YUYV Dataset Capture Script

**File**: `scripts/capture_yuyv_dataset.py`

```python
"""
Capture YUYV minimap frames for object detection test dataset.

Usage:
    python scripts/capture_yuyv_dataset.py --output data/yuyv_test_set/ --count 60
"""

import time
import argparse
from pathlib import Path
import numpy as np
from msmacro.cv.capture import get_capture_instance

def capture_yuyv_dataset(output_dir: Path, count: int = 60, interval: float = 2.0):
    """
    Capture minimap frames in YUYV format.

    Args:
        output_dir: Directory to save .yuv files
        count: Number of frames to capture
        interval: Seconds between captures
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = get_capture_instance()

    print(f"Capturing {count} YUYV frames to {output_dir}")
    print("Game state scenarios needed:")
    print("  - Player alone (various positions): 15 frames")
    print("  - Player at edges/corners: 10 frames")
    print("  - Player + 1 other: 10 frames")
    print("  - Player + 2-3 others: 10 frames")
    print("  - Player + 5+ others: 5 frames")
    print("  - Different lighting (day/night): 10 frames")

    for i in range(count):
        # Get raw YUYV frame
        frame_bgr, metadata = capture.get_latest_frame()

        # Extract minimap region (340x86)
        minimap_bgr = frame_bgr[56:142, 68:408]

        # Save as raw numpy array (can convert back to YUYV if needed)
        filename = output_dir / f"minimap_{i:04d}_{int(time.time())}.npy"
        np.save(filename, minimap_bgr)

        print(f"Captured {i+1}/{count}: {filename.name}")
        time.sleep(interval)

    print(f"Dataset capture complete: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/yuyv_test_set"))
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    capture_yuyv_dataset(args.output, args.count, args.interval)
```

**Time**: 4 hours
**Test**: Run script, verify .npy files saved correctly, load and display with cv2.imshow()

#### Task 0.3: Ground Truth Annotation Tool

**File**: `scripts/annotate_ground_truth.py`

```python
"""
Manual ground truth annotation tool for YUYV test dataset.

Usage:
    python scripts/annotate_ground_truth.py --dataset data/yuyv_test_set/
"""

import argparse
from pathlib import Path
import json
import cv2
import numpy as np

class AnnotationTool:
    def __init__(self, dataset_dir: Path):
        self.dataset_dir = dataset_dir
        self.frames = sorted(dataset_dir.glob("*.npy"))
        self.annotations = {}
        self.current_idx = 0
        self.player_clicks = []
        self.other_clicks = []

    def run(self):
        """Interactive annotation loop."""
        cv2.namedWindow("Annotate")
        cv2.setMouseCallback("Annotate", self._mouse_callback)

        while self.current_idx < len(self.frames):
            frame_path = self.frames[self.current_idx]
            frame = np.load(frame_path)

            # Draw current annotations
            vis = frame.copy()
            for x, y in self.player_clicks:
                cv2.circle(vis, (x, y), 5, (0, 255, 255), 2)  # Yellow
            for x, y in self.other_clicks:
                cv2.circle(vis, (x, y), 5, (0, 0, 255), 2)    # Red

            # Instructions
            cv2.putText(vis, "Click: Player (yellow)", (10, 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.putText(vis, "Shift+Click: Other players (red)", (10, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            cv2.putText(vis, "n: Next | s: Save | q: Quit", (10, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            cv2.imshow("Annotate", vis)

            key = cv2.waitKey(0) & 0xFF
            if key == ord('n'):  # Next
                self._save_current_annotation(frame_path)
                self.current_idx += 1
                self.player_clicks = []
                self.other_clicks = []
            elif key == ord('s'):  # Save
                self._save_annotations()
            elif key == ord('q'):  # Quit
                break

        cv2.destroyAllWindows()
        self._save_annotations()

    def _mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if flags & cv2.EVENT_FLAG_SHIFTKEY:
                self.other_clicks.append((x, y))
            else:
                self.player_clicks = [(x, y)]  # Only one player

    def _save_current_annotation(self, frame_path):
        annotation = {
            "player": self.player_clicks[0] if self.player_clicks else None,
            "other_players": self.other_clicks
        }
        self.annotations[frame_path.name] = annotation

    def _save_annotations(self):
        output_path = self.dataset_dir / "ground_truth.json"
        with open(output_path, 'w') as f:
            json.dump(self.annotations, f, indent=2)
        print(f"Annotations saved: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()

    tool = AnnotationTool(args.dataset)
    tool.run()
```

**Time**: 6 hours
**Test**: Run on YUYV dataset, annotate 10 frames, verify JSON saved correctly

#### Task 0.4: Automated Validation Script

**File**: `scripts/validate_detection.py`

```python
"""
Validate object detection accuracy against ground truth.

Usage:
    python scripts/validate_detection.py --dataset data/yuyv_test_set/
"""

import argparse
from pathlib import Path
import json
import numpy as np
from msmacro.cv.object_detection import MinimapObjectDetector

def validate_detection(dataset_dir: Path):
    """Run detection on test dataset and calculate metrics."""
    # Load ground truth
    gt_path = dataset_dir / "ground_truth.json"
    with open(gt_path) as f:
        ground_truth = json.load(f)

    detector = MinimapObjectDetector()

    metrics = {
        "player_tp": 0,  # True positives
        "player_fp": 0,  # False positives
        "player_fn": 0,  # False negatives
        "position_errors": [],
        "other_tp": 0,
        "other_fp": 0,
        "other_fn": 0
    }

    for filename, gt in ground_truth.items():
        frame = np.load(dataset_dir / filename)
        result = detector.detect(frame)

        # Player detection
        if gt["player"] is not None:
            if result.player.detected:
                metrics["player_tp"] += 1
                gt_x, gt_y = gt["player"]
                error = np.sqrt((result.player.x - gt_x)**2 +
                               (result.player.y - gt_y)**2)
                metrics["position_errors"].append(error)
            else:
                metrics["player_fn"] += 1
        else:
            if result.player.detected:
                metrics["player_fp"] += 1

        # Other players detection
        has_others = len(gt["other_players"]) > 0
        if has_others and result.other_players.detected:
            metrics["other_tp"] += 1
        elif has_others and not result.other_players.detected:
            metrics["other_fn"] += 1
        elif not has_others and result.other_players.detected:
            metrics["other_fp"] += 1

    # Calculate metrics
    player_precision = metrics["player_tp"] / (metrics["player_tp"] + metrics["player_fp"])
    player_recall = metrics["player_tp"] / (metrics["player_tp"] + metrics["player_fn"])
    avg_position_error = np.mean(metrics["position_errors"])

    other_precision = metrics["other_tp"] / (metrics["other_tp"] + metrics["other_fp"])
    other_recall = metrics["other_tp"] / (metrics["other_tp"] + metrics["other_fn"])

    print("=" * 60)
    print("OBJECT DETECTION VALIDATION RESULTS")
    print("=" * 60)
    print(f"Player Detection:")
    print(f"  Precision: {player_precision:.2%} (target: >90%)")
    print(f"  Recall: {player_recall:.2%} (target: >85%)")
    print(f"  Avg Position Error: {avg_position_error:.2f} px (target: <5px)")
    print(f"\nOther Players Detection:")
    print(f"  Precision: {other_precision:.2%} (target: >85%)")
    print(f"  Recall: {other_recall:.2%} (target: >80%)")
    print("=" * 60)

    # Gate check
    gate_passed = (
        player_precision >= 0.90 and
        player_recall >= 0.85 and
        avg_position_error < 5.0 and
        other_precision >= 0.85 and
        other_recall >= 0.80
    )

    if gate_passed:
        print("✅ VALIDATION PASSED - Ready for production deployment")
    else:
        print("❌ VALIDATION FAILED - Recalibrate HSV ranges")

    return gate_passed

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()

    validate_detection(args.dataset)
```

**Time**: 4 hours
**Test**: Run on annotated dataset, verify metrics calculated correctly

### Phase 0 Deliverables Checklist

- [ ] Test Pi accessible remotely via web UI
- [ ] YUYV dataset captured (50+ frames, various scenarios)
- [ ] Ground truth annotations complete
- [ ] Validation script working
- [ ] Documentation updated

**Gate**: Cannot proceed to Phase 2 (YUYV calibration) without completed test dataset

---

## Phase 1: Core Detection Module (Week 2)

**⚠️ IMPORTANT**: This phase uses JPEG test images with **placeholder** HSV ranges. Real calibration happens in Phase 2 on test Pi with YUYV frames.

### Deliverables

1. **`msmacro/cv/object_detection.py`** - Complete detector implementation
2. **Unit tests** - Test with sample images
3. **Debug scripts** - Visualization and color tuning tools

### Implementation Tasks

#### Task 1.1: Data Classes and Configuration

```python
# Define data structures
@dataclass
class PlayerPosition:
    detected: bool
    x: int
    y: int
    confidence: float = 0.0

@dataclass
class OtherPlayersStatus:
    detected: bool
    count: int = 0

@dataclass
class DetectionResult:
    player: PlayerPosition
    other_players: OtherPlayersStatus
    timestamp: float

@dataclass
class DetectorConfig:
    # Player detection
    player_hsv_lower: Tuple[int, int, int]
    player_hsv_upper: Tuple[int, int, int]
    
    # Other players detection
    other_player_hsv_ranges: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]
    
    # Blob filtering
    min_blob_size: int
    max_blob_size: int
    min_circularity: float
```

**Time**: 2 hours  
**Test**: Verify data structures serialize/deserialize correctly

#### Task 1.2: HSV Color Masking

```python
def _create_color_mask(frame: np.ndarray, 
                       hsv_lower: Tuple[int, int, int],
                       hsv_upper: Tuple[int, int, int]) -> np.ndarray:
    """
    Create binary mask for color range.
    
    Args:
        frame: BGR image
        hsv_lower: (h_min, s_min, v_min)
        hsv_upper: (h_max, s_max, v_max)
    
    Returns:
        Binary mask (0 or 255)
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, hsv_lower, hsv_upper)
    
    # Morphological operations to clean noise
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)  # Remove noise
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # Fill holes
    
    return mask
```

**Time**: 3 hours  
**Test**: Apply to sample images, verify mask quality

#### Task 1.3: Blob Detection and Filtering

```python
def _find_circular_blobs(mask: np.ndarray,
                         min_size: int,
                         max_size: int,
                         min_circularity: float) -> List[Dict]:
    """
    Find circular blobs in binary mask.
    
    Returns:
        List of blobs with keys: 'center', 'radius', 'circularity'
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    blobs = []
    for contour in contours:
        # Calculate properties
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        
        if perimeter == 0:
            continue
        
        # Circularity = 4π*area / perimeter²
        circularity = 4 * np.pi * area / (perimeter ** 2)
        
        # Size filtering
        radius = np.sqrt(area / np.pi)
        if radius < min_size / 2 or radius > max_size / 2:
            continue
        
        # Circularity filtering
        if circularity < min_circularity:
            continue
        
        # Get centroid
        M = cv2.moments(contour)
        if M["m00"] == 0:
            continue
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        
        blobs.append({
            'center': (cx, cy),
            'radius': radius,
            'circularity': circularity,
            'area': area
        })
    
    return blobs
```

**Time**: 4 hours  
**Test**: Run on test images, verify blob detection accuracy

#### Task 1.4: Player Detection Logic

```python
def _detect_player(self, frame: np.ndarray) -> PlayerPosition:
    """Detect single yellow player point."""
    mask = self._create_color_mask(
        frame,
        self.config.player_hsv_lower,
        self.config.player_hsv_upper
    )
    
    blobs = self._find_circular_blobs(
        mask,
        self.config.min_blob_size,
        self.config.max_blob_size,
        self.config.min_circularity
    )
    
    if not blobs:
        return PlayerPosition(detected=False, x=0, y=0)
    
    # Take blob closest to center (most likely player)
    frame_center = (frame.shape[1] // 2, frame.shape[0] // 2)
    
    def distance_to_center(blob):
        cx, cy = blob['center']
        dx = cx - frame_center[0]
        dy = cy - frame_center[1]
        return dx**2 + dy**2
    
    best_blob = min(blobs, key=distance_to_center)
    
    return PlayerPosition(
        detected=True,
        x=best_blob['center'][0],
        y=best_blob['center'][1],
        confidence=best_blob['circularity']
    )
```

**Time**: 2 hours  
**Test**: Verify single player detection with various positions

#### Task 1.5: Other Players Detection Logic

```python
def _detect_other_players(self, frame: np.ndarray) -> OtherPlayersStatus:
    """Detect multiple red other_player points."""
    all_blobs = []
    
    # Red wraps around HSV, need multiple ranges
    for hsv_lower, hsv_upper in self.config.other_player_hsv_ranges:
        mask = self._create_color_mask(frame, hsv_lower, hsv_upper)
        blobs = self._find_circular_blobs(
            mask,
            self.config.min_blob_size,
            self.config.max_blob_size,
            self.config.min_circularity
        )
        all_blobs.extend(blobs)
    
    # Remove duplicates (same position detected in multiple ranges)
    unique_blobs = self._deduplicate_blobs(all_blobs, distance_threshold=5)
    
    return OtherPlayersStatus(
        detected=len(unique_blobs) > 0,
        count=len(unique_blobs)
    )
```

**Time**: 2 hours  
**Test**: Verify multiple other player detection

#### Task 1.6: Main Detection Entry Point

```python
def detect(self, frame: np.ndarray) -> DetectionResult:
    """Main detection entry point."""
    import time
    
    player = self._detect_player(frame)
    other_players = self._detect_other_players(frame)
    
    return DetectionResult(
        player=player,
        other_players=other_players,
        timestamp=time.time()
    )
```

**Time**: 1 hour  
**Test**: End-to-end detection test

#### Task 1.7: Visualization for Debugging

```python
def visualize(self, frame: np.ndarray, result: DetectionResult) -> np.ndarray:
    """Draw detection results on frame."""
    vis = frame.copy()
    
    # Draw player
    if result.player.detected:
        cv2.circle(vis, (result.player.x, result.player.y), 8, (0, 255, 255), 2)
        cv2.putText(vis, f"Player ({result.player.x},{result.player.y})",
                    (result.player.x + 12, result.player.y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
    
    # Draw other players indicator
    if result.other_players.detected:
        cv2.putText(vis, f"Other Players: {result.other_players.count}",
                    (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    return vis
```

**Time**: 2 hours  
**Test**: Generate visualization images for various scenarios

### Phase 1 Deliverables Checklist

- [ ] `object_detection.py` implemented
- [ ] Unit tests passing (>90% coverage)
- [ ] Debug visualization working
- [ ] Color tuning script created
- [ ] Performance benchmarked (< 5ms per frame)
- [ ] Documentation updated

---

## Phase 2: Integration (Week 2)

### Task 2.1: Add to CVCapture

**File**: `msmacro/cv/capture.py`

```python
class CVCapture:
    def __init__(self):
        # ... existing code ...
        self._object_detector = None
        self._object_detection_enabled = False
        self._last_detection_result = None
        
    def enable_object_detection(self, config: dict):
        """Enable object detection with configuration."""
        from .object_detection import MinimapObjectDetector, DetectorConfig
        
        detector_config = DetectorConfig(**config)
        self._object_detector = MinimapObjectDetector(detector_config)
        self._object_detection_enabled = True
        
    def _capture_loop(self):
        # ... existing capture code ...
        
        # After frame capture
        if self._object_detection_enabled and self._object_detector:
            try:
                # Use minimap region
                result = self._object_detector.detect(minimap_frame)
                self._last_detection_result = result
                
                # Emit event
                emit("OBJECT_DETECTED", result.to_dict())
            except Exception as e:
                log.error(f"Object detection failed: {e}")
```

**Time**: 4 hours  
**Test**: Verify detection runs in capture loop without errors

### Task 2.2: Daemon Commands

**File**: `msmacro/daemon_handlers/cv_commands.py`

Add methods:
```python
async def object_detection_status(self, msg: Dict[str, Any]) -> Dict[str, Any]:
    """Get object detection status."""
    capture = get_capture_instance()
    
    return {
        "enabled": capture._object_detection_enabled,
        "last_result": capture._last_detection_result.to_dict() if capture._last_detection_result else None
    }

async def object_detection_start(self, msg: Dict[str, Any]) -> Dict[str, Any]:
    """Start object detection."""
    config = msg.get("config", {})
    capture = get_capture_instance()
    capture.enable_object_detection(config)
    
    return {"success": True}

async def object_detection_stop(self, msg: Dict[str, Any]) -> Dict[str, Any]:
    """Stop object detection."""
    capture = get_capture_instance()
    capture._object_detection_enabled = False
    
    return {"success": True}
```

**Time**: 2 hours  
**Test**: IPC command tests

### Task 2.3: Web API Endpoints

**File**: `msmacro/web/handlers.py`

```python
async def api_object_detection_status(request: web.Request):
    """Get object detection status and latest result."""
    try:
        result = await _daemon("object_detection_status")
        return _json(result)
    except Exception as e:
        return _json({"error": str(e)}, 500)

async def api_object_detection_start(request: web.Request):
    """Start object detection."""
    try:
        data = await request.json()
        config = data.get("config", {})
        result = await _daemon("object_detection_start", config=config)
        return _json(result)
    except Exception as e:
        return _json({"error": str(e)}, 500)
```

**Time**: 3 hours  
**Test**: API endpoint tests

### Phase 2 Deliverables Checklist

- [ ] CVCapture integration complete
- [ ] Daemon commands working
- [ ] API endpoints tested
- [ ] SSE events emitting
- [ ] No performance regression
- [ ] Integration tests passing

---

## Phase 3: UI (Week 3)

### Task 3.1: Frontend API Client

**File**: `webui/src/api.js`

```javascript
// Object Detection API
export function getObjectDetectionStatus() {
  return API("/api/cv/object-detection/status");
}

export function startObjectDetection(config = {}) {
  return API("/api/cv/object-detection/start", {
    method: "POST",
    body: JSON.stringify({ config })
  });
}

export function stopObjectDetection() {
  return API("/api/cv/object-detection/stop", {
    method: "POST"
  });
}
```

**Time**: 1 hour

### Task 3.2: Object Detection Page Component

**File**: `webui/src/components/ObjectDetection.jsx`

Display:
- Detection status (enabled/disabled)
- Player position (x, y) with visualization
- Other players count
- Real-time updates via SSE
- Enable/disable toggle
- Configuration editor

**Time**: 8 hours  
**Test**: Manual UI testing

### Task 3.3: Color Configuration UI (Manual Tuning)

Interactive HSV range picker for tuning colors on real device.

**Time**: 4 hours

### Task 3.4: Auto-Calibration Wizard Backend

**File**: `msmacro/daemon_handlers/cv_commands.py`

Add click-to-calibrate functionality:

```python
async def object_detection_calibrate(self, msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Auto-calibrate HSV ranges from user clicks.

    Args:
        msg: {
            "frames": [base64_frame1, ...],  # 5 frames
            "clicks": [(x, y), ...]           # 5 click positions
        }

    Returns:
        {
            "hsv_lower": [h, s, v],
            "hsv_upper": [h, s, v],
            "preview_mask": base64_mask
        }
    """
    frames = [decode_base64_frame(f) for f in msg["frames"]]
    clicks = msg["clicks"]

    hsv_samples = []
    for frame, (x, y) in zip(frames, clicks):
        # Sample 3x3 region
        region = frame[max(0,y-1):y+2, max(0,x-1):x+2]
        hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        hsv_samples.extend(hsv_region.reshape(-1, 3))

    # Calculate percentile ranges
    hsv_array = np.array(hsv_samples)
    hsv_min = np.percentile(hsv_array, 5, axis=0)
    hsv_max = np.percentile(hsv_array, 95, axis=0)

    # Add 20% margin
    margin = (hsv_max - hsv_min) * 0.2
    hsv_lower = np.maximum(hsv_min - margin, [0, 0, 0])
    hsv_upper = np.minimum(hsv_max + margin, [179, 255, 255])

    # Generate preview mask
    preview_frame = frames[0]
    hsv_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv_frame, hsv_lower, hsv_upper)

    return {
        "hsv_lower": hsv_lower.astype(int).tolist(),
        "hsv_upper": hsv_upper.astype(int).tolist(),
        "preview_mask": encode_base64(mask)
    }
```

**Time**: 6 hours
**Test**: Send 5 frames + clicks, verify HSV ranges generated correctly

### Task 3.5: Lossless YUYV Frame Viewer

**File**: `msmacro/web/handlers.py`

Add endpoint for lossless PNG frame delivery:

```python
async def api_cv_frame_lossless(request: web.Request):
    """
    Serve latest frame as lossless PNG (not JPEG).
    For calibration UI to avoid compression artifacts.
    """
    try:
        capture = get_capture_instance()
        frame_bgr, metadata = capture.get_latest_frame()

        # Extract minimap region
        minimap = frame_bgr[56:142, 68:408]

        # Encode as PNG (lossless)
        success, png_bytes = cv2.imencode('.png', minimap)

        if not success:
            return web.Response(status=500, text="PNG encode failed")

        return web.Response(
            body=png_bytes.tobytes(),
            content_type="image/png",
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        return web.Response(status=500, text=str(e))
```

**Time**: 2 hours
**Test**: Access endpoint, verify PNG served correctly, check filesize ~50KB

### Task 3.6: Click-to-Calibrate Frontend

**File**: `webui/src/components/CalibrationWizard.jsx`

Interactive calibration wizard:

**Features**:
- Display live YUYV frame (lossless PNG)
- Zoom controls (200-400%)
- Click on player dot in 5 frames
- Show sampled pixels and calculated HSV ranges
- Preview detection mask overlay
- Export/save config

**Workflow**:
1. Load live frame from `/api/cv/frame-lossless`
2. User clicks player dot
3. Capture click position and frame
4. Repeat 5 times
5. Send to `/api/cv/object-detection/calibrate`
6. Display preview mask
7. User confirms or retries
8. Save config to Pi

**Time**: 8 hours
**Test**: Manual calibration on test Pi, verify HSV ranges work

### Task 3.7: Config Export/Import API

**File**: `msmacro/web/handlers.py`

```python
async def api_cv_detection_config_export(request: web.Request):
    """Export calibrated config as JSON."""
    config = load_detection_config()
    config["calibration_metadata"] = {
        "timestamp": time.time(),
        "device_id": get_device_id(),
        "version": "2.0"
    }
    return _json(config)

async def api_cv_detection_config_import(request: web.Request):
    """Import config JSON."""
    data = await request.json()

    # Validate schema
    required_keys = ["player", "other_players"]
    if not all(k in data for k in required_keys):
        return _json({"error": "Invalid config schema"}, 400)

    # Save config
    save_detection_config(data)

    # Reload detector
    capture = get_capture_instance()
    capture.reload_object_detection_config()

    return _json({"success": True})
```

**Time**: 2 hours
**Test**: Export config from test Pi, import to production Pi, verify detection works

### Task 3.8: Live Detection Validation Dashboard

**File**: `webui/src/components/ValidationDashboard.jsx`

Display real-time detection metrics:

**Metrics**:
- Detection rate (% of frames with player)
- Position stability (std deviation over 5s)
- Average confidence score
- Performance (latency ms)
- Alerts (red border if no detection >2s)

**Visualization**:
- Minimap stream with overlays
- Green circle: player (radius = confidence)
- Red circles: other players
- Position trace (last 30 positions)

**Time**: 6 hours
**Test**: Run detection, verify metrics update in real-time

### Phase 3 Deliverables Checklist

- [ ] Frontend page complete
- [ ] Real-time updates working
- [ ] Manual configuration UI functional (Task 3.3)
- [ ] Auto-calibration wizard working (Task 3.4-3.6)
- [ ] Config export/import functional (Task 3.7)
- [ ] Live validation dashboard (Task 3.8)
- [ ] Responsive design
- [ ] Error handling
- [ ] User documentation

---

## Phase 4: Playback Integration (Week 4)

### Task 4.1: Position Error Calculation

```python
def calculate_position_error(current: PlayerPosition, 
                             expected: PlayerPosition) -> Tuple[float, float]:
    """Calculate (dx, dy) error from expected position."""
    if not current.detected:
        return (0, 0)
    
    dx = current.x - expected.x
    dy = current.y - expected.y
    return (dx, dy)
```

### Task 4.2: Correction Keystroke Mapping

```python
def map_error_to_correction(dx: float, dy: float, 
                            threshold: float = 10.0) -> Optional[str]:
    """Map position error to correction keystroke."""
    distance = np.sqrt(dx**2 + dy**2)
    
    if distance < threshold:
        return None  # Within tolerance
    
    # Determine primary direction
    angle = np.arctan2(dy, dx)
    
    # Map to WASD keys
    if -np.pi/4 <= angle < np.pi/4:
        return "KEY_D"  # Right
    elif np.pi/4 <= angle < 3*np.pi/4:
        return "KEY_S"  # Down
    elif -3*np.pi/4 <= angle < -np.pi/4:
        return "KEY_W"  # Up
    else:
        return "KEY_A"  # Left
```

### Task 4.3: Inject Corrections During Playback

**File**: `msmacro/core/player.py`

Add position-based correction loop.

**Time**: 6 hours  
**Test**: Test with simple macros

### Phase 4 Deliverables Checklist

- [ ] Position error calculation working
- [ ] Correction mapping tested
- [ ] Playback integration complete
- [ ] Performance acceptable (< 150ms latency)
- [ ] Success rate > 80%
- [ ] Documentation complete

---

## Testing Strategy

### Two-Stage Testing Approach

**Stage 1: Algorithm Tests (JPEG - Development)**

Unit tests with JPEG fixtures (placeholder HSV ranges):

```python
def test_player_detection_jpeg():
    """Test player detection logic with JPEG (approximation)."""
    detector = MinimapObjectDetector()
    frame = cv2.imread("docus/archived/msmacro_cv_frame_object_recognize.jpg")

    result = detector.detect(frame)

    # Only test logic, not accuracy
    assert hasattr(result, 'player')
    assert hasattr(result.player, 'detected')
    # Color accuracy tested in Stage 2

def test_blob_filtering():
    """Test blob filtering logic."""
    # Mock contours, test circularity/size filtering
    # Verify correct blobs selected
```

**Stage 2: Calibration Tests (YUYV - Test Pi)**

Production accuracy tests with YUYV dataset:

```python
def test_yuyv_detection_accuracy():
    """Test detection accuracy on YUYV test dataset."""
    # Use scripts/validate_detection.py
    # Ground truth comparison
    # GATE: Must achieve >90% before deployment
```

### Integration Tests (Test Pi)

1. **Capture Loop Test**: Run detection with YUYV capture for 60 seconds
2. **Performance Test**: Measure CPU usage (< 3%), latency (< 15ms), frame drops (0)
3. **Stress Test**: Run with high CPU load, verify stability
4. **API Test**: Test all endpoints including calibration wizard
5. **24-Hour Stability**: Continuous operation, no memory leaks

### Acceptance Criteria (YUYV on Test Pi)

**CRITICAL GATE - Must pass before production deployment:**

- [ ] Player detection precision > 90% (on YUYV test dataset)
- [ ] Player detection recall > 85%
- [ ] Position error < 5 pixels average
- [ ] Other players detection precision > 85%
- [ ] Other players detection recall > 80%
- [ ] Latency < 15ms per detection (Pi 4)
- [ ] CPU overhead < 3% (11-14ms per 500ms)
- [ ] No frame drops during detection
- [ ] API responses < 100ms
- [ ] UI updates < 500ms
- [ ] Calibration wizard functional
- [ ] Config export/import working
- [ ] 24-hour stability test passed

---

## Risk Management

### Risk 1: JPEG vs YUYV Color Mismatch
**Problem**: Development with JPEG images, production uses YUYV
**Mitigation**:
- Clear documentation: JPEG HSV values are placeholders
- Phase 0 creates YUYV test dataset before algorithm development
- Auto-calibration wizard simplifies YUYV tuning
- Validation gate requires >90% accuracy on YUYV before deployment

### Risk 2: Remote Calibration UX Difficulty
**Problem**: No monitor on Pi, must calibrate via web UI
**Mitigation**:
- Lossless PNG frame viewer (not compressed JPEG)
- Zoom controls (200-400%) for precise clicking
- Auto-calibration wizard (click 5 times, system generates HSV)
- Live preview of detection mask before saving
- Thorough user documentation with screenshots

### Risk 3: Performance Impact on Pi 4
**Mitigation**:
- Crop minimap BEFORE color conversion (saves 7ms)
- Skip frame detection if needed (500ms headroom available)
- Adaptive quality: disable preprocessing if CPU > 80%
- Continuous performance monitoring in validation dashboard

### Risk 4: False Positives/Negatives
**Mitigation**:
- Temporal filtering (exponential moving average)
- Confidence thresholds (circularity > 0.6)
- Ground truth validation (require >90% accuracy)
- Live validation dashboard for monitoring

### Risk 5: Test Pi Availability
**Problem**: Need separate Pi for testing/calibration
**Mitigation**:
- Document requirement in Phase 0
- Can use same hardware as production (swap SD cards)
- Calibration is one-time (export config for reuse)
- Support config import from another Pi

---

## Success Criteria

### Functional (YUYV on Test Pi)
- [ ] Detects player position with >90% precision, >85% recall
- [ ] Position error < 5 pixels average
- [ ] Detects other players with >85% precision, >80% recall
- [ ] Returns position in < 15ms (YUYV on Pi 4)
- [ ] Integrates with capture loop without errors
- [ ] API endpoints functional (including calibration)
- [ ] UI displays real-time updates
- [ ] Click-to-calibrate wizard works remotely
- [ ] Config export/import functional

### Performance (Pi 4 with YUYV)
- [ ] CPU overhead < 3% (11-14ms per 500ms cycle)
- [ ] No frame drops (maintain 2 FPS capture)
- [ ] Latency < 15ms per detection
- [ ] End-to-end latency < 200ms (detection + IPC + action)
- [ ] Memory stable (no leaks over 24 hours)

### Usability
- [ ] Remote calibration via web UI (no monitor needed)
- [ ] Auto-calibration wizard simplifies HSV tuning
- [ ] Config export/import between test and production Pi
- [ ] Live validation dashboard shows metrics
- [ ] Real-time visualization of detection
- [ ] Clear documentation with YUYV workflow
- [ ] Error messages helpful and actionable

---

**Document Version**: 2.0
**Last Updated**: 2025-01-08
**Status**: Planning Complete - Updated for YUYV Production Reality
**Key Changes in v2.0**:
- Added Phase 0: Test Pi setup and YUYV dataset creation
- Updated for YUYV color space (not JPEG)
- Expanded Phase 3 with remote calibration UI tasks (3.4-3.8)
- Revised performance targets (< 15ms on Pi 4, 3% CPU)
- Updated testing strategy for two-stage approach (JPEG dev → YUYV calibration)
- Added YUYV-specific acceptance criteria

**Next Action**:
1. Complete Phase 0 on test Pi (dataset creation, ground truth annotation)
2. Begin Phase 1 implementation with placeholder HSV ranges
3. Deploy to test Pi for Phase 2 calibration
