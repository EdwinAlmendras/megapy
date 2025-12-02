"""Base node class using Composite Pattern."""
from abc import ABC
from typing import Dict, Any, Optional, List
from ...crypto import Base64Encoder


class Node(ABC):
    """Base node class using Composite Pattern."""
    
    def __init__(
        self,
        handle: str,
        parent_handle: Optional[str] = None,
        node_type: int = 0,
        size: int = 0,
        creation_date: int = 0,
        owner: Optional[str] = None,
        key: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """Initializes node."""
        self.handle = handle
        self.parent_handle = parent_handle
        self.type = node_type
        self.size = size
        self.creation_date = creation_date
        self.owner = owner
        self.key = key
        self.attributes = attributes or {}
        self.name = self.attributes.get('n', handle)
        
        # Tree structure
        self._parent: Optional['Node'] = None
        self._children: List['Node'] = []
    
    @property
    def is_dir(self) -> bool:
        """Checks if node is directory."""
        return self.type == 1
    
    def get_parent(self) -> Optional['Node']:
        """Gets parent node."""
        return self._parent
    
    def get_children(self) -> List['Node']:
        """Gets child nodes."""
        return self._children.copy()
    
    def add_child(self, child: 'Node'):
        """Adds child node."""
        if child not in self._children:
            self._children.append(child)
            child._parent = self
    
    def remove_child(self, child: 'Node'):
        """Removes child node."""
        if child in self._children:
            self._children.remove(child)
            child._parent = None
    
    def get_path(self) -> str:
        """Gets node path."""
        if self._parent is None:
            return f"/{self.name}"
        return f"{self._parent.get_path()}/{self.name}"
    
    def find_child(self, name: str) -> Optional['Node']:
        """Finds child by name."""
        for child in self._children:
            if child.name == name:
                return child
        return None
    
    def find_by_path(self, path: str) -> Optional['Node']:
        """Finds node by path."""
        parts = [p for p in path.split('/') if p]
        if not parts:
            return self
        
        child = self.find_child(parts[0])
        if not child:
            return None
        
        if len(parts) == 1:
            return child
        
        return child.find_by_path('/'.join(parts[1:]))
    
    def rename(self, new_name: str):
        """Renames node."""
        self.name = new_name
        if 'n' not in self.attributes:
            self.attributes['n'] = new_name
        else:
            self.attributes['n'] = new_name
    
    def move(self, new_parent: 'Node'):
        """Moves node to new parent."""
        if self._parent:
            self._parent.remove_child(self)
        new_parent.add_child(self)
        self.parent_handle = new_parent.handle
    
    def update_attributes(self, attrs: Dict[str, Any]):
        """Updates node attributes."""
        self.attributes.update(attrs)
        if 'n' in attrs:
            self.name = attrs['n']
    
    def to_dict(self) -> Dict[str, Any]:
        """Converts node to dictionary."""
        return {
            'handle': self.handle,
            'parent': self.parent_handle,
            'type': self.type,
            'is_dir': self.is_dir,
            'size': self.size,
            'creation_date': self.creation_date,
            'owner': self.owner,
            'key': self.key,
            'name': self.name,
            'attributes': self.attributes
        }

