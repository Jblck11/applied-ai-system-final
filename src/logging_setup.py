"""Central logging configuration for the recommender system.

A single named logger (``"recommender"``) is used across the whole system so
that every stage of a run is traced consistently. The CLI and the evaluation
harness both call :func:`configure_logging` once at startup; library modules
(``pipeline``, ``reliability``) only ever *use* the logger, never configure it.
This keeps logging predictable and avoids duplicate handlers.
"""

import logging
import os
import sys
from typing import Optional

LOGGER_NAME = "recommender"


def get_logger() -> logging.Logger:
    """Return the shared system logger (no side effects)."""
    return logging.getLogger(LOGGER_NAME)


def configure_logging(logfile: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """Configure and return the shared logger.

    Args:
        logfile: If given, logs are also appended to this file (its parent
            directory is created if needed). Console output is always enabled.
        level: Logging level (defaults to INFO).

    Safe to call more than once: existing handlers are cleared first so we never
    emit duplicate lines.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    if logfile:
        parent = os.path.dirname(os.path.abspath(logfile))
        os.makedirs(parent, exist_ok=True)
        file_handler = logging.FileHandler(logfile, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger
