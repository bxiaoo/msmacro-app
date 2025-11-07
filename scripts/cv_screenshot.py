#!/usr/bin/env python3
"""
Capture a single screenshot from the CV system and save it to disk.

Usage on Raspberry Pi:
    # Capture and save screenshot
    python scripts/cv_screenshot.py

    # Save to specific location
    python scripts/cv_screenshot.py --output /tmp/screenshot.jpg

    # Transfer to host machine (run this from Pi)
    scp /tmp/cv_screenshot.jpg user@your-host-machine:/path/to/destination/

Example workflow:
    # 1. On Pi: Capture screenshot
    python scripts/cv_screenshot.py --output /tmp/screenshot.jpg

    # 2. On Pi: Transfer to your laptop/desktop
    scp /tmp/screenshot.jpg you@192.168.1.100:~/Downloads/

    # 3. On your machine: View the screenshot
    open ~/Downloads/screenshot.jpg
"""

import asyncio
import sys
import argparse
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from msmacro.cv import get_capture_instance


async def main():
    parser = argparse.ArgumentParser(description="Capture screenshot from CV system")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="/tmp/cv_screenshot.jpg",
        help="Output path for screenshot (default: /tmp/cv_screenshot.jpg)",
    )
    parser.add_argument(
        "--start-capture",
        action="store_true",
        help="Start CV capture if not already running",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=2.0,
        help="Seconds to wait for fresh frame (default: 2.0)",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"CV Screenshot Utility")
    print(f"=" * 60)

    # Get capture instance
    capture = get_capture_instance()

    # Start capture if requested and not running
    status = capture.get_status()
    if args.start_capture and not status.get("capturing"):
        print("Starting CV capture system...")
        try:
            await capture.start()
            print("✓ Capture started")
        except Exception as e:
            print(f"✗ Failed to start capture: {e}")
            return 1
    elif not status.get("capturing"):
        print("⚠ Warning: CV capture is not running")
        print("  Use --start-capture to automatically start it")
        print("  Or start the daemon first: python -m msmacro daemon")
        return 1

    # Wait for fresh frame
    print(f"Waiting {args.wait}s for fresh frame...")
    await asyncio.sleep(args.wait)

    # Get latest frame
    frame_result = capture.get_latest_frame()
    if not frame_result:
        print("✗ No frame available")
        print("  Check if capture device is connected")
        return 1

    jpeg_bytes, metadata = frame_result

    # Save to file
    output_path.write_bytes(jpeg_bytes)

    print(f"✓ Screenshot saved: {output_path}")
    print(f"  Resolution: {metadata.width}x{metadata.height}")
    print(f"  Size: {len(jpeg_bytes):,} bytes ({len(jpeg_bytes) / 1024:.1f} KB)")
    print(f"  Age: {time.time() - metadata.timestamp:.2f}s")
    print()
    print("To transfer to your host machine, run:")
    print(f"  scp {output_path} user@your-host-ip:~/Downloads/")
    print()
    print("Example:")
    print(f"  scp {output_path} you@192.168.1.100:~/Desktop/screenshot.jpg")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
