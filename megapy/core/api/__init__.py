"""MEGA API module - refactored with SOLID principles."""
from .client import APIClient
from .errors import MegaAPIError, APIErrorCodes
from .events import EventEmitter
from .config import APIConfig, ProxyConfig, SSLConfig, TimeoutConfig, RetryConfig
from .async_client import AsyncAPIClient
from .async_auth import AsyncAuthService, AuthResult
from .registration import (
    AccountRegistrationBase,
    StandardAccountRegistration,
    BusinessAccountRegistration,
    EphemeralAccountCreator,
    RegistrationData,
    RegistrationResult
)

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
    
    # Registration
    'AccountRegistrationBase',
    'StandardAccountRegistration',
    'BusinessAccountRegistration',
    'EphemeralAccountCreator',
    'RegistrationData',
    'RegistrationResult',
    
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

