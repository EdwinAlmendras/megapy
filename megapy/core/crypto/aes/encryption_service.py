"""High-level encryption/decryption services."""
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from ..utils.key_utils import KeyManager


class EncryptionService:
    """High-level encryption service."""
    
    def __init__(self, key_manager: KeyManager = None):
        """Initializes encryption service."""
        self.key_manager = key_manager or KeyManager()
    
    def encrypt(self, data: bytes, key) -> bytes:
        """Encrypts data with AES-CBC."""
        key = self.key_manager.prepare(key)
        iv = get_random_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_data = pad(data if isinstance(data, bytes) else data.encode(), 16)
        encrypted = cipher.encrypt(padded_data)
        return iv + encrypted
    
    def encrypt_key(self, data_key: bytes, master_key) -> bytes:
        """Encrypts a key with master key."""
        return self.encrypt(data_key, master_key)


class DecryptionService:
    """High-level decryption service."""
    
    def __init__(self, key_manager: KeyManager = None):
        """Initializes decryption service."""
        self.key_manager = key_manager or KeyManager()
    
    def decrypt(self, data: bytes, key) -> bytes:
        """Decrypts data with AES-CBC."""
        key = self.key_manager.prepare(key)
        iv, encrypted = data[:16], data[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)
        return unpad(decrypted, 16)
    
    def decrypt_key(self, encrypted_key: bytes, master_key) -> bytes:
        """Decrypts a key with master key."""
        return self.decrypt(encrypted_key, master_key)
    
    def decrypt_data(self, data: bytes, key: bytes, position: int = 0) -> bytes:
        """
        Decrypts file data using AES-CTR mode (MEGA file encryption).
        
        Args:
            data: Encrypted data chunk
            key: Node key (32 bytes: 24 key + 8 mac from MegaEncrypt)
            position: Byte position in file (for CTR counter)
            
        Returns:
            Decrypted data
        """
        from Crypto.Util import Counter
        
        key = self.key_manager.prepare(key)
        
        # Extract AES key and nonce from merged key
        # MegaEncrypt produces: 24 bytes key (16 AES + 8 nonce) + 8 bytes MAC = 32 bytes
        if len(key) >= 32:
            aes_key = key[:16]
            nonce = key[16:24]
        elif len(key) >= 24:
            aes_key = key[:16]
            nonce = key[16:24]
        else:
            aes_key = key[:16]
            nonce = b'\x00' * 8
        
        # Calculate initial counter value based on position
        initial_value = position // 16
        
        ctr = Counter.new(
            64,
            prefix=nonce,
            initial_value=initial_value,
            allow_wraparound=False
        )
        
        cipher = AES.new(aes_key, AES.MODE_CTR, counter=ctr)
        
        # Handle partial block offset
        offset = position % 16
        if offset > 0:
            # Decrypt padding bytes and discard
            cipher.decrypt(b'\x00' * offset)
        
        return cipher.decrypt(data)

