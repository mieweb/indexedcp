"""
Tests for logger module
"""
import logging
import os
import pytest
from indexedcp.logger import create_logger


def test_create_logger_basic():
    """Test basic logger creation"""
    logger = create_logger("TestLogger")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "TestLogger"


def test_create_logger_with_level():
    """Test logger creation with specific level"""
    logger = create_logger("TestLogger", level="DEBUG")
    assert logger.level == logging.DEBUG
    
    logger2 = create_logger("TestLogger2", level="ERROR")
    assert logger2.level == logging.ERROR


def test_create_logger_with_env_var(monkeypatch):
    """Test logger respects INDEXEDCP_LOG_LEVEL environment variable"""
    monkeypatch.setenv("INDEXEDCP_LOG_LEVEL", "WARNING")
    logger = create_logger("TestLogger")
    assert logger.level == logging.WARNING


def test_create_logger_default_level():
    """Test logger defaults to INFO when no level specified"""
    # Clear any env var
    if "INDEXEDCP_LOG_LEVEL" in os.environ:
        del os.environ["INDEXEDCP_LOG_LEVEL"]
    
    logger = create_logger("TestLogger")
    assert logger.level == logging.INFO


def test_logger_has_handler():
    """Test that logger has a console handler configured"""
    logger = create_logger("TestLogger")
    assert len(logger.handlers) > 0
    assert isinstance(logger.handlers[0], logging.StreamHandler)


def test_logger_no_propagation():
    """Test that logger doesn't propagate to root logger"""
    logger = create_logger("TestLogger")
    assert logger.propagate is False


def test_logger_prefix_in_output(caplog):
    """Test that logger prefix (name) appears in log output"""
    logger = create_logger("IndexedCP.Client", level="INFO")
    
    # Need to add caplog handler to our logger since we set propagate=False
    logger.addHandler(caplog.handler)
    
    with caplog.at_level(logging.INFO):
        logger.info("Test message")
    
    assert "IndexedCP.Client" in caplog.text
    assert "Test message" in caplog.text


def test_multiple_loggers():
    """Test creating multiple loggers with different names"""
    logger1 = create_logger("Module1")
    logger2 = create_logger("Module2")
    
    assert logger1.name == "Module1"
    assert logger2.name == "Module2"
    assert logger1 is not logger2


def test_logger_case_insensitive_level():
    """Test that log level is case-insensitive"""
    logger1 = create_logger("TestLogger", level="debug")
    logger2 = create_logger("TestLogger2", level="DEBUG")
    logger3 = create_logger("TestLogger3", level="DeBuG")
    
    assert logger1.level == logging.DEBUG
    assert logger2.level == logging.DEBUG
    assert logger3.level == logging.DEBUG


def test_logger_methods_work(caplog):
    """Test that all standard logging methods work"""
    logger = create_logger("TestLogger", level="DEBUG")
    
    # Need to add caplog handler to our logger since we set propagate=False
    logger.addHandler(caplog.handler)
    
    with caplog.at_level(logging.DEBUG):
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")
    
    assert "Debug message" in caplog.text
    assert "Info message" in caplog.text
    assert "Warning message" in caplog.text
    assert "Error message" in caplog.text
    assert "Critical message" in caplog.text
