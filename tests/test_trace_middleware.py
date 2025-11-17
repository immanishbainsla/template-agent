"""Tests for the trace_middleware module."""

import time
from unittest.mock import Mock, patch, AsyncMock

import pytest
from fastapi import Request, Response
from fastapi.testclient import TestClient

from template_agent.src.middleware.trace_middleware import TraceMiddleware
from template_agent.utils.trace_context import get_trace_id, get_log_context


class TestTraceMiddleware:
    """Test cases for TraceMiddleware class."""

    def setup_method(self):
        """Set up test method."""
        self.middleware = TraceMiddleware(app=None)

    def test_extract_jwt_claims_valid_jwt(self):
        """Test extracting JWT claims from valid token."""
        # Create a mock request with valid JWT
        request = Mock(spec=Request)
        request.headers = {
            "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJhenAiOiJ0ZXN0LWNsaWVudCIsInByZWZlcnJlZF91c2VybmFtZSI6InRlc3R1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        }

        claims = self.middleware._extract_jwt_claims(request)

        assert claims["sub"] == "1234567890"
        assert claims["name"] == "John Doe"
        assert claims["azp"] == "test-client"
        assert claims["preferred_username"] == "testuser"

    def test_extract_jwt_claims_invalid_jwt(self):
        """Test extracting JWT claims from invalid token."""
        request = Mock(spec=Request)
        request.headers = {"authorization": "Bearer invalid-token"}

        claims = self.middleware._extract_jwt_claims(request)

        assert claims == {}

    def test_extract_jwt_claims_no_auth_header(self):
        """Test extracting JWT claims when no auth header present."""
        request = Mock(spec=Request)
        request.headers = {}

        claims = self.middleware._extract_jwt_claims(request)

        assert claims == {}

    def test_extract_jwt_claims_malformed_auth_header(self):
        """Test extracting JWT claims from malformed auth header."""
        request = Mock(spec=Request)
        request.headers = {"authorization": "InvalidFormat token"}

        claims = self.middleware._extract_jwt_claims(request)

        assert claims == {}

    def test_extract_jwt_claims_case_insensitive_header(self):
        """Test extracting JWT claims with case insensitive header."""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer valid.jwt.token"}

        # This will fail JWT parsing but should not crash
        claims = self.middleware._extract_jwt_claims(request)

        assert claims == {}  # Invalid JWT but no crash

    def test_extract_client_info_all_headers_present(self):
        """Test extracting client info when all headers are present."""
        request = Mock(spec=Request)
        request.headers = {"x-client-name": "test-client", "x-client-version": "1.2.3"}

        client_name, client_version = self.middleware._extract_client_info(request)

        assert client_name == "test-client"
        assert client_version == "1.2.3"

    def test_extract_client_info_alternative_headers(self):
        """Test extracting client info from alternative header names."""
        request = Mock(spec=Request)
        request.headers = {"client-name": "alt-client", "app-version": "2.0.0"}

        client_name, client_version = self.middleware._extract_client_info(request)

        assert client_name == "alt-client"
        assert client_version == "2.0.0"

    def test_extract_client_info_missing_headers(self):
        """Test extracting client info when headers are missing."""
        request = Mock(spec=Request)
        request.headers = {}

        client_name, client_version = self.middleware._extract_client_info(request)

        assert client_name == "unknown"
        assert client_version == "unknown"

    def test_extract_client_info_priority_order(self):
        """Test that client info extraction follows priority order."""
        request = Mock(spec=Request)
        request.headers = {
            "x-client-name": "priority-client",
            "client-name": "secondary-client",
            "x-client-version": "priority-version",
            "client-version": "secondary-version",
        }

        client_name, client_version = self.middleware._extract_client_info(request)

        assert client_name == "priority-client"
        assert client_version == "priority-version"

    def test_create_log_context_complete(self):
        """Test creating log context with complete request information."""
        request = Mock(spec=Request)
        request.headers = {
            "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhenAiOiJjbGllbnQtaWQiLCJwcmVmZXJyZWRfdXNlcm5hbWUiOiJ0ZXN0dXNlciJ9.mock",
            "x-client-name": "test-client",
            "x-client-version": "1.0.0",
            "origin": "https://example.com",
            "user-agent": "TestAgent/1.0",
        }
        request.method = "POST"
        request.url.path = "/api/test"

        log_context = self.middleware._create_log_context(request)

        assert log_context["client_name"] == "test-client"
        assert log_context["client_version"] == "1.0.0"
        assert log_context["http_origin"] == "https://example.com"
        assert log_context["http_method"] == "POST"
        assert log_context["http_path"] == "/api/test"
        assert log_context["user_agent"] == "TestAgent/1.0"

    def test_create_log_context_minimal(self):
        """Test creating log context with minimal request information."""
        request = Mock(spec=Request)
        request.headers = {}
        request.method = "GET"
        request.url.path = "/"

        log_context = self.middleware._create_log_context(request)

        assert log_context["client_name"] == "unknown"
        assert log_context["client_version"] == "unknown"
        assert log_context["jwt_client_id"] == "unknown"
        assert log_context["jwt_username"] == "unknown"
        assert log_context["http_origin"] == "unknown"
        assert log_context["http_method"] == "GET"
        assert log_context["http_path"] == "/"
        assert log_context["user_agent"] == "unknown"

    @pytest.mark.asyncio
    async def test_dispatch_successful_request(self):
        """Test dispatch for successful request."""
        # Mock request
        request = Mock(spec=Request)
        request.headers = {"x-client-name": "test-client"}
        request.method = "GET"
        request.url.path = "/test"
        request.state = Mock()

        # Mock response
        mock_response = Mock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {}

        # Mock call_next
        call_next = AsyncMock(return_value=mock_response)

        with patch(
            "template_agent.src.middleware.trace_middleware.logger"
        ) as mock_logger:
            result = await self.middleware.dispatch(request, call_next)

        # Verify trace ID was set
        assert hasattr(request.state, "trace_id")
        assert hasattr(request.state, "log_context")

        # Verify response has trace ID header
        assert "X-Trace-ID" in mock_response.headers

        # Verify logging calls
        assert mock_logger.info.call_count == 2  # Start and completion logs

        assert result == mock_response

    @pytest.mark.asyncio
    async def test_dispatch_request_with_exception(self):
        """Test dispatch when request processing raises exception."""
        request = Mock(spec=Request)
        request.headers = {}
        request.method = "POST"
        request.url.path = "/error"
        request.state = Mock()

        # Mock call_next to raise exception
        call_next = AsyncMock(side_effect=ValueError("Test error"))

        with patch(
            "template_agent.src.middleware.trace_middleware.logger"
        ) as mock_logger:
            with pytest.raises(ValueError) as exc_info:
                await self.middleware.dispatch(request, call_next)

        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Request failed" in error_call
        assert "Test error" in error_call

        # Verify original exception was re-raised
        assert "Test error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dispatch_sets_context_variables(self):
        """Test that dispatch properly sets context variables."""
        request = Mock(spec=Request)
        request.headers = {
            "x-client-name": "context-client",
            "x-client-version": "1.0.0",
        }
        request.method = "GET"
        request.url.path = "/context"
        request.state = Mock()

        mock_response = Mock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {}

        call_next = AsyncMock(return_value=mock_response)

        await self.middleware.dispatch(request, call_next)

        # Check that context variables were set
        trace_id = get_trace_id()
        log_context = get_log_context()

        assert trace_id is not None
        assert trace_id.startswith("template-agent-")
        assert log_context["client_name"] == "context-client"
        assert log_context["client_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_dispatch_measures_duration(self):
        """Test that dispatch measures request duration."""
        request = Mock(spec=Request)
        request.headers = {}
        request.method = "GET"
        request.url.path = "/slow"
        request.state = Mock()

        mock_response = Mock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {}

        # Mock call_next with delay
        async def slow_call_next(req):
            await asyncio.sleep(0.1)  # 100ms delay
            return mock_response

        import asyncio

        call_next = slow_call_next

        with patch(
            "template_agent.src.middleware.trace_middleware.logger"
        ) as mock_logger:
            with patch(
                "time.time", side_effect=[1000.0, 1000.1]
            ):  # Mock 100ms duration
                await self.middleware.dispatch(request, call_next)

        # Verify duration was logged
        completion_call = mock_logger.info.call_args_list[1][0][0]
        assert "Duration: 0.100s" in completion_call

    def test_origin_header_fallback(self):
        """Test origin header extraction with fallback."""
        request = Mock(spec=Request)
        request.headers = {"host": "fallback.example.com"}
        request.method = "GET"
        request.url.path = "/"

        log_context = self.middleware._create_log_context(request)

        assert log_context["http_origin"] == "fallback.example.com"

    def test_jwt_claim_extraction_multiple_fields(self):
        """Test JWT claim extraction tries multiple field names."""
        request = Mock(spec=Request)

        # Test different JWT claim field names
        with patch.object(self.middleware, "_extract_jwt_claims") as mock_extract:
            mock_extract.return_value = {"client_id": "test-client-id"}

            request.headers = {}
            request.method = "GET"
            request.url.path = "/"

            log_context = self.middleware._create_log_context(request)

            assert log_context["jwt_client_id"] == "test-client-id"


class TestTraceMiddlewareIntegration:
    """Integration tests for TraceMiddleware."""

    def test_middleware_integration_with_fastapi(self):
        """Test middleware integration with FastAPI application."""
        from fastapi import FastAPI

        app = FastAPI()
        app.add_middleware(TraceMiddleware)

        @app.get("/test")
        async def test_endpoint():
            # Access context variables set by middleware
            trace_id = get_trace_id()
            log_context = get_log_context()
            return {
                "trace_id": trace_id,
                "client_name": log_context.get("client_name", "unknown"),
            }

        with TestClient(app) as client:
            response = client.get(
                "/test", headers={"x-client-name": "integration-client"}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify trace ID is present and properly formatted
            assert "trace_id" in data
            assert data["trace_id"].startswith("template-agent-")

            # Verify client name was extracted
            assert data["client_name"] == "integration-client"

            # Verify trace ID is in response headers
            assert "X-Trace-ID" in response.headers
            assert response.headers["X-Trace-ID"] == data["trace_id"]

    def test_middleware_context_isolation(self):
        """Test that middleware properly isolates context between requests."""
        from fastapi import FastAPI

        app = FastAPI()
        app.add_middleware(TraceMiddleware)

        @app.get("/context-test")
        async def context_test():
            trace_id = get_trace_id()
            log_context = get_log_context()
            return {"trace_id": trace_id, "client_name": log_context.get("client_name")}

        with TestClient(app) as client:
            # Make two requests with different client names
            response1 = client.get(
                "/context-test", headers={"x-client-name": "client1"}
            )
            response2 = client.get(
                "/context-test", headers={"x-client-name": "client2"}
            )

            data1 = response1.json()
            data2 = response2.json()

            # Verify different trace IDs
            assert data1["trace_id"] != data2["trace_id"]

            # Verify different client names
            assert data1["client_name"] == "client1"
            assert data2["client_name"] == "client2"
