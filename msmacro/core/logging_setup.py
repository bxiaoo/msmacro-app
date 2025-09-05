"""Logging configuration for msmacro daemon."""
import logging
import os
from ..utils.config import SETTINGS


def setup_logger() -> logging.Logger:
    """Setup and configure logger for msmacro daemon."""
    lvl_name = (getattr(SETTINGS, "log_level", None) or os.environ.get("MSMACRO_LOGLEVEL", "INFO")).upper()
    level = getattr(logging, lvl_name, logging.INFO)
    logger = logging.getLogger("msmacro.daemon")
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger