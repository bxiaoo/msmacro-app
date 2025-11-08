#!/usr/bin/env python3
"""
Diagnostic script to troubleshoot CV capture issues.

This script checks:
- Video device availability
- Daemon status
- Capture configuration
- Permissions
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_video_devices():
    """Check for available video devices."""
    print("\n" + "="*70)
    print("1. VIDEO DEVICE CHECK")
    print("="*70)

    video_devices = list(Path("/dev").glob("video*"))
    if not video_devices:
        print("❌ NO video devices found in /dev/")
        print("\n  Possible causes:")
        print("  - No capture card connected")
        print("  - USB cable not plugged in")
        print("  - Capture card driver not loaded")
        return False

    print(f"✓ Found {len(video_devices)} video device(s):")
    for dev in sorted(video_devices):
        stat = dev.stat()
        readable = os.access(dev, os.R_OK)
        writable = os.access(dev, os.W_OK)
        perms = f"r{'✓' if readable else '✗'} w{'✓' if writable else '✗'}"
        print(f"  {dev.name}: {perms} (mode: {oct(stat.st_mode)[-3:]})")

    return True


def check_daemon_status():
    """Check if daemon is running."""
    print("\n" + "="*70)
    print("2. DAEMON STATUS")
    print("="*70)

    try:
        from msmacro.utils.config import SETTINGS
        socket_path = Path(getattr(SETTINGS, "socket_path", "/run/msmacro.sock"))

        # If default socket doesn't exist, try common alternatives
        if not socket_path.exists():
            alternatives = [
                Path("/run/user/1000/msmacro.sock"),  # systemd user runtime
                Path(f"/run/user/{os.getuid()}/msmacro.sock"),  # current user
            ]

            for alt_path in alternatives:
                if alt_path.exists():
                    print(f"ℹ️  Default socket not found: {socket_path}")
                    print(f"✓ Found socket at: {alt_path}")
                    socket_path = alt_path
                    # Update environment for subsequent calls
                    os.environ["MSMACRO_SOCKET"] = str(socket_path)
                    break
            else:
                print(f"❌ Daemon socket not found: {socket_path}")
                print("\n  Also checked:")
                for alt_path in alternatives:
                    print(f"    {alt_path}")
                print("\n  Start daemon with:")
                print("    python -m msmacro daemon")
                print("  OR")
                print("    sudo systemctl start msmacro")
                print("\n  If using systemd, set environment variable:")
                print("    export MSMACRO_SOCKET=/run/user/1000/msmacro.sock")
                return False

        print(f"✓ Daemon socket exists: {socket_path}")

        # Try to connect and get status
        import asyncio
        from msmacro.io.ipc import send

        async def get_status():
            return await send(str(socket_path), {"cmd": "status"})

        status = asyncio.run(get_status())
        print(f"✓ Daemon is running (mode: {status.get('mode', 'unknown')})")
        return True

    except Exception as e:
        print(f"❌ Failed to communicate with daemon: {e}")
        return False


def check_cv_capture():
    """Check CV capture status."""
    print("\n" + "="*70)
    print("3. CV CAPTURE STATUS")
    print("="*70)

    try:
        from msmacro.cv.capture import get_capture_instance

        capture = get_capture_instance()
        status = capture.get_status()

        print(f"  Connected: {status.get('connected')}")
        print(f"  Capturing: {status.get('capturing')}")
        print(f"  Has frame: {status.get('has_frame')}")
        print(f"  Frames captured: {status.get('frames_captured')}")
        print(f"  Frames failed: {status.get('frames_failed')}")

        if status.get('last_error'):
            print(f"\n  ⚠️  Last error:")
            print(f"    {status['last_error'].get('message')}")
            if 'detail' in status['last_error']:
                print(f"    Detail: {status['last_error']['detail']}")

        if status.get('device'):
            print(f"\n  Device:")
            print(f"    Path: {status['device'].get('path')}")
            print(f"    Name: {status['device'].get('name')}")

        if status.get('capturing') and status.get('has_frame'):
            print("\n✓ CV capture is working!")
            return True
        elif not status.get('capturing'):
            print("\n❌ CV capture is NOT running")
            print("\n  Start with:")
            print("    python -m msmacro ctl cv-start")
            return False
        else:
            print("\n⚠️  CV capture is running but no frames yet")
            print("   Wait a few seconds for first frame...")
            return False

    except Exception as e:
        print(f"❌ Failed to get CV capture status: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_map_config():
    """Check map configuration."""
    print("\n" + "="*70)
    print("4. MAP CONFIGURATION")
    print("="*70)

    try:
        from msmacro.cv.map_config import get_manager

        manager = get_manager()
        active_config = manager.get_active_config()

        if active_config is None:
            print("⚠️  No active map configuration")
            print("\n  This is REQUIRED for object detection!")
            print("\n  Create a map config via web UI:")
            print("    http://localhost:8787")
            print("    Navigate to: CV Capture → Map Configuration")
            print("    Set the minimap position and dimensions")
            return False

        print(f"✓ Active map config: '{active_config.name}'")
        print(f"  Position: ({active_config.tl_x}, {active_config.tl_y})")
        print(f"  Size: {active_config.width}x{active_config.height}")
        return True

    except Exception as e:
        print(f"❌ Failed to check map config: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_frame_capture():
    """Try to capture a test frame."""
    print("\n" + "="*70)
    print("5. TEST FRAME CAPTURE")
    print("="*70)

    try:
        from msmacro.cv.capture import get_capture_instance
        import asyncio

        capture = get_capture_instance()

        # Auto-start if not running
        if not capture.get_status().get('capturing'):
            print("  Starting CV capture...")

            async def start_capture():
                await capture.start()

            try:
                asyncio.run(start_capture())
                print("  ✓ CV capture started")
            except Exception as e:
                print(f"  ❌ Failed to start capture: {e}")
                return False

        # Wait for frame
        import time
        print("  Waiting for first frame...")
        for i in range(10):
            time.sleep(0.5)
            result = capture.get_latest_frame()
            if result is not None:
                frame_data, metadata = result
                print(f"\n✓ Successfully captured frame!")
                print(f"  Size: {metadata.width}x{metadata.height}")
                print(f"  Data size: {len(frame_data)} bytes")
                print(f"  Region detected: {metadata.region_detected}")
                if metadata.region_detected:
                    print(f"  Region: ({metadata.region_x}, {metadata.region_y}) "
                          f"{metadata.region_width}x{metadata.region_height}")
                return True

        print("  ❌ Timed out waiting for frame")
        return False

    except Exception as e:
        print(f"❌ Frame capture test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*70)
    print("CV CAPTURE DIAGNOSTICS")
    print("="*70)

    results = {
        "video_devices": check_video_devices(),
        "daemon": check_daemon_status(),
        "cv_capture": check_cv_capture(),
        "map_config": check_map_config(),
        "test_capture": test_frame_capture(),
    }

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status:8} {name}")

    all_passed = all(results.values())

    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL CHECKS PASSED - CV capture should work!")
        print("\nYou can now:")
        print("  1. Access web UI at http://localhost:8787")
        print("  2. Navigate to Object Detection → Calibrate")
        print("  3. Click on player dots to calibrate")
    else:
        print("❌ SOME CHECKS FAILED - Fix issues above")
        print("\nCommon fixes:")
        print("  - Ensure capture card is connected")
        print("  - Start daemon: python -m msmacro daemon")
        print("  - Start CV capture: python -m msmacro ctl cv-start")
        print("  - Create map config via web UI")
    print("="*70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
