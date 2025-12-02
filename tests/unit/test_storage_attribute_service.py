"""Tests for attribute service."""
import pytest
import json
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

from megapy.core.storage.services.attribute_service import AttributeService
from megapy.core.crypto.utils.encoding import Base64Encoder
from megapy.core.crypto.utils.key_utils import KeyManager


class TestAttributeService:
    """Test suite for AttributeService."""
    
    @pytest.fixture
    def service(self):
        """Create service instance."""
        return AttributeService()
    
    @pytest.fixture
    def encoder(self):
        """Create encoder instance."""
        return Base64Encoder()
    
    @pytest.fixture
    def key_manager(self):
        """Create key manager instance."""
        return KeyManager()
    
    def _create_encrypted_attrs(self, attrs: dict, key: bytes, encoder, key_manager):
        """Helper to create encrypted attributes."""
        key_16 = key_manager.unmerge_key_mac(key)[:16]
        attr_str = 'MEGA' + json.dumps(attrs)
        
        # Pad to 16-byte boundary
        if len(attr_str) % 16:
            attr_str += '\x00' * (16 - len(attr_str) % 16)
        
        aes = AES.new(key_16, AES.MODE_CBC, b'\x00' * 16)
        encrypted = aes.encrypt(attr_str.encode('utf-8'))
        return encoder.encode(encrypted)
    
    def test_decrypt_basic_attributes(self, service, encoder, key_manager):
        """Test decrypting basic attributes."""
        attrs = {'n': 'test_file.txt'}
        key = get_random_bytes(32)
        encrypted = self._create_encrypted_attrs(attrs, key, encoder, key_manager)
        
        result = service.decrypt(encrypted, key)
        
        assert result['name'] == 'test_file.txt'
        assert result['n'] == 'test_file.txt'
    
    def test_decrypt_with_label(self, service, encoder, key_manager):
        """Test decrypting attributes with label."""
        attrs = {'n': 'important.doc', 'lbl': 2}
        key = get_random_bytes(32)
        encrypted = self._create_encrypted_attrs(attrs, key, encoder, key_manager)
        
        result = service.decrypt(encrypted, key)
        
        assert result['label'] == 2
        assert result['label_name'] == 'orange'
    
    def test_decrypt_with_favorite(self, service, encoder, key_manager):
        """Test decrypting attributes with favorite flag."""
        attrs = {'n': 'favorite.pdf', 'fav': 1}
        key = get_random_bytes(32)
        encrypted = self._create_encrypted_attrs(attrs, key, encoder, key_manager)
        
        result = service.decrypt(encrypted, key)
        
        assert result['is_fav'] is True
    
    def test_decrypt_invalid_prefix_raises(self, service, encoder, key_manager):
        """Test decryption fails without MEGA prefix."""
        key = get_random_bytes(32)
        key_16 = key_manager.unmerge_key_mac(key)[:16]
        
        # Create invalid attributes (no MEGA prefix)
        invalid_str = 'INVALID' + json.dumps({'n': 'test'})
        if len(invalid_str) % 16:
            invalid_str += '\x00' * (16 - len(invalid_str) % 16)
        
        aes = AES.new(key_16, AES.MODE_CBC, b'\x00' * 16)
        encrypted = aes.encrypt(invalid_str.encode('utf-8'))
        encoded = encoder.encode(encrypted)
        
        with pytest.raises(ValueError, match="MEGA NOT VALID ATTRS"):
            service.decrypt(encoded, key)
    
    def test_encrypt_basic_attributes(self, service, encoder, key_manager):
        """Test encrypting basic attributes."""
        attrs = {'name': 'new_file.txt'}
        key = get_random_bytes(32)
        
        encrypted = service.encrypt(attrs, key, 0)
        
        # Should be able to decrypt it back
        decrypted = service.decrypt(encrypted, key)
        assert decrypted['name'] == 'new_file.txt'
    
    def test_encrypt_decrypt_roundtrip(self, service):
        """Test encrypt/decrypt roundtrip."""
        key = get_random_bytes(32)
        original = {'name': 'roundtrip.txt', 'label': 3, 'is_fav': True}
        
        encrypted = service.encrypt(original, key, 0)
        decrypted = service.decrypt(encrypted, key)
        
        assert decrypted['name'] == 'roundtrip.txt'
        assert decrypted['label'] == 3
        assert decrypted['is_fav'] is True
    
    def test_parse_attributes(self, service):
        """Test parsing raw attributes."""
        raw = {'n': 'file.txt', 'lbl': 1, 'fav': 1}
        
        result = service.parse(raw)
        
        assert result['n'] == 'file.txt'
        assert result['name'] == 'file.txt'
        assert result['label'] == 1
        assert result['label_name'] == 'red'
        assert result['is_fav'] is True
    
    def test_parse_empty_attributes(self, service):
        """Test parsing empty attributes."""
        raw = {}
        
        result = service.parse(raw)
        
        assert result['n'] == ''
        assert result['name'] == ''
        assert result['label'] == 0
        assert result['is_fav'] is False
    
    def test_unparse_attributes(self, service):
        """Test unparsing to raw format."""
        attrs = {'name': 'file.txt', 'label': 2, 'is_fav': True}
        
        result = service.unparse(attrs)
        
        assert result['n'] == 'file.txt'
        assert result['lbl'] == 2
        assert result['fav'] == 1
    
    def test_unparse_minimal_attributes(self, service):
        """Test unparsing minimal attributes."""
        attrs = {'name': 'minimal.txt'}
        
        result = service.unparse(attrs)
        
        assert result == {'n': 'minimal.txt'}
        assert 'lbl' not in result
        assert 'fav' not in result
    
    def test_label_names(self, service):
        """Test all label names are correct."""
        expected = ['', 'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'grey']
        assert service.LABEL_NAMES == expected
    
    def test_decrypt_unicode_filename(self, service, encoder, key_manager):
        """Test decrypting unicode filename."""
        attrs = {'n': 'archivo_español_日本語.txt'}
        key = get_random_bytes(32)
        encrypted = self._create_encrypted_attrs(attrs, key, encoder, key_manager)
        
        result = service.decrypt(encrypted, key)
        
        assert result['name'] == 'archivo_español_日本語.txt'
    
    def test_decrypt_long_filename(self, service, encoder, key_manager):
        """Test decrypting long filename."""
        long_name = 'a' * 200 + '.txt'
        attrs = {'n': long_name}
        key = get_random_bytes(32)
        encrypted = self._create_encrypted_attrs(attrs, key, encoder, key_manager)
        
        result = service.decrypt(encrypted, key)
        
        assert result['name'] == long_name


class TestAttributeServiceEdgeCases:
    """Edge case tests for AttributeService."""
    
    @pytest.fixture
    def service(self):
        """Create service instance."""
        return AttributeService()
    
    def test_decrypt_with_16_byte_key(self, service):
        """Test decryption with 16-byte key."""
        encoder = Base64Encoder()
        key_manager = KeyManager()
        
        # 16-byte key - should still work after unmerge
        key = get_random_bytes(16)
        attrs = {'n': 'test.txt'}
        
        key_processed = key_manager.unmerge_key_mac(key)[:16]
        attr_str = 'MEGA' + json.dumps(attrs)
        if len(attr_str) % 16:
            attr_str += '\x00' * (16 - len(attr_str) % 16)
        
        aes = AES.new(key_processed, AES.MODE_CBC, b'\x00' * 16)
        encrypted = aes.encrypt(attr_str.encode('utf-8'))
        encoded = encoder.encode(encrypted)
        
        result = service.decrypt(encoded, key)
        
        assert result['name'] == 'test.txt'
    
    def test_encrypt_preserves_n_key(self, service):
        """Test encrypt uses 'n' key if 'name' not present."""
        key = get_random_bytes(32)
        attrs = {'n': 'via_n_key.txt'}
        
        encrypted = service.encrypt(attrs, key, 0)
        decrypted = service.decrypt(encrypted, key)
        
        assert decrypted['name'] == 'via_n_key.txt'
