#!/usr/bin/env python3
"""
Improved white frame detection demonstrator.

This script shows the new detect_top_left_white_frame function in action,
with visual feedback showing:
- Full frame with detected region highlighted
- Cropped region isolated
- Detection statistics and confidence

Usage:
    # Monitor with default settings
    python scripts/cv_detect_improved.py

    # Adjust detection threshold
    python scripts/cv_detect_improved.py --threshold 230 --ratio 0.85

    # Save visualizations when white frame detected
    python scripts/cv_detect_improved.py --save-viz /tmp/detection_

    # Run once and exit (for testing)
    python scripts/cv_detect_improved.py --once

    # Start capture automatically
    python scripts/cv_detect_improved.py --start-capture
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
from msmacro.cv.region_analysis import detect_top_left_white_frame, visualize_region, Region


async def main():
    parser = argparse.ArgumentParser(
        description="Improved white frame detection with visualization"
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
        default=0.85,
        help="Minimum white pixel ratio 0.0-1.0 (default: 0.85)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Check interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--save-viz",
        type=str,
        help="Save visualization images to this directory prefix (e.g., /tmp/detection_)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit",
    )
    parser.add_argument(
        "--start-capture",
        action="store_true",
        help="Start CV capture if not already running",
    )
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("IMPROVED WHITE FRAME DETECTION")
    print("=" * 70)
    print(f"Threshold:          {args.threshold} (0-255, higher = whiter)")
    print(f"Min white ratio:    {args.ratio:.1%}")
    print(f"Check interval:     {args.interval}s")
    if args.save_viz:
        print(f"Save visualizations to: {args.save_viz}*")
    print("=" * 70)
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

    print("Monitoring for white frame detection...\n")

    detection_count = 0
    last_save_time = 0

    try:
        while True:
            # Get latest frame
            frame_result = capture.get_latest_frame()
            if not frame_result:
                print(f"\r[{time.strftime('%H:%M:%S')}] ⚠ Waiting for frame...", end="", flush=True)
                await asyncio.sleep(args.interval)
                continue

            jpeg_bytes, metadata = frame_result

            # Decode JPEG to numpy array
            nparr = np.frombuffer(jpeg_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                print(f"\r[{time.strftime('%H:%M:%S')}] ⚠ Failed to decode frame", end="", flush=True)
                await asyncio.sleep(args.interval)
                continue

            # Perform detection
            result = detect_top_left_white_frame(
                frame,
                threshold=args.threshold,
                min_white_ratio=args.ratio
            )

            current_time = time.time()

            if result and result.get("detected"):
                detection_count += 1

                # Extract region info
                x = result.get("x", 0)
                y = result.get("y", 0)
                w = result.get("width", 0)
                h = result.get("height", 0)
                confidence = result.get("confidence", 0.0)
                white_ratio = result.get("region_white_ratio", 0.0)
                avg_brightness = result.get("avg_brightness", 0.0)

                print(f"\n{'='*70}")
                print(f"[{time.strftime('%H:%M:%S')}] 🟦 WHITE FRAME DETECTED (#{detection_count})")
                print(f"{'='*70}")
                print(f"  Region:        x={x}, y={y}, {w}x{h} pixels")
                print(f"  Confidence:    {confidence:.1%}")
                print(f"  White ratio:   {white_ratio:.1%}")
                print(f"  Avg brightness:{avg_brightness:>6.1f}")
                print(f"  Frame size:    {metadata.width}x{metadata.height} ({len(jpeg_bytes):,} bytes)")
                print(f"{'='*70}\n")

                # Save visualization if requested
                if args.save_viz and current_time - last_save_time >= 2.0:
                    last_save_time = current_time
                    timestamp = int(current_time)

                    # Visualize detection on full frame
                    viz_frame = frame.copy()
                    cv2.rectangle(viz_frame, (x, y), (x + w, y + h), (0, 255, 0), 3)  # Green rectangle
                    cv2.putText(
                        viz_frame,
                        f"Confidence: {confidence:.1%}",
                        (x + 10, y + 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2
                    )

                    # Save full frame with overlay
                    full_path = f"{args.save_viz}{timestamp}_full.jpg"
                    cv2.imwrite(full_path, viz_frame)
                    print(f"  Saved full frame: {full_path}")

                    # Save cropped region
                    if w > 0 and h > 0:
                        cropped = frame[y:y+h, x:x+w]
                        crop_path = f"{args.save_viz}{timestamp}_crop.jpg"
                        cv2.imwrite(crop_path, cropped)
                        print(f"  Saved cropped region: {crop_path}")

            else:
                # Not detected - show current stats
                white_ratio = result.get("white_ratio", 0.0) if result else 0.0
                avg_brightness = result.get("avg_brightness", 0.0) if result else 0.0

                print(
                    f"\r[{time.strftime('%H:%M:%S')}] Monitoring... "
                    f"White: {white_ratio:>5.1%} | "
                    f"Brightness: {avg_brightness:>6.1f} | "
                    f"Detections: {detection_count}",
                    end="",
                    flush=True,
                )

            # Exit if --once flag
            if args.once:
                print("\n--once flag set, exiting")
                return 0

            await asyncio.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n\nStopped by user")
        print(f"Total detections: {detection_count}")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
