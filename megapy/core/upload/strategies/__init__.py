"""Upload strategies module."""
from .chunking import MegaChunkingStrategy, FixedSizeChunkingStrategy
from .encryption import MegaEncryptionStrategy

__all__ = [
    'MegaChunkingStrategy',
    'FixedSizeChunkingStrategy',
    'MegaEncryptionStrategy',
]
