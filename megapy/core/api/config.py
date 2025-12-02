"""
API configuration module.

Provides comprehensive configuration for the MEGA API client.
Open for extension through custom configurations.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import ssl


@dataclass
class ProxyConfig:
    """
    Proxy configuration.
    
    Supports HTTP, HTTPS, and SOCKS proxies.
    """
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    
    def to_aiohttp_proxy(self) -> Optional[str]:
        """Convert to aiohttp proxy format."""
        if not self.url:
            return None
        
        if self.username and self.password:
            # Insert credentials into URL
            if '://' in self.url:
                protocol, rest = self.url.split('://', 1)
                return f"{protocol}://{self.username}:{self.password}@{rest}"
        
        return self.url


@dataclass
class SSLConfig:
    """
    SSL/TLS configuration.
    
    Allows customization of SSL behavior for security requirements.
    """
    verify: bool = True
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    ca_file: Optional[str] = None
    check_hostname: bool = True
    
    def create_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create SSL context from configuration."""
        if not self.verify:
            return False  # Disable SSL verification
        
        context = ssl.create_default_context()
        
        if self.ca_file:
            context.load_verify_locations(self.ca_file)
        
        if self.cert_file:
            context.load_cert_chain(
                self.cert_file,
                keyfile=self.key_file
            )
        
        context.check_hostname = self.check_hostname
        
        return context


@dataclass
class TimeoutConfig:
    """
    Timeout configuration.
    
    Granular control over different timeout types.
    """
    total: float = 300.0  # Total request timeout
    connect: float = 30.0  # Connection timeout
    sock_read: float = 60.0  # Socket read timeout
    sock_connect: float = 30.0  # Socket connect timeout
    
    def to_aiohttp_timeout(self):
        """Convert to aiohttp ClientTimeout."""
        import aiohttp
        return aiohttp.ClientTimeout(
            total=self.total,
            connect=self.connect,
            sock_read=self.sock_read,
            sock_connect=self.sock_connect
        )


@dataclass
class RetryConfig:
    """
    Retry configuration.
    
    Controls retry behavior for failed requests.
    """
    max_retries: int = 4
    base_delay: float = 0.25
    max_delay: float = 16.0
    exponential_base: float = 2.0
    retry_on_codes: tuple = (-3, -6, -18)  # MEGA error codes to retry
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


@dataclass
class APIConfig:
    """
    Complete API configuration.
    
    Centralizes all configuration options for the MEGA API client.
    Follows Open/Closed principle - extend by creating new config classes.
    """
    # Gateway settings
    gateway: str = 'https://g.api.mega.co.nz/'
    
    # User agent
    user_agent: str = 'megapy/1.0.0'
    
    # Connection settings
    keepalive: bool = True
    
    # Sub-configurations
    proxy: Optional[ProxyConfig] = None
    ssl: SSLConfig = field(default_factory=SSLConfig)
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    
    # Additional headers
    extra_headers: Dict[str, str] = field(default_factory=dict)
    
    # Logging
    log_level: int = 20  # logging.INFO
    
    # Connection pool settings
    limit_per_host: int = 10
    limit: int = 100
    
    @classmethod
    def default(cls) -> 'APIConfig':
        """Create default configuration."""
        return cls()
    
    @classmethod
    def with_proxy(cls, proxy_url: str, **kwargs) -> 'APIConfig':
        """Create configuration with proxy."""
        return cls(
            proxy=ProxyConfig(url=proxy_url),
            **kwargs
        )
    
    @classmethod
    def insecure(cls, **kwargs) -> 'APIConfig':
        """Create configuration with SSL verification disabled."""
        return cls(
            ssl=SSLConfig(verify=False, check_hostname=False),
            **kwargs
        )
    
    def get_connector_kwargs(self) -> Dict[str, Any]:
        """Get kwargs for aiohttp TCPConnector."""
        return {
            'limit': self.limit,
            'limit_per_host': self.limit_per_host,
            'ssl': self.ssl.create_ssl_context(),
        }
    
    def get_session_kwargs(self) -> Dict[str, Any]:
        """Get kwargs for aiohttp ClientSession."""
        headers = {
            'User-Agent': self.user_agent,
            **self.extra_headers
        }
        
        return {
            'headers': headers,
            'timeout': self.timeout.to_aiohttp_timeout(),
        }
