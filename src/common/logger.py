"""Structured logging setup with PII redaction and rotation support."""

from __future__ import annotations

import json
import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

from src.common.config import get_config

# Regex patterns for basic PII redaction in logs
_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_IP_REGEX = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


class PIIRedactionFilter(logging.Filter):
    """Log filter that scrubs obvious PII patterns from all log records before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            msg = _EMAIL_REGEX.sub("[EMAIL]", msg)
            msg = _PHONE_REGEX.sub("[PHONE]", msg)
            msg = _IP_REGEX.sub("[IP]", msg)
            record.msg = msg

        if record.args:
            if isinstance(record.args, dict):
                redacted_args = {}
                for k, v in record.args.items():
                    if isinstance(v, str):
                        v = _EMAIL_REGEX.sub("[EMAIL]", v)
                        v = _PHONE_REGEX.sub("[PHONE]", v)
                        v = _IP_REGEX.sub("[IP]", v)
                    redacted_args[k] = v
                record.args = redacted_args
            elif isinstance(record.args, tuple):
                new_args = []
                for v in record.args:
                    if isinstance(v, str):
                        v = _EMAIL_REGEX.sub("[EMAIL]", v)
                        v = _PHONE_REGEX.sub("[PHONE]", v)
                        v = _IP_REGEX.sub("[IP]", v)
                    new_args.append(v)
                record.args = tuple(new_args)

        return True


class JSONFormatter(logging.Formatter):
    """Outputs log events in a structured JSON format."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def setup_logger(
    name: str = "GooglePhotosEngine",
    level: str | None = None,
    log_to_file: bool = True,
) -> logging.Logger:
    """Configures and returns a logger instance with console and rotating file handlers."""
    config = get_config()
    log_level = getattr(logging, (level or config.log_level).upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Avoid adding duplicate handlers if already configured
    if logger.handlers:
        return logger

    # Add PII redaction filter
    pii_filter = PIIRedactionFilter()
    logger.addFilter(pii_filter)

    # Console Handler (Human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    console_handler.addFilter(pii_filter)
    logger.addHandler(console_handler)

    # File Handler (Structured JSON with rotation)
    if log_to_file:
        config.ensure_directories()
        log_file_path = config.logs_dir / config.log_file_name
        file_handler = RotatingFileHandler(
            filename=str(log_file_path),
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(JSONFormatter())
        file_handler.addFilter(pii_filter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Retrieve an existing logger or child logger."""
    base_name = "GooglePhotosEngine"
    if name:
        logger_name = f"{base_name}.{name}"
    else:
        logger_name = base_name

    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        return setup_logger(logger_name)
    return logger
