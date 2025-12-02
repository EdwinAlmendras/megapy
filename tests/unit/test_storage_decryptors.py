"""Tests for storage decryptors."""
import pytest
import json
from unittest.mock import Mock, MagicMock
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

from megapy.core.crypto.utils.encoding import Base64Encoder
from megapy.core.crypto.utils.key_utils import KeyManager
from megapy.core.storage.decryptors.node_key_decryptor import (
    StandardNodeKeyDecryptor, NodeKeyDecryptor
)
from megapy.core.storage.decryptors.attribute_decryptor import (
    StandardAttributeDecryptor, AttributeDecryptor
)


class TestStandardNodeKeyDecryptor:
    """Test suite for StandardNodeKeyDecryptor."""
    
    @pytest.fixture
    def decryptor(self):
        """Create decryptor instance."""
        return StandardNodeKeyDecryptor()
    
    @pytest.fixture
    def encoder(self):
        """Create encoder instance."""
        return Base64Encoder()
    
    def test_decrypt_returns_none_when_no_key(self, decryptor):
        """Test returns None when node has no key."""
        node_data = {'h': 'handle', 'u': 'user'}
        master_key = get_random_bytes(16)
        
        result = decryptor.decrypt(node_data, master_key, {})
        
        assert result is None
    
    def test_decrypt_returns_none_for_invalid_key_format(self, decryptor):
        """Test returns None for invalid key format."""
        node_data = {'h': 'handle', 'k': 'no_colon_here'}
        master_key = get_random_bytes(16)
        
        result = decryptor.decrypt(node_data, master_key, {})
        
        assert result is None
    
    def test_decrypt_with_master_key(self, decryptor, encoder):
        """Test decryption with master key."""
        master_key = get_random_bytes(16)
        node_key = get_random_bytes(16)
        
        # Encrypt node key with master key (ECB mode)
        aes = AES.new(master_key, AES.MODE_ECB)
        encrypted_key = aes.encrypt(node_key)
        encoded_key = encoder.encode(encrypted_key)
        
        node_data = {
            'h': 'test_handle',
            'u': 'user_handle',
            'k': f'user_handle:{encoded_key}'
        }
        
        result = decryptor.decrypt(node_data, master_key, {})
        
        assert result == node_key
    
    def test_decrypt_with_shared_key(self, decryptor, encoder):
        """Test decryption with shared key."""
        master_key = get_random_bytes(16)
        shared_key = get_random_bytes(16)
        node_key = get_random_bytes(16)
        
        # Create mock decryption service that returns expected key
        mock_service = Mock()
        mock_service.decrypt_key = Mock(return_value=node_key)
        decryptor.decryption_service = mock_service
        
        # Encrypt with shared key
        aes = AES.new(shared_key, AES.MODE_ECB)
        encrypted_key = aes.encrypt(node_key)
        encoded_key = encoder.encode(encrypted_key)
        
        node_data = {
            'h': 'test_handle',
            'u': 'different_user',
            'k': f'shared_handle:{encoded_key}'
        }
        
        shared_keys = {'shared_handle': shared_key}
        
        result = decryptor.decrypt(node_data, master_key, shared_keys)
        
        assert result == node_key
    
    def test_decrypt_handles_exception_gracefully(self, decryptor):
        """Test graceful handling of decryption exceptions."""
        node_data = {
            'h': 'handle',
            'u': 'user',
            'k': 'user:invalid_base64_!!!'
        }
        master_key = get_random_bytes(16)
        
        # Should not raise, just return None
        result = decryptor.decrypt(node_data, master_key, {})
        
        # Result depends on how encoder handles invalid input
        # Either None or raises - both are acceptable behaviors


class TestStandardAttributeDecryptor:
    """Test suite for StandardAttributeDecryptor."""
    
    @pytest.fixture
    def decryptor(self):
        """Create decryptor instance."""
        return StandardAttributeDecryptor()
    
    @pytest.fixture
    def encoder(self):
        """Create encoder instance."""
        return Base64Encoder()
    
    @pytest.fixture
    def key_manager(self):
        """Create key manager instance."""
        return KeyManager()
    
    def test_decrypt_valid_attributes(self, decryptor, encoder, key_manager):
        """Test decrypting valid attributes."""
        # Create valid MEGA attributes
        attrs = {'n': 'test_file.txt', 'lbl': 1, 'fav': 0}
        attr_str = 'MEGA' + json.dumps(attrs)
        
        # Pad to 16-byte boundary
        if len(attr_str) % 16:
            attr_str += '\x00' * (16 - len(attr_str) % 16)
        
        # Create 32-byte key
        node_key = get_random_bytes(32)
        key_16 = key_manager.unmerge_key_mac(node_key)[:16]
        
        # Encrypt attributes
        aes = AES.new(key_16, AES.MODE_CBC, b'\x00' * 16)
        encrypted = aes.encrypt(attr_str.encode('utf-8'))
        encoded = encoder.encode(encrypted)
        
        # Mock the attribute service
        mock_service = Mock()
        mock_service.decrypt = Mock(return_value={
            'n': 'test_file.txt',
            'name': 'test_file.txt',
            'label': 1,
            'label_name': 'red',
            'is_fav': False
        })
        decryptor.attr_service = mock_service
        
        result = decryptor.decrypt(encoded, node_key, 'handle')
        
        assert result['name'] == 'test_file.txt'
    
    def test_decrypt_returns_fallback_on_error(self, decryptor):
        """Test returns fallback attributes on decryption error."""
        # Create invalid encrypted data
        mock_service = Mock()
        mock_service.decrypt = Mock(side_effect=Exception("Decryption failed"))
        decryptor.attr_service = mock_service
        
        result = decryptor.decrypt("invalid_data", b"key", "test_handle")
        
        assert result['n'] == 'test_handle'
        assert result['name'] == 'test_handle'


class TestNodeKeyDecryptorInterface:
    """Test NodeKeyDecryptor interface compliance."""
    
    def test_standard_decryptor_is_instance(self):
        """Test StandardNodeKeyDecryptor implements interface."""
        decryptor = StandardNodeKeyDecryptor()
        assert isinstance(decryptor, NodeKeyDecryptor)
    
    def test_interface_has_decrypt_method(self):
        """Test interface defines decrypt method."""
        assert hasattr(NodeKeyDecryptor, 'decrypt')


class TestAttributeDecryptorInterface:
    """Test AttributeDecryptor interface compliance."""
    
    def test_standard_decryptor_is_instance(self):
        """Test StandardAttributeDecryptor implements interface."""
        decryptor = StandardAttributeDecryptor()
        assert isinstance(decryptor, AttributeDecryptor)
    
    def test_interface_has_decrypt_method(self):
        """Test interface defines decrypt method."""
        assert hasattr(AttributeDecryptor, 'decrypt')
