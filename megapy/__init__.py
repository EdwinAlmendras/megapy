"""
MegaPy - Async Python library for MEGA cloud storage.

Usage:
    >>> from megapy import MegaClient
    >>> 
    >>> async with MegaClient("session") as mega:
    ...     root = await mega.get_root()
    ...     for node in root:
    ...         print(node)
"""
import logging
from .client import MegaClient, UserInfo, AccountInfo
from .node import Node

# Backward compatibility aliases
MegaFile = Node
MegaNode = Node

# Configuration
from .core.api import (
    APIConfig,
    ProxyConfig,
    SSLConfig,
    TimeoutConfig,
    RetryConfig,
    AsyncAPIClient,
    AsyncAuthService
)

# Session management
from .core.session import (
    SessionStorage,
    SessionData,
    SQLiteSession,
    MemorySession
)

__version__ = '1.0.0'


def setup_logging(level=logging.INFO):
    """
    Configure logging for megapy modules.
    
    This ensures that all megapy loggers are properly configured
    to show log messages at the specified level.
    
    Args:
        level: Logging level (default: logging.INFO)
    """
    # Configure megapy loggers
    loggers = [
        'megapy',
        'megapy.client',
        'megapy.upload',
        'megapy.upload.chunk',
        'megapy.upload.file',
        'megapy.upload.node',
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        # Ensure propagation is enabled
        logger.propagate = True


__all__ = [
    'MegaClient',
    'Node',
    'MegaFile',  # Alias
    'MegaNode',  # Alias
    'UserInfo',
    'AccountInfo',
    'SessionStorage',
    'SessionData',
    'SQLiteSession',
    'MemorySession',
    'APIConfig',
    'ProxyConfig', 
    'SSLConfig',
    'TimeoutConfig',
    'RetryConfig',
    'AsyncAPIClient',
    'AsyncAuthService',
    'setup_logging',
]