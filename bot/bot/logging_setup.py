# logging_setup.py
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    *,
    log_dir: str = "logs",
    log_file_name: str = "bot.log",
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    clear_handlers: bool = False,
) -> logging.Logger:
    """
    Centralized logging setup for Academic Bot.

    - Safe to call multiple times (idempotent)
    - Rotating file logs + console logs
    - UTF-8 safe
    - Production & Docker friendly
    """

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / log_file_name

    logger = logging.getLogger("academic_bot")
    logger.setLevel(level)
    logger.propagate = False  # VERY IMPORTANT

    if clear_handlers:
        logger.handlers.clear()

    if logger.handlers:
        return logger  # already configured

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | "
        "%(filename)s:%(lineno)d | %(message)s"
    )

    # Console (stdout) — Docker / systemd friendly
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info(
        "Logger initialized | level=%s | file=%s",
        logging.getLevelName(level),
        log_file.resolve(),
    )

    return logger
