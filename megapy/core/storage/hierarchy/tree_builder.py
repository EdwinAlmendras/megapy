"""Tree builder using Builder Pattern."""
from typing import Dict, Optional, Any
from ..models import Node, FileNode, FolderNode


class TreeBuilder:
    """Builds node tree from flat dictionary."""
    
    def build(self, nodes: Dict[str, Dict[str, Any]]) -> Optional[Node]:
        """Builds tree structure from flat nodes dictionary."""
        if not nodes:
            return None
        
        # Create node objects
        node_objects: Dict[str, Node] = {}
        
        for handle, node_data in nodes.items():
            node_type = node_data.get('node_type', node_data.get('type', 0))
            
            if node_type == 1:  # Folder
                node = FolderNode(
                    api_client=None,
                    handle=handle,
                    parent_handle=node_data.get('parent'),
                    node_type=node_type,
                    size=node_data.get('size', 0),
                    creation_date=node_data.get('creation_date', 0),
                    owner=node_data.get('owner'),
                    key=node_data.get('key'),
                    attributes=node_data.get('attributes', {})
                )
            else:  # File
                node = FileNode(
                    api_client=None,
                    handle=handle,
                    parent_handle=node_data.get('parent'),
                    node_type=node_type,
                    size=node_data.get('size', 0),
                    creation_date=node_data.get('creation_date', 0),
                    owner=node_data.get('owner'),
                    key=node_data.get('key'),
                    attributes=node_data.get('attributes', {})
                )
            
            node_objects[handle] = node
        
        # Build parent-child relationships
        roots = []
        for handle, node in node_objects.items():
            if node.parent_handle and node.parent_handle in node_objects:
                parent = node_objects[node.parent_handle]
                parent.add_child(node)
            elif node.parent_handle is None:
                roots.append(node)
        
        # Find the main root (Cloud Drive, type=2)
        # Priority: type 2 (Root) > type 3 (Inbox) > type 4 (Trash) > others
        if not roots:
            return None
        
        # Get original type from node_data
        main_root = None
        for r in roots:
            node_data = nodes.get(r.handle, {})
            original_type = node_data.get('type', 0)
            if original_type == 2:  # NODE_TYPE_DRIVE
                main_root = r
                break
        
        if not main_root:
            main_root = roots[0]
        
        return main_root
    
    def build_from_flat(self, nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Node]:
        """Builds tree and returns all nodes as dictionary."""
        root = self.build(nodes)
        if not root:
            return {}
        
        # Collect all nodes
        all_nodes = {}
        self._collect_nodes(root, all_nodes)
        return all_nodes
    
    def _collect_nodes(self, node: Node, collection: Dict[str, Node]):
        """Collects all nodes recursively."""
        collection[node.handle] = node
        for child in node.get_children():
            self._collect_nodes(child, collection)

