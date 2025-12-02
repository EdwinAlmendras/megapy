"""
Chunk upload service.

Handles uploading individual chunks to MEGA servers.
"""
from typing import Optional
import aiohttp


class ChunkUploader:
    """
    Handles uploading encrypted chunks to MEGA.
    
    Responsibilities:
    - Send chunks to upload URL
    - Handle HTTP responses
    - Track upload token
    """
    
    DEFAULT_TIMEOUT = 120
    
    def __init__(self, upload_url: str, timeout: int = DEFAULT_TIMEOUT):
        """
        Initialize chunk uploader.
        
        Args:
            upload_url: Base URL for chunk uploads
            timeout: Request timeout in seconds
        """
        self._upload_url = upload_url
        self._timeout = timeout
        self._upload_token: Optional[str] = None
    
    @property
    def upload_url(self) -> str:
        """Returns the upload URL."""
        return self._upload_url
    
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
        
        url = f"{self._upload_url}/{start_position}"
        headers = {"Content-Length": str(len(encrypted_chunk))}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=encrypted_chunk,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._timeout)
            ) as response:
                response.raise_for_status()
                response_text = await response.text()
                return self._process_response(response_text, chunk_index)
    
    def _process_response(self, response_text: str, chunk_index: int) -> str:
        """
        Process server response.
        
        Args:
            response_text: Raw response text
            chunk_index: Index of uploaded chunk
            
        Returns:
            Upload token
            
        Raises:
            ValueError: If response is an error code
        """
        # Check for error code (negative number)
        try:
            error_code = int(response_text)
            if error_code < 0:
                raise ValueError(
                    f"Server error {error_code} uploading chunk {chunk_index}"
                )
        except ValueError as e:
            # Re-raise if it was our error
            if "Server error" in str(e):
                raise
            # Otherwise it's not a number, likely a valid token
        
        self._upload_token = response_text
        return response_text
    
    def get_upload_token(self) -> Optional[str]:
        """
        Get the latest upload token.
        
        Returns:
            Upload token or None if no chunks uploaded
        """
        return self._upload_token
