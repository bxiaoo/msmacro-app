"""Platform abstraction utilities for cross-platform compatibility.

This module provides platform detection and abstracts platform-specific
functionality to enable msmacro to run on both Linux (production) and
macOS (development/testing).
"""

import platform
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Platform detection
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"

# Feature availability flags
HAS_EVDEV = False
HAS_HID_GADGET = False
HAS_V4L2 = False

# Try to import evdev (Linux-only dependency)
try:
    import evdev
    from evdev import ecodes as _real_ecodes
    HAS_EVDEV = True
    logger.debug("evdev module available")
except ImportError:
    evdev = None
    _real_ecodes = None
    if IS_LINUX:
        logger.warning("⚠️  evdev not available on Linux - keyboard features disabled")
    elif IS_MACOS:
        logger.debug("evdev not available (expected on macOS)")

# Check for Linux-specific hardware on Linux systems
if IS_LINUX:
    HAS_HID_GADGET = Path("/dev/hidg0").exists()
    HAS_V4L2 = any(Path("/dev").glob("video*"))

    if not HAS_HID_GADGET:
        logger.debug("HID gadget (/dev/hidg0) not found")
    if not HAS_V4L2:
        logger.debug("V4L2 devices not found")


def get_platform_info():
    """
    Get comprehensive platform and capability information.

    Returns:
        dict: Platform capabilities including hardware availability
    """
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": platform.python_version(),
        "is_macos": IS_MACOS,
        "is_linux": IS_LINUX,
        "is_windows": IS_WINDOWS,
        "has_evdev": HAS_EVDEV,
        "has_hid_gadget": HAS_HID_GADGET,
        "has_v4l2": HAS_V4L2,
        "video_backend": "AVFoundation" if IS_MACOS else ("V4L2" if HAS_V4L2 else "None"),
        "keyboard_input": "evdev" if HAS_EVDEV else "mock",
        "hid_output": "real" if HAS_HID_GADGET else "mock",
    }


def log_platform_info():
    """
    Log platform capabilities at startup.

    Provides clear visibility into which features are available
    and which are mocked/unavailable.
    """
    info = get_platform_info()

    logger.info("=" * 60)
    logger.info("Platform Information")
    logger.info("=" * 60)
    logger.info(f"OS: {info['platform']} {info['platform_release']}")
    logger.info(f"Python: {info['python_version']}")
    logger.info("-" * 60)
    logger.info(f"Video Backend: {info['video_backend']}")
    logger.info(f"Keyboard Input: {info['keyboard_input']}")
    logger.info(f"HID Output: {info['hid_output']}")
    logger.info("=" * 60)

    if IS_MACOS:
        logger.warning("🍎 Running on macOS - Development Mode")
        logger.warning("  ✅ Video capture: REAL (capture card)")
        logger.warning("  ✅ Object detection: REAL (full algorithms)")
        logger.warning("  ✅ Web UI: REAL (100% functional)")
        logger.warning("  ⚠️  Keyboard input: MOCK (simulated)")
        logger.warning("  ⚠️  HID output: MOCK (logged, not sent)")
        logger.info("  → For full functionality, deploy to Raspberry Pi / Linux")
    elif IS_LINUX:
        logger.info("🐧 Running on Linux - Production Mode")
        if not HAS_EVDEV:
            logger.error("  ❌ evdev not available - install python3-evdev")
        if not HAS_HID_GADGET:
            logger.warning("  ⚠️  HID gadget not configured - see USB gadget setup")
    else:
        logger.warning(f"⚠️  Unsupported platform: {platform.system()}")
        logger.warning("  msmacro is designed for Linux (production) and macOS (development)")


