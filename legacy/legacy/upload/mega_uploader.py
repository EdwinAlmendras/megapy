"""
MEGA Uploader main entry point.

This module provides a simple interface for uploading files to MEGA.
"""
from pathlib import Path
from typing import Dict, Any, Optional, Union
import logging
from mega_py.upload.types.upload_types import FileAttributes, ApiProtocol, LoggerProtocol
from mega_py.upload.upload_coordinator import UploadCoordinator
from utils.logger import setup_logger

class MegaUploader:
    """
    Main entry point for uploading files to MEGA.
    
    This class provides a simple interface for:
    - Uploading files to MEGA
    - Setting file attributes
    - Getting upload results
    
    Attributes:
        api: MEGA API client
        master_key: Master encryption key
        logger: Logger instance
    """
    
    def __init__(
        self,
        api: ApiProtocol, 
        master_key: bytes,
        logger: Optional[LoggerProtocol] = None,
        log_level: int = logging.DEBUG
    ) -> None:
        """
        Initialize the MEGA uploader.
        
        Args:
            api: MEGA API client
            master_key: Master encryption key
            logger: Logger instance (optional)
            log_level: Logging level (default: INFO)
            
        Example:
            >>> from mega_py.api import MegaApi
            >>> api = MegaApi("your_email", "your_password")
            >>> uploader = MegaUploader(api, master_key)
        """
        self.api = api
        self.master_key = master_key
        self.logger = logger or setup_logger("MegaUploader", log_level)
    
    async def upload(
        self,
        file_path: Union[str, Path],
        target_folder_id: str,
        attributes: Optional[FileAttributes] = None,
        encryption_key: Optional[bytes] = None,
        max_concurrent_uploads: int = 4
    ) -> Dict[str, Any]:
        """
        Upload a file to MEGA.
        
        Args:
            file_path: Path to the file to upload
            target_folder_id: Target folder node ID
            attributes: File attributes (optional)
            encryption_key: Custom encryption key (optional)
            max_concurrent_uploads: Maximum number of concurrent uploads
            
        Returns:
            Response data from MEGA API
            
        Raises:
            ValueError: If the upload fails
            
        Example:
            >>> result = await uploader.upload("file.txt", "folder_id")
            >>> print(f"Upload succeeded: {result}")
        """
        # Convert string path to Path if needed
        if isinstance(file_path, str):
            file_path = Path(file_path)
            
        self.logger.info(f"Starting upload of {file_path} to folder {target_folder_id}")
        
        # Create upload coordinator
        coordinator = UploadCoordinator(
            file_path=file_path,
            target_id=target_folder_id,
            api=self.api,
            master_key=self.master_key,
            attributes=attributes,
            max_concurrent_uploads=max_concurrent_uploads,
            logger=self.logger,
            encryption_key=encryption_key
        )
        
        # Execute upload
        result = await coordinator.upload()
        
        self.logger.info(f"Upload of {file_path} completed successfully")
        return result 