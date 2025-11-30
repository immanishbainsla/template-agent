"""Tests for the uvicorn_logging_config module."""

import json
import os
import tempfile
from unittest.mock import patch

from template_agent.utils.uvicorn_logging_config import (
    get_uvicorn_log_config,
    write_uvicorn_log_config_file,
)
from template_agent.utils.trace_context import set_trace_id, set_log_context


class TestGetUvicornLogConfig:
    """Test cases for get_uvicorn_log_config function."""

    def test_get_uvicorn_log_config_default_settings(self):
        """Test get_uvicorn_log_config with default settings."""
        with patch.dict("os.environ", {"PYTHON_LOG_LEVEL": "INFO"}):
            config = get_uvicorn_log_config()

            assert config["version"] == 1
            assert config["disable_existing_loggers"] is False
            assert "template-agent-logger" in config["formatters"]
            assert "console" in config["handlers"]
            assert "file" in config["handlers"]

            # Check uvicorn loggers are configured
            assert "uvicorn" in config["loggers"]
            assert "uvicorn.access" in config["loggers"]
            assert "uvicorn.error" in config["loggers"]
            assert "uvicorn.asgi" in config["loggers"]
            assert "template_agent" in config["loggers"]

    def test_get_uvicorn_log_config_custom_log_level(self):
        """Test get_uvicorn_log_config with custom log level."""
        with patch.dict("os.environ", {"PYTHON_LOG_LEVEL": "DEBUG"}):
            config = get_uvicorn_log_config()

            # Check that loggers use the custom log level
            for logger_name in [
                "uvicorn",
                "uvicorn.access",
                "uvicorn.error",
                "template_agent",
            ]:
                assert config["loggers"][logger_name]["level"] == "DEBUG"

    def test_get_uvicorn_log_config_custom_log_file_path(self):
        """Test get_uvicorn_log_config with custom log file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_log_path = os.path.join(temp_dir, "custom_uvicorn.log")
            with patch.dict("os.environ", {"LOG_FILE_PATH": custom_log_path}):
                config = get_uvicorn_log_config()

                assert config["handlers"]["file"]["filename"] == custom_log_path

    def test_get_uvicorn_log_config_creates_log_directory(self):
        """Test that get_uvicorn_log_config creates log directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_subdir = os.path.join(temp_dir, "uvicorn_logs")
            log_file = os.path.join(log_subdir, "uvicorn.log")

            with patch.dict("os.environ", {"LOG_FILE_PATH": log_file}):
                config = get_uvicorn_log_config()

                assert os.path.exists(log_subdir)
                assert config["handlers"]["file"]["filename"] == log_file

    def test_get_uvicorn_log_config_fallback_to_temp(self):
        """Test fallback to temp directory when log path is not writable."""
        with patch("os.makedirs", side_effect=PermissionError("Access denied")):
            with patch.dict(
                "os.environ", {"LOG_FILE_PATH": "/invalid/uvicorn/path/test.log"}
            ):
                config = get_uvicorn_log_config()

                # Should fall back to temp directory
                expected_path = os.path.join(tempfile.gettempdir(), "app.log")
                assert config["handlers"]["file"]["filename"] == expected_path

    def test_uvicorn_formatter_configuration(self):
        """Test that uvicorn formatter is correctly configured."""
        config = get_uvicorn_log_config()

        formatter_config = config["formatters"]["template-agent-logger"]
        assert (
            formatter_config["()"]
            == "template_agent.utils.uvicorn_logging_config.UvicornTraceFormatter"
        )
        assert "timestamp=" in formatter_config["format"]
        assert "trace_id=" in formatter_config["format"]
        assert "client.name=" in formatter_config["format"]
        assert "log_message=" in formatter_config["format"]

    def test_handler_configuration(self):
        """Test that handlers are correctly configured."""
        config = get_uvicorn_log_config()

        console_handler = config["handlers"]["console"]
        assert console_handler["class"] == "logging.StreamHandler"
        assert console_handler["formatter"] == "template-agent-logger"
        assert console_handler["stream"] == "ext://sys.stdout"

        file_handler = config["handlers"]["file"]
        assert file_handler["class"] == "logging.handlers.RotatingFileHandler"
        assert file_handler["formatter"] == "template-agent-logger"
        assert file_handler["maxBytes"] == 52428800  # 50MB
        assert file_handler["backupCount"] == 5
        assert file_handler["encoding"] == "utf-8"

    def test_logger_configuration(self):
        """Test that loggers are correctly configured."""
        config = get_uvicorn_log_config()

        for logger_name in [
            "uvicorn",
            "uvicorn.error",
            "uvicorn.access",
            "uvicorn.asgi",
            "watchfiles",
            "template_agent",
        ]:
            logger_config = config["loggers"][logger_name]
            assert logger_config["handlers"] == ["console", "file"]
            assert logger_config["propagate"] is False

        # Test root logger
        root_config = config["root"]
        assert root_config["handlers"] == ["console", "file"]


