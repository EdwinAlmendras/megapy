"""Centralized key decryption for MEGA nodes."""
import json
from typing import Dict, Any, Optional, Tuple
from Crypto.Cipher import AES
from ..crypto import Base64Encoder, unmerge_key_mac, merge_key_mac
from megapy.core.attributes.packer import AttributesPacker
import logging

logger = logging.getLogger(__name__)

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
        master_key: bytes,
        share_keys: Optional[Dict[str, bytes]] = None
    ) -> Optional[bytes]:
        """
        Decrypt node key from API response.
        
        Handles multiple id:key pairs separated by '/' (for shared nodes).
        Similar to mega.js mutable-file.mjs lines 22-44.
        
        The 'k' field can contain:
        - Single pair: "userId:encryptedKey"
        - Multiple pairs: "userId1:key1/userId2:key2" (for shared nodes)
        
        Priority:
        1. Try to decrypt with master_key if id matches current user
        2. Try to decrypt with share_keys if id is in share_keys
        
        Args:
            node: Node data from API response
            master_key: Master encryption key for current user
            share_keys: Optional dict mapping share handles to their keys
        
        Returns:
            Full 32-byte key for files (needed for media attributes)
            16-byte key for folders
        """
        key_str = node.get('k', '')
        if not key_str:
            return None
        
        share_keys = share_keys or {}
        user_id = node.get('u')  # Current user ID
        user_key = None
        share_key = None
        # Handle multiple id:key pairs separated by '/'
        if '/' in key_str:
            id_key_pairs = key_str.split('/')
            
            for id_key_pair in id_key_pairs:
                if ':' not in id_key_pair:
                    continue
                
                id_part, encrypted_b64 = id_key_pair.split(':', 1)
                # First, try if it's the current user's key
                if id_part == user_id:
                    encrypted = self._encoder.decode(encrypted_b64)
                    cipher = AES.new(master_key, AES.MODE_ECB)
                    decrypted = cipher.decrypt(encrypted)
                    logger.info(f"Decrypted from user key {self._encoder.encode(decrypted)}")
                    user_key = decrypted
                # Then, try if there's a shareKey for this id

                share_id = id_part
                encrypted = self._encoder.decode(encrypted_b64)
                cipher = AES.new(master_key, AES.MODE_ECB)
                decrypted = cipher.decrypt(encrypted)
                logger.info(f"Decrypted from shared key : {self._encoder.encode(decrypted)}")
                share_key = decrypted
                return user_key, share_key
        else:
            # Single id:key pair (original behavior)
            if ':' not in key_str:
                return None, None
            
            try:
                id_part, encrypted_b64 = key_str.split(':', 1)
                encrypted = self._encoder.decode(encrypted_b64)
                
                user_key = None
                # Try master key first (if id matches user)
                if id_part == user_id:
                    cipher = AES.new(master_key, AES.MODE_ECB)
                    decrypted = cipher.decrypt(encrypted)
                    user_key = decrypted
                
                share_key = None
                # Try share key
                if id_part in share_keys:
                    share_key = share_keys[id_part]
                    cipher = AES.new(share_key, AES.MODE_ECB)
                    decrypted = cipher.decrypt(encrypted)
                    share_key = decrypted
                return user_key, share_key
                    
            except Exception:
                pass
        
        return None, None
            
    
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
        

