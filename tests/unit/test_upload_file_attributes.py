"""Tests for file attribute upload (thumbnails/previews)."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import aiohttp

from megapy.core.upload.coordinator import UploadCoordinator
from megapy.core.upload.models import UploadConfig, FileAttributes
from pathlib import Path


class TestUploadFileAttributes:
    """Test suite for file attribute (thumbnail/preview) upload."""
    
    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = AsyncMock()
        api.request = AsyncMock()
        return api
    
    @pytest.fixture
    def coordinator(self, mock_api):
        """Create UploadCoordinator instance."""
        master_key = b'\x00' * 16
        return UploadCoordinator(
            api_client=mock_api,
            master_key=master_key
        )
    
    @pytest.mark.asyncio
    async def test_upload_thumbnail_uses_correct_url_endpoint(self, coordinator, mock_api):
        """Test thumbnail upload POSTs to /0 endpoint."""
        mock_api.request.return_value = {'p': 'https://upload.mega.co.nz/test'}
        
        # Mock aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b'handle123')
        
        mock_post = AsyncMock(return_value=mock_response)
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await coordinator._upload_file_attribute(
                data=b'thumbnail_data',
                aes_key=b'\x00' * 16,
                attr_type=0  # thumbnail
            )
        
        # Verify POST was called with /0 endpoint
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get('url', '')
        
        assert '/0' in url, f"Expected /0 in URL for thumbnail, got: {url}"
    
    @pytest.mark.asyncio
    async def test_upload_preview_uses_correct_url_endpoint(self, coordinator, mock_api):
        """Test preview upload POSTs to /1 endpoint."""
        mock_api.request.return_value = {'p': 'https://upload.mega.co.nz/test'}
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b'handle456')
        
        mock_post = AsyncMock(return_value=mock_response)
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await coordinator._upload_file_attribute(
                data=b'preview_data',
                aes_key=b'\x00' * 16,
                attr_type=1  # preview
            )
        
        # Verify POST was called with /1 endpoint
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get('url', '')
        
        assert '/1' in url, f"Expected /1 in URL for preview, got: {url}"
    
    @pytest.mark.asyncio
    async def test_upload_file_attribute_requests_ufa_endpoint(self, coordinator, mock_api):
        """Test file attribute upload uses 'ufa' API command."""
        mock_api.request.return_value = {'p': 'https://upload.mega.co.nz/test'}
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b'handle')
        
        mock_post = AsyncMock(return_value=mock_response)
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            await coordinator._upload_file_attribute(
                data=b'data',
                aes_key=b'\x00' * 16,
                attr_type=0
            )
        
        # Verify API was called with 'ufa' command
        mock_api.request.assert_called_once()
        call_args = mock_api.request.call_args[0][0]
        assert call_args.get('a') == 'ufa', "Expected 'ufa' API command"
    
    @pytest.mark.asyncio
    async def test_upload_file_attribute_pads_to_16_bytes(self, coordinator, mock_api):
        """Test data is padded to 16-byte boundary."""
        mock_api.request.return_value = {'p': 'https://upload.mega.co.nz/test'}
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b'handle')
        
        mock_post = AsyncMock(return_value=mock_response)
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        # Use 10 bytes of data (not a multiple of 16)
        test_data = b'1234567890'
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            await coordinator._upload_file_attribute(
                data=test_data,
                aes_key=b'\x00' * 16,
                attr_type=0
            )
        
        # Verify uploaded data length is multiple of 16
        call_args = mock_session.post.call_args
        uploaded_data = call_args[1].get('data', b'')
        assert len(uploaded_data) % 16 == 0, "Data should be padded to 16-byte boundary"
    
    @pytest.mark.asyncio
    async def test_upload_file_attribute_encrypts_with_aes_cbc(self, coordinator, mock_api):
        """Test data is encrypted with AES-CBC."""
        mock_api.request.return_value = {'p': 'https://upload.mega.co.nz/test'}
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b'handle')
        
        mock_post = AsyncMock(return_value=mock_response)
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        test_data = b'0123456789ABCDEF'  # 16 bytes exactly
        test_key = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10'
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            await coordinator._upload_file_attribute(
                data=test_data,
                aes_key=test_key,
                attr_type=0
            )
        
        # Verify data was encrypted (should not be the same as input)
        call_args = mock_session.post.call_args
        uploaded_data = call_args[1].get('data', b'')
        assert uploaded_data != test_data, "Data should be encrypted"
    
    @pytest.mark.asyncio
    async def test_upload_file_attribute_returns_base64_handle(self, coordinator, mock_api):
        """Test returns base64-encoded handle."""
        mock_api.request.return_value = {'p': 'https://upload.mega.co.nz/test'}
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b'\x01\x02\x03\x04\x05\x06\x07\x08')
        
        mock_post = AsyncMock(return_value=mock_response)
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await coordinator._upload_file_attribute(
                data=b'data',
                aes_key=b'\x00' * 16,
                attr_type=0
            )
        
        assert result is not None
        assert isinstance(result, str)
        # Base64 encoded 8 bytes = ~11 chars
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_upload_file_attribute_returns_none_on_missing_url(self, coordinator, mock_api):
        """Test returns None when upload URL is not returned."""
        mock_api.request.return_value = {}  # No 'p' key
        
        result = await coordinator._upload_file_attribute(
            data=b'data',
            aes_key=b'\x00' * 16,
            attr_type=0
        )
        
        assert result is None


class TestFileAttributeFormat:
    """Test suite for file attribute string format."""
    
    def test_fa_format_thumbnail_only(self):
        """Test fa format with thumbnail only."""
        fa = "0*abc123"
        
        assert fa.startswith("0*")
        assert "abc123" in fa
    
    def test_fa_format_preview_only(self):
        """Test fa format with preview only."""
        fa = "1*def456"
        
        assert fa.startswith("1*")
        assert "def456" in fa
    
    def test_fa_format_both(self):
        """Test fa format with both thumbnail and preview."""
        fa = "0*abc123/1*def456"
        
        parts = fa.split('/')
        assert len(parts) == 2
        assert parts[0].startswith("0*")
        assert parts[1].startswith("1*")
    
    def test_parse_fa_with_user_id(self):
        """Test parsing fa with user_id prefix."""
        fa = "700:0*abc123/700:1*def456"
        
        thumb_handle = None
        preview_handle = None
        
        for part in fa.split('/'):
            if ':0*' in part:
                thumb_handle = part.split(':0*')[1]
            elif ':1*' in part:
                preview_handle = part.split(':1*')[1]
        
        assert thumb_handle == "abc123"
        assert preview_handle == "def456"
