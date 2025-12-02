"""Key management utilities."""
import base64
from typing import Union


class KeyManager:
    """Manages encryption keys."""
    
    @staticmethod
    def prepare(key: Union[str, bytes]) -> bytes:
        """Prepares a key, converting string to bytes if necessary."""
        if isinstance(key, str):
            return base64.b64decode(key)
        return key
    
    @staticmethod
    def unmerge_key_mac(merged_key: bytes) -> bytes:
        """Separates key and MAC from Mega's combined format."""
        new_key = bytearray(32)
        copy_len = min(len(merged_key), 32)
        new_key[:copy_len] = merged_key[:copy_len]
        
        for i in range(16):
            new_key[i] = new_key[i] ^ new_key[16 + i]
        
        return bytes(new_key)
    
    @staticmethod
    def merge_key_mac(key: bytes, mac: bytes) -> bytes:
        """Combines encryption key and MAC."""
        return key + mac
