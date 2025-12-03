"""Server-side notification puller."""
import asyncio
import threading
import json
from urllib.parse import urlencode
from typing import Optional
from ..errors import MegaAPIError, APIErrorCodes
from ..retry import RetryStrategy, ExponentialBackoffStrategy
from megapy.core.logging import get_logger


class NotificationPuller:
    """Pulls server-side notifications."""
    
    def __init__(self, gateway: str, session_id: Optional[str], 
                 session_manager, event_emitter, retry_strategy: RetryStrategy = None):
        """Initializes notification puller."""
        self.gateway = gateway
        self.session_id = session_id
        self.session_manager = session_manager
        self.event_emitter = event_emitter
        self.retry_strategy = retry_strategy or ExponentialBackoffStrategy()
        self.logger = get_logger("NOTIFICATION_PULLER")
        self._sn_task: Optional[threading.Thread] = None
        self.closed = False
    
    def start(self, sn: str):
        """Starts pull loop in background thread."""
        if self._sn_task:
            return
        
        def pull_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._pull(sn))
        
        self._sn_task = threading.Thread(target=pull_loop, daemon=True)
        self._sn_task.start()
    
    async def _pull(self, sn: str, retry_count: int = 0, max_retries: int = 4):
        """Pulls server-side notifications."""
        session = await self.session_manager.get_async_session()
        
        try:
            params = {'sn': sn, 'ssl': 1}
            if self.session_id:
                params['sid'] = self.session_id
            
            url = f"{self.gateway}sc?{urlencode(params)}"
            
            async with session.post(url) as response:
                resp_data = await response.json()
                
                if self.closed:
                    return
                
                if isinstance(resp_data, int) and resp_data < 0:
                    if self.retry_strategy.should_retry(resp_data, retry_count, max_retries):
                        await self.retry_strategy.wait_async(retry_count)
                        await self._pull(sn, retry_count + 1, max_retries)
                        return
                    
                    self.event_emitter.emit('error', MegaAPIError(resp_data))
                    return
                
                if resp_data.get('w'):
                    await self._wait(resp_data['w'], sn)
                elif resp_data.get('sn'):
                    if resp_data.get('a'):
                        self.event_emitter.emit('sc', resp_data['a'])
                    await self._pull(resp_data['sn'])
                    
        except Exception as e:
            if not self.closed:
                self.event_emitter.emit('error', e)
    
    async def _wait(self, url: str, sn: str):
        """Waits for server-side events."""
        session = await self.session_manager.get_async_session()
        
        try:
            async with session.post(url) as response:
                resp_data = await response.json()
                if resp_data.get('sn'):
                    await self._pull(resp_data['sn'])
        except Exception as e:
            if not self.closed:
                self.event_emitter.emit('error', e)
    
    def close(self):
        """Closes puller."""
        self.closed = True

