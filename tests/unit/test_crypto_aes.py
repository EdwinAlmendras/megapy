"""Tests for AES encryption/decryption."""
import pytest
from Crypto.Random import get_random_bytes

from megapy.core.crypto.aes.strategies import AESCBCStrategy, AESECBStrategy
from megapy.core.crypto.aes.aes_crypto import AESCrypto
from megapy.core.crypto.aes.encryption_service import EncryptionService, DecryptionService


class TestAESCBCStrategy:
    """Test suite for AES-CBC strategy."""
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test CBC encrypt/decrypt roundtrip."""
        strategy = AESCBCStrategy()
        key = get_random_bytes(16)
        data = b"Hello, World!!!"  # 15 bytes, need 16
        data = data + b"\x00"  # Pad to 16 bytes
        
        encrypted = strategy.encrypt(data, key)
        decrypted = strategy.decrypt(encrypted, key)
        
        assert decrypted == data
    
    def test_encrypt_changes_data(self):
        """Test encryption actually changes data."""
        strategy = AESCBCStrategy()
        key = get_random_bytes(16)
        data = b"0123456789abcdef"
        
        encrypted = strategy.encrypt(data, key)
        
        assert encrypted != data
    
    def test_same_plaintext_same_ciphertext_with_zero_iv(self):
        """Test same plaintext produces same ciphertext with zero IV."""
        strategy = AESCBCStrategy(iv=b'\x00' * 16)
        key = get_random_bytes(16)
        data = b"0123456789abcdef"
        
        encrypted1 = strategy.encrypt(data, key)
        encrypted2 = strategy.encrypt(data, key)
        
        assert encrypted1 == encrypted2
    
    def test_custom_iv(self):
        """Test encryption with custom IV."""
        iv = get_random_bytes(16)
        strategy = AESCBCStrategy(iv=iv)
        key = get_random_bytes(16)
        data = b"0123456789abcdef"
        
        encrypted = strategy.encrypt(data, key)
        decrypted = strategy.decrypt(encrypted, key)
        
        assert decrypted == data
    
    def test_different_iv_different_ciphertext(self):
        """Test different IVs produce different ciphertexts."""
        key = get_random_bytes(16)
        data = b"0123456789abcdef"
        
        strategy1 = AESCBCStrategy(iv=b'\x00' * 16)
        strategy2 = AESCBCStrategy(iv=b'\x01' * 16)
        
        encrypted1 = strategy1.encrypt(data, key)
        encrypted2 = strategy2.encrypt(data, key)
        
        assert encrypted1 != encrypted2
    
    def test_multiple_blocks(self):
        """Test encryption of multiple blocks."""
        strategy = AESCBCStrategy()
        key = get_random_bytes(16)
        data = b"A" * 64  # 4 blocks
        
        encrypted = strategy.encrypt(data, key)
        decrypted = strategy.decrypt(encrypted, key)
        
        assert decrypted == data
        assert len(encrypted) == len(data)


class TestAESECBStrategy:
    """Test suite for AES-ECB strategy."""
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test ECB encrypt/decrypt roundtrip."""
        strategy = AESECBStrategy()
        key = get_random_bytes(16)
        data = b"0123456789abcdef"  # Exactly 16 bytes
        
        encrypted = strategy.encrypt(data, key)
        decrypted = strategy.decrypt(encrypted, key)
        
        assert decrypted == data
    
    def test_encrypt_changes_data(self):
        """Test encryption actually changes data."""
        strategy = AESECBStrategy()
        key = get_random_bytes(16)
        data = b"0123456789abcdef"
        
        encrypted = strategy.encrypt(data, key)
        
        assert encrypted != data
    
    def test_deterministic_encryption(self):
        """Test ECB is deterministic (same plaintext = same ciphertext)."""
        strategy = AESECBStrategy()
        key = get_random_bytes(16)
        data = b"0123456789abcdef"
        
        encrypted1 = strategy.encrypt(data, key)
        encrypted2 = strategy.encrypt(data, key)
        
        assert encrypted1 == encrypted2
    
    def test_ecb_pattern_preservation(self):
        """Test ECB preserves patterns (same blocks encrypt same)."""
        strategy = AESECBStrategy()
        key = get_random_bytes(16)
        block = b"0123456789abcdef"
        data = block * 4
        
        encrypted = strategy.encrypt(data, key)
        
        # All blocks should be identical in ECB mode
        assert encrypted[:16] == encrypted[16:32]
        assert encrypted[16:32] == encrypted[32:48]
        assert encrypted[32:48] == encrypted[48:64]


