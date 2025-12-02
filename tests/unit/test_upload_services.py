"""Tests for upload services."""
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import os

from megapy.core.upload.services import (
    FileValidator,
    AsyncFileReader,
    ChunkUploader
)


class TestFileValidator:
    """Test suite for FileValidator."""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return FileValidator()
    
    @pytest.fixture
    def temp_file(self):
        """Create temporary file for testing."""
        fd, path = tempfile.mkstemp()
        os.write(fd, b"test content")
        os.close(fd)
        yield Path(path)
        os.unlink(path)
    
    def test_validate_existing_file(self, validator, temp_file):
        """Test validating existing file."""
        path, size = validator.validate(temp_file)
        
        assert path == temp_file
        assert size == 12  # "test content"
    
    def test_validate_string_path(self, validator, temp_file):
        """Test validating string path."""
        path, size = validator.validate(str(temp_file))
        
        assert path == temp_file
    
    def test_validate_nonexistent_file(self, validator):
        """Test validating non-existent file."""
        with pytest.raises(FileNotFoundError):
            validator.validate(Path("/nonexistent/file.txt"))
    
    def test_validate_directory(self, validator):
        """Test validating directory raises error."""
        with pytest.raises(ValueError):
            validator.validate(Path(tempfile.gettempdir()))
    
    def test_validate_size_ok(self, validator):
        """Test size validation passes."""
        validator.validate_size(1000, max_size=2000)
    
    def test_validate_size_empty(self, validator):
        """Test empty file raises error."""
        with pytest.raises(ValueError, match="empty"):
            validator.validate_size(0)
    
    def test_validate_size_exceeds_max(self, validator):
        """Test exceeding max size raises error."""
        with pytest.raises(ValueError, match="exceeds"):
            validator.validate_size(2000, max_size=1000)


class TestAsyncFileReader:
    """Test suite for AsyncFileReader."""
    
    @pytest.fixture
    def reader(self):
        """Create reader instance."""
        return AsyncFileReader()
    
    @pytest.fixture
    def temp_file(self):
        """Create temporary file with known content."""
        fd, path = tempfile.mkstemp()
        content = b"0123456789ABCDEFGHIJ"  # 20 bytes
        os.write(fd, content)
        os.close(fd)
        yield Path(path)
        os.unlink(path)
    
    @pytest.mark.asyncio
    async def test_read_chunk(self, reader, temp_file):
        """Test reading a chunk."""
        chunk = await reader.read_chunk(temp_file, 0, 10)
        
        assert chunk == b"0123456789"
    
    @pytest.mark.asyncio
    async def test_read_chunk_middle(self, reader, temp_file):
        """Test reading chunk from middle."""
        chunk = await reader.read_chunk(temp_file, 5, 15)
        
        assert chunk == b"56789ABCDE"
    
    @pytest.mark.asyncio
    async def test_read_entire_file(self, reader, temp_file):
        """Test reading entire file."""
        data = await reader.read_file(temp_file)
        
        assert data == b"0123456789ABCDEFGHIJ"
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, reader):
        """Test reading non-existent file returns None."""
        result = await reader.read_chunk(
            Path("/nonexistent/file.txt"), 0, 100
        )
        
        assert result is None


class TestChunkUploader:
    """Test suite for ChunkUploader."""
    
    @pytest.fixture
    def uploader(self):
        """Create uploader instance."""
        return ChunkUploader("https://example.com/upload", timeout=30)
    
    def test_init(self, uploader):
        """Test initialization."""
        assert uploader.upload_url == "https://example.com/upload"
        assert uploader.get_upload_token() is None
    
    def test_process_response_valid(self, uploader):
        """Test processing valid response."""
        token = uploader._process_response("upload_token_123", 0)
        
        assert token == "upload_token_123"
        assert uploader.get_upload_token() == "upload_token_123"
    
    def test_process_response_error_code(self, uploader):
        """Test processing error code."""
        with pytest.raises(ValueError, match="Server error"):
            uploader._process_response("-5", 0)
    
    @pytest.mark.asyncio
    async def test_upload_empty_chunk_raises(self, uploader):
        """Test uploading empty chunk raises error."""
        with pytest.raises(ValueError, match="empty"):
            await uploader.upload_chunk(0, 0, b"")
    
    @pytest.mark.asyncio
    async def test_upload_chunk_with_mock(self, uploader):
        """Test upload chunk with mocked HTTP."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.text = AsyncMock(return_value="token123")
            
            mock_post = AsyncMock(return_value=mock_response)
            mock_post.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.__aexit__ = AsyncMock()
            
            mock_session_instance = Mock()
            mock_session_instance.post = Mock(return_value=mock_post)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock()
            
            mock_session.return_value = mock_session_instance
            
            token = await uploader.upload_chunk(0, 0, b"test data")
            
            assert token == "token123"
