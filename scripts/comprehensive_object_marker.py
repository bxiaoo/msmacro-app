#!/usr/bin/env python3
"""
Comprehensive Minimap Object Marker for Multi-Modal Detection Development

A comprehensive GUI tool for annotating minimap objects with multiple characteristics
and testing multi-modal detection algorithms (HSV color, Hough circles, edge detection).

Features:
- Load minimap images (PNG/JPEG/NPY)
- Multi-mode marking: Position, Region, Comprehensive characteristics
- Real-time detection preview with multiple methods
- Interactive parameter tuning
- HSV sampling at marked positions
- Side-by-side ground truth comparison
- Export annotations and calibration data

Keyboard Controls:
- Tab:          Cycle marking modes
- Left-click:   Mark player/object (mode-dependent)
- Right-click:  Mark enemy/other object
- Space:        Sample HSV at cursor
- Delete/Back:  Remove nearest marker
- 'r':          Reset all markers
- 's':          Save annotations
- 'c':          Auto-calibrate from markers
- 'h':          Toggle Hough circles
- 'e':          Toggle edge detection
- 't':          Toggle detection method tabs
- 'q'/Esc:      Quit

Usage:
    python scripts/comprehensive_object_marker.py --image minimap.png
    python scripts/comprehensive_object_marker.py --directory samples/
    python scripts/comprehensive_object_marker.py --image minimap.npy --live-detector
"""

import sys
import argparse
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np

# Import existing detector
try:
    from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig
    from msmacro.cv.detection_config import load_config, save_config
    HAS_DETECTOR = True
except ImportError:
    HAS_DETECTOR = False
    print("Warning: Could not import msmacro detector, some features disabled")


class MarkingMode(Enum):
    """Marking modes for different levels of detail."""
    POSITION = "Position"  # Simple x,y marking
    REGION = "Region"  # Bounding box + shape
    COMPREHENSIVE = "Comprehensive"  # Full characteristics


class ObjectType(Enum):
    """Types of objects that can be marked."""
    PLAYER = "player"
    ENEMY = "enemy"
    NPC = "npc"
    PORTAL = "portal"
    MARKER = "marker"
    OTHER = "other"


