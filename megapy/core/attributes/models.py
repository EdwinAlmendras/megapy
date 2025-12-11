"""
Attribute models for MEGA files.

Keys are minimized to save space (following MEGA conventions):
- n: name
- t: modification time
- lbl: label (color)
- fav: favorite
- m: mega_id (links to MongoDB)

All custom attributes are stored FLAT (not nested).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union, Set
from enum import IntEnum
from datetime import datetime


class AttributeType(IntEnum):
    """Type of file attribute upload."""
    FILE = 0
    THUMBNAIL = 1
    PREVIEW = 2


@dataclass
class FileAttributes:
    """
    Complete file attributes for MEGA.
    
    All attributes are stored FLAT (not nested):
    - n: name (required)
    - t: modification time (Unix timestamp)
    - lbl: label/color (0-7)
    - fav: favorite (0/1)
    - m: mega_id (links to MongoDB source_id)
    
    Example:
        >>> attrs = FileAttributes(name="video.mp4", mega_id="abc123")
        >>> attrs.to_dict()
        {'n': 'video.mp4', 'm': 'abc123'}
        
        >>> # With exclusions (for storage)
        >>> attrs.to_dict(exclude={'m'})
        {'n': 'video.mp4'}
    """
    name: str  # n (required)
    mtime: Optional[Union[int, datetime]] = None  # t
    label: int = 0  # lbl
    favorite: bool = False  # fav
    mega_id: Optional[str] = None  # m (links to MongoDB)
    c: Optional[str] = None  # c (checksum, optional)
    # Extra custom attributes (flat, single-char keys)
    _extra: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.mtime, datetime):
            self.mtime = int(self.mtime.timestamp())
    
    def set(self, key: str, value: Any) -> 'FileAttributes':
        """
        Set a custom attribute.
        
        Args:
            key: Short key (1-2 chars recommended)
            value: Attribute value
        """
        self._extra[key] = value
        return self
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a custom attribute."""
        return self._extra.get(key, default)
    
    def to_dict(self, exclude: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        Convert to dictionary with minimized keys.
        
        Args:
            exclude: Set of keys to exclude (e.g., {'m'} to exclude mega_id)
        
        Returns:
            Dict ready for JSON serialization
        """
        exclude = exclude or set()
        result: Dict[str, Any] = {'n': self.name}
        
        if self.mtime is not None and 't' not in exclude:
            result['t'] = self.mtime
        
        if self.label > 0 and 'lbl' not in exclude:
            result['lbl'] = self.label
        
        if self.favorite and 'fav' not in exclude:
            result['fav'] = 1
        
        if self.mega_id is not None and 'm' not in exclude:
            result['m'] = self.mega_id
        
        # Add extra attributes (excluding specified keys)
        for key, value in self._extra.items():
            if key not in exclude:
                result[key] = value
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileAttributes':
        """
        Create from dictionary.
        
        Args:
            data: Dict from MEGA API
            
        Returns:
            FileAttributes instance
        """
        known_keys = {'n', 't', 'lbl', 'fav', 'm'}
        extra = {k: v for k, v in data.items() if k not in known_keys}
        
        return cls(
            name=data.get('n', ''),
            mtime=data.get('t'),
            label=data.get('lbl', 0),
            favorite=bool(data.get('fav', 0)),
            mega_id=data.get('m'),
            #**extra
        )
    
    @classmethod
    def create(
        cls,
        name: str,
        mega_id: Optional[str] = None,
        mtime: Optional[Union[int, datetime]] = None,
        **extra
    ) -> 'FileAttributes':
        """
        Factory method for creating FileAttributes.
        
        Args:
            name: File name
            mega_id: ID linking to MongoDB (stored as 'm')
            mtime: Modification time
            **extra: Additional custom attributes
            
        Returns:
            FileAttributes instance
        """
        attrs = cls(name=name, mega_id=mega_id, mtime=mtime)
        for key, value in extra.items():
            attrs.set(key, value)
        return attrs


# Backward compatibility alias
CustomAttributes = FileAttributes
