"""Centralized key decryption for MEGA nodes."""
import json
from typing import Dict, Any, Optional, Tuple
from Crypto.Cipher import AES
from ..crypto import Base64Encoder


class KeyDecryptor:
    """
    Single source of truth for key decryption.
    
    Handles both file keys (32 bytes) and folder keys (16 bytes).
    Returns the FULL decrypted key (32 bytes for files) for media attributes.
    """
    
    def __init__(self):
        self._encoder = Base64Encoder()
    
    def decrypt_node_key(
        self,
        node: Dict[str, Any],
        master_key: bytes
    ) -> Optional[bytes]:
        """
        Decrypt node key from API response.
        
        Returns:
            Full 32-byte key for files (needed for media attributes)
            16-byte key for folders
        """
        key_str = node.get('k', '')
        if not key_str or ':' not in key_str:
            return None
        
        try:
            _, encrypted_b64 = key_str.split(':', 1)
            encrypted = self._encoder.decode(encrypted_b64)
            
            cipher = AES.new(master_key, AES.MODE_ECB)
            decrypted = cipher.decrypt(encrypted)
            
            # Return full key (32 bytes for files, 16 for folders)
            return decrypted
            
        except Exception:
            return None
    
    def get_file_key(self, full_key: bytes) -> bytes:
        """
        Get 16-byte file key for AES encryption/decryption.
        
        For 32-byte keys, XORs two halves.
        For 16-byte keys, returns as-is.
        """
        if len(full_key) >= 32:
            return bytes(a ^ b for a, b in zip(full_key[:16], full_key[16:32]))
        return full_key[:16]
    
    def decrypt_attributes(
        self,
        node: Dict[str, Any],
        key: bytes
    ) -> Dict[str, Any]:
        """Decrypt node attributes (name, custom attrs, etc.)."""
        attrs_b64 = node.get('a', '')
        if not attrs_b64 or not key:
            return {'n': node.get('h', 'Unknown')}
        
        try:
            file_key = self.get_file_key(key)
            attrs_bytes = self._encoder.decode(attrs_b64)
            
            cipher = AES.new(file_key, AES.MODE_CBC, iv=b'\x00' * 16)
            decrypted = cipher.decrypt(attrs_bytes)
            
            if decrypted.startswith(b'MEGA'):
                end = 4
                while end < len(decrypted) and decrypted[end] != 0:
                    end += 1
                json_str = decrypted[4:end].decode('utf-8', errors='ignore')
                return json.loads(json_str)
            
        except Exception:
            pass
        
        return {'n': node.get('h', 'Unknown')}
