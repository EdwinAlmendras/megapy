"""User credentials and session models."""
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class UserCredentials:
    """User credentials for MEGA authentication."""
    email: str
    password: str


@dataclass
class SessionData:
    """Session data for resuming MEGA sessions."""
    session_id: str
    key: bytes


@dataclass
class LoginResult:
    """Result of a successful login operation."""
    session_id: str
    user_id: str
    user_name: str
    file_count: int
    master_key: bytes

