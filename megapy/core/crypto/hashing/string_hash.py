"""String hashing using AES-ECB."""
from Crypto.Cipher import AES
from ..utils.key_utils import KeyManager


class StringHasher:
    """Computes string hash using AES-ECB."""
    
    def __init__(self, key_manager: KeyManager = None):
        """Initializes string hasher."""
        self.key_manager = key_manager or KeyManager()
    
    def hash(self, string: str | bytes, key) -> bytes:
        """Computes string hash using AES-ECB."""
        key = self.key_manager.prepare(key)
        if isinstance(string, str):
            string = string.encode()
        
        cipher = AES.new(key, AES.MODE_ECB)
        h = b'\0' * 16
        
        for i in range(0, len(string), 16):
            block = string[i:i+16].ljust(16, b'\0')
            h = bytes(a ^ b for a, b in zip(h, cipher.encrypt(block)))
        
        return h

