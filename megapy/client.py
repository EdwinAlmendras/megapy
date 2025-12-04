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
        session: Union[str, SessionStorage],
        api_id: Optional[str] = None,  # Second arg = password for backward compat
        *,
        config: Optional[APIConfig] = None,
        base_path: Optional[Path] = None,
        auto_reconnect: bool = True
    ):
        """
        Initialize MEGA client.
        
        Args:
            session: Session name (creates .session file) OR email (if api_id provided)
            api_id: Password (for backward compatibility with email/password usage)
            config: Optional API configuration
            base_path: Base path for session files
            auto_reconnect: Whether to auto-reconnect on session resume
        """
        self._config = config or APIConfig.default()
        self._auto_reconnect = auto_reconnect
        self._logger = logging.getLogger('megapy.client')
        
        # Determine mode based on arguments
        if api_id is not None:
            # Backward compatible: MegaClient(email, password)
            self._email = session
            self._password = api_id
            self._session: SessionStorage = MemorySession()
            self._session_mode = False
        elif isinstance(session, str):
            # Session mode: MegaClient("session_name")
            self._email: Optional[str] = None
            self._password: Optional[str] = None
            self._session = SQLiteSession(session, base_path)
            self._session_mode = True
        else:
            # Custom session storage: MegaClient(custom_storage)
            self._email = None
            self._password = None
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
        
        # Try to resume existing session
        if self._session.exists():
            session_data = self._session.load()
            if session_data and session_data.is_valid():
                try:
                    await self._resume_session(session_data)
                    self._logger.info(f"Session resumed for {session_data.email}")
                    return self
                except Exception as e:
                    self._logger.warning(f"Failed to resume session: {e}")
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
            master_key=self._auth_result.master_key
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
                master_key=session_data.master_key
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
            await self.start()
        else:
            # Direct credentials mode
            self._api = AsyncAPIClient(self._config)
            await self._api.__aenter__()
            self._auth = AsyncAuthService(self._api)
            await self._do_login()
        
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
                result = await processor.process(path)
                if thumb_data is None:
                    thumb_data = result.thumbnail
                if preview_data is None:
                    preview_data = result.preview
        
        # Always extract media attributes for videos (independent of auto_thumb)
        try:
            from .core.attributes import MediaProcessor
            processor = MediaProcessor()
            if processor.is_video(path):
                media_info = processor.extract_metadata(path)
        except Exception:
            pass
        
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
        
        # Add to node service cache
        if self._node_service:
            self._node_service.nodes[result.node_handle] = node
        
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
        """Decrypt a file chunk using AES-CTR."""
        from Crypto.Cipher import AES
        from Crypto.Util import Counter
        
        aes_key = key[:16]
        iv = key[16:24]
        
        nonce = int.from_bytes(iv, 'big')
        block_num = position // 16
        ctr = Counter.new(128, initial_value=nonce + block_num)
        
        cipher = AES.new(aes_key, AES.MODE_CTR, counter=ctr)
        return cipher.decrypt(data)
    
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
        """Create a new folder."""
        self._ensure_logged_in()
        
        if self._node_service is None:
            await self._load_nodes()
        
        parent_id = self._node_service.root_handle
        if parent:
            parent_node = await self._resolve_file(parent)
            if parent_node:
                parent_id = parent_node.handle
        
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
                self._node_service.nodes[data['h']] = node
            return node
        
        raise ValueError("Failed to create folder")
    
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
        
        if self._node_service is None:
            await self._load_nodes()
        
        node = self._node_service.get(file)
        if node:
            return node
        
        return await self.find(file)