class TestWriteUvicornLogConfigFile:
    """Test cases for write_uvicorn_log_config_file function."""

    def test_write_uvicorn_log_config_file(self):
        """Test writing uvicorn log config to file."""
        config_file_path = write_uvicorn_log_config_file()

        try:
            # Verify file was created
            assert os.path.exists(config_file_path)
            assert config_file_path.endswith("_uvicorn_log_config.json")

            # Verify content is valid JSON and matches expected structure
            with open(config_file_path, "r") as f:
                written_config = json.load(f)

            expected_config = get_uvicorn_log_config()
            assert written_config == expected_config

        finally:
            # Clean up the temporary file
            if os.path.exists(config_file_path):
                os.unlink(config_file_path)

    def test_write_uvicorn_log_config_file_with_custom_settings(self):
        """Test writing config file with custom environment settings."""
        with patch.dict("os.environ", {"PYTHON_LOG_LEVEL": "WARNING"}):
            config_file_path = write_uvicorn_log_config_file()

            try:
                with open(config_file_path, "r") as f:
                    written_config = json.load(f)

                # Verify custom log level is reflected in the file
                for logger_name in ["uvicorn", "uvicorn.access", "template_agent"]:
                    assert written_config["loggers"][logger_name]["level"] == "WARNING"

            finally:
                if os.path.exists(config_file_path):
                    os.unlink(config_file_path)


class TestUvicornLoggingIntegration:
    """Integration tests for uvicorn logging functionality."""

    def test_config_structure_completeness(self):
        """Test that the config structure is complete and valid."""
        config = get_uvicorn_log_config()

        # Required top-level keys
        required_keys = [
            "version",
            "disable_existing_loggers",
            "formatters",
            "handlers",
            "loggers",
            "root",
        ]
        for key in required_keys:
            assert key in config

        # Verify all referenced formatters exist
        for handler_name, handler_config in config["handlers"].items():
            formatter_name = handler_config["formatter"]
            assert formatter_name in config["formatters"]

        # Verify all logger handlers exist
        for logger_name, logger_config in config["loggers"].items():
            for handler_name in logger_config["handlers"]:
                assert handler_name in config["handlers"]

    def test_formatter_class_path_is_valid(self):
        """Test that the formatter class path is importable."""
        config = get_uvicorn_log_config()
        formatter_class_path = config["formatters"]["template-agent-logger"]["()"]

        # Should be able to import the formatter class
        module_path, class_name = formatter_class_path.rsplit(".", 1)
        import importlib

        module = importlib.import_module(module_path)
        formatter_class = getattr(module, class_name)

        # Should be able to instantiate it
        formatter = formatter_class()
        assert hasattr(formatter, "format")

    def test_log_rotation_settings(self):
        """Test that log rotation settings are properly configured."""
        config = get_uvicorn_log_config()
        file_handler = config["handlers"]["file"]

        assert file_handler["maxBytes"] == 52428800  # 50MB
        assert file_handler["backupCount"] == 5
        assert file_handler["encoding"] == "utf-8"

        # Verify the handler class supports rotation
        assert file_handler["class"] == "logging.handlers.RotatingFileHandler"
