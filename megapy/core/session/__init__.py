"""
Session management module.

Provides persistent session storage for MEGA authentication.
Supports SQLite storage similar to Telethon's session system.
"""
from .protocols import SessionStorage
from .models import SessionData
from .sqlite_session import SQLiteSession
from .memory_session import MemorySession

__all__ = [
    'SessionStorage',
    'SessionData',
    'SQLiteSession',
    'MemorySession',
]
