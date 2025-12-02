"""Tests for upload models."""
import pytest
from pathlib import Path
from megapy.core.upload.models import (
    FileAttributes,
    ChunkInfo,
    UploadConfig,
    UploadResult,
    UploadProgress
)


class TestFileAttributes:
    """Test suite for FileAttributes."""
    
    def test_create_basic(self):
        """Test basic creation."""
        attrs = FileAttributes(name="test.txt")
        
        assert attrs.name == "test.txt"
        assert attrs.label == 0
        assert attrs.is_favorite is False
    
    def test_create_with_options(self):
        """Test creation with all options."""
        attrs = FileAttributes(
            name="document.pdf",
            label=2,
            is_favorite=True
        )
        
        assert attrs.name == "document.pdf"
        assert attrs.label == 2
        assert attrs.is_favorite is True
    
    def test_to_dict_basic(self):
        """Test converting to dict."""
        attrs = FileAttributes(name="test.txt")
        d = attrs.to_dict()
        
        assert d == {'n': 'test.txt'}
    
    def test_to_dict_with_label(self):
        """Test dict with label."""
        attrs = FileAttributes(name="test.txt", label=3)
        d = attrs.to_dict()
        
        assert d == {'n': 'test.txt', 'lbl': 3}
    
    def test_to_dict_with_favorite(self):
        """Test dict with favorite."""
        attrs = FileAttributes(name="test.txt", is_favorite=True)
        d = attrs.to_dict()
        
        assert d == {'n': 'test.txt', 'fav': 1}
    
    def test_from_dict(self):
        """Test creating from dict."""
        d = {'n': 'file.txt', 'lbl': 1, 'fav': 1}
        attrs = FileAttributes.from_dict(d)
        
        assert attrs.name == 'file.txt'
        assert attrs.label == 1
        assert attrs.is_favorite is True
    
    def test_from_dict_alternative_keys(self):
        """Test creating from dict with alternative keys."""
        d = {'name': 'file.txt', 'label': 2, 'is_favorite': True}
        attrs = FileAttributes.from_dict(d)
        
        assert attrs.name == 'file.txt'
        assert attrs.label == 2
        assert attrs.is_favorite is True
    
    def test_custom_attributes(self):
        """Test custom attributes."""
        from megapy.core.upload.models import CustomAttributes
        
        custom = CustomAttributes(document_id="DOC123", url="https://example.com")
        attrs = FileAttributes(name="test.txt", custom=custom)
        
        result = attrs.to_dict()
        assert result['n'] == "test.txt"
        assert 'e' in result
        assert result['e']['i'] == "DOC123"
        assert result['e']['u'] == "https://example.com"
    
    def test_with_custom(self):
        """Test adding custom attributes with with_custom()."""
        attrs = FileAttributes(name="test.txt")
        attrs.with_custom(document_id="DOC456", url="https://test.com")
        
        result = attrs.to_dict()
        assert result['e']['i'] == "DOC456"
        assert result['e']['u'] == "https://test.com"


class TestChunkInfo:
    """Test suite for ChunkInfo."""
    
    def test_create(self):
        """Test basic creation."""
        chunk = ChunkInfo(index=0, start=0, end=1024)
        
        assert chunk.index == 0
        assert chunk.start == 0
        assert chunk.end == 1024
    
    def test_size_property(self):
        """Test size calculation."""
        chunk = ChunkInfo(index=0, start=100, end=500)
        
        assert chunk.size == 400
    
    def test_immutable(self):
        """Test chunk info is immutable."""
        chunk = ChunkInfo(index=0, start=0, end=100)
        
        with pytest.raises(AttributeError):
            chunk.start = 50


class TestUploadConfig:
    """Test suite for UploadConfig."""
    
    def test_create_basic(self):
        """Test basic creation."""
        config = UploadConfig(
            file_path=Path("test.txt"),
            target_folder_id="folder123"
        )
        
        assert config.file_path == Path("test.txt")
        assert config.target_folder_id == "folder123"
        assert config.attributes is not None
        assert config.attributes.name == "test.txt"
    
    def test_create_from_string_path(self):
        """Test creation from string path."""
        config = UploadConfig(
            file_path="path/to/file.txt",
            target_folder_id="folder123"
        )
        
        assert isinstance(config.file_path, Path)
        assert config.file_path == Path("path/to/file.txt")
    
    def test_default_attributes(self):
        """Test default attributes from filename."""
        config = UploadConfig(
            file_path=Path("document.pdf"),
            target_folder_id="folder"
        )
        
        assert config.attributes.name == "document.pdf"
    
    def test_custom_attributes(self):
        """Test custom attributes."""
        attrs = FileAttributes(name="custom.txt", label=1)
        config = UploadConfig(
            file_path=Path("original.txt"),
            target_folder_id="folder",
            attributes=attrs
        )
        
        assert config.attributes.name == "custom.txt"
        assert config.attributes.label == 1
    
    def test_defaults(self):
        """Test default values."""
        config = UploadConfig(
            file_path=Path("test.txt"),
            target_folder_id="folder"
        )
        
        assert config.encryption_key is None
        assert config.max_concurrent_uploads == 4
        assert config.timeout == 120


class TestUploadResult:
    """Test suite for UploadResult."""
    
    @pytest.fixture
    def result(self):
        """Create sample result."""
        return UploadResult(
            node_handle="abc123",
            file_key=b"x" * 32,
            file_size=1024,
            attributes=FileAttributes(name="test.txt")
        )
    
    def test_properties(self, result):
        """Test basic properties."""
        assert result.node_handle == "abc123"
        assert len(result.file_key) == 32
        assert result.file_size == 1024
        assert result.attributes.name == "test.txt"
    
    def test_public_link(self, result):
        """Test public link generation."""
        link = result.public_link
        
        assert "mega.nz/file/abc123" in link
        assert "#" in link
    
    def test_immutable(self, result):
        """Test result is immutable."""
        with pytest.raises(AttributeError):
            result.node_handle = "changed"


class TestUploadProgress:
    """Test suite for UploadProgress."""
    
    def test_create(self):
        """Test basic creation."""
        progress = UploadProgress(total_chunks=10)
        
        assert progress.total_chunks == 10
        assert progress.uploaded_chunks == 0
    
    def test_percentage(self):
        """Test percentage calculation."""
        progress = UploadProgress(total_chunks=10, uploaded_chunks=5)
        
        assert progress.percentage == 50.0
    
    def test_percentage_zero_chunks(self):
        """Test percentage with zero chunks."""
        progress = UploadProgress(total_chunks=0)
        
        assert progress.percentage == 0.0
    
    def test_is_complete(self):
        """Test completion check."""
        progress = UploadProgress(total_chunks=10, uploaded_chunks=10)
        
        assert progress.is_complete is True
    
    def test_not_complete(self):
        """Test not complete."""
        progress = UploadProgress(total_chunks=10, uploaded_chunks=5)
        
        assert progress.is_complete is False
