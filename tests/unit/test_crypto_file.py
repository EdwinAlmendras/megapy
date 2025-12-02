"""Tests for file encryption/decryption."""
import pytest
from Crypto.Random import get_random_bytes

from megapy.core.crypto.file import MegaEncrypt, MegaDecrypt, merge_key_mac


class TestMegaEncrypt:
    """Test suite for MegaEncrypt."""
    
    @pytest.fixture
    def key(self):
        """Generate 24-byte encryption key."""
        return get_random_bytes(24)
    
    def test_init_with_valid_key(self, key):
        """Test initialization with valid key."""
        encryptor = MegaEncrypt(key)
        
        assert encryptor.key == key
        assert encryptor.aes_key == key[:16]
        assert encryptor.nonce == key[16:]
    
    def test_init_invalid_key_length(self):
        """Test initialization with invalid key length."""
        with pytest.raises(ValueError, match="Key must be 24 bytes"):
            MegaEncrypt(get_random_bytes(16))
    
    def test_encrypt_basic(self, key):
        """Test basic encryption."""
        encryptor = MegaEncrypt(key)
        data = b"Hello, World!"
        
        encrypted = encryptor.encrypt(data)
        
        assert encrypted != data
        assert len(encrypted) == len(data)
    
    def test_encrypt_changes_data(self, key):
        """Test encryption actually changes data."""
        encryptor = MegaEncrypt(key)
        data = b"Test data for encryption"
        
        encrypted = encryptor.encrypt(data)
        
        assert encrypted != data
    
    def test_encrypt_deterministic(self, key):
        """Test same key produces same output (CTR mode)."""
        data = b"Deterministic test"
        
        enc1 = MegaEncrypt(key)
        enc2 = MegaEncrypt(key)
        
        result1 = enc1.encrypt(data)
        result2 = enc2.encrypt(data)
        
        assert result1 == result2
    
    def test_finalize_returns_mac(self, key):
        """Test finalize returns MAC and merged key."""
        encryptor = MegaEncrypt(key)
        encryptor.encrypt(b"Some data")
        
        mac, merged = encryptor.finalize()
        
        assert len(mac) == 8
        assert len(merged) == 32  # 24 key + 8 mac
    
    def test_encrypt_multiple_chunks(self, key):
        """Test encrypting multiple chunks."""
        encryptor = MegaEncrypt(key)
        
        chunk1 = encryptor.encrypt(b"First chunk data")
        chunk2 = encryptor.encrypt(b"Second chunk")
        chunk3 = encryptor.encrypt(b"Third")
        
        assert chunk1 is not None
        assert chunk2 is not None
        assert chunk3 is not None
    
    def test_encrypt_large_data(self, key):
        """Test encrypting large data."""
        encryptor = MegaEncrypt(key)
        large_data = get_random_bytes(1024 * 1024)  # 1MB
        
        encrypted = encryptor.encrypt(large_data)
        
        assert len(encrypted) == len(large_data)


class TestMegaDecrypt:
    """Test suite for MegaDecrypt."""
    
    @pytest.fixture
    def key_with_mac(self):
        """Generate 32-byte key (24 key + 8 mac)."""
        return get_random_bytes(32)
    
    def test_init_with_valid_key(self, key_with_mac):
        """Test initialization with valid key."""
        decryptor = MegaDecrypt(key_with_mac)
        
        assert decryptor.key == key_with_mac[:24]
        assert decryptor.mac == key_with_mac[24:]
        assert decryptor.aes_key == key_with_mac[:16]
        assert decryptor.nonce == key_with_mac[16:24]
    
    def test_decrypt_basic(self, key_with_mac):
        """Test basic decryption."""
        decryptor = MegaDecrypt(key_with_mac)
        encrypted = get_random_bytes(100)
        
        decrypted = decryptor.decrypt(encrypted)
        
        assert len(decrypted) == len(encrypted)
    
    def test_finalize_returns_bool(self, key_with_mac):
        """Test finalize returns boolean."""
        decryptor = MegaDecrypt(key_with_mac)
        decryptor.decrypt(b"test data")
        
        result = decryptor.finalize()
        
        assert isinstance(result, bool)


class TestMegaEncryptDecryptRoundtrip:
    """Test encryption/decryption roundtrip."""
    
    def test_roundtrip_basic(self):
        """Test basic encrypt/decrypt roundtrip."""
        key = get_random_bytes(24)
        data = b"Test data for roundtrip"
        
        # Encrypt
        encryptor = MegaEncrypt(key)
        encrypted = encryptor.encrypt(data)
        mac, merged_key = encryptor.finalize()
        
        # Decrypt
        decryptor = MegaDecrypt(merged_key)
        decrypted = decryptor.decrypt(encrypted)
        
        assert decrypted == data
    
    def test_roundtrip_multiple_chunks(self):
        """Test roundtrip with multiple chunks."""
        key = get_random_bytes(24)
        chunks = [b"Chunk 1", b"Chunk 2", b"Chunk 3"]
        
        # Encrypt
        encryptor = MegaEncrypt(key)
        encrypted_chunks = [encryptor.encrypt(c) for c in chunks]
        mac, merged_key = encryptor.finalize()
        
        # Decrypt
        decryptor = MegaDecrypt(merged_key)
        decrypted_chunks = [decryptor.decrypt(c) for c in encrypted_chunks]
        
        assert decrypted_chunks == chunks
    
    def test_roundtrip_binary_data(self):
        """Test roundtrip with binary data."""
        key = get_random_bytes(24)
        data = bytes(range(256)) * 10
        
        encryptor = MegaEncrypt(key)
        encrypted = encryptor.encrypt(data)
        _, merged_key = encryptor.finalize()
        
        decryptor = MegaDecrypt(merged_key)
        decrypted = decryptor.decrypt(encrypted)
        
        assert decrypted == data
    
    def test_roundtrip_empty_data(self):
        """Test roundtrip with empty data."""
        key = get_random_bytes(24)
        data = b""
        
        encryptor = MegaEncrypt(key)
        encrypted = encryptor.encrypt(data)
        _, merged_key = encryptor.finalize()
        
        decryptor = MegaDecrypt(merged_key)
        decrypted = decryptor.decrypt(encrypted)
        
        assert decrypted == data
    
    def test_roundtrip_large_file(self):
        """Test roundtrip with large data (simulating file)."""
        key = get_random_bytes(24)
        data = get_random_bytes(5 * 1024 * 1024)  # 5MB
        
        encryptor = MegaEncrypt(key)
        encrypted = encryptor.encrypt(data)
        _, merged_key = encryptor.finalize()
        
        decryptor = MegaDecrypt(merged_key)
        decrypted = decryptor.decrypt(encrypted)
        
        assert decrypted == data


class TestMergeKeyMac:
    """Test merge_key_mac function."""
    
    def test_merge_basic(self):
        """Test basic key+MAC merging."""
        key = b"0123456789abcdef12345678"  # 24 bytes
        mac = b"MAC12345"  # 8 bytes
        
        result = merge_key_mac(key, mac)
        
        assert result == key + mac
        assert len(result) == 32
    
    def test_merge_empty(self):
        """Test merging empty values."""
        result = merge_key_mac(b"", b"")
        
        assert result == b""
