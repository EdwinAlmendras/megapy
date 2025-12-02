"""Tests for chunking strategies."""
import pytest
from megapy.core.upload.strategies.chunking import (
    MegaChunkingStrategy,
    FixedSizeChunkingStrategy
)


class TestMegaChunkingStrategy:
    """Test suite for MegaChunkingStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy instance."""
        return MegaChunkingStrategy()
    
    def test_empty_file(self, strategy):
        """Test chunking empty file."""
        chunks = strategy.calculate_chunks(0)
        assert chunks == []
    
    def test_small_file(self, strategy):
        """Test chunking file smaller than first boundary."""
        chunks = strategy.calculate_chunks(100)
        
        assert len(chunks) == 1
        assert chunks[0] == (0, 100)
    
    def test_file_at_first_boundary(self, strategy):
        """Test file exactly at 128K boundary."""
        size = 128 * 1024
        chunks = strategy.calculate_chunks(size)
        
        assert len(chunks) == 1
        assert chunks[0] == (0, size)
    
    def test_file_between_boundaries(self, strategy):
        """Test file between first two boundaries."""
        size = 200 * 1024  # 200K
        chunks = strategy.calculate_chunks(size)
        
        assert len(chunks) == 2
        assert chunks[0] == (0, 128 * 1024)
        assert chunks[1] == (128 * 1024, size)
    
    def test_large_file_chunks(self, strategy):
        """Test chunking large file."""
        size = 10 * 1024 * 1024  # 10MB
        chunks = strategy.calculate_chunks(size)
        
        # Verify first chunk starts at 0
        assert chunks[0][0] == 0
        
        # Verify last chunk ends at file size
        assert chunks[-1][1] == size
        
        # Verify chunks are contiguous
        for i in range(len(chunks) - 1):
            assert chunks[i][1] == chunks[i + 1][0]
    
    def test_chunks_cover_entire_file(self, strategy):
        """Test that chunks cover entire file."""
        size = 5 * 1024 * 1024  # 5MB
        chunks = strategy.calculate_chunks(size)
        
        total_covered = sum(end - start for start, end in chunks)
        assert total_covered == size
    
    def test_mega_specific_boundaries(self, strategy):
        """Test MEGA's specific chunk boundaries."""
        # File size that spans multiple MEGA boundaries
        size = 4 * 1024 * 1024  # 4MB
        chunks = strategy.calculate_chunks(size)
        
        # First chunk should be 0-128K
        assert chunks[0] == (0, 128 * 1024)
        
        # Second chunk should be 128K-384K
        assert chunks[1] == (128 * 1024, 384 * 1024)
    
    def test_very_large_file(self, strategy):
        """Test chunking very large file."""
        size = 1024 * 1024 * 1024  # 1GB
        chunks = strategy.calculate_chunks(size)
        
        assert len(chunks) > 0
        assert chunks[-1][1] == size


class TestFixedSizeChunkingStrategy:
    """Test suite for FixedSizeChunkingStrategy."""
    
    def test_default_chunk_size(self):
        """Test default 1MB chunk size."""
        strategy = FixedSizeChunkingStrategy()
        assert strategy.chunk_size == 1024 * 1024
    
    def test_custom_chunk_size(self):
        """Test custom chunk size."""
        strategy = FixedSizeChunkingStrategy(chunk_size=512 * 1024)
        assert strategy.chunk_size == 512 * 1024
    
    def test_invalid_chunk_size(self):
        """Test invalid chunk size raises error."""
        with pytest.raises(ValueError):
            FixedSizeChunkingStrategy(chunk_size=0)
        
        with pytest.raises(ValueError):
            FixedSizeChunkingStrategy(chunk_size=-1)
    
    def test_empty_file(self):
        """Test chunking empty file."""
        strategy = FixedSizeChunkingStrategy()
        chunks = strategy.calculate_chunks(0)
        assert chunks == []
    
    def test_file_smaller_than_chunk(self):
        """Test file smaller than chunk size."""
        strategy = FixedSizeChunkingStrategy(chunk_size=1024)
        chunks = strategy.calculate_chunks(500)
        
        assert len(chunks) == 1
        assert chunks[0] == (0, 500)
    
    def test_file_exact_multiple(self):
        """Test file size exact multiple of chunk size."""
        strategy = FixedSizeChunkingStrategy(chunk_size=1000)
        chunks = strategy.calculate_chunks(3000)
        
        assert len(chunks) == 3
        assert chunks[0] == (0, 1000)
        assert chunks[1] == (1000, 2000)
        assert chunks[2] == (2000, 3000)
    
    def test_file_not_exact_multiple(self):
        """Test file size not exact multiple of chunk size."""
        strategy = FixedSizeChunkingStrategy(chunk_size=1000)
        chunks = strategy.calculate_chunks(2500)
        
        assert len(chunks) == 3
        assert chunks[0] == (0, 1000)
        assert chunks[1] == (1000, 2000)
        assert chunks[2] == (2000, 2500)
    
    def test_chunks_cover_entire_file(self):
        """Test that chunks cover entire file."""
        strategy = FixedSizeChunkingStrategy(chunk_size=1000)
        size = 5500
        chunks = strategy.calculate_chunks(size)
        
        total_covered = sum(end - start for start, end in chunks)
        assert total_covered == size
