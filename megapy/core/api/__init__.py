"""MEGA API module - refactored with SOLID principles."""
from .client import APIClient
from .errors import MegaAPIError, APIErrorCodes
from .events import EventEmitter
from .config import APIConfig, ProxyConfig, SSLConfig, TimeoutConfig, RetryConfig
from .async_client import AsyncAPIClient
from .async_auth import AsyncAuthService, AuthResult

# Backward compatibility
MegaApi = APIClient
MegaEventEmitter = EventEmitter

__all__ = [
    # Sync client
    'APIClient',
    'MegaApi',
    
    # Async client
    'AsyncAPIClient',
    'AsyncAuthService',
    'AuthResult',
    
    # Configuration
    'APIConfig',
    'ProxyConfig',
    'SSLConfig',
    'TimeoutConfig',
    'RetryConfig',
    
    # Errors
    'MegaAPIError',
    'APIErrorCodes',
    
    # Events
    'EventEmitter',
    'MegaEventEmitter',
]

