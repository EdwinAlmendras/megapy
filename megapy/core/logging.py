"""Logging configuration for MegaPy."""
import logging
import sys
from typing import Optional
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class MegaLogger:
    """Centralized logger for MegaPy library."""
    
    _instance: Optional['MegaLogger'] = None
    _logger: Optional[logging.Logger] = None
    
    DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DEBUG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._logger = logging.getLogger('megapy')
        self._logger.setLevel(logging.WARNING)
        self._handlers = []
    
    @property
    def logger(self) -> logging.Logger:
        """Returns the underlying logger."""
        return self._logger
    
    def set_level(self, level: LogLevel) -> 'MegaLogger':
        """Sets the log level."""
        self._logger.setLevel(level.value)
        return self
    
    def enable_console(self, level: LogLevel = LogLevel.INFO, 
                       use_debug_format: bool = False) -> 'MegaLogger':
        """Enables console logging."""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level.value)
        
        fmt = self.DEBUG_FORMAT if use_debug_format else self.DEFAULT_FORMAT
        handler.setFormatter(logging.Formatter(fmt))
        
        self._logger.addHandler(handler)
        self._handlers.append(handler)
        return self
    
    def enable_file(self, filepath: str, level: LogLevel = LogLevel.DEBUG,
                    use_debug_format: bool = True) -> 'MegaLogger':
        """Enables file logging."""
        handler = logging.FileHandler(filepath, encoding='utf-8')
        handler.setLevel(level.value)
        
        fmt = self.DEBUG_FORMAT if use_debug_format else self.DEFAULT_FORMAT
        handler.setFormatter(logging.Formatter(fmt))
        
        self._logger.addHandler(handler)
        self._handlers.append(handler)
        return self
    
    def disable_all(self) -> 'MegaLogger':
        """Disables all logging."""
        for handler in self._handlers:
            self._logger.removeHandler(handler)
        self._handlers.clear()
        return self
    
    def debug(self, msg: str, *args, **kwargs):
        """Logs debug message."""
        self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """Logs info message."""
        self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Logs warning message."""
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """Logs error message."""
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        """Logs critical message."""
        self._logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        """Logs exception with traceback."""
        self._logger.exception(msg, *args, **kwargs)


def get_logger(name: str = None) -> logging.Logger:
    """
    Gets a logger instance for a module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f'megapy.{name}')
    return logging.getLogger('megapy')


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    enable_console: bool = True,
    log_file: Optional[str] = None,
    debug_format: bool = False
) -> MegaLogger:
    """
    Configures MegaPy logging.
    
    Args:
        level: Minimum log level
        enable_console: Whether to log to console
        log_file: Optional file path for file logging
        debug_format: Use detailed format with file/line info
        
    Returns:
        Configured MegaLogger instance
    """
    logger = MegaLogger()
    logger.set_level(level)
    
    if enable_console:
        logger.enable_console(level, debug_format)
    
    if log_file:
        logger.enable_file(log_file, LogLevel.DEBUG, debug_format)
    
    return logger


# Module-level logger for convenience
_mega_logger = MegaLogger()


def debug(msg: str, *args, **kwargs):
    """Logs debug message."""
    _mega_logger.debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """Logs info message."""
    _mega_logger.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """Logs warning message."""
    _mega_logger.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """Logs error message."""
    _mega_logger.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    """Logs critical message."""
    _mega_logger.critical(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs):
    """Logs exception with traceback."""
    _mega_logger.exception(msg, *args, **kwargs)
