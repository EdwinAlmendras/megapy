"""
Attribute models for MEGA files.

Keys are minimized to save space (following MEGA conventions):
- n: name
- lbl: label (color)
- fav: favorite
- e: extra/custom attributes
  - i: document_id
  - u: url
  - d: date
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, Union
from enum import IntEnum
from datetime import datetime


class AttributeType(IntEnum):
    """Type of file attribute upload."""
    FILE = 0
    THUMBNAIL = 1
    PREVIEW = 2


@dataclass
class CustomAttributes:
    """
    Custom attributes stored in the 'e' (extra) object.
    
    All fields use minimized keys to save space:
    - i: document_id
    - u: url  
    - d: date (Unix timestamp)
    
    Example:
        >>> attrs = CustomAttributes(document_id="DOC123", url="https://example.com")
        >>> attrs.to_dict()
        {'i': 'DOC123', 'u': 'https://example.com'}
    """
    document_id: Optional[str] = None  # i
    url: Optional[str] = None  # u
    date: Optional[Union[int, datetime]] = None  # d (Unix timestamp)
    
    # Additional custom fields (minimized keys)
    _extra: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Convert datetime to timestamp
        if isinstance(self.date, datetime):
            self.date = int(self.date.timestamp())
    
    def set(self, key: str, value: Any) -> 'CustomAttributes':
        """
        Set a custom attribute with minimized key.
        
        Args:
            key: Single character key (e.g., 't' for type)
            value: Attribute value
            
        Returns:
            Self for chaining
        """
        if len(key) > 2:
            raise ValueError(f"Key should be 1-2 characters for space efficiency: {key}")
        self._extra[key] = value
        return self
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a custom attribute."""
        return self._extra.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary with minimized keys.
        
        Returns:
            Dict with minimized keys (i, u, d, etc.)
        """
        result = {}
        
        if self.document_id is not None:
            result['i'] = self.document_id
        if self.url is not None:
            result['u'] = self.url
        if self.date is not None:
            result['d'] = self.date
        
        # Add extra attributes
        result.update(self._extra)
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CustomAttributes':
        """
        Create from dictionary with minimized keys.
        
        Args:
            data: Dict with minimized keys
            
        Returns:
            CustomAttributes instance
        """
        known_keys = {'i', 'u', 'd'}
        extra = {k: v for k, v in data.items() if k not in known_keys}
        
        return cls(
            document_id=data.get('i'),
            url=data.get('u'),
            date=data.get('d'),
            _extra=extra
        )


@dataclass
class FileAttributes:
    """
    Complete file attributes for MEGA.
    
    Standard attributes:
    - n: name (required)
    - t: modification time (Unix timestamp in seconds)
    - lbl: label/color (0-7)
    - fav: favorite (0/1)
    - e: extra/custom attributes
    
    The modification time (mtime) is stored in the 't' attribute as a Unix
    timestamp (seconds since epoch). This preserves the original file's
    modification date when uploading to MEGA, matching the official web client
    behavior.
    
    Example:
        >>> attrs = FileAttributes(
        ...     name="document.pdf",
        ...     mtime=1701532800,  # Dec 2, 2023
        ...     label=1,
        ...     custom=CustomAttributes(document_id="DOC123")
        ... )
        >>> attrs.to_dict()
        {'n': 'document.pdf', 't': 1701532800, 'lbl': 1, 'e': {'i': 'DOC123'}}
    """
    name: str  # n (required)
    mtime: Optional[Union[int, datetime]] = None  # t (modification time as Unix timestamp)
    label: int = 0  # lbl (0=none, 1=red, 2=orange, 3=yellow, 4=green, 5=blue, 6=purple, 7=grey)
    favorite: bool = False  # fav
    custom: Optional[CustomAttributes] = None  # e
    
    # Raw extra data from API (for unknown fields)
    _raw: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Convert datetime to Unix timestamp
        if isinstance(self.mtime, datetime):
            self.mtime = int(self.mtime.timestamp())
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary with minimized keys for MEGA API.
        
        Returns:
            Dict ready for JSON serialization
        """
        result: Dict[str, Any] = {'n': self.name}
        
        # Modification time (stored as 't' attribute)
        if self.mtime is not None:
            result['t'] = self.mtime
        
        if self.label > 0:
            result['lbl'] = self.label
        
        if self.favorite:
            result['fav'] = 1
        
        if self.custom:
            custom_dict = self.custom.to_dict()
            if custom_dict:  # Only add if not empty
                result['e'] = custom_dict
        
        # Include any raw/unknown fields
        for key, value in self._raw.items():
            if key not in ('n', 't', 'lbl', 'fav', 'e'):
                result[key] = value
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileAttributes':
        """
        Create from dictionary with minimized keys.
        
        Args:
            data: Dict from MEGA API
            
        Returns:
            FileAttributes instance
        """
        custom = None
        if 'e' in data and isinstance(data['e'], dict):
            custom = CustomAttributes.from_dict(data['e'])
        
        known_keys = {'n', 't', 'lbl', 'fav', 'e'}
        raw = {k: v for k, v in data.items() if k not in known_keys}
        
        return cls(
            name=data.get('n', ''),
            mtime=data.get('t'),
            label=data.get('lbl', 0),
            favorite=bool(data.get('fav', 0)),
            custom=custom,
            _raw=raw
        )
    
    def with_custom(self, **kwargs) -> 'FileAttributes':
        """
        Add custom attributes.
        
        Args:
            **kwargs: Custom attribute values
            
        Returns:
            Self for chaining
        """
        if self.custom is None:
            self.custom = CustomAttributes()
        
        for key, value in kwargs.items():
            if key == 'document_id':
                self.custom.document_id = value
            elif key == 'url':
                self.custom.url = value
            elif key == 'date':
                self.custom.date = value
            else:
                # Use first character as key for unknowns
                self.custom.set(key[0] if len(key) > 1 else key, value)
        
        return self
