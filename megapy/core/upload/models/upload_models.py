"""
Data models for upload module.

Uses dataclasses for immutable, type-safe data structures.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from datetime import datetime


@dataclass
class CustomAttributes:
    """
    Custom attributes stored in 'e' (extra) object.
    
    Uses minimized keys to save space:
    - i: document_id
    - u: url
    - d: date (Unix timestamp)
    
    Example:
        >>> custom = CustomAttributes(document_id="DOC123", url="https://example.com")
        >>> custom.to_dict()
        {'i': 'DOC123', 'u': 'https://example.com'}
    """
    document_id: Optional[str] = None  # i
    url: Optional[str] = None  # u
    date: Optional[Union[int, datetime]] = None  # d
    _extra: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.date, datetime):
            self.date = int(self.date.timestamp())
    
    def set(self, key: str, value: Any) -> 'CustomAttributes':
        """Set a custom attribute (key should be 1-2 chars)."""
        self._extra[key] = value
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to minimized key dict."""
        result = {}
        if self.document_id is not None:
            result['i'] = self.document_id
        if self.url is not None:
            result['u'] = self.url
        if self.date is not None:
            result['d'] = self.date
        result.update(self._extra)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CustomAttributes':
        """Create from minimized key dict."""
        known = {'i', 'u', 'd'}
        return cls(
            document_id=data.get('i'),
            url=data.get('u'),
            date=data.get('d'),
            _extra={k: v for k, v in data.items() if k not in known}
        )


@dataclass
class FileAttributes:
    """
    File attributes for MEGA upload.
    
    Attributes:
        name: File name (n)
        mtime: Modification time as Unix timestamp (t)
        label: Label color 0-7 (lbl)
        is_favorite: Favorite flag (fav)
        custom: Custom attributes in 'e' object
    
    The modification time (mtime) is stored in the 't' attribute as a Unix
    timestamp (seconds since epoch). This preserves the original file's
    modification date when uploading to MEGA, matching the official web client.
    
    Example:
        >>> attrs = FileAttributes(
        ...     name="doc.pdf",
        ...     mtime=1701532800,
        ...     custom=CustomAttributes(document_id="123")
        ... )
        >>> attrs.to_dict()
        {'n': 'doc.pdf', 't': 1701532800, 'e': {'i': '123'}}
    """
    name: str
    mtime: Optional[Union[int, datetime]] = None  # t (modification time)
    label: int = 0
    is_favorite: bool = False
    custom: Optional[CustomAttributes] = None
    
    def __post_init__(self):
        # Convert datetime to Unix timestamp
        if isinstance(self.mtime, datetime):
            self.mtime = int(self.mtime.timestamp())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to MEGA attribute format."""
        result = {'n': self.name}
        if self.mtime is not None:
            result['t'] = self.mtime
        if self.label:
            result['lbl'] = self.label
        if self.is_favorite:
            result['fav'] = 1
        if self.custom:
            custom_dict = self.custom.to_dict()
            if custom_dict:
                result['e'] = custom_dict
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileAttributes':
        """Create from dictionary."""
        custom = None
        if 'e' in data and isinstance(data['e'], dict):
            custom = CustomAttributes.from_dict(data['e'])
        return cls(
            name=data.get('n', data.get('name', '')),
            mtime=data.get('t'),
            label=data.get('lbl', data.get('label', 0)),
            is_favorite=bool(data.get('fav', data.get('is_favorite', False))),
            custom=custom
        )
    
    def with_custom(self, **kwargs) -> 'FileAttributes':
        """Add custom attributes."""
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
                self.custom.set(key[0], value)
        return self


@dataclass(frozen=True)
class ChunkInfo:
    """
    Information about a file chunk.
    
    Attributes:
        index: Chunk index
        start: Start position in bytes
        end: End position in bytes
        size: Chunk size in bytes
    """
    index: int
    start: int
    end: int
    
    @property
    def size(self) -> int:
        """Returns chunk size."""
        return self.end - self.start


@dataclass
class UploadConfig:
    """
    Configuration for file upload.
    
    Attributes:
        file_path: Path to file to upload
        target_folder_id: Target folder node ID
        attributes: Optional file attributes
        encryption_key: Optional custom encryption key
        max_concurrent_uploads: Maximum concurrent chunk uploads
        timeout: Request timeout in seconds
        thumbnail: Optional thumbnail image bytes (240x240 JPEG 80%)
        preview: Optional preview image bytes (max 1024px JPEG 85%)
        auto_thumbnail: Auto-generate thumbnail for media files
        auto_preview: Auto-generate preview for media files
        custom_attributes: Custom attributes for 'e' object
        media_info: Optional media metadata for video/audio files
        replace_handle: Optional handle of existing file to replace (creates new version)
    """
    file_path: Path
    target_folder_id: str
    attributes: Optional[FileAttributes] = None
    encryption_key: Optional[bytes] = None
    max_concurrent_uploads: int = 4
    timeout: int = 120
    thumbnail: Optional[bytes] = None
    preview: Optional[bytes] = None
    auto_thumbnail: bool = True
    auto_preview: bool = True
    custom_attributes: Optional[CustomAttributes] = None
    media_info: Optional[Any] = None  # MediaInfo from core.attributes
    replace_handle: Optional[str] = None  # Handle of file to replace (for versioning)
    
    def __post_init__(self):
        """Validate and normalize config."""
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)
        
        if self.attributes is None:
            self.attributes = FileAttributes(name=self.file_path.name)
        
        # Merge custom_attributes into attributes
        if self.custom_attributes and self.attributes:
            self.attributes.custom = self.custom_attributes


@dataclass(frozen=True)
class UploadResult:
    """
    Result of a successful upload.
    
    Attributes:
        node_handle: Handle of created node
        file_key: Encryption key for the file
        file_size: Size of uploaded file
        attributes: File attributes
        response: Raw API response
    """
    node_handle: str
    file_key: bytes
    file_size: int
    attributes: FileAttributes
    response: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def public_link(self) -> str:
        """Generate public link for the file."""
        import base64
        key_b64 = base64.b64encode(self.file_key).decode().rstrip('=')
        return f"https://mega.nz/file/{self.node_handle}#{key_b64}"


@dataclass
class UploadProgress:
    """
    Upload progress information.
    
    Attributes:
        total_chunks: Total number of chunks
        uploaded_chunks: Number of uploaded chunks
        total_bytes: Total file size
        uploaded_bytes: Bytes uploaded so far
    """
    total_chunks: int
    uploaded_chunks: int = 0
    total_bytes: int = 0
    uploaded_bytes: int = 0
    
    @property
    def percentage(self) -> float:
        """Returns upload progress as percentage."""
        if self.total_chunks == 0:
            return 0.0
        return (self.uploaded_chunks / self.total_chunks) * 100
    
    @property
    def is_complete(self) -> bool:
        """Returns True if upload is complete."""
        return self.uploaded_chunks >= self.total_chunks
