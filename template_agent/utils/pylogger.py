"""Logging utilities for the template agent.

This module provides comprehensive logging functionality including trace-aware
formatters, configuration utilities, and shared logging components used across
the template agent service.
"""

from __future__ import annotations

import logging.config
import os
import socket
import sys

from tqdm import tqdm

from template_agent.utils.constants import LOGGER
from template_agent.utils.trace_context import get_log_context, get_trace_id


def get_log_file_path(default_path: str = "/etc/logs/app.log") -> str:
    """Get the log file path with directory creation and fallback handling.

    Args:
        default_path: Default log file path if LOG_FILE_PATH env var is not set

    Returns:
        Valid log file path that can be written to
    """
    import os
    import tempfile

    log_file_path = os.environ.get("LOG_FILE_PATH", default_path)

    # Ensure log directory exists
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except (OSError, PermissionError):
            # Fallback to temp directory if log directory is not writable
            log_file_path = os.path.join(tempfile.gettempdir(), "app.log")

    return log_file_path


def get_default_log_format() -> str:
    """Get the default log format string used across the application.

    Returns:
        Standard log format optimized for Splunk ingestion
    """
    return "timestamp=%(asctime)s.%(msecs)03d log_level=%(levelname)s hostname=%(hostname)s environment=%(environment)s trace_id=%(trace_id)s client.name=%(client_name)s client.version=%(client_version)s jwt.client_id=%(jwt_client_id)s jwt.username=%(jwt_username)s http.origin=%(http_origin)s http.method=%(http_method)s http.path=%(http_path)s user_agent=%(user_agent)s class=%(module)s function=%(funcName)s log_message=%(message)s"


def get_default_log_date_format() -> str:
    """Get the default date format string used for logging.

    Returns:
        Standard date format for log timestamps
    """
    return "%Y-%m-%d %H:%M:%S"


def get_log_rotation_config() -> dict:
    """Get the standard log rotation configuration.

    Returns:
        Dictionary with log rotation settings
    """
    return {
        "maxBytes": 52428800,  # 50MB for better Splunk ingestion
        "backupCount": 5,  # Keep 5 backup files
        "encoding": "utf-8",
    }


class TqdmLoggingHandler(logging.StreamHandler):
    """Custom logging handler that uses tqdm.write to avoid interfering with progress bars."""

    def __init__(self, level=logging.NOTSET):
        """Initialize the TqdmLoggingHandler with the specified logging level."""
        super().__init__(level)

    def emit(self, record):
        """Emit a log record using tqdm.write to avoid progress bar interference."""
        try:
            msg = self.format(record)
            tqdm.write(
                msg
            )  # Use tqdm's write method to ensure output doesn't interfere with progress bars
        except Exception:
            self.handleError(record)


class TraceFormatter(logging.Formatter):
    """Custom formatter that includes trace ID, client/JWT information, hostname, and environment in log messages."""

    def format(self, record):
        """Format the log record with trace context information."""
        # Add trace ID to the log record
        trace_id = get_trace_id()
        if trace_id:
            record.trace_id = trace_id
        else:
            record.trace_id = "no-trace"

        # Get log context from context variable
        log_context = get_log_context()

        # Add client and JWT fields from context
        record.client_name = log_context.get("client_name", "unknown")
        record.client_version = log_context.get("client_version", "unknown")
        record.jwt_client_id = log_context.get("jwt_client_id", "unknown")
        record.jwt_username = log_context.get("jwt_username", "unknown")
        record.http_origin = log_context.get("http_origin", "unknown")
        record.http_method = log_context.get("http_method", "unknown")
        record.http_path = log_context.get("http_path", "unknown")
        record.user_agent = log_context.get("user_agent", "unknown")

        # Add hostname/pod name
        record.hostname = os.environ.get("HOSTNAME", socket.gethostname())

        # Add environment from APP_ENV
        record.environment = os.environ.get("APP_ENV", "local")

        return super().format(record)


def configure_logging(
    log_level="INFO",
    log_format=None,
    log_date_format=None,
    enable_file_logging=True,
):
    """Configure logging for the entire application.

    This should be called once at application startup.
    Supports both console and file logging with the same format, optimized for Splunk ingestion.
    """
    log_level = log_level.upper()
    log_file_path = get_log_file_path() if enable_file_logging else None

    # Use default formats if not provided
    if log_format is None:
        log_format = get_default_log_format()
    if log_date_format is None:
        log_date_format = get_default_log_date_format()

    formatters = {
        LOGGER: {
            "()": TraceFormatter,
            "format": log_format,
            "datefmt": log_date_format,
        }
    }

    handlers = {
        "console": {
            "level": log_level,
            "class": "logging.StreamHandler",
            "formatter": LOGGER,
            "stream": sys.stdout,
        },
        "tqdm_console": {
            "level": log_level,
            "()": TqdmLoggingHandler,
            "formatter": LOGGER,
        },
    }

    # Add file handler if enabled
    if enable_file_logging:
        rotation_config = get_log_rotation_config()
        handlers["file"] = {
            "level": log_level,
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": LOGGER,
            "filename": log_file_path,
            **rotation_config,
        }

    # Configure root handlers
    root_handlers = ["tqdm_console"]
    if enable_file_logging:
        root_handlers.append("file")

    logger_config = {
        "version": 1,
        "formatters": formatters,
        "handlers": handlers,
        "root": {
            "level": log_level,
            "handlers": root_handlers,
        },
        "disable_existing_loggers": False,
    }

    logging.config.dictConfig(logger_config)


def get_python_logger(name=None):
    """Get a logger with the specified name.

    Args:
        name: The name of the logger. If None, uses the default root logger.
              It's recommended to use __name__ to get module-specific loggers.

    Returns:
        logging.Logger: Configured logger instance
    """
    if name is None:
        name = LOGGER
    return logging.getLogger(name)
