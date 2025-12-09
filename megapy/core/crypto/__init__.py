"""Crypto module - refactored with SOLID principles and design patterns."""
from .utils import Base64Encoder, KeyManager
from .aes import AESCrypto, EncryptionService, DecryptionService
from .key_derivation import PasswordKeyDeriverV1, PasswordKeyDeriverV2
from .hashing import StringHasher, HashcashGenerator
from .rsa import RSAService, RSAKeyDecoder

# Compatibility layer - maintain old function-based API
_base64 = Base64Encoder()
_key_manager = KeyManager()
_encryption_service = EncryptionService()
_decryption_service = DecryptionService()
_string_hasher = StringHasher()
_hashcash = HashcashGenerator()
_rsa_service = RSAService()

# Export old function names for backward compatibility
def prepare_key(key):
    """Prepares a key (backward compatibility)."""
    return _key_manager.prepare(key)

def unmerge_key_mac(key):
    """Unmerges key and MAC (backward compatibility)."""
    return _key_manager.unmerge_key_mac(key)

def merge_key_mac(key, mac):
    """Merges key and MAC (backward compatibility)."""
    return _key_manager.merge_key_mac(key, mac)

class Base64:
    """Base64 encoder (backward compatibility)."""
    @staticmethod
    def encode(data: bytes) -> str:
        return _base64.encode(data)
    
    @staticmethod
    def decode(data: str) -> bytes:
        return _base64.decode(data)

def mega_encrypt(data, key):
    """Encrypts data with AES-CBC (backward compatibility)."""
    return _encryption_service.encrypt(data, key)

def mega_decrypt(data, key):
    """Decrypts data with AES-CBC (backward compatibility)."""
    return _decryption_service.decrypt(data, key)

def encrypt_key(data_key, master_key):
    """Encrypts a key with master key (backward compatibility)."""
    return _encryption_service.encrypt_key(data_key, master_key)

def decrypt_key(encrypted_key, master_key):
    """Decrypts a key with master key (backward compatibility)."""
    return _decryption_service.decrypt_key(encrypted_key, master_key)

def stringhash(string, key):
    """Computes string hash (backward compatibility)."""
    return _string_hasher.hash(string, key)

def generate_hashcash_token(challenge):
    """Generates hashcash token (backward compatibility)."""
    return _hashcash.generate_sync(challenge)

async def generate_hashcash_token_async(challenge):
    """Generates hashcash token asynchronously."""
    return await _hashcash.generate(challenge)

def mega_verify(data, signature, public_key):
    """Verifies data signature (backward compatibility)."""
    return _rsa_service.verify(data, signature, public_key)

def prepare_key_password_v1(password):
    """Prepares key from password v1 (backward compatibility)."""
    deriver = PasswordKeyDeriverV1()
    return deriver.derive(password)

def prepare_key_password_v2(password, salt):
    """Prepares key from password v2 (backward compatibility)."""
    deriver = PasswordKeyDeriverV2()
    return deriver.derive(password, salt)

def decrypt_with_rsa(privk: bytes, t: str) -> bytes:
    """Decrypts with RSA (backward compatibility)."""
    return _rsa_service.decrypt(privk, t)

# Import MPI helper (needed for RSA)
from .rsa import mpi_to_int

# Import AES helper functions (backward compatibility)
def aes_cbc_encrypt(key, data):
    """AES CBC encrypt (backward compatibility)."""
    from Crypto.Cipher import AES
    aes_cipher = AES.new(key, AES.MODE_CBC, b'\0' * 16)
    return aes_cipher.encrypt(data)

def aes_cbc_decrypt(data, key):
    """AES CBC decrypt (backward compatibility)."""
    from Crypto.Cipher import AES
    aes_cipher = AES.new(key, AES.MODE_CBC, b'\0' * 16)
    return aes_cipher.decrypt(data)

# Export all functions for backward compatibility
__all__ = [
    # New OOP classes
    'Base64Encoder',
    'KeyManager',
    'AESCrypto',
    'EncryptionService',
    'DecryptionService',
    'PasswordKeyDeriverV1',
    'PasswordKeyDeriverV2',
    'StringHasher',
    'HashcashGenerator',
    'RSAService',
    'RSAKeyDecoder',
    # Backward compatibility functions
    'mega_encrypt',
    'mega_decrypt',
    'mega_verify',
    'stringhash',
    'prepare_key',
    'prepare_key_password_v1',
    'prepare_key_password_v2',
    'encrypt_key',
    'decrypt_key',
    'generate_hashcash_token',
    'decrypt_with_rsa',
    'Base64',
    'aes_cbc_encrypt',
    'aes_cbc_decrypt',
    'unmerge_key_mac',
    'merge_key_mac',
    'mpi_to_int',
]

# Alias for compatibility
encrypt = mega_encrypt
decrypt = mega_decrypt
verify = mega_verify
