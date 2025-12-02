"""MEGA API client using composition."""
import random
import logging
from typing import Dict, Optional, Callable, Any
from ..events import EventEmitter
from ..session import SessionManager
from ..request import RequestHandler, RequestBuilder
from ..notifications import NotificationPuller
from ..errors import MegaAPIError
from utils.logger import setup_logger


class APIClient(EventEmitter):
    """MEGA API client."""
    
    DEFAULT_GATEWAY = 'https://g.api.mega.co.nz/'
    
    def __init__(self, keepalive: bool = True, **options):
        """Initializes API client."""
        super().__init__("MEGA_API")
        self.keepalive = keepalive
        self.counter_id = str(random.randint(0, 1000000000))
        self.gateway = options.get('gateway', self.DEFAULT_GATEWAY)
        try:
            import megapy
            version = getattr(megapy, '__version__', '0.0.0')
        except ImportError:
            version = '0.0.0'
        user_agent = options.get('user_agent', f'megapy/{version}')
        
        self.session_manager = SessionManager(user_agent)
        self.request_handler = RequestHandler(self.session_manager.get_sync_session())
        self.notification_puller: Optional[NotificationPuller] = None
        
        self._session_id: Optional[str] = None
        self.sn: Optional[str] = None
        self.closed = False
        
        level = options.get('level', logging.DEBUG)
        self.logger = setup_logger("MEGA_API", level=level)
    
    @property
    def session_id(self) -> Optional[str]:
        """Gets session ID."""
        return self._session_id
    
    @session_id.setter
    def session_id(self, value: Optional[str]):
        """Sets session ID."""
        self._session_id = value
    
    @property
    def sid(self) -> Optional[str]:
        """Session ID (for backward compatibility)."""
        return self._session_id
    
    @sid.setter
    def sid(self, value: Optional[str]):
        """Sets session ID."""
        self._session_id = value
    
    def request(self, json_data: Dict, callback: Optional[Callable] = None, 
                retry_no: int = 0) -> Any:
        """Makes a request to the MEGA API."""
        is_logout = json_data.get('a') == 'sml'
        
        if self.closed and not is_logout:
            raise Exception("API is closed")
        
        if '_hashcash' not in json_data:
            self.counter_id = str(int(self.counter_id) + 1)
        
        builder = RequestBuilder(self.gateway, self.counter_id, self.session_id)
        
        if '_querystring' in json_data:
            builder = RequestBuilder(
                self.gateway, 
                self.counter_id, 
                self.session_id
            )
        
        result = self.request_handler.execute(builder, json_data, callback, retry_no)
        
        if isinstance(result, dict) and 'sn' in result and self.keepalive:
            if not self.notification_puller:
                self.notification_puller = NotificationPuller(
                    self.gateway,
                    self.session_id,
                    self.session_manager,
                    self
                )
            self.notification_puller.start(result['sn'])
        
        return result
    
    def get_files(self):
        """Gets files list."""
        return self.request({'a': 'f', 'c': 1})
    
    def get_user_info(self):
        """Gets user information."""
        return self.request({'a': 'ug'})
    
    def get_download_url(self, handle: str):
        """Gets download URL."""
        return self.request({'a': 'g', 'g': 1, 'n': handle})
    
    def move(self, handle: str, target: str):
        """Moves node."""
        return self.request({'a': 'm', 'n': handle, 't': target})
    
    def rename(self, handle: str, attrs: Dict):
        """Renames node."""
        return self.request({'a': 'a', 'n': handle, 'attr': attrs})
    
    def close(self):
        """Closes API connection (synchronous for compatibility)."""
        import asyncio
        self.closed = True
        if self.notification_puller:
            self.notification_puller.close()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.session_manager.close())
            else:
                loop.run_until_complete(self.session_manager.close())
        except RuntimeError:
            asyncio.run(self.session_manager.close())

