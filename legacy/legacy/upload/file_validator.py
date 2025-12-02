"""
File validation and preparation for MEGA uploads.

This module handles file validation and preparation for uploading to MEGA.
"""
from pathlib import Path
from typing import Tuple, Union
from mega_py.upload.types.upload_types import FileSize, LoggerProtocol

class FileValidator:
    """
    Handles file validation and preparation for MEGA uploads.
    
    This class is responsible for:
    - Validating file existence and properties
    - Converting file paths to Path objects
    - Retrieving file size information
    
    Attributes:
        logger: Logger instance
    """
    
    def __init__(self, logger: LoggerProtocol = None) -> None:
        """
        Initialize the file validator.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
    
    def validate_and_prepare(self, source_path: Union[str, Path]) -> Tuple[Path, FileSize]:
        """
        Validate and prepare a file for upload.
        
        Args:
            source_path: Path to the file to upload (str or Path)
            
        Returns:
            Tuple of (path as Path, file size)
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the path is not a valid file
            
        Example:
            >>> validator = FileValidator()
            >>> path, size = validator.validate_and_prepare("example.txt")
        """
        # Convert to Path if string
        if isinstance(source_path, str):
            source_path = Path(source_path)
            
        # Verify that the file exists
        if not source_path.exists():
            if self.logger:
                self.logger.error(f"File not found: {source_path}")
            raise FileNotFoundError(f"File {source_path} doesn't exist")
        
        # Verify that it's a file (not a directory)
        if not source_path.is_file():
            if self.logger:
                self.logger.error(f"Path is not a file: {source_path}")
            raise ValueError(f"Path {source_path} is not a file")
            
        # Get file size
        file_size = source_path.stat().st_size
        
        if file_size == 0:
            if self.logger:
                self.logger.warning(f"File is empty: {source_path}")
            
        if self.logger:
            self.logger.debug(f"File validated: {source_path} ({file_size} bytes)")
            
        return source_path, file_size 