@dataclass
class ObjectAnnotation:
    """Comprehensive annotation for a single object."""
    # Core identification
    type: str  # ObjectType
    id: int  # Unique ID

    # Spatial characteristics
    x: int
    y: int
    width: Optional[int] = None
    height: Optional[int] = None
    radius: Optional[float] = None

    # Visual - Color (HSV at center)
    hsv_h: Optional[int] = None
    hsv_s: Optional[int] = None
    hsv_v: Optional[int] = None

    # Visual - Shape
    shape: str = "circle"  # circle, rectangle, polygon, irregular
    circularity: Optional[float] = None
    aspect_ratio: Optional[float] = None

    # Visual - Texture/Structure
    has_border: bool = False
    border_color: Optional[Tuple[int, int, int]] = None
    border_thickness: Optional[int] = None
    edge_strength: Optional[float] = None

    # Detection confidence (if from auto-detection)
    confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class ComprehensiveMarker:
    """Main application for comprehensive object marking."""

    def __init__(self, image_path: str, live_detector: bool = False):
        self.image_path = Path(image_path)
        self.image = self._load_image()
        if self.image is None:
            raise ValueError(f"Could not load image: {image_path}")

        self.original = self.image.copy()
        self.h, self.w = self.image.shape[:2]

        # Marking state
        self.mode = MarkingMode.POSITION
        self.annotations: List[ObjectAnnotation] = []
        self.next_id = 1
        self.current_type = ObjectType.PLAYER

        # Visual state
        self.zoom = 2.0
        self.show_hough = False
        self.show_edge = False
        self.show_detection = True
        self.detection_method = "hsv"  # hsv, hough, edge, combined

        # Detector (if available)
        self.detector = None
        self.detector_config = None
        if HAS_DETECTOR and live_detector:
            try:
                self.detector_config = load_config()
                self.detector = MinimapObjectDetector(self.detector_config)
            except:
                pass

        # UI windows
        self.window_name = "Comprehensive Object Marker"
        self.help_shown = False

        # Mouse state
        self.mouse_pos = (0, 0)
        self.drawing_box = False
        self.box_start = None

    def _load_image(self) -> Optional[np.ndarray]:
        """Load image from file (PNG/JPEG/NPY)."""
        path = self.image_path

        if path.suffix.lower() == '.npy':
            # Load numpy array
            arr = np.load(str(path))
            if arr.ndim == 2:
                # Grayscale, convert to BGR
                return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
            return arr
        else:
            # Load image file
            img = cv2.imread(str(path))
            return img

    def _sample_hsv(self, x: int, y: int, size: int = 3) -> Tuple[int, int, int]:
        """Sample HSV values at a point (average of size×size region)."""
        # Ensure within bounds
        x1 = max(0, x - size // 2)
        y1 = max(0, y - size // 2)
        x2 = min(self.w, x + size // 2 + 1)
        y2 = min(self.h, y + size // 2 + 1)

        # Extract region and convert to HSV
        region = self.original[y1:y2, x1:x2]
        if region.size == 0:
            return (0, 0, 0)

        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        # Average HSV values
        h_mean = int(np.mean(hsv[:, :, 0]))
        s_mean = int(np.mean(hsv[:, :, 1]))
        v_mean = int(np.mean(hsv[:, :, 2]))

        return (h_mean, s_mean, v_mean)

    def _calculate_circularity(self, contour) -> float:
        """Calculate circularity of a contour (4π × area / perimeter²)."""
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            return 0.0
        return (4 * np.pi * area) / (perimeter ** 2)

    def _detect_with_hough(self, gray: np.ndarray) -> List[Tuple[int, int, int]]:
        """Detect circles using Hough transform."""
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT,
            dp=1, minDist=10,
            param1=50, param2=15,
            minRadius=2, maxRadius=16
        )

        if circles is not None:
            circles = np.uint16(np.around(circles))
            return [(x, y, r) for x, y, r in circles[0, :]]
        return []

    def _detect_with_edge(self, gray: np.ndarray) -> np.ndarray:
        """Detect edges using Canny."""
        edges = cv2.Canny(gray, 50, 150)
        return edges

    def _detect_with_hsv(self) -> List[Dict]:
        """Run HSV-based detection using loaded detector."""
        if self.detector is None:
            return []

        try:
            result = self.detector.detect(self.original)
            detected = []

            if result.player.detected:
                detected.append({
                    'type': 'player',
                    'x': result.player.x,
                    'y': result.player.y,
                    'confidence': result.player.confidence
                })

            for i, (x, y) in enumerate(result.other_players.positions):
                detected.append({
                    'type': 'enemy',
                    'x': x,
                    'y': y,
                    'confidence': 0.8  # Default confidence
                })

            return detected
        except:
            return []

    def _draw_visualization(self) -> np.ndarray:
        """Draw the main visualization with annotations and detection results."""
        vis = self.original.copy()

        # Draw detection results if enabled
        if self.show_detection:
            if self.detection_method == "hough" or self.show_hough:
                gray = cv2.cvtColor(self.original, cv2.COLOR_BGR2GRAY)
                circles = self._detect_with_hough(gray)
                for (x, y, r) in circles:
                    cv2.circle(vis, (x, y), r, (0, 255, 255), 1)  # Cyan circles
                    cv2.circle(vis, (x, y), 1, (0, 255, 255), -1)

            if self.detection_method == "hsv":
                detected = self._detect_with_hsv()
                for obj in detected:
                    color = (0, 255, 0) if obj['type'] == 'player' else (0, 0, 255)
                    cv2.drawMarker(vis, (obj['x'], obj['y']), color,
                                 cv2.MARKER_CROSS, 10, 2)

        # Draw edge detection overlay if enabled
        if self.show_edge:
            gray = cv2.cvtColor(self.original, cv2.COLOR_BGR2GRAY)
            edges = self._detect_with_edge(gray)
            # Overlay edges in cyan
            vis[edges > 0] = [255, 255, 0]

        # Draw manual annotations
        for ann in self.annotations:
            if ann.type == ObjectType.PLAYER.value:
                color = (0, 255, 255)  # Yellow
                marker_type = cv2.MARKER_CROSS
            elif ann.type == ObjectType.ENEMY.value:
                color = (0, 0, 255)  # Red
                marker_type = cv2.MARKER_TILTED_CROSS
            else:
                color = (255, 0, 255)  # Magenta
                marker_type = cv2.MARKER_STAR

            # Draw marker at position
            cv2.drawMarker(vis, (ann.x, ann.y), color, marker_type, 15, 2)

            # Draw bounding box if available
            if ann.width and ann.height:
                x1 = ann.x - ann.width // 2
                y1 = ann.y - ann.height // 2
                cv2.rectangle(vis, (x1, y1), (x1 + ann.width, y1 + ann.height),
                            color, 1)

            # Draw circle if radius available
            if ann.radius:
                cv2.circle(vis, (ann.x, ann.y), int(ann.radius), color, 1)

            # Draw ID label
            cv2.putText(vis, f"#{ann.id}", (ann.x + 10, ann.y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # Draw current mouse position HSV if hovering
        if self.mouse_pos != (0, 0):
            mx, my = self.mouse_pos
            if 0 <= mx < self.w and 0 <= my < self.h:
                h, s, v = self._sample_hsv(mx, my)
                hsv_text = f"HSV: ({h}, {s}, {v})"
                cv2.putText(vis, hsv_text, (mx + 15, my),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                cv2.circle(vis, (mx, my), 3, (255, 255, 255), 1)

        # Draw mode and status
        mode_text = f"Mode: {self.mode.value} | Type: {self.current_type.value}"
        cv2.putText(vis, mode_text, (10, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        status_text = f"Markers: {len(self.annotations)}"
        cv2.putText(vis, status_text, (10, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        method_text = f"Detection: {self.detection_method.upper()}"
        cv2.putText(vis, method_text, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Scale for display
        if self.zoom != 1.0:
            new_w = int(self.w * self.zoom)
            new_h = int(self.h * self.zoom)
            vis = cv2.resize(vis, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        return vis

    def _show_help(self):
        """Display help overlay."""
        help_text = [
            "COMPREHENSIVE OBJECT MARKER - HELP",
            "",
            "MOUSE CONTROLS:",
            "  Left-click:   Mark player/object",
            "  Right-click:  Mark enemy",
            "  Space:        Sample HSV at cursor",
            "",
            "KEYBOARD CONTROLS:",
            "  Tab:      Cycle marking modes",
            "  Delete:   Remove nearest marker",
            "  'r':      Reset all markers",
            "  's':      Save annotations",
            "  'c':      Auto-calibrate",
            "  'h':      Toggle Hough circles",
            "  'e':      Toggle edge detection",
            "  't':      Toggle detection method",
            "  'q'/Esc:  Quit",
            "",
            "MODES:",
            f"  {MarkingMode.POSITION.value}:      Simple x,y marking",
            f"  {MarkingMode.REGION.value}:        Bounding box + shape",
            f"  {MarkingMode.COMPREHENSIVE.value}: Full characteristics",
            "",
            "Press 'h' to close this help"
        ]

        # Create help overlay
        help_img = np.zeros((len(help_text) * 25 + 40, 600, 3), dtype=np.uint8)
        for i, line in enumerate(help_text):
            cv2.putText(help_img, line, (20, 30 + i * 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow("Help", help_img)

    def _mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events."""
        # Adjust for zoom
        x = int(x / self.zoom)
        y = int(y / self.zoom)

        # Update mouse position
        self.mouse_pos = (x, y)

        if event == cv2.EVENT_LBUTTONDOWN:
            # Mark player/object
            h, s, v = self._sample_hsv(x, y)
            ann = ObjectAnnotation(
                type=self.current_type.value,
                id=self.next_id,
                x=x,
                y=y,
                hsv_h=h,
                hsv_s=s,
                hsv_v=v
            )
            self.annotations.append(ann)
            self.next_id += 1
            print(f"Added {self.current_type.value} at ({x}, {y}), HSV=({h},{s},{v})")

        elif event == cv2.EVENT_RBUTTONDOWN:
            # Mark enemy
            h, s, v = self._sample_hsv(x, y)
            ann = ObjectAnnotation(
                type=ObjectType.ENEMY.value,
                id=self.next_id,
                x=x,
                y=y,
                hsv_h=h,
                hsv_s=s,
                hsv_v=v
            )
            self.annotations.append(ann)
            self.next_id += 1
            print(f"Added enemy at ({x}, {y}), HSV=({h},{s},{v})")

    def _remove_nearest_marker(self, x: int, y: int):
        """Remove the marker closest to (x, y)."""
        if not self.annotations:
            return

        # Find nearest
        min_dist = float('inf')
        nearest_idx = -1

        for i, ann in enumerate(self.annotations):
            dist = np.sqrt((ann.x - x)**2 + (ann.y - y)**2)
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i

        if nearest_idx >= 0 and min_dist < 20:  # Within 20 pixels
            removed = self.annotations.pop(nearest_idx)
            print(f"Removed marker #{removed.id} at ({removed.x}, {removed.y})")

    def _auto_calibrate(self):
        """Auto-calibrate HSV ranges from marked objects."""
        if not self.annotations:
            print("No markers to calibrate from!")
            return

        # Separate by type
        player_hsv = []
        enemy_hsv = []

        for ann in self.annotations:
            if ann.hsv_h is not None:
                hsv = (ann.hsv_h, ann.hsv_s, ann.hsv_v)
                if ann.type == ObjectType.PLAYER.value:
                    player_hsv.append(hsv)
                elif ann.type == ObjectType.ENEMY.value:
                    enemy_hsv.append(hsv)

        print("\n=== AUTO-CALIBRATION RESULTS ===")

        if player_hsv:
            player_hsv = np.array(player_hsv)
            h_mean, s_mean, v_mean = player_hsv.mean(axis=0)
            h_std, s_std, v_std = player_hsv.std(axis=0)

            # Calculate ranges (mean ± 2σ, clamped)
            h_min = max(0, int(h_mean - 2 * h_std))
            h_max = min(179, int(h_mean + 2 * h_std))
            s_min = max(0, int(s_mean - 2 * s_std))
            s_max = min(255, int(s_mean + 2 * s_std))
            v_min = max(0, int(v_mean - 2 * v_std))
            v_max = min(255, int(v_mean + 2 * v_std))

            print(f"\nPlayer (yellow) - {len(player_hsv)} samples:")
            print(f"  Mean HSV: ({h_mean:.1f}, {s_mean:.1f}, {v_mean:.1f})")
            print(f"  Std  HSV: ({h_std:.1f}, {s_std:.1f}, {v_std:.1f})")
            print(f"  Calibrated range:")
            print(f"    H: {h_min} - {h_max}")
            print(f"    S: {s_min} - {s_max}")
            print(f"    V: {v_min} - {v_max}")

        if enemy_hsv:
            enemy_hsv = np.array(enemy_hsv)
            h_mean, s_mean, v_mean = enemy_hsv.mean(axis=0)
            h_std, s_std, v_std = enemy_hsv.std(axis=0)

            h_min = max(0, int(h_mean - 2 * h_std))
            h_max = min(179, int(h_mean + 2 * h_std))
            s_min = max(0, int(s_mean - 2 * s_std))
            s_max = min(255, int(s_mean + 2 * s_std))
            v_min = max(0, int(v_mean - 2 * v_std))
            v_max = min(255, int(v_mean + 2 * v_std))

            print(f"\nEnemy (red) - {len(enemy_hsv)} samples:")
            print(f"  Mean HSV: ({h_mean:.1f}, {s_mean:.1f}, {v_mean:.1f})")
            print(f"  Std  HSV: ({h_std:.1f}, {s_std:.1f}, {v_std:.1f})")
            print(f"  Calibrated range:")
            print(f"    H: {h_min} - {h_max}")
            print(f"    S: {s_min} - {s_max}")
            print(f"    V: {v_min} - {v_max}")

    def _save_annotations(self):
        """Save annotations to JSON file."""
        output_path = self.image_path.with_suffix('.annotations.json')

        data = {
            'image': str(self.image_path),
            'image_size': {'width': self.w, 'height': self.h},
            'mode': self.mode.value,
            'annotations': [ann.to_dict() for ann in self.annotations],
            'count': {
                'player': sum(1 for a in self.annotations if a.type == ObjectType.PLAYER.value),
                'enemy': sum(1 for a in self.annotations if a.type == ObjectType.ENEMY.value),
                'total': len(self.annotations)
            }
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n✅ Saved {len(self.annotations)} annotations to: {output_path}")

    def run(self):
        """Run the interactive marker application."""
        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self._mouse_callback)

        print("\n" + "=" * 60)
        print("COMPREHENSIVE OBJECT MARKER")
        print("=" * 60)
        print(f"Image: {self.image_path}")
        print(f"Size: {self.w}×{self.h}")
        print(f"Mode: {self.mode.value}")
        print("\nPress 'h' for help")
        print("=" * 60)

        while True:
            # Draw visualization
            vis = self._draw_visualization()
            cv2.imshow(self.window_name, vis)

            # Handle keyboard
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == 27:  # Q or Esc
                break
            elif key == ord('h'):
                if self.help_shown:
                    cv2.destroyWindow("Help")
                    self.help_shown = False
                else:
                    self._show_help()
                    self.help_shown = True
            elif key == ord('\t') or key == 9:  # Tab
                modes = list(MarkingMode)
                current_idx = modes.index(self.mode)
                self.mode = modes[(current_idx + 1) % len(modes)]
                print(f"Mode: {self.mode.value}")
            elif key == ord('r'):
                self.annotations.clear()
                self.next_id = 1
                print("Reset all markers")
            elif key == 8 or key == 127:  # Delete/Backspace
                mx, my = self.mouse_pos
                self._remove_nearest_marker(mx, my)
            elif key == ord('s'):
                self._save_annotations()
            elif key == ord('c'):
                self._auto_calibrate()
            elif key == ord('e'):
                self.show_edge = not self.show_edge
                print(f"Edge detection: {'ON' if self.show_edge else 'OFF'}")
            elif key == ord('t'):
                methods = ['hsv', 'hough', 'edge', 'combined']
                current_idx = methods.index(self.detection_method)
                self.detection_method = methods[(current_idx + 1) % len(methods)]
                print(f"Detection method: {self.detection_method.upper()}")
            elif key == ord(' '):
                mx, my = self.mouse_pos
                if 0 <= mx < self.w and 0 <= my < self.h:
                    h, s, v = self._sample_hsv(mx, my)
                    print(f"Sampled HSV at ({mx}, {my}): H={h}, S={s}, V={v}")

        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description='Comprehensive Object Marker')
    parser.add_argument('--image', required=True, help='Minimap image file (PNG/JPEG/NPY)')
    parser.add_argument('--live-detector', action='store_true',
                       help='Enable live HSV detector preview')
    args = parser.parse_args()

    try:
        marker = ComprehensiveMarker(args.image, args.live_detector)
        marker.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
