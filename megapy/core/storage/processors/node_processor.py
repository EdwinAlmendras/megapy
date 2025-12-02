"""Node processor using Strategy Pattern."""
from typing import Dict, List, Any, Optional
from ..repository import NodeRepository
from ..decryptors import NodeKeyDecryptor, AttributeDecryptor
from .node_factory import NodeFactory


class NodeProcessor:
    """Processes MEGA file nodes."""
    
    NODE_TYPE_DRIVE = 2
    NODE_TYPE_INBOX = 3
    NODE_TYPE_RUBBISH_BIN = 4
    
    def __init__(
        self,
        repository: NodeRepository,
        key_decryptor: NodeKeyDecryptor,
        attr_decryptor: AttributeDecryptor,
        node_factory: NodeFactory = None
    ):
        """Initializes node processor."""
        self.repository = repository
        self.key_decryptor = key_decryptor
        self.attr_decryptor = attr_decryptor
        self.factory = node_factory or NodeFactory()
    
    def process_all(
        self,
        master_key: bytes,
        shared_keys: Optional[Dict[str, bytes]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Processes all nodes from repository."""
        nodes = self.repository.get_all_nodes()
        shared_keys = shared_keys or self.repository.get_shared_keys()
        
        return self.process_nodes(nodes, master_key, shared_keys)
    
    def process_nodes(
        self,
        nodes: List[Dict[str, Any]],
        master_key: bytes,
        shared_keys: Dict[str, bytes]
    ) -> Dict[str, Dict[str, Any]]:
        """Processes nodes list."""
        processed = {}
        
        for node in nodes:
            try:
                node_handle = node.get('h')
                if not node_handle:
                    continue
                
                # Handle special nodes
                node_type = node.get('t')
                if node_type == self.NODE_TYPE_DRIVE:
                    processed[node_handle] = self._create_special_node(
                        node_handle, 'Root', self.NODE_TYPE_DRIVE
                    )
                    continue
                elif node_type == self.NODE_TYPE_RUBBISH_BIN:
                    processed[node_handle] = self._create_special_node(
                        node_handle, 'Trash', self.NODE_TYPE_RUBBISH_BIN
                    )
                    continue
                elif node_type == self.NODE_TYPE_INBOX:
                    processed[node_handle] = self._create_special_node(
                        node_handle, 'Inbox', self.NODE_TYPE_INBOX
                    )
                    continue
                
                # Decrypt node key
                node_key = self.key_decryptor.decrypt(node, master_key, shared_keys)
                if not node_key:
                    continue
                
                # Decrypt attributes
                attributes = None
                if node.get('a'):
                    try:
                        attributes = self.attr_decryptor.decrypt(
                            node['a'],
                            node_key,
                            node_handle
                        )
                    except Exception:
                        attributes = {'n': node_handle}
                
                # Create node data
                node_data = self.factory.create_node_data(node, node_key, attributes)
                processed[node_handle] = node_data
                
            except Exception as e:
                continue
        
        return processed
    
    def _create_special_node(
        self,
        handle: str,
        name: str,
        node_type: int
    ) -> Dict[str, Any]:
        """Creates special node (root, trash, inbox)."""
        return {
            'handle': handle,
            'name': name,
            'type': node_type,
            'node_type': 1,  # Treat as folder for TreeBuilder
            'is_dir': True,
            'parent': None,
            'size': 0,
            'creation_date': 0,
            'owner': None,
            'key': None,
            'attributes': {'n': name}
        }

