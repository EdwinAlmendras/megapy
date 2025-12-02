"""
Upload coordinator.

Orchestrates the upload process using injected dependencies.
Follows Dependency Inversion Principle - depends on abstractions, not concretions.
"""
import logging
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable
from Crypto.Cipher import AES

from .protocols import (
    ChunkingStrategy,
    EncryptionStrategy,
    FileReaderProtocol,
    ChunkUploaderProtocol,
    NodeCreatorProtocol,
    ApiClientProtocol,
    LoggerProtocol
)
from .models import UploadConfig, UploadResult, UploadProgress, FileAttributes
from .strategies import MegaChunkingStrategy, MegaEncryptionStrategy
from .services import FileValidator, AsyncFileReader, ChunkUploader, NodeCreator
from ..crypto import Base64Encoder


class UploadCoordinator:
    """
    Coordinates the file upload process.
    
    Uses dependency injection for all components, making it:
    - Testable (mock dependencies)
    - Extensible (swap strategies)
    - Maintainable (single responsibility)
    
    Supports both sync and async API clients.
    """
    
    def __init__(
        self,
        api_client: ApiClientProtocol,
        master_key: bytes,
        chunking_strategy: Optional[ChunkingStrategy] = None,
        encryption_strategy: Optional[EncryptionStrategy] = None,
        file_reader: Optional[FileReaderProtocol] = None,
        logger: Optional[LoggerProtocol] = None,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None
    ):
        """
        Initialize upload coordinator.
        
        Args:
            api_client: MEGA API client (sync or async)
            master_key: Master encryption key
            chunking_strategy: Strategy for chunking files
            encryption_strategy: Strategy for encryption
            file_reader: File reader implementation
            logger: Logger instance
            progress_callback: Optional callback for progress updates
        """
        self._api = api_client
        self._master_key = master_key
        self._chunking = chunking_strategy or MegaChunkingStrategy()
        self._file_reader = file_reader or AsyncFileReader()
        self._validator = FileValidator()
        self._logger = logger or logging.getLogger('megapy.upload')
        self._progress_callback = progress_callback
        
        # Encryption strategy can be set per-upload
        self._default_encryption = encryption_strategy
    
    async def upload(self, config: UploadConfig) -> UploadResult:
        """
        Execute the complete upload process.
        
        Args:
            config: Upload configuration
            
        Returns:
            Upload result with node info
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If upload fails
        """
        self._logger.info(f"Starting upload: {config.file_path}")
        
        # Step 1: Validate file
        path, file_size = self._validator.validate(config.file_path)
        self._logger.debug(f"File validated: {file_size} bytes")
        
        # Step 2: Get upload URL
        upload_url = await self._get_upload_url(file_size)
        self._logger.debug(f"Upload URL obtained")
        
        # Step 3: Initialize components
        encryption = self._create_encryption(config.encryption_key)
        chunk_uploader = ChunkUploader(upload_url, config.timeout)
        node_creator = NodeCreator(self._api, self._master_key)
        
        # Step 4: Calculate chunks
        chunks = self._chunking.calculate_chunks(file_size)
        self._logger.info(f"File split into {len(chunks)} chunks")
        
        # Step 5: Upload chunks
        await self._upload_chunks(
            path, chunks, encryption, chunk_uploader, file_size
        )
        
        # Step 6: Get original key (24 bytes) for thumbnail encryption
        # and finalize to get the 32-byte file key for node creation
        original_key = encryption.key  # 24 bytes - used for thumbnails
        file_key = encryption.finalize()  # 32 bytes - used for node creation
        upload_token = chunk_uploader.get_upload_token()
        
        if not upload_token:
            raise ValueError("No upload token received")
        
        # Step 7: Upload thumbnail and preview (if provided)
        # Use first 16 bytes of ORIGINAL key (not file_key) for encryption
        file_attributes = []
        if config.thumbnail:
            try:
                thumb_hash = await self._upload_file_attribute(config.thumbnail, original_key[:16], 0)
                if thumb_hash:
                    file_attributes.append(f"0*{thumb_hash}")
                    self._logger.debug("Thumbnail uploaded")
            except Exception as e:
                self._logger.warning(f"Failed to upload thumbnail: {e}")
        
        if config.preview:
            try:
                preview_hash = await self._upload_file_attribute(config.preview, original_key[:16], 1)
                if preview_hash:
                    file_attributes.append(f"1*{preview_hash}")
                    self._logger.debug("Preview uploaded")
            except Exception as e:
                self._logger.warning(f"Failed to upload preview: {e}")
        
        # Step 8: Create node
        attributes = config.attributes.to_dict() if config.attributes else {'n': path.name}
        fa_string = '/'.join(file_attributes) if file_attributes else None
        
        response = await node_creator.create_node(
            upload_token,
            config.target_folder_id,
            file_key,
            attributes,
            file_attributes=fa_string
        )
        
        # Extract node handle from response
        node_handle = self._extract_node_handle(response)
        
        # Step 9: Upload media attributes if provided (for video/audio files)
        if config.media_info:
            try:
                await self._upload_media_attributes(node_handle, config.media_info, file_key)
                self._logger.debug("Media attributes uploaded")
            except Exception as e:
                self._logger.warning(f"Failed to upload media attributes: {e}")
        
        self._logger.info(f"Upload complete: {node_handle}")
        
        return UploadResult(
            node_handle=node_handle,
            file_key=file_key,
            file_size=file_size,
            attributes=config.attributes or FileAttributes(name=path.name),
            response=response
        )
    
    async def _upload_file_attribute(
        self,
        data: bytes,
        aes_key: bytes,
        attr_type: int
    ) -> Optional[str]:
        """
        Upload a file attribute (thumbnail or preview).
        
        Args:
            data: Image data bytes
            aes_key: 16-byte AES key (first 16 bytes of original 24-byte key)
            attr_type: 0=thumbnail, 1=preview
            
        Returns:
            Attribute hash or None
        """
        # Pad to 16-byte boundary
        padded_len = (len(data) + 15) // 16 * 16
        padded_data = data + b'\x00' * (padded_len - len(data))
        
        # Encrypt with AES-CBC using zero IV
        cipher = AES.new(aes_key, AES.MODE_CBC, iv=b'\x00' * 16)
        encrypted = cipher.encrypt(padded_data)
        
        # Get upload URL for file attribute
        result = await self._api.request({'a': 'ufa', 's': len(encrypted)})
        if 'p' not in result:
            return None
        
        upload_url = result['p']
        
        # Upload the encrypted data
        # POST to /{attr_type}: 0 for thumbnail, 1 for preview
        encoder = Base64Encoder()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{upload_url}/{attr_type}",
                data=encrypted,
                headers={'Content-Type': 'application/octet-stream'}
            ) as resp:
                response_bytes = await resp.read()
                if resp.status == 200 and response_bytes:
                    # Response is the handle - encode as base64
                    return encoder.encode(response_bytes)
        
        return None
    
    async def _get_upload_url(self, file_size: int) -> str:
        """Get upload URL from API."""
        # Support both sync and async clients
        if hasattr(self._api.request, '__call__'):
            import inspect
            if inspect.iscoroutinefunction(self._api.request):
                result = await self._api.request({'a': 'u', 's': file_size})
            else:
                result = self._api.request({'a': 'u', 's': file_size})
        else:
            result = self._api.request({'a': 'u', 's': file_size})
        
        if 'p' not in result:
            raise ValueError("Could not obtain upload URL")
        
        return result['p']
    
    def _create_encryption(
        self, 
        key: Optional[bytes] = None
    ) -> EncryptionStrategy:
        """Create encryption strategy."""
        if self._default_encryption:
            return self._default_encryption
        return MegaEncryptionStrategy(key)
    
    async def _upload_chunks(
        self,
        file_path: Path,
        chunks: List[Tuple[int, int]],
        encryption: EncryptionStrategy,
        uploader: ChunkUploader,
        total_bytes: int
    ) -> None:
        """
        Upload all chunks sequentially.
        
        CTR mode requires sequential processing for correct encryption.
        """
        total = len(chunks)
        uploaded_bytes = 0
        
        progress = UploadProgress(
            total_chunks=total,
            total_bytes=total_bytes
        )
        
        for i, (start, end) in enumerate(chunks):
            # Read chunk
            data = await self._file_reader.read_chunk(file_path, start, end)
            if not data:
                raise ValueError(f"Failed to read chunk {i}")
            
            # Encrypt chunk (must be sequential for CTR)
            encrypted = encryption.encrypt_chunk(i, data)
            
            # Upload chunk
            await uploader.upload_chunk(i, start, encrypted)
            
            # Update progress
            uploaded_bytes += len(data)
            progress.uploaded_chunks = i + 1
            progress.uploaded_bytes = uploaded_bytes
            
            # Callback if provided
            if self._progress_callback:
                self._progress_callback(progress)
            
            # Log progress
            if (i + 1) % 10 == 0 or (i + 1) == total:
                pct = progress.percentage
                self._logger.info(f"Progress: {i + 1}/{total} ({pct:.1f}%)")
    
    def _extract_node_handle(self, response: Dict[str, Any]) -> str:
        """Extract node handle from API response."""
        if 'f' in response and len(response['f']) > 0:
            return response['f'][0].get('h', '')
        return ''
    
    async def _upload_media_attributes(
        self,
        node_handle: str,
        media_info: Any,
        file_key: bytes
    ) -> None:
        """
        Upload media attributes (type 8 and optionally 9) for video/audio files.
        
        Uses the 'pfa' (put file attribute) API command.
        
        Args:
            node_handle: The node handle to attach attributes to
            media_info: MediaInfo object with video/audio metadata
            file_key: 32-byte file encryption key
        """
        from ..attributes import MediaAttributeService
        
        service = MediaAttributeService()
        fa_string = service.encode(media_info, file_key)
        
        if not fa_string:
            return
        
        # Use pfa command to add media attributes
        result = await self._api.request({
            'a': 'pfa',
            'n': node_handle,
            'fa': fa_string
        })
        
        self._logger.debug(f"Media attributes stored: {fa_string}")
