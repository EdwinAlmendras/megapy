"""
Chunking strategies for file uploads.

Implements Strategy Pattern for different chunking algorithms.
Open for extension (new strategies), closed for modification.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple
from ..protocols import ChunkingStrategy


class BaseChunkingStrategy(ABC):
    """Abstract base class for chunking strategies."""
    
    @abstractmethod
    def calculate_chunks(self, file_size: int) -> List[Tuple[int, int]]:
        """Calculate chunk boundaries."""
        pass


class MegaChunkingStrategy(BaseChunkingStrategy):
    """
    MEGA's specific chunking strategy.
    
    MEGA uses specific chunk boundaries:
    0 / 128K / 384K / 768K / 1280K / 1920K / 2688K / 3584K / 4608K / 
    ... (each additional 1024 KB) / EOF
    """
    
    # Initial chunk boundaries in bytes
    INITIAL_BOUNDARIES = [
        0,
        128 * 1024,    # 128K
        384 * 1024,    # 384K
        768 * 1024,    # 768K
        1280 * 1024,   # 1280K
        1920 * 1024,   # 1920K
        2688 * 1024,   # 2688K
        3584 * 1024,   # 3584K
    ]
    
    # After 3584K, increment by 1024K
    REGULAR_INCREMENT = 1024 * 1024
    REGULAR_START = 4608 * 1024
    
    def calculate_chunks(self, file_size: int) -> List[Tuple[int, int]]:
        """
        Calculate chunk boundaries for a file.
        
        Args:
            file_size: Total file size in bytes
            
        Returns:
            List of (start, end) tuples
        """
        if file_size == 0:
            return []
        
        boundaries = self._get_boundaries(file_size)
        chunks = []
        
        for i in range(len(boundaries) - 1):
            if boundaries[i] < file_size:
                end = min(boundaries[i + 1], file_size)
                chunks.append((boundaries[i], end))
        
        return chunks
    
    def _get_boundaries(self, file_size: int) -> List[int]:
        """Generate all boundaries needed for file size."""
        boundaries = list(self.INITIAL_BOUNDARIES)
        
        current = self.REGULAR_START
        while current < file_size:
            boundaries.append(current)
            current += self.REGULAR_INCREMENT
        
        boundaries.append(file_size)
        return boundaries


class FixedSizeChunkingStrategy(BaseChunkingStrategy):
    """
    Simple fixed-size chunking strategy.
    
    Useful for testing or when MEGA-specific chunking is not required.
    """
    
    DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1MB
    
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE):
        """
        Initialize with chunk size.
        
        Args:
            chunk_size: Size of each chunk in bytes
        """
        if chunk_size <= 0:
            raise ValueError("Chunk size must be positive")
        self.chunk_size = chunk_size
    
    def calculate_chunks(self, file_size: int) -> List[Tuple[int, int]]:
        """
        Calculate fixed-size chunk boundaries.
        
        Args:
            file_size: Total file size in bytes
            
        Returns:
            List of (start, end) tuples
        """
        if file_size == 0:
            return []
        
        chunks = []
        position = 0
        
        while position < file_size:
            end = min(position + self.chunk_size, file_size)
            chunks.append((position, end))
            position = end
        
        return chunks
