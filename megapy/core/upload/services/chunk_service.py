"""
Chunk upload service.

Handles uploading individual chunks to MEGA servers.
"""
from typing import Optional
import logging
import time
import asyncio
import aiohttp


class ChunkUploader:
    """
    Handles uploading encrypted chunks to MEGA.
    
    Reuses HTTP session for all chunks (critical for performance).
    
    Responsibilities:
    - Send chunks to upload URL
    - Handle HTTP responses
    - Track upload token
    """
    
    DEFAULT_TIMEOUT = 120
    
    def __init__(
        self, 
        upload_url: str, 
        timeout: int = DEFAULT_TIMEOUT,
        session: Optional[aiohttp.ClientSession] = None
    ):
        """
        Initialize chunk uploader.
        
        Args:
            upload_url: Base URL for chunk uploads
            timeout: Request timeout in seconds
            session: Optional shared session (RECOMMENDED for performance)
        """
        self._upload_url = upload_url
        self._timeout = timeout
        self._upload_token: Optional[str] = None
        self._session = session
        self._owns_session = False
        self._logger = logging.getLogger('megapy.upload.chunk')
    
    @property
    def upload_url(self) -> str:
        """Returns the upload URL."""
        return self._upload_url
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=10, keepalive_timeout=30)
            )
            self._owns_session = True
        return self._session
    
    async def close(self):
        """Close session if we own it."""
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None
    
    async def upload_chunk(
        self,
        chunk_index: int,
        start_position: int,
        encrypted_chunk: bytes
    ) -> str:
        """
        Upload a single encrypted chunk.
        
        Args:
            chunk_index: Index of the chunk
            start_position: Start position in file
            encrypted_chunk: Encrypted chunk data
            
        Returns:
            Upload token from server
            
        Raises:
            ValueError: If chunk is empty or server returns error
            aiohttp.ClientError: If network error occurs
        """
        if not encrypted_chunk:
            raise ValueError(f"Cannot upload empty chunk {chunk_index}")
        
        chunk_size_kb = len(encrypted_chunk) / 1024
        url = f"{self._upload_url}/{start_position}"
        headers = {"Content-Length": str(len(encrypted_chunk))}
        session = await self._get_session()
        
        upload_start = time.time()
        self._logger.debug(f"Uploading chunk {chunk_index} at position {start_position} ({chunk_size_kb:.1f} KB)")
        
        try:
            async with session.post(
                url,
                data=encrypted_chunk,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=self._timeout, connect=10)
            ) as response:
                response.raise_for_status()
                response_text = await response.text()
                result = self._process_response(response_text, chunk_index)
                upload_time = time.time() - upload_start
                speed_kbps = (chunk_size_kb / upload_time) if upload_time > 0 else 0
                self._logger.debug(f"Chunk {chunk_index} uploaded successfully in {upload_time:.2f}s ({speed_kbps:.1f} KB/s)")
                return result
        except asyncio.TimeoutError:
            upload_time = time.time() - upload_start
            self._logger.error(f"Chunk {chunk_index} upload timeout after {upload_time:.2f}s (timeout={self._timeout}s)")
            raise
        except Exception as e:
            upload_time = time.time() - upload_start
            self._logger.error(f"Chunk {chunk_index} upload failed after {upload_time:.2f}s: {e}")
            raise
    
    def _process_response(self, response_text: str, chunk_index: int) -> str:
        """
        Process server response.
        
        Args:
            response_text: Raw response text
            chunk_index: Index of uploaded chunk
            
        Returns:
            Upload token (empty string for intermediate chunks, token for last chunk)
            
        Raises:
            ValueError: If response is an error code
        """
        # Check for error code (negative number)
        try:
            error_code = int(response_text)
            if error_code < 0:
                self._logger.error(f"Server returned error {error_code} for chunk {chunk_index}")
                raise ValueError(
                    f"Server error {error_code} uploading chunk {chunk_index}"
                )
        except ValueError as e:
            # Re-raise if it was our error
            if "Server error" in str(e):
                raise
            # Otherwise it's not a number, likely a valid token
        
        # CRITICAL: Only update token if response is not empty
        # MEGA returns empty string for intermediate chunks, and the token only for the last chunk
        # Due to parallel uploads, intermediate chunks might complete after the last chunk,
        # so we must not overwrite a valid token with an empty string
        if response_text and response_text.strip():
            self._upload_token = response_text
            self._logger.debug(f"Upload token received from chunk {chunk_index}: {response_text[:20]}...")
        else:
            # Empty response for intermediate chunk - this is normal
            self._logger.debug(f"Chunk {chunk_index} completed (intermediate chunk, no token)")
        
        return response_text
    
    def get_upload_token(self) -> Optional[str]:
        """
        Get the latest upload token.
        
        Returns:
            Upload token or None if no chunks uploaded
        """
        return self._upload_token
