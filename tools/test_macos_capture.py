#!/usr/bin/env python3
"""
macOS Video Capture Card Testing Tool

This script helps test and debug USB HDMI capture cards on macOS.
It provides:
- Device detection and enumeration
- Live video preview with detection overlays
- Format compatibility testing
- Performance benchmarking
- Object detection verification

Usage:
    python tools/test_macos_capture.py [--device INDEX] [--no-preview] [--test-detection]
"""

import sys
import argparse
import logging
import time
from pathlib import Path

# Add parent directory to path to import msmacro
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from msmacro.cv.device import list_video_devices, find_capture_device
from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_device_enumeration():
    """Test video device detection."""
    print("\n" + "=" * 60)
    print("DEVICE ENUMERATION TEST")
    print("=" * 60)

    devices = list_video_devices()

    if not devices:
        print("❌ No video devices found!")
        print("\nTroubleshooting:")
        print("1. Ensure USB capture card is plugged in")
        print("2. Check System Settings → Privacy & Security → Camera")
        print("3. Grant camera access to Terminal/Python")
        print("4. Try different USB ports")
        return None

    print(f"\n✅ Found {len(devices)} video device(s):\n")

    for i, device in enumerate(devices):
        device_type = "🔌 USB Capture Card" if device.is_usb else "📷 Built-in Camera"
        print(f"{i + 1}. {device_type}")
        print(f"   Name: {device.name}")
        print(f"   Path: {device.device_path}")
        print(f"   Index: {device.device_index}")
        print()

    # Find best capture device
    best_device = find_capture_device()
    if best_device:
        print(f"🎯 Best device selected: {best_device.name} (index {best_device.device_index})")
        return best_device
    else:
        print("❌ Could not select a suitable capture device")
        return None


def test_device_access(device_index):
    """Test if we can open and read from a device."""
    print("\n" + "=" * 60)
    print(f"DEVICE ACCESS TEST (Index {device_index})")
    print("=" * 60)

    try:
        cap = cv2.VideoCapture(device_index, cv2.CAP_AVFOUNDATION)

        if not cap.isOpened():
            print(f"❌ Cannot open device {device_index}")
            print("\nPossible issues:")
            print("- Device is already in use by another application")
            print("- Camera permissions not granted")
            print("- Device disconnected")
            return None

        print(f"✅ Device opened successfully")

        # Get device properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        backend = cap.getBackendName()

        print(f"\nDevice Properties:")
        print(f"  Resolution: {width}x{height}")
        print(f"  FPS: {fps}")
        print(f"  Backend: {backend}")

        # Try to read a frame
        print(f"\nAttempting to read test frame...")
        ret, frame = cap.read()

        if ret and frame is not None:
            print(f"✅ Successfully read frame: {frame.shape}")
            return cap
        else:
            print(f"❌ Failed to read frame from device")
            cap.release()
            return None

    except Exception as e:
        print(f"❌ Error accessing device: {e}")
        return None


def test_format_compatibility(cap):
    """Test different video format configurations."""
    print("\n" + "=" * 60)
    print("FORMAT COMPATIBILITY TEST")
    print("=" * 60)

    formats_to_test = [
        ("1280x720 (720p)", 1280, 720),
        ("1920x1080 (1080p)", 1920, 1080),
        ("640x480 (VGA)", 640, 480),
    ]

    compatible_formats = []

    for format_name, width, height in formats_to_test:
        print(f"\nTesting {format_name}...")

        # Set resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        # Try to read a frame
        ret, frame = cap.read()

        if ret and frame is not None:
            actual_h, actual_w = frame.shape[:2]
            if actual_w == width and actual_h == height:
                print(f"  ✅ Supported: {actual_w}x{actual_h}")
                compatible_formats.append((format_name, width, height))
            else:
                print(f"  ⚠️  Requested {width}x{height}, got {actual_w}x{actual_h}")
                compatible_formats.append((f"{format_name} (scaled)", actual_w, actual_h))
        else:
            print(f"  ❌ Not supported")

    # Reset to 1280x720 (default for msmacro)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print(f"\n📊 Compatible formats: {len(compatible_formats)}")
    return compatible_formats


def test_object_detection(cap):
    """Test object detection on live frames."""
    print("\n" + "=" * 60)
    print("OBJECT DETECTION TEST")
    print("=" * 60)

    # Load detection config
    try:
        config = DetectorConfig.load()
        print(f"✅ Loaded detection config")
        print(f"  Player HSV: {config.player_hsv_lower} - {config.player_hsv_upper}")
        print(f"  Other player ranges: {len(config.other_player_hsv_ranges)}")
    except Exception as e:
        print(f"⚠️  Could not load config: {e}")
        print("  Using default configuration")
        config = DetectorConfig()

    detector = MinimapObjectDetector(config)

    # Capture a test frame
    ret, frame = cap.read()
    if not ret or frame is None:
        print("❌ Cannot read frame for detection test")
        return

    # Simulate minimap crop (you may need to adjust these coordinates)
    minimap_region = (68, 56, 340, 86)  # (x, y, w, h)
    x, y, w, h = minimap_region
    h_frame, w_frame = frame.shape[:2]

    if x + w <= w_frame and y + h <= h_frame:
        minimap_crop = frame[y:y+h, x:x+w]
        print(f"✅ Extracted minimap region: {minimap_crop.shape}")

        # Run detection
        print("\nRunning object detection...")
        start_time = time.time()
        result = detector.detect(minimap_crop)
        detection_time = (time.time() - start_time) * 1000

        print(f"⏱️  Detection time: {detection_time:.2f}ms")

        if result.player.detected:
            print(f"✅ Player detected at ({result.player.x}, {result.player.y})")
            print(f"   Confidence: {result.player.confidence:.2f}")
        else:
            print(f"⚠️  No player detected (normal if no yellow dot in minimap)")

        if result.other_players.detected:
            print(f"✅ Other players detected: {result.other_players.count}")
        else:
            print(f"⚠️  No other players detected (normal if no red dots in minimap)")

    else:
        print(f"⚠️  Minimap region out of bounds for {w_frame}x{h_frame} frame")
        print(f"   Region: {minimap_region}")


