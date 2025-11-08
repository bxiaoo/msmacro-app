#!/usr/bin/env python3
"""
Capture YUYV minimap frames for object detection test dataset.

This script captures raw frames from the msmacro CV capture system
and saves them for ground truth annotation and validation testing.

Usage:
    # Capture 60 frames with default settings
    python scripts/capture_yuyv_dataset.py

    # Capture custom number of frames
    python scripts/capture_yuyv_dataset.py --count 100 --output data/custom_set/

    # Capture with longer interval between frames
    python scripts/capture_yuyv_dataset.py --interval 3.0

Requirements:
    - msmacro daemon must be running
    - CV capture must be active
    - Game should be running with minimap visible
"""

import argparse
import sys
import time
from pathlib import Path
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from msmacro.cv.capture import get_capture_instance


def print_scenario_guide():
    """Print guide for capture scenarios."""
    print("\n" + "="*70)
    print("CAPTURE SCENARIO GUIDE")
    print("="*70)
    print("\nFor best validation results, capture frames covering these scenarios:")
    print("\n1. Player Alone (Various Positions) - 15 frames")
    print("   - Move player around minimap to different positions")
    print("   - Include center, edges, and corners")
    print("   - Ensure player dot is clearly visible")
    print("\n2. Player at Edges/Corners - 10 frames")
    print("   - Position player near minimap boundaries")
    print("   - Test edge cases for position detection")
    print("\n3. Player + 1 Other Player - 10 frames")
    print("   - Single other player visible on minimap")
    print("   - Various distances from player")
    print("\n4. Player + 2-3 Other Players - 10 frames")
    print("   - Small group of other players")
    print("   - Test multiple object detection")
    print("\n5. Player + 5+ Other Players - 5 frames")
    print("   - Crowded minimap scenario")
    print("   - Stress test for detection")
    print("\n6. Different Lighting Conditions - 10 frames")
    print("   - If game has day/night cycles, capture both")
    print("   - Different weather/environmental lighting")
    print("\n" + "="*70)
    print("\nPress Ctrl+C at any time to stop capture early")
    print("="*70 + "\n")


def capture_yuyv_dataset(output_dir: Path, count: int = 60, interval: float = 2.0):
    """
    Capture minimap frames in YUYV format.

    Args:
        output_dir: Directory to save .npy files
        count: Number of frames to capture
        interval: Seconds between captures
    """
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nInitializing CV capture...")

    # Get capture instance
    try:
        capture = get_capture_instance()
    except Exception as e:
        print(f"ERROR: Failed to get capture instance: {e}")
        print("\nMake sure:")
        print("  1. msmacro daemon is running")
        print("  2. CV capture has been started")
        print("  3. Game is running with minimap visible")
        return 1

    # Check if capture is running
    try:
        result = capture.get_latest_frame()
        if result is None:
            print("ERROR: No frame available from capture")
            print("\nMake sure CV capture is started first:")
            print("  CLI: python -m msmacro ctl cv-start")
            print("  API: curl -X POST http://localhost:5050/api/cv/start")
            print("  Web UI: Navigate to http://localhost:5050 and enable CV capture")
            return 1

        test_frame, test_meta = result
        print(f"✓ CV capture is active (frame size: {test_frame.shape})")
    except Exception as e:
        print(f"ERROR: Failed to get frame: {e}")
        return 1

    print(f"\nCapture Settings:")
    print(f"  Output: {output_dir}")
    print(f"  Frames: {count}")
    print(f"  Interval: {interval}s")
    print(f"  Total time: ~{count * interval / 60:.1f} minutes")

    # Show scenario guide
    print_scenario_guide()

    input("\nPress ENTER to start capture...")

    captured = 0
    failed = 0

    print(f"\n{'='*70}")
    print(f"STARTING CAPTURE")
    print(f"{'='*70}\n")

    try:
        for i in range(count):
            # Progress indicator
            progress_pct = (i / count) * 100
            print(f"[{i+1}/{count}] ({progress_pct:.1f}%) Capturing frame...", end=" ", flush=True)

            try:
                # Get latest frame
                result = capture.get_latest_frame()

                if result is None:
                    print("❌ FAILED (no frame)")
                    failed += 1
                    continue

                frame_bgr, metadata = result

                # Extract minimap region if region detection is enabled
                if hasattr(metadata, 'region_detected') and metadata.region_detected:
                    # Use detected region coordinates
                    x1, y1 = metadata.region_x, metadata.region_y
                    # Minimap is typically 340x86 from config
                    minimap_bgr = frame_bgr[y1:y1+86, x1:x1+340]
                else:
                    # Fallback to fixed coordinates (68, 56) from plan
                    minimap_bgr = frame_bgr[56:142, 68:408]

                # Validate minimap size
                if minimap_bgr.shape[0] < 50 or minimap_bgr.shape[1] < 200:
                    print(f"❌ FAILED (invalid size: {minimap_bgr.shape})")
                    failed += 1
                    continue

                # Save as numpy array
                timestamp = int(time.time() * 1000)  # Milliseconds
                filename = output_dir / f"minimap_{i:04d}_{timestamp}.npy"
                np.save(filename, minimap_bgr)

                print(f"✓ SAVED ({minimap_bgr.shape}) -> {filename.name}")
                captured += 1

            except Exception as e:
                print(f"❌ FAILED ({e})")
                failed += 1

            # Wait before next capture (except on last frame)
            if i < count - 1:
                time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Capture interrupted by user")

    # Summary
    print(f"\n{'='*70}")
    print(f"CAPTURE COMPLETE")
    print(f"{'='*70}")
    print(f"  Captured: {captured} frames")
    print(f"  Failed: {failed} frames")
    print(f"  Success Rate: {(captured / count) * 100:.1f}%")
    print(f"  Output: {output_dir}")
    print(f"\nNext Steps:")
    print(f"  1. Run annotation tool:")
    print(f"     python scripts/annotate_ground_truth.py --dataset {output_dir}")
    print(f"  2. After annotation, run validation:")
    print(f"     python scripts/validate_detection.py --dataset {output_dir}")
    print(f"{'='*70}\n")

    return 0 if captured > 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="Capture YUYV minimap frames for object detection testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture default 60 frames
  python scripts/capture_yuyv_dataset.py

  # Capture 100 frames with 3 second interval
  python scripts/capture_yuyv_dataset.py --count 100 --interval 3.0

  # Capture to custom directory
  python scripts/capture_yuyv_dataset.py --output data/test_batch_2/
        """
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/yuyv_test_set"),
        help="Output directory for frames (default: data/yuyv_test_set)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=60,
        help="Number of frames to capture (default: 60)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Seconds between captures (default: 2.0)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.count < 1:
        print("ERROR: Count must be at least 1")
        return 1

    if args.interval < 0.1:
        print("ERROR: Interval must be at least 0.1 seconds")
        return 1

    try:
        return capture_yuyv_dataset(args.output, args.count, args.interval)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
