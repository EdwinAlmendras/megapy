"""Unified Node class for MEGA files and folders."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Iterator, Union, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from .client import MegaClient
    from .core.attributes.media import MediaInfo
    from .core.attributes.models import FileAttributes


@dataclass
class Node:
    """
    Unified representation of a file or folder in MEGA.
    
    Supports both flat access and tree navigation:
        >>> for node in root:
        ...     print(node.name)
        >>> 
        >>> docs = root / "Documents"
        >>> file = docs / "report.pdf"
    """
    handle: str
    name: str
    size: int = 0
    is_folder: bool = False
    parent_handle: Optional[str] = None
    key: Optional[bytes] = None
    fa: Optional[str] = None
    attributes: Optional[FileAttributes] = None
    parent: Optional[Node] = field(default=None, repr=False)
    children: List[Node] = field(default_factory=list, repr=False)
    
    _client: Optional[MegaClient] = field(default=None, repr=False)
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)
    _media_info_cache: Any = field(default=None, repr=False)
    
    # =========================================================================
    # Display
    # =========================================================================
    
    """ def __str__(self) -> str:
        type_str = "[DIR]" if self.is_folder else "[FILE]"
        size_str = f" ({self._format_size()})" if not self.is_folder else ""
        media_str = ""
        if self.has_media_info:
            info = self.media_info
            if info:
                media_str = f" [{info.width}x{info.height} {info.duration_formatted}]"
        return f"{type_str} {self.name}{size_str}{media_str}" """
    
    def _format_size(self) -> str:
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def is_file(self) -> bool:
        return not self.is_folder
    
    @property
    def is_root(self) -> bool:
        return self.parent is None and self.is_folder
    
    @property
    def path(self) -> str:
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
        depth = 0
        node = self
        while node.parent is not None:
            depth += 1
            node = node.parent
        return depth
    
    @property
    def files(self) -> List[Node]:
        return [c for c in self.children if c.is_file]
    
    @property
    def folders(self) -> List[Node]:
        return [c for c in self.children if c.is_folder]
    
    # =========================================================================
    # Media Properties
    # =========================================================================
    
    @property
    def has_media_info(self) -> bool:
        return self.fa is not None and ':8*' in self.fa
    
    @property
    def has_thumbnail(self) -> bool:
        return self.fa is not None and ':0*' in self.fa
    
    @property
    def has_preview(self) -> bool:
        return self.fa is not None and ':1*' in self.fa
    
    @property
    def media_info(self) -> Optional[MediaInfo]:
        """Get media info (duration, resolution, codecs) for video/audio files."""
        if self._media_info_cache is not None:
            return self._media_info_cache
        if not self.has_media_info or not self.key or not self.fa:
            return None
        try:
            from .core.attributes import MediaAttributeService
            service = MediaAttributeService()
            self._media_info_cache = service.decode(self.fa, self.key)
            return self._media_info_cache
        except Exception:
            return None
    
    @property
    def duration(self) -> Optional[int]:
        info = self.media_info
        return info.playtime if info else None
    
    @property
    def width(self) -> Optional[int]:
        info = self.media_info
        return info.width if info and info.width > 0 else None
    
    @property
    def height(self) -> Optional[int]:
        info = self.media_info
        return info.height if info and info.height > 0 else None
    
    @property
    def fps(self) -> Optional[int]:
        info = self.media_info
        return info.fps if info and info.fps > 0 else None
    
    @property
    def is_video(self) -> bool:
        return self.width is not None and self.height is not None
    
    @property
    def is_audio(self) -> bool:
        info = self.media_info
        return info is not None and info.is_audio
    
    # =========================================================================
    # Thumbnail & Preview
    # =========================================================================
    
    def _get_fa_handle(self, attr_type: int) -> Optional[str]:
        """
        Extract file attribute handle from 'fa' string.
        
        Args:
            attr_type: 0=thumbnail, 1=preview, 8=media_info
            
        Returns:
            Attribute handle or None
        """
        if not self.fa:
            return None
        
        # Format: "user_id:type*handle/user_id:type*handle"
        for part in self.fa.split('/'):
            if ':' in part:
                _, type_handle = part.split(':', 1)
            else:
                type_handle = part
            
            if '*' in type_handle:
                t, handle = type_handle.split('*', 1)
                try:
                    if int(t) == attr_type:
                        return handle
                except ValueError:
                    continue
        
        return None
    
    async def get_thumbnail(self) -> Optional[bytes]:
        """
        Download and decrypt thumbnail image.
        
        Returns:
            Decrypted JPEG thumbnail bytes (240x240) or None
            
        Example:
            >>> if node.has_thumbnail:
            ...     thumb = await node.get_thumbnail()
            ...     with open("thumb.jpg", "wb") as f:
            ...         f.write(thumb)
        """
        if not self._client or not self.has_thumbnail:
            return None
        
        handle = self._get_fa_handle(0)
        if not handle:
            return None
        
        return await self._client._download_file_attribute(self, handle, 0)
    
    async def get_preview(self) -> Optional[bytes]:
        """
        Download and decrypt preview image.
        
        Returns:
            Decrypted JPEG preview bytes (max 1024px) or None
            
        Example:
            >>> if node.has_preview:
            ...     preview = await node.get_preview()
            ...     with open("preview.jpg", "wb") as f:
            ...         f.write(preview)
        """
        if not self._client or not self.has_preview:
            return None
        
        handle = self._get_fa_handle(1)
        if not handle:
            return None
        
        return await self._client._download_file_attribute(self, handle, 1)
    
    # =========================================================================
    # Tree Navigation
    # =========================================================================
    
    def __iter__(self) -> Iterator[Node]:
        return iter(self.children)
    
    def __len__(self) -> int:
        return len(self.children)
    
    def __bool__(self) -> bool:
        return True  # Node always truthy
    
    def __contains__(self, name: str) -> bool:
        return any(c.name == name for c in self.children)
    
    def __truediv__(self, name: str) -> Optional[Node]:
        for child in self.children:
            if child.name == name:
                return child
        return None
    
    def __getitem__(self, name: str) -> Node:
        for child in self.children:
            if child.name == name:
                return child
        raise KeyError(f"'{name}' not found in {self.name}")
    
    def get(self, name: str, default: Optional[Node] = None) -> Optional[Node]:
        return self / name or default
    
    def find(self, path: str) -> Optional[Node]:
        if not path or path == ".":
            return self
        if path == "..":
            return self.parent
        
        parts = path.strip("/").split("/")
        current = self
        
        for part in parts:
            if not part or part == ".":
                continue
            if part == "..":
                current = current.parent if current.parent else current
            else:
                current = current / part
                if current is None:
                    return None
        return current
    
    def walk(self, include_self: bool = False) -> Iterator[Node]:
        if include_self:
            yield self
        for child in self.children:
            yield child
            if child.is_folder:
                yield from child.walk()
    
    def all_files(self) -> List[Node]:
        return [n for n in self.walk() if n.is_file]
    
    def all_folders(self) -> List[Node]:
        return [n for n in self.walk() if n.is_folder]
    
    # =========================================================================
    # Operations (delegate to client)
    # =========================================================================
    
    async def download(self, dest: str = ".") -> 'Path':
        """Download file to local path. Returns Path object."""
        if not self._client:
            raise RuntimeError("No client attached")
        from pathlib import Path
        result = await self._client.download(self, dest)
        return Path(result) if isinstance(result, str) else result
    
    async def delete(self) -> bool:
        if not self._client:
            raise RuntimeError("No client attached")
        return await self._client.delete(self)
    
    async def rename(self, new_name: str) -> 'Node':
        """Rename file/folder. Returns updated Node."""
        if not self._client:
            raise RuntimeError("No client attached")
        return await self._client.rename(self, new_name)
    
    async def move(self, dest_folder: Node) -> 'Node':
        """Move file/folder to destination. Returns updated Node."""
        if not self._client:
            raise RuntimeError("No client attached")
        return await self._client.move(self, dest_folder)
    
    async def import_link(
        self,
        source: Union[str, 'Node'],
        clear_attributes: bool = True
    ) -> List['Node']:
        """
        Import a file or folder link (with all its children) into this folder.
        
        This creates a copy of the source file/folder and all its contents
        in this folder. Based on webclient's import logic.
        
        Args:
            source: Source file or folder to import (URL, handle, path, or Node)
            clear_attributes: If True, clear sensitive attributes (s4, lbl, fav, sen)
            
        Returns:
            List of imported Node objects
            
        Example:
            >>> root = await mega.get_root()
            >>> imports_folder = root / "imports"
            >>> imported = await imports_folder.import_link(
            ...     "https://mega.nz/folder/iJkVRL7T#SMCUCSEOhqwgV6uIUa1Wsw",
            ...     clear_attributes=False
            ... )
            >>> print(f"Imported {len(imported)} nodes")
        """
        if not self._client:
            raise RuntimeError("No client attached")
        
        if not self.is_folder:
            raise ValueError(f"Cannot import into a file. This node is not a folder: {self.name}")
        
        return await self._client.import_folder(
            source_folder=source,
            target_folder=self,
            clear_attributes=clear_attributes
        )


# Backward compatibility aliases
MegaFile = Node
MegaNode = Node
