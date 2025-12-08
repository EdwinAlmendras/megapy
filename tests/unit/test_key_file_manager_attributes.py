"""Tests for KeyFileManager attribute encryption/decryption reversibility."""
import pytest
from Crypto.Random import get_random_bytes

from megapy.core.nodes.key import KeyFileManager
from megapy.core.utils import b64decode
from megapy.core.attributes.models import FileAttributes


class TestKeyFileManagerAttributes:
    """Test suite for KeyFileManager attribute encryption/decryption."""
    
    @pytest.fixture
    def master_key(self):
        """Create a master key for testing."""
        return get_random_bytes(16)
    
    @pytest.fixture
    def file_key(self):
        """Create a file key (32 bytes) for testing."""
        return get_random_bytes(32)
    
    @pytest.fixture
    def folder_key(self):
        """Create a folder key (16 bytes) for testing."""
        return get_random_bytes(16)
    
    def _test_encrypt_decrypt_roundtrip(self, manager: KeyFileManager, original_attrs: dict):
        """
        Helper method to test encrypt/decrypt roundtrip.
        
        Args:
            manager: KeyFileManager instance
            original_attrs: Original attributes dictionary to encrypt
            
        Returns:
            Tuple of (encrypted_str, decrypted_attrs, decrypted_dict)
        """
        # Encrypt
        encrypted_str = manager.encrypt_attributes(original_attrs)
        assert isinstance(encrypted_str, str), "encrypt_attributes should return a string"
        
        # Decrypt
        encrypted_bytes = b64decode(encrypted_str)
        decrypted_attrs = manager.decrypt_attributes(encrypted_bytes)
        
        # Verify decryption succeeded
        assert decrypted_attrs is not None, "decrypt_attributes should not return None"
        assert isinstance(decrypted_attrs, FileAttributes), "decrypt_attributes should return FileAttributes"
        
        # Convert to dict for comparison
        decrypted_dict = decrypted_attrs.to_dict()
        
        # Compare all original attributes with decrypted ones
        for key, value in original_attrs.items():
            assert key in decrypted_dict, f"Key '{key}' missing in decrypted attributes"
            assert decrypted_dict[key] == value, f"Value mismatch for key '{key}': expected {value}, got {decrypted_dict[key]}"
        
        return encrypted_str, decrypted_attrs, decrypted_dict
    
    def test_encrypt_decrypt_basic_attributes_file(self, master_key, file_key):
        """Test encrypt/decrypt roundtrip with basic attributes for file."""
        manager = KeyFileManager.from_full_key(file_key, master_key)
        original_attrs = {'n': 'test_file.txt'}
        
        # Use helper method to test roundtrip
        encrypted_str, decrypted_attrs, decrypted_dict = self._test_encrypt_decrypt_roundtrip(
            manager, original_attrs
        )
        
        # Additional assertions
        assert decrypted_attrs.name == 'test_file.txt'
    
    def test_encrypt_decrypt_basic_attributes_folder(self, master_key, folder_key):
        """Test encrypt/decrypt roundtrip with basic attributes for folder."""
        manager = KeyFileManager(folder_key, master_key)
        original_attrs = {'n': 'test_folder'}
        
        # Use helper method to test roundtrip
        encrypted_str, decrypted_attrs, decrypted_dict = self._test_encrypt_decrypt_roundtrip(
            manager, original_attrs
        )
        
        # Additional assertions
        assert decrypted_attrs.name == 'test_folder'
    
    def test_encrypt_decrypt_complex_attributes_file(self, master_key, file_key):
        """Test encrypt/decrypt roundtrip with complex attributes for file."""
        manager = KeyFileManager.from_full_key(file_key, master_key)
        
        original_attrs = {
            'n': 'video.mp4',
            't': 1699900000,
            'lbl': 2,
            'fav': 1,
            'm': 'mega_id_123'
        }
        
        # Use helper method to test roundtrip - it will compare all attributes
        encrypted_str, decrypted_attrs, decrypted_dict = self._test_encrypt_decrypt_roundtrip(
            manager, original_attrs
        )
    
    def test_encrypt_decrypt_unicode_filename(self, master_key, file_key):
        """Test encrypt/decrypt roundtrip with unicode filename."""
        manager = KeyFileManager.from_full_key(file_key, master_key)
        original_attrs = {'n': 'archivo_español_日本語.txt'}
        
        # Use helper method to test roundtrip
        encrypted_str, decrypted_attrs, decrypted_dict = self._test_encrypt_decrypt_roundtrip(
            manager, original_attrs
        )
        
        # Additional assertions
        assert decrypted_attrs.name == 'archivo_español_日本語.txt'
    
    def test_encrypt_decrypt_long_filename(self, master_key, file_key):
        """Test encrypt/decrypt roundtrip with long filename."""
        manager = KeyFileManager.from_full_key(file_key, master_key)
        
        long_name = 'a' * 200 + '.txt'
        original_attrs = {'n': long_name}
        
        # Use helper method to test roundtrip
        encrypted_str, decrypted_attrs, decrypted_dict = self._test_encrypt_decrypt_roundtrip(
            manager, original_attrs
        )
        
        # Additional assertions
        assert decrypted_attrs.name == long_name
    
    def test_encrypt_decrypt_with_custom_attributes(self, master_key, file_key):
        """Test encrypt/decrypt roundtrip with custom attributes."""
        manager = KeyFileManager.from_full_key(file_key, master_key)
        
        # Use known attributes and 'c' (checksum) which is supported
        original_attrs = {
            'n': 'custom_file.txt',
            'c': 'custom_checksum_value',
            't': 1699900000
        }
        
        # Encrypt
        encrypted_str = manager.encrypt_attributes(original_attrs)
        
        # Decrypt
        encrypted_bytes = b64decode(encrypted_str)
        decrypted_attrs = manager.decrypt_attributes(encrypted_bytes)
        
        # Verify roundtrip
        assert decrypted_attrs is not None
        decrypted_dict = decrypted_attrs.to_dict()
        assert decrypted_dict['n'] == original_attrs['n']
        # 'c' is stored as checksum attribute
        assert decrypted_attrs.c == original_attrs['c']
        assert decrypted_dict.get('t') == original_attrs['t']
    
    def test_encrypt_decrypt_empty_name(self, master_key, file_key):
        """Test encrypt/decrypt roundtrip with empty name."""
        manager = KeyFileManager.from_full_key(file_key, master_key)
        original_attrs = {'n': ''}
        
        # Use helper method to test roundtrip
        encrypted_str, decrypted_attrs, decrypted_dict = self._test_encrypt_decrypt_roundtrip(
            manager, original_attrs
        )
        
        # Additional assertions
        assert decrypted_attrs.name == ''
    
    def test_encrypt_decrypt_multiple_roundtrips(self, master_key, file_key):
        """Test multiple encrypt/decrypt roundtrips produce consistent results."""
        manager = KeyFileManager.from_full_key(file_key, master_key)
        
        original_attrs = {
            'n': 'multi_roundtrip.txt',
            't': 1699900000,
            'lbl': 3,
            'fav': 1
        }
        
        # Perform multiple roundtrips
        for _ in range(5):
            encrypted_str = manager.encrypt_attributes(original_attrs)
            encrypted_bytes = b64decode(encrypted_str)
            decrypted_attrs = manager.decrypt_attributes(encrypted_bytes)
            
            assert decrypted_attrs is not None
            decrypted_dict = decrypted_attrs.to_dict()
            assert decrypted_dict['n'] == original_attrs['n']
            assert decrypted_dict.get('t') == original_attrs['t']
            assert decrypted_dict.get('lbl') == original_attrs['lbl']
            assert decrypted_dict.get('fav') == original_attrs['fav']
    
    def test_encrypt_decrypt_different_keys_produce_different_encryption(
        self, master_key
    ):
        """Test that different keys produce different encrypted output."""
        key1 = get_random_bytes(32)
        key2 = get_random_bytes(32)
        
        manager1 = KeyFileManager.from_full_key(key1, master_key)
        manager2 = KeyFileManager.from_full_key(key2, master_key)
        
        original_attrs = {'n': 'same_file.txt'}
        
        encrypted1 = manager1.encrypt_attributes(original_attrs)
        encrypted2 = manager2.encrypt_attributes(original_attrs)
        
        # Encrypted outputs should be different
        assert encrypted1 != encrypted2
        
        # But both should decrypt to the same attributes
        decrypted1 = manager1.decrypt_attributes(b64decode(encrypted1))
        decrypted2 = manager2.decrypt_attributes(b64decode(encrypted2))
        
        assert decrypted1.name == decrypted2.name == 'same_file.txt'
    
    def test_encrypt_decrypt_wrong_key_fails(self, master_key):
        """Test that decrypting with wrong key fails."""
        key1 = get_random_bytes(32)
        key2 = get_random_bytes(32)
        
        manager1 = KeyFileManager.from_full_key(key1, master_key)
        manager2 = KeyFileManager.from_full_key(key2, master_key)
        
        original_attrs = {'n': 'test_file.txt'}
        
        # Encrypt with key1
        encrypted_str = manager1.encrypt_attributes(original_attrs)
        encrypted_bytes = b64decode(encrypted_str)
        
        # Try to decrypt with key2 (wrong key)
        # Should raise ValueError or return None/incorrect data
        try:
            decrypted_attrs = manager2.decrypt_attributes(encrypted_bytes)
            # If it doesn't raise, the name should be wrong or None
            if decrypted_attrs is None:
                assert True  # Expected - decryption failed
            else:
                # If it doesn't return None, the name should be wrong
                assert decrypted_attrs.name != original_attrs['n']
        except ValueError:
            # This is expected - decryption failed with wrong key
            assert True

