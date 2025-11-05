"""
Unit tests for status command handler.

These tests demonstrate the pattern for testing command handlers
using mocked daemon instances.
"""

import pytest
from pathlib import Path
from msmacro.daemon.status_commands import StatusCommandHandler


class MockDaemon:
    """
    Mock daemon instance for testing.

    Only includes the attributes accessed by status_commands.
    """

    def __init__(self):
        self.mode = "BRIDGE"
        self.rec_dir = Path("/tmp/test_recordings")
        self.evdev_path = "/dev/input/event0"
        self._last_actions = None
        self._current_playing_file = None

        # Ensure test recording directory exists
        self.rec_dir.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def mock_daemon():
    """Fixture providing a mock daemon instance."""
    return MockDaemon()


@pytest.fixture
def handler(mock_daemon):
    """Fixture providing a status command handler."""
    return StatusCommandHandler(mock_daemon)


class TestStatusCommand:
    """Test suite for the status command handler."""

    @pytest.mark.asyncio
    async def test_status_basic(self, handler, mock_daemon):
        """Test basic status command response."""
        result = await handler.status({})

        # Verify required keys
        assert "mode" in result
        assert "record_dir" in result
        assert "keyboard" in result
        assert "have_last_actions" in result
        assert "files" in result
        assert "current_playing_file" in result

        # Verify values
        assert result["mode"] == "BRIDGE"
        assert str(mock_daemon.rec_dir) in result["record_dir"]
        assert result["have_last_actions"] is False
        assert isinstance(result["files"], list)

    @pytest.mark.asyncio
    async def test_status_with_last_actions(self, handler, mock_daemon):
        """Test status when recording in memory."""
        mock_daemon._last_actions = [{"usage": 30, "press": 0.0, "dur": 0.1}]

        result = await handler.status({})

        assert result["have_last_actions"] is True

    @pytest.mark.asyncio
    async def test_status_with_files(self, handler, mock_daemon):
        """Test status with recording files present."""
        # Create test recording file
        test_file = mock_daemon.rec_dir / "test.json"
        test_file.write_text('{"actions": []}')

        result = await handler.status({})

        assert len(result["files"]) > 0
        assert any(f["name"] == "test.json" for f in result["files"])

        # Cleanup
        test_file.unlink()

    @pytest.mark.asyncio
    async def test_status_different_modes(self, handler, mock_daemon):
        """Test status reflects current daemon mode."""
        modes = ["BRIDGE", "RECORDING", "PLAYING", "POSTRECORD"]

        for mode in modes:
            mock_daemon.mode = mode
            result = await handler.status({})
            assert result["mode"] == mode

    @pytest.mark.asyncio
    async def test_status_with_playing_file(self, handler, mock_daemon):
        """Test status during playback."""
        mock_daemon.mode = "PLAYING"
        mock_daemon._current_playing_file = "/path/to/recording.json"

        result = await handler.status({})

        assert result["current_playing_file"] == "/path/to/recording.json"


# Template for other test files:
"""
To create tests for other command handlers, follow this pattern:

1. Create MockDaemon with only needed attributes
2. Create fixtures for mock_daemon and handler
3. Write test methods for each command:
   - Happy path (valid inputs, expected outputs)
   - Error cases (missing params, invalid state)
   - Edge cases (empty lists, None values)

Example test file names:
- test_file_commands.py
- test_recording_commands.py
- test_playback_commands.py
- test_skills_commands.py
- test_cv_commands.py
- test_command_dispatcher.py

Run tests with:
  pytest tests/daemon/ -v
"""
