from __future__ import annotations

import time

import jwt
from fastapi import Request
from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware

from template_agent.src.core.exceptions.exceptions import AppException
from template_agent.utils.pylogger import get_python_logger
from template_agent.utils.trace_context import generate_trace_id, set_trace_id, set_log_context

logger = get_python_logger(__name__)


class TraceMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and propagate trace IDs for requests."""

    def _extract_jwt_claims(self, request: Request) -> dict:
        """Extract JWT claims from request without validation."""
        try:
            # Try to get the Authorization header
            auth_header = request.headers.get("authorization") or request.headers.get(
                "Authorization"
            )
            if not auth_header or not auth_header.startswith("Bearer "):
                return {}

            # Extract token from "Bearer <token>"
            token = auth_header[7:]  # Remove "Bearer " prefix

            # Decode JWT without verification (just to extract claims for logging)
            # Using options to skip all verifications since we only need claims for logging
            claims = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
            return claims
        except Exception as e:
            # If JWT extraction fails, log the error but don't fail the request
            logger.debug(f"Failed to extract JWT claims for logging: {e}")
            return {}

    def _extract_client_info(self, request: Request) -> tuple[str, str]:
        """Extract client name and version from request headers."""
        # Common patterns for client info in headers
        client_name = (
            request.headers.get("x-client-name")
            or request.headers.get("client-name")
            or request.headers.get("x-app-name")
            or request.headers.get("app-name")
            or "unknown"
        )

        client_version = (
            request.headers.get("x-client-version")
            or request.headers.get("client-version")
            or request.headers.get("x-app-version")
            or request.headers.get("app-version")
            or "unknown"
        )

        return client_name, client_version

    def _create_log_context(self, request: Request) -> dict:
        """Create logging context with all required fields."""
        # Extract JWT claims
        jwt_claims = self._extract_jwt_claims(request)

        # Extract client info
        client_name, client_version = self._extract_client_info(request)

        # Extract origin header
        http_origin = (
            request.headers.get("origin")
            or request.headers.get("Origin")
            or request.headers.get("host")
            or "unknown"
        )

        # Build context
        log_context = {
            "client_name": client_name,
            "client_version": client_version,
            "jwt_client_id": jwt_claims.get("azp")
            or jwt_claims.get("client_id")
            or jwt_claims.get("clientId")
            or "unknown",
            "jwt_username": jwt_claims.get("preferred_username") or "unknown",
            "http_origin": http_origin,
            "http_method": request.method,
            "http_path": request.url.path,
            "user_agent": request.headers.get("user-agent", "unknown"),
        }

        return log_context

    async def dispatch(self, request: Request, call_next):
        # Generate a new trace ID for this request
        trace_id = generate_trace_id()
        set_trace_id(trace_id)

        # Add trace ID to request state for potential use in other parts of the app
        request.state.trace_id = trace_id

        # Extract logging context
        log_context = self._create_log_context(request)

        # Set log context in context variable for global access
        set_log_context(log_context)

        # Add context to request state for backwards compatibility
        request.state.log_context = log_context

        # Log the start of the request
        start_time = time.time()
        logger.info(f"Request started: {request.method} {request.url.path}")

        try:
            # Process the request
            response: Response = await call_next(request)

            # Add trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id

            # Log successful completion
            process_time = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {process_time:.3f}s"
            )

            return response

        except Exception as e:
            # Log errors with trace ID
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} - Error: {str(e)} - Duration: {process_time:.3f}s"
            )
            raise AppException("Failed to generate new traceId")
