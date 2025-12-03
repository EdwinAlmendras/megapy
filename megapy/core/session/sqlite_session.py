"""
SQLite session storage implementation.

Provides persistent session storage using SQLite database.
Similar to Telethon's session system.
"""
import json
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Union, Any
from contextlib import contextmanager

from .protocols import SessionStorage
from .models import SessionData


class SQLiteSession(SessionStorage):
    """
    SQLite-based session storage.
    
    Stores session data in a local SQLite database file.
    Thread-safe implementation with connection pooling.
    
    Example:
        >>> session = SQLiteSession("my_account")
        >>> # Creates my_account.session file
        >>> 
        >>> session.save(session_data)
        >>> loaded = session.load()
    """
    
    EXTENSION = '.session'
    SCHEMA_VERSION = 1
    
    def __init__(
        self,
        session_name: Union[str, Path],
        base_path: Optional[Path] = None
    ):
        """
        Initialize SQLite session storage.
        
        Args:
            session_name: Session name (without extension) or full path
            base_path: Optional base directory for session files
        """
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        
        # Determine file path
        if isinstance(session_name, Path) or session_name.endswith(self.EXTENSION):
            self._path = Path(session_name)
        else:
            if base_path:
                self._path = base_path / f"{session_name}{self.EXTENSION}"
            else:
                self._path = Path(f"{session_name}{self.EXTENSION}")
        
        # Ensure parent directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    @property
    def path(self) -> Path:
        """Get session file path."""
        return self._path
    
    @contextmanager
    def _get_connection(self):
        """Get thread-safe database connection."""
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(
                    str(self._path),
                    check_same_thread=False
                )
                self._conn.row_factory = sqlite3.Row
            yield self._conn
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create version table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS version (
                    version INTEGER PRIMARY KEY
                )
            ''')
            
            # Create session table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    master_key BLOB NOT NULL,
                    private_key BLOB,
                    rsa_private_key_data BLOB,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # Create cache table for codecs, etc.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # Set schema version
            cursor.execute('SELECT version FROM version LIMIT 1')
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    'INSERT INTO version (version) VALUES (?)',
                    (self.SCHEMA_VERSION,)
                )
            
            conn.commit()
    
    def load(self) -> Optional[SessionData]:
        """
        Load session data from database.
        
        Returns:
            SessionData if exists, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT email, session_id, user_id, user_name,
                       master_key, private_key, rsa_private_key_data,
                       created_at, updated_at
                FROM session
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            if row is None:
                return None
            
            return SessionData(
                email=row['email'],
                session_id=row['session_id'],
                user_id=row['user_id'],
                user_name=row['user_name'] or '',
                master_key=row['master_key'],
                private_key=row['private_key'],
                rsa_private_key_data=row['rsa_private_key_data'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at']),
            )
    
    def save(self, data: SessionData) -> None:
        """
        Save session data to database.
        
        Args:
            data: Session data to save
        """
        data.update_timestamp()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Delete existing session
            cursor.execute('DELETE FROM session')
            
            # Insert new session
            cursor.execute('''
                INSERT INTO session (
                    email, session_id, user_id, user_name,
                    master_key, private_key, rsa_private_key_data,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.email,
                data.session_id,
                data.user_id,
                data.user_name,
                data.master_key,
                data.private_key,
                data.rsa_private_key_data,
                data.created_at.isoformat(),
                data.updated_at.isoformat(),
            ))
            
            conn.commit()
    
    def delete(self) -> None:
        """Delete session data from database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM session')
            conn.commit()
    
    def exists(self) -> bool:
        """
        Check if session exists.
        
        Returns:
            True if session data exists
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM session')
            count = cursor.fetchone()[0]
            return count > 0
    
    def close(self) -> None:
        """Close database connection."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
    
    def delete_file(self) -> None:
        """Delete the session file completely."""
        self.close()
        if self._path.exists():
            self._path.unlink()
    
    def get_cache(self, key: str) -> Optional[Any]:
        """
        Get cached value by key.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT value FROM cache WHERE key = ?',
                (key,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            try:
                return json.loads(row['value'])
            except (json.JSONDecodeError, TypeError):
                return None
    
    def set_cache(self, key: str, value: Any) -> None:
        """
        Set cached value.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO cache (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, json.dumps(value), datetime.now().isoformat()))
            conn.commit()
    
    def __enter__(self) -> 'SQLiteSession':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __del__(self):
        """Destructor - ensure connection is closed."""
        try:
            self.close()
        except Exception:
            pass
