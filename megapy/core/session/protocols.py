"""
Session storage protocols.

Defines interfaces for session storage implementations.
Follows Interface Segregation Principle (ISP).
"""
from typing import Protocol, Optional, runtime_checkable
from .models import SessionData


@runtime_checkable
class SessionStorage(Protocol):
    """
    Protocol for session storage implementations.
    
    Implementations can use SQLite, JSON, Redis, or any other storage backend.
    Follows Dependency Inversion Principle (DIP).
    """
    
    def load(self) -> Optional[SessionData]:
        """
        Load session data from storage.
        
        Returns:
            SessionData if session exists, None otherwise
        """
        ...
    
    def save(self, data: SessionData) -> None:
        """
        Save session data to storage.
        
        Args:
            data: Session data to save
        """
        ...
    
    def delete(self) -> None:
        """
        Delete session data from storage.
        """
        ...
    
    def exists(self) -> bool:
        """
        Check if session exists in storage.
        
        Returns:
            True if session exists
        """
        ...
    
    def close(self) -> None:
        """
        Close storage connection and release resources.
        """
        ...


@runtime_checkable
class SessionStorageAsync(Protocol):
    """
    Async protocol for session storage implementations.
    
    For storage backends that support async operations.
    """
    
    async def load(self) -> Optional[SessionData]:
        """Load session data asynchronously."""
        ...
    
    async def save(self, data: SessionData) -> None:
        """Save session data asynchronously."""
        ...
    
    async def delete(self) -> None:
        """Delete session data asynchronously."""
        ...
    
    async def exists(self) -> bool:
        """Check if session exists asynchronously."""
        ...
    
    async def close(self) -> None:
        """Close storage connection asynchronously."""
        ...
