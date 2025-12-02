"""RSA encryption/decryption service."""
from cryptography.hazmat.primitives.asymmetric import rsa, padding as rsa_padding
from cryptography.hazmat.primitives import hashes
from .rsa_key_decoder import RSAKeyDecoder
from ..utils.encoding import Base64Encoder


class RSAService:
    """RSA encryption/decryption and verification service."""
    
    def __init__(self, key_decoder: RSAKeyDecoder = None):
        """Initializes RSA service."""
        self.key_decoder = key_decoder or RSAKeyDecoder()
        self.encoder = Base64Encoder()
    
    def decrypt(self, privk: bytes, encrypted_data: str) -> bytes:
        """Decrypts data using RSA private key."""
        from . import mpi_to_int
        bytes_data = self.encoder.decode(encrypted_data)
        encrypted_int = mpi_to_int(bytes_data)
        rsa_privk = self.key_decoder.decode(privk)
        decrypted_data = '%x' % rsa_privk._decrypt(encrypted_int)
        return decrypted_data
    
    def verify(self, data: bytes, signature: bytes, public_key: dict) -> bool:
        """Verifies data signature using RSA public key."""
        try:
            public_key_obj = rsa.RSAPublicNumbers(
                e=int(public_key['e'], 16),
                n=int(public_key['n'], 16)
            ).public_key()
            
            public_key_obj.verify(
                signature,
                data,
                rsa_padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

