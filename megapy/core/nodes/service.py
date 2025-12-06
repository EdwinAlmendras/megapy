"""Node loading and tree building service."""
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from .decryptor import KeyDecryptor
from ...node import Node
from ..attributes.models import FileAttributes

if TYPE_CHECKING:
    from ...client import MegaClient


class NodeService:
    """
    Single service for loading and managing MEGA nodes.
    
    Responsibilities:
    - Load nodes from API
    - Decrypt keys and attributes
    - Build node tree with parent/child relationships
    """
    
    NODE_TYPE_FILE = 0
    NODE_TYPE_FOLDER = 1
    NODE_TYPE_ROOT = 2
    NODE_TYPE_INBOX = 3
    NODE_TYPE_TRASH = 4
    
    def __init__(self, master_key: bytes, client: 'MegaClient' = None):
        self._master_key = master_key
        self._client = client
        self._decryptor = KeyDecryptor()
        
        self._nodes: Dict[str, Node] = {}
        self._root: Optional[Node] = None
        self._root_handle: Optional[str] = None
    
    @property
    def root(self) -> Optional[Node]:
        return self._root
    
    @property
    def root_handle(self) -> Optional[str]:
        return self._root_handle
    
    @property
    def nodes(self) -> Dict[str, Node]:
        return self._nodes
    
    def load(self, api_response: Dict[str, Any]) -> Node:
        """
        Load nodes from API response and build tree.
        
        Returns:
            Root node with full hierarchy
        """
        nodes_data = api_response.get('f', [])
        
        self._nodes.clear()
        self._root = None
        
        # First pass: create all nodes
        for data in nodes_data:
            node = self._create_node(data)
            if node:
                self._nodes[node.handle] = node
        
        # Second pass: build parent/child relationships
        for data in nodes_data:
            handle = data.get('h')
            parent_handle = data.get('p')
            
            if handle not in self._nodes:
                continue
            
            node = self._nodes[handle]
            
            if parent_handle and parent_handle in self._nodes:
                parent = self._nodes[parent_handle]
                node.parent = parent
                if node not in parent.children:
                    parent.children.append(node)
        
        return self._root
    
    def _create_node(self, data: Dict[str, Any]) -> Optional[Node]:
        """Create a single node from API data."""
        try:
            handle = data.get('h', '')
            node_type = data.get('t', 0)
            
            # Skip inbox and trash
            if node_type in (self.NODE_TYPE_INBOX, self.NODE_TYPE_TRASH):
                return None
            
            # Decrypt key (full 32 bytes for files)
            key = self._decryptor.decrypt_node_key(data, self._master_key)
            
            # Decrypt attributes
            attrs = self._decryptor.decrypt_attributes(data, key)
            name = attrs.get('n', handle)
            
            # Handle root folder
            if node_type == self.NODE_TYPE_ROOT:
                name = "Cloud Drive"
                self._root_handle = handle
            
            node = Node(
                handle=handle,
                name=name,
                size=data.get('s', 0),
                is_folder=(node_type in (self.NODE_TYPE_FOLDER, self.NODE_TYPE_ROOT)),
                parent_handle=data.get('p'),
                key=key,
                fa=data.get('fa'),
                attributes=FileAttributes.from_dict(attrs),
                _client=self._client,
                _raw=data
            )
            
            if node_type == self.NODE_TYPE_ROOT:
                self._root = node
            
            return node
        except Exception:
            return None
    
    def get(self, handle: str) -> Optional[Node]:
        """Get node by handle."""
        return self._nodes.get(handle)
    
    def find_by_name(self, name: str) -> Optional[Node]:
        """Find first node matching name."""
        for node in self._nodes.values():
            if node.name == name:
                return node
        return None
    
    def find_by_path(self, path: str) -> Optional[Node]:
        """Find node by path from root."""
        if not self._root or not path:
            return self._root
        
        if path == "/":
            return self._root
        
        return self._root.find(path.lstrip("/"))
    
    def all_files(self) -> List[Node]:
        """Get all files (flat list)."""
        return [n for n in self._nodes.values() if n.is_file]
    
    def all_folders(self) -> List[Node]:
        """Get all folders (flat list)."""
        return [n for n in self._nodes.values() if n.is_folder]
    
    def add_node(self, node: Node) -> None:
        """
        Add a node to the tree and update parent-child relationships.
        
        This method should be called after creating a new node (via create_folder,
        upload, etc.) to ensure it's properly integrated into the tree structure.
        
        Args:
            node: Node to add to the tree
        """
        if not node or not node.handle:
            return
        
        # Add to nodes dictionary
        self._nodes[node.handle] = node
        
        # Update parent-child relationship if parent exists
        if node.parent_handle:
            parent_node = self._nodes.get(node.parent_handle)
            if parent_node:
                node.parent = parent_node
                if node not in parent_node.children:
                    parent_node.children.append(node)