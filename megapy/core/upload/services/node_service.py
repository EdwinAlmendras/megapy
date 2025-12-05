"""
Node creation service.

Handles creating file nodes in MEGA after upload.
"""
from typing import Dict, Any, Union, Optional
import logging
from ...crypto import Base64Encoder, AESCrypto


class NodeCreator:
    """
    Creates file nodes in MEGA after successful upload.
    
    Responsibilities:
    - Encrypt file attributes
    - Encrypt file key with master key
    - Create node via API
    
    Supports both sync and async API clients.
    """
    
    def __init__(self, api_client, master_key: bytes):
        """
        Initialize node creator.
        
        Args:
            api_client: MEGA API client (sync or async)
            master_key: Master encryption key
        """
        self._api = api_client
        self._master_key = master_key
        self._encoder = Base64Encoder()
        self._logger = logging.getLogger('megapy.upload.node')
    
    async def create_node(
        self,
        upload_token: str,
        target_id: str,
        file_key: bytes,
        attributes: Dict[str, Any],
        file_attributes: Optional[str] = None,
        replace_handle: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a file node in MEGA.
        
        Args:
            upload_token: Temporary upload handle from chunk upload
            target_id: Parent folder node ID
            file_key: File encryption key
            attributes: File attributes dict
            file_attributes: Optional file attributes string (fa) for thumbnails/previews
            replace_handle: Optional handle of existing file to replace (creates new version)
            
        Returns:
            API response with created node data
            
        Raises:
            ValueError: If node creation fails
        """
        node_data = self._prepare_node_data(
            upload_token, target_id, file_key, attributes, file_attributes, replace_handle
        )
        
        file_name = attributes.get('n', 'unknown')
        self._logger.debug(f"Creating node for file: {file_name}")
        
        # Support both sync and async clients
        if hasattr(self._api, '__aenter__') or hasattr(self._api.request, '__await__'):
            response = await self._api.request(node_data)
        else:
            response = self._api.request(node_data)
        
        if not response or isinstance(response, int):
            self._logger.error(f"Failed to create node: {response}")
            raise ValueError(f"Failed to create node: {response}")
        
        self._logger.debug("Node created successfully")
        return response
    
    def _prepare_node_data(
        self,
        upload_token: str,
        target_id: str,
        file_key: bytes,
        attributes: Dict[str, Any],
        file_attributes: Optional[str] = None,
        replace_handle: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare node data for API request.
        
        Args:
            upload_token: Upload handle
            target_id: Parent folder ID
            file_key: File key
            attributes: File attributes
            file_attributes: Optional fa string for thumbnails/previews
            replace_handle: Optional handle of file to replace (creates version)
            
        Returns:
            Node data dictionary
        """
        # Encrypt attributes with file key
        encrypted_attrs = self._encrypt_attributes(attributes, file_key)
        
        # Encrypt file key with master key
        encrypted_key = self._encrypt_key(file_key)
        
        node = {
            'h': upload_token,
            't': 0,  # file type
            'a': encrypted_attrs,
            'k': self._encoder.encode(encrypted_key)
        }
        
        # Add file attributes (thumbnail/preview) if provided
        if file_attributes:
            node['fa'] = file_attributes
        
        # Add old version handle for file versioning
        # When 'ov' is set, MEGA creates a new version and keeps the old file
        if replace_handle:
            node['ov'] = replace_handle
        
        return {
            'a': 'p',  # put command
            't': target_id,
            'n': [node]
        }
    
    def _encrypt_attributes(
        self, 
        attributes: Dict[str, Any], 
        file_key: bytes
    ) -> str:
        """
        Encrypt file attributes.
        
        Args:
            attributes: Attribute dictionary
            file_key: File encryption key
            
        Returns:
            Base64-encoded encrypted attributes
        """
        from ...storage.services import AttributeService
        
        attr_service = AttributeService()
        return attr_service.encrypt(attributes, file_key, node_type=0)
    
    def _encrypt_key(self, file_key: bytes) -> bytes:
        """
        Encrypt file key with master key.
        
        Args:
            file_key: File encryption key
            
        Returns:
            Encrypted key
        """
        aes = AESCrypto(self._master_key)
        return aes.encrypt_ecb(file_key)
