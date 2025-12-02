"""
File validation and reading services.

Single Responsibility: Each class handles one specific task.
"""
from pathlib import Path
from typing import Tuple, Optional, Union
import aiofiles


class FileValidator:
    """
    Validates files before upload.
    
    Responsibilities:
    - Check file existence
    - Verify file is not a directory
    - Get file size
    """
    
    def validate(self, file_path: Union[str, Path]) -> Tuple[Path, int]:
        """
        Validate a file for upload.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (validated Path, file size in bytes)
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is not a regular file
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        
        file_size = path.stat().st_size
        
        return path, file_size
    
    def validate_size(self, file_size: int, max_size: Optional[int] = None) -> None:
        """
        Validate file size.
        
        Args:
            file_size: File size in bytes
            max_size: Optional maximum allowed size
            
        Raises:
            ValueError: If file is empty or exceeds max size
        """
        if file_size == 0:
            raise ValueError("Cannot upload empty file")
        
        if max_size and file_size > max_size:
            raise ValueError(
                f"File size {file_size} exceeds maximum {max_size}"
            )


class AsyncFileReader:
    """
    Asynchronous file reader for chunk-based reading.
    
    Uses aiofiles for non-blocking I/O operations.
    """
    
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
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                await f.seek(start)
                data = await f.read(end - start)
                return data if data else None
        except (IOError, OSError):
            return None
    
    async def read_file(self, file_path: Path) -> Optional[bytes]:
        """
        Read entire file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File data or None if reading failed
        """
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
        except (IOError, OSError):
            return None
