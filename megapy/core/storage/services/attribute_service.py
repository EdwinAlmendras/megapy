"""Attribute encryption/decryption service."""
import json
from typing import Dict, Any, Optional
from Crypto.Cipher import AES
from ...crypto import Base64Encoder, KeyManager


class AttributeService:
    """Handles MEGA node attributes encryption/decryption."""
    
    FOLDER_KEY_SIZE = 16
    FILE_KEY_SIZE = 24
    LABEL_NAMES = ['', 'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'grey']
    
    def __init__(self, encoder: Base64Encoder = None, key_manager: KeyManager = None):
        """Initializes attribute service."""
        self.encoder = encoder or Base64Encoder()
        self.key_manager = key_manager or KeyManager()
    
    def decrypt(self, attr: str, key: bytes) -> Dict[str, Any]:
        """Decrypts node attributes."""
        key_16 = self.key_manager.unmerge_key_mac(key)[:16]
        aes = AES.new(key_16, AES.MODE_CBC, b'\0' * 16)
        bytes_attr = aes.decrypt(self.encoder.decode(attr))
        
        attr_str = bytes_attr.rstrip(b'\0').decode('utf-8', errors='ignore')
        
        if not attr_str.startswith('MEGA{"'):
            raise ValueError("MEGA NOT VALID ATTRS")
        
        try:
            raw_attrs = json.loads(attr_str[4:])
            return self.parse(raw_attrs)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in attributes: {e}")
    
    def encrypt(self, attr: Dict[str, Any], key: bytes, node_type: int) -> str:
        """Encrypts node attributes."""
        key_16 = self.key_manager.unmerge_key_mac(key)[:16]
        
        raw_attrs = self.unparse(attr)
        attr_bytes = ('MEGA' + json.dumps(raw_attrs)).encode('utf-8')
        
        if len(attr_bytes) % 16:
            attr_bytes += b'\0' * (16 - len(attr_bytes) % 16)
        
        aes = AES.new(key_16, AES.MODE_CBC, b'\0' * 16)
        encrypted_attr = aes.encrypt(attr_bytes)
        return self.encoder.encode(encrypted_attr)
    
    def parse(self, attr: Dict[str, Any]) -> Dict[str, Any]:
        """Converts from MEGA internal format to friendly format."""
        return {
            'n': attr.get('n', ''),
            'name': attr.get('n', ''),
            'label': attr.get('lbl', 0),
            'label_name': self.LABEL_NAMES[attr.get('lbl', 0)],
            'is_fav': bool(attr.get('fav')),
        }
    
    def unparse(self, attr: Dict[str, Any]) -> Dict[str, Any]:
        """Converts from friendly format to MEGA internal format."""
        result = {}
        
        # Name is required
        result['n'] = attr.get('name', attr.get('n', ''))
        
        # Label
        if 'label' in attr and attr['label']:
            result['lbl'] = attr['label']
        elif 'lbl' in attr and attr['lbl']:
            result['lbl'] = attr['lbl']
        
        # Favorite
        if attr.get('is_fav') or attr.get('fav'):
            result['fav'] = 1
        
        # Custom attributes (e object) - preserve as-is
        if 'e' in attr:
            result['e'] = attr['e']
        
        # Preserve any other unknown attributes
        for key, value in attr.items():
            if key not in ('n', 'name', 'lbl', 'label', 'fav', 'is_fav', 'e', 'label_name'):
                result[key] = value
        
        return result