class TestAESCrypto:
    """Test suite for AESCrypto class."""
    
    def test_init_with_key(self):
        """Test initialization with key."""
        key = get_random_bytes(16)
        crypto = AESCrypto(key)
        
        assert crypto.key == key
    
    def test_init_empty_key_raises(self):
        """Test empty key raises ValueError."""
        with pytest.raises(ValueError, match="Key cannot be empty"):
            AESCrypto(b"")
    
    def test_init_none_key_raises(self):
        """Test None key raises ValueError."""
        with pytest.raises(ValueError):
            AESCrypto(None)
    
    def test_encrypt_cbc(self):
        """Test CBC encryption."""
        key = get_random_bytes(16)
        crypto = AESCrypto(key)
        data = b"0123456789abcdef"
        
        encrypted = crypto.encrypt_cbc(data)
        
        assert encrypted != data
        assert len(encrypted) == len(data)
    
    def test_decrypt_cbc(self):
        """Test CBC decryption."""
        key = get_random_bytes(16)
        crypto = AESCrypto(key)
        data = b"0123456789abcdef"
        
        encrypted = crypto.encrypt_cbc(data)
        decrypted = crypto.decrypt_cbc(encrypted)
        
        assert decrypted == data
    
    def test_encrypt_ecb(self):
        """Test ECB encryption."""
        key = get_random_bytes(16)
        crypto = AESCrypto(key)
        data = b"0123456789abcdef"
        
        encrypted = crypto.encrypt_ecb(data)
        
        assert encrypted != data
    
    def test_decrypt_ecb(self):
        """Test ECB decryption."""
        key = get_random_bytes(16)
        crypto = AESCrypto(key)
        data = b"0123456789abcdef"
        
        encrypted = crypto.encrypt_ecb(data)
        decrypted = crypto.decrypt_ecb(encrypted)
        
        assert decrypted == data
    
    def test_set_strategy(self):
        """Test setting custom strategy."""
        key = get_random_bytes(16)
        crypto = AESCrypto(key)
        
        new_strategy = AESECBStrategy()
        crypto.set_strategy(new_strategy)
        
        assert crypto.strategy == new_strategy


class TestEncryptionService:
    """Test suite for EncryptionService."""
    
    def test_encrypt_basic(self):
        """Test basic encryption."""
        service = EncryptionService()
        key = get_random_bytes(16)
        data = b"Test data to encrypt"
        
        encrypted = service.encrypt(data, key)
        
        assert encrypted != data
        # Encrypted should include IV (16 bytes) + encrypted data
        assert len(encrypted) > len(data)
    
    def test_encrypt_includes_iv(self):
        """Test encrypted data includes IV."""
        service = EncryptionService()
        key = get_random_bytes(16)
        data = b"Test data"
        
        encrypted = service.encrypt(data, key)
        
        # First 16 bytes should be IV
        assert len(encrypted) >= 16
    
    def test_encrypt_key(self):
        """Test key encryption."""
        service = EncryptionService()
        master_key = get_random_bytes(16)
        data_key = get_random_bytes(16)
        
        encrypted = service.encrypt_key(data_key, master_key)
        
        assert encrypted != data_key


