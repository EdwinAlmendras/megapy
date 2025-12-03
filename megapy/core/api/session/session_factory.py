"""Session factory using Factory Pattern."""
import requests
import aiohttp
from requests.adapters import HTTPAdapter, Retry
from typing import Optional


class SessionFactory:
    """Factory for creating HTTP sessions."""
    
    @staticmethod
    def create_sync_session(user_agent: str) -> requests.Session:
        """Creates a synchronous HTTP session with retries."""
        session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.5)
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))
        return session
    
    @staticmethod
    async def create_async_session(user_agent: str) -> aiohttp.ClientSession:
        """Creates an asynchronous HTTP session."""
        return aiohttp.ClientSession(
            headers={'User-Agent': user_agent}
        )

