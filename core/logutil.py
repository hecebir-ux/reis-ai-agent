from __future__ import annotations

import logging
from pathlib import Path

import config
from core.security import redact


def _make_logger(name: str, filename: str, level: int) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    path = Path(config.LOGS_DIR) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


user_log = _make_logger("reis.user", "user.log", logging.INFO)
debug_log = _make_logger("reis.debug", "debug.log", logging.DEBUG)
system_log = _make_logger("reis.system", "system.log", logging.INFO)


def log_user(msg: str) -> None:
    user_log.info(redact(msg))


def log_debug(msg: str) -> None:
    debug_log.debug(redact(msg))


def log_system(msg: str) -> None:
    system_log.info(redact(msg))
