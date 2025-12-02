"""Tests for video/media attributes upload functionality."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from megapy.core.attributes import MediaInfo, MediaAttributeService, MediaProcessor
from megapy.core.upload.models import UploadConfig, FileAttributes
from megapy.core.upload.coordinator import UploadCoordinator


class TestMediaAttributeEncoding:
    """Test suite for MediaAttributeService encoding."""
    
    @pytest.fixture
    def service(self):
        """Create MediaAttributeService instance."""
        return MediaAttributeService()
    
    @pytest.fixture
    def file_key(self):
        """Create a 32-byte file key."""
        return b'\x01\x02\x03\x04\x05\x06\x07\x08' * 4
    
    def test_encode_basic_video_info(self, service, file_key):
        """Test encoding basic video info."""
        info = MediaInfo(
            width=1920,
            height=1080,
            fps=30,
            playtime=120,
            shortformat=1  # MP4/H.264/AAC
        )
        
        result = service.encode(info, file_key)
        
        assert result.startswith("8*")
        assert len(result) > 3
    
    def test_encode_decode_roundtrip(self, service, file_key):
        """Test encode/decode roundtrip preserves data."""
        info = MediaInfo(
            width=1280,
            height=720,
            fps=24,
            playtime=300,
            shortformat=1
        )
        
        encoded = service.encode(info, file_key)
        decoded = service.decode(f"123:{encoded}", file_key)
        
        assert decoded.width == info.width
        assert decoded.height == info.height
        assert decoded.fps == info.fps
        assert decoded.playtime == info.playtime
        assert decoded.shortformat == info.shortformat
    
    def test_encode_with_custom_codecs(self, service, file_key):
        """Test encoding with custom codec info (shortformat=0)."""
        info = MediaInfo(
            width=3840,
            height=2160,
            fps=60,
            playtime=600,
            shortformat=0,
            container=1,
            videocodec=2,
            audiocodec=3
        )
        
        result = service.encode(info, file_key)
        
        # Should have both 8* and 9* attributes
        assert "8*" in result
        assert "9*" in result
        assert "/" in result  # Separator between attributes
    
    def test_encode_audio_only(self, service, file_key):
        """Test encoding audio-only file."""
        info = MediaInfo(
            width=0,
            height=0,
            fps=0,
            playtime=180,  # 3 minutes
            shortformat=3  # MP4 audio only
        )
        
        result = service.encode(info, file_key)
        
        assert result.startswith("8*")
    
    def test_encode_unknown_format(self, service, file_key):
        """Test encoding with unknown format (shortformat=255)."""
        info = MediaInfo(
            width=1920,
            height=1080,
            fps=30,
            playtime=60,
            shortformat=255
        )
        
        result = service.encode(info, file_key)
        
        # Should only have 8* attribute (no 9* for unknown format)
        assert result.startswith("8*")
        assert "9*" not in result


class TestMediaProcessorExtractMetadata:
    """Test suite for MediaProcessor.extract_metadata."""
    
    def test_get_shortformat_mp4_h264_aac(self):
        """Test shortformat detection for MP4/H.264/AAC."""
        result = MediaProcessor._get_shortformat('mp4', 'h264', 'aac')
        assert result == 1
    
    def test_get_shortformat_mp4_h264_no_audio(self):
        """Test shortformat detection for MP4/H.264 without audio."""
        result = MediaProcessor._get_shortformat('mp4', 'h264', '')
        assert result == 2
    
    def test_get_shortformat_mp4_aac_only(self):
        """Test shortformat detection for MP4/AAC audio only."""
        result = MediaProcessor._get_shortformat('mp4', '', 'aac')
        assert result == 3
    
    def test_get_shortformat_mov_h264_aac(self):
        """Test shortformat detection for MOV/H.264/AAC."""
        result = MediaProcessor._get_shortformat('mov', 'h264', 'aac')
        assert result == 1  # Same as MP4
    
    def test_get_shortformat_unknown_container(self):
        """Test shortformat detection for unknown container."""
        result = MediaProcessor._get_shortformat('webm', 'vp9', 'opus')
        assert result == 255
    
    def test_get_shortformat_mkv(self):
        """Test shortformat detection for MKV."""
        result = MediaProcessor._get_shortformat('mkv', 'h264', 'aac')
        assert result == 255  # MKV is not MP4


class TestUploadConfigWithMediaInfo:
    """Test suite for UploadConfig with media_info."""
    
    def test_upload_config_accepts_media_info(self):
        """Test UploadConfig accepts media_info parameter."""
        info = MediaInfo(width=1920, height=1080, fps=30, playtime=120)
        
        config = UploadConfig(
            file_path=Path("test.mp4"),
            target_folder_id="test_folder",
            media_info=info
        )
        
        assert config.media_info is not None
        assert config.media_info.width == 1920
    
    def test_upload_config_media_info_default_none(self):
        """Test UploadConfig has media_info default to None."""
        config = UploadConfig(
            file_path=Path("test.txt"),
            target_folder_id="test_folder"
        )
        
        assert config.media_info is None


class TestUploadMediaAttributes:
    """Test suite for uploading media attributes via pfa command."""
    
    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = AsyncMock()
        api.request = AsyncMock(return_value={'fa': '470:8*abc123'})
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
    async def test_upload_media_attributes_calls_pfa(self, coordinator, mock_api):
        """Test _upload_media_attributes calls pfa API command."""
        info = MediaInfo(width=1920, height=1080, fps=30, playtime=120, shortformat=1)
        file_key = b'\x01\x02\x03\x04' * 8
        
        await coordinator._upload_media_attributes("test_handle", info, file_key)
        
        # Verify pfa command was called
        mock_api.request.assert_called()
        call_args = mock_api.request.call_args[0][0]
        assert call_args['a'] == 'pfa'
        assert call_args['n'] == 'test_handle'
        assert 'fa' in call_args
        assert call_args['fa'].startswith('8*')
    
    @pytest.mark.asyncio
    async def test_upload_media_attributes_includes_attr9_when_needed(self, coordinator, mock_api):
        """Test _upload_media_attributes includes attr 9 for custom formats."""
        info = MediaInfo(
            width=1920, height=1080, fps=30, playtime=120,
            shortformat=0,  # Custom format requires attr 9
            container=1, videocodec=2, audiocodec=3
        )
        file_key = b'\x01\x02\x03\x04' * 8
        
        await coordinator._upload_media_attributes("test_handle", info, file_key)
        
        call_args = mock_api.request.call_args[0][0]
        fa = call_args['fa']
        assert '8*' in fa
        assert '9*' in fa


class TestMediaInfoProperties:
    """Test suite for MediaInfo properties."""
    
    def test_is_video_true(self):
        """Test is_video returns True for video files."""
        info = MediaInfo(width=1920, height=1080)
        assert info.is_video is True
    
    def test_is_video_false_for_audio(self):
        """Test is_video returns False for audio-only files."""
        info = MediaInfo(width=0, height=0, playtime=180)
        assert info.is_video is False
    
    def test_is_audio_true(self):
        """Test is_audio returns True for audio-only files."""
        info = MediaInfo(width=0, height=0, playtime=180)
        assert info.is_audio is True
    
    def test_is_audio_false_for_video(self):
        """Test is_audio returns False for video files."""
        info = MediaInfo(width=1920, height=1080, playtime=120)
        assert info.is_audio is False
    
    def test_duration_formatted_short(self):
        """Test duration_formatted for short videos."""
        info = MediaInfo(playtime=65)  # 1:05
        assert info.duration_formatted == "1:05"
    
    def test_duration_formatted_long(self):
        """Test duration_formatted for long videos."""
        info = MediaInfo(playtime=3665)  # 1:01:05
        assert info.duration_formatted == "1:01:05"
    
    def test_resolution_string(self):
        """Test resolution property."""
        info = MediaInfo(width=1920, height=1080)
        assert info.resolution == "1920x1080"
    
    def test_resolution_empty_for_audio(self):
        """Test resolution is empty for audio."""
        info = MediaInfo(width=0, height=0)
        assert info.resolution == ""
    
    def test_is_valid_true(self):
        """Test is_valid for known format."""
        info = MediaInfo(shortformat=1)
        assert info.is_valid is True
    
    def test_is_valid_false_for_unknown(self):
        """Test is_valid for unknown format."""
        info = MediaInfo(shortformat=255)
        assert info.is_valid is False
