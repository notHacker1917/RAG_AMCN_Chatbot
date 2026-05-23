"""
Logging configuration.

Provides `get_logger(name)` -> rotating-file + console logger using
`loguru` under the hood when available, falling back to stdlib.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = (
    "[%(asctime)s] %(levelname)-7s %(name)s :: %(message)s"
)
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _ensure_log_dir() -> Path:
    log_dir = Path(os.getenv("LOG_DIR", "./logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_logger(name: str = "notesrag") -> logging.Logger:
    """Return a configured logger (idempotent)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))
    fmt = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FMT)

    # Console
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # File logging disabled for development
    # log_dir = _ensure_log_dir()
    # fh = RotatingFileHandler(
    #     log_dir / "notesrag.log",
    #     maxBytes=5 * 1024 * 1024,
    #     backupCount=5,
    #     encoding="utf-8",
    # )
    # fh.setFormatter(fmt)
    # logger.addHandler(fh)

    logger.propagate = False
    return logger
