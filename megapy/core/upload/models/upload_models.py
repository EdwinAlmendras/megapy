"""
Data models for upload module.

Uses dataclasses for immutable, type-safe data structures.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union
from pathlib import Path

# Re-export FileAttributes from attributes module (single source of truth)
from ...attributes.models import FileAttributes, CustomAttributes


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
        attributes: Optional file attributes (flat, with mega_id)
        encryption_key: Optional custom encryption key
        max_concurrent_uploads: Maximum concurrent chunk uploads
        timeout: Request timeout in seconds
        thumbnail: Optional thumbnail image bytes (240x240 JPEG 80%)
        preview: Optional preview image bytes (max 1024px JPEG 85%)
        auto_thumbnail: Auto-generate thumbnail for media files
        auto_preview: Auto-generate preview for media files
        mega_id: ID linking to MongoDB (stored as 'm' attribute)
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
    mega_id: Optional[str] = None
    media_info: Optional[Any] = None
    replace_handle: Optional[str] = None
    
    def __post_init__(self):
        """Validate and normalize config."""
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)
        
        if self.attributes is None:
            self.attributes = FileAttributes(
                name=self.file_path.name,
                mega_id=self.mega_id
            )
        elif self.mega_id and not self.attributes.mega_id:
            self.attributes.mega_id = self.mega_id


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
