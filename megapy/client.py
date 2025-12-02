"""
MegaClient - High-level async client for MEGA.

This is the main entry point for using megapy.
Provides a simple, intuitive API for all MEGA operations.

Supports session persistence similar to Telethon.

Example with session:
    >>> client = MegaClient("my_account")
    >>> await client.start()
    >>> 
    >>> # Tree navigation
    >>> root = await client.get_root()
    >>> docs = root / "Documents"
    >>> for file in docs:
    ...     print(file.name)

Example with credentials:
    >>> async with MegaClient("email@example.com", "password") as mega:
    ...     files = await mega.list_files()
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
from .nodes import MegaNode, MegaNodeBuilder


@dataclass
class MegaFile:
    """Represents a file or folder in MEGA."""
    handle: str
    name: str
    size: int = 0
    is_folder: bool = False
    parent_handle: Optional[str] = None
    key: Optional[bytes] = None
    
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)
    
    def __str__(self) -> str:
        type_str = "[DIR]" if self.is_folder else "[FILE]"
        size_str = f" ({self._format_size()})" if not self.is_folder else ""
        return f"{type_str} {self.name}{size_str}"
    
    def _format_size(self) -> str:
        """Format size in human readable format."""
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


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
        
        # Cached data
        self._nodes: Dict[str, MegaFile] = {}
        self._root_id: Optional[str] = None
        self._master_key: Optional[bytes] = None
        
        # Tree navigation
        self._root_node: Optional[MegaNode] = None
        self._current_node: Optional[MegaNode] = None
        self._node_map: Dict[str, MegaNode] = {}
    
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
        self._nodes.clear()
        self._root_id = None
        
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
    
    # =========================================================================
    # File listing
    # =========================================================================
    
    async def list_files(
        self,
        folder: Optional[str] = None,
        refresh: bool = False
    ) -> List[MegaFile]:
        """
        List files in a folder.
        
        Args:
            folder: Folder handle or path. None for root.
            refresh: Force refresh from server
            
        Returns:
            List of MegaFile objects
        """
        self._ensure_logged_in()
        
        if refresh or not self._nodes:
            await self._load_nodes()
        
        parent_id = folder or self._root_id
        
        return [
            f for f in self._nodes.values()
            if f.parent_handle == parent_id
        ]
    
    async def get_all_files(self, refresh: bool = False) -> List[MegaFile]:
        """
        Get all files (flat list).
        
        Args:
            refresh: Force refresh from server
            
        Returns:
            List of all MegaFile objects
        """
        self._ensure_logged_in()
        
        if refresh or not self._nodes:
            await self._load_nodes()
        
        return list(self._nodes.values())
    
    async def find(self, name: str) -> Optional[MegaFile]:
        """
        Find a file by name.
        
        Args:
            name: File name to search for
            
        Returns:
            MegaFile if found, None otherwise
        """
        self._ensure_logged_in()
        
        if not self._nodes:
            await self._load_nodes()
        
        for f in self._nodes.values():
            if f.name == name:
                return f
        return None
    
    # =========================================================================
    # Tree Navigation (Professional File System Interface)
    # =========================================================================
    
    async def get_root(self, refresh: bool = False) -> MegaNode:
        """
        Get the root node (Cloud Drive).
        
        Args:
            refresh: Force refresh from server
            
        Returns:
            Root MegaNode
            
        Example:
            >>> root = await mega.get_root()
            >>> for item in root:
            ...     print(item.name)
        """
        self._ensure_logged_in()
        
        if refresh or self._root_node is None:
            await self._load_tree()
        
        return self._root_node
    
    async def get(self, path: str, refresh: bool = False) -> Optional[MegaNode]:
        """
        Get node by path.
        
        Args:
            path: Path from root (e.g., "/Documents/report.pdf")
            refresh: Force refresh from server
            
        Returns:
            MegaNode or None if not found
            
        Example:
            >>> docs = await mega.get("/Documents")
            >>> file = await mega.get("/Documents/report.pdf")
        """
        self._ensure_logged_in()
        
        if refresh or self._root_node is None:
            await self._load_tree()
        
        if not path or path == "/":
            return self._root_node
        
        # Remove leading slash and split
        path = path.lstrip("/")
        return self._root_node.find(path)
    
    async def cd(self, path: str) -> MegaNode:
        """
        Change current directory.
        
        Args:
            path: Path to navigate to (absolute or relative)
            
        Returns:
            New current node
            
        Example:
            >>> await mega.cd("/Documents")
            >>> await mega.cd("Reports")  # Relative
            >>> await mega.cd("..")       # Parent
        """
        self._ensure_logged_in()
        
        if self._root_node is None:
            await self._load_tree()
        
        if self._current_node is None:
            self._current_node = self._root_node
        
        if path == "/":
            self._current_node = self._root_node
        elif path.startswith("/"):
            # Absolute path
            node = self._root_node.find(path.lstrip("/"))
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
        """
        Get current working directory path.
        
        Returns:
            Current path string
            
        Example:
            >>> print(mega.pwd())
            /Documents/Reports
        """
        if self._current_node is None:
            return "/"
        return self._current_node.path
    
    async def ls(
        self,
        path: Optional[str] = None,
        show_hidden: bool = False
    ) -> List[MegaNode]:
        """
        List directory contents.
        
        Args:
            path: Path to list (None for current directory)
            show_hidden: Include hidden files
            
        Returns:
            List of child nodes
            
        Example:
            >>> files = await mega.ls()
            >>> files = await mega.ls("/Documents")
        """
        self._ensure_logged_in()
        
        if self._root_node is None:
            await self._load_tree()
        
        if path:
            node = await self.get(path)
        else:
            node = self._current_node or self._root_node
        
        if node is None:
            raise FileNotFoundError(f"Path not found: {path}")
        
        return node.ls(show_hidden=show_hidden)
    
    async def tree(self, path: Optional[str] = None, max_depth: int = 3) -> str:
        """
        Get tree representation of directory structure.
        
        Args:
            path: Starting path (None for current/root)
            max_depth: Maximum depth to display
            
        Returns:
            Tree string
            
        Example:
            >>> print(await mega.tree())
            [+] Cloud Drive
              [+] Documents
                [-] report.pdf
              [+] Photos
        """
        self._ensure_logged_in()
        
        if self._root_node is None:
            await self._load_tree()
        
        if path:
            node = await self.get(path)
        else:
            node = self._current_node or self._root_node
        
        if node is None:
            raise FileNotFoundError(f"Path not found: {path}")
        
        return node.tree(max_depth=max_depth)
    
    async def glob(self, pattern: str, path: Optional[str] = None) -> List[MegaNode]:
        """
        Find files matching glob pattern.
        
        Args:
            pattern: Glob pattern (e.g., "*.pdf", "**/*.txt")
            path: Starting path
            
        Returns:
            List of matching nodes
            
        Example:
            >>> pdfs = await mega.glob("*.pdf")
            >>> all_docs = await mega.glob("Documents/**/*.docx")
        """
        self._ensure_logged_in()
        
        if self._root_node is None:
            await self._load_tree()
        
        if path:
            node = await self.get(path)
        else:
            node = self._root_node
        
        if node is None:
            return []
        
        return node.glob(pattern)
    
    async def walk(
        self,
        path: Optional[str] = None
    ):
        """
        Walk the directory tree like os.walk().
        
        Args:
            path: Starting path
            
        Yields:
            (folder, subfolders, files) tuples
            
        Example:
            >>> async for folder, subfolders, files in mega.walk():
            ...     print(f"{folder.path}: {len(files)} files")
        """
        self._ensure_logged_in()
        
        if self._root_node is None:
            await self._load_tree()
        
        if path:
            node = await self.get(path)
        else:
            node = self._root_node
        
        if node is None:
            return
        
        for item in node.walk():
            yield item
    
    def get_node(self, handle: str) -> Optional[MegaNode]:
        """
        Get node by handle.
        
        Args:
            handle: Node handle
            
        Returns:
            MegaNode or None
        """
        return self._node_map.get(handle)
    
    async def _load_tree(self) -> None:
        """Load file tree from server."""
        response = await self._api.get_files()
        nodes_data = response.get('f', [])
        
        # Build tree
        self._root_node = MegaNodeBuilder.build_tree(
            nodes_data,
            self._master_key,
            self
        )
        
        # Set current to root
        if self._current_node is None:
            self._current_node = self._root_node
        
        # Build node map
        self._node_map.clear()
        if self._root_node:
            self._build_node_map(self._root_node)
            self._root_id = self._root_node.handle
    
    def _build_node_map(self, node: MegaNode) -> None:
        """Recursively build node handle map."""
        self._node_map[node.handle] = node
        for child in node.children:
            self._build_node_map(child)
    
    # =========================================================================
    # Upload
    # =========================================================================
    
    async def upload(
        self,
        file_path: Union[str, Path],
        dest_folder: Optional[str] = None,
        name: Optional[str] = None,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None,
        custom: Optional[Dict[str, Any]] = None,
        label: int = 0,
        auto_thumb: bool = True
    ) -> MegaFile:
        """
        Upload a file to MEGA.
        
        Args:
            file_path: Local file path
            dest_folder: Destination folder handle. None for root.
            name: Optional custom name for the file
            progress_callback: Optional callback for progress updates
            custom: Custom attributes dict. Keys: i=document_id, u=url, d=date, or any 1-2 char key
            label: Color label (0-7: none, red, orange, yellow, green, blue, purple, grey)
            auto_thumb: Auto-generate thumbnail/preview for images/videos
            
        Returns:
            MegaFile representing the uploaded file
            
        Example:
            # Simple upload
            await mega.upload("file.txt")
            
            # With custom attributes
            await mega.upload("doc.pdf", custom={
                'i': 'DOC-001',
                'u': 'https://example.com',
                't': 'invoice'
            })
            
            # Image with auto thumbnail
            await mega.upload("photo.jpg")  # auto-generates thumb & preview
        """
        self._ensure_logged_in()
        
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not self._root_id:
            await self._load_nodes()
        
        target_id = dest_folder or self._root_id
        
        # Build custom attributes if provided
        custom_attrs = None
        if custom:
            from .core.upload.models import CustomAttributes
            custom_attrs = CustomAttributes(
                document_id=custom.get('i'),
                url=custom.get('u'),
                date=custom.get('d')
            )
            # Add extra keys
            for k, v in custom.items():
                if k not in ('i', 'u', 'd'):
                    custom_attrs.set(k, v)
        
        # Build file attributes
        attrs = FileAttributes(
            name=name or path.name,
            label=label,
            custom=custom_attrs
        )
        
        # Auto-generate thumbnail and preview for media
        thumbnail = None
        preview = None
        if auto_thumb:
            try:
                from .core.attributes import MediaProcessor
                processor = MediaProcessor()
                if processor.is_media(path):
                    result = processor.process(path)
                    thumbnail = result.thumbnail
                    preview = result.preview
            except ImportError:
                pass  # Pillow not installed
            except Exception:
                pass  # Silently ignore media processing errors
        
        coordinator = UploadCoordinator(
            api_client=self._api,
            master_key=self._master_key,
            progress_callback=progress_callback
        )
        
        config = UploadConfig(
            file_path=path,
            target_folder_id=target_id,
            attributes=attrs,
            thumbnail=thumbnail,
            preview=preview
        )
        
        result = await coordinator.upload(config)
        
        mega_file = MegaFile(
            handle=result.node_handle,
            name=name or path.name,
            size=result.file_size,
            is_folder=False,
            parent_handle=target_id,
            key=result.file_key
        )
        
        self._nodes[result.node_handle] = mega_file
        
        return mega_file
    
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
        self._nodes.pop(mega_file.handle, None)
        
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
    ) -> MegaFile:
        """Create a new folder."""
        self._ensure_logged_in()
        
        if not self._root_id:
            await self._load_nodes()
        
        parent_id = self._root_id
        if parent:
            parent_file = await self._resolve_file(parent)
            if parent_file:
                parent_id = parent_file.handle
        
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
            node = result['f'][0]
            mega_file = MegaFile(
                handle=node['h'],
                name=name,
                is_folder=True,
                parent_handle=parent_id
            )
            self._nodes[node['h']] = mega_file
            return mega_file
        
        raise ValueError("Failed to create folder")
    
    # =========================================================================
    # Private helpers
    # =========================================================================
    
    def _ensure_logged_in(self):
        """Ensure user is logged in."""
        if not self._master_key:
            raise RuntimeError("Not logged in. Call start() or use 'async with' first.")
    
    async def _load_nodes(self):
        """Load all nodes from server."""
        response = await self._api.get_files()
        nodes = response.get('f', [])
        
        encoder = Base64Encoder()
        
        for node in nodes:
            node_type = node.get('t', 0)
            handle = node.get('h', '')
            
            if node_type in (3, 4):
                continue
            
            if node_type == 2:
                self._root_id = handle
                self._nodes[handle] = MegaFile(
                    handle=handle,
                    name="Cloud Drive",
                    is_folder=True,
                    _raw=node
                )
                continue
            
            name = self._decrypt_name(node, encoder)
            
            self._nodes[handle] = MegaFile(
                handle=handle,
                name=name,
                size=node.get('s', 0),
                is_folder=(node_type == 1),
                parent_handle=node.get('p'),
                key=self._decrypt_key(node, encoder),
                _raw=node
            )
    
    def _decrypt_name(self, node: Dict, encoder: Base64Encoder) -> str:
        """Decrypt node name from attributes."""
        try:
            attrs = node.get('a', '')
            key_str = node.get('k', '')
            
            if not attrs or not key_str:
                return node.get('h', 'Unknown')
            
            node_key = self._decrypt_key(node, encoder)
            if not node_key:
                return node.get('h', 'Unknown')
            
            from Crypto.Cipher import AES
            
            attrs_bytes = encoder.decode(attrs)
            cipher = AES.new(node_key[:16], AES.MODE_CBC, iv=b'\x00' * 16)
            decrypted = cipher.decrypt(attrs_bytes)
            
            if decrypted.startswith(b'MEGA'):
                import json
                json_str = decrypted[4:].rstrip(b'\x00').decode('utf-8', errors='ignore')
                attrs_dict = json.loads(json_str)
                return attrs_dict.get('n', node.get('h', 'Unknown'))
            
            return node.get('h', 'Unknown')
            
        except Exception:
            return node.get('h', 'Unknown')
    
    def _decrypt_key(self, node: Dict, encoder: Base64Encoder) -> Optional[bytes]:
        """Decrypt node key."""
        try:
            key_str = node.get('k', '')
            if not key_str or ':' not in key_str:
                return None
            
            _, encrypted = key_str.split(':', 1)
            encrypted_key = encoder.decode(encrypted)
            
            from Crypto.Cipher import AES
            cipher = AES.new(self._master_key, AES.MODE_ECB)
            
            if len(encrypted_key) == 32:
                decrypted = cipher.decrypt(encrypted_key)
                return decrypted
            elif len(encrypted_key) == 16:
                return cipher.decrypt(encrypted_key)
            
            return None
            
        except Exception:
            return None
    
    async def _resolve_file(self, file: Union[str, MegaFile]) -> Optional[MegaFile]:
        """Resolve file argument to MegaFile."""
        if isinstance(file, MegaFile):
            return file
        
        if not self._nodes:
            await self._load_nodes()
        
        if file in self._nodes:
            return self._nodes[file]
        
        return await self.find(file)