# Mock ecodes for macOS
class MockEcodes:
    """
    Mock evdev ecodes for macOS.

    Provides minimal ecodes compatibility for testing and development.
    Add more codes as needed based on actual usage.
    """
    # Event types
    EV_KEY = 1
    EV_REL = 2
    EV_ABS = 3
    EV_MSC = 4
    EV_SW = 5
    EV_LED = 17
    EV_SND = 18
    EV_REP = 20
    EV_FF = 21

    # Common key codes (add more as needed)
    KEY_RESERVED = 0
    KEY_ESC = 1
    KEY_1 = 2
    KEY_2 = 3
    KEY_3 = 4
    KEY_4 = 5
    KEY_5 = 6
    KEY_6 = 7
    KEY_7 = 8
    KEY_8 = 9
    KEY_9 = 10
    KEY_0 = 11
    KEY_MINUS = 12
    KEY_EQUAL = 13
    KEY_BACKSPACE = 14
    KEY_TAB = 15
    KEY_Q = 16
    KEY_W = 17
    KEY_E = 18
    KEY_R = 19
    KEY_T = 20
    KEY_Y = 21
    KEY_U = 22
    KEY_I = 23
    KEY_O = 24
    KEY_P = 25
    KEY_LEFTBRACE = 26
    KEY_RIGHTBRACE = 27
    KEY_ENTER = 28
    KEY_LEFTCTRL = 29
    KEY_A = 30
    KEY_S = 31
    KEY_D = 32
    KEY_F = 33
    KEY_G = 34
    KEY_H = 35
    KEY_J = 36
    KEY_K = 37
    KEY_L = 38
    KEY_SEMICOLON = 39
    KEY_APOSTROPHE = 40
    KEY_GRAVE = 41
    KEY_LEFTSHIFT = 42
    KEY_BACKSLASH = 43
    KEY_Z = 44
    KEY_X = 45
    KEY_C = 46
    KEY_V = 47
    KEY_B = 48
    KEY_N = 49
    KEY_M = 50
    KEY_COMMA = 51
    KEY_DOT = 52
    KEY_SLASH = 53
    KEY_RIGHTSHIFT = 54
    KEY_KPASTERISK = 55
    KEY_LEFTALT = 56
    KEY_SPACE = 57
    KEY_CAPSLOCK = 58

    # Function keys
    KEY_F1 = 59
    KEY_F2 = 60
    KEY_F3 = 61
    KEY_F4 = 62
    KEY_F5 = 63
    KEY_F6 = 64
    KEY_F7 = 65
    KEY_F8 = 66
    KEY_F9 = 67
    KEY_F10 = 68
    KEY_F11 = 87
    KEY_F12 = 88

    # Additional keys
    KEY_RIGHTCTRL = 97
    KEY_RIGHTALT = 100
    KEY_HOME = 102
    KEY_UP = 103
    KEY_PAGEUP = 104
    KEY_LEFT = 105
    KEY_RIGHT = 106
    KEY_END = 107
    KEY_DOWN = 108
    KEY_PAGEDOWN = 109
    KEY_INSERT = 110
    KEY_DELETE = 111

    # Modifier keys
    KEY_LEFTMETA = 125
    KEY_RIGHTMETA = 126


# Export appropriate ecodes based on platform
if HAS_EVDEV:
    ecodes = _real_ecodes
else:
    ecodes = MockEcodes()


def check_feature_available(feature: str) -> bool:
    """
    Check if a specific feature is available on current platform.

    Args:
        feature: Feature name ('evdev', 'hid_gadget', 'v4l2')

    Returns:
        bool: True if feature is available
    """
    feature_map = {
        'evdev': HAS_EVDEV,
        'hid_gadget': HAS_HID_GADGET,
        'v4l2': HAS_V4L2,
    }
    return feature_map.get(feature.lower(), False)


def require_feature(feature: str, operation: str = "This operation"):
    """
    Raise error if required feature is not available.

    Args:
        feature: Required feature name
        operation: Description of operation requiring the feature

    Raises:
        RuntimeError: If feature is not available
    """
    if not check_feature_available(feature):
        raise RuntimeError(
            f"{operation} requires {feature} which is not available on {platform.system()}. "
            f"Deploy to Linux/Raspberry Pi for full functionality."
        )
