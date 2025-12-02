"""
Node creator for MEGA uploads.

This module handles creating nodes in MEGA after file uploads.
"""
from typing import Dict, Any, Optional
from mega_py.upload.types.upload_types import FileAttributes, UploadToken, LoggerProtocol, ApiProtocol
from mega_py.crypto import Base64, unmerge_key_mac
from mega_py.attributes import Attributes
from mega_py.crypto import AESCrypto
class NodeCreator:
    """
    Handles creating nodes in MEGA after file uploads.
    
    This class is responsible for:
    - Preparing node data for the MEGA API
    - Encrypting file attributes
    - Encrypting file keys
    - Sending node creation requests to MEGA
    
    Attributes:
        api: MEGA API client
        master_key: Master encryption key
        logger: Logger instance
    """
    
    def __init__(
        self, 
        api: ApiProtocol, 
        master_key: bytes, 
        logger: LoggerProtocol = None
    ) -> None:
        """
        Initialize the node creator.
        
        Args:
            api: MEGA API client
            master_key: Master encryption key
            logger: Logger instance
        """
        self.api = api
        self.master_key = master_key
        self.logger = logger
    
    def prepare_node_data(
        self, 
        upload_token: UploadToken, 
        target_id: str, 
        final_key: bytes, 
        attributes: FileAttributes
    ) -> Dict[str, Any]:
        """
        Prepare data for creating a node in MEGA.
        
        Args:
            upload_token: Temporary upload handle
            target_id: Parent folder node ID
            final_key: File encryption key
            attributes: File attributes
            
        Returns:
            Dictionary of node data ready for API request
            
        Raises:
            ValueError: If unable to encrypt attributes or key
        """
        try:

            
            if self.logger:
                self.logger.debug(f"Preparing node data for upload token: {upload_token}")
            
            # Handle key format
            #unmerged_key = unmerge_key_mac(final_key)
            
            #unmerged_key = unmerge_key_mac(final_key)
            # Encrypt attributes and key
            aes = AESCrypto(self.master_key)
            encrypted_attrs = Attributes.encrypt(attributes, final_key, 0)  # 0 = file
            encrypted_key = aes.encrypt_ecb(final_key)
            
            # Build node data
            node_data = {
                'a': 'p',  # put
                't': target_id,  # target (parent)
                'n': [{  # node
                    'h': upload_token,  # handle
                    't': 0,  # type (0 = file)
                    'a': encrypted_attrs,  # attributes
                    'k': Base64.encode(encrypted_key)  # key
                }]
            }
            
            return node_data
            
        except Exception as e:
            error_msg = f"Error preparing node data: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            raise ValueError(error_msg)
    
    async def create_node(
        self, 
        upload_token: UploadToken, 
        target_id: str, 
        final_key: bytes, 
        attributes: FileAttributes
    ) -> Dict[str, Any]:
        """
        Create a node in MEGA after a successful upload.
        
        Args:
            upload_token: Temporary upload handle
            target_id: Parent folder node ID
            final_key: File encryption key
            attributes: File attributes
            
        Returns:
            API response data
            
        Raises:
            ValueError: If the node creation fails
        """
        if self.logger:
            self.logger.debug(f"Creating node for upload token: {upload_token}")
            
        try:
            # Prepare node data
            node_data = self.prepare_node_data(upload_token, target_id, final_key, attributes)
            
            # Send request to API
            response = self.api.request(node_data)
            
            if not response or isinstance(response, int):
                error_msg = f"Error creating node: {response}"
                if self.logger:
                    self.logger.error(error_msg)
                raise ValueError(error_msg)
                
            if self.logger:
                self.logger.debug("Node created successfully")
                
            return response
            
        except Exception as e:
            error_msg = f"Error creating node: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            raise ValueError(error_msg) 