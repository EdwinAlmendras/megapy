"""Centralized key decryption for MEGA nodes."""
import json
from typing import Dict, Any, Optional, Tuple
from Crypto.Cipher import AES
from megapy.core.utils import b64encode, b64decode
from megapy.core.attributes.packer import AttributesPacker
from megapy.core.crypto.aes import AESCrypto
from megapy.core.crypto import unmerge_key_mac, merge_key_mac


class KeyFileManager:
    """
    Single source of truth for key decryption.
    
    Handles both file keys (32 bytes) and folder keys (16 bytes).
    Returns the FULL decrypted key (32 bytes for files) for media attributes.
    """
    
    def __init__(self, key: bytes, master_key: bytes, mac: Optional[bytes] = None):
        self.key = key
        self.aes = AESCrypto(master_key)
        self.mac = mac
        
    @classmethod
    def from_full_key(cls, full_key: bytes, master_key: bytes) -> 'KeyFileManager':
        """Create a KeyFileManager from a full key (32 bytes)."""
        key, mac = full_key[:16], full_key[16:]
        return cls(key, master_key, mac)
    
    @classmethod
    def from_merged_key(cls, merged_key: bytes, master_key: bytes) -> 'KeyFileManager':
        """Create a KeyFileManager from a merged key (32 bytes)."""
        full_key = unmerge_key_mac(merged_key)
        key, mac = full_key[:16], full_key[16:]
        return cls(key, master_key, mac)


    @classmethod
    def parse_key(cls, key_str: str, master_key: bytes) -> 'KeyFileManager':
        """Parse key from MEGA API response.
        
        Args:
            key_str: Key string from MEGA API response
            
        Returns:
            KeyDecryptor
            
        File are 32 bytes long -> are key (16 bytes for AES-ECB + 16 bytes for MAC) this is XORed to get the file key
        Folder are 16 bytes long -> are key (16 bytes for AES-ECB)
        
        """
        key = cls._decrypt_key(key_str, master_key)
        if key is None:
            raise ValueError("Failed to decrypt key")
        if len(key) == 16:
            return cls(key, master_key)
        else:
            full_key = unmerge_key_mac(key)
            key, mac = full_key[:16], full_key[16:]
            return cls(key, master_key, mac)
    
    
    
    @staticmethod
    def _decrypt_key(
        key_str: str,
        master_key: bytes
    ) -> Optional[bytes]:
        """Decrypt key from MEGA API response."""
        _, encrypted_b64 = key_str.split(':', 1)
        encrypted = b64decode(encrypted_b64)
        decrypted = AESCrypto(master_key).decrypt_ecb(encrypted)
        return decrypted
    
    
    @property
    def full_key(self) -> bytes:
        """Get the full key (32 bytes for files, 16 for folders)."""
        if self.mac:
            return self.key + self.mac
        else:
            return self.key
    
    @property
    def mega_key(self) -> str:
        """
        Get the MEGA key as a string.
        
        For files (with MAC): Reconstructs MEGA format by applying XOR to first 16 bytes
        with the MAC, then encrypts the full 32 bytes with master_key using AES-ECB.
        
        For folders (no MAC): Encrypts the 16-byte key directly.
        
        Returns:
            Base64 URL-safe encoded encrypted key (without padding)
        """
        if self.mac is None:
            # Folder: just encrypt the 16-byte key
            return b64encode(self.aes.encrypt_ecb(self.key))
        else:
            # File: reconstruct MEGA format (inverse of unmerge_key_mac)
            # MEGA format: first 16 bytes are XORed with MAC, then MAC follows
            merged_key = bytearray(32)
            merged_key[16:32] = self.mac  # Last 16 bytes are MAC
            
            # Reconstruct first 16 bytes: key XOR mac (inverse of unmerge_key_mac)
            for i in range(16):
                merged_key[i] = self.key[i] ^ self.mac[i]
            
            return b64encode(self.aes.encrypt_ecb(bytes(merged_key)))
        
    def decrypt_attributes(
        self,
        attr: any,
    ) -> Dict[str, Any]:
        """Decrypt node attributes (name, custom attrs, etc.)."""
        return AttributesPacker.unpack(attr, self.key)
    
    def encrypt_attributes(
        self,
        attr: Dict[str, Any],
    ) -> str:
        """
        Encrypt node attributes (name, custom attrs, etc.).
        
        For files: Uses the first 16 bytes after applying unmerge_key_mac
        (same as AttributeService.encrypt does).
        
        For folders: Uses the 16-byte key directly.
        
        Returns:
            Base64-encoded encrypted attributes
        """
        # For files with MAC, we need to apply unmerge_key_mac to get the real key
        # This matches what AttributeService.encrypt does
        if self.mac:
            # Reconstruct full key in MEGA format, then apply unmerge_key_mac
            merged_key = bytearray(32)
            merged_key[16:32] = self.mac
            for i in range(16):
                merged_key[i] = self.key[i] ^ self.mac[i]
            
            # Apply unmerge_key_mac to get the real key for attributes
            key_for_attrs = unmerge_key_mac(bytes(merged_key))[:16]
        else:
            # Folder: use key directly
            key_for_attrs = self.key
        
        return b64encode(AttributesPacker.pack(attr, key_for_attrs))