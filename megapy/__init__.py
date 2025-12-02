"""
MegaPy - Professional Python library for MEGA cloud storage.

Session-based usage (like Telethon):
    >>> from megapy import MegaClient
    >>> 
    >>> client = MegaClient("my_session")
    >>> await client.start()  # Prompts for credentials if needed
    >>> files = await client.list_files()

Direct credentials usage:
    >>> async with MegaClient(email, password) as mega:
    ...     files = await mega.list_files()
    ...     await mega.upload("file.txt")
"""
from .client import MegaClient, MegaFile, UserInfo
from .nodes import MegaNode, MegaNodeBuilder
from .core.storage.facade import StorageFacade

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
    # Main client
    'MegaClient',
    'MegaFile',
    'UserInfo',
    'MegaNode',
    'MegaNodeBuilder',
    
    # Session management
    'SessionStorage',
    'SessionData',
    'SQLiteSession',
    'MemorySession',
    
    # Configuration
    'APIConfig',
    'ProxyConfig', 
    'SSLConfig',
    'TimeoutConfig',
    'RetryConfig',
    
    # Low-level async
    'AsyncAPIClient',
    'AsyncAuthService',
    
    # Legacy
    'StorageFacade',
]