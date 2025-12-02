"""Tests for logging module."""
import pytest
import logging
import tempfile
import os

from megapy.core.logging import (
    MegaLogger, LogLevel, get_logger, configure_logging,
    debug, info, warning, error, critical
)


class TestMegaLogger:
    """Test suite for MegaLogger."""
    
    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset logger state before each test."""
        logger = MegaLogger()
        logger.disable_all()
        logger._logger.setLevel(logging.WARNING)
        yield
        logger.disable_all()
    
    def test_singleton_pattern(self):
        """Test MegaLogger is a singleton."""
        logger1 = MegaLogger()
        logger2 = MegaLogger()
        
        assert logger1 is logger2
    
    def test_set_level(self):
        """Test setting log level."""
        logger = MegaLogger()
        logger.set_level(LogLevel.DEBUG)
        
        assert logger.logger.level == logging.DEBUG
    
    def test_set_level_returns_self(self):
        """Test set_level returns self for chaining."""
        logger = MegaLogger()
        result = logger.set_level(LogLevel.INFO)
        
        assert result is logger
    
    def test_enable_console(self):
        """Test enabling console logging."""
        logger = MegaLogger()
        initial_handlers = len(logger._handlers)
        
        logger.enable_console(LogLevel.INFO)
        
        assert len(logger._handlers) == initial_handlers + 1
    
    def test_enable_console_returns_self(self):
        """Test enable_console returns self for chaining."""
        logger = MegaLogger()
        result = logger.enable_console()
        
        assert result is logger
    
    def test_enable_file(self):
        """Test enabling file logging."""
        logger = MegaLogger()
        initial_handlers = len(logger._handlers)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as f:
            filepath = f.name
        
        try:
            logger.enable_file(filepath)
            assert len(logger._handlers) == initial_handlers + 1
        finally:
            logger.disable_all()
            os.unlink(filepath)
    
    def test_enable_file_returns_self(self):
        """Test enable_file returns self for chaining."""
        logger = MegaLogger()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as f:
            filepath = f.name
        
        try:
            result = logger.enable_file(filepath)
            assert result is logger
        finally:
            logger.disable_all()
            os.unlink(filepath)
    
    def test_disable_all(self):
        """Test disabling all logging."""
        logger = MegaLogger()
        logger.enable_console()
        
        logger.disable_all()
        
        assert len(logger._handlers) == 0
    
    def test_method_chaining(self):
        """Test method chaining works."""
        logger = MegaLogger()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as f:
            filepath = f.name
        
        try:
            result = (logger
                     .set_level(LogLevel.DEBUG)
                     .enable_console(LogLevel.INFO)
                     .enable_file(filepath))
            
            assert result is logger
            assert len(logger._handlers) == 2
        finally:
            logger.disable_all()
            os.unlink(filepath)
    
    def test_debug_format(self):
        """Test debug format includes file and line info."""
        logger = MegaLogger()
        
        # Debug format should contain specific placeholders
        assert '%(filename)s' in logger.DEBUG_FORMAT
        assert '%(lineno)d' in logger.DEBUG_FORMAT


class TestGetLogger:
    """Test suite for get_logger function."""
    
    def test_get_logger_with_name(self):
        """Test getting logger with name."""
        logger = get_logger('test_module')
        
        assert logger.name == 'megapy.test_module'
    
    def test_get_logger_without_name(self):
        """Test getting logger without name."""
        logger = get_logger()
        
        assert logger.name == 'megapy'
    
    def test_get_logger_returns_logger_instance(self):
        """Test returns logging.Logger instance."""
        logger = get_logger('test')
        
        assert isinstance(logger, logging.Logger)


class TestConfigureLogging:
    """Test suite for configure_logging function."""
    
    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset logger state."""
        logger = MegaLogger()
        logger.disable_all()
        yield
        logger.disable_all()
    
    def test_configure_with_defaults(self):
        """Test configure with default parameters."""
        logger = configure_logging()
        
        assert logger is not None
        assert len(logger._handlers) == 1  # Console handler
    
    def test_configure_with_level(self):
        """Test configure with specific level."""
        logger = configure_logging(level=LogLevel.ERROR)
        
        assert logger.logger.level == logging.ERROR
    
    def test_configure_without_console(self):
        """Test configure without console logging."""
        logger = configure_logging(enable_console=False)
        
        assert len(logger._handlers) == 0
    
    def test_configure_with_file(self):
        """Test configure with file logging."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as f:
            filepath = f.name
        
        try:
            logger = configure_logging(log_file=filepath, enable_console=False)
            assert len(logger._handlers) == 1
        finally:
            logger.disable_all()
            os.unlink(filepath)


class TestLogLevel:
    """Test suite for LogLevel enum."""
    
    def test_debug_level(self):
        """Test DEBUG level value."""
        assert LogLevel.DEBUG.value == logging.DEBUG
    
    def test_info_level(self):
        """Test INFO level value."""
        assert LogLevel.INFO.value == logging.INFO
    
    def test_warning_level(self):
        """Test WARNING level value."""
        assert LogLevel.WARNING.value == logging.WARNING
    
    def test_error_level(self):
        """Test ERROR level value."""
        assert LogLevel.ERROR.value == logging.ERROR
    
    def test_critical_level(self):
        """Test CRITICAL level value."""
        assert LogLevel.CRITICAL.value == logging.CRITICAL


class TestModuleLevelFunctions:
    """Test module-level logging functions."""
    
    def test_debug_callable(self):
        """Test debug function is callable."""
        assert callable(debug)
    
    def test_info_callable(self):
        """Test info function is callable."""
        assert callable(info)
    
    def test_warning_callable(self):
        """Test warning function is callable."""
        assert callable(warning)
    
    def test_error_callable(self):
        """Test error function is callable."""
        assert callable(error)
    
    def test_critical_callable(self):
        """Test critical function is callable."""
        assert callable(critical)
