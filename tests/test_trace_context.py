"""Tests for the trace_context module."""

import os
from unittest.mock import patch
from uuid import UUID

import pytest

from template_agent.utils.trace_context import (
    generate_trace_id,
    set_trace_id,
    get_trace_id,
    get_trace_id_or_generate,
    set_log_context,
    get_log_context,
    trace_id_context,
    log_context_var,
)


class TestTraceIdFunctions:
    """Test cases for trace ID related functions."""

    def test_generate_trace_id_default_env(self):
        """Test generate_trace_id with default environment."""
        with patch.dict("os.environ", {"APP_ENV": "test"}):
            trace_id = generate_trace_id()

            assert trace_id.startswith("template-agent-test-")
            # Verify UUID part is valid
            uuid_part = trace_id.split("-", 3)[-1]
            UUID(uuid_part)  # Should not raise exception if valid UUID

    def test_generate_trace_id_no_env(self):
        """Test generate_trace_id without APP_ENV set."""
        with patch.dict("os.environ", {}, clear=True):
            trace_id = generate_trace_id()

            assert trace_id.startswith("template-agent-local-")
            # Verify UUID part is valid
            uuid_part = trace_id.split("-", 3)[-1]
            UUID(uuid_part)  # Should not raise exception if valid UUID

    def test_generate_trace_id_custom_env(self):
        """Test generate_trace_id with custom environment."""
        with patch.dict("os.environ", {"APP_ENV": "production"}):
            trace_id = generate_trace_id()

            assert trace_id.startswith("template-agent-production-")

    def test_set_and_get_trace_id(self):
        """Test setting and getting trace ID."""
        test_trace_id = "test-trace-123"

        set_trace_id(test_trace_id)
        retrieved_trace_id = get_trace_id()

        assert retrieved_trace_id == test_trace_id

    def test_get_trace_id_when_none_set(self):
        """Test getting trace ID when none is set."""
        # Clear any existing trace ID
        trace_id_context.set(None)

        result = get_trace_id()
        assert result is None

    def test_get_trace_id_or_generate_existing(self):
        """Test get_trace_id_or_generate when trace ID already exists."""
        existing_id = "existing-trace-123"
        set_trace_id(existing_id)

        result = get_trace_id_or_generate()
        assert result == existing_id

    def test_get_trace_id_or_generate_new(self):
        """Test get_trace_id_or_generate when no trace ID exists."""
        # Clear any existing trace ID
        trace_id_context.set(None)

        with patch.dict("os.environ", {"APP_ENV": "test"}):
            result = get_trace_id_or_generate()

            assert result.startswith("template-agent-test-")
            # Verify it was also set in context
            assert get_trace_id() == result


class TestLogContextFunctions:
    """Test cases for log context related functions."""

    def test_set_and_get_log_context(self):
        """Test setting and getting log context."""
        test_context = {
            "client_name": "test-client",
            "client_version": "1.0.0",
            "jwt_client_id": "client123",
            "jwt_username": "testuser",
            "http_origin": "https://example.com",
            "http_method": "GET",
            "http_path": "/test",
            "user_agent": "TestAgent/1.0",
        }

        set_log_context(test_context)
        retrieved_context = get_log_context()

        assert retrieved_context == test_context

    def test_get_log_context_when_none_set(self):
        """Test getting log context when none is set."""
        # Clear any existing log context
        log_context_var.set(None)

        result = get_log_context()

        # Should return default context with 'unknown' values
        expected_default = {
            "client_name": "unknown",
            "client_version": "unknown",
            "jwt_client_id": "unknown",
            "jwt_username": "unknown",
            "http_origin": "unknown",
            "http_method": "unknown",
            "http_path": "unknown",
            "user_agent": "unknown",
        }

        assert result == expected_default

    def test_partial_log_context(self):
        """Test setting partial log context."""
        partial_context = {
            "client_name": "partial-client",
            "jwt_username": "partial-user",
        }

        set_log_context(partial_context)
        retrieved_context = get_log_context()

        assert retrieved_context == partial_context

    def test_empty_log_context(self):
        """Test setting empty log context."""
        empty_context = {}

        set_log_context(empty_context)
        retrieved_context = get_log_context()

        assert retrieved_context == empty_context


class TestContextVariables:
    """Test cases for context variables behavior."""

    def test_trace_id_context_isolation(self):
        """Test that trace ID context is properly isolated."""
        import asyncio

        async def set_trace_in_context(trace_id):
            set_trace_id(trace_id)
            return get_trace_id()

        async def test_isolation():
            # Run two concurrent contexts
            task1 = asyncio.create_task(set_trace_in_context("trace-1"))
            task2 = asyncio.create_task(set_trace_in_context("trace-2"))

            result1, result2 = await asyncio.gather(task1, task2)

            assert result1 == "trace-1"
            assert result2 == "trace-2"

        # Skip if we're not in an async context
        try:
            asyncio.run(test_isolation())
        except RuntimeError:
            # If we can't run async test, just verify basic functionality
            set_trace_id("sync-trace")
            assert get_trace_id() == "sync-trace"

    def test_log_context_variable_isolation(self):
        """Test that log context variable is properly isolated."""
        import asyncio

        async def set_context_in_task(context):
            set_log_context(context)
            return get_log_context()

        async def test_isolation():
            context1 = {"client_name": "client-1"}
            context2 = {"client_name": "client-2"}

            task1 = asyncio.create_task(set_context_in_task(context1))
            task2 = asyncio.create_task(set_context_in_task(context2))

            result1, result2 = await asyncio.gather(task1, task2)

            assert result1 == context1
            assert result2 == context2

        # Skip if we're not in an async context
        try:
            asyncio.run(test_isolation())
        except RuntimeError:
            # If we can't run async test, just verify basic functionality
            context = {"client_name": "sync-client"}
            set_log_context(context)
            assert get_log_context() == context


class TestIntegration:
    """Integration tests for trace context functionality."""

    def test_trace_id_and_context_together(self):
        """Test using trace ID and log context together."""
        trace_id = "integration-trace-123"
        log_context = {
            "client_name": "integration-client",
            "http_method": "POST",
            "http_path": "/api/test",
        }

        set_trace_id(trace_id)
        set_log_context(log_context)

        assert get_trace_id() == trace_id
        assert get_log_context() == log_context

    def test_context_clearing(self):
        """Test clearing contexts."""
        # Set some values
        set_trace_id("test-trace")
        set_log_context({"client_name": "test"})

        # Clear contexts
        trace_id_context.set(None)
        log_context_var.set(None)

        # Verify they're cleared
        assert get_trace_id() is None
        assert get_log_context() == {
            "client_name": "unknown",
            "client_version": "unknown",
            "jwt_client_id": "unknown",
            "jwt_username": "unknown",
            "http_origin": "unknown",
            "http_method": "unknown",
            "http_path": "unknown",
            "user_agent": "unknown",
        }
