"""Node key decryption using Strategy Pattern."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from Crypto.Cipher import AES
from ...crypto import Base64Encoder, DecryptionService


class NodeKeyDecryptor(ABC):
    """Abstract node key decryptor."""
    
    @abstractmethod
    def decrypt(
        self,
        node_data: Dict[str, Any],
        master_key: bytes,
        shared_keys: Dict[str, bytes]
    ) -> Optional[bytes]:
        """Decrypts node key."""
        pass


class StandardNodeKeyDecryptor(NodeKeyDecryptor):
    """Standard node key decryption strategy."""
    
    def __init__(self, decryption_service: DecryptionService = None):
        """Initializes decryptor."""
        self.decryption_service = decryption_service or DecryptionService()
        self.encoder = Base64Encoder()
    
    def decrypt(
        self,
        node_data: Dict[str, Any],
        master_key: bytes,
        shared_keys: Dict[str, bytes]
    ) -> Optional[bytes]:
        """Decrypts node key using master key or shared keys."""
        if 'k' not in node_data:
            return None
        
        key_parts = node_data['k'].split(':')
        if len(key_parts) < 2:
            return None
        
        handle = key_parts[0]
        encrypted_key = self.encoder.decode(key_parts[1])
        node_key = None
        
        # Try master key first
        if handle == node_data.get('u'):
            try:
                aes = AES.new(master_key, AES.MODE_ECB)
                node_key = aes.decrypt(encrypted_key)
            except Exception:
                pass
        
        # Try shared key if master key failed
        if not node_key and handle in shared_keys:
            try:
                node_key = self.decryption_service.decrypt_key(
                    encrypted_key,
                    shared_keys[handle]
                )
            except Exception:
                pass
        
        return node_key

