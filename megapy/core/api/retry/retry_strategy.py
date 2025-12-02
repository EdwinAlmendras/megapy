"""Retry strategies using Strategy Pattern."""
import time
import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Any


class RetryStrategy(ABC):
    """Abstract retry strategy."""
    
    @abstractmethod
    def should_retry(self, error_code: int, retry_count: int, max_retries: int) -> bool:
        """Determines if request should be retried."""
        pass
    
    @abstractmethod
    def wait(self, retry_count: int):
        """Waits before retry."""
        pass
    
    @abstractmethod
    async def wait_async(self, retry_count: int):
        """Waits before retry (async)."""
        pass


class ExponentialBackoffStrategy(RetryStrategy):
    """Exponential backoff retry strategy."""
    
    def should_retry(self, error_code: int, retry_count: int, max_retries: int) -> bool:
        """Retries on EAGAIN (-3) errors."""
        return error_code == -3 and retry_count < max_retries
    
    def wait(self, retry_count: int):
        """Waits with exponential backoff."""
        backoff_time = 2 ** (retry_count + 1)
        time.sleep(backoff_time)
    
    async def wait_async(self, retry_count: int):
        """Waits with exponential backoff (async)."""
        backoff_time = 2 ** (retry_count + 1)
        await asyncio.sleep(backoff_time)

