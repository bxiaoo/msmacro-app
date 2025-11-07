#!/usr/bin/env python3
"""
Test YUYV-based white frame detection with real MapleStory frames.
"""

import cv2
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from msmacro.cv.region_analysis import (
    detect_white_frame_yuyv,
    bgr_to_yuyv_bytes
)

def test_frame(image_path, description):
    """Test detection on a single frame."""
    print(f"\n{'='*70}")
    print(f"Testing: {description}")
    print(f"File: {image_path}")
    print(f"{'='*70}")

    # Load frame
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"ERROR: Failed to load image: {image_path}")
        return False

    h, w = frame.shape[:2]
    print(f"Frame dimensions: {w}x{h}")

    # Convert BGR to YUYV
    print("\nConverting BGR to YUYV...")
    yuyv_bytes = bgr_to_yuyv_bytes(frame)
    print(f"YUYV data size: {len(yuyv_bytes):,} bytes ({len(yuyv_bytes)/(1024*1024):.2f} MB)")

    # Run detection
    print("\nRunning YUYV detection...")
    result = detect_white_frame_yuyv(
        yuyv_bytes,
        w,
        h,
        fixed_start_x=68,
        fixed_start_y=56,
        max_frame_width=500,
        max_frame_height=150,
        white_threshold=240
    )

    if result is None:
        print("ERROR: Detection returned None")
        return False

    # Display results
    print("\nDetection Results:")
    print(f"  Detected: {result['detected']}")
    print(f"  Position: ({result['x']}, {result['y']})")
    print(f"  Size: {result['width']}x{result['height']}")
    print(f"  Confidence: {result['confidence']:.2%}")
    print(f"  White Border Quality: {result['white_border_quality']:.2%}")
    print(f"  Dark Background: {result['dark_background']}")
    print(f"  Method: {result['method']}")

    if result['detected']:
        print(f"\n✓ SUCCESS: White frame detected with {result['confidence']:.0%} confidence")

        # Draw overlays on original frame
        x, y, width, height = result['x'], result['y'], result['width'], result['height']

        # Red rectangle
        cv2.rectangle(
            frame,
            (x, y),
            (x + width, y + height),
            (0, 0, 255),  # Red
            2
        )

        # Confidence badge
        confidence_text = f"{result['confidence']:.0%}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        font_thickness = 2

        (text_width, text_height), _ = cv2.getTextSize(
            confidence_text,
            font,
            font_scale,
            font_thickness
        )

        badge_x = x + width - text_width - 8
        badge_y = y + text_height + 8

        # Background
        cv2.rectangle(
            frame,
            (badge_x - 4, badge_y - text_height - 4),
            (badge_x + text_width + 4, badge_y + 4),
            (0, 0, 255),  # Red background
            -1
        )

        # Text
        cv2.putText(
            frame,
            confidence_text,
            (badge_x, badge_y),
            font,
            font_scale,
            (255, 255, 255),  # White text
            font_thickness
        )

        # Save result
        output_path = image_path.replace('.jpg', '_detected.jpg')
        cv2.imwrite(output_path, frame)
        print(f"\nSaved result with overlays to: {output_path}")

        return True
    else:
        print(f"\n✗ FAILED: No white frame detected")
        return False

def main():
    """Test detection on all example frames."""
    test_files = [
        ("/Users/boweixiao/Downloads/msmacro_cv_frame_original.jpg",
         "Original captured frame"),
        ("/Users/boweixiao/Downloads/msmacro_cv_frame_redmark.jpg",
         "Frame with red rectangle marker"),
    ]

    print("=" * 70)
    print("YUYV-Based White Frame Detection Test")
    print("=" * 70)

    results = []
    for path, desc in test_files:
        success = test_frame(path, desc)
        results.append((desc, success))

    # Summary
    print(f"\n{'='*70}")
    print("Test Summary")
    print(f"{'='*70}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for desc, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {desc}")

    print(f"\nTotal: {passed}/{total} tests passed ({passed/total:.0%})")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
