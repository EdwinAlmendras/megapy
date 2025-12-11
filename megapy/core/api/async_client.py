"""
Async MEGA API client.

Fully asynchronous client with comprehensive configuration support.
"""
import json
import random
import logging
import asyncio
from typing import Dict, Optional, Any, List, Union, Callable
import aiohttp

from .config import APIConfig
from .errors import MegaAPIError
from .events import EventEmitter
from ..crypto import generate_hashcash_token, make_crypto_request


class AsyncAPIClient:
    """
    Asynchronous MEGA API client.
    
    Features:
    - Full async/await support
    - Configurable proxy, SSL, timeouts
    - Automatic retry with exponential backoff
    - Connection pooling
    - Hashcash challenge handling
    - Request batching (groups multiple requests into single API call to avoid EAGAIN)
    
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
        
        # Event emitter for action packets and notifications
        self._event_emitter = EventEmitter('megapy.api')
        
        # Request batching (like webclient)
        self._request_queue: List[Dict[str, Any]] = []
        self._queue_futures: List[asyncio.Future] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._flush_delay = 0.35  # 350ms delay like webclient
        self._max_batch_size = 50  # Maximum requests per batch
        
        from ..logging import get_logger
        self._logger = get_logger('megapy.api')
        # Only set level if root logger has no handlers (basicConfig not called)
        # Otherwise, let it inherit from root logger
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            self._logger.setLevel(self._config.log_level)
    
    def on(self, event: str, callback: Callable) -> 'AsyncAPIClient':
        """Register an event handler (for action packets, etc.)."""
        self._event_emitter.on(event, callback)
        return self
    
    def off(self, event: str, callback: Optional[Callable] = None) -> 'AsyncAPIClient':
        """Remove an event handler."""
        self._event_emitter.off(event, callback)
        return self
    
    def emit(self, event: str, *args, **kwargs):
        """Emit an event."""
        self._event_emitter.emit(event, *args, **kwargs)
    
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
        
        # Flush any pending requests before closing
        if self._request_queue:
            await self._flush_queue()
        
        # Cancel flush task if pending
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
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
        retry_count: int = 0,
        querystring: Optional[Dict[str, str]] = None
    ) -> Any:
        """
        Make async request to MEGA API with automatic batching.
        
        Requests are automatically batched together (like webclient) to avoid
        EAGAIN errors from too many concurrent API calls.
        
        Args:
            data: Request data
            retry_count: Current retry attempt (internal use)
            querystring: Optional query string parameters to add to URL
                        (e.g., {"n": "node_id"}). Can also be passed in data as '_querystring'
            
        Returns:
            API response data
            
        Raises:
            MegaAPIError: If request fails
        """
        if self._closed:
            raise MegaAPIError(-1, "Client is closed")
        
        # Add querystring to data if provided (merge with existing _querystring if any)
        if querystring:
            existing_qs = data.get('_querystring', {})
            if isinstance(existing_qs, dict):
                # Merge querystrings (parameter takes precedence)
                merged_qs = {**existing_qs, **querystring}
            else:
                merged_qs = querystring
            data['_querystring'] = merged_qs
        
        # For immediate requests (with special flags) or if retrying, don't batch
        immediate = data.get('_immediate', False) or retry_count > 0
        
        if immediate:
            return await self._request_immediate(data, retry_count)
        
        # Queue request for batching
        future = asyncio.Future()
        self._request_queue.append(data)
        self._queue_futures.append(future)
        
        # Schedule flush if not already scheduled
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._schedule_flush())
        
        # If queue is full, flush immediately
        if len(self._request_queue) >= self._max_batch_size:
            await self._flush_queue()
        
        return await future
    
    async def _schedule_flush(self):
        """Schedule a flush after delay (like webclient's 350ms delay)."""
        await asyncio.sleep(self._flush_delay)
        await self._flush_queue()
    
    async def _flush_queue(self):
        """Flush all queued requests in a single batch."""
        if not self._request_queue:
            return
        
        # Take all queued requests
        queue = self._request_queue[:]
        futures = self._queue_futures[:]
        
        # Clear queue
        self._request_queue.clear()
        self._queue_futures.clear()
        
        # Cancel flush task if still pending
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        self._flush_task = None
        
        if not queue:
            return
        
        # Execute batch request
        try:
            results = await self._request_batch(queue)
            
            # Resolve futures with results
            for i, future in enumerate(futures):
                if not future.done():
                    if i < len(results):
                        if isinstance(results[i], int) and results[i] < 0:
                            future.set_exception(MegaAPIError(results[i], f"MEGA API error: {results[i]}"))
                        else:
                            future.set_result(results[i])
                    else:
                        future.set_exception(MegaAPIError(-1, "No response received"))
        except Exception as e:
            # If batch fails, fail all futures
            for future in futures:
                if not future.done():
                    future.set_exception(e)
    
    async def _request_batch(
        self,
        requests: List[Dict[str, Any]],
        retry_count: int = 0
    ) -> List[Any]:
        """
        Execute a batch of requests in a single API call.
        
        Args:
            requests: List of request data dicts
            retry_count: Current retry attempt
            
        Returns:
            List of response data
        """
        session = await self._ensure_session()
        self._counter_id += 1
        
        # Extract special fields from first request (if any)
        querystring = requests[0].pop('_querystring', None) if requests else None
        hashcash = requests[0].pop('_hashcash', None) if requests else None
        
        url = self._build_url(querystring)
        headers = {}
        
        if hashcash:
            headers['X-MEGA-hashcash'] = hashcash
        
        # Prepare batch request body (array of requests)
        body = json.dumps(requests)
        
        self._logger.debug(f"Batch request ({len(requests)} requests) to {url}")
        self._logger.debug(f"Request data: {body[:300] if len(body) > 300 else body}")
        
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
                    if requests:
                        requests[0]['_hashcash'] = generate_hashcash_token(challenge)
                    return await self._request_batch(requests, retry_count)
                
                response_text = await response.text()
                self._logger.debug(f"Response data: {response_text[:1000] if len(response_text) > 1000 else response_text}")
                results = self._parse_batch_response(response_text)
                
                # Check for errors and retry if needed
                for i, result in enumerate(results):
                    if isinstance(result, int) and result < 0:
                        if self._should_retry(result, retry_count):
                            # Retry entire batch
                            delay = self._config.retry.calculate_delay(retry_count)
                            self._logger.warning(
                                f"Retrying batch after error {result}, attempt {retry_count + 1}"
                            )
                            await asyncio.sleep(delay)
                            return await self._request_batch(requests, retry_count + 1)
                
                return results
                
        except aiohttp.ClientError as e:
            self._logger.error(f"Network error in batch: {e}")
            
            if retry_count < self._config.retry.max_retries:
                delay = self._config.retry.calculate_delay(retry_count)
                await asyncio.sleep(delay)
                return await self._request_batch(requests, retry_count + 1)
            
            raise MegaAPIError(-1, f"Network error: {e}")
    
    async def _request_immediate(
        self,
        data: Dict[str, Any],
        retry_count: int = 0
    ) -> Any:
        """
        Make immediate request without batching (for retries or special cases).
        
        Args:
            data: Request data
            retry_count: Current retry attempt
            
        Returns:
            API response data
        """
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
        
        self._logger.debug(f"Immediate request to {url}")
        self._logger.debug(f"Request data: {body}")
        
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
                    return await self._request_immediate(data, retry_count)
                
                response_text = await response.text()
                self._logger.debug(f"Response data: {response_text[:1000] if len(response_text) > 1000 else response_text}")
                result = self._parse_response(response_text)
                
                # Handle errors with retry
                if isinstance(result, int) and result < 0:
                    if self._should_retry(result, retry_count):
                        delay = self._config.retry.calculate_delay(retry_count)
                        self._logger.warning(
                            f"Retrying after error {result}, attempt {retry_count + 1}"
                        )
                        await asyncio.sleep(delay)
                        return await self._request_immediate(data, retry_count + 1)
                    
                    raise MegaAPIError(result, f"MEGA API error: {result}")
                
                return result
                
        except aiohttp.ClientError as e:
            self._logger.error(f"Network error: {e}")
            
            if retry_count < self._config.retry.max_retries:
                delay = self._config.retry.calculate_delay(retry_count)
                await asyncio.sleep(delay)
                return await self._request_immediate(data, retry_count + 1)
            
            raise MegaAPIError(-1, f"Network error: {e}")
    
    def _parse_batch_response(self, response_text: str) -> List[Any]:
        """Parse batch API response (array of results)."""
        try:
            data = json.loads(response_text)
            
            if isinstance(data, list):
                return data
            
            # Single result wrapped in array
            return [data]
            
        except json.JSONDecodeError:
            return [response_text]
    
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
    
    async def get_link(self, node_id: str) -> str:
        """
        Get public link for a node.
        
        Args:
            node_id: Node handle
            
        Returns:
            Link ID (to be used in URL construction)
        """
        result = await self.request({'a': 'l', 'n': node_id})
        
        if isinstance(result, int) and result < 0:
            raise MegaAPIError(result, f"Failed to get link: {result}")
        
        if isinstance(result, str):
            return result
        
        # Response might be wrapped
        if isinstance(result, dict) and 'id' in result:
            return result['id']
        
        return str(result)
    
    async def share_folder(
        self,
        node_id: str,
        share_key: bytes,
        encrypted_share_key: str,
        auth_key: str,
        crypto_request: List[Any]
    ) -> Dict[str, Any]:
        """
        Share a folder with a share key.
        
        Args:
            node_id: Folder node handle
            share_key: 16-byte share key (raw bytes)
            encrypted_share_key: Base64-encoded encrypted share key
            auth_key: Base64-encoded authentication key
            crypto_request: Crypto request array [shares, nodes, keys]
            
        Returns:
            API response
        """
        request_data = {
            'a': 's2',
            'n': node_id,
            'ok': encrypted_share_key,
            'ha': auth_key,
            'cr': crypto_request,
            's': [{ "u": "EXP", "r": 0 }]
        }
        
        return await self.request(request_data)
    
    def make_crypto_request(
        self,
        share_keys: Dict[str, bytes],
        sources: Union[List[Dict[str, Any]], Dict[str, Any]],
        shares: Optional[List[str]] = None
    ) -> List[Any]:
        """
        Create a crypto request array for sharing files/folders.
        
        This is a convenience method that wraps the make_crypto_request function.
        It creates the crypto request array format used in MEGA API calls.
        
        Args:
            share_keys: Dictionary mapping share handles to their encryption keys
            sources: List of source nodes (dicts with 'nodeId'/'handle' and 'key') 
                     or a single node dict
            shares: Optional list of share handles. If not provided, will be 
                    automatically determined from share_keys
        
        Returns:
            Crypto request array: [shares, nodes, keys]
            
        Example:
            >>> share_keys = {'share_handle': b'16-byte-share-key'}
            >>> sources = [{'nodeId': 'node1', 'key': b'32-byte-file-key'}]
            >>> cr = await api_client.make_crypto_request(share_keys, sources)
        """
        return make_crypto_request(share_keys, sources, shares)
    
    async def get_media_codecs(self) -> Dict[str, Any]:
        """
        Get media codecs list from MEGA.
        
        Returns:
            Dict with container, video, audio codec mappings
        """
        result = await self.request({'a': 'mc'})
        
        if not isinstance(result, list) or len(result) != 2:
            return {}
        
        # Parse the codec list (format from MEGA API)
        # result[0] = version number
        # result[1] = [[container list], [video list], [audio list], [shortformat list]]
        data = {
            'version': result[0],
            'container': {},
            'video': {},
            'audio': {},
            'shortformat': {}
        }
        
        sections = result[1]
        keys = ['container', 'video', 'audio', 'shortformat']
        
        for i, sec in enumerate(sections):
            if i >= len(keys):
                break
            key = keys[i]
            
            if i < 3:
                # container, video, audio: [[id, name, mime], ...]
                for item in sec:
                    codec_id = item[0]
                    codec_name = item[1]
                    data[key][codec_id] = codec_name
            else:
                # shortformat: [[id, container_id, video_id, audio_id], ...]
                for item in sec:
                    sf_id = item[0]
                    container = data['container'].get(item[1], '')
                    video = data['video'].get(item[2], '')
                    audio = data['audio'].get(item[3], '')
                    data[key][sf_id] = (container, video, audio)
        
        return data
