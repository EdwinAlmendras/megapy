"""
Thumbnail generation service.

Generates 240x240 JPEG thumbnails with 80% quality (MEGA standard).
"""
from __future__ import annotations
import io
from pathlib import Path
from typing import Union, Optional, BinaryIO

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ThumbnailService:
    """
    Service for generating MEGA-compatible thumbnails.
    
    Specifications (from MEGA webclient):
    - Size: 240x240 pixels (square, cropped to center)
    - Format: JPEG
    - Quality: 80%
    
    Example:
        >>> service = ThumbnailService()
        >>> thumb_data = service.generate("photo.jpg")
        >>> # thumb_data is bytes of 240x240 JPEG
    """
    
    SIZE = (240, 240) # 240
    QUALITY = 80  # MEGA uses 0.80
    FORMAT = 'JPEG'
    
    def __init__(self):
        if not PIL_AVAILABLE:
            raise ImportError(
                "Pillow is required for thumbnail generation. "
                "Install with: pip install Pillow"
            )
    
    def generate(
        self,
        source: Union[str, Path, bytes, BinaryIO],
        crop_center: bool = True
    ) -> bytes:
        """
        Generate a thumbnail from an image.
        
        Args:
            source: Image file path, bytes, or file-like object
            crop_center: If True, crop to center square before resize
            
        Returns:
            JPEG thumbnail bytes (240x240, 80% quality)
        """
        # Load image
        img = self._load_image(source)
        
        # Convert to RGB if necessary (for PNG with transparency, etc.)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        """ if crop_center:
            # Crop to center square
            img = self._crop_center_square(img) """
        
        # Resize to 240x240 TODO i change resize to thumbnail img = img.resize
        # img = img.resize(self.SIZE, Image.Resampling.LANCZOS)
        
        
        w, h = img.size
        SIZE = self.SIZE[0]
        if w < h:
            new_w = SIZE
            new_h = int(h * SIZE / w)
        else:
            new_h = SIZE
            new_w = int(w * SIZE / h)

        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
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
        Generate thumbnail from video frame.
        
        Requires ffmpeg to be installed.
        
        Args:
            video_path: Path to video file
            frame_time: Time in seconds to extract frame
            
        Returns:
            JPEG thumbnail bytes or None if failed
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
            
            # Generate thumbnail from extracted frame
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
    
    def _crop_center_square(self, img: Image.Image) -> Image.Image:
        """Crop image to center square."""
        width, height = img.size
        
        if width == height:
            return img
        
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        
        return img.crop((left, top, left + size, top + size))
    
    @staticmethod
    def is_image(file_path: Union[str, Path]) -> bool:
        """Check if file is a supported image."""
        ext = Path(file_path).suffix.lower()
        return ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
    
    @staticmethod
    def is_video(file_path: Union[str, Path]) -> bool:
        """Check if file is a supported video."""
        ext = Path(file_path).suffix.lower()
        return ext in {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
