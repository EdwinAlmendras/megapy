"""Logging utilities for megapy modules."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Get a logger that automatically inherits from root logger.
    
    This ensures that loggers work with basicConfig() without needing
    explicit setup_logging() calls. The logger will:
    - Propagate to root logger (default behavior)
    - Only set a default level if root logger has no handlers
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.propagate = True
    
    # Only set default level if root logger has no handlers
    # (i.e., basicConfig hasn't been called yet)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logger.setLevel(logging.WARNING)  # Default to WARNING if no basicConfig
    
    return logger
