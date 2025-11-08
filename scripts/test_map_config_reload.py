#!/usr/bin/env python3
"""
Test map configuration reload via daemon IPC.

This script tests if the daemon can reload the map configuration.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_reload_config():
    """Test reloading map config via daemon."""
    from msmacro.io.ipc import send
    from msmacro.cv.map_config import get_manager

    print("=" * 70)
    print("MAP CONFIG RELOAD TEST")
    print("=" * 70)

    # Find socket path
    socket_path = os.environ.get("MSMACRO_SOCKET", "/run/msmacro.sock")
    alt_socket = f"/run/user/{os.getuid()}/msmacro.sock"

    if not Path(socket_path).exists() and Path(alt_socket).exists():
        socket_path = alt_socket
        print(f"Using socket: {socket_path}")

    if not Path(socket_path).exists():
        print(f"❌ Socket not found: {socket_path}")
        print(f"   Also tried: {alt_socket}")
        return 1

    print(f"✓ Socket: {socket_path}\n")

    # Step 1: Check local config file
    print("1. CHECKING LOCAL CONFIG FILE")
    print("-" * 70)

    manager = get_manager()
    config_file = manager._config_file

    print(f"Config file: {config_file}")
    print(f"File exists: {config_file.exists()}")

    if config_file.exists():
        print(f"File size: {config_file.stat().st_size} bytes")
        print(f"Modified: {config_file.stat().st_mtime}")

        # Show contents
        import json
        with open(config_file) as f:
            data = json.load(f)

        print(f"\nConfigs in file: {len(data.get('configs', []))}")
        print(f"Active config name: {data.get('active_config', '(none)')}")

        for cfg in data.get('configs', []):
            active_marker = " ✓ ACTIVE" if cfg.get('is_active') else ""
            print(f"  - {cfg['name']}: {cfg['width']}x{cfg['height']} at ({cfg['tl_x']}, {cfg['tl_y']}){active_marker}")

    active_config = manager.get_active_config()
    if active_config:
        print(f"\n✓ Manager reports active config: {active_config.name}")
    else:
        print(f"\n✗ Manager reports NO active config")

    # Step 2: Check daemon's CV status
    print("\n2. CHECKING DAEMON CV STATUS")
    print("-" * 70)

    try:
        status = await send(socket_path, {"cmd": "cv_status"})

        print(f"CV Capturing: {status.get('capturing')}")
        print(f"Has frame: {status.get('has_frame')}")

        # CV status doesn't include map config info, so we need to check via capture directly

    except Exception as e:
        print(f"❌ Failed to get CV status: {e}")

    # Step 3: Send reload command
    print("\n3. SENDING RELOAD COMMAND TO DAEMON")
    print("-" * 70)

    try:
        print("Sending cv_reload_config command...")
        result = await send(socket_path, {"cmd": "cv_reload_config"})

        print(f"✓ Daemon responded successfully")
        print(f"Response: {result}")

        if result.get('reloaded'):
            print(f"\n✓ Config was reloaded!")

            active = result.get('active_config')
            if active:
                print(f"  Active config: {active.get('name')}")
                print(f"  Position: ({active.get('tl_x')}, {active.get('tl_y')})")
                print(f"  Size: {active.get('width')}x{active.get('height')}")
            else:
                print(f"  ⚠️  No active config reported by daemon")
        else:
            print(f"\n⚠️  Daemon did not reload config")

    except Exception as e:
        print(f"❌ Failed to reload config: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Step 4: Verify reload worked
    print("\n4. VERIFICATION")
    print("-" * 70)

    try:
        # Get CV status again to see if config is active
        status = await send(socket_path, {"cmd": "cv_status"})

        # Unfortunately cv_status doesn't include map config info
        # We need to check via another method

        print("Reload command completed successfully.")
        print("\nNext steps:")
        print("  1. Check daemon logs: journalctl -u msmacro -n 20")
        print("  2. Look for 'Loaded active map config' or 'No active map config'")
        print("  3. Test frame capture to see if region is detected")

    except Exception as e:
        print(f"❌ Verification failed: {e}")

    print("\n" + "=" * 70)
    return 0


def main():
    try:
        return asyncio.run(test_reload_config())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
