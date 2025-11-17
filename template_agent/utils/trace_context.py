"""Trace context management utilities.

This module provides context variable management for distributed tracing
and logging context across async request processing.
"""

from __future__ import annotations

import contextvars
import os
import uuid
from typing import Any, Dict, Optional

from template_agent.utils.constants import AGENT

# Context variable to store trace ID for the current request
trace_id_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trace_id", default=None
)

# Context variable to store log context for the current request
log_context_var: contextvars.ContextVar[Optional[Dict[str, Any]]] = (
    contextvars.ContextVar("log_context", default=None)
)


def generate_trace_id() -> str:
    """Generate a new trace ID using UUID4."""
    app_env = os.environ.get("APP_ENV", "local")
    return AGENT + "-" + app_env + "-" + str(uuid.uuid4())


def set_trace_id(trace_id: str) -> None:
    """Set the trace ID for the current context."""
    trace_id_context.set(trace_id)


def get_trace_id() -> Optional[str]:
    """Get the trace ID from the current context."""
    return trace_id_context.get()


def get_trace_id_or_generate() -> str:
    """Get the current trace ID or generate a new one if none exists."""
    trace_id = get_trace_id()
    if trace_id is None:
        trace_id = generate_trace_id()
        set_trace_id(trace_id)
    return trace_id


def set_log_context(log_context: Dict[str, Any]) -> None:
    """Set the log context for the current request."""
    log_context_var.set(log_context)


def get_log_context() -> Dict[str, Any]:
    """Get the log context from the current context."""
    context = log_context_var.get()
    if context is None:
        # Return default context if none is set
        return {
            "client_name": "unknown",
            "client_version": "unknown",
            "jwt_client_id": "unknown",
            "jwt_username": "unknown",
            "http_origin": "unknown",
            "http_method": "unknown",
            "http_path": "unknown",
            "user_agent": "unknown",
        }
    return context
