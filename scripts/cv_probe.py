#!/usr/bin/env python3
"""
Quick diagnostics script for the CV capture pipeline.

Usage:
    python scripts/cv_probe.py [--timeout 8] [--output frame.jpg]

The script starts the shared CVCapture instance, waits for a frame,
prints metadata to the console, and optionally writes the JPEG to disk.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

from msmacro.cv import get_capture_instance, CVCaptureError, list_video_devices


async def gather_frame(timeout: float, output: Optional[Path]) -> int:
    devices = list_video_devices()
    if not devices:
        print("[cv_probe] No /dev/video* devices detected. Check cabling and kernel drivers.", file=sys.stderr)
    else:
        print("[cv_probe] Detected video devices:")
        for dev in devices:
            print(f"  - {dev.device_path} (index={dev.device_index}, name='{dev.name}')")

    capture = get_capture_instance()
    try:
        await capture.start()
    except CVCaptureError as exc:
        print(f"[cv_probe] Failed to start capture: {exc}", file=sys.stderr)
        return 2

    try:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            frame_result = capture.get_latest_frame()
            if frame_result:
                frame_bytes, metadata = frame_result
                status = capture.get_status()

                print("[cv_probe] Capture status:")
                print(f"  connected: {status.get('connected')}")
                print(f"  capturing: {status.get('capturing')}")
                print(f"  frames_captured: {status.get('frames_captured')}")
                print(f"  frames_failed: {status.get('frames_failed')}")
                if metadata:
                    print("[cv_probe] Latest frame metadata:")
                    print(f"  resolution: {metadata.width} x {metadata.height}")
                    print(f"  size_bytes: {metadata.size_bytes}")
                    print(f"  timestamp: {metadata.timestamp}")

                if output:
                    output.write_bytes(frame_bytes)
                    print(f"[cv_probe] Wrote latest frame to {output}")
                return 0

            await asyncio.sleep(0.1)

        last_status = capture.get_status()
        print("[cv_probe] Timed out waiting for frame.")
        print(f"  connected: {last_status.get('connected')}")
        print(f"  capturing: {last_status.get('capturing')}")
        print(f"  last_error: {last_status.get('last_error')}")
        return 1
    finally:
        await capture.stop()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect CV capture output")
    parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Seconds to wait for a frame before giving up (default: 8s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the captured JPEG frame",
    )

    args = parser.parse_args(argv)
    try:
        return asyncio.run(gather_frame(args.timeout, args.output))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
