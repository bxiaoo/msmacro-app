"""
Daemon utilities and helpers for CV-AUTO mode.
"""

# Import run_daemon and MacroDaemon from the sibling daemon.py file
# We need to use importlib because Python treats 'daemon' as this package now
import importlib.util
import sys
from pathlib import Path

_daemon_py_path = Path(__file__).parent.parent / 'daemon.py'
_spec = importlib.util.spec_from_file_location('msmacro.daemon_main', _daemon_py_path)
_daemon_main = importlib.util.module_from_spec(_spec)

# Set __package__ so relative imports work
_daemon_main.__package__ = 'msmacro'

# Add to sys.modules before executing to avoid import issues
sys.modules['msmacro.daemon_main'] = _daemon_main
_spec.loader.exec_module(_daemon_main)

# Re-export from daemon.py
run_daemon = _daemon_main.run_daemon
MacroDaemon = _daemon_main.MacroDaemon

# Export from this package
from .point_navigator import PointNavigator

__all__ = ['run_daemon', 'MacroDaemon', 'PointNavigator']
