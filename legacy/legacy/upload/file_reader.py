"""
File reader for MEGA uploads.

This module handles reading chunks from files for MEGA uploads.
"""
import aiofiles
from typing import Optional
from pathlib import Path
from mega_py.upload.types.upload_types import ChunkData, Position, LoggerProtocol

class FileReader:
    """
    Handles reading chunks from files for MEGA uploads.
    
    This class is responsible for:
    - Opening files for reading
    - Reading specific chunks from a file
    - Handling file I/O errors
    
    Attributes:
        logger: Logger instance
    """
    
    def __init__(self, logger: LoggerProtocol = None) -> None:
        """
        Initialize the file reader.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
    
    async def read_chunk(
        self, 
        file_path: Path, 
        start: Position, 
        end: Position
    ) -> Optional[ChunkData]:
        """
        Read a chunk from a file.
        
        Args:
            file_path: Path to the file
            start: Start position of the chunk in bytes
            end: End position of the chunk in bytes
            
        Returns:
            Chunk data or None if reading failed
            
        Example:
            >>> reader = FileReader()
            >>> chunk = await reader.read_chunk(Path("file.txt"), 0, 1024)
        """
        try:
            async with aiofiles.open(file_path, "rb") as file_handle:
                await file_handle.seek(start)
                chunk_data = await file_handle.read(end - start)
                
                if not chunk_data:
                    if self.logger:
                        self.logger.error(f"Failed to read chunk from position {start} to {end}")
                    return None
                
                """ if self.logger:
                    self.logger.debug(
                        f"Read chunk from position {start} to {end}, "
                        f"size: {len(chunk_data)} bytes"
                    ) """
                    
                return chunk_data
                
        except (IOError, OSError) as e:
            if self.logger:
                self.logger.error(f"I/O error reading file at {file_path}: {str(e)}")
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading file at {file_path}: {str(e)}")
            return None 