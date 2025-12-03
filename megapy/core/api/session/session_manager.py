"""Session manager for HTTP connections."""
import aiohttp
from typing import Optional
from .session_factory import SessionFactory


class SessionManager:
    """Manages HTTP sessions."""
    
    def __init__(self, user_agent: str):
        """Initializes session manager."""
        self.user_agent = user_agent
        self.sync_session = SessionFactory.create_sync_session(user_agent)
        self._async_session: Optional[aiohttp.ClientSession] = None
    
    def get_sync_session(self):
        """Gets synchronous session."""
        return self.sync_session
    
    async def get_async_session(self) -> aiohttp.ClientSession:
        """Gets or creates asynchronous session."""
        if self._async_session is None or self._async_session.closed:
            self._async_session = await SessionFactory.create_async_session(self.user_agent)
        return self._async_session
    
    async def close(self):
        """Closes all sessions."""
        if self.sync_session:
            self.sync_session.close()
        
        if self._async_session and not self._async_session.closed:
            await self._async_session.close()
            self._async_session = None

