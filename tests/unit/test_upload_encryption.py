"""Tests for encryption strategies."""
import pytest
from Crypto.Random import get_random_bytes
from megapy.core.upload.strategies.encryption import MegaEncryptionStrategy


class TestMegaEncryptionStrategy:
    """Test suite for MegaEncryptionStrategy."""
    
    def test_init_random_key(self):
        """Test initialization with random key."""
        strategy = MegaEncryptionStrategy()
        
        assert len(strategy.key) == 24
        assert isinstance(strategy.key, bytes)
    
    def test_init_custom_key(self):
        """Test initialization with custom key."""
        key = get_random_bytes(24)
        strategy = MegaEncryptionStrategy(key)
        
        assert strategy.key == key
    
    def test_init_invalid_key_length(self):
        """Test invalid key length raises error."""
        with pytest.raises(ValueError):
            MegaEncryptionStrategy(get_random_bytes(16))
    
    def test_encrypt_chunk(self):
        """Test basic chunk encryption."""
        strategy = MegaEncryptionStrategy()
        data = b"Hello, World!"
        
        encrypted = strategy.encrypt_chunk(0, data)
        
        assert encrypted != data
        assert len(encrypted) == len(data)
    
    def test_encrypt_deterministic(self):
        """Test same key produces same encryption."""
        key = get_random_bytes(24)
        data = b"Test data"
        
        strategy1 = MegaEncryptionStrategy(key)
        strategy2 = MegaEncryptionStrategy(key)
        
        encrypted1 = strategy1.encrypt_chunk(0, data)
        encrypted2 = strategy2.encrypt_chunk(0, data)
        
        assert encrypted1 == encrypted2
    
    def test_encrypt_sequential_order(self):
        """Test chunks must be encrypted sequentially."""
        strategy = MegaEncryptionStrategy()
        
        # First chunk OK
        strategy.encrypt_chunk(0, b"chunk 0")
        
        # Skip chunk 1, try chunk 2 - should fail
        with pytest.raises(ValueError, match="sequentially"):
            strategy.encrypt_chunk(2, b"chunk 2")
    
    def test_encrypt_multiple_chunks(self):
        """Test encrypting multiple chunks."""
        strategy = MegaEncryptionStrategy()
        
        encrypted_chunks = []
        for i in range(5):
            data = f"Chunk {i}".encode()
            encrypted = strategy.encrypt_chunk(i, data)
            encrypted_chunks.append(encrypted)
        
        # All should be different
        assert len(set(encrypted_chunks)) == 5
    
    def test_finalize_returns_key(self):
        """Test finalize returns 32-byte key."""
        strategy = MegaEncryptionStrategy()
        strategy.encrypt_chunk(0, b"test data")
        
        final_key = strategy.finalize()
        
        assert len(final_key) == 32
        assert isinstance(final_key, bytes)
    
    def test_finalize_deterministic(self):
        """Test finalize is deterministic for same data."""
        key = get_random_bytes(24)
        data = b"test data for finalization"
        
        strategy1 = MegaEncryptionStrategy(key)
        strategy1.encrypt_chunk(0, data)
        key1 = strategy1.finalize()
        
        strategy2 = MegaEncryptionStrategy(key)
        strategy2.encrypt_chunk(0, data)
        key2 = strategy2.finalize()
        
        assert key1 == key2
    
    def test_different_data_different_key(self):
        """Test different data produces different final key."""
        key = get_random_bytes(24)
        
        strategy1 = MegaEncryptionStrategy(key)
        strategy1.encrypt_chunk(0, b"data A")
        key1 = strategy1.finalize()
        
        strategy2 = MegaEncryptionStrategy(key)
        strategy2.encrypt_chunk(0, b"data B")
        key2 = strategy2.finalize()
        
        assert key1 != key2
    
    def test_large_chunk(self):
        """Test encrypting large chunk."""
        strategy = MegaEncryptionStrategy()
        large_data = get_random_bytes(1024 * 1024)  # 1MB
        
        encrypted = strategy.encrypt_chunk(0, large_data)
        
        assert len(encrypted) == len(large_data)
    
    def test_empty_chunk(self):
        """Test encrypting empty chunk."""
        strategy = MegaEncryptionStrategy()
        
        encrypted = strategy.encrypt_chunk(0, b"")
        
        assert encrypted == b""


class TestMegaEncryptionStrategyMAC:
    """Test MAC calculation in MegaEncryptionStrategy."""
    
    def test_mac_accumulation(self):
        """Test MAC is accumulated across chunks."""
        strategy = MegaEncryptionStrategy()
        
        # Encrypt multiple chunks
        for i in range(3):
            strategy.encrypt_chunk(i, f"chunk {i}".encode())
        
        key = strategy.finalize()
        
        # Key should be 32 bytes with MAC incorporated
        assert len(key) == 32
    
    def test_mac_order_matters(self):
        """Test that chunk order affects final MAC."""
        key = get_random_bytes(24)
        chunk1 = b"First chunk data"
        chunk2 = b"Second chunk data"
        
        # Order 1: chunk1 then chunk2
        strategy1 = MegaEncryptionStrategy(key)
        strategy1.encrypt_chunk(0, chunk1)
        strategy1.encrypt_chunk(1, chunk2)
        key1 = strategy1.finalize()
        
        # Order 2: chunk2 then chunk1 (different content at same indices)
        strategy2 = MegaEncryptionStrategy(key)
        strategy2.encrypt_chunk(0, chunk2)
        strategy2.encrypt_chunk(1, chunk1)
        key2 = strategy2.finalize()
        
        assert key1 != key2
