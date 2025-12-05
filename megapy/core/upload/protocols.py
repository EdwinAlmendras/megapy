"""
Protocol definitions for upload module.

Defines interfaces (protocols) for dependency injection and strategy pattern.
Following Interface Segregation Principle (ISP) and Dependency Inversion Principle (DIP).
"""
from typing import Protocol, Dict, Any, List, Tuple, Optional
from pathlib import Path


class ChunkingStrategy(Protocol):
    """
    Protocol for file chunking strategies.
    
    Allows different chunking algorithms to be plugged in.
    """
    
    def calculate_chunks(self, file_size: int) -> List[Tuple[int, int]]:
        """
        Calculate chunk boundaries for a file.
        
        Args:
            file_size: Total file size in bytes
            
        Returns:
            List of (start, end) tuples representing chunk boundaries
        """
        ...


class EncryptionStrategy(Protocol):
    """
    Protocol for file encryption strategies.
    
    Allows different encryption algorithms to be plugged in.
    """
    
    def encrypt_chunk(self, chunk_index: int, data: bytes) -> bytes:
        """
        Encrypt a chunk of data.
        
        Args:
            chunk_index: Index of the chunk (for CTR mode counter)
            data: Raw data to encrypt
            
        Returns:
            Encrypted data
        """
        ...
    
    def finalize(self) -> bytes:
        """
        Finalize encryption and return the file key.
        
        Returns:
            Final encryption key in MEGA format
        """
        ...
    
    @property
    def key(self) -> bytes:
        """Returns the encryption key."""
        ...


class FileReaderProtocol(Protocol):
    """Protocol for file reading operations."""
    
    async def read_chunk(
        self, 
        file_path: Path, 
        start: int, 
        end: int
    ) -> Optional[bytes]:
        """
        Read a chunk from a file.
        
        Args:
            file_path: Path to the file
            start: Start position in bytes
            end: End position in bytes
            
        Returns:
            Chunk data or None if reading failed
        """
        ...


class FileValidatorProtocol(Protocol):
    """Protocol for file validation operations."""
    
    def validate(self, file_path: Path) -> Tuple[Path, int]:
        """
        Validate a file for upload.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (validated path, file size)
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is not a valid file
        """
        ...


class ChunkUploaderProtocol(Protocol):
    """Protocol for chunk upload operations."""
    
    async def upload_chunk(
        self,
        chunk_index: int,
        start_position: int,
        encrypted_chunk: bytes
    ) -> str:
        """
        Upload a single chunk.
        
        Args:
            chunk_index: Index of the chunk
            start_position: Start position in file
            encrypted_chunk: Encrypted chunk data
            
        Returns:
            Upload token from server
        """
        ...
    
    def get_upload_token(self) -> Optional[str]:
        """Returns the latest upload token."""
        ...


class NodeCreatorProtocol(Protocol):
    """Protocol for MEGA node creation."""
    
    async def create_node(
        self,
        upload_token: str,
        target_id: str,
        file_key: bytes,
        attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a node in MEGA after upload.
        
        Args:
            upload_token: Temporary upload handle
            target_id: Parent folder node ID
            file_key: File encryption key
            attributes: File attributes
            
        Returns:
            API response with created node data
        """
        ...



class LoggerProtocol(Protocol):
    """Protocol for logger objects."""
    
    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
