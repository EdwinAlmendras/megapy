"""
Attribute packing/unpacking for MEGA API.

Attributes are stored as:
- JSON object with "MEGA" prefix
- Padded to 16-byte boundary for encryption
"""
from __future__ import annotations
import json
from typing import Dict, Any, Optional, Union
from Crypto.Cipher import AES

from .models import FileAttributes


class AttributesPacker:
    """
    Pack and unpack file attributes for MEGA API.
    
    Format:
        MEGA{"n":"filename","e":{"i":"docid"}}
        
    Padded to 16-byte boundary with null bytes.
    """
    
    PREFIX = b'MEGA'
    
    @staticmethod
    def pack(
        attributes: Union[FileAttributes, Dict[str, Any]],
        key: bytes
    ) -> bytes:
        """
        Pack and encrypt attributes for upload.
        
        Args:
            attributes: FileAttributes or dict to pack
            key: 16-byte AES key for encryption
            
        Returns:
            Encrypted attributes bytes
        """
        # Convert to dict if needed
        if isinstance(attributes, FileAttributes):
            attrs_dict = attributes.to_dict()
        else:
            attrs_dict = attributes
        # Convert to JSON
        json_str = json.dumps(attrs_dict, separators=(',', ':'))
        # Add MEGA prefix
        data = AttributesPacker.PREFIX + json_str.encode('utf-8')
        padding_len = (16 - (len(data) % 16)) % 16
        if padding_len == 0:
            padding_len = 16  # Always add some padding
        data = data + (b'\x00' * padding_len)
        
        # Encrypt with AES-CBC
        cipher = AES.new(key[:16], AES.MODE_CBC, iv=b'\x00' * 16)
        encrypted = cipher.encrypt(data)
        
        return encrypted
    
    @staticmethod
    def unpack(
        encrypted: bytes,
        key: bytes
    ) -> Optional[FileAttributes]:
        """
        Decrypt and unpack attributes.
        
        Args:
            encrypted: Encrypted attributes bytes
            key: 16-byte AES key for decryption
            
        Returns:
            FileAttributes or None if decryption fails
        """
        # Decrypt
        cipher = AES.new(key[:16], AES.MODE_CBC, iv=b'\x00' * 16)
        decrypted = cipher.decrypt(encrypted)
        if not decrypted.startswith(AttributesPacker.PREFIX):
            raise ValueError("Invalid attributes prefix")
        
        # Remove prefix and null padding
        json_data = decrypted[4:]
        
        # Find end of JSON (null terminator)
        end = 0
        while end < len(json_data) and json_data[end] != 0:
            end += 1
        
        json_str = json_data[:end].decode('utf-8')
        
        # Parse JSON
        attrs_dict = json.loads(json_str)
        return FileAttributes.from_dict(attrs_dict)
            
    
    @staticmethod
    def pack_raw(
        attrs_dict: Dict[str, Any]
    ) -> bytes:
        """
        Pack attributes without encryption (for testing).
        
        Args:
            attrs_dict: Attributes dictionary
            
        Returns:
            Packed bytes (not encrypted)
        """
        json_str = json.dumps(attrs_dict, separators=(',', ':'))
        data = AttributesPacker.PREFIX + json_str.encode('utf-8')
        
        # Pad to 16-byte boundary
        padding_len = (16 - (len(data) % 16)) % 16
        if padding_len == 0:
            padding_len = 16
        
        return data + (b'\x00' * padding_len)
    
    @staticmethod
    def unpack_raw(data: bytes) -> Optional[Dict[str, Any]]:
        """
        Unpack attributes without decryption (for testing).
        
        Args:
            data: Packed bytes (not encrypted)
            
        Returns:
            Attributes dictionary or None
        """
        try:
            if not data.startswith(AttributesPacker.PREFIX):
                return None
            
            # Remove prefix and null padding
            json_data = data[4:]
            
            end = 0
            while end < len(json_data) and json_data[end] != 0:
                end += 1
            
            json_str = json_data[:end].decode('utf-8')
            return json.loads(json_str)
            
        except Exception:
            return None
