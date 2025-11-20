#!/usr/bin/env python3
"""
High Resolution Capture Testing Tool

Tests capture capabilities at various resolutions including 2K and 4K.
Measures memory usage, processing time, and minimap quality improvements.

Usage:
    python scripts/test_high_resolution_capture.py [--device INDEX] [--save-samples]
"""

import sys
import argparse
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from msmacro.cv.device import find_capture_device

def get_memory_usage():
    """Get current process memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # Convert to MB
    except ImportError:
        return None

def test_resolution(cap, width, height, name, save_dir=None):
    """Test a specific resolution and measure metrics."""
    print(f"\n{'=' * 70}")
    print(f"Testing {name} ({width}x{height})")
    print('=' * 70)

    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # Warm up - read a few frames
    for _ in range(5):
        cap.read()

    # Memory before capture
    mem_before = get_memory_usage()

    # Capture frame
    start_time = time.time()
    ret, frame = cap.read()
    capture_time = (time.time() - start_time) * 1000  # Convert to ms

    if not ret or frame is None:
        print(f"❌ FAILED: Could not capture frame")
        return None

    actual_h, actual_w = frame.shape[:2]

    if actual_w != width or actual_h != height:
        print(f"⚠️  WARNING: Requested {width}x{height}, got {actual_w}x{actual_h}")
    else:
        print(f"✅ SUCCESS: Captured {actual_w}x{actual_h}")

    # Calculate frame size
    frame_size_mb = frame.nbytes / 1024 / 1024

    # JPEG encoding test
    start_time = time.time()
    _, jpeg_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    jpeg_time = (time.time() - start_time) * 1000
    jpeg_size_kb = len(jpeg_data) / 1024

    # Extract minimap region (typical position and size scaled by resolution)
    # At 720p: minimap is at (68, 56, 340, 86)
    # Scale proportionally
    scale = height / 720
    minimap_x = int(68 * scale)
    minimap_y = int(56 * scale)
    minimap_w = int(340 * scale)
    minimap_h = int(86 * scale)

    minimap = frame[minimap_y:minimap_y+minimap_h, minimap_x:minimap_x+minimap_w]
    minimap_size_kb = minimap.nbytes / 1024

    # Memory after
    mem_after = get_memory_usage()
    mem_increase = mem_after - mem_before if mem_before and mem_after else None

    # Print metrics
    print(f"\n📊 Metrics:")
    print(f"   Capture time:     {capture_time:.2f} ms")
    print(f"   Frame size (raw): {frame_size_mb:.2f} MB")
    print(f"   JPEG encoding:    {jpeg_time:.2f} ms")
    print(f"   JPEG size:        {jpeg_size_kb:.1f} KB")
    print(f"   Minimap region:   {minimap_w}×{minimap_h} ({minimap_size_kb:.1f} KB)")

    if mem_increase:
        print(f"   Memory increase:  {mem_increase:.2f} MB")

    # Calculate total pixels
    total_pixels = actual_w * actual_h
    minimap_pixels = minimap_w * minimap_h
    print(f"\n📏 Resolution details:")
    print(f"   Total pixels:     {total_pixels:,} ({total_pixels / 1_000_000:.2f}M)")
    print(f"   Minimap pixels:   {minimap_pixels:,}")

    # Save sample if requested
    if save_dir:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Save full frame
        frame_path = save_dir / f"full_frame_{width}x{height}.jpg"
        cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

        # Save minimap crop
        minimap_path = save_dir / f"minimap_{minimap_w}x{minimap_h}.png"
        cv2.imwrite(str(minimap_path), minimap)

        print(f"\n💾 Saved samples:")
        print(f"   Full frame: {frame_path}")
        print(f"   Minimap:    {minimap_path}")

    return {
        'name': name,
        'requested': (width, height),
        'actual': (actual_w, actual_h),
        'capture_time_ms': capture_time,
        'frame_size_mb': frame_size_mb,
        'jpeg_time_ms': jpeg_time,
        'jpeg_size_kb': jpeg_size_kb,
        'minimap_size': (minimap_w, minimap_h),
        'minimap_pixels': minimap_pixels,
        'memory_increase_mb': mem_increase
    }

def main():
    parser = argparse.ArgumentParser(description='Test high resolution capture')
    parser.add_argument('--device', type=int, help='Device index to use')
    parser.add_argument('--save-samples', metavar='DIR', help='Directory to save sample images')
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("HIGH RESOLUTION CAPTURE TESTING")
    print("=" * 70)

    # Find device
    if args.device is not None:
        device_index = args.device
        print(f"\nUsing device index: {device_index}")
    else:
        device = find_capture_device()
        if not device:
            print("❌ No suitable capture device found!")
            return 1
        device_index = device.device_index
        print(f"\nAuto-selected device: {device.name} (index {device_index})")

    # Open capture device
    cap = cv2.VideoCapture(device_index, cv2.CAP_AVFOUNDATION)

    if not cap.isOpened():
        print(f"❌ Failed to open device {device_index}")
        return 1

    # Test resolutions
    resolutions = [
        (1280, 720, "720p (Current)"),
        (1920, 1080, "1080p (Full HD)"),
        (2560, 1440, "2K (QHD)"),
        (3840, 2160, "4K (UHD)"),
    ]

    results = []
    for width, height, name in resolutions:
        result = test_resolution(cap, width, height, name, args.save_samples)
        if result:
            results.append(result)
        time.sleep(0.5)  # Brief pause between tests

    cap.release()

    # Summary comparison
    print("\n" + "=" * 70)
    print("SUMMARY COMPARISON")
    print("=" * 70)

    if not results:
        print("❌ No successful captures")
        return 1

    print(f"\n{'Resolution':<20} {'Frame':<12} {'JPEG':<12} {'Minimap':<15} {'Capture':<10}")
    print(f"{'':20} {'(MB)':<12} {'(KB)':<12} {'(pixels)':<15} {'(ms)':<10}")
    print("-" * 70)

    baseline = results[0]  # 720p is baseline

    for r in results:
        resolution_str = f"{r['actual'][0]}x{r['actual'][1]}"
        frame_mb = r['frame_size_mb']
        jpeg_kb = r['jpeg_size_kb']
        minimap_px = r['minimap_pixels']
        capture_ms = r['capture_time_ms']

        # Calculate multipliers relative to 720p baseline
        frame_mult = frame_mb / baseline['frame_size_mb']
        jpeg_mult = jpeg_kb / baseline['jpeg_size_kb']
        minimap_mult = minimap_px / baseline['minimap_pixels']

        print(f"{resolution_str:<20} {frame_mb:>6.2f} ({frame_mult:>4.1f}x)  "
              f"{jpeg_kb:>6.1f} ({jpeg_mult:>4.1f}x)  "
              f"{minimap_px:>9,} ({minimap_mult:>4.1f}x)  "
              f"{capture_ms:>6.1f}")

    # Recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)

    # Find highest supported resolution
    supported = [r for r in results if r['actual'] == r['requested']]

    if not supported:
        print("❌ No resolutions matched requested values")
    else:
        highest = supported[-1]
        print(f"\n✅ Highest supported resolution: {highest['name']}")
        print(f"   {highest['actual'][0]}x{highest['actual'][1]}")
        print(f"   Minimap size: {highest['minimap_size'][0]}×{highest['minimap_size'][1]}")
        print(f"   Minimap pixels: {highest['minimap_pixels']:,}")

        # Compare to 720p
        if highest != baseline:
            pixel_increase = highest['minimap_pixels'] / baseline['minimap_pixels']
            memory_increase = highest['frame_size_mb'] / baseline['frame_size_mb']

            print(f"\n📈 Improvement over 720p:")
            print(f"   Minimap pixels: {pixel_increase:.1f}x increase")
            print(f"   Frame memory:   {memory_increase:.1f}x increase")

            if pixel_increase >= 4.0 and memory_increase <= 5.0:
                print(f"\n✅ RECOMMENDATION: Use {highest['name']} for development")
                print(f"   Significant detail improvement with acceptable memory cost")
            elif pixel_increase >= 2.0 and memory_increase <= 3.0:
                print(f"\n✅ RECOMMENDATION: Use {highest['name']} if memory allows")
                print(f"   Good detail improvement with moderate memory cost")
            else:
                print(f"\n⚠️  RECOMMENDATION: Stay with 720p")
                print(f"   Marginal benefit vs memory cost trade-off")
        else:
            print(f"\n✅ Current 720p resolution is optimal")

    return 0

if __name__ == '__main__':
    sys.exit(main())
