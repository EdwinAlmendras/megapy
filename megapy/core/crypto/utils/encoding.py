"""Encoding utilities."""
import base64


class Base64Encoder:
    """Base64 URL-safe encoder/decoder."""
    
    @staticmethod
    def encode(data: bytes) -> str:
        """Encodes bytes to Base64 URL-safe without padding."""
        encoded = base64.b64encode(data).decode()
        encoded = encoded.replace('+', '-').replace('/', '_')
        encoded = encoded.rstrip('=')
        return encoded

    @staticmethod
    def decode(data: str) -> bytes:
        """Decodes Base64 URL-safe (with or without padding)."""
        data = data.replace('-', '+').replace('_', '/')
        padding = len(data) % 4
        if padding:
            data += '=' * (4 - padding)
        return base64.b64decode(data)
