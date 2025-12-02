"""File node implementation."""
from typing import Optional
from .node import Node
from .file_operations import FileOperationsMixin
from ...api import APIClient


class FileNode(Node, FileOperationsMixin):
    """File node with download operations."""
    
    def __init__(self, api_client: Optional[APIClient] = None, **kwargs):
        """Initializes file node."""
        # Convert 'type' to 'node_type' if present
        if 'type' in kwargs and 'node_type' not in kwargs:
            kwargs['node_type'] = kwargs.pop('type')
        kwargs.setdefault('node_type', 0)
        Node.__init__(self, **kwargs)
        FileOperationsMixin.__init__(self, api_client)
    
    @property
    def link(self) -> str:
        """Gets public link to file."""
        import base64
        if not self.key:
            return ""
        key_bytes = self.encoder.decode(self.key) if isinstance(self.key, str) else self.key
        key_b64 = base64.b64encode(key_bytes).decode().rstrip('=')
        return f"https://mega.nz/file/{self.handle}#{key_b64}"

