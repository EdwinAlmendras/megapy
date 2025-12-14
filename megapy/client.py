"""
MegaClient - High-level async client for MEGA.

Example:
    >>> async with MegaClient("session") as mega:
    ...     root = await mega.get_root()
    ...     for node in root:
    ...         print(node)
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Callable
from dataclasses import dataclass, field
from .core.nodes.key import KeyFileManager
from .core.api import (
    AsyncAPIClient,
    AsyncAuthService,
    AuthResult,
    APIConfig,
    ProxyConfig,
    SSLConfig,
    TimeoutConfig,
    RetryConfig
)
from .core.upload import UploadCoordinator, UploadConfig, UploadResult, UploadProgress
from .core.upload.models import FileAttributes
from .core.crypto import Base64Encoder, AESCrypto
from .core.session import SessionStorage, SessionData, SQLiteSession, MemorySession
from .core.nodes import NodeService
from .node import Node

# Backward compatibility
MegaFile = Node
MegaNode = Node


import logging
logger = logging.getLogger(__name__)

@dataclass  
class UserInfo:
    """User account information."""
    user_id: str
    email: str
    name: str
    total_storage: int = 0
    used_storage: int = 0
    
    @property
    def free_storage(self) -> int:
        return self.total_storage - self.used_storage
    
    @property
    def usage_percent(self) -> float:
        if self.total_storage == 0:
            return 0.0
        return (self.used_storage / self.total_storage) * 100


@dataclass
class AccountInfo:
    """
    MEGA account storage and bandwidth information.
    
    Attributes:
        account_type: Account type (0=free, 1=pro1, 2=pro2, 3=pro3, 4=lite, 100=business)
        space_used: Storage used in bytes
        space_total: Total storage in bytes
        download_bandwidth_used: Download bandwidth used in bytes
        download_bandwidth_total: Total download bandwidth (default 10PB for pro)
        shared_bandwidth_used: Shared bandwidth used
        shared_bandwidth_limit: Shared bandwidth ratio limit
    """
    account_type: int
    space_used: int
    space_total: int
    download_bandwidth_used: int = 0
    download_bandwidth_total: int = 0
    shared_bandwidth_used: int = 0
    shared_bandwidth_limit: float = 0.0
    
    @property
    def space_free(self) -> int:
        """Free storage space in bytes."""
        return max(0, self.space_total - self.space_used)
    
    @property
    def space_used_percent(self) -> float:
        """Storage usage percentage."""
        if self.space_total == 0:
            return 0.0
        return (self.space_used / self.space_total) * 100
    
    @property
    def space_free_gb(self) -> float:
        """Free storage in GB."""
        return self.space_free / (1024 ** 3)
    
    @property
    def space_used_gb(self) -> float:
        """Used storage in GB."""
        return self.space_used / (1024 ** 3)
    
    @property
    def space_total_gb(self) -> float:
        """Total storage in GB."""
        return self.space_total / (1024 ** 3)
    
    @property
    def is_free_account(self) -> bool:
        """Check if this is a free account."""
        return self.account_type == 0
    
    @property
    def is_pro_account(self) -> bool:
        """Check if this is a pro account."""
        return self.account_type in (1, 2, 3, 4, 100)
    
    def has_space_for(self, file_size: int) -> bool:
        """Check if account has enough space for a file."""
        return self.space_free >= file_size
    
    def __str__(self) -> str:
        type_names = {0: "Free", 1: "Pro I", 2: "Pro II", 3: "Pro III", 4: "Lite", 100: "Business"}
        type_name = type_names.get(self.account_type, f"Unknown({self.account_type})")
        return (
            f"Account: {type_name}\n"
            f"Storage: {self.space_used_gb:.2f} GB / {self.space_total_gb:.2f} GB "
            f"({self.space_used_percent:.1f}% used, {self.space_free_gb:.2f} GB free)"
        )


class MegaClient:
    """
    High-level async client for MEGA with session support.
    
    Supports two modes:
    
    1. Session mode (like Telethon):
        >>> client = MegaClient("my_account")
        >>> await client.start()  # Prompts for email/password if needed
        >>> # Session saved to my_account.session
    
    2. Direct credentials mode:
        >>> async with MegaClient("email", "password") as mega:
        ...     files = await mega.list_files()
    
    With custom configuration:
        >>> config = MegaClient.create_config(proxy="http://proxy:8080")
        >>> client = MegaClient("session", config=config)
        >>> await client.start()
    """
    
    _codecs_cache: Optional[dict] = None  # Class-level cache for codec list
    
    def __init__(
        self,
        session: Optional[Union[str, SessionStorage]] = None,
        api_id: Optional[str] = None,  # Second arg = password for backward compat
        *,
        config: Optional[APIConfig] = None,
        base_path: Optional[Path] = None,
        auto_reconnect: bool = True,
        email: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize MEGA client.
        
        Args:
            session: Session name (creates .session file) OR email (if api_id provided)
            api_id: Password (for backward compatibility with email/password usage)
            config: Optional API configuration
            base_path: Base path for session files
            auto_reconnect: Whether to auto-reconnect on session resume
            email: Optional email for login (used with session mode)
            password: Optional password for login (used with session mode)
        """
        from .core.logging import get_logger
        
        self._config = config or APIConfig.default()
        self._auto_reconnect = auto_reconnect
        self._logger = get_logger('megapy.client')
        
        # Determine mode based on arguments
        if session is None:
            # No session provided - use memory session (for registration, etc.)
            self._email: Optional[str] = email
            self._password: Optional[str] = password
            self._session: SessionStorage = MemorySession()
            self._session_mode = False
        elif api_id is not None:
            # Backward compatible: MegaClient(email, password)
            self._email = session
            self._password = api_id
            self._session: SessionStorage = MemorySession()
            self._session_mode = False
        elif isinstance(session, str):
            # Session mode: MegaClient("session_name", email=..., password=...)
            self._email: Optional[str] = email
            self._password: Optional[str] = password
            self._session = SQLiteSession(session, base_path)
            self._session_mode = True
        else:
            # Custom session storage: MegaClient(custom_storage)
            self._email = email
            self._password = password
            self._session = session
            self._session_mode = True
        
        # API clients
        self._api: Optional[AsyncAPIClient] = None
        self._auth: Optional[AsyncAuthService] = None
        self._auth_result: Optional[AuthResult] = None
        
        # State
        self._master_key: Optional[bytes] = None
        self._node_service: Optional[NodeService] = None
        self._current_node: Optional[Node] = None
        
        # Registration state (for multi-step registration)
        self._registration_master_key: Optional[bytes] = None
        self._registration_client_random_value: Optional[bytes] = None
        self._registration_password: Optional[str] = None
    
    # =========================================================================
    # Configuration helpers
    # =========================================================================
    
    @staticmethod
    def create_config(
        proxy: Optional[str] = None,
        proxy_user: Optional[str] = None,
        proxy_pass: Optional[str] = None,
        timeout: float = 300,
        max_retries: int = 4,
        verify_ssl: bool = True,
        user_agent: Optional[str] = None
    ) -> APIConfig:
        """
        Create API configuration with common options.
        
        Args:
            proxy: Proxy URL (e.g., "http://proxy:8080")
            proxy_user: Proxy username
            proxy_pass: Proxy password
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            verify_ssl: Whether to verify SSL certificates
            user_agent: Custom user agent string
            
        Returns:
            APIConfig instance
        """
        proxy_config = None
        if proxy:
            proxy_config = ProxyConfig(
                url=proxy,
                username=proxy_user,
                password=proxy_pass
            )
        
        return APIConfig(
            proxy=proxy_config,
            timeout=TimeoutConfig(total=timeout),
            retry=RetryConfig(max_retries=max_retries),
            ssl=SSLConfig(verify=verify_ssl),
            user_agent=user_agent or 'megapy/1.0.0'
        )
    
    # =========================================================================
    # Session management
    # =========================================================================
    
    async def start(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None
    ) -> 'MegaClient':
        """
        Start the client - login or resume session.
        
        If a valid session exists, it will be resumed.
        Otherwise, prompts for credentials interactively.
        
        Args:
            email: Optional email (skips prompt)
            password: Optional password (skips prompt)
            
        Returns:
            Self for chaining
            
        Example:
            >>> client = MegaClient("my_session")
            >>> await client.start()
            Enter email: user@example.com
            Enter password: 
            Logged in as: UserName
        """
        # Initialize API client
        self._api = AsyncAPIClient(self._config)
        await self._api.__aenter__()
        self._auth = AsyncAuthService(self._api)
        self._logger.info(f"Existing sesino: {self._session}")
        # Try to resume existing session
        if self._session.exists():
            session_data = self._session.load()
            self._logger.info(f"Session data: {session_data}")
            if session_data and session_data.is_valid():
                self._logger.info(f"Session data is valid")
                try:
                    self._logger.info(f"Trying to resume sessions.. {session_data.email}")
                    await self._resume_session(session_data)
                    self._logger.info(f"Session resumed for {session_data.email}")
                    return self
                except Exception as e:
                    self._logger.warning(f"Failed to resume session {self._session} : {e}")
                    # Continue to fresh login
        
        # Get credentials
        if email:
            self._email = email
        if password:
            self._password = password
        if not self._email or not self._password:
            self._email, self._password = await self._prompt_credentials()
        
        # Fresh login
        await self._do_login()
        
        return self
    
    async def _prompt_credentials(self) -> tuple:
        """Prompt user for credentials interactively."""
        import getpass
        
        loop = asyncio.get_event_loop()
        
        # Use thread executor for blocking input
        def get_email():
            return input("Enter email: ")
        
        def get_password():
            return getpass.getpass("Enter password: ")
        
        email = self._email
        password = self._password
        
        if not email:
            email = await loop.run_in_executor(None, get_email)
        
        if not password:
            password = await loop.run_in_executor(None, get_password)
        
        return email, password
    
    async def _do_login(self) -> UserInfo:
        """Perform fresh login and save session."""
        if not self._auth:
            raise RuntimeError("Client not initialized")
        
        # Login
        self._auth_result = await self._auth.login(self._email, self._password)
        self._master_key = self._auth_result.master_key
        
        # Save session
        session_data = SessionData(
            email=self._email,
            session_id=self._auth_result.session_id,
            user_id=self._auth_result.user_id,
            user_name=self._auth_result.user_name,
            master_key=self._auth_result.master_key,
            private_key=self._auth_result.private_key
        )
        self._session.save(session_data)
        
        self._logger.info(f"Logged in as {self._auth_result.user_name}")
        
        return UserInfo(
            user_id=self._auth_result.user_id,
            email=self._email,
            name=self._auth_result.user_name
        )
    
    async def _resume_session(self, session_data: SessionData) -> None:
        """Resume existing session."""
        # Set session ID on API client
        self._api.session_id = session_data.session_id
        self._master_key = session_data.master_key
        self._email = session_data.email
        
        # Verify session is still valid
        try:
            user_info = await self._api.get_user_info()
            
            # Create auth result from session data
            self._auth_result = AuthResult(
                session_id=session_data.session_id,
                user_id=session_data.user_id,
                user_name=user_info.get('name', session_data.user_name),
                email=session_data.email,
                master_key=session_data.master_key,
                private_key=session_data.private_key
            )
            
            # Update session with latest info
            session_data.user_name = self._auth_result.user_name
            session_data.update_timestamp()
            self._session.save(session_data)
            
        except Exception as e:
            # Session expired or invalid
            self._session.delete()
            raise RuntimeError(f"Session expired: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect but keep session for later."""
        await self.close()
    
    async def log_out(self) -> None:
        """Logout and delete session."""
        if self._auth:
            try:
                await self._auth.logout()
            except Exception:
                pass
        
        self._session.delete()
        self._auth_result = None
        self._master_key = None
        self._node_service = None
        self._current_node = None
        
        await self.close()
    
    def get_session(self) -> Optional[SessionData]:
        """Get current session data."""
        return self._session.load()
    
    # =========================================================================
    # Context manager
    # =========================================================================
    
    async def __aenter__(self) -> 'MegaClient':
        """Enter async context - connects and logs in."""
        if self._session_mode:
            # If email and password are provided, pass them to start()
            if self._email and self._password:
                await self.start(email=self._email, password=self._password)
            else:
                await self.start()
        elif self._email and self._password:
            # Direct credentials mode
            self._api = AsyncAPIClient(self._config)
            await self._api.__aenter__()
            self._auth = AsyncAuthService(self._api)
            await self._do_login()
        else:
            # No credentials - just initialize API (for registration, etc.)
            self._api = AsyncAPIClient(self._config)
            await self._api.__aenter__()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context - cleanup."""
        await self.close()
    
    async def close(self):
        """Close the client and release resources."""
        if self._api:
            await self._api.close()
            self._api = None
        
        if hasattr(self._session, 'close'):
            self._session.close()
    
    # =========================================================================
    # Authentication (backward compatible)
    # =========================================================================
    
    async def login(self) -> UserInfo:
        """
        Login to MEGA (backward compatible method).
        
        Returns:
            UserInfo with account details
        """
        return await self._do_login()
    
    async def logout(self):
        """Logout from MEGA (backward compatible)."""
        await self.log_out()
    
    @property
    def is_logged_in(self) -> bool:
        """Check if logged in."""
        return self._auth_result is not None or self._master_key is not None
    
    @property
    def session_file(self) -> Optional[Path]:
        """Get session file path if using SQLite session."""
        if isinstance(self._session, SQLiteSession):
            return self._session.path
        return None
    
    async def get_account_info(self) -> AccountInfo:
        """
        Get account storage and bandwidth information.
        
        Queries MEGA API for current account status including:
        - Storage used and total
        - Download bandwidth used and limits
        - Account type
        
        Returns:
            AccountInfo with storage and bandwidth details
            
        Example:
            >>> info = await mega.get_account_info()
            >>> print(f"Free space: {info.space_free_gb:.2f} GB")
            >>> if info.has_space_for(file_size):
            ...     await mega.upload(file)
        """
        self._ensure_logged_in()
        
        # Request account quota info
        # a=uq: user quota, strg=1: storage info, xfer=1: transfer info, pro=1: pro status
        response = await self._api.request({
            'a': 'uq',
            'strg': 1,
            'xfer': 1,
            'pro': 1
        })
        
        # Default bandwidth for pro accounts (10 PB)
        default_bandwidth = (1024 ** 5) * 10
        
        return AccountInfo(
            account_type=response.get('utype', 0),
            space_used=response.get('cstrg', 0),
            space_total=response.get('mstrg', 0),
            download_bandwidth_used=response.get('caxfer', 0),
            download_bandwidth_total=response.get('mxfer', default_bandwidth),
            shared_bandwidth_used=response.get('csxfer', 0),
            shared_bandwidth_limit=response.get('srvratio', 0)
        )
    
    # =========================================================================
    # Properties (Clean API)
    # =========================================================================
    
    @property
    def root(self) -> Optional[Node]:
        """Root node (call load() first)."""
        return self._node_service.root if self._node_service else None
    
    async def load_codecs(self, force: bool = False) -> dict:
        """
        Load media codec list from MEGA API (cached in session).
        
        Args:
            force: Force reload from API even if cached
            
        Returns:
            Dict with container, video, audio codec mappings
        """
        # Check memory cache first
        if MegaClient._codecs_cache and not force:
            return MegaClient._codecs_cache
        
        # Check session cache (SQLite)
        if not force and hasattr(self._session, 'get_cache'):
            cached = self._session.get_cache('codecs')
            if cached:
                MegaClient._codecs_cache = cached
                self._apply_codecs(cached)
                return cached
        
        self._ensure_logged_in()
        
        codecs = await self._api.get_media_codecs()
        
        if codecs:
            MegaClient._codecs_cache = codecs
            self._apply_codecs(codecs)
            
            # Save to session cache
            if hasattr(self._session, 'set_cache'):
                self._session.set_cache('codecs', codecs)
        
        return codecs
    
    def _apply_codecs(self, codecs: dict) -> None:
        """Apply codec mappings to global maps."""
        from .core.attributes.media import (
            CONTAINER_MAP, VIDEO_CODEC_MAP, AUDIO_CODEC_MAP, SHORTFORMAT_MAP
        )
        CONTAINER_MAP.update(codecs.get('container', {}))
        VIDEO_CODEC_MAP.update(codecs.get('video', {}))
        AUDIO_CODEC_MAP.update(codecs.get('audio', {}))
        SHORTFORMAT_MAP.update(codecs.get('shortformat', {}))
    
    @property
    def files(self) -> List[Node]:
        """All files (call load() first)."""
        return self._node_service.all_files() if self._node_service else []
    
    @property
    def folders(self) -> List[Node]:
        """All folders (call load() first)."""
        return self._node_service.all_folders() if self._node_service else []
    
    # =========================================================================
    # Core Operations
    # =========================================================================
    
    async def load(self, refresh: bool = False) -> Node:
        """Load nodes from server. Returns root node."""
        self._ensure_logged_in()
        
        if refresh or self._node_service is None:
            await self._load_nodes()
        
        return self._node_service.root
    
    async def get_root(self, refresh: bool = False) -> Node:
        """Get root node (Cloud Drive)."""
        return await self.load(refresh)
    
    async def get(self, path: str, refresh: bool = False) -> Optional[Node]:
        """Get node by path (e.g., '/Documents/file.pdf')."""
        self._ensure_logged_in()
        
        if refresh or self._node_service is None:
            await self._load_nodes()
        
        return self._node_service.find_by_path(path)
    
    async def find(self, name: str) -> Optional[Node]:
        """Find first node matching name."""
        self._ensure_logged_in()
        
        if self._node_service is None:
            await self._load_nodes()
        
        return self._node_service.find_by_name(name)
    
    # =========================================================================
    # Backward Compatibility
    # =========================================================================
    
    async def list_files(self, folder: Optional[str] = None, refresh: bool = False) -> List[Node]:
        """List files in folder (backward compat)."""
        self._ensure_logged_in()
        
        if refresh or self._node_service is None:
            await self._load_nodes()
        
        if folder:
            node = self._node_service.get(folder)
            return node.files if node else []
        
        return self._node_service.root.files if self._node_service.root else []
    
    async def get_all_files(self, refresh: bool = False) -> List[Node]:
        """Get all files flat (backward compat)."""
        await self.load(refresh)
        return list(self._node_service.nodes.values())
    
    async def cd(self, path: str) -> Node:
        """Change current directory."""
        self._ensure_logged_in()
        
        if self._node_service is None:
            await self._load_nodes()
        
        root = self._node_service.root
        if self._current_node is None:
            self._current_node = root
        
        if path == "/":
            self._current_node = root
        elif path.startswith("/"):
            node = self._node_service.find_by_path(path)
            if node is None:
                raise FileNotFoundError(f"Path not found: {path}")
            self._current_node = node
        else:
            # Relative path
            node = self._current_node.find(path)
            if node is None:
                raise FileNotFoundError(f"Path not found: {path}")
            self._current_node = node
        
        return self._current_node
    
    def pwd(self) -> str:
        """Get current working directory path."""
        return self._current_node.path if self._current_node else "/"
    
    async def ls(self, path: Optional[str] = None) -> List[Node]:
        """List directory contents."""
        await self.load()
        
        if path:
            node = await self.get(path)
        else:
            node = self._current_node or self._node_service.root
        
        if node is None:
            raise FileNotFoundError(f"Path not found: {path}")
        
        return list(node.children)
    
    def get_node(self, handle: str) -> Optional[Node]:
        """Get node by handle."""
        return self._node_service.get(handle) if self._node_service else None
    
    # =========================================================================
    # Upload
    # =========================================================================
    
    async def upload(
        self,
        file_path: Union[str, Path],
        dest_folder: Optional[str] = None,
        name: Optional[str] = None,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None,
        mega_id: Optional[str] = None,
        label: int = 0,
        auto_thumb: bool = True,
        thumbnail: Optional[Union[str, Path, bytes]] = None,
        preview: Optional[Union[str, Path, bytes]] = None,
        **extra_attrs
    ) -> MegaFile:
        """
        Upload a file to MEGA.
        
        Args:
            file_path: Local file path
            dest_folder: Destination folder handle. None for root.
            name: Optional custom name for the file
            progress_callback: Optional callback for progress updates
            mega_id: ID linking to MongoDB (stored as 'm' attribute, flat)
            label: Color label (0-7: none, red, orange, yellow, green, blue, purple, grey)
            auto_thumb: Auto-generate thumbnail/preview for images/videos
            thumbnail: Custom thumbnail (path or bytes). Overrides auto_thumb.
            preview: Custom preview (path or bytes). Overrides auto_thumb.
            **extra_attrs: Additional custom attributes (flat, single-char keys)
            
        Returns:
            MegaFile representing the uploaded file
            
        Example:
            # Simple upload
            await mega.upload("file.txt")
            
            # With mega_id (links to MongoDB)
            await mega.upload("doc.pdf", mega_id="abc123")
            
            # With extra attributes
            await mega.upload("doc.pdf", mega_id="abc123", t="invoice")
            
            # Image with auto thumbnail
            await mega.upload("photo.jpg")  # auto-generates thumb & preview
            
            # Custom thumbnail
            await mega.upload("video.mp4", thumbnail="custom_thumb.jpg")
        """
        self._ensure_logged_in()
        
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if self._node_service is None:
            await self._load_nodes()
        
        target_id = dest_folder or self._node_service.root_handle
        
        # Build file attributes (flat, with mega_id as 'm')
        attrs = FileAttributes(
            name=name or path.name,
            label=label,
            mega_id=mega_id
        )
        
        # Add extra attributes (flat)
        for key, value in extra_attrs.items():
            attrs.set(key, value)
        
        # Handle thumbnail/preview - custom or auto-generated
        thumb_data = None
        preview_data = None
        media_info = None
        
        # Load and resize custom thumbnail if provided
        if thumbnail is not None:
            try:
                from .core.attributes import ThumbnailService
                thumb_gen = ThumbnailService()
                # Convert to Path if string
                thumb_source = Path(thumbnail) if isinstance(thumbnail, str) else thumbnail
                thumb_data = thumb_gen.generate(thumb_source)
            except Exception as e:
                self._logger.warning(f"Failed to generate custom thumbnail: {e}")
        
        # Load and resize custom preview if provided
        if preview is not None:
            try:
                from .core.attributes import PreviewService
                preview_gen = PreviewService()
                # Convert to Path if string
                preview_source = Path(preview) if isinstance(preview, str) else preview
                preview_data = preview_gen.generate(preview_source)
            except Exception as e:
                self._logger.warning(f"Failed to generate custom preview: {e}")
        
        # Auto-generate thumbnails if not provided and auto_thumb is True
        if auto_thumb and (thumb_data is None or preview_data is None):
            from .core.attributes import MediaProcessor
            processor = MediaProcessor()
            if processor.is_media(path):
                self._logger.info("Generating thumbnail and preview for media file")
                result = await processor.process(path)
                if thumb_data is None:
                    thumb_data = result.thumbnail
                    if thumb_data:
                        self._logger.debug("Thumbnail generated successfully")
                if preview_data is None:
                    preview_data = result.preview
                    if preview_data:
                        self._logger.debug("Preview generated successfully")
        
        # Always extract media attributes for videos (independent of auto_thumb)
        try:
            from .core.attributes import MediaProcessor
            processor = MediaProcessor()
            if processor.is_video(path):
                self._logger.info("Extracting media metadata for video file")
                media_info = processor.extract_metadata(path)
                if media_info:
                    self._logger.debug("Media metadata extracted successfully")
        except Exception as e:
            self._logger.debug(f"Could not extract media metadata: {e}")
        
        coordinator = UploadCoordinator(
            api_client=self._api,
            master_key=self._master_key,
            progress_callback=progress_callback
        )
        
        config = UploadConfig(
            file_path=path,
            target_folder_id=target_id,
            attributes=attrs,
            thumbnail=thumb_data,
            preview=preview_data,
            media_info=media_info
        )
        
        result = await coordinator.upload(config)
        
        node = Node(
            handle=result.node_handle,
            name=name or path.name,
            size=result.file_size,
            is_folder=False,
            parent_handle=target_id,
            key=result.file_key,
            _client=self
        )
        
        # Add to node service tree and update parent-child relationships
        if self._node_service:
            self._node_service.add_node(node)
        
        file_size_mb = result.file_size / (1024 * 1024)
        self._logger.info(f"Upload finished successfully: {path.name} -> {result.node_handle} ({file_size_mb:.2f} MB)")
        
        return node
    
    async def update(
        self,
        file: Union[str, MegaFile],
        new_content: Union[str, Path],
        name: Optional[str] = None,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None,
        auto_thumb: bool = True,
        thumbnail: Optional[Union[str, Path, bytes]] = None,
        preview: Optional[Union[str, Path, bytes]] = None
    ) -> MegaFile:
        """
        Update an existing file with new content, creating a new version.
        
        MEGA's file versioning keeps the old file as a previous version,
        accessible through the version history. This matches the behavior
        of the official MEGA web client.
        
        Args:
            file: Existing file to update (handle, path, or MegaFile object)
            new_content: Path to local file with new content
            name: Optional new name for the file (defaults to keeping original name)
            progress_callback: Optional callback for progress updates
            auto_thumb: Auto-generate thumbnail/preview for images/videos
            thumbnail: Custom thumbnail (path or bytes)
            preview: Custom preview (path or bytes)
            
        Returns:
            MegaFile representing the new version
            
        Raises:
            FileNotFoundError: If the file to update or new content doesn't exist
            ValueError: If the target is a folder
            
        Example:
            # Update a file by path
            new_version = await mega.update("/Documents/report.pdf", "report_v2.pdf")
            
            # Update a file by handle
            new_version = await mega.update(old_file.handle, "updated_data.txt")
            
            # Update with new name
            new_version = await mega.update(old_file, "new_data.csv", name="data_2024.csv")
            
            # Get version history (the old version is preserved)
            versions = await mega.get_versions(new_version)
        """
        self._ensure_logged_in()
        
        # Resolve the existing file
        existing_file = await self._resolve_file(file)
        if not existing_file:
            raise FileNotFoundError(f"File not found: {file}")
        
        if existing_file.is_folder:
            raise ValueError("Cannot update a folder, only files support versioning")
        
        # Get the parent folder of the existing file
        parent_handle = existing_file.parent_handle
        if not parent_handle:
            # If no parent, use root
            await self.load()
            parent_handle = self._node_service.root.handle
        
        # Upload the new content as a replacement
        new_path = Path(new_content)
        if not new_path.exists():
            raise FileNotFoundError(f"New content file not found: {new_content}")
        
        # Use original name if not specified
        file_name = name or existing_file.name
        
        # Build attributes
        attrs = FileAttributes(name=file_name)
        
        # Process thumbnails (same logic as upload)
        thumb_data = None
        preview_data = None
        media_info = None
        
        if thumbnail is not None:
            try:
                from .core.attributes import ThumbnailService
                thumb_gen = ThumbnailService()
                thumb_source = Path(thumbnail) if isinstance(thumbnail, str) else thumbnail
                thumb_data = thumb_gen.generate(thumb_source)
            except Exception as e:
                self._logger.warning(f"Failed to generate custom thumbnail: {e}")
        
        if preview is not None:
            try:
                from .core.attributes import PreviewService
                preview_gen = PreviewService()
                preview_source = Path(preview) if isinstance(preview, str) else preview
                preview_data = preview_gen.generate(preview_source)
            except Exception as e:
                self._logger.warning(f"Failed to generate custom preview: {e}")
        
        if auto_thumb and (thumb_data is None or preview_data is None):
            try:
                from .core.attributes import MediaProcessor
                processor = MediaProcessor()
                if processor.is_media(new_path):
                    result = processor.process(new_path)
                    if thumb_data is None:
                        thumb_data = result.thumbnail
                    if preview_data is None:
                        preview_data = result.preview
            except Exception:
                pass
        
        # Extract media info for videos
        try:
            from .core.attributes import MediaProcessor
            processor = MediaProcessor()
            if processor.is_video(new_path):
                media_info = processor.extract_metadata(new_path)
        except Exception:
            pass
        
        # Create upload coordinator with replace_handle
        coordinator = UploadCoordinator(
            api_client=self._api,
            master_key=self._master_key,
            progress_callback=progress_callback
        )
        
        config = UploadConfig(
            file_path=new_path,
            target_folder_id=parent_handle,
            attributes=attrs,
            thumbnail=thumb_data,
            preview=preview_data,
            media_info=media_info,
            replace_handle=existing_file.handle  # Key: tells MEGA to create version
        )
        
        result = await coordinator.upload(config)
        
        node = Node(
            handle=result.node_handle,
            name=file_name,
            size=result.file_size,
            is_folder=False,
            parent_handle=parent_handle,
            key=result.file_key,
            _client=self
        )
        
        # Update node service cache
        if self._node_service:
            self._node_service.nodes[result.node_handle] = node
        
        self._logger.info(f"File updated: {existing_file.handle} -> {result.node_handle}")
        
        return node
    
    # =========================================================================
    # Download
    # =========================================================================
    
    async def download(
        self,
        file: Union[str, MegaFile],
        dest_path: Union[str, Path] = ".",
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        """
        Download a file from MEGA.
        
        Args:
            file: File handle, name, or MegaFile object
            dest_path: Local destination path or directory
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
            
        Returns:
            Path to downloaded file
        """
        self._ensure_logged_in()
        
        mega_file = await self._resolve_file(file)
        if not mega_file:
            raise FileNotFoundError(f"File not found: {file}")
        
        if mega_file.is_folder:
            raise ValueError("Cannot download a folder")
        
        result = await self._api.request({
            'a': 'g',
            'g': 1,
            'n': mega_file.handle
        })
        
        download_url = result.get('g')
        if not download_url:
            raise ValueError("Could not get download URL")
        
        file_size = result.get('s', 0)
        
        dest = Path(dest_path)
        if dest.is_dir():
            dest = dest / mega_file.name
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                response.raise_for_status()
                
                downloaded = 0
                with open(dest, 'wb') as f:
                    async for chunk in response.content.iter_chunked(131072):
                        if mega_file.key:
                            chunk = self._decrypt_chunk(chunk, mega_file.key, downloaded)
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback:
                            progress_callback(downloaded, file_size)
        
        return dest
    
    def _decrypt_chunk(self, data: bytes, key: bytes, position: int) -> bytes:
        """
        Decrypt a file chunk using AES-CTR.
        
        Uses MegaDecrypt class for consistent decryption logic.
        
        MEGA uses AES-CTR mode for file encryption. The key format is:
        - key[:16]: AES key (16 bytes)
        - key[16:24]: Nonce/IV (8 bytes)
        - key[24:32]: MAC (8 bytes, optional, not used for chunk decryption)
        
        Args:
            data: Encrypted data chunk to decrypt
            key: Decryption key (24 or 32 bytes)
            position: Byte position in the file (for CTR counter calculation)
            
        Returns:
            Decrypted data
        """
        from .core.crypto.file import MegaDecrypt
        
        # Use MegaDecrypt with position option to handle counter correctly
        decryptor = MegaDecrypt(key, options={'position': position})
        # Decrypt without MAC verification (we're just decrypting a chunk)
        return decryptor.decrypt(data, position=position)
    
    async def get_download_url(self, node: 'MegaFile') -> tuple[str, int]:
        """
        Get download URL and file size for a node.
        
        Args:
            node: Node to get download URL for
            
        Returns:
            Tuple of (download_url, file_size)
        """
        self._ensure_logged_in()
        
        result = await self._api.request({
            'a': 'g',
            'g': 1,
            'n': node.handle
        })
        
        download_url = result.get('g')
        if not download_url:
            raise ValueError("Could not get download URL")
        
        file_size = result.get('s', node.size if hasattr(node, 'size') else 0)
        return download_url, file_size
    
    async def read_file_range(
        self, 
        node: 'MegaFile', 
        offset: int, 
        size: int
    ) -> bytes:
        """
        Read a range of bytes from a file without downloading the entire file.
        
        Args:
            node: Node to read from
            offset: Starting byte offset
            size: Number of bytes to read
            
        Returns:
            Decrypted bytes from the file
        """
        self._ensure_logged_in()
        
        if node.is_folder:
            raise ValueError("Cannot read from a folder")
        
        # Get download URL
        download_url, file_size = await self.get_download_url(node)
        
        if offset >= file_size or size <= 0:
            return b""
        
        actual_size = min(size, file_size - offset)
        
        # Download the range
        import aiohttp
        headers = {
            'Range': f'bytes={offset}-{offset + actual_size - 1}'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url, headers=headers) as response:
                response.raise_for_status()
                encrypted_data = await response.read()
        
        # Decrypt if node has a key
        # Note: MEGA files are encrypted, so we always need to decrypt
        if not node.key:
            raise ValueError(f"Node {node.handle} does not have a decryption key")
        
        # Decrypt the chunk starting from the offset
        # The position parameter in _decrypt_chunk is the byte offset in the decrypted file
        from megapy.core.nodes.decryptor import KeyDecryptor
        from megapy.core.crypto import unmerge_key_mac
        key = unmerge_key_mac(node.key)
        
        decrypted_data = self._decrypt_chunk(encrypted_data, key, offset)
        return decrypted_data
    
    async def _download_file_attribute(
        self,
        node: 'MegaNode',
        fa_handle: str,
        attr_type: int
    ) -> Optional[bytes]:
        """
        Download and decrypt a file attribute (thumbnail or preview).
        
        Based on MEGA webclient's api_getfileattr() in crypto.js.
        
        Args:
            node: MegaNode with the file key
            fa_handle: File attribute handle from 'fa' field (base64url, 8 bytes decoded)
            attr_type: 0=thumbnail, 1=preview
            
        Returns:
            Decrypted attribute bytes or None
        """
        from Crypto.Cipher import AES
        import aiohttp
        import struct
        
        if not node.key:
            return None
        
        encoder = Base64Encoder()
        
        # Decode handle from base64url to binary (8 bytes)
        handle_binary = encoder.decode(fa_handle)
        if len(handle_binary) != 8:
            return None
        
        # Request download URL for file attribute
        # fah = base64url encoded handle (first 8 bytes)
        try:
            result = await self._api.request({
                'a': 'ufa',
                'fah': fa_handle,  # base64url handle
                'ssl': 2,
                'r': 1
            })
        except Exception:
            return None
        
        # Get download URL
        download_url = result.get('p')
        if not download_url:
            return None
        
        # Download the encrypted data - POST binary handle to URL
        import ssl
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        ssl_ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(download_url, data=handle_binary) as resp:
                if resp.status != 200:
                    return None
                response = await resp.read()
        
        if not response or len(response) < 12:
            return None
        
        # Parse response format: [handle.8 data_length.4] data
        # First 8 bytes: handle (should match our request)
        # Next 4 bytes: data length (little endian)
        # Remaining bytes: encrypted data
        
        resp_handle = response[0:8]
        data_len = struct.unpack('<I', response[8:12])[0]
        
        # Verify handle matches
        if resp_handle != handle_binary:
            return None
        
        # Extract encrypted data
        encrypted = response[12:12 + data_len]
        if not encrypted:
            return None
        
        # Pad to 16-byte boundary for AES
        padded_len = (len(encrypted) + 15) // 16 * 16
        if len(encrypted) < padded_len:
            encrypted = encrypted + b'\x00' * (padded_len - len(encrypted))
        
        # Decrypt with file key
        # For 32-byte keys: XOR first 16 bytes with second 16 bytes
        # For 16-byte keys: use directly
        key = node.key
        if len(key) >= 32:
            k = bytes(a ^ b for a, b in zip(key[:16], key[16:32]))
        else:
            k = key[:16]
        
        # AES-CBC decrypt with zero IV
        cipher = AES.new(k, AES.MODE_CBC, iv=b'\x00' * 16)
        decrypted = cipher.decrypt(encrypted)
        
        # Find end of JPEG (FFD9) or remove padding
        if decrypted[:2] == b'\xff\xd8':  # JPEG
            end_marker = decrypted.rfind(b'\xff\xd9')
            if end_marker > 0:
                return decrypted[:end_marker + 2]
        
        # Remove null padding for non-JPEG data
        end = len(decrypted)
        while end > 0 and decrypted[end - 1] == 0:
            end -= 1
        
        return decrypted[:end] if end > 0 else decrypted
    
    # =========================================================================
    # File operations
    # =========================================================================
    
    async def delete(self, file: Union[str, MegaFile]) -> bool:
        """Delete a file or folder."""
        self._ensure_logged_in()
        
        mega_file = await self._resolve_file(file)
        if not mega_file:
            raise FileNotFoundError(f"File not found: {file}")
        
        await self._api.delete_node(mega_file.handle)
        if self._node_service:
            self._node_service.nodes.pop(mega_file.handle, None)
        
        return True
    
    async def rename(self, file: Union[str, MegaFile], new_name: str) -> MegaFile:
        """Rename a file or folder."""
        self._ensure_logged_in()
        
        mega_file = await self._resolve_file(file)
        if not mega_file:
            raise FileNotFoundError(f"File not found: {file}")
        
        encoder = Base64Encoder()
        attrs = {'n': new_name}
        attrs_json = f"MEGA{__import__('json').dumps(attrs)}"
        
        padding = 16 - (len(attrs_json) % 16)
        attrs_padded = attrs_json.encode() + (b'\x00' * padding)
        
        from Crypto.Cipher import AES
        if mega_file.key:
            cipher = AES.new(mega_file.key[:16], AES.MODE_CBC, iv=b'\x00' * 16)
            encrypted_attrs = encoder.encode(cipher.encrypt(attrs_padded))
        else:
            encrypted_attrs = encoder.encode(attrs_padded)
        
        await self._api.request({
            'a': 'a',
            'n': mega_file.handle,
            'attr': encrypted_attrs
        })
        
        mega_file.name = new_name
        return mega_file
    
    async def move(
        self,
        file: Union[str, MegaFile],
        dest_folder: Union[str, MegaFile]
    ) -> MegaFile:
        """Move a file to another folder."""
        self._ensure_logged_in()
        
        mega_file = await self._resolve_file(file)
        if not mega_file:
            raise FileNotFoundError(f"File not found: {file}")
        
        dest = await self._resolve_file(dest_folder)
        if not dest:
            raise FileNotFoundError(f"Folder not found: {dest_folder}")
        
        if not dest.is_folder:
            raise ValueError("Destination must be a folder")
        
        await self._api.move_node(mega_file.handle, dest.handle)
        mega_file.parent_handle = dest.handle
        
        return mega_file
    
    async def create_folder(
        self,
        name: str,
        parent: Optional[Union[str, MegaFile]] = None
    ) -> Node:
        """
        Create a new folder, or return existing folder if it already exists.
        
        Args:
            name: Folder name
            parent: Parent folder (handle, path, or Node). None for root.
            
        Returns:
            Node representing the folder (existing or newly created)
        """
        self._ensure_logged_in()
        
        if self._node_service is None:
            await self._load_nodes()
        
        # Resolve parent node
        parent_node = None
        parent_id = self._node_service.root_handle
        if parent:
            parent_node = await self._resolve_file(parent)
            if parent_node:
                parent_id = parent_node.handle
        else:
            parent_node = self._node_service.root
        
        # Check if folder already exists in parent
        if parent_node:
            existing_folder = parent_node.get(name)
            if existing_folder and existing_folder.is_folder:
                # Folder already exists, return it
                return existing_folder
        
        # Folder doesn't exist, create it
        import os
        import json
        from Crypto.Cipher import AES
        
        folder_key = os.urandom(16)
        
        attrs = {'n': name}
        attrs_json = f"MEGA{json.dumps(attrs)}"
        padding = 16 - (len(attrs_json) % 16)
        attrs_padded = attrs_json.encode() + (b'\x00' * padding)
        
        cipher = AES.new(folder_key, AES.MODE_CBC, iv=b'\x00' * 16)
        encrypted_attrs = Base64Encoder().encode(cipher.encrypt(attrs_padded))
        
        master_cipher = AES.new(self._master_key, AES.MODE_ECB)
        encrypted_key = Base64Encoder().encode(master_cipher.encrypt(folder_key))
        
        result = await self._api.request({
            'a': 'p',
            't': parent_id,
            'n': [{
                'h': 'xxxxxxxx',
                't': 1,
                'a': encrypted_attrs,
                'k': encrypted_key
            }]
        })
        
        if 'f' in result and len(result['f']) > 0:
            data = result['f'][0]
            node = Node(
                handle=data['h'],
                name=name,
                is_folder=True,
                parent_handle=parent_id,
                _client=self
            )
            if self._node_service:
                # Add node to tree and update parent-child relationships
                self._node_service.add_node(node)
            return node
        
        raise ValueError("Failed to create folder")
    
    async def import_link(
        self,
        source_node: Union[str, MegaFile, Node],
        target_folder: Union[str, MegaFile, Node],
        clear_attributes: bool = True
    ) -> List[Node]:
        """
        Import a folder or file from public link to target folder.
        
        This creates a copy of the source node (folder with all children, or single file)
        in the target location. Based on webclient's link import logic.
        
        Args:
            source_node: Source node to import (handle, path, or Node) - can be folder or file
            target_folder: Target folder where to import (handle, path, or Node)
            clear_attributes: If True, clear sensitive attributes (s4, lbl, fav, sen)
            
        Returns:
            List of imported Node objects
            
        Example:
            >>> # Import a folder
            >>> source = await mega.resolve_public_link("https://mega.nz/folder/...")
            >>> target = await mega.find("Backups")
            >>> imported = await mega.import_link(source, target)
            >>> 
            >>> # Import a single file
            >>> source_file = await mega.resolve_public_link("https://mega.nz/file/...")
            >>> imported = await mega.import_link(source_file, target)
        """
        self._ensure_logged_in()
        
        if self._node_service is None:
            await self._load_nodes()
        
        # Resolve source node (can be folder or file)
        source = await self._resolve_file(source_node)
        if not source:
            raise FileNotFoundError(f"Source node not found: {source_node}")
        
        # Resolve target folder
        target = await self._resolve_file(target_folder)
        if not target:
            raise FileNotFoundError(f"Target folder not found: {target_folder}")
        
        if not target.is_folder:
            raise ValueError(f"Target must be a folder, got: {target.handle}")
        
        from .core.nodes.folder_importer import FolderImporter
        
        importer = FolderImporter(
            master_key=self._master_key,
            api_client=self._api,
            node_service=self._node_service
        )
        
        # Execute import (supports both folders and files)
        handles = await importer.import_link(
            source_node=source,
            target_folder_handle=target.handle,
            clear_attributes=clear_attributes
        )
        
        # Return empty list for now (handles are returned but we'd need to fetch nodes)
        # TODO: Fetch and return actual Node objects from handles
        return []
    
    async def import_folder(
        self,
        source_folder: Union[str, MegaFile],
        target_folder: Union[str, MegaFile],
        clear_attributes: bool = True
    ) -> List[Node]:
        """
        Import a folder with all its children to target folder.
        
        DEPRECATED: Use import_link() instead. This method is kept for backward compatibility.
        
        Args:
            source_folder: Source folder to import (handle, path, or Node)
            target_folder: Target folder where to import (handle, path, or Node)
            clear_attributes: If True, clear sensitive attributes (s4, lbl, fav, sen)
            
        Returns:
            List of imported Node objects
        """
        source = await self._resolve_file(source_folder)
        if not source:
            raise FileNotFoundError(f"Source folder not found: {source_folder}")
        
        if not source.is_folder:
            raise ValueError(f"Source must be a folder, got: {source.handle}")
        
        return await self.import_link(source, target_folder, clear_attributes)
        
    
    async def init_register(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str
    ):
        """
        Initialize account registration (step 1 of 3).
        
        This creates a new account and sends a confirmation email.
        The user must confirm their email before the account is fully activated.
        
        Args:
            email: User email address
            password: User password
            first_name: User's first name
            last_name: User's last name
            
        Returns:
            RegistrationResult with success status and message
            
        Example:
            >>> async with MegaClient() as mega:
            ...     result = await mega.init_register(
            ...         email="user@example.com",
            ...         password="secure_password",
            ...         first_name="John",
            ...         last_name="Doe"
            ...     )
            ...     if result.success:
            ...         print("Check your email for confirmation")
        """
        import os
        from .core.api.registration import StandardAccountRegistration, RegistrationData
        
        # Initialize API client if not already done
        if self._api is None:
            self._api = AsyncAPIClient(self._config)
            await self._api.__aenter__()
        
        # Create registration handler
        registration = StandardAccountRegistration(self._api)
        
        # Prepare registration data
        data = RegistrationData(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Execute registration
        result = await registration.init_register(data)
        
        # Store registration data for later steps
        if result.success and data.master_key and data.client_random_value:
            self._registration_master_key = data.master_key
            self._registration_client_random_value = data.client_random_value
            self._registration_password = password
        
        return result
    
    async def register(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str
    ):
        """
        Register a new MEGA account (alias for init_register for backward compatibility).
        
        This creates a new account and sends a confirmation email.
        The user must confirm their email before the account is fully activated.
        
        Args:
            email: User email address
            password: User password
            first_name: User's first name
            last_name: User's last name
            
        Returns:
            RegistrationResult with success status and message
            
        Example:
            >>> async with MegaClient() as mega:
            ...     result = await mega.register(
            ...         email="user@example.com",
            ...         password="secure_password",
            ...         first_name="John",
            ...         last_name="Doe"
            ...     )
            ...     if result.success:
            ...         print("Check your email for confirmation")
        """
        return await self.init_register(email, password, first_name, last_name)
    
    async def confirm_code(self, confirm_code: str):
        """
        Confirm email with confirmation code (step 2 of 3).
        
        After calling init_register, the user receives an email with a confirmation code.
        This method confirms the email address using that code.
        
        Args:
            confirm_code: Confirmation code from email (base64url encoded, typically from URL hash)
            
        Returns:
            ConfirmCodeResult with email, name, and user handle
            
        Example:
            >>> async with MegaClient() as mega:
            ...     result = await mega.init_register(...)
            ...     # User receives email and clicks confirmation link
            ...     confirm_result = await mega.confirm_code("ConfirmCodeV2...")
            ...     if confirm_result.success:
            ...         print(f"Email {confirm_result.email} confirmed")
        """
        from .core.api.registration import StandardAccountRegistration
        
        # Initialize API client if not already done
        if self._api is None:
            self._api = AsyncAPIClient(self._config)
            await self._api.__aenter__()
        
        # Create registration handler
        registration = StandardAccountRegistration(self._api)
        
        # Execute confirmation
        return await registration.confirm_code(confirm_code)
    
    async def finalize_registration(self, confirm_code: str):
        """
        Finalize registration by completing verification and generating RSA keys (step 3 of 3).
        
        After confirming the email, this method completes the registration by:
        1. Completing email verification
        2. Generating RSA key pair
        3. Uploading the keys to the server
        
        Args:
            confirm_code: Confirmation code from email (same as used in confirm_code)
            
        Returns:
            FinalizeResult with success status
            
        Example:
            >>> async with MegaClient() as mega:
            ...     # Step 1: Initialize registration
            ...     result = await mega.init_register(...)
            ...     
            ...     # Step 2: Confirm email
            ...     confirm_result = await mega.confirm_code("ConfirmCodeV2...")
            ...     
            ...     # Step 3: Finalize registration
            ...     finalize_result = await mega.finalize_registration("ConfirmCodeV2...")
            ...     if finalize_result.success:
            ...         print("Account fully activated!")
        """
        from .core.api.registration import StandardAccountRegistration
        
        # Check if we have the necessary registration data
        if not self._registration_master_key:
            raise RuntimeError(
                "No registration data found. Call init_register first."
            )
        if not self._registration_password:
            raise RuntimeError(
                "No registration password found. Call init_register first."
            )
        if not self._registration_client_random_value:
            raise RuntimeError(
                "No client random value found. Call init_register first."
            )
        
        # Initialize API client if not already done
        if self._api is None:
            self._api = AsyncAPIClient(self._config)
            await self._api.__aenter__()
        
        # Create registration handler
        registration = StandardAccountRegistration(self._api)
        
        # Execute finalization
        result = await registration.finalize_registration(
            password=self._registration_password,
            confirm_code=confirm_code,
            master_key=self._registration_master_key,
            client_random_value=self._registration_client_random_value
        )
        
        # Clear registration data after finalization
        if result.success:
            self._registration_master_key = None
            self._registration_client_random_value = None
            self._registration_password = None
        
        return result
    
    # =========================================================================
    # Private helpers
    # =========================================================================
    
    def _ensure_logged_in(self):
        """Ensure user is logged in."""
        if not self._master_key:
            raise RuntimeError("Not logged in. Call start() or use 'async with' first.")
    
    async def _load_nodes(self):
        """Load all nodes from server using NodeService."""
        response = await self._api.get_files()
        self._node_service = NodeService(self._master_key, self)
        self._node_service.load(response)
    
    async def _resolve_file(self, file: Union[str, Node]) -> Optional[Node]:
        """Resolve file argument to Node."""
        if isinstance(file, Node):
            return file
        
        # Check if it's a MEGA URL (folder or file)
        if isinstance(file, str) and file.startswith('https://mega.nz/'):
            return await self._resolve_url(file)
        
        if self._node_service is None:
            await self._load_nodes()
        
        node = self._node_service.get(file)
        if node:
            return node
        
        return await self.find(file)
    
    async def _resolve_url(self, url: str) -> Optional[Node]:
        """
        Resolve a MEGA URL to a Node.
        
        Supports:
        - Folder URLs: https://mega.nz/folder/HANDLE#KEY
        - File URLs: https://mega.nz/file/HANDLE#KEY
        
        Returns:
            Node object for the folder/file, or None if not found
        """
        import re
        import base64
        import binascii
        from urllib.parse import urlparse
        
        logger.debug(f"Resolving MEGA URL: {url}")
        
        # Parse URL
        parsed = urlparse(url)
        path = parsed.path
        fragment = parsed.fragment
        
        if not fragment:
            logger.error(f"Missing key in MEGA URL: {url}")
            raise ValueError(f"Missing key in MEGA URL: {url}")
        
        # Extract handle and type from path
        folder_match = re.search(r'/folder/([^#/?]+)', path)
        file_match = re.search(r'/file/([^#/?]+)', path)
        
        if folder_match:
            handle = folder_match.group(1)
            is_folder = True
            logger.debug(f"Detected folder URL, handle: {handle}")
        elif file_match:
            handle = file_match.group(1)
            is_folder = False
            logger.debug(f"Detected file URL, handle: {handle}")
        else:
            logger.error(f"Invalid MEGA URL format: {url}")
            raise ValueError(f"Invalid MEGA URL format: {url}")
        
        # Decode key from fragment
        key_str = fragment
        # Pad key if needed for base64 decoding
        padding = len(key_str) % 4
        if padding:
            key_str += '=' * (4 - padding)
            logger.debug(f"Padded key string for base64 decoding (padding: {4 - padding})")
        
        try:
            key_bytes = base64.urlsafe_b64decode(key_str)
            logger.debug(f"Successfully decoded key from URL fragment (key length: {len(key_bytes)} bytes)")
        except (binascii.Error, ValueError) as e:
            logger.error(f"Failed to decode key from MEGA URL: {url}, error: {e}")
            raise ValueError(f"Invalid key in MEGA URL: {url}")
        
        # For folders, we need to fetch the folder info
        if is_folder:
            print("its folder")
            logger.info(f"Resolving folder URL, handle: {handle}")
            from .node import Node
            folder_node = Node(
                handle=handle,
                name=f"Folder-{handle}",  # Temporary name
                size=0,
                is_folder=True,
                parent_handle=None,
                key=key_bytes,  # This is the share key from URL
                _client=self,
                _raw={
                    'h': handle,
                    't': 1,  # Folder type
                    'a': None,  # Attributes will be loaded during import
                    'k': None  # Key will be handled during import
                }
            )
            
            # Store the URL in _raw for later use during import
            folder_node._raw['_public_url'] = url
            
            logger.debug(f"Requesting folder info from API for handle: {handle}")
            result = await self._api.request({
                'a': 'f',
                'c': 1,
                'r': 1,
                'ca': 1
            }, querystring={'n': handle})

            if isinstance(result, list):
                nodes = result[0]["f"]
            else:
                nodes = result["f"]
            
            logger.debug(f"Received {len(nodes)} nodes from API response")
            
            print(nodes)
            node_data = nodes[0]
                
            logger.debug(f"Found matching folder node, updating with real data")
            # Update with real data
            folder_node._raw = node_data
            folder_node.handle = node_data["h"]
            # Try to decrypt name
            from .core.attributes.packer import AttributesPacker
            from .core.crypto import Base64Encoder
            from .core.nodes.key import KeyFileManager
            encoder = Base64Encoder()
            
            if node_data.get('a') and key_bytes:
                manager = KeyFileManager.parse_key(node_data["k"], key_bytes)
                attrs = manager.decrypt_attributes(encoder.decode(node_data['a']))
                folder_node.attributes = attrs
                if attrs:
                    folder_node.name = attrs.name
                    logger.debug(f"Successfully decrypted folder name: {folder_node.name}")
                else:
                    raise ValueError(f"Failed to decrypt folder attributes for handle: {handle}")

            logger.debug(f"Loading children nodes for folder: {folder_node.name}")

            
            self._load_children_from_api_result(folder_node, nodes, key_bytes)
            logger.info(f"Successfully resolved folder URL: {folder_node.name} ({handle})")
            return folder_node
        
        # For files, we can create a Node directly
        else:
            print("its file")
            logger.info(f"Resolving file URL, handle: {handle}")
            logger.debug(f"Requesting file info from API for handle: {handle}")
            result = await self._api.request({
                'a': 'g',
                'p': handle
            })
            
            logger.debug(f"Received file info from API: size={result.get('s', 0)}")
            
            from .node import Node
            file_node = Node(
                handle=handle,
                name=handle,  # Will be decrypted from attributes if available
                size=result.get('s', 0),
                is_folder=False,
                parent_handle=None,
                key=key_bytes,
                _client=self,
                _raw=result
            )
            
            from .core.attributes.packer import AttributesPacker
            from .core.crypto import Base64Encoder
            from .core.nodes.key import KeyFileManager
            encoder = Base64Encoder()
            node_data = result
            
            # Try to decrypt attributes
            if node_data.get('a') and key_bytes:
                try:
                    # For files, the key in the URL is the encrypted key, need to decrypt it first
                    # The key_bytes from URL is the master key for the file link
                    # We need to parse the key from the API response
                    if node_data.get('k'):
                        # Parse the key from API response format: "user:encrypted_key"
                        manager = KeyFileManager.parse_key(node_data['k'], key_bytes)
                    else:
                        # If no 'k' in response, use key_bytes directly as file key
                        # For file links, key_bytes might be the file key itself
                        manager = KeyFileManager.from_full_key(key_bytes, self._master_key)
                    
                    attrs = manager.decrypt_attributes(encoder.decode(node_data['a']))
                    file_node.key = manager.full_key
                    file_node.attributes = attrs
                    if attrs:
                        file_node.name = attrs.name if hasattr(attrs, 'name') else attrs.to_dict().get('n', handle)
                        logger.debug(f"Successfully decrypted file name: {file_node.name}")
                except Exception as e:
                    logger.warning(f"Failed to decrypt file attributes: {e}, keeping default name")
                    # Keep default name if decryption fails
            logger.info(f"Successfully resolved file URL: {file_node.name} ({handle}), size: {file_node.size}")
            return file_node

        return None
    
    def _load_children_from_api_result(self, folder_node: 'Node', all_nodes: List[Dict[str, Any]], parent_key: bytes):
        """Load children nodes from API result recursively."""
        from .node import Node
        from .core.attributes.packer import AttributesPacker
        from .core.crypto import Base64Encoder
        encoder = Base64Encoder()
        
        logger.debug(f"Loading children for folder: {folder_node.name} (handle: {folder_node.handle}), total nodes in result: {len(all_nodes)}")
        print(all_nodes)
        def process_children(parent_node: 'Node', parent_key: bytes, depth: int = 0):
            """Recursively process children nodes."""
            indent = "  " * depth
            children_count = 0
            print(parent_node)
            for child_data in all_nodes:
                if child_data.get('p') == parent_node.handle:
                    children_count += 1
                    child_handle = child_data.get('h', '')
                    is_child_folder = (child_data.get('t', 0) == 1)
                    logger.debug(f"{indent}Processing child: handle={child_handle}, type={'folder' if is_child_folder else 'file'}")
                    
                    manager = KeyFileManager.parse_key(child_data.get('k'), parent_key)
                    attributes = manager.decrypt_attributes(
                        encoder.decode(child_data.get('a', ''))
                    )
                    # Create child node
                    child_node = Node(
                        handle=child_handle,
                        name=attributes.name,
                        attributes=attributes,
                        size=child_data.get('s', 0),
                        is_folder=is_child_folder,
                        parent_handle=parent_node.handle,
                        key=manager.full_key,
                        _client=self,
                        _raw=child_data
                    )
                    
                    # Set parent relationship
                    child_node.parent = parent_node
                    # Add to parent's children (not folder_node!)
                    parent_node.children.append(child_node)
                    
                    # If it's a folder, recursively process its children
                    # Always use parent_key (master_key) for all children, not the child's key
                    if child_node.is_folder:
                        process_children(child_node, parent_key, depth + 1)
            
            if children_count > 0:
                logger.debug(f"{indent}Processed {children_count} children for parent: {parent_node.handle} ({parent_node.name})")
        print("procssing")
        process_children(folder_node, parent_key)
        logger.info(f"Finished loading children for folder: {folder_node.name}, total children: {len(folder_node.children)}")
    
    def _decrypt_child_key(self, child_data: Dict[str, Any], parent_key: bytes) -> bytes:
        """Decrypt a child node's key using parent folder key."""
        from .core.crypto.aes.aes_crypto import AESCrypto
        
        child_handle = child_data.get('h', 'unknown')
        
        # Child key is encrypted with parent key
        encrypted_key = child_data.get('k', '')
        if not encrypted_key:
            logger.debug(f"No encrypted key found for child {child_handle}, using parent key as fallback")
            return parent_key  # Fallback to parent key
        
        # Parse key: "handle:encrypted_key"
        if ':' in encrypted_key:
            _, enc_key_part = encrypted_key.split(':', 1)
            logger.debug(f"Parsed encrypted key for child {child_handle} (format: handle:key)")
        else:
            enc_key_part = encrypted_key
            logger.debug(f"Using encrypted key directly for child {child_handle} (no handle prefix)")
        
        # Decode and decrypt
        try:
            from .core.crypto.utils.encoding import Base64Encoder
            encoder = Base64Encoder()
            enc_key_bytes = encoder.decode(enc_key_part)
            logger.debug(f"Decoded encrypted key bytes for child {child_handle} (length: {len(enc_key_bytes)} bytes)")
            logger.info(f"Decrypting child key for {child_handle} using parent key, key length: {len(parent_key)} bytes")

            if len(enc_key_bytes) <= 32:
                aes = AESCrypto(parent_key)
                decrypted_key = aes.decrypt_ecb(enc_key_bytes)
                logger.debug(f"Successfully decrypted child key for {child_handle}")
            else:
                raise ValueError("Encrypted key only can be decrypted with rsa key.")
 
            return decrypted_key
        except Exception as e:
            logger.warning(f"Failed to decrypt child key for {child_handle}: {e}, using parent key as fallback")
            return parent_key  # Fallback


def get_file_key(key):
    if len(key) >= 32:
        return bytes(a ^ b for a, b in zip(key[:16], key[16:32]))
    return key[:16]