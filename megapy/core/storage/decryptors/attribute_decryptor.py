"""Attribute decryption using Strategy Pattern."""
from abc import ABC, abstractmethod
from typing import Dict, Any
from Crypto.Cipher import AES
from ...crypto import Base64Encoder


class AttributeDecryptor(ABC):
    """Abstract attribute decryptor."""
    
    @abstractmethod
    def decrypt(
        self,
        attribute_data: str,
        node_key: bytes,
        node_handle: str
    ) -> Dict[str, Any]:
        """Decrypts node attributes."""
        pass


class StandardAttributeDecryptor(AttributeDecryptor):
    """Standard attribute decryption strategy."""
    
    def __init__(self, attribute_service=None):
        """Initializes decryptor."""
        from ..services import AttributeService
        self.attr_service = attribute_service or AttributeService()
    
    def decrypt(
        self,
        attribute_data: str,
        node_key: bytes,
        node_handle: str
    ) -> Dict[str, Any]:
        """Decrypts node attributes using node key."""
        try:
            return self.attr_service.decrypt(attribute_data, node_key)
        except Exception as e:
            return {"n": node_handle, "name": node_handle}

