"""Uvicorn logging configuration utilities.

This module provides logging configuration specifically designed for uvicorn,
ensuring consistent log formatting and trace context across both application
and web server logs.
"""

from __future__ import annotations

import json
import os
import tempfile

from template_agent.utils.constants import (
    DEFAULT_LOG_DATE_FORMAT,
    DEFAULT_LOG_FORMAT,
    LOG_ROTATION_CONFIG,
    LOGGER,
)
from template_agent.utils.pylogger import (
    get_log_file_path,
)


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
                "()": "template_agent.utils.pylogger.TraceFormatter",
                "format": DEFAULT_LOG_FORMAT,
                "datefmt": DEFAULT_LOG_DATE_FORMAT,
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
                **LOG_ROTATION_CONFIG,
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
