"""Path resolution for nodes."""
from typing import Optional
from ..models import Node


class PathResolver:
    """Resolves paths in node tree."""
    
    @staticmethod
    def resolve_path(root: Node, path: str) -> Optional[Node]:
        """Resolves path from root node."""
        if not path or path == '/':
            return root
        
        parts = [p for p in path.split('/') if p]
        current = root
        
        for part in parts:
            current = current.find_child(part)
            if not current:
                return None
        
        return current
    
    @staticmethod
    def get_path(node: Node) -> str:
        """Gets full path for node."""
        return node.get_path()

