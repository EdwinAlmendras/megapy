"""
Chunk uploader for MEGA file uploads.

This module handles the upload of individual chunks to the MEGA API.
"""
import aiohttp
from typing import Dict, Final, Optional
from mega_py.upload.types.upload_types import EncryptedChunk, Headers, Position, LoggerProtocol, UploadToken

class ChunkUploader:
    """
    Handles the upload of individual chunks to the MEGA API.
    
    This class is responsible for:
    - Preparing HTTP headers for chunk uploads
    - Sending chunks to the MEGA server
    - Processing server responses
    
    Attributes:
        upload_url: Base URL for upload
        logger: Logger instance
    """
    
    # Default timeout in seconds
    DEFAULT_TIMEOUT: Final[int] = 120
    
    def __init__(self, upload_url: str, logger: LoggerProtocol = None) -> None:
        """
        Initialize the chunk uploader.
        
        Args:
            upload_url: Base URL for upload
            logger: Logger instance
        """
        self.upload_url = upload_url
        self.logger = logger
        self.upload_token: Optional[str] = None
    
    def prepare_headers(self, chunk_size: int) -> Headers:
        """
        Prepare HTTP headers for chunk upload.
        
        Args:
            chunk_size: Size of the chunk in bytes
            
        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Length": str(chunk_size)
        }
        
        return headers
    
    async def upload_chunk(
        self, 
        chunk_index: int, 
        start_position: Position, 
        encrypted_chunk: EncryptedChunk,
        timeout: int = DEFAULT_TIMEOUT
    ) -> UploadToken:
        """
        Upload a chunk to the MEGA server.
        
        Args:
            chunk_index: Index of the chunk being uploaded
            start_position: Start position of the chunk in the file
            encrypted_chunk: Encrypted chunk data to upload
            timeout: Request timeout in seconds (default: 120)
            
        Returns:
            Upload token from the server
            
        Raises:
            aiohttp.ClientError: If there's a network error
            ValueError: If there's an error in the server response
        """
        if not encrypted_chunk:
            error_msg = f"Cannot upload empty chunk at position {start_position}"
            if self.logger:
                self.logger.error(error_msg)
            raise ValueError(error_msg)
            
        upload_url = f"{self.upload_url}/{start_position}"
        headers = self.prepare_headers(len(encrypted_chunk))
        
        """ if self.logger:
            self.logger.debug(
                f"Uploading chunk {chunk_index} at position {start_position} "
                f"with size: {len(encrypted_chunk)} bytes"
            ) """
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    upload_url,
                    data=encrypted_chunk,
                    headers=headers,
                    ssl=None,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    response.raise_for_status()
                    response_text = await response.text()
                    return await self._process_response(response_text, chunk_index)
                    
        except aiohttp.ClientError as e:
            if self.logger:
                self.logger.error(f"Network error uploading chunk {chunk_index}: {str(e)}")
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error uploading chunk {chunk_index}: {str(e)}")
            raise
    
    async def _process_response(self, response_text: str, chunk_index: int) -> UploadToken:
        """
        Process the server response after uploading a chunk.
        
        Args:
            response_text: Text response from the server
            chunk_index: Index of the uploaded chunk
            
        Returns:
            Upload token
            
        Raises:
            ValueError: If there's an error in the response
        """
        """ if not response_text:
            error_msg = f"Empty response when uploading chunk {chunk_index}"
            if self.logger:
                self.logger.error(error_msg)
            raise ValueError(error_msg) """
            
        # Check if the response is an error code
        try:
            error_code = -int(response_text)
            error_msg = f"Error code {error_code} when uploading chunk {chunk_index}"
            if self.logger:
                self.logger.error(error_msg)
            raise ValueError(error_msg)
        except ValueError:
            # Not an error code, should be a valid token
            pass
        
        # Store the token for the final completion
        self.upload_token = response_text
        
        #if self.logger:
            #self.logger.debug(f"Successfully uploaded chunk {chunk_index}")
        return response_text
        
    def get_upload_token(self) -> Optional[UploadToken]:
        """
        Get the latest upload token.
        
        Returns:
            The latest upload token or None if no chunks have been uploaded
        """
        return self.upload_token 