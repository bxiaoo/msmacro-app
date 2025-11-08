#!/usr/bin/env python3
"""
Test the calibration frame endpoint directly.

This checks if the /api/cv/frame-lossless endpoint is working.
"""

import sys
import requests
from pathlib import Path

def test_frame_endpoint(base_url="http://localhost:8787"):
    """Test the frame endpoint."""
    print("=" * 70)
    print("TESTING CALIBRATION FRAME ENDPOINT")
    print("=" * 70)

    endpoint = f"{base_url}/api/cv/frame-lossless"
    print(f"\nEndpoint: {endpoint}")

    try:
        print("\nRequesting frame...")
        response = requests.get(endpoint, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"Content-Length: {len(response.content)} bytes")

        if response.status_code == 200:
            if response.headers.get('Content-Type') == 'image/png':
                print("\n✓ SUCCESS! Frame endpoint is working")
                print(f"  Received {len(response.content)} bytes of PNG data")

                # Optionally save the frame for inspection
                output_path = Path("/tmp/test_frame.png")
                output_path.write_bytes(response.content)
                print(f"  Saved test frame to: {output_path}")

                return True
            else:
                print(f"\n❌ FAIL: Wrong content type: {response.headers.get('Content-Type')}")
                print(f"Response body: {response.text[:500]}")
                return False
        else:
            print(f"\n❌ FAIL: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ CONNECTION ERROR: Cannot connect to {base_url}")
        print(f"   Is the web server running?")
        print(f"   Error: {e}")
        return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cv_status(base_url="http://localhost:8787"):
    """Test the CV status endpoint."""
    print("\n" + "=" * 70)
    print("TESTING CV STATUS ENDPOINT")
    print("=" * 70)

    endpoint = f"{base_url}/api/cv/status"
    print(f"\nEndpoint: {endpoint}")

    try:
        response = requests.get(endpoint, timeout=5)

        if response.status_code == 200:
            data = response.json()
            print("\n✓ CV Status:")
            print(f"  Connected: {data.get('connected')}")
            print(f"  Capturing: {data.get('capturing')}")
            print(f"  Has frame: {data.get('has_frame')}")
            print(f"  Frames captured: {data.get('frames_captured')}")

            if data.get('device'):
                print(f"\n  Device:")
                print(f"    Path: {data['device'].get('path')}")
                print(f"    Name: {data['device'].get('name')}")

            return data.get('capturing') and data.get('has_frame')
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test calibration endpoints")
    parser.add_argument("--url", default="http://localhost:8787",
                       help="Base URL (default: http://localhost:8787)")
    args = parser.parse_args()

    print(f"\nTesting against: {args.url}")

    # Test CV status first
    status_ok = test_cv_status(args.url)

    # Test frame endpoint
    frame_ok = test_frame_endpoint(args.url)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  CV Status: {'✓ PASS' if status_ok else '✗ FAIL'}")
    print(f"  Frame Endpoint: {'✓ PASS' if frame_ok else '✗ FAIL'}")
    print("=" * 70 + "\n")

    if frame_ok:
        print("✓ Calibration should work! Try refreshing the web UI.")
    else:
        print("❌ Frame endpoint not working. Check daemon logs:")
        print("   journalctl -u msmacro -f")

    return 0 if (status_ok and frame_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
