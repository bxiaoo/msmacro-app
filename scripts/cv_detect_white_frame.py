#!/usr/bin/env python3
"""
Demo: Detect white frame in top-left corner of screen.

This script continuously monitors the top-left corner of the captured screen
and detects when a white frame appears.

Usage:
    # Monitor with default settings
    python scripts/cv_detect_white_frame.py

    # Custom region size (top-left 300x150 pixels)
    python scripts/cv_detect_white_frame.py --width 300 --height 150

    # Adjust white detection threshold
    python scripts/cv_detect_white_frame.py --threshold 230 --ratio 0.9

    # Save screenshot when white frame detected
    python scripts/cv_detect_white_frame.py --save-on-detect /tmp/white_frame.jpg

    # Run once and exit (for testing)
    python scripts/cv_detect_white_frame.py --once
"""

import asyncio
import sys
import argparse
from pathlib import Path
import time
import cv2
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from msmacro.cv import get_capture_instance
from msmacro.cv.region_analysis import Region, is_white_region, visualize_region


async def main():
    parser = argparse.ArgumentParser(
        description="Detect white frame in top-left corner"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=200,
        help="Region width in pixels (default: 200)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=100,
        help="Region height in pixels (default: 100)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=240,
        help="White pixel threshold 0-255 (default: 240)",
    )
    parser.add_argument(
        "--ratio",
        type=float,
        default=0.95,
        help="Minimum white pixel ratio 0.0-1.0 (default: 0.95)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Check interval in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--save-on-detect",
        type=str,
        help="Save screenshot to this path when white frame detected",
    )
    parser.add_argument(
        "--visualize",
        type=str,
        help="Save visualization with region marked to this path",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (for testing)",
    )
    parser.add_argument(
        "--start-capture",
        action="store_true",
        help="Start CV capture if not already running",
    )
    args = parser.parse_args()

    # Define region (top-left corner)
    region = Region(x=0, y=0, width=args.width, height=args.height)

    print(f"White Frame Detector")
    print(f"=" * 60)
    print(f"Region: Top-left {args.width}x{args.height} pixels")
    print(f"Threshold: {args.threshold} (0-255)")
    print(f"Min white ratio: {args.ratio:.1%}")
    print(f"Check interval: {args.interval}s")
    print(f"=" * 60)
    print()

    # Get capture instance
    capture = get_capture_instance()

    # Start capture if requested
    status = capture.get_status()
    if args.start_capture and not status.get("capturing"):
        print("Starting CV capture system...")
        try:
            await capture.start()
            print("✓ Capture started")
            await asyncio.sleep(2)  # Wait for first frame
        except Exception as e:
            print(f"✗ Failed to start capture: {e}")
            return 1
    elif not status.get("capturing"):
        print("✗ CV capture is not running")
        print("  Use --start-capture or start daemon first")
        return 1

    print("Monitoring for white frame... (Ctrl+C to stop)")
    print()

    detection_count = 0
    last_detection_time = 0

    try:
        while True:
            # Get latest frame
            frame_result = capture.get_latest_frame()
            if not frame_result:
                print("⚠ No frame available, waiting...")
                await asyncio.sleep(args.interval)
                continue

            jpeg_bytes, metadata = frame_result

            # Decode JPEG to numpy array
            nparr = np.frombuffer(jpeg_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                print("⚠ Failed to decode frame")
                await asyncio.sleep(args.interval)
                continue

            # Check if region is white
            is_white, stats = is_white_region(
                frame, region, threshold=args.threshold, min_white_ratio=args.ratio
            )

            current_time = time.time()

            if is_white:
                # Debounce detections (only report once per second)
                if current_time - last_detection_time >= 1.0:
                    detection_count += 1
                    last_detection_time = current_time

                    print(f"[{time.strftime('%H:%M:%S')}] 🟦 WHITE FRAME DETECTED!")
                    print(f"  Detection #{detection_count}")
                    print(f"  White pixels: {stats['white_ratio']:.1%}")
                    print(f"  Avg brightness: {stats['avg_brightness']:.1f}")

                    # Save screenshot if requested
                    if args.save_on_detect:
                        save_path = Path(args.save_on_detect)
                        save_path.parent.mkdir(parents=True, exist_ok=True)

                        # Add timestamp to filename
                        stem = save_path.stem
                        suffix = save_path.suffix
                        timestamped = save_path.with_name(
                            f"{stem}_{int(current_time)}{suffix}"
                        )

                        cv2.imwrite(str(timestamped), frame)
                        print(f"  Screenshot saved: {timestamped}")

                    print()
            else:
                # Show live stats (overwrite same line)
                print(
                    f"\r[{time.strftime('%H:%M:%S')}] Monitoring... "
                    f"White: {stats['white_ratio']:>5.1%} | "
                    f"Brightness: {stats['avg_brightness']:>5.1f} | "
                    f"Detections: {detection_count}",
                    end="",
                    flush=True,
                )

            # Save visualization if requested
            if args.visualize and is_white:
                vis_frame = visualize_region(
                    frame,
                    region,
                    color=(0, 255, 0) if is_white else (0, 0, 255),
                    label=f"White: {stats['white_ratio']:.1%}",
                )
                cv2.imwrite(args.visualize, vis_frame)
                print(f"  Visualization saved: {args.visualize}")

            # Exit if --once flag
            if args.once:
                print("\n--once flag set, exiting")
                return 0

            await asyncio.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n\nStopped by user")
        print(f"Total detections: {detection_count}")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
