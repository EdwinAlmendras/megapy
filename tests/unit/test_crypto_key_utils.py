"""Tests for key management utilities."""
import pytest
from megapy.core.crypto.utils.key_utils import KeyManager


class TestKeyManager:
    """Test suite for KeyManager."""
    
    def test_prepare_bytes_key(self):
        """Test preparing a bytes key."""
        key = b"0123456789abcdef"
        result = KeyManager.prepare(key)
        
        assert result == key
        assert isinstance(result, bytes)
    
    def test_prepare_base64_string_key(self):
        """Test preparing a base64 encoded string key."""
        import base64
        original = b"0123456789abcdef"
        encoded = base64.b64encode(original).decode()
        
        result = KeyManager.prepare(encoded)
        
        assert result == original
        assert isinstance(result, bytes)
    
    def test_unmerge_key_mac_32_bytes(self):
        """Test unmerging a 32-byte key+MAC."""
        merged_key = bytes(range(32))
        result = KeyManager.unmerge_key_mac(merged_key)
        
        assert len(result) == 32
        # First 16 bytes should be XOR of original first 16 and second 16
        for i in range(16):
            expected = merged_key[i] ^ merged_key[16 + i]
            assert result[i] == expected
    
    def test_unmerge_key_mac_short_key(self):
        """Test unmerging a key shorter than 32 bytes."""
        short_key = bytes(range(24))
        result = KeyManager.unmerge_key_mac(short_key)
        
        assert len(result) == 32
    
    def test_unmerge_key_mac_16_bytes(self):
        """Test unmerging a 16-byte key."""
        key_16 = bytes(range(16))
        result = KeyManager.unmerge_key_mac(key_16)
        
        assert len(result) == 32
    
    def test_merge_key_mac(self):
        """Test merging key and MAC."""
        key = b"0123456789abcdef"
        mac = b"MAC_VALUE_12345"
        
        result = KeyManager.merge_key_mac(key, mac)
        
        assert result == key + mac
        assert len(result) == len(key) + len(mac)
    
    def test_unmerge_key_mac_deterministic(self):
        """Test unmerging is deterministic."""
        key = b"test_key_1234567890abcdef"
        
        result1 = KeyManager.unmerge_key_mac(key)
        result2 = KeyManager.unmerge_key_mac(key)
        
        assert result1 == result2
    
    def test_xor_operation_correctness(self):
        """Test XOR operation in unmerge is correct."""
        # Create a known key where we can verify XOR
        key = b"\x00" * 16 + b"\xff" * 16
        result = KeyManager.unmerge_key_mac(key)
        
        # XOR of 0x00 and 0xFF should be 0xFF
        assert result[:16] == b"\xff" * 16


class TestKeyManagerEdgeCases:
    """Edge case tests for KeyManager."""
    
    def test_prepare_empty_bytes(self):
        """Test preparing empty bytes."""
        result = KeyManager.prepare(b"")
        assert result == b""
    
    def test_unmerge_empty_key(self):
        """Test unmerging empty key."""
        result = KeyManager.unmerge_key_mac(b"")
        assert len(result) == 32
        assert result == b"\x00" * 32
    
    def test_unmerge_very_long_key(self):
        """Test unmerging key longer than 32 bytes."""
        long_key = bytes(range(64))
        result = KeyManager.unmerge_key_mac(long_key)
        
        assert len(result) == 32
        # Should only use first 32 bytes
        for i in range(16):
            expected = long_key[i] ^ long_key[16 + i]
            assert result[i] == expected