def live_preview(cap, with_detection=False):
    """Show live video preview with optional detection overlays."""
    print("\n" + "=" * 60)
    print("LIVE PREVIEW")
    print("=" * 60)
    print("\nShowing live preview...")
    print("Press 'q' to quit")
    print("Press 's' to save screenshot")
    print("Press 'd' to toggle detection overlay")
    print()

    if with_detection:
        try:
            config = DetectorConfig.load()
            detector = MinimapObjectDetector(config)
            detection_enabled = True
            print("✅ Object detection enabled")
        except Exception as e:
            print(f"⚠️  Detection disabled: {e}")
            detection_enabled = False
    else:
        detection_enabled = False

    frame_count = 0
    fps_start = time.time()
    fps = 0

    while True:
        ret, frame = cap.read()

        if not ret or frame is None:
            print("❌ Failed to read frame")
            break

        # Calculate FPS
        frame_count += 1
        if frame_count % 30 == 0:
            fps_time = time.time() - fps_start
            fps = 30 / fps_time if fps_time > 0 else 0
            fps_start = time.time()

        # Create display frame
        display_frame = frame.copy()
        h, w = frame.shape[:2]

        # Draw info overlay
        cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(display_frame, f"Resolution: {w}x{h}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Draw minimap region outline
        minimap_x, minimap_y, minimap_w, minimap_h = 68, 56, 340, 86
        if minimap_x + minimap_w <= w and minimap_y + minimap_h <= h:
            cv2.rectangle(display_frame,
                          (minimap_x, minimap_y),
                          (minimap_x + minimap_w, minimap_y + minimap_h),
                          (255, 0, 0), 2)
            cv2.putText(display_frame, "Minimap Region", (minimap_x, minimap_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

        # Run object detection if enabled
        if detection_enabled:
            minimap_crop = frame[minimap_y:minimap_y+minimap_h, minimap_x:minimap_x+minimap_w]
            result = detector.detect(minimap_crop)

            # Draw detection results on minimap
            if result.player.detected:
                player_x = minimap_x + result.player.x
                player_y = minimap_y + result.player.y
                cv2.circle(display_frame, (player_x, player_y), 6, (0, 255, 255), 2)
                cv2.putText(display_frame, "Player", (player_x + 10, player_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            if result.other_players.detected:
                for pos in result.other_players.positions:
                    other_x = minimap_x + pos['x']
                    other_y = minimap_y + pos['y']
                    cv2.circle(display_frame, (other_x, other_y), 5, (0, 0, 255), 2)

            cv2.putText(display_frame, "Detection: ON", (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        # Show frame
        cv2.imshow('macOS Capture Card Test - Press Q to quit', display_frame)

        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("\nQuitting preview...")
            break
        elif key == ord('s'):
            # Save screenshot
            filename = f"screenshot_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            print(f"📸 Screenshot saved: {filename}")
        elif key == ord('d'):
            # Toggle detection
            if with_detection:
                detection_enabled = not detection_enabled
                status = "ON" if detection_enabled else "OFF"
                print(f"Detection: {status}")

    cv2.destroyAllWindows()


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test USB HDMI capture card on macOS")
    parser.add_argument('--device', type=int, help='Device index to use (overrides auto-detection)')
    parser.add_argument('--no-preview', action='store_true', help='Skip live preview')
    parser.add_argument('--test-detection', action='store_true', help='Enable object detection testing')
    args = parser.parse_args()

    print("🍎 macOS Video Capture Card Testing Tool")
    print("=" * 60)

    # Step 1: Enumerate devices
    best_device = test_device_enumeration()

    if args.device is not None:
        device_index = args.device
        print(f"\n🎯 Using manually specified device: {device_index}")
    elif best_device:
        device_index = best_device.device_index
    else:
        print("\n❌ No suitable device found. Exiting.")
        return 1

    # Step 2: Test device access
    cap = test_device_access(device_index)
    if not cap:
        return 1

    # Step 3: Test format compatibility
    test_format_compatibility(cap)

    # Step 4: Test object detection (if requested)
    if args.test_detection:
        test_object_detection(cap)

    # Step 5: Live preview (if not disabled)
    if not args.no_preview:
        live_preview(cap, with_detection=args.test_detection)
    else:
        print("\n⏭️  Skipping live preview (--no-preview)")

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()

    print("\n" + "=" * 60)
    print("✅ Testing complete!")
    print("\nNext steps:")
    print("1. If capture works, you can now run calibration via web UI")
    print("2. Start daemon: python -m msmacro daemon")
    print("3. Access web UI: http://localhost:8787")
    print("4. Navigate to CV settings to calibrate colors")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
