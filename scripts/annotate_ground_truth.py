#!/usr/bin/env python3
"""
Manual ground truth annotation tool for YUYV test dataset.

This interactive tool allows you to manually annotate player and other player
positions in captured frames. The annotations are used for validation testing.

Usage:
    python scripts/annotate_ground_truth.py --dataset data/yuyv_test_set/

Controls:
    - Click: Mark player position (yellow)
    - Shift+Click: Mark other player position (red)
    - 'n': Next frame (saves current annotations)
    - 'p': Previous frame
    - 'c': Clear current frame annotations
    - 's': Save annotations to disk
    - 'q' or ESC: Save and quit
    - '=' or '+': Zoom in
    - '-': Zoom out
    - '0': Reset zoom
"""

import argparse
import sys
from pathlib import Path
import json
import cv2
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class AnnotationTool:
    """Interactive ground truth annotation tool."""

    def __init__(self, dataset_dir: Path):
        """
        Initialize annotation tool.

        Args:
            dataset_dir: Path to directory containing .npy frames
        """
        self.dataset_dir = dataset_dir
        self.frames = sorted(dataset_dir.glob("*.npy"))

        if not self.frames:
            raise ValueError(f"No .npy files found in {dataset_dir}")

        self.current_idx = 0
        self.annotations = {}
        self.zoom = 2.0  # Default 2x zoom for easier clicking

        # Current frame annotations
        self.player_click = None  # (x, y) or None
        self.other_clicks = []    # List of (x, y)

        # Window setup
        self.window_name = "Ground Truth Annotation"

        # Load existing annotations if they exist
        self.gt_path = dataset_dir / "ground_truth.json"
        self._load_annotations()

        print(f"\nAnnotation Tool Initialized")
        print(f"  Dataset: {dataset_dir}")
        print(f"  Frames: {len(self.frames)}")
        print(f"  Existing annotations: {len(self.annotations)}")

    def _load_annotations(self):
        """Load existing annotations from JSON file."""
        if self.gt_path.exists():
            try:
                with open(self.gt_path, 'r') as f:
                    self.annotations = json.load(f)
                print(f"  ✓ Loaded {len(self.annotations)} existing annotations")
            except Exception as e:
                print(f"  ⚠️  Failed to load existing annotations: {e}")
                self.annotations = {}
        else:
            self.annotations = {}

    def _save_annotations(self):
        """Save all annotations to JSON file."""
        try:
            with open(self.gt_path, 'w') as f:
                json.dump(self.annotations, f, indent=2)
            print(f"\n✓ Saved {len(self.annotations)} annotations to {self.gt_path}")
            return True
        except Exception as e:
            print(f"\n❌ Failed to save annotations: {e}")
            return False

    def _load_current_frame(self):
        """Load current frame and its existing annotations."""
        frame_path = self.frames[self.current_idx]

        # Load frame
        frame = np.load(str(frame_path))

        # Load existing annotations for this frame
        frame_name = frame_path.name
        if frame_name in self.annotations:
            ann = self.annotations[frame_name]
            self.player_click = tuple(ann.get("player")) if ann.get("player") else None
            self.other_clicks = [tuple(p) for p in ann.get("other_players", [])]
        else:
            self.player_click = None
            self.other_clicks = []

        return frame

    def _save_current_annotation(self):
        """Save current frame annotations to dictionary."""
        frame_name = self.frames[self.current_idx].name

        annotation = {
            "player": list(self.player_click) if self.player_click else None,
            "other_players": [list(p) for p in self.other_clicks]
        }

        self.annotations[frame_name] = annotation

    def _draw_annotations(self, frame):
        """Draw current annotations on frame."""
        vis = frame.copy()

        # Scale for zoom
        if self.zoom != 1.0:
            h, w = vis.shape[:2]
            new_w = int(w * self.zoom)
            new_h = int(h * self.zoom)
            vis = cv2.resize(vis, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

        # Draw player
        if self.player_click:
            x, y = self.player_click
            x_scaled = int(x * self.zoom)
            y_scaled = int(y * self.zoom)

            # Crosshair
            cv2.drawMarker(vis, (x_scaled, y_scaled), (0, 255, 255),
                          markerType=cv2.MARKER_CROSS,
                          markerSize=int(15 * self.zoom), thickness=2)
            # Circle
            cv2.circle(vis, (x_scaled, y_scaled), int(10 * self.zoom), (0, 255, 255), 2)
            # Label
            cv2.putText(vis, f"Player ({x},{y})",
                       (x_scaled + int(12 * self.zoom), y_scaled - int(12 * self.zoom)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5 * self.zoom, (0, 255, 255), max(1, int(self.zoom)))

        # Draw other players
        for i, (x, y) in enumerate(self.other_clicks):
            x_scaled = int(x * self.zoom)
            y_scaled = int(y * self.zoom)

            cv2.circle(vis, (x_scaled, y_scaled), int(8 * self.zoom), (0, 0, 255), 2)
            cv2.putText(vis, f"Other {i+1}",
                       (x_scaled + int(10 * self.zoom), y_scaled - int(10 * self.zoom)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4 * self.zoom, (0, 0, 255), max(1, int(self.zoom)))

        return vis

    def _draw_ui(self, frame):
        """Draw UI elements (instructions, status)."""
        vis = self._draw_annotations(frame)

        # Instructions panel (scaled for zoom)
        instructions = [
            "Controls:",
            "  Click: Player (yellow)",
            "  Shift+Click: Other players (red)",
            "  n: Next | p: Previous | c: Clear",
            "  s: Save | q/ESC: Save & Quit",
            "  +/-: Zoom | 0: Reset Zoom",
            "",
            f"Frame: {self.current_idx + 1}/{len(self.frames)}",
            f"Zoom: {self.zoom:.1f}x",
            f"Player: {'✓' if self.player_click else '✗'}",
            f"Others: {len(self.other_clicks)}",
            f"Total annotated: {len(self.annotations)}/{len(self.frames)}"
        ]

        y_offset = int(15 * self.zoom)
        for i, text in enumerate(instructions):
            cv2.putText(vis, text,
                       (int(10 * self.zoom), y_offset + i * int(18 * self.zoom)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4 * self.zoom,
                       (255, 255, 255), max(1, int(self.zoom)))

        return vis

    def _mouse_callback(self, event, x, y, flags, param):
        """Handle mouse clicks."""
        if event == cv2.EVENT_LBUTTONDOWN:
            # Convert click coordinates back to original scale
            x_orig = int(x / self.zoom)
            y_orig = int(y / self.zoom)

            if flags & cv2.EVENT_FLAG_SHIFT:
                # Shift+Click: Add other player
                self.other_clicks.append((x_orig, y_orig))
                print(f"  Added other player at ({x_orig}, {y_orig})")
            else:
                # Click: Set player position
                self.player_click = (x_orig, y_orig)
                print(f"  Set player at ({x_orig}, {y_orig})")

    def run(self):
        """Run interactive annotation loop."""
        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self._mouse_callback)

        print("\n" + "="*70)
        print("STARTING ANNOTATION")
        print("="*70)
        print("\nControls:")
        print("  - Click: Mark player position (yellow)")
        print("  - Shift+Click: Mark other player (red)")
        print("  - 'n': Next frame")
        print("  - 'p': Previous frame")
        print("  - 'c': Clear current annotations")
        print("  - 's': Save to disk")
        print("  - 'q' or ESC: Save and quit")
        print("  - '=' or '+': Zoom in")
        print("  - '-': Zoom out")
        print("  - '0': Reset zoom")
        print("="*70 + "\n")

        while True:
            # Load and display current frame
            frame = self._load_current_frame()
            vis = self._draw_ui(frame)
            cv2.imshow(self.window_name, vis)

            # Handle key press
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == 27:  # Q or ESC
                self._save_current_annotation()
                self._save_annotations()
                break

            elif key == ord('n'):  # Next
                self._save_current_annotation()
                if self.current_idx < len(self.frames) - 1:
                    self.current_idx += 1
                    print(f"\nFrame {self.current_idx + 1}/{len(self.frames)}: {self.frames[self.current_idx].name}")
                else:
                    print("\n⚠️  Already at last frame")

            elif key == ord('p'):  # Previous
                self._save_current_annotation()
                if self.current_idx > 0:
                    self.current_idx -= 1
                    print(f"\nFrame {self.current_idx + 1}/{len(self.frames)}: {self.frames[self.current_idx].name}")
                else:
                    print("\n⚠️  Already at first frame")

            elif key == ord('c'):  # Clear
                self.player_click = None
                self.other_clicks = []
                print("  Cleared annotations for current frame")

            elif key == ord('s'):  # Save
                self._save_current_annotation()
                if self._save_annotations():
                    print(f"  Progress: {len(self.annotations)}/{len(self.frames)} frames annotated")

            elif key == ord('=') or key == ord('+'):  # Zoom in
                self.zoom = min(self.zoom + 0.5, 5.0)
                print(f"  Zoom: {self.zoom:.1f}x")

            elif key == ord('-'):  # Zoom out
                self.zoom = max(self.zoom - 0.5, 1.0)
                print(f"  Zoom: {self.zoom:.1f}x")

            elif key == ord('0'):  # Reset zoom
                self.zoom = 2.0
                print(f"  Zoom reset: {self.zoom:.1f}x")

        cv2.destroyAllWindows()

        # Final summary
        print("\n" + "="*70)
        print("ANNOTATION COMPLETE")
        print("="*70)
        print(f"  Total frames: {len(self.frames)}")
        print(f"  Annotated: {len(self.annotations)}")
        print(f"  Completion: {(len(self.annotations) / len(self.frames)) * 100:.1f}%")
        print(f"  Output: {self.gt_path}")
        print("\nNext Steps:")
        print(f"  python scripts/validate_detection.py --dataset {self.dataset_dir}")
        print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Interactive ground truth annotation tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to dataset directory containing .npy files"
    )

    args = parser.parse_args()

    if not args.dataset.is_dir():
        print(f"ERROR: Dataset directory not found: {args.dataset}")
        return 1

    try:
        tool = AnnotationTool(args.dataset)
        tool.run()
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
