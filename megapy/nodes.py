"""
MegaNode - Professional tree-based file system navigation.

Provides intuitive file/folder navigation similar to a real file system.

Example:
    >>> root = await mega.get_root()
    >>> for item in root:
    ...     print(item.name)
    >>> 
    >>> docs = root / "Documents"  # Navigate using /
    >>> file = docs / "report.pdf"
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Iterator, TYPE_CHECKING
from pathlib import PurePosixPath
from Crypto.Cipher import AES

if TYPE_CHECKING:
    from .client import MegaClient


@dataclass
class MegaNode:
    """
    Represents a file or folder in MEGA with tree navigation.
    
    Supports intuitive navigation:
        >>> folder = root / "Documents"
        >>> file = folder / "report.pdf"
        >>> 
        >>> for child in folder:
        ...     print(child)
        >>> 
        >>> if "report.pdf" in folder:
        ...     print("Found!")
    
    Attributes:
        handle: Unique node identifier
        name: Display name
        size: File size in bytes (0 for folders)
        is_folder: True if this is a folder
        parent: Parent node (None for root)
        children: List of child nodes
        key: Encryption key (bytes)
        path: Full path from root
    """
    handle: str
    name: str
    size: int = 0
    is_folder: bool = False
    node_type: int = 0
    key: Optional[bytes] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Tree structure
    parent: Optional[MegaNode] = field(default=None, repr=False)
    children: List[MegaNode] = field(default_factory=list, repr=False)
    
    # Client reference for operations
    _client: Optional[MegaClient] = field(default=None, repr=False)
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def is_file(self) -> bool:
        """Check if this is a file."""
        return not self.is_folder
    
    @property
    def path(self) -> str:
        """Get full path from root."""
        if self.parent is None:
            return "/"
        
        parts = []
        node = self
        while node.parent is not None:
            parts.append(node.name)
            node = node.parent
        
        return "/" + "/".join(reversed(parts))
    
    @property
    def depth(self) -> int:
        """Get depth in tree (root = 0)."""
        depth = 0
        node = self
        while node.parent is not None:
            depth += 1
            node = node.parent
        return depth
    
    @property
    def is_root(self) -> bool:
        """Check if this is the root node."""
        return self.parent is None
    
    @property
    def is_empty(self) -> bool:
        """Check if folder is empty."""
        return len(self.children) == 0
    
    @property
    def files(self) -> List[MegaNode]:
        """Get only file children."""
        return [c for c in self.children if c.is_file]
    
    @property
    def folders(self) -> List[MegaNode]:
        """Get only folder children."""
        return [c for c in self.children if c.is_folder]
    
    @property
    def size_formatted(self) -> str:
        """Get human-readable size."""
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    @property
    def label(self) -> int:
        """Get color label (0-7)."""
        return self.attributes.get('lbl', 0)
    
    @property
    def label_name(self) -> str:
        """Get color label name."""
        labels = ['none', 'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'grey']
        return labels[self.label] if self.label < len(labels) else 'none'
    
    @property
    def favorite(self) -> bool:
        """Check if marked as favorite."""
        return bool(self.attributes.get('fav', 0))
    
    @property
    def custom(self) -> Optional[Dict[str, Any]]:
        """Get custom attributes (e object)."""
        return self.attributes.get('e')
    
    @property
    def document_id(self) -> Optional[str]:
        """Get document_id from custom attributes (i key)."""
        e = self.attributes.get('e')
        return e.get('i') if e else None
    
    @property
    def url(self) -> Optional[str]:
        """Get url from custom attributes (u key)."""
        e = self.attributes.get('e')
        return e.get('u') if e else None
    
    @property
    def has_thumbnail(self) -> bool:
        """Check if file has a thumbnail."""
        fa = self._raw.get('fa', '') if self._raw else ''
        return '0*' in fa
    
    @property
    def has_preview(self) -> bool:
        """Check if file has a preview."""
        fa = self._raw.get('fa', '') if self._raw else ''
        return '1*' in fa
    
    @property
    def file_attributes(self) -> Optional[str]:
        """Get raw file attributes string (fa field)."""
        return self._raw.get('fa') if self._raw else None
    
    def _get_fa_handle(self, attr_type: int) -> Optional[str]:
        """
        Get handle for a specific file attribute type.
        
        Args:
            attr_type: 0=thumbnail, 1=preview
            
        Returns:
            Attribute handle or None
        """
        fa = self._raw.get('fa', '') if self._raw else ''
        if not fa:
            return None
        
        # Format: "user_id:type*handle/user_id:type*handle"
        for part in fa.split('/'):
            if ':' in part:
                _, type_handle = part.split(':', 1)
            else:
                type_handle = part
            
            if '*' in type_handle:
                t, handle = type_handle.split('*', 1)
                if int(t) == attr_type:
                    return handle
        
        return None
    
    async def get_thumbnail(self) -> Optional[bytes]:
        """
        Download and decrypt thumbnail.
        
        Returns:
            Decrypted thumbnail bytes or None
        """
        if not self._client or not self.has_thumbnail:
            return None
        
        handle = self._get_fa_handle(0)
        if not handle:
            return None
        
        return await self._client._download_file_attribute(self, handle, 0)
    
    async def get_preview(self) -> Optional[bytes]:
        """
        Download and decrypt preview.
        
        Returns:
            Decrypted preview bytes or None
        """
        if not self._client or not self.has_preview:
            return None
        
        handle = self._get_fa_handle(1)
        if not handle:
            return None
        
        return await self._client._download_file_attribute(self, handle, 1)
    
    # =========================================================================
    # Media attributes (video/audio metadata)
    # =========================================================================
    
    @property
    def has_media_info(self) -> bool:
        """Check if file has media attributes (video/audio metadata)."""
        fa = self._raw.get('fa', '') if self._raw else ''
        return ':8*' in fa
    
    @property
    def media_info(self) -> Optional['MediaInfo']:
        """
        Get media info (video/audio metadata).
        
        Returns:
            MediaInfo with width, height, fps, playtime, etc. or None
        """
        if not self.has_media_info or not self.key:
            return None
        
        from megapy.core.attributes import MediaAttributeService
        
        fa = self._raw.get('fa', '') if self._raw else ''
        service = MediaAttributeService()
        return service.decode(fa, self.key)
    
    @property
    def duration(self) -> Optional[int]:
        """Get media duration in seconds."""
        info = self.media_info
        return info.playtime if info else None
    
    @property
    def duration_formatted(self) -> Optional[str]:
        """Get formatted duration (MM:SS or HH:MM:SS)."""
        info = self.media_info
        return info.duration_formatted if info else None
    
    @property
    def resolution(self) -> Optional[str]:
        """Get video resolution string (e.g., '1920x1080')."""
        info = self.media_info
        return info.resolution if info and info.is_video else None
    
    @property
    def width(self) -> Optional[int]:
        """Get video width in pixels."""
        info = self.media_info
        return info.width if info and info.width > 0 else None
    
    @property
    def height(self) -> Optional[int]:
        """Get video height in pixels."""
        info = self.media_info
        return info.height if info and info.height > 0 else None
    
    @property
    def fps(self) -> Optional[int]:
        """Get video frames per second."""
        info = self.media_info
        return info.fps if info and info.fps > 0 else None
    
    # =========================================================================
    # Navigation operators
    # =========================================================================
    
    def __truediv__(self, name: str) -> Optional[MegaNode]:
        """
        Navigate to child using / operator.
        
        Example:
            >>> docs = root / "Documents"
            >>> file = docs / "report.pdf"
        """
        return self.get(name)
    
    def __contains__(self, name: str) -> bool:
        """
        Check if child exists using 'in' operator.
        
        Example:
            >>> if "Documents" in root:
            ...     print("Found!")
        """
        return any(c.name == name for c in self.children)
    
    def __iter__(self) -> Iterator[MegaNode]:
        """
        Iterate over children.
        
        Example:
            >>> for child in folder:
            ...     print(child.name)
        """
        return iter(self.children)
    
    def __len__(self) -> int:
        """Get number of children."""
        return len(self.children)
    
    def __getitem__(self, key: str) -> Optional[MegaNode]:
        """
        Get child by name using [] operator.
        
        Example:
            >>> file = folder["report.pdf"]
        """
        return self.get(key)
    

    
    # =========================================================================
    # Navigation methods
    # =========================================================================
    
    def get(self, name: str) -> Optional[MegaNode]:
        """
        Get child by name.
        
        Args:
            name: Child name
            
        Returns:
            Child node or None
        """
        for child in self.children:
            if child.name == name:
                return child
        return None
    
    def find(self, path: str) -> Optional[MegaNode]:
        """
        Find node by relative path.
        
        Args:
            path: Relative path (e.g., "Documents/Reports/file.pdf")
            
        Returns:
            Node or None
        """
        if not path or path == ".":
            return self
        
        if path == "..":
            return self.parent
        
        parts = [p for p in path.split("/") if p and p != "."]
        
        current = self
        for part in parts:
            if part == "..":
                if current.parent:
                    current = current.parent
            else:
                child = current.get(part)
                if not child:
                    return None
                current = child
        
        return current
    
    def walk(self) -> Iterator[tuple[MegaNode, List[MegaNode], List[MegaNode]]]:
        """
        Walk the tree like os.walk().
        
        Yields:
            (folder, subfolders, files) for each folder
            
        Example:
            >>> for folder, subfolders, files in root.walk():
            ...     print(f"{folder.path}: {len(files)} files")
        """
        folders = self.folders
        files = self.files
        yield self, folders, files
        
        for folder in folders:
            yield from folder.walk()
    
    def tree(self, indent: int = 0, max_depth: int = -1) -> str:
        """
        Get tree representation as string.
        
        Args:
            indent: Current indentation level
            max_depth: Maximum depth (-1 for unlimited)
            
        Returns:
            Tree string
        """
        if max_depth == 0:
            return ""
        
        prefix = "  " * indent
        icon = "[+]" if self.is_folder else "[-]"
        result = f"{prefix}{icon} {self.name}\n"
        
        if self.is_folder and max_depth != 0:
            for child in sorted(self.children, key=lambda x: (not x.is_folder, x.name)):
                result += child.tree(indent + 1, max_depth - 1 if max_depth > 0 else -1)
        
        return result
    
    def ls(self, show_hidden: bool = False) -> List[MegaNode]:
        """
        List children (like ls command).
        
        Args:
            show_hidden: Include hidden files (starting with .)
            
        Returns:
            List of children
        """
        children = self.children
        if not show_hidden:
            children = [c for c in children if not c.name.startswith('.')]
        return sorted(children, key=lambda x: (not x.is_folder, x.name.lower()))
    
    # =========================================================================
    # Tree modification
    # =========================================================================
    
    def add_child(self, child: MegaNode) -> None:
        """Add a child node."""
        if child not in self.children:
            child.parent = self
            self.children.append(child)
    
    def remove_child(self, child: MegaNode) -> None:
        """Remove a child node."""
        if child in self.children:
            child.parent = None
            self.children.remove(child)
    
    # =========================================================================
    # Search methods
    # =========================================================================
    
    def find_all(self, name: str, recursive: bool = True) -> List[MegaNode]:
        """
        Find all nodes matching name.
        
        Args:
            name: Name to search for
            recursive: Search in subfolders
            
        Returns:
            List of matching nodes
        """
        results = []
        
        for child in self.children:
            if child.name == name:
                results.append(child)
            
            if recursive and child.is_folder:
                results.extend(child.find_all(name, recursive=True))
        
        return results
    
    def find_by_extension(self, ext: str, recursive: bool = True) -> List[MegaNode]:
        """
        Find files by extension.
        
        Args:
            ext: Extension (e.g., ".pdf" or "pdf")
            recursive: Search in subfolders
            
        Returns:
            List of matching files
        """
        if not ext.startswith('.'):
            ext = '.' + ext
        
        results = []
        
        for child in self.children:
            if child.is_file and child.name.lower().endswith(ext.lower()):
                results.append(child)
            
            if recursive and child.is_folder:
                results.extend(child.find_by_extension(ext, recursive=True))
        
        return results
    
    def glob(self, pattern: str) -> List[MegaNode]:
        """
        Find nodes matching glob pattern.
        
        Args:
            pattern: Glob pattern (e.g., "*.pdf", "docs/*.txt")
            
        Returns:
            List of matching nodes
        """
        import fnmatch
        
        results = []
        
        # Simple pattern (no /)
        if '/' not in pattern:
            for child in self.children:
                if fnmatch.fnmatch(child.name, pattern):
                    results.append(child)
                if child.is_folder:
                    results.extend(child.glob(pattern))
        else:
            # Path pattern
            parts = pattern.split('/', 1)
            for child in self.children:
                if fnmatch.fnmatch(child.name, parts[0]):
                    if len(parts) == 1:
                        results.append(child)
                    elif child.is_folder:
                        results.extend(child.glob(parts[1]))
        
        return results
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_total_size(self) -> int:
        """Get total size including all descendants."""
        total = self.size
        for child in self.children:
            if child.is_folder:
                total += child.get_total_size()
            else:
                total += child.size
        return total
    
    def count_files(self, recursive: bool = True) -> int:
        """Count files."""
        count = len(self.files)
        if recursive:
            for folder in self.folders:
                count += folder.count_files(recursive=True)
        return count
    
    def count_folders(self, recursive: bool = True) -> int:
        """Count folders."""
        count = len(self.folders)
        if recursive:
            for folder in self.folders:
                count += folder.count_folders(recursive=True)
        return count


class MegaNodeBuilder:
    """Builds MegaNode tree from API response."""
    
    @staticmethod
    def build_tree(
        nodes_data: List[Dict[str, Any]],
        master_key: bytes,
        client: Optional[MegaClient] = None
    ) -> Optional[MegaNode]:
        """
        Build node tree from API response.
        
        Args:
            nodes_data: List of node data from API
            master_key: Master encryption key
            client: MegaClient instance
            
        Returns:
            Root node or None
        """
        from .core.crypto import Base64Encoder
        from Crypto.Cipher import AES
        
        encoder = Base64Encoder()
        node_map: Dict[str, MegaNode] = {}
        root_candidates: List[MegaNode] = []
        
        # First pass: create all nodes
        for node_data in nodes_data:
            handle = node_data.get('h', '')
            node_type = node_data.get('t', 0)
            parent_handle = node_data.get('p')
            
            # Skip trash and inbox
            if node_type in (3, 4):
                continue
            
            # Decrypt key
            key = MegaNodeBuilder._decrypt_key(node_data, master_key, encoder)
            
            # Decrypt all attributes
            attrs = MegaNodeBuilder._decrypt_attributes(node_data, key, encoder)
            if attrs:
                name = attrs.get('n', handle)
            else:
                name = handle
                attrs = {'n': name}
            
            # Create node
            node = MegaNode(
                handle=handle,
                name=name,
                size=node_data.get('s', 0),
                is_folder=(node_type == 1 or node_type == 2),
                node_type=node_type,
                key=key,
                attributes=attrs,
                _client=client,
                _raw=node_data
            )
            
            node_map[handle] = node
            
            # Root folder (type 2)
            if node_type == 2:
                node.name = "Cloud Drive"
                root_candidates.insert(0, node)  # Priority
            elif parent_handle is None:
                root_candidates.append(node)
        
        # Second pass: build relationships
        for node_data in nodes_data:
            handle = node_data.get('h', '')
            parent_handle = node_data.get('p')
            
            if handle not in node_map:
                continue
            
            node = node_map[handle]
            
            if parent_handle and parent_handle in node_map:
                parent = node_map[parent_handle]
                parent.add_child(node)
        
        # Return root
        if root_candidates:
            return root_candidates[0]
        
        return None
    
    @staticmethod
    def _decrypt_key(
        node_data: Dict,
        master_key: bytes,
        encoder: Base64Encoder
    ) -> Optional[bytes]:
        """Decrypt node key."""
        try:
            key_str = node_data.get('k', '')
            if not key_str or ':' not in key_str:
                return None
            
            _, encrypted = key_str.split(':', 1)
            encrypted_key = encoder.decode(encrypted)
            
            cipher = AES.new(master_key, AES.MODE_ECB)
            
            if len(encrypted_key) == 32:
                # File key: decrypt and XOR the two halves
                decrypted = cipher.decrypt(encrypted_key)
                # XOR first 16 bytes with last 16 bytes to get actual key
                key = bytes(a ^ b for a, b in zip(decrypted[:16], decrypted[16:]))
                return key
            elif len(encrypted_key) == 16:
                # Folder key: just decrypt
                return cipher.decrypt(encrypted_key)
            
            return None
        except Exception:
            return None
    
    @staticmethod
    def _decrypt_attributes(
        node_data: Dict,
        key: Optional[bytes],
        encoder: Base64Encoder
    ) -> Optional[Dict[str, Any]]:
        """Decrypt all node attributes."""
        try:
            if not key:
                return None
            
            attrs = node_data.get('a', '')
            if not attrs:
                return None
            
            attrs_bytes = encoder.decode(attrs)
            cipher = AES.new(key[:16], AES.MODE_CBC, iv=b'\x00' * 16)
            decrypted = cipher.decrypt(attrs_bytes)
            
            if decrypted.startswith(b'MEGA'):
                import json
                # Find end of JSON (null terminator)
                end = 4
                while end < len(decrypted) and decrypted[end] != 0:
                    end += 1
                json_str = decrypted[4:end].decode('utf-8', errors='ignore')
                return json.loads(json_str)
            
            return None
        except Exception:
            return None