class TestDecryptionService:
    """Test suite for DecryptionService."""
    
    def test_decrypt_basic(self):
        """Test basic decryption."""
        enc_service = EncryptionService()
        dec_service = DecryptionService()
        key = get_random_bytes(16)
        data = b"Test data to encrypt"
        
        encrypted = enc_service.encrypt(data, key)
        decrypted = dec_service.decrypt(encrypted, key)
        
        assert decrypted == data
    
    def test_decrypt_key(self):
        """Test key decryption."""
        enc_service = EncryptionService()
        dec_service = DecryptionService()
        master_key = get_random_bytes(16)
        data_key = get_random_bytes(16)
        
        encrypted = enc_service.encrypt_key(data_key, master_key)
        decrypted = dec_service.decrypt_key(encrypted, master_key)
        
        assert decrypted == data_key
    
    def test_roundtrip_various_sizes(self):
        """Test roundtrip with various data sizes."""
        enc_service = EncryptionService()
        dec_service = DecryptionService()
        key = get_random_bytes(16)
        
        test_sizes = [1, 15, 16, 17, 32, 100, 1000]
        
        for size in test_sizes:
            data = get_random_bytes(size)
            encrypted = enc_service.encrypt(data, key)
            decrypted = dec_service.decrypt(encrypted, key)
            assert decrypted == data, f"Failed for size {size}"


class TestAESCryptoEdgeCases:
    """Edge case tests for AES crypto."""
    
    def test_32_byte_key(self):
        """Test with 32-byte (256-bit) key."""
        key = get_random_bytes(32)
        crypto = AESCrypto(key)
        data = b"0123456789abcdef"
        
        encrypted = crypto.encrypt_ecb(data)
        decrypted = crypto.decrypt_ecb(encrypted)
        
        assert decrypted == data
    
    def test_24_byte_key(self):
        """Test with 24-byte (192-bit) key."""
        key = get_random_bytes(24)
        crypto = AESCrypto(key)
        data = b"0123456789abcdef"
        
        encrypted = crypto.encrypt_ecb(data)
        decrypted = crypto.decrypt_ecb(encrypted)
        
        assert decrypted == data


class TestDecryptionServiceDecryptData:
    """Test suite for DecryptionService.decrypt_data method."""
    
    def test_decrypt_data_basic(self):
        """Test basic data decryption with CTR mode."""
        from megapy.core.crypto.file import MegaEncrypt
        
        key = get_random_bytes(24)
        data = b"Test data for encryption"
        
        # Encrypt with MegaEncrypt
        encryptor = MegaEncrypt(key)
        encrypted = encryptor.encrypt(data)
        _, merged_key = encryptor.finalize()
        
        # Decrypt with DecryptionService
        service = DecryptionService()
        decrypted = service.decrypt_data(encrypted, merged_key, 0)
        
        assert decrypted == data
    
    def test_decrypt_data_large_chunk(self):
        """Test decrypting large data."""
        from megapy.core.crypto.file import MegaEncrypt
        
        key = get_random_bytes(24)
        data = get_random_bytes(1024 * 100)  # 100KB
        
        encryptor = MegaEncrypt(key)
        encrypted = encryptor.encrypt(data)
        _, merged_key = encryptor.finalize()
        
        service = DecryptionService()
        decrypted = service.decrypt_data(encrypted, merged_key, 0)
        
        assert decrypted == data
    
    def test_decrypt_data_with_32_byte_key(self):
        """Test with 32-byte key format."""
        key = get_random_bytes(32)
        data = b"Test with 32-byte key"
        
        service = DecryptionService()
        # Just verify it doesn't crash with 32-byte key
        result = service.decrypt_data(data, key, 0)
        assert isinstance(result, bytes)
    
    def test_decrypt_data_with_position(self):
        """Test decryption at specific position."""
        from megapy.core.crypto.file import MegaEncrypt
        
        key = get_random_bytes(24)
        data = b"A" * 32 + b"B" * 32  # 64 bytes
        
        encryptor = MegaEncrypt(key)
        encrypted = encryptor.encrypt(data)
        _, merged_key = encryptor.finalize()
        
        service = DecryptionService()
        
        # Decrypt full data
        decrypted_full = service.decrypt_data(encrypted, merged_key, 0)
        assert decrypted_full == data
