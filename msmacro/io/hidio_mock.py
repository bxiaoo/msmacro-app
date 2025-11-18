"""Mock HID output for macOS development.

This module provides mock HID keyboard output functionality for testing
and development on macOS where /dev/hidg0 USB gadget is not available.
"""

import logging
import time
from typing import List, Dict, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class MockHIDWriter:
    """
    Mock HID writer for macOS development.

    Logs HID reports instead of sending them to /dev/hidg0 USB gadget.
    Useful for:
    - Testing playback logic without hardware
    - Developing skill injection on macOS
    - Verifying keystroke sequences
    - Debugging macro timing

    All HID reports are logged and optionally saved to a file for analysis.
    """

    def __init__(self, hidg_path: str = "/dev/hidg0"):
        """
        Initialize mock HID writer.

        Args:
            hidg_path: Path to HID gadget device (not used on macOS, for compatibility)
        """
        self.hidg_path = hidg_path
        self._reports = []
        self._is_open = True
        self._report_count = 0

        # Create log file in user's home directory
        self._log_file = Path.home() / ".msmacro" / "hid_mock.log"
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

        logger.warning(f"🔶 MOCK HID Writer Initialized: {hidg_path}")
        logger.info("  → Keystrokes will be LOGGED but NOT actually sent")
        logger.info(f"  → HID reports logged to: {self._log_file}")
        logger.info("  → For real keystroke output, deploy to Linux/Raspberry Pi")

        # Initialize log file with header
        with open(self._log_file, 'w') as f:
            f.write("# msmacro Mock HID Reports Log\n")
            f.write(f"# Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Platform: macOS (Development Mode)\n")
            f.write("# Format: timestamp, modmask, keys, human_readable\n")
            f.write("#" + "=" * 70 + "\n\n")

    def send(self, modmask: int, keys: List[int]) -> None:
        """
        Log HID report instead of sending to device.

        Args:
            modmask: Modifier key bitmask (8 bits)
                - Bit 0: Left Control
                - Bit 1: Left Shift
                - Bit 2: Left Alt
                - Bit 3: Left Meta (Windows/Cmd)
                - Bit 4: Right Control
                - Bit 5: Right Shift
                - Bit 6: Right Alt
                - Bit 7: Right Meta
            keys: List of key usage IDs (up to 6 keys)
        """
        # Truncate to 6 keys max (HID keyboard report limitation)
        keys_truncated = keys[:6] if keys else []

        # Pad with zeros to 6 keys
        keys_padded = keys_truncated + [0] * (6 - len(keys_truncated))

        # Create report record
        report = {
            "timestamp": time.time(),
            "report_num": self._report_count,
            "modmask": modmask,
            "keys": keys_padded,
            "keys_sent": len(keys_truncated),
        }

        self._reports.append(report)
        self._report_count += 1

        # Format human-readable representation
        mod_str = self._format_modifiers(modmask)
        key_str = self._format_keys(keys_truncated)
        human_readable = f"{mod_str} + {key_str}" if mod_str else key_str

        # Log to console (debug level)
        logger.debug(f"MOCK HID #{self._report_count}: {human_readable}")

        # Log to file
        self._log_to_file(report, human_readable)

    def all_up(self) -> None:
        """
        Log all keys released (empty report).

        This sends a report with no modifiers and no keys pressed.
        """
        logger.debug("MOCK HID: All keys up (release all)")

        report = {
            "timestamp": time.time(),
            "report_num": self._report_count,
            "modmask": 0,
            "keys": [0, 0, 0, 0, 0, 0],
            "keys_sent": 0,
        }

        self._reports.append(report)
        self._report_count += 1

        # Log to file
        self._log_to_file(report, "ALL KEYS UP")

    def close(self) -> None:
        """
        Close the mock HID writer.
        """
        self._is_open = False
        logger.debug("MOCK HID: Closed")

        # Write summary to log file
        with open(self._log_file, 'a') as f:
            f.write("\n" + "#" + "=" * 70 + "\n")
            f.write(f"# Session ended: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total reports sent: {self._report_count}\n")
            f.write("#" + "=" * 70 + "\n")

    def _format_modifiers(self, modmask: int) -> str:
        """
        Format modifier bitmask as human-readable string.

        Args:
            modmask: Modifier bitmask

        Returns:
            str: Human-readable modifier string (e.g., "LCTRL+LSHIFT")
        """
        mods = []
        if modmask & 0x01:
            mods.append("LCTRL")
        if modmask & 0x02:
            mods.append("LSHIFT")
        if modmask & 0x04:
            mods.append("LALT")
        if modmask & 0x08:
            mods.append("LMETA")
        if modmask & 0x10:
            mods.append("RCTRL")
        if modmask & 0x20:
            mods.append("RSHIFT")
        if modmask & 0x40:
            mods.append("RALT")
        if modmask & 0x80:
            mods.append("RMETA")

        return "+".join(mods) if mods else ""

    def _format_keys(self, keys: List[int]) -> str:
        """
        Format key usage IDs as human-readable string.

        Args:
            keys: List of HID usage IDs

        Returns:
            str: Human-readable key string (e.g., "A, B, C")
        """
        if not keys:
            return "(none)"

        # Filter out zero keys
        non_zero_keys = [k for k in keys if k != 0]

        if not non_zero_keys:
            return "(none)"

        # Map some common usage IDs to names (add more as needed)
        key_names = {
            4: "A", 5: "B", 6: "C", 7: "D", 8: "E", 9: "F", 10: "G",
            11: "H", 12: "I", 13: "J", 14: "K", 15: "L", 16: "M", 17: "N",
            18: "O", 19: "P", 20: "Q", 21: "R", 22: "S", 23: "T", 24: "U",
            25: "V", 26: "W", 27: "X", 28: "Y", 29: "Z",
            30: "1", 31: "2", 32: "3", 33: "4", 34: "5",
            35: "6", 36: "7", 37: "8", 38: "9", 39: "0",
            40: "ENTER", 41: "ESC", 42: "BACKSPACE", 43: "TAB", 44: "SPACE",
            58: "F1", 59: "F2", 60: "F3", 61: "F4", 62: "F5", 63: "F6",
            64: "F7", 65: "F8", 66: "F9", 67: "F10", 68: "F11", 69: "F12",
        }

        key_strs = [key_names.get(k, f"0x{k:02X}") for k in non_zero_keys]
        return ", ".join(key_strs)

    def _log_to_file(self, report: Dict, human_readable: str):
        """
        Append report to log file.

        Args:
            report: Report dictionary
            human_readable: Human-readable representation
        """
        try:
            with open(self._log_file, 'a') as f:
                timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(report["timestamp"]))
                f.write(f"[{timestamp_str}] #{report['report_num']:05d} | {human_readable}\n")
        except Exception as e:
            logger.error(f"MOCK HID: Failed to write to log file: {e}")

    # Testing/Analysis Helper Methods

    def get_sent_reports(self) -> List[Dict]:
        """
        Get all sent HID reports for testing/analysis.

        Returns:
            List[Dict]: Copy of all reports sent since initialization
        """
        return self._reports.copy()

    def clear_reports(self) -> None:
        """
        Clear report history (useful for testing).
        """
        self._reports.clear()
        self._report_count = 0
        logger.debug("MOCK HID: Report history cleared")

    def get_report_count(self) -> int:
        """
        Get total number of reports sent.

        Returns:
            int: Number of reports sent
        """
        return self._report_count

    def export_reports_json(self, filepath: Optional[Path] = None) -> Path:
        """
        Export all reports to JSON file for analysis.

        Args:
            filepath: Output file path (default: ~/.msmacro/hid_reports.json)

        Returns:
            Path: Path to exported file
        """
        if filepath is None:
            filepath = Path.home() / ".msmacro" / "hid_reports.json"

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(self._reports, f, indent=2)

        logger.info(f"MOCK HID: Exported {len(self._reports)} reports to {filepath}")
        return filepath

    def get_keystroke_summary(self) -> Dict:
        """
        Get summary statistics of keystrokes sent.

        Returns:
            Dict: Summary statistics
        """
        total_keystrokes = sum(r["keys_sent"] for r in self._reports)
        unique_keys = set()

        for report in self._reports:
            for key in report["keys"]:
                if key != 0:
                    unique_keys.add(key)

        return {
            "total_reports": len(self._reports),
            "total_keystrokes": total_keystrokes,
            "unique_keys": len(unique_keys),
            "reports_with_modifiers": sum(1 for r in self._reports if r["modmask"] != 0),
        }
