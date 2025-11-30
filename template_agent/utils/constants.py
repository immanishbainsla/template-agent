"""Application constants.

This module defines global constants used throughout the template agent application.
"""

from __future__ import annotations

LOGGER = "template-agent-logger"
AGENT = "template-agent"
DEFAULT_LOG_FORMAT = "timestamp=%(asctime)s.%(msecs)03d log_level=%(levelname)s hostname=%(hostname)s environment=%(environment)s trace_id=%(trace_id)s client.name=%(client_name)s client.version=%(client_version)s jwt.client_id=%(jwt_client_id)s jwt.username=%(jwt_username)s http.origin=%(http_origin)s http.method=%(http_method)s http.path=%(http_path)s user_agent=%(user_agent)s class=%(module)s function=%(funcName)s log_message=%(message)s"
DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_ROTATION_CONFIG = {"maxBytes": 52428800, "backupCount": 5, "encoding": "utf-8"}
