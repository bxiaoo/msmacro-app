#!/usr/bin/env python3
"""
Debug object detection with live visualization.

Usage:
    # Test with single image
    python scripts/debug_object_detection.py --image /path/to/minimap.jpg
    
    # Test with directory of images
    python scripts/debug_object_detection.py --dir /path/to/images/
    
    # Show color masks
    python scripts/debug_object_detection.py --image /path/to/minimap.jpg --show-masks
"""

import argparse
import sys
from pathlib import Path
import cv2
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig


def debug_single_image(image_path: Path, show_masks: bool = False):
    """
    Debug detection on a single image.
    
    Args:
        image_path: Path to image file
        show_masks: Whether to show color masks
    """
    print(f"Loading image: {image_path}")
    
    # Read image
    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"ERROR: Could not read image: {image_path}")
        return
    
    print(f"Image size: {frame.shape[1]}x{frame.shape[0]}")
    
    # Create detector with default config
    detector = MinimapObjectDetector()
    
    # Detect
    print("\nRunning detection...")
    result = detector.detect(frame)
    
    # Print results
    print("\n=== Detection Results ===")
    print(f"Timestamp: {result.timestamp}")
    print(f"\nPlayer:")
    print(f"  Detected: {result.player.detected}")
    if result.player.detected:
        print(f"  Position: ({result.player.x}, {result.player.y})")
        print(f"  Confidence: {result.player.confidence:.3f}")
    
    print(f"\nOther Players:")
    print(f"  Detected: {result.other_players.detected}")
    print(f"  Count: {result.other_players.count}")
    
    # Visualize
    vis_frame = detector.visualize(frame, result)
    
    # Show main visualization
    cv2.imshow("Object Detection", vis_frame)
    
    # Show color masks if requested
    if show_masks:
        masks = detector.get_debug_masks(frame)
        
        # Stack masks horizontally
        player_mask_color = cv2.cvtColor(masks['player_mask'], cv2.COLOR_GRAY2BGR)
        other_mask_color = cv2.cvtColor(masks['other_players_mask'], cv2.COLOR_GRAY2BGR)
        
        # Add labels
        cv2.putText(player_mask_color, "Player Mask (Yellow)",
                   (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(other_mask_color, "Other Players Mask (Red)",
                   (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        masks_combined = np.hstack([player_mask_color, other_mask_color])
        cv2.imshow("Color Masks", masks_combined)
    
    print("\nPress any key to continue...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def debug_directory(dir_path: Path, show_masks: bool = False):
    """
    Debug detection on all images in a directory.
    
    Args:
        dir_path: Path to directory containing images
        show_masks: Whether to show color masks
    """
    # Find all image files
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.npy']
    image_files = []
    for ext in image_extensions:
        image_files.extend(dir_path.glob(f'*{ext}'))
    
    image_files = sorted(image_files)
    
    if not image_files:
        print(f"No image files found in: {dir_path}")
        return
    
    print(f"Found {len(image_files)} images")
    
    # Create detector
    detector = MinimapObjectDetector()
    
    # Process each image
    for i, image_path in enumerate(image_files):
        print(f"\n{'='*60}")
        print(f"Image {i+1}/{len(image_files)}: {image_path.name}")
        print('='*60)
        
        # Read image
        if image_path.suffix == '.npy':
            # NumPy array
            frame = np.load(str(image_path))
        else:
            # Regular image
            frame = cv2.imread(str(image_path))
        
        if frame is None:
            print(f"ERROR: Could not read image")
            continue
        
        # Detect
        result = detector.detect(frame)
        
        # Print results
        print(f"Player: detected={result.player.detected}", end="")
        if result.player.detected:
            print(f", pos=({result.player.x},{result.player.y}), conf={result.player.confidence:.3f}")
        else:
            print()
        
        print(f"Other Players: detected={result.other_players.detected}, count={result.other_players.count}")
        
        # Visualize
        vis_frame = detector.visualize(frame, result)
        cv2.imshow("Object Detection", vis_frame)
        
        # Show masks if requested
        if show_masks:
            masks = detector.get_debug_masks(frame)
            player_mask_color = cv2.cvtColor(masks['player_mask'], cv2.COLOR_GRAY2BGR)
            other_mask_color = cv2.cvtColor(masks['other_players_mask'], cv2.COLOR_GRAY2BGR)
            masks_combined = np.hstack([player_mask_color, other_mask_color])
            cv2.imshow("Color Masks", masks_combined)
        
        # Wait for key
        print("Press any key for next image, ESC to quit...")
        key = cv2.waitKey(0)
        if key == 27:  # ESC
            break
    
    cv2.destroyAllWindows()
    print(f"\nProcessed {i+1} images")


def main():
    parser = argparse.ArgumentParser(
        description="Debug object detection with visualization"
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Path to single image file"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        help="Path to directory containing images"
    )
    parser.add_argument(
        "--show-masks",
        action="store_true",
        help="Show color masks for debugging"
    )
    
    args = parser.parse_args()
    
    if not args.image and not args.dir:
        parser.print_help()
        print("\nERROR: Must specify --image or --dir")
        return 1
    
    if args.image:
        if not args.image.exists():
            print(f"ERROR: Image not found: {args.image}")
            return 1
        debug_single_image(args.image, args.show_masks)
    
    if args.dir:
        if not args.dir.is_dir():
            print(f"ERROR: Directory not found: {args.dir}")
            return 1
        debug_directory(args.dir, args.show_masks)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
