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
from .client import MegaClient, UserInfo
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

__all__ = [
    'MegaClient',
    'Node',
    'MegaFile',  # Alias
    'MegaNode',  # Alias
    'UserInfo',
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
]