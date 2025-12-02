"""Tests for MediaProcessor and thumbnail/preview generation."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import io

from megapy.core.attributes import (
    MediaProcessor,
    MediaResult,
    ThumbnailService,
    PreviewService
)


class TestMediaProcessor:
    """Test suite for MediaProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create MediaProcessor instance."""
        return MediaProcessor()
    
    @pytest.fixture
    def processor_no_auto(self):
        """Create MediaProcessor with auto generation disabled."""
        return MediaProcessor(auto_thumbnail=False, auto_preview=False)
    
    # is_media tests
    def test_is_media_jpg(self, processor):
        """Test JPG is recognized as media."""
        assert processor.is_media("photo.jpg") is True
        assert processor.is_media("photo.JPG") is True
    
    def test_is_media_png(self, processor):
        """Test PNG is recognized as media."""
        assert processor.is_media("image.png") is True
    
    def test_is_media_gif(self, processor):
        """Test GIF is recognized as media."""
        assert processor.is_media("animation.gif") is True
    
    def test_is_media_webp(self, processor):
        """Test WebP is recognized as media."""
        assert processor.is_media("image.webp") is True
    
    def test_is_media_video_mp4(self, processor):
        """Test MP4 is recognized as media."""
        assert processor.is_media("video.mp4") is True
    
    def test_is_media_video_mkv(self, processor):
        """Test MKV is recognized as media."""
        assert processor.is_media("video.mkv") is True
    
    def test_is_media_video_mov(self, processor):
        """Test MOV is recognized as media."""
        assert processor.is_media("video.mov") is True
    
    def test_is_media_non_media_txt(self, processor):
        """Test TXT is not recognized as media."""
        assert processor.is_media("document.txt") is False
    
    def test_is_media_non_media_pdf(self, processor):
        """Test PDF is not recognized as media."""
        assert processor.is_media("document.pdf") is False
    
    def test_is_media_non_media_zip(self, processor):
        """Test ZIP is not recognized as media."""
        assert processor.is_media("archive.zip") is False
    
    def test_is_media_path_object(self, processor):
        """Test works with Path objects."""
        assert processor.is_media(Path("photo.jpg")) is True
        assert processor.is_media(Path("doc.pdf")) is False
    
    # is_image tests
    def test_is_image_jpg(self, processor):
        """Test JPG is recognized as image."""
        assert processor.is_image("photo.jpg") is True
        assert processor.is_image("photo.jpeg") is True
    
    def test_is_image_png(self, processor):
        """Test PNG is recognized as image."""
        assert processor.is_image("image.png") is True
    
    def test_is_image_video_not_image(self, processor):
        """Test video is not recognized as image."""
        assert processor.is_image("video.mp4") is False
    
    # is_video tests
    def test_is_video_mp4(self, processor):
        """Test MP4 is recognized as video."""
        assert processor.is_video("video.mp4") is True
    
    def test_is_video_mkv(self, processor):
        """Test MKV is recognized as video."""
        assert processor.is_video("video.mkv") is True
    
    def test_is_video_image_not_video(self, processor):
        """Test image is not recognized as video."""
        assert processor.is_video("photo.jpg") is False
    
    # process tests
    def test_process_non_media_returns_not_media(self, processor):
        """Test processing non-media file returns is_media=False."""
        result = processor.process("document.txt")
        
        assert isinstance(result, MediaResult)
        assert result.is_media is False
        assert result.thumbnail is None
        assert result.preview is None
    
    def test_process_image_sets_media_type(self, processor):
        """Test processing image sets correct media_type."""
        with patch.object(processor, 'generate_thumbnail', return_value=b'thumb'):
            with patch.object(processor, 'generate_preview', return_value=b'preview'):
                result = processor.process("photo.jpg")
        
        assert result.is_media is True
        assert result.media_type == 'image'
    
    def test_process_video_sets_media_type(self, processor):
        """Test processing video sets correct media_type."""
        with patch.object(processor, 'generate_video_thumbnail', return_value=b'thumb'):
            with patch.object(processor, 'generate_video_preview', return_value=b'preview'):
                result = processor.process("video.mp4")
        
        assert result.is_media is True
        assert result.media_type == 'video'
    
    def test_process_respects_auto_thumbnail_false(self, processor_no_auto):
        """Test auto_thumbnail=False prevents thumbnail generation."""
        with patch.object(processor_no_auto, 'generate_thumbnail') as mock_gen:
            result = processor_no_auto.process("photo.jpg")
        
        mock_gen.assert_not_called()
        assert result.thumbnail is None
    
    def test_process_respects_auto_preview_false(self, processor_no_auto):
        """Test auto_preview=False prevents preview generation."""
        with patch.object(processor_no_auto, 'generate_preview') as mock_gen:
            result = processor_no_auto.process("photo.jpg")
        
        mock_gen.assert_not_called()
        assert result.preview is None


class TestMediaResult:
    """Test suite for MediaResult dataclass."""
    
    def test_default_values(self):
        """Test MediaResult default values."""
        result = MediaResult()
        
        assert result.thumbnail is None
        assert result.preview is None
        assert result.is_media is False
        assert result.media_type is None
    
    def test_with_values(self):
        """Test MediaResult with values."""
        result = MediaResult(
            thumbnail=b'thumb_data',
            preview=b'preview_data',
            is_media=True,
            media_type='image'
        )
        
        assert result.thumbnail == b'thumb_data'
        assert result.preview == b'preview_data'
        assert result.is_media is True
        assert result.media_type == 'image'


class TestThumbnailService:
    """Test suite for ThumbnailService."""
    
    @pytest.fixture
    def service(self):
        """Create ThumbnailService instance."""
        return ThumbnailService()
    
    @pytest.fixture
    def test_image(self):
        """Create a test image file."""
        from PIL import Image
        
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        
        img = Image.new('RGB', (800, 600), color='red')
        img.save(path)
        
        yield Path(path)
        os.unlink(path)
    
    @pytest.fixture
    def test_image_rgba(self):
        """Create a test RGBA image file."""
        from PIL import Image
        
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        
        img = Image.new('RGBA', (800, 600), color=(255, 0, 0, 128))
        img.save(path)
        
        yield Path(path)
        os.unlink(path)
    
    def test_thumbnail_size_is_240x240(self):
        """Test thumbnail size constant is 240x240."""
        assert ThumbnailService.SIZE == (240, 240)
    
    def test_thumbnail_quality_is_80(self):
        """Test thumbnail quality constant is 80."""
        assert ThumbnailService.QUALITY == 80
    
    def test_generate_returns_bytes(self, service, test_image):
        """Test generate returns bytes."""
        result = service.generate(test_image)
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    def test_generate_produces_240x240_image(self, service, test_image):
        """Test generated thumbnail is 240x240."""
        from PIL import Image
        
        result = service.generate(test_image)
        img = Image.open(io.BytesIO(result))
        
        assert img.size == (240, 240)
    
    def test_generate_produces_jpeg(self, service, test_image):
        """Test generated thumbnail is JPEG."""
        from PIL import Image
        
        result = service.generate(test_image)
        img = Image.open(io.BytesIO(result))
        
        assert img.format == 'JPEG'
    
    def test_generate_handles_rgba_image(self, service, test_image_rgba):
        """Test handles RGBA images by converting to RGB."""
        from PIL import Image
        
        result = service.generate(test_image_rgba)
        img = Image.open(io.BytesIO(result))
        
        assert img.mode == 'RGB'
        assert img.size == (240, 240)
    
    def test_generate_from_bytes(self, service, test_image):
        """Test generate from bytes input."""
        image_bytes = test_image.read_bytes()
        result = service.generate(image_bytes)
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    def test_is_image_returns_true_for_images(self):
        """Test is_image returns True for image extensions."""
        assert ThumbnailService.is_image("photo.jpg") is True
        assert ThumbnailService.is_image("photo.jpeg") is True
        assert ThumbnailService.is_image("photo.png") is True
        assert ThumbnailService.is_image("photo.gif") is True
    
    def test_is_image_returns_false_for_non_images(self):
        """Test is_image returns False for non-image extensions."""
        assert ThumbnailService.is_image("doc.pdf") is False
        assert ThumbnailService.is_image("video.mp4") is False
    
    def test_is_video_returns_true_for_videos(self):
        """Test is_video returns True for video extensions."""
        assert ThumbnailService.is_video("video.mp4") is True
        assert ThumbnailService.is_video("video.mkv") is True
        assert ThumbnailService.is_video("video.mov") is True
    
    def test_is_video_returns_false_for_non_videos(self):
        """Test is_video returns False for non-video extensions."""
        assert ThumbnailService.is_video("photo.jpg") is False
        assert ThumbnailService.is_video("doc.pdf") is False


class TestPreviewService:
    """Test suite for PreviewService."""
    
    @pytest.fixture
    def service(self):
        """Create PreviewService instance."""
        return PreviewService()
    
    @pytest.fixture
    def test_image_large(self):
        """Create a large test image file."""
        from PIL import Image
        
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        
        img = Image.new('RGB', (2000, 1500), color='blue')
        img.save(path)
        
        yield Path(path)
        os.unlink(path)
    
    @pytest.fixture
    def test_image_small(self):
        """Create a small test image file (smaller than MAX_SIZE)."""
        from PIL import Image
        
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        
        img = Image.new('RGB', (500, 400), color='green')
        img.save(path)
        
        yield Path(path)
        os.unlink(path)
    
    def test_preview_max_size_is_1024(self):
        """Test preview max size constant is 1024."""
        assert PreviewService.MAX_SIZE == 1024
    
    def test_preview_quality_is_85(self):
        """Test preview quality constant is 85."""
        assert PreviewService.QUALITY == 85
    
    def test_generate_returns_bytes(self, service, test_image_large):
        """Test generate returns bytes."""
        result = service.generate(test_image_large)
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    def test_generate_resizes_large_image(self, service, test_image_large):
        """Test large image is resized to max 1024px."""
        from PIL import Image
        
        result = service.generate(test_image_large)
        img = Image.open(io.BytesIO(result))
        
        assert max(img.size) <= 1024
    
    def test_generate_maintains_aspect_ratio(self, service, test_image_large):
        """Test aspect ratio is maintained after resize."""
        from PIL import Image
        
        result = service.generate(test_image_large)
        img = Image.open(io.BytesIO(result))
        
        # Original is 2000x1500 (4:3 ratio)
        # Should be 1024x768 (maintaining 4:3)
        assert img.size == (1024, 768)
    
    def test_generate_small_image_not_upscaled(self, service, test_image_small):
        """Test small images are not upscaled."""
        from PIL import Image
        
        result = service.generate(test_image_small)
        img = Image.open(io.BytesIO(result))
        
        # Original is 500x400, should stay the same
        assert img.size == (500, 400)
    
    def test_generate_produces_jpeg(self, service, test_image_large):
        """Test generated preview is JPEG."""
        from PIL import Image
        
        result = service.generate(test_image_large)
        img = Image.open(io.BytesIO(result))
        
        assert img.format == 'JPEG'
    
    def test_get_dimensions(self, service, test_image_large):
        """Test get_dimensions returns correct size."""
        width, height = service.get_dimensions(test_image_large)
        
        assert width == 2000
        assert height == 1500
