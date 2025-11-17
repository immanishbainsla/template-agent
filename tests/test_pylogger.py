"""Tests for the pylogger module."""

import logging
import os
import tempfile
from io import StringIO
from unittest.mock import patch, Mock

import pytest

from template_agent.utils.pylogger import (
    configure_logging,
    get_python_logger,
    TraceFormatter,
    TqdmLoggingHandler,
)
from template_agent.utils.trace_context import set_trace_id, set_log_context


class TestTraceFormatter:
    """Test cases for TraceFormatter class."""

    def setup_method(self):
        """Set up test method."""
        from template_agent.utils.pylogger import (
            get_default_log_format,
            get_default_log_date_format,
        )

        self.formatter = TraceFormatter(
            fmt=get_default_log_format(), datefmt=get_default_log_date_format()
        )

    def test_format_with_trace_id(self):
        """Test formatting with trace ID set."""
        set_trace_id("test-trace-123")
        set_log_context(
            {
                "client_name": "test-client",
                "client_version": "1.0.0",
                "jwt_client_id": "client123",
                "jwt_username": "testuser",
                "http_origin": "https://example.com",
                "http_method": "GET",
                "http_path": "/test",
                "user_agent": "TestAgent/1.0",
            }
        )

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = self.formatter.format(record)

        assert "test-trace-123" in formatted
        assert "test-client" in formatted
        assert "1.0.0" in formatted
        assert "client123" in formatted
        assert "testuser" in formatted
        assert "https://example.com" in formatted
        assert "GET" in formatted
        assert "/test" in formatted
        assert "TestAgent/1.0" in formatted

    def test_format_without_trace_id(self):
        """Test formatting without trace ID set."""
        set_trace_id(None)
        set_log_context({})

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = self.formatter.format(record)

        assert "no-trace" in formatted
        assert "unknown" in formatted

    @patch.dict("os.environ", {"HOSTNAME": "test-host", "APP_ENV": "test"})
    def test_format_with_environment_vars(self):
        """Test formatting includes environment variables."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = self.formatter.format(record)

        assert "test-host" in formatted
        assert "test" in formatted

    @patch.dict("os.environ", {}, clear=True)
    @patch("socket.gethostname", return_value="fallback-host")
    def test_format_with_fallback_hostname(self, mock_gethostname):
        """Test formatting uses fallback hostname when HOSTNAME not set."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = self.formatter.format(record)

        assert "fallback-host" in formatted
        assert "local" in formatted  # Default APP_ENV


class TestTqdmLoggingHandler:
    """Test cases for TqdmLoggingHandler class."""

    def test_emit_calls_tqdm_write(self):
        """Test that emit calls tqdm.write."""
        handler = TqdmLoggingHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with patch("template_agent.utils.pylogger.tqdm") as mock_tqdm:
            handler.emit(record)
            mock_tqdm.write.assert_called_once_with("Test message")

    def test_emit_handles_exception(self):
        """Test that emit handles exceptions gracefully."""
        handler = TqdmLoggingHandler()
        handler.handleError = Mock()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with patch("template_agent.utils.pylogger.tqdm") as mock_tqdm:
            mock_tqdm.write.side_effect = Exception("Test error")
            handler.emit(record)
            handler.handleError.assert_called_once_with(record)


class TestConfigureLogging:
    """Test cases for configure_logging function."""

    def test_configure_logging_default_settings(self):
        """Test configure_logging with default settings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"LOG_FILE_PATH": f"{temp_dir}/test.log"}):
                configure_logging()

                # Verify root logger is configured
                root_logger = logging.getLogger()
                assert root_logger.level == logging.INFO
                assert len(root_logger.handlers) > 0

    def test_configure_logging_custom_settings(self):
        """Test configure_logging with custom settings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = f"{temp_dir}/custom.log"
            with patch.dict("os.environ", {"LOG_FILE_PATH": log_file}):
                configure_logging(
                    log_level="DEBUG",
                    log_format="%(message)s",
                    enable_file_logging=True,
                )

                root_logger = logging.getLogger()
                assert root_logger.level == logging.DEBUG

    def test_configure_logging_without_file(self):
        """Test configure_logging with file logging disabled."""
        configure_logging(enable_file_logging=False)

        root_logger = logging.getLogger()
        # Should only have console handler, not file handler
        handler_classes = [type(h).__name__ for h in root_logger.handlers]
        assert "RotatingFileHandler" not in handler_classes

    def test_configure_logging_creates_log_directory(self):
        """Test configure_logging creates log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = os.path.join(temp_dir, "logs", "subdir")
            log_file = os.path.join(log_dir, "test.log")

            with patch.dict("os.environ", {"LOG_FILE_PATH": log_file}):
                configure_logging(enable_file_logging=True)

                assert os.path.exists(log_dir)

    def test_configure_logging_fallback_to_temp(self):
        """Test configure_logging falls back to temp directory when log dir not writable."""
        with patch("os.makedirs", side_effect=PermissionError("Access denied")):
            with patch.dict("os.environ", {"LOG_FILE_PATH": "/invalid/path/test.log"}):
                configure_logging(enable_file_logging=True)

                # Should not raise an exception and should use temp directory


class TestGetPythonLogger:
    """Test cases for get_python_logger function."""

    def test_get_python_logger_with_name(self):
        """Test get_python_logger returns logger with specified name."""
        logger = get_python_logger("test.module")
        assert logger.name == "test.module"
        assert isinstance(logger, logging.Logger)

    def test_get_python_logger_without_name(self):
        """Test get_python_logger returns default logger when name is None."""
        logger = get_python_logger(None)
        assert logger.name == "template-agent-logger"
        assert isinstance(logger, logging.Logger)

    def test_get_python_logger_default_name(self):
        """Test get_python_logger uses module name when called with __name__."""
        logger = get_python_logger(__name__)
        assert logger.name == __name__
        assert isinstance(logger, logging.Logger)


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    def test_logging_with_trace_context(self):
        """Test logging with trace context integration."""
        # Configure logging
        configure_logging(log_level="DEBUG", enable_file_logging=False)

        # Set trace context
        set_trace_id("integration-test-123")
        set_log_context(
            {"client_name": "integration-client", "client_version": "2.0.0"}
        )

        # Create logger and log message
        logger = get_python_logger("integration.test")

        # Capture log output
        with patch("sys.stdout", new=StringIO()) as captured_output:
            logger.info("Integration test message")
            output = captured_output.getvalue()

            # Verify trace context is included in output
            assert "integration-test-123" in output
            assert "integration-client" in output
            assert "2.0.0" in output

    def test_multiple_loggers_use_same_config(self):
        """Test that multiple loggers use the same configuration."""
        configure_logging(log_level="WARNING", enable_file_logging=False)

        logger1 = get_python_logger("test.module1")
        logger2 = get_python_logger("test.module2")

        # Both should inherit the WARNING level from root logger
        assert logger1.level <= logging.WARNING or logger1.level == logging.NOTSET
        assert logger2.level <= logging.WARNING or logger2.level == logging.NOTSET
