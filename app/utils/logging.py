"""Logging utilities for StockTerm.

This module centralizes logging configuration using a rotating file
handler to keep log files small while preserving history. It is imported
by :mod:`main` before any other internal modules so that logging is
consistently configured across the application.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_FILE_NAME = "stockterm.log"


def setup_logging(log_dir: Path | None = None, level: int = logging.INFO) -> Path:
    """Configure application-wide logging.

    Parameters
    ----------
    log_dir:
        Optional directory to place the log file. When omitted the current
        working directory is used.
    level:
        Logging verbosity. Defaults to :data:`logging.INFO`.

    Returns
    -------
    Path
        The path to the configured log file.
    """

    directory = Path.cwd() if log_dir is None else Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / LOG_FILE_NAME

    handler = RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=3)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    logging.basicConfig(level=level, handlers=[handler], force=True)

    # Keep third-party log noise manageable.
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("textual").setLevel(logging.INFO)

    return log_path
