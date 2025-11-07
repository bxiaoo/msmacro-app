#!/usr/bin/env python3
"""
Find the actual white border location in the frame.
"""

import cv2
import numpy as np

def find_white_border(image_path):
    """Scan for white border in the frame."""
    print(f"\nSearching for white border in: {image_path}")
    print("=" * 70)

    frame = cv2.imread(image_path)
    if frame is None:
        print("ERROR: Failed to load image")
        return

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    h, w = gray.shape
    print(f"Frame dimensions: {w}x{h}")

    # Create white mask (threshold 240)
    white_mask = gray >= 240

    # Search in the top-left quadrant
    search_h, search_w = 200, 500

    print(f"\nScanning top-left {search_w}x{search_h} region for white pixels...")

    # Find all white pixels in search region
    white_pixels = np.argwhere(white_mask[:search_h, :search_w])

    if len(white_pixels) == 0:
        print("No white pixels found!")
        return

    print(f"Found {len(white_pixels):,} white pixels")

    # Find bounding box of white pixels
    min_y, min_x = white_pixels.min(axis=0)
    max_y, max_x = white_pixels.max(axis=0)

    print(f"\nWhite pixel bounding box:")
    print(f"  Top-left: ({min_x}, {min_y})")
    print(f"  Bottom-right: ({max_x}, {max_y})")
    print(f"  Size: {max_x - min_x}x{max_y - min_y}")

    # Check if this forms a rectangular border
    # Sample the border area
    border_top = white_mask[min_y:min_y+3, min_x:max_x]
    border_left = white_mask[min_y:max_y, min_x:min_x+3]
    border_right = white_mask[min_y:max_y, max_x-3:max_x]
    border_bottom = white_mask[max_y-3:max_y, min_x:max_x]

    print(f"\nBorder analysis:")
    print(f"  Top border white ratio: {border_top.sum() / border_top.size:.2%}")
    print(f"  Left border white ratio: {border_left.sum() / border_left.size:.2%}")
    print(f"  Right border white ratio: {border_right.sum() / border_right.size:.2%}")
    print(f"  Bottom border white ratio: {border_bottom.sum() / border_bottom.size:.2%}")

    # Visualize
    viz = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # Draw white pixel bounding box in green
    cv2.rectangle(viz, (min_x, min_y), (max_x, max_y), (0, 255, 0), 2)

    # Draw expected position (68, 56) in red
    cv2.circle(viz, (68, 56), 5, (0, 0, 255), -1)
    cv2.putText(viz, "Expected (68,56)", (68, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    # Draw actual position in blue
    cv2.circle(viz, (min_x, min_y), 5, (255, 0, 0), -1)
    cv2.putText(viz, f"Actual ({min_x},{min_y})", (min_x, min_y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

    output_path = image_path.replace('.jpg', '_white_border_found.jpg')
    cv2.imwrite(output_path, viz)
    print(f"\nSaved visualization to: {output_path}")

    print(f"\n{'='*70}")
    print(f"RECOMMENDATION:")
    print(f"  Use fixed_start_x={min_x}, fixed_start_y={min_y}")
    print(f"  Expected size: ~{max_x - min_x}x{max_y - min_y}")
    print(f"{'='*70}")

def main():
    find_white_border("/Users/boweixiao/Downloads/msmacro_cv_frame_original.jpg")
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
