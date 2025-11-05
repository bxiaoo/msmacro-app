"""
Daemon module for msmacro.

This module contains the refactored daemon implementation, split into
multiple focused modules for better maintainability.

The main MacroDaemon class coordinates all operations, while command
handlers are organized into separate modules by functionality.
"""

# These will be imported after we move the code
# from .core import MacroDaemon, run_daemon

__all__ = []  # Will be populated as we refactor
