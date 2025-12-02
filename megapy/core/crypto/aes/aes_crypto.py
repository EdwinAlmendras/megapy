"""AES crypto class using Strategy Pattern."""
from .strategies import AESStrategy, AESCBCStrategy, AESECBStrategy


class AESCrypto:
    """AES encryption class using Strategy Pattern."""
    
    def __init__(self, key: bytes, strategy: AESStrategy = None):
        """Initializes AES crypto with a key and optional strategy."""
        if not key:
            raise ValueError("Key cannot be empty")
        self.key = key
        self.strategy = strategy or AESCBCStrategy()
    
    def set_strategy(self, strategy: AESStrategy):
        """Sets the encryption strategy."""
        self.strategy = strategy
    
    def encrypt_cbc(self, data: bytes) -> bytes:
        """Encrypts data using CBC mode with master key."""
        return self.strategy.encrypt(data, self.key)
    
    def encrypt_ecb(self, data: bytes) -> bytes:
        """Encrypts data using ECB mode with master key."""
        ecb_strategy = AESECBStrategy()
        return ecb_strategy.encrypt(data, self.key)
    
    def decrypt_cbc(self, data: bytes) -> bytes:
        """Decrypts data using CBC mode with master key."""
        return self.strategy.decrypt(data, self.key)
    
    def decrypt_ecb(self, data: bytes) -> bytes:
        """Decrypts data using ECB mode with master key."""
        ecb_strategy = AESECBStrategy()
        return ecb_strategy.decrypt(data, self.key)

