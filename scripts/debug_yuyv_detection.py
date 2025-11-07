#!/usr/bin/env python3
"""
Debug YUYV detection by analyzing Y channel values.
"""

import cv2
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from msmacro.cv.region_analysis import (
    bgr_to_yuyv_bytes,
    extract_y_channel_from_yuyv
)

def debug_frame(image_path):
    """Debug Y channel values at expected white frame location."""
    print(f"\nAnalyzing: {image_path}")
    print("=" * 70)

    # Load frame
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"ERROR: Failed to load image")
        return

    h, w = frame.shape[:2]
    print(f"Frame dimensions: {w}x{h}")

    # Convert BGR to YUYV
    yuyv_bytes = bgr_to_yuyv_bytes(frame)

    # Extract Y channel for a region around the expected position
    start_x, start_y = 68, 56
    region_w, region_h = 400, 120

    y_channel = extract_y_channel_from_yuyv(
        yuyv_bytes,
        w, h,
        start_x - 20, start_y - 20,  # Include some margin
        region_w, region_h
    )

    if y_channel is None:
        print("ERROR: Failed to extract Y channel")
        return

    print(f"\nExtracted Y channel region: {y_channel.shape}")

    # Analyze the corner where white border should be
    # Offset by 20 because we extracted with margin
    local_x, local_y = 20, 20

    corner = y_channel[local_y:local_y+5, local_x:local_x+5]
    print(f"\nCorner region (should be white border):")
    print(f"  Position in frame: ({start_x}, {start_y})")
    print(f"  Y values:\n{corner}")
    print(f"  Min: {corner.min()}, Max: {corner.max()}, Mean: {corner.mean():.1f}")
    print(f"  White pixels (≥240): {np.sum(corner >= 240)}/{corner.size}")

    # Check top edge
    top_edge = y_channel[local_y:local_y+3, local_x:local_x+50]
    print(f"\nTop edge (first 50 pixels):")
    print(f"  Mean: {top_edge.mean():.1f}")
    print(f"  White pixels (≥240): {np.sum(top_edge >= 240)}/{top_edge.size}")

    # Check left edge
    left_edge = y_channel[local_y:local_y+50, local_x:local_x+3]
    print(f"\nLeft edge (first 50 pixels):")
    print(f"  Mean: {left_edge.mean():.1f}")
    print(f"  White pixels (≥240): {np.sum(left_edge >= 240)}/{left_edge.size}")

    # Visualize Y channel
    print(f"\nVisualizing Y channel region...")

    # Create visualization
    viz = np.zeros((region_h, region_w, 3), dtype=np.uint8)

    # Show Y channel as grayscale
    viz[:,:,0] = y_channel
    viz[:,:,1] = y_channel
    viz[:,:,2] = y_channel

    # Mark the expected starting point
    cv2.circle(viz, (local_x, local_y), 3, (0, 0, 255), -1)  # Red dot

    # Mark regions with Y >= 240 (white)
    white_mask = y_channel >= 240
    viz[white_mask] = [255, 255, 0]  # Cyan for white regions

    # Save visualization
    output_path = image_path.replace('.jpg', '_y_channel_debug.jpg')
    cv2.imwrite(output_path, viz)
    print(f"Saved Y channel visualization to: {output_path}")

    # Also create a heatmap
    heatmap = cv2.applyColorMap(y_channel, cv2.COLORMAP_JET)
    output_path2 = image_path.replace('.jpg', '_y_heatmap.jpg')
    cv2.imwrite(output_path2, heatmap)
    print(f"Saved Y channel heatmap to: {output_path2}")

def main():
    debug_frame("/Users/boweixiao/Downloads/msmacro_cv_frame_original.jpg")
    return 0

if __name__ == '__main__':
    sys.exit(main())
