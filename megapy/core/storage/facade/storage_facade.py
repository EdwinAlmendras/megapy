"""Storage Facade - main entry point."""
from typing import Dict, Optional, List
from ...api import APIClient
from ..services import AuthService
from ..repository import NodeRepository
from ..decryptors import StandardNodeKeyDecryptor, StandardAttributeDecryptor
from ..processors import NodeProcessor
from ..hierarchy import TreeBuilder, PathResolver
from ..models import Node, LoginResult, FileNode, FolderNode


class StorageFacade:
    """Main facade for storage operations."""
    
    def __init__(self, api_client: Optional[APIClient] = None):
        """Initializes storage facade."""
        self.api = api_client or APIClient()
        self.auth = AuthService(self.api)
        self.repository = NodeRepository(self.api)
        
        # Decryptors
        self.key_decryptor = StandardNodeKeyDecryptor()
        self.attr_decryptor = StandardAttributeDecryptor()
        
        # Processor
        self.processor = NodeProcessor(
            self.repository,
            self.key_decryptor,
            self.attr_decryptor
        )
        
        # Hierarchy
        self.tree_builder = TreeBuilder()
        self.path_resolver = PathResolver()
        
        # State
        self._master_key: Optional[bytes] = None
        self._root_node: Optional[Node] = None
        self._nodes: Dict[str, Node] = {}
    
    def login(self, email: str, password: str) -> LoginResult:
        """Logs in and initializes storage."""
        result = self.auth.login(email, password)
        self._master_key = result.master_key
        return result
    
    def resume(self, session):
        """Resumes session."""
        self.auth.resume(session)
        # Note: master_key should be stored/retrieved from session
    
    def load_nodes(self) -> Node:
        """Loads and builds node tree."""
        if not self._master_key:
            raise ValueError("Not logged in. Call login() first.")
        
        # Process nodes
        processed = self.processor.process_all(
            self._master_key,
            self.repository.get_shared_keys()
        )
        
        # Build tree
        self._root_node = self.tree_builder.build(processed)
        self._nodes = self.tree_builder.build_from_flat(processed)
        
        # Inject API client into nodes for operations
        for node in self._nodes.values():
            if isinstance(node, FileNode):
                node.api = self.api
            elif isinstance(node, FolderNode):
                node.api = self.api
        
        return self._root_node
    
    def get_root(self) -> Optional[Node]:
        """Gets root node."""
        return self._root_node
    
    def get_node(self, handle: str) -> Optional[Node]:
        """Gets node by handle."""
        return self._nodes.get(handle)
    
    def find_by_path(self, path: str) -> Optional[Node]:
        """Finds node by path."""
        if not self._root_node:
            return None
        return self.path_resolver.resolve_path(self._root_node, path)
    
    def list_folder(self, folder_handle: Optional[str] = None) -> List[Node]:
        """Lists folder contents."""
        if folder_handle:
            folder = self.get_node(folder_handle)
        else:
            folder = self._root_node
        
        if not folder or not folder.is_dir:
            return []
        
        return folder.get_children()
    
    def get_path(self, node: Node) -> str:
        """Gets full path for node."""
        return self.path_resolver.get_path(node)

