"""
Structured logging configuration using structlog with JSON rendering
and RotatingFileHandler (50MB max, 5 backups).
"""
import logging
import logging.handlers
import os
from contextvars import ContextVar
from pathlib import Path

import structlog

# Context variables for structured log binding
session_id_var: ContextVar[str] = ContextVar("session_id", default="")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

LOG_DIR = Path("backend/logs")
LOG_FILE = LOG_DIR / "tax_ai.log"
MAX_BYTES = 50 * 1024 * 1024  # 50MB
BACKUP_COUNT = 5


def add_context_vars(logger, method_name, event_dict):
    """Inject session_id and trace_id from context vars."""
    sid = session_id_var.get("")
    tid = trace_id_var.get("")
    if sid:
        event_dict["session_id"] = sid
    if tid:
        event_dict["trace_id"] = tid
    return event_dict


def configure_logging(level: int = logging.INFO):
    """Configure structlog with JSON renderer + rotating file handler."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Standard library handler — rotating file
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # Configure standard library logging root
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[console_handler, file_handler],
        force=True,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_context_vars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
