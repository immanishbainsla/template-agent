"""Uvicorn logging configuration utilities.

This module provides logging configuration specifically designed for uvicorn,
ensuring consistent log formatting and trace context across both application
and web server logs.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import tempfile

from template_agent.utils.constants import LOGGER
from template_agent.utils.pylogger import (
    get_default_log_date_format,
    get_default_log_format,
    get_log_file_path,
    get_log_rotation_config,
)
from template_agent.utils.trace_context import get_log_context, get_trace_id


class UvicornTraceFormatter(logging.Formatter):
    """Custom formatter for uvicorn logs that matches the application log format.

    Uses the same trace context logic as pylogger TraceFormatter.
    """

    def format(self, record):
        """Format the log record with trace context information."""
        # Add trace ID to the log record (same logic as pylogger)
        trace_id = get_trace_id()
        if trace_id:
            record.trace_id = trace_id
        else:
            record.trace_id = "no-trace"

        # Get log context from context variable (same logic as pylogger)
        log_context = get_log_context()

        # Add client and JWT fields from context (same logic as pylogger)
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


def get_uvicorn_log_config():
    """Returns a uvicorn-compatible logging configuration that writes to both console and file.

    This will capture uvicorn's startup, shutdown, and access logs.
    Optimized for Splunk ingestion with improved log rotation.
    """
    log_level = os.environ.get("PYTHON_LOG_LEVEL", "INFO").upper()
    log_file_path = get_log_file_path()

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            LOGGER: {
                "()": "template_agent.utils.uvicorn_logging_config.UvicornTraceFormatter",
                "format": get_default_log_format(),
                "datefmt": get_default_log_date_format(),
            },
        },
        "handlers": {
            "console": {
                "formatter": LOGGER,
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "formatter": LOGGER,
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file_path,
                **get_log_rotation_config(),
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.asgi": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
            "watchfiles": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
            # Capture all template_agent application logs
            "template_agent": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file"],
        },
    }

    return config


def write_uvicorn_log_config_file():
    """Write uvicorn logging configuration to a JSON file.

    Returns the path to the configuration file.
    """
    config = get_uvicorn_log_config()

    # Write to a temporary file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_uvicorn_log_config.json", delete=False
    ) as f:
        json.dump(config, f, indent=2)
        return f.name
