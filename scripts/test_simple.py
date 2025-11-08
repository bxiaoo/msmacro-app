#!/usr/bin/env python3
"""Simple test to check if Python is working."""

print("=" * 70)
print("SIMPLE TEST - Starting...")
print("=" * 70)

import sys
print(f"Python version: {sys.version}")

try:
    print("\n1. Testing basic imports...")
    from pathlib import Path
    print("  ✓ pathlib works")

    import os
    print("  ✓ os works")

    print("\n2. Testing socket detection...")
    socket_paths = [
        "/run/user/1000/msmacro.sock",
        "/run/msmacro.sock",
    ]

    for path in socket_paths:
        exists = Path(path).exists()
        print(f"  {path}: {'✓ EXISTS' if exists else '✗ not found'}")

    print("\n3. Testing msmacro imports...")
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from msmacro.utils.config import SETTINGS
    print(f"  ✓ SETTINGS imported")
    print(f"  Socket path: {SETTINGS.socket_path}")

    print("\n4. Testing video devices...")
    video_devices = list(Path("/dev").glob("video*"))
    print(f"  Found {len(video_devices)} video device(s)")
    for dev in video_devices:
        print(f"    - {dev}")

    print("\n" + "=" * 70)
    print("✓ SIMPLE TEST COMPLETED")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
