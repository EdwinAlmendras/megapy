"""
Upload coordinator.

Orchestrates the upload process using injected dependencies.
Follows Dependency Inversion Principle - depends on abstractions, not concretions.
"""
import logging
import asyncio
import aiohttp
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable
from Crypto.Cipher import AES

from .protocols import (
    ChunkingStrategy,
    EncryptionStrategy,
    FileReaderProtocol,
    LoggerProtocol
)
from .models import UploadConfig, UploadResult, UploadProgress, FileAttributes
from .strategies import MegaChunkingStrategy, MegaEncryptionStrategy
from .services import FileValidator, AsyncFileReader, ChunkUploader, NodeCreator
from ..crypto import Base64Encoder
import logging

logger = logging.getLogger('megapy.upload.coordinator')


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
        api_client,
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
        path, file_size = self._validator.validate(config.file_path)
        file_size_mb = file_size / (1024 * 1024)
        logger.info(f"Starting upload: {path.name} ({file_size_mb:.2f} MB)")
        
        # Step 1: Validate file
        logger.debug(f"File validated: {file_size} bytes")
        
        # Step 1.5: Set modification time from file if not provided
        # This preserves the original file's mtime, matching MEGA web client behavior
        if config.attributes and config.attributes.mtime is None:
            try:
                file_mtime = int(path.stat().st_mtime)
                config.attributes.mtime = file_mtime
                logger.debug(f"File mtime set: {file_mtime}")
            except (OSError, AttributeError) as e:
                logger.debug(f"Could not get file mtime: {e}")
        
        logger.info("Requesting upload URL from MEGA API")
        upload_url = await self._get_upload_url(file_size)
        
        encryption = self._create_encryption(config.encryption_key)
        chunk_uploader = ChunkUploader(upload_url, config.timeout)
        node_creator = NodeCreator(self._api, self._master_key)
        
        # Step 4: Calculate chunks
        chunks = self._chunking.calculate_chunks(file_size)
        avg_chunk_size = file_size / len(chunks) if chunks else 0
        avg_chunk_size_kb = avg_chunk_size / 1024
        logger.info(f"File split into {len(chunks)} chunks (avg {avg_chunk_size_kb:.1f} KB per chunk)")
        
        # Step 5: Upload chunks
        logger.info("Beginning chunk upload process")
        try:
            await self._upload_chunks(
                path, chunks, encryption, chunk_uploader, file_size
            )
        finally:
            await chunk_uploader.close()
            logger.debug("Upload session closed")
        
        # Step 6: Get original key (24 bytes) for thumbnail encryption
        # and finalize to get the 32-byte file key for node creation
        original_key = encryption.key  # 24 bytes - used for thumbnails
        file_key = encryption.finalize()  # 32 bytes - used for node creation
        upload_token = chunk_uploader.get_upload_token()
        
        if not upload_token:
            raise ValueError("No upload token received")
        
        # Step 7: Upload thumbnail and preview (if provided) in parallel
        # Use first 16 bytes of ORIGINAL key (not file_key) for encryption
        file_attributes = []
        
        # Upload thumbnail and preview sequentially (not in parallel)
        attrs_start = time.time()
        
        
        
        # Upload thumbnail first
        if config.thumbnail:
            thumb_size_kb = len(config.thumbnail) / 1024
            logger.info(f"Uploading thumbnail ({thumb_size_kb:.1f} KB)")
            try:
                thumb_hash = await self._upload_file_attribute(config.thumbnail, original_key[:16], 0)
                if thumb_hash:
                    file_attributes.append(f"0*{thumb_hash}")
                    logger.info("Thumbnail uploaded successfully")
                else:
                    logger.warning("Failed to upload thumbnail: no hash returned")
            except Exception as e:
                logger.warning(f"Failed to upload thumbnail: {e}")
        
        # Upload preview second (after thumbnail completes)
        # Skip preview if largest side is less than 1024px
        if config.preview:
            preview_size_kb = len(config.preview) / 1024
            
            # Check preview dimensions
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(config.preview))
                width, height = img.size
                max_dimension = max(width, height)
                
                if max_dimension < 1024:
                    logger.info(f"Skipping preview upload: largest side is {max_dimension}px (less than 1024px)")
                else:
                    logger.info(f"Uploading preview ({preview_size_kb:.1f} KB, {width}x{height}px)")
                    try:
                        preview_hash = await self._upload_file_attribute(config.preview, original_key[:16], 1)
                        if preview_hash:
                            file_attributes.append(f"1*{preview_hash}")
                            logger.info("Preview uploaded successfully")
                        else:
                            logger.warning("Failed to upload preview: no hash returned")
                    except Exception as e:
                        logger.warning(f"Failed to upload preview: {e}")
            except Exception as e:
                # If we can't read dimensions, upload anyway (fallback)
                logger.warning(f"Could not read preview dimensions, uploading anyway: {e}")
                try:
                    preview_hash = await self._upload_file_attribute(config.preview, original_key[:16], 1)
                    if preview_hash:
                        file_attributes.append(f"1*{preview_hash}")
                        logger.info("Preview uploaded successfully")
                    else:
                        logger.warning("Failed to upload preview: no hash returned")
                except Exception as upload_error:
                    logger.warning(f"Failed to upload preview: {upload_error}")
        
        if config.thumbnail or config.preview:
            attrs_time = time.time() - attrs_start
            logger.info(f"File attributes upload completed in {attrs_time:.2f}s")
        
        # Step 8: Create node
        logger.info("Creating file node in MEGA")
        node_start = time.time()
        attributes = config.attributes.to_dict() if config.attributes else {'n': path.name}
        fa_string = '/'.join(file_attributes) if file_attributes else None
        
        response = await node_creator.create_node(
            upload_token,
            config.target_folder_id,
            file_key,
            attributes,
            file_attributes=fa_string,
            replace_handle=config.replace_handle
        )
        
        # Extract node handle from response
        node_handle = self._extract_node_handle(response)
        node_time = time.time() - node_start
        logger.info(f"File node created in {node_time:.2f}s: {node_handle}")
        
        # Step 9: Upload media attributes if provided (for video/audio files)
        if config.media_info:
            try:
                logger.info("Uploading media attributes")
                await self._upload_media_attributes(node_handle, config.media_info, file_key)
                logger.info("Media attributes uploaded successfully")
            except Exception as e:
                logger.warning(f"Failed to upload media attributes: {e}")
        
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
        attr_name = "thumbnail" if attr_type == 0 else "preview"
        data_size_kb = len(data) / 1024
        logger.debug(f"Preparing {attr_name} upload ({data_size_kb:.1f} KB)")
        
        # Pad to 16-byte boundary
        padded_len = (len(data) + 15) // 16 * 16
        padded_data = data + b'\x00' * (padded_len - len(data))
        
        # Encrypt with AES-CBC using zero IV
        cipher = AES.new(aes_key, AES.MODE_CBC, iv=b'\x00' * 16)
        encrypted = cipher.encrypt(padded_data)
        
        result = await self._api.request({'a': 'ufa', 's': len(encrypted)})
        
        upload_url = result['p']
        
        encoder = Base64Encoder()
        connector = aiohttp.TCPConnector(limit=10, keepalive_timeout=30, force_close=False)
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        
        upload_start = time.time()
        
        
        logger.debug(f"Uploading {attr_name} to {upload_url}/{attr_type}")
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.post(
                f"{upload_url}/{attr_type}",
                data=encrypted,
                headers={'Content-Type': 'application/octet-stream'},
                ssl=False
            ) as resp:
                if resp.status != 200:
                    upload_time = time.time() - upload_start
                    logger.error(f"Failed to upload {attr_name}: HTTP {resp.status} after {upload_time:.2f}s")
                    return None
                response_bytes = await resp.read()
                upload_time = time.time() - upload_start
                if response_bytes:
                    hash_result = encoder.encode(response_bytes)
                    logger.debug(f"{attr_name} uploaded successfully in {upload_time:.2f}s")
                    return hash_result
                else:
                    logger.error(f"No response data received for {attr_name} after {upload_time:.2f}s")
                    return None
        logger.debug(f"Uploaded {attr_name} to {upload_url}/{attr_type}")

    
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
        Upload chunks with sequential encryption and parallel uploads.
        
        CTR mode requires sequential encryption, but uploads can be parallel.
        Uses up to 21 concurrent uploads for maximum throughput.
        
        Optimized for memory: Opens file once, reads chunks on-demand, and
        explicitly releases data references after encryption to minimize RAM usage.
        """
        total = len(chunks)
        uploaded_bytes = 0
        
        progress = UploadProgress(
            total_chunks=total,
            total_bytes=total_bytes
        )
        
        # Max parallel uploads (same as mega_api)
        max_parallel_uploads = 21
        active_uploads: set = set()
        chunks_completed = 0
        
        total_mb = total_bytes / (1024 * 1024)
        logger.info(f"Processing {total} chunks ({total_mb:.2f} MB total, max {max_parallel_uploads} parallel uploads)")
        
        # Open file once for efficient reading (avoids repeated open/close)
        # Check if file_reader supports open_file/close_file (optional optimization)
        has_file_management = hasattr(self._file_reader, 'open_file') and hasattr(self._file_reader, 'close_file')
        try:
            if has_file_management:
                await self._file_reader.open_file(file_path)
            
            for i, (start, end) in enumerate(chunks):
                chunk_start_time = time.time()
                # 1. Read chunk (reuses open file handle)
                data = await self._file_reader.read_chunk(file_path, start, end)
                if not data:
                    raise ValueError(f"Failed to read chunk {i}")
                
                # 2. Encrypt chunk
                encrypted = encryption.encrypt_chunk(i, data)
                
                # 3. Explicitly release reference to unencrypted data to free memory
                # The encrypted data will be released after upload completes
                del data
                
                # 4. Create upload task with cleanup callback
                # The callback will release the encrypted data from memory after upload
                # Capture encrypted data in closure for cleanup
                enc_data_ref = [encrypted]  # Use list to allow modification in callback
                upload_task = asyncio.create_task(
                    self._upload_chunk_task(uploader, i, start, encrypted, chunk_start_time)
                )
                
                def cleanup_callback(finished_task):
                    # Release encrypted chunk data from memory after upload completes
                    # This helps free RAM, especially important for large files
                    if enc_data_ref:
                        del enc_data_ref[0]
                        enc_data_ref.clear()
                    active_uploads.discard(finished_task)
                
                upload_task.add_done_callback(cleanup_callback)
                active_uploads.add(upload_task)
                
                # Update progress tracking (track original file bytes, not encrypted)
                chunk_original_size = end - start
                uploaded_bytes += chunk_original_size
                
                # Wait if we've reached max parallel uploads
                if len(active_uploads) >= max_parallel_uploads:
                    done, _ = await asyncio.wait(
                        active_uploads,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        try:
                            await task
                            chunks_completed += 1
                        except Exception as e:
                            logger.error(f"Chunk upload failed: chunk {i}, error: {e}")
                            raise
                
                # Update progress
                progress.uploaded_chunks = i + 1
                progress.uploaded_bytes = uploaded_bytes
                
                # Callback if provided
                if self._progress_callback:
                    self._progress_callback(progress)
            
            # Wait for remaining uploads to complete
            if active_uploads:
                remaining = len(active_uploads)
                logger.info(f"Waiting for {remaining} remaining chunk uploads to complete")
                results = await asyncio.gather(*active_uploads, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Chunk upload failed: {result}")
                        raise result
        finally:
            # Always close the file handle if it was opened
            if has_file_management:
                await self._file_reader.close_file()
        
        uploaded_mb = total_bytes / (1024 * 1024)
        logger.info(f"All chunks uploaded successfully: {total} chunks, {uploaded_mb:.2f} MB")
    
    async def _upload_chunk_task(
        self,
        uploader: ChunkUploader,
        index: int,
        start: int,
        encrypted_chunk: bytes,
        start_time: float
    ) -> None:
        """
        Upload a single chunk (used as async task).
        
        Args:
            uploader: Chunk uploader instance
            index: Chunk index
            start: Start position in file
            encrypted_chunk: Encrypted chunk data
            start_time: Start time for timing
        """
        try:
            await uploader.upload_chunk(index, start, encrypted_chunk)
            elapsed = time.time() - start_time
            chunk_size_kb = len(encrypted_chunk) / 1024
            speed_kbps = (chunk_size_kb / elapsed) if elapsed > 0 else 0
            logger.debug(f"Chunk {index} completed in {elapsed:.2f}s ({speed_kbps:.1f} KB/s)")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Chunk {index} failed after {elapsed:.2f}s: {e}")
            raise
    
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
        

        await self._api.request({
                'a': 'pfa',
                'n': node_handle,
                'fa': fa_string
            })
        
        logger.debug(f"Media attributes stored: {fa_string}")
