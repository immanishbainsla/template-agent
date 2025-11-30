"""FastAPI server implementation for the template agent.

This module provides the main FastAPI application setup, including
middleware configuration, route registration, and application lifecycle
management for the template agent service.
"""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from template_agent.src.core.agent import initialize_database
from template_agent.src.core.exceptions.exceptions import AppException, AppExceptionCode
from template_agent.src.middleware.trace_middleware import TraceMiddleware
from template_agent.src.routes.feedback import router as feedback_router
from template_agent.src.routes.health import router as health_router
from template_agent.src.routes.history import router as history_router
from template_agent.src.routes.stream import router as stream_router
from template_agent.src.routes.threads import router as threads_router
from template_agent.src.settings import settings
from template_agent.utils.pylogger import configure_logging, get_python_logger

# Initialize logger
configure_logging(log_level=settings.PYTHON_LOG_LEVEL)

logger = get_python_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests and outgoing responses."""

    async def dispatch(self, request: Request, call_next: Callable):
        """Process and log incoming requests and outgoing responses."""
        if not settings.REQUEST_LOGGING_ENABLED:
            return await call_next(request)

        start_time = time.time()

        # Capture request details
        request_data = {
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
            "query_params": dict(request.query_params)
            if request.query_params
            else None,
        }

        # Optionally log headers
        if settings.REQUEST_LOG_HEADERS:
            request_data["headers"] = dict(request.headers)

        # Optionally log request body
        if settings.REQUEST_LOG_BODY:
            try:
                body_bytes = await request.body()
                body_size = len(body_bytes)

                if body_size > 0:
                    request_data["body_size"] = body_size
                    if (
                        settings.REQUEST_LOG_BODY_MAX_SIZE == 0
                        or body_size <= settings.REQUEST_LOG_BODY_MAX_SIZE
                    ):
                        try:
                            body_str = body_bytes.decode("utf-8")
                            request_data["body"] = body_str
                        except UnicodeDecodeError:
                            request_data["body"] = "<binary data>"
                    else:
                        request_data["body"] = f"<truncated: {body_size} bytes>"

                # Rebuild request with body
                async def receive():
                    return {"type": "http.request", "body": body_bytes}

                request = Request(request.scope, receive)
            except Exception as e:
                logger.warning("Failed to read request body: %s", str(e))

        logger.info("Incoming request: %s", request_data)

        # Process request
        response = await call_next(request)

        # Capture response details
        duration_ms = (time.time() - start_time) * 1000
        response_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }

        # Optionally log response headers
        if settings.REQUEST_LOG_HEADERS:
            response_data["headers"] = dict(response.headers)

        logger.info("Outgoing response: %s", response_data)

        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Configure application lifespan.

    This context manager handles the application startup and shutdown
    lifecycle. Database schema is initialized on startup, while agent
    initialization is deferred to per-request handling to allow for
    authenticated MCP connections.

    Args:
        app: The FastAPI application instance to manage.

    Yields:
        None: The lifespan context for the application.

    Raises:
        AppException: If database initialization fails on startup.
    """
    logger.info("Agent server starting up")

    # Initialize database schema on startup
    try:
        await initialize_database()
    except Exception as e:
        logger.critical("Failed to initialize database on startup: %s", str(e))
        raise

    logger.info("Agent server ready - MCP connection will be established per-request")
    yield
    logger.info("Agent server shutting down")


# Create FastAPI application with lifespan management
app = FastAPI(lifespan=lifespan)

# Register request logging middleware first to capture all requests
app.add_middleware(RequestLoggingMiddleware)

# Configure CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure application logger
app.logger = logger

app.add_middleware(TraceMiddleware)

# Register all route handlers
app.include_router(health_router)
app.include_router(stream_router)
app.include_router(feedback_router)
app.include_router(history_router)
app.include_router(threads_router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Generic exception handler for unhandled exceptions."""
    logger.exception(
        "Unhandled exception occurred for request_method=%s, request_path=%s, error=%s",
        request.method,
        request.url.path,
        exc,
    )
    logger.debug("Unhandled exception occurred for request=%s, error=%s", request, exc)
    return JSONResponse(
        status_code=AppExceptionCode.INTERNAL_SERVER_ERROR.response_code,
        content={
            "detail_message": str(exc),
            "message": AppExceptionCode.INTERNAL_SERVER_ERROR.message,
            "error_code": AppExceptionCode.INTERNAL_SERVER_ERROR.error_code,
        },
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """App exception handler for unhandled exceptions."""
    logger.warn(
        "App exception occurred for request_method=%s, request_path=%s, error=%s",
        request.method,
        request.url.path,
        exc,
    )
    logger.debug("App exception occurred for request=%s, error=%s", request, exc)
    return JSONResponse(
        status_code=exc.response_code,
        content={
            "detail_message": exc.detail_message,
            "message": exc.message,
            "error_code": exc.error_code,
        },
    )
