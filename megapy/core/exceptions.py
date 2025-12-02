"""
Custom exceptions for MEGA storage operations.

This module defines exception classes specific to MEGA file operations.
"""
from typing import Optional, Any


class MegaException(Exception):
    """Base exception for all MEGA-related errors."""
    
    def __init__(self, message: str, error_code: Optional[int] = None) -> None:
        """
        Initialize the exception.
        
        Args:
            message: Error message
            error_code: Numeric error code (if available)
        """
        self.error_code = error_code
        super().__init__(message)


class MegaAuthError(MegaException):
    """Exception raised for authentication-related errors."""
    pass


class MegaRequestError(MegaException):
    """Exception raised for API request errors."""
    pass


class MegaDecryptionError(MegaException):
    """Exception raised when decryption of data fails."""
    
    def __init__(
        self, 
        message: str, 
        node_handle: Optional[str] = None, 
        error_code: Optional[int] = None
    ) -> None:
        """
        Initialize the exception.
        
        Args:
            message: Error message
            node_handle: Handle of the node that failed to decrypt
            error_code: Numeric error code (if available)
        """
        self.node_handle = node_handle
        super().__init__(message, error_code)


class MegaNodeError(MegaException):
    """Exception raised for node-related operations."""
    pass


class MegaFileNotFoundError(MegaNodeError):
    """Exception raised when a node is not found."""
    pass


class MegaAttributeError(MegaNodeError):
    """Exception raised when node attributes cannot be processed."""
    
    def __init__(
        self, 
        message: str, 
        node_handle: Optional[str] = None, 
        attribute_data: Any = None, 
        error_code: Optional[int] = None
    ) -> None:
        """
        Initialize the exception.
        
        Args:
            message: Error message
            node_handle: Handle of the node with attribute issues
            attribute_data: Raw attribute data (if available)
            error_code: Numeric error code (if available)
        """
        self.node_handle = node_handle
        self.attribute_data = attribute_data
        super().__init__(message, error_code) 