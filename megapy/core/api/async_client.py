"""
Async MEGA API client.

Fully asynchronous client with comprehensive configuration support.
"""
import json
import random
import logging
import asyncio
from typing import Dict, Optional, Any, List
import aiohttp

from .config import APIConfig
from .errors import MegaAPIError
from ..crypto import generate_hashcash_token


class AsyncAPIClient:
    """
    Asynchronous MEGA API client.
    
    Features:
    - Full async/await support
    - Configurable proxy, SSL, timeouts
    - Automatic retry with exponential backoff
    - Connection pooling
    - Hashcash challenge handling
    
    Example:
        >>> config = APIConfig.default()
        >>> async with AsyncAPIClient(config) as client:
        ...     result = await client.request({'a': 'ug'})
    """
    
    def __init__(self, config: Optional[APIConfig] = None):
        """
        Initialize async API client.
        
        Args:
            config: API configuration (uses defaults if not provided)
        """
        self._config = config or APIConfig.default()
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._counter_id = random.randint(0, 1_000_000_000)
        self._session_id: Optional[str] = None
        self._closed = False
        
        self._logger = logging.getLogger('megapy.api')
        self._logger.setLevel(self._config.log_level)
    
    @property
    def session_id(self) -> Optional[str]:
        """Get session ID."""
        return self._session_id
    
    @session_id.setter
    def session_id(self, value: Optional[str]):
        """Set session ID."""
        self._session_id = value
    
    # Alias for compatibility
    @property
    def sid(self) -> Optional[str]:
        return self._session_id
    
    @sid.setter
    def sid(self, value: Optional[str]):
        self._session_id = value
    
    @property
    def config(self) -> APIConfig:
        """Get current configuration."""
        return self._config
    
    async def __aenter__(self) -> 'AsyncAPIClient':
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure session is created and open."""
        if self._session is None or self._session.closed:
            self._connector = aiohttp.TCPConnector(
                **self._config.get_connector_kwargs()
            )
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                **self._config.get_session_kwargs()
            )
        return self._session
    
    async def close(self):
        """Close client and release resources."""
        self._closed = True
        
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        
        if self._connector and not self._connector.closed:
            await self._connector.close()
            self._connector = None
    
    def _build_url(self, querystring: Optional[Dict[str, str]] = None) -> str:
        """Build request URL."""
        url = f"{self._config.gateway}cs?id={self._counter_id}"
        
        if self._session_id:
            url += f"&sid={self._session_id}"
        
        if querystring:
            for key, value in querystring.items():
                url += f"&{key}={value}"
        
        return url
    
    async def request(
        self,
        data: Dict[str, Any],
        retry_count: int = 0
    ) -> Any:
        """
        Make async request to MEGA API.
        
        Args:
            data: Request data
            retry_count: Current retry attempt
            
        Returns:
            API response data
            
        Raises:
            MegaAPIError: If request fails
        """
        if self._closed:
            raise MegaAPIError(-1, "Client is closed")
        
        session = await self._ensure_session()
        self._counter_id += 1
        
        # Extract special fields
        querystring = data.pop('_querystring', None)
        hashcash = data.pop('_hashcash', None)
        
        url = self._build_url(querystring)
        headers = {}
        
        if hashcash:
            headers['X-MEGA-hashcash'] = hashcash
        
        # Prepare request body
        body = json.dumps([data])
        
        self._logger.debug(f"Request to {url}")
        
        try:
            async with session.post(
                url,
                data=body,
                headers=headers,
                proxy=self._config.proxy.to_aiohttp_proxy() if self._config.proxy else None
            ) as response:
                # Handle hashcash challenge
                if 'X-Hashcash' in response.headers:
                    challenge = response.headers['X-Hashcash']
                    data['_hashcash'] = generate_hashcash_token(challenge)
                    return await self.request(data, retry_count)
                
                response_text = await response.text()
                result = self._parse_response(response_text)
                
                # Handle errors with retry
                if isinstance(result, int) and result < 0:
                    if self._should_retry(result, retry_count):
                        delay = self._config.retry.calculate_delay(retry_count)
                        self._logger.warning(
                            f"Retrying after error {result}, attempt {retry_count + 1}"
                        )
                        await asyncio.sleep(delay)
                        return await self.request(data, retry_count + 1)
                    
                    raise MegaAPIError(result, f"MEGA API error: {result}")
                
                return result
                
        except aiohttp.ClientError as e:
            self._logger.error(f"Network error: {e}")
            
            if retry_count < self._config.retry.max_retries:
                delay = self._config.retry.calculate_delay(retry_count)
                await asyncio.sleep(delay)
                return await self.request(data, retry_count + 1)
            
            raise MegaAPIError(-1, f"Network error: {e}")
    
    def _parse_response(self, response_text: str) -> Any:
        """Parse API response."""
        try:
            data = json.loads(response_text)
            
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            
            return data
            
        except json.JSONDecodeError:
            return response_text
    
    def _should_retry(self, error_code: int, retry_count: int) -> bool:
        """Check if should retry for given error."""
        return (
            error_code in self._config.retry.retry_on_codes and
            retry_count < self._config.retry.max_retries
        )
    
    # Convenience methods
    
    async def get_user_info(self) -> Dict[str, Any]:
        """Get user information."""
        return await self.request({'a': 'ug'})
    
    async def get_files(self) -> Dict[str, Any]:
        """Get files list."""
        return await self.request({'a': 'f', 'c': 1})
    
    async def get_upload_url(self, size: int) -> str:
        """
        Get upload URL for file.
        
        Args:
            size: File size in bytes
            
        Returns:
            Upload URL
        """
        result = await self.request({'a': 'u', 's': size})
        
        if 'p' not in result:
            raise MegaAPIError(-1, "Failed to get upload URL")
        
        return result['p']
    
    async def create_node(
        self,
        target_id: str,
        nodes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create node(s) in MEGA.
        
        Args:
            target_id: Parent folder ID
            nodes: List of node data
            
        Returns:
            API response
        """
        return await self.request({
            'a': 'p',
            't': target_id,
            'n': nodes
        })
    
    async def get_download_url(self, handle: str) -> str:
        """
        Get download URL for file.
        
        Args:
            handle: File handle
            
        Returns:
            Download URL
        """
        result = await self.request({'a': 'g', 'g': 1, 'n': handle})
        return result.get('g', '')
    
    async def delete_node(self, handle: str) -> Dict[str, Any]:
        """
        Delete a node.
        
        Args:
            handle: Node handle
            
        Returns:
            API response
        """
        return await self.request({'a': 'd', 'n': handle})
    
    async def move_node(self, handle: str, target: str) -> Dict[str, Any]:
        """
        Move node to different folder.
        
        Args:
            handle: Node handle
            target: Target folder handle
            
        Returns:
            API response
        """
        return await self.request({'a': 'm', 'n': handle, 't': target})
