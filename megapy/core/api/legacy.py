"""Legacy API module - backward compatibility layer."""
from . import APIClient, MegaAPIError, EventEmitter, APIErrorCodes

# Backward compatibility
MegaApi = APIClient
MegaEventEmitter = EventEmitter

# Legacy constants
DEFAULT_GATEWAY = APIClient.DEFAULT_GATEWAY
MAX_RETRIES = 4
ERRORS = APIErrorCodes.ERROR_CODES

__all__ = [
    'MegaApi',
    'MegaAPIError',
    'MegaEventEmitter',
    'DEFAULT_GATEWAY',
    'MAX_RETRIES',
    'ERRORS',
]
