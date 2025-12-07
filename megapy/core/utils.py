import base64


def b64encode(data: bytes) -> str:
    """Encodes bytes to Base64 URL-safe without padding."""
    encoded = base64.b64encode(data).decode()
    encoded = encoded.replace('+', '-').replace('/', '_')
    encoded = encoded.rstrip('=')
    return encoded

def b64decode(data: str) -> bytes:
    """Decodes Base64 URL-safe (with or without padding)."""
    data = data.replace('-', '+').replace('_', '/')
    padding = len(data) % 4
    if padding:
        data += '=' * (4 - padding)
    return base64.b64decode(data)