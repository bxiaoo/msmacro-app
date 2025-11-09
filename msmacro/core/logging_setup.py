"""Logging configuration for msmacro daemon."""
import logging
import os
from ..utils.config import SETTINGS


def setup_logger() -> logging.Logger:
    """Setup and configure logger for msmacro daemon."""
    lvl_name = (getattr(SETTINGS, "log_level", None) or os.environ.get("MSMACRO_LOGLEVEL", "INFO")).upper()
    level = getattr(logging, lvl_name, logging.INFO)

    # Configure ROOT logger so ALL child loggers (msmacro.cv.*, etc.) inherit the level
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S"))
        root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Return daemon logger for compatibility
    daemon_logger = logging.getLogger("msmacro.daemon")
    daemon_logger.setLevel(level)
    return daemon_logger