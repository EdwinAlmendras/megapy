"""
Upload facade.

Provides a simplified interface for file uploads.
Follows Facade Pattern - hides complexity of the upload subsystem.
"""
from pathlib import Path
from typing import Optional, Union, Dict, Any
import logging

from .coordinator import UploadCoordinator
from .models import UploadConfig, UploadResult, FileAttributes
from .protocols import ApiClientProtocol, ChunkingStrategy, EncryptionStrategy


class UploadFacade:
    """
    Simplified interface for MEGA file uploads.
    
    This is the main entry point for uploading files.
    Hides the complexity of chunking, encryption, and API calls.
    
    Example:
        >>> from megapy.core.upload import UploadFacade
        >>> uploader = UploadFacade(api_client, master_key)
        >>> result = await uploader.upload("file.txt", "target_folder_id")
        >>> print(f"Uploaded: {result.node_handle}")
    """
    
    def __init__(
        self,
        api_client: ApiClientProtocol,
        master_key: bytes,
        chunking_strategy: Optional[ChunkingStrategy] = None,
        encryption_strategy: Optional[EncryptionStrategy] = None,
        log_level: int = logging.INFO
    ):
        """
        Initialize upload facade.
        
        Args:
            api_client: MEGA API client
            master_key: Master encryption key
            chunking_strategy: Optional custom chunking strategy
            encryption_strategy: Optional custom encryption strategy
            log_level: Logging level
        """
        self._logger = logging.getLogger('megapy.upload')
        self._logger.setLevel(log_level)
        
        self._coordinator = UploadCoordinator(
            api_client=api_client,
            master_key=master_key,
            chunking_strategy=chunking_strategy,
            encryption_strategy=encryption_strategy,
            logger=self._logger
        )
    
    async def upload(
        self,
        file_path: Union[str, Path],
        target_folder_id: str,
        name: Optional[str] = None,
        attributes: Optional[Union[FileAttributes, Dict[str, Any]]] = None,
        encryption_key: Optional[bytes] = None,
        timeout: int = 120
    ) -> UploadResult:
        """
        Upload a file to MEGA.
        
        Args:
            file_path: Path to file to upload
            target_folder_id: Target folder node ID
            name: Optional custom file name
            attributes: Optional file attributes
            encryption_key: Optional custom encryption key
            timeout: Request timeout in seconds
            
        Returns:
            UploadResult with node info and file key
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If upload fails
            
        Example:
            >>> result = await uploader.upload(
            ...     "document.pdf",
            ...     "folder_handle",
            ...     name="renamed.pdf"
            ... )
            >>> print(result.public_link)
        """
        # Normalize path
        path = Path(file_path) if isinstance(file_path, str) else file_path
        
        # Create attributes
        if attributes is None:
            file_attrs = FileAttributes(name=name or path.name)
        elif isinstance(attributes, dict):
            file_attrs = FileAttributes.from_dict(attributes)
            if name:
                file_attrs = FileAttributes(
                    name=name,
                    label=file_attrs.label,
                    is_favorite=file_attrs.is_favorite
                )
        else:
            file_attrs = attributes
            if name:
                file_attrs = FileAttributes(
                    name=name,
                    label=file_attrs.label,
                    is_favorite=file_attrs.is_favorite
                )
        
        # Create config
        config = UploadConfig(
            file_path=path,
            target_folder_id=target_folder_id,
            attributes=file_attrs,
            encryption_key=encryption_key,
            timeout=timeout
        )
        
        return await self._coordinator.upload(config)
    
    async def upload_with_config(self, config: UploadConfig) -> UploadResult:
        """
        Upload a file using explicit configuration.
        
        Args:
            config: Upload configuration
            
        Returns:
            UploadResult with node info and file key
        """
        return await self._coordinator.upload(config)
