"""
In-memory session storage implementation.

Provides non-persistent session storage for testing and temporary use.
"""
from typing import Optional

from .protocols import SessionStorage
from .models import SessionData


class MemorySession(SessionStorage):
    """
    In-memory session storage.
    
    Stores session data in memory only.
    Data is lost when the object is destroyed.
    
    Useful for:
    - Unit testing
    - Temporary sessions
    - CI/CD environments
    
    Example:
        >>> session = MemorySession()
        >>> session.save(session_data)
        >>> loaded = session.load()
    """
    
    def __init__(self):
        """Initialize memory session storage."""
        self._data: Optional[SessionData] = None
    
    def load(self) -> Optional[SessionData]:
        """
        Load session data from memory.
        
        Returns:
            SessionData if exists, None otherwise
        """
        return self._data
    
    def save(self, data: SessionData) -> None:
        """
        Save session data to memory.
        
        Args:
            data: Session data to save
        """
        data.update_timestamp()
        self._data = data
    
    def delete(self) -> None:
        """Delete session data from memory."""
        self._data = None
    
    def exists(self) -> bool:
        """
        Check if session exists.
        
        Returns:
            True if session data exists
        """
        return self._data is not None
    
    def close(self) -> None:
        """Close storage (no-op for memory storage)."""
        pass
    
    def __enter__(self) -> 'MemorySession':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
