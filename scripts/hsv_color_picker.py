#!/usr/bin/env python3
"""
Interactive HSV color range picker for object detection calibration.

Usage:
    python scripts/hsv_color_picker.py --image /path/to/minimap.jpg
    
Controls:
    - Adjust trackbars to tune HSV ranges
    - Press 's' to save current ranges to config file
    - Press 'r' to reset to default ranges
    - Press 'q' or ESC to quit
"""

import argparse
import sys
from pathlib import Path
import cv2
import numpy as np
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class HSVColorPicker:
    """Interactive HSV range picker tool."""
    
    def __init__(self, image_path: Path):
        """
        Initialize picker with image.
        
        Args:
            image_path: Path to image file
        """
        self.image_path = image_path
        self.frame = cv2.imread(str(image_path))
        
        if self.frame is None:
            raise ValueError(f"Could not read image: {image_path}")
        
        self.hsv_frame = cv2.cvtColor(self.frame, cv2.COLOR_BGR2HSV)
        
        # Default ranges (placeholders)
        self.h_min = 20
        self.h_max = 30
        self.s_min = 100
        self.s_max = 255
        self.v_min = 100
        self.v_max = 255
        
        # Window name
        self.window_name = "HSV Color Picker"
        
    def create_window(self):
        """Create window with trackbars."""
        cv2.namedWindow(self.window_name)
        
        # Create trackbars
        cv2.createTrackbar("H Min", self.window_name, self.h_min, 179, self._on_trackbar)
        cv2.createTrackbar("H Max", self.window_name, self.h_max, 179, self._on_trackbar)
        cv2.createTrackbar("S Min", self.window_name, self.s_min, 255, self._on_trackbar)
        cv2.createTrackbar("S Max", self.window_name, self.s_max, 255, self._on_trackbar)
        cv2.createTrackbar("V Min", self.window_name, self.v_min, 255, self._on_trackbar)
        cv2.createTrackbar("V Max", self.window_name, self.v_max, 255, self._on_trackbar)
    
    def _on_trackbar(self, value):
        """Trackbar callback."""
        pass  # Update happens in run loop
    
    def _get_current_ranges(self):
        """Get current HSV ranges from trackbars."""
        self.h_min = cv2.getTrackbarPos("H Min", self.window_name)
        self.h_max = cv2.getTrackbarPos("H Max", self.window_name)
        self.s_min = cv2.getTrackbarPos("S Min", self.window_name)
        self.s_max = cv2.getTrackbarPos("S Max", self.window_name)
        self.v_min = cv2.getTrackbarPos("V Min", self.window_name)
        self.v_max = cv2.getTrackbarPos("V Max", self.window_name)
        
        return (self.h_min, self.s_min, self.v_min), (self.h_max, self.s_max, self.v_max)
    
    def _create_mask(self, hsv_lower, hsv_upper):
        """Create binary mask from HSV ranges."""
        lower = np.array(hsv_lower, dtype=np.uint8)
        upper = np.array(hsv_upper, dtype=np.uint8)
        mask = cv2.inRange(self.hsv_frame, lower, upper)
        
        # Apply morphological operations
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        return mask
    
    def _visualize(self, mask):
        """Create visualization image."""
        # Convert mask to color
        mask_color = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        
        # Apply mask to original image
        masked = cv2.bitwise_and(self.frame, self.frame, mask=mask)
        
        # Stack images: original | mask | masked
        height = self.frame.shape[0]
        width = self.frame.shape[1]
        
        # Resize for display if too large
        max_width = 400
        if width > max_width:
            scale = max_width / width
            width = int(width * scale)
            height = int(height * scale)
            original = cv2.resize(self.frame, (width, height))
            mask_color = cv2.resize(mask_color, (width, height))
            masked = cv2.resize(masked, (width, height))
        else:
            original = self.frame.copy()
        
        # Add labels
        cv2.putText(original, "Original", (10, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(mask_color, "Mask", (10, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(masked, "Result", (10, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Stack horizontally
        vis = np.hstack([original, mask_color, masked])
        
        # Add instructions
        instructions = [
            "Controls:",
            "  's' = Save ranges",
            "  'r' = Reset",
            "  'q'/ESC = Quit"
        ]
        
        y_offset = vis.shape[0] - 80
        for i, text in enumerate(instructions):
            cv2.putText(vis, text, (10, y_offset + i*20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Add current ranges
        hsv_lower, hsv_upper = self._get_current_ranges()
        range_text = f"HSV: [{hsv_lower[0]}-{hsv_upper[0]}, {hsv_lower[1]}-{hsv_upper[1]}, {hsv_lower[2]}-{hsv_upper[2]}]"
        cv2.putText(vis, range_text, (10, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        
        return vis
    
    def save_ranges(self, output_file: Path):
        """Save current HSV ranges to JSON file."""
        hsv_lower, hsv_upper = self._get_current_ranges()
        
        config = {
            "hsv_lower": list(hsv_lower),
            "hsv_upper": list(hsv_upper),
            "note": f"Calibrated from {self.image_path.name}"
        }
        
        with open(output_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"\n✓ Saved ranges to: {output_file}")
        print(f"  HSV Lower: {hsv_lower}")
        print(f"  HSV Upper: {hsv_upper}")
    
    def run(self):
        """Run interactive picker loop."""
        self.create_window()
        
        print("\n" + "="*60)
        print("HSV Color Picker")
        print("="*60)
        print(f"Image: {self.image_path}")
        print(f"Size: {self.frame.shape[1]}x{self.frame.shape[0]}")
        print("\nControls:")
        print("  - Adjust trackbars to tune HSV ranges")
        print("  - Press 's' to save current ranges")
        print("  - Press 'r' to reset to defaults")
        print("  - Press 'q' or ESC to quit")
        print("="*60)
        
        while True:
            # Get current ranges
            hsv_lower, hsv_upper = self._get_current_ranges()
            
            # Create mask
            mask = self._create_mask(hsv_lower, hsv_upper)
            
            # Visualize
            vis = self._visualize(mask)
            
            # Display
            cv2.imshow(self.window_name, vis)
            
            # Handle key press
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == 27:  # Q or ESC
                break
            elif key == ord('s'):  # Save
                output_file = Path("hsv_ranges_calibrated.json")
                self.save_ranges(output_file)
            elif key == ord('r'):  # Reset
                cv2.setTrackbarPos("H Min", self.window_name, 20)
                cv2.setTrackbarPos("H Max", self.window_name, 30)
                cv2.setTrackbarPos("S Min", self.window_name, 100)
                cv2.setTrackbarPos("S Max", self.window_name, 255)
                cv2.setTrackbarPos("V Min", self.window_name, 100)
                cv2.setTrackbarPos("V Max", self.window_name, 255)
                print("\nReset to default ranges")
        
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description="Interactive HSV color range picker"
    )
    parser.add_argument(
        "--image",
        type=Path,
        required=True,
        help="Path to minimap image"
    )
    
    args = parser.parse_args()
    
    if not args.image.exists():
        print(f"ERROR: Image not found: {args.image}")
        return 1
    
    try:
        picker = HSVColorPicker(args.image)
        picker.run()
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
