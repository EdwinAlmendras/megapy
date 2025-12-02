"""Folder node implementation."""
from typing import List, Optional
from .node import Node
from ...api import APIClient


class FolderNode(Node):
    """Folder node with folder operations."""
    
    def __init__(self, api_client: Optional[APIClient] = None, **kwargs):
        """Initializes folder node."""
        # Convert 'type' to 'node_type' if present
        if 'type' in kwargs and 'node_type' not in kwargs:
            kwargs['node_type'] = kwargs.pop('type')
        kwargs.setdefault('node_type', 1)
        super().__init__(**kwargs)
        self.api = api_client
    
    def list_files(self) -> List[Node]:
        """Lists files in folder."""
        return [child for child in self._children if not child.is_dir]
    
    def list_folders(self) -> List[Node]:
        """Lists folders in folder."""
        return [child for child in self._children if child.is_dir]
    
    def mkdir(self, name: str) -> 'FolderNode':
        """Creates subfolder."""
        if not self.api:
            raise ValueError("API client required for mkdir")
        
        from ..services import AttributeService
        from ...crypto import EncryptionService
        import os
        
        attr_service = AttributeService()
        enc_service = EncryptionService()
        
        folder_key = os.urandom(16)
        encrypted_key = enc_service.encrypt_key(folder_key, self.api.master_key)
        encrypted_attrs = attr_service.encrypt({'name': name}, folder_key, 1)
        
        response = self.api.request({
            'a': 'p',
            't': self.handle,
            'n': [{
                'h': 'xxxxxxxx',
                't': 1,
                'a': encrypted_attrs,
                'k': self.encoder.encode(encrypted_key)
            }]
        })
        
        folder_handle = response['f'][0]['h']
        return FolderNode(
            handle=folder_handle,
            parent_handle=self.handle,
            node_type=1,
            attributes={'n': name, 'name': name},
            api_client=self.api
        )

