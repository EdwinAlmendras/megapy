"""
Preview image generation service.

Generates JPEG previews with max 1024px dimension and 85% quality (MEGA standard).
"""
from __future__ import annotations
import io
from pathlib import Path
from typing import Union, Optional, BinaryIO, Tuple

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class PreviewService:
    """
    Service for generating MEGA-compatible preview images.
    
    Specifications (from MEGA webclient):
    - Max size: 1024x1024 pixels (maintains aspect ratio)
    - Format: JPEG
    - Quality: 85%
    
    Example:
        >>> service = PreviewService()
        >>> preview_data = service.generate("photo.jpg")
        >>> # preview_data is bytes of max 1024px JPEG
    """
    
    MAX_SIZE = 1024  # MEGA uses PREVIEW_SIZE: 1024
    QUALITY = 85     # MEGA uses PREVIEW_QUALITY: 0.85
    FORMAT = 'JPEG'
    
    def __init__(self):
        if not PIL_AVAILABLE:
            raise ImportError(
                "Pillow is required for preview generation. "
                "Install with: pip install Pillow"
            )
    
    def generate(
        self,
        source: Union[str, Path, bytes, BinaryIO],
        max_size: Optional[int] = None
    ) -> bytes:
        """
        Generate a preview image.
        
        Args:
            source: Image file path, bytes, or file-like object
            max_size: Maximum width/height (default: 1024)
            
        Returns:
            JPEG preview bytes (max 1024px, 85% quality)
        """
        max_size = max_size or self.MAX_SIZE
        
        # Load image
        img = self._load_image(source)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if larger than max_size
        img = self._resize_to_max(img, max_size)
        
        # Save as JPEG
        output = io.BytesIO()
        img.save(output, format=self.FORMAT, quality=self.QUALITY, optimize=True)
        
        return output.getvalue()
    
    def generate_from_video(
        self,
        video_path: Union[str, Path],
        frame_time: float = 1.0
    ) -> Optional[bytes]:
        """
        Generate preview from video frame.
        
        Requires ffmpeg to be installed.
        
        Args:
            video_path: Path to video file
            frame_time: Time in seconds to extract frame
            
        Returns:
            JPEG preview bytes or None if failed
        """
        import subprocess
        import tempfile
        
        video_path = Path(video_path)
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Extract frame with ffmpeg
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(frame_time),
                '-i', str(video_path),
                '-vframes', '1',
                '-q:v', '2',
                tmp_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return None
            
            # Generate preview from extracted frame
            return self.generate(tmp_path)
            
        except Exception:
            return None
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    
    def _load_image(
        self,
        source: Union[str, Path, bytes, BinaryIO]
    ) -> Image.Image:
        """Load image from various sources."""
        if isinstance(source, (str, Path)):
            return Image.open(source)
        elif isinstance(source, bytes):
            return Image.open(io.BytesIO(source))
        else:
            return Image.open(source)
    
    def _resize_to_max(
        self,
        img: Image.Image,
        max_size: int
    ) -> Image.Image:
        """Resize image to fit within max_size while maintaining aspect ratio."""
        width, height = img.size
        
        if width <= max_size and height <= max_size:
            return img
        
        # Calculate new size
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))
        
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def get_dimensions(
        self,
        source: Union[str, Path, bytes, BinaryIO]
    ) -> Tuple[int, int]:
        """Get original image dimensions."""
        img = self._load_image(source)
        return img.size
