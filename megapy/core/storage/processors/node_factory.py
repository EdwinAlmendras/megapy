"""Node factory using Factory Pattern."""
from typing import Dict, Any, Optional
from ...crypto import Base64Encoder


class NodeFactory:
    """Factory for creating node objects."""
    
    def __init__(self):
        """Initializes factory."""
        self.encoder = Base64Encoder()
    
    def create_node_data(
        self,
        node: Dict[str, Any],
        node_key: Optional[bytes],
        attributes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Creates node data structure."""
        node_handle = node.get('h')
        node_type = node.get('t', 0)
        
        node_data = {
            'handle': node_handle,
            'parent': node.get('p') or None,
            'node_type': node_type,
            'type': node_type,
            'is_dir': (node_type == 1),
            'size': node.get('s', 0),
            'creation_date': node.get('ts', 0),
            'owner': node.get('u') or None,
            'key': self.encoder.encode(node_key) if node_key else None,
        }
        
        if attributes:
            node_data['attributes'] = attributes
            node_data['name'] = attributes.get('n', node_handle)
        else:
            node_data['name'] = node_handle
        
        return node_data

