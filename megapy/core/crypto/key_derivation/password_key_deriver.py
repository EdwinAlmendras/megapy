"""Password-based key derivation using Strategy Pattern."""
from abc import ABC, abstractmethod
from Crypto.Cipher import AES
import hashlib
from ..utils.encoding import Base64Encoder


class PasswordKeyDeriver(ABC):
    """Abstract base class for password-based key derivation."""
    
    @abstractmethod
    def derive(self, password: str | bytes, salt: bytes | None = None) -> bytes:
        """Derives a key from a password."""
        pass


class PasswordKeyDeriverV1(PasswordKeyDeriver):
    """Legacy password key derivation (v1)."""
    
    def derive(self, password: str | bytes, salt: bytes | None = None) -> bytes:
        """Derives key from password using legacy method."""
        if isinstance(password, str):
            password = password.encode()
        
        pkey = b'\0' * 16
        for i in range(65536):
            for j in range(0, len(password), 16):
                key = password[j:j+16].ljust(16, b'\0')
                pkey = bytes(a ^ b for a, b in zip(pkey, AES.new(key, AES.MODE_ECB).encrypt(pkey)))
        
        return pkey


class PasswordKeyDeriverV2(PasswordKeyDeriver):
    """Modern password key derivation using PBKDF2 (v2)."""
    
    def __init__(self, iterations: int = 100000, key_size: int = 32):
        """Initializes PBKDF2 key deriver."""
        self.iterations = iterations
        self.key_size = key_size
        self.encoder = Base64Encoder()
    
    def derive(self, password: str | bytes, salt: bytes | None = None) -> bytes:
        """Derives key from password using PBKDF2 with SHA-512."""
        if salt is None:
            raise ValueError("Salt is required for v2 key derivation")
        
        if isinstance(salt, str):
            salt = self.encoder.decode(salt)
        
        return hashlib.pbkdf2_hmac(
            'sha512',
            password if isinstance(password, bytes) else password.encode(),
            salt,
            self.iterations,
            self.key_size
        )

