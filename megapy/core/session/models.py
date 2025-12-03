"""
Session data models.

Contains data classes for session information.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class SessionData:
    """
    Complete session data for MEGA authentication.
    
    Contains all information needed to resume a session
    without re-entering credentials.
    
    Attributes:
        email: User email address
        session_id: MEGA session ID (sid)
        user_id: MEGA user ID
        user_name: Display name
        master_key: Master encryption key (16 bytes)
        private_key: RSA private key (encrypted, optional)
        rsa_private_key_data: Raw RSA key components
        created_at: Session creation timestamp
        updated_at: Last update timestamp
    """
    email: str
    session_id: str
    user_id: str
    user_name: str
    master_key: bytes
    private_key: Optional[bytes] = None
    rsa_private_key_data: Optional[bytes] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            'email': self.email,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'master_key': self.master_key.hex(),
            'private_key': self.private_key.hex() if self.private_key else None,
            'rsa_private_key_data': self.rsa_private_key_data.hex() if self.rsa_private_key_data else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SessionData':
        """
        Create from dictionary.
        
        Args:
            data: Dictionary with session data
            
        Returns:
            SessionData instance
        """
        return cls(
            email=data['email'],
            session_id=data['session_id'],
            user_id=data['user_id'],
            user_name=data['user_name'],
            master_key=bytes.fromhex(data['master_key']),
            private_key=bytes.fromhex(data['private_key']) if data.get('private_key') else None,
            rsa_private_key_data=bytes.fromhex(data['rsa_private_key_data']) if data.get('rsa_private_key_data') else None,
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.now(),
        )
    
    def to_json(self) -> str:
        """
        Serialize to JSON string.
        
        Returns:
            JSON string
        """
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SessionData':
        """
        Create from JSON string.
        
        Args:
            json_str: JSON string
            
        Returns:
            SessionData instance
        """
        return cls.from_dict(json.loads(json_str))
    
    def is_valid(self) -> bool:
        """
        Check if session data is valid.
        
        Returns:
            True if all required fields are present
        """
        return bool(
            self.email and
            self.session_id and
            self.user_id and
            self.master_key and
            len(self.master_key) == 16
        )
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to now."""
        self.updated_at = datetime.now()
