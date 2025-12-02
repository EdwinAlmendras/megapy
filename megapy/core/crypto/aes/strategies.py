"""AES encryption strategies using Strategy Pattern."""
from abc import ABC, abstractmethod
from Crypto.Cipher import AES
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class AESStrategy(ABC):
    """Abstract base class for AES encryption strategies."""
    
    @abstractmethod
    def encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypts data using the strategy."""
        pass
    
    @abstractmethod
    def decrypt(self, data: bytes, key: bytes) -> bytes:
        """Decrypts data using the strategy."""
        pass


class AESCBCStrategy(AESStrategy):
    """AES-CBC encryption strategy."""
    
    def __init__(self, iv: bytes = None):
        """Initializes CBC strategy."""
        self.iv = iv or (b'\0' * 16)
    
    def encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypts data using AES-CBC mode."""
        cipher = AES.new(key, AES.MODE_CBC, self.iv)
        return cipher.encrypt(data)
    
    def decrypt(self, data: bytes, key: bytes) -> bytes:
        """Decrypts data using AES-CBC mode."""
        cipher = AES.new(key, AES.MODE_CBC, self.iv)
        return cipher.decrypt(data)


class AESECBStrategy(AESStrategy):
    """AES-ECB encryption strategy."""
    
    def encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypts data using AES-ECB mode."""
        cipher = Cipher(
            algorithms.AES(key),
            modes.ECB(),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        return encryptor.update(data) + encryptor.finalize()
    
    def decrypt(self, data: bytes, key: bytes) -> bytes:
        """Decrypts data using AES-ECB mode."""
        cipher = Cipher(
            algorithms.AES(key),
            modes.ECB(),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()

