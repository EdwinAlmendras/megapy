"""
Media attributes for video/audio files.

Based on MEGA webclient's MediaAttribute implementation (js/crypto.js).
Stores video/audio metadata like duration, resolution, fps, and codecs.
"""
from __future__ import annotations
import struct
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from ..crypto import Base64Encoder


# XXTEA constants (from MEGA webclient js/crypto.js)
# Reference: https://github.com/xxtea/xxtea-js/blob/master/src/xxtea.js
XXTEA_DELTA = 0x9E3779B9


def _uint32(i: int) -> int:
    """Convert to unsigned 32-bit integer."""
    return i & 0xFFFFFFFF


def _mx(sum_val: int, y: int, z: int, p: int, e: int, k: List[int]) -> int:
    """
    XXTEA mixing function - exact match of MEGA's JavaScript implementation.
    
    JavaScript: (z >>> 5 ^ y << 2) + (y >>> 3 ^ z << 4) ^ (sum ^ y) + (k[p & 3 ^ e] ^ z)
    
    All operations use unsigned 32-bit integers.
    """
    return _uint32(
        _uint32((_uint32(z) >> 5) ^ _uint32(y << 2)) +
        _uint32((_uint32(y) >> 3) ^ _uint32(z << 4))
    ) ^ _uint32(
        _uint32(sum_val ^ y) + _uint32(k[(p & 3) ^ e] ^ z)
    )


def xxtea_encrypt(v: List[int], k: List[int]) -> List[int]:
    """
    Encrypt uint32 array with XXTEA (exact MEGA webclient implementation).
    
    From js/crypto.js:
        for (q = Math.floor(6 + 52 / length) | 0; q > 0; --q) {
            sum = int32(sum + DELTA);
            e = sum >>> 2 & 3;
            for (p = 0; p < n; ++p) {
                y = v[p + 1];
                z = v[p] = int32(v[p] + mx(sum, y, z, p, e, k));
            }
            y = v[0];
            z = v[n] = int32(v[n] + mx(sum, y, z, n, e, k));
        }
    
    Args:
        v: Array of uint32 values to encrypt (modified in place)
        k: Key as array of 4 uint32 values
        
    Returns:
        Encrypted uint32 array
    """
    length = len(v)
    n = length - 1
    z = v[n]
    sum_val = 0
    q = 6 + 52 // length
    
    for _ in range(q):
        sum_val = _uint32(sum_val + XXTEA_DELTA)
        e = (sum_val >> 2) & 3
        
        for p in range(n):
            y = v[p + 1]
            v[p] = _uint32(v[p] + _mx(sum_val, y, z, p, e, k))
            z = v[p]
        
        y = v[0]
        v[n] = _uint32(v[n] + _mx(sum_val, y, z, n, e, k))
        z = v[n]
    
    return v


def xxtea_decrypt(v: List[int], k: List[int]) -> List[int]:
    """
    Decrypt uint32 array with XXTEA (exact MEGA webclient implementation).
    
    From js/crypto.js:
        for (sum = int32(q * DELTA); sum !== 0; sum = int32(sum - DELTA)) {
            e = sum >>> 2 & 3;
            for (p = n; p > 0; --p) {
                z = v[p - 1];
                y = v[p] = int32(v[p] - mx(sum, y, z, p, e, k));
            }
            z = v[n];
            y = v[0] = int32(v[0] - mx(sum, y, z, 0, e, k));
        }
    
    Args:
        v: Array of encrypted uint32 values (modified in place)
        k: Key as array of 4 uint32 values
        
    Returns:
        Decrypted uint32 array
    """
    length = len(v)
    n = length - 1
    y = v[0]
    q = 6 + 52 // length
    sum_val = _uint32(q * XXTEA_DELTA)
    
    while sum_val != 0:
        e = (sum_val >> 2) & 3
        
        for p in range(n, 0, -1):
            z = v[p - 1]
            v[p] = _uint32(v[p] - _mx(sum_val, y, z, p, e, k))
            y = v[p]
        
        z = v[n]
        v[0] = _uint32(v[0] - _mx(sum_val, y, z, 0, e, k))
        y = v[0]
        
        sum_val = _uint32(sum_val - XXTEA_DELTA)
    
    return v


def _xxkey(filekey: List[int]) -> List[int]:
    """
    Extract XXTEA key from file key.
    Uses the last 4 elements of the 8-element file key.
    """
    return [filekey[i + 4] for i in range(4)]


def _bytes_to_uint32_le(data: bytes) -> List[int]:
    """Convert bytes to list of uint32 (little-endian)."""
    result = []
    for i in range(0, len(data), 4):
        chunk = data[i:i+4]
        if len(chunk) < 4:
            chunk = chunk + b'\x00' * (4 - len(chunk))
        result.append(struct.unpack('<I', chunk)[0])
    return result


def _uint32_to_bytes_le(values: List[int]) -> bytes:
    """Convert list of uint32 to bytes (little-endian)."""
    return b''.join(struct.pack('<I', v & 0xFFFFFFFF) for v in values)


@dataclass
class MediaInfo:
    """
    Media information for video/audio files.
    
    Attributes:
        width: Video width in pixels
        height: Video height in pixels
        fps: Frames per second
        playtime: Duration in seconds
        shortformat: Format index (0=custom, 255=unknown)
        container: Container format ID (if shortformat=0)
        videocodec: Video codec ID (if shortformat=0)
        audiocodec: Audio codec ID (if shortformat=0)
    """
    width: int = 0
    height: int = 0
    fps: int = 0
    playtime: int = 0
    shortformat: int = 0
    container: int = 0
    videocodec: int = 0
    audiocodec: int = 0
    
    @property
    def is_valid(self) -> bool:
        """Check if media info is valid (not unknown format)."""
        return self.shortformat != 255
    
    @property
    def is_video(self) -> bool:
        """Check if this is a video file."""
        return self.width > 0 and self.height > 0
    
    @property
    def is_audio(self) -> bool:
        """Check if this is an audio-only file."""
        return self.playtime > 0 and not self.is_video
    
    @property
    def duration_formatted(self) -> str:
        """Get formatted duration (HH:MM:SS or MM:SS)."""
        total = self.playtime
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    
    @property
    def resolution(self) -> str:
        """Get resolution string (e.g., '1920x1080')."""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return ""
    
    @property
    def container_name(self) -> str:
        """Get container format name (e.g., 'mp4', 'mkv')."""
        if self.shortformat > 0 and self.shortformat in SHORTFORMAT_MAP:
            return SHORTFORMAT_MAP[self.shortformat][0]
        return CONTAINER_MAP.get(self.container, f"id:{self.container}")
    
    @property
    def video_codec_name(self) -> str:
        """Get video codec name (e.g., 'h264', 'hevc')."""
        if self.shortformat > 0 and self.shortformat in SHORTFORMAT_MAP:
            return SHORTFORMAT_MAP[self.shortformat][1]
        return VIDEO_CODEC_MAP.get(self.videocodec, f"id:{self.videocodec}" if self.videocodec else "")
    
    @property
    def audio_codec_name(self) -> str:
        """Get audio codec name (e.g., 'aac', 'mp3')."""
        if self.shortformat > 0 and self.shortformat in SHORTFORMAT_MAP:
            return SHORTFORMAT_MAP[self.shortformat][2]
        return AUDIO_CODEC_MAP.get(self.audiocodec, f"id:{self.audiocodec}" if self.audiocodec else "")
    
    @property 
    def codec_string(self) -> str:
        """Get full codec string (e.g., 'mp4/h264/aac')."""
        parts = [self.container_name, self.video_codec_name, self.audio_codec_name]
        return "/".join(p for p in parts if p)


# Common shortformat mappings (id -> container, vcodec, acodec)
SHORTFORMAT_MAP = {
    1: ('mp4', 'h264', 'aac'),
    2: ('mp4', 'h264', ''),
    3: ('mp4', '', 'aac'),
}

# Known codec IDs from MEGA (obtained via 'mc' API command)
# These are common mappings - full list can be fetched dynamically
CONTAINER_MAP = {
    0: 'unknown',
    129: 'mp4',
    130: 'webm',
    131: 'mkv',
    132: 'avi',
    133: 'mov',
    134: 'flv',
    135: '3gp',
    136: 'wmv',
    137: 'ogg',
}

VIDEO_CODEC_MAP = {
    0: '',
    887: 'h264',
    888: 'hevc',
    889: 'vp8',
    890: 'vp9',
    891: 'av1',
    892: 'mpeg4',
    893: 'mpeg2',
    894: 'theora',
}

AUDIO_CODEC_MAP = {
    0: '',
    1: 'aac',
    2: 'mp3',
    3: 'opus',
    4: 'vorbis',
    5: 'flac',
    6: 'ac3',
    7: 'eac3',
    8: 'dts',
}


class MediaAttributeService:
    """
    Service for encoding/decoding MEGA media attributes.
    
    Media attributes are stored in the 'fa' field with type 8 (and optionally 9).
    Format: "user_id:8*base64_data" or "user_id:8*base64_data/user_id:9*base64_data"
    
    Example:
        >>> service = MediaAttributeService()
        >>> # Decode from fa string
        >>> info = service.decode("123:8*COXwfdF5an8", file_key)
        >>> print(info.playtime, info.width, info.height)
        
        >>> # Encode media info
        >>> fa_string = service.encode(info, file_key)
    """
    
    def __init__(self):
        self._encoder = Base64Encoder()
    
    def decode(self, fa: str, file_key: bytes) -> Optional[MediaInfo]:
        """
        Decode media attributes from fa string.
        
        Args:
            fa: File attributes string (e.g., "123:8*COXwfdF5an8")
            file_key: File key (32 bytes)
            
        Returns:
            MediaInfo or None if not found/invalid
        """
        if not fa or ':8*' not in fa:
            return None
        
        # Convert file_key to 8-element array of uint32
        key_array = self._key_to_array(file_key)
        if not key_array:
            return None
        
        # Extract attribute 8 data
        pos = fa.find(':8*')
        if pos < 0:
            return None
        
        # Get base64 data (11 characters = 8 bytes)
        attr8_b64 = fa[pos + 3:pos + 3 + 11]
        if len(attr8_b64) < 11:
            return None
        
        try:
            attr8_data = self._encoder.decode(attr8_b64)
            if len(attr8_data) < 8:
                return None
            
            # Decrypt with XXTEA
            v = _bytes_to_uint32_le(attr8_data[:8])
            k = _xxkey(key_array)
            v = xxtea_decrypt(v, k)
            
            # Convert back to bytes for parsing
            decrypted = _uint32_to_bytes_le(v)
            
            # Parse fields (little-endian bit packing)
            info = self._parse_attr8(decrypted)
            
            # If shortformat is 0, parse attribute 9 for codec details
            # Format can be ":9*" (with user_id) or "/9*" (after attr 8)
            if info.shortformat == 0:
                pos9 = fa.find(':9*')
                if pos9 < 0:
                    pos9 = fa.find('/9*')
                if pos9 >= 0:
                    attr9_b64 = fa[pos9 + 3:pos9 + 3 + 11]
                    if len(attr9_b64) >= 11:
                        attr9_data = self._encoder.decode(attr9_b64)
                        if len(attr9_data) >= 8:
                            v9 = _bytes_to_uint32_le(attr9_data[:8])
                            v9 = xxtea_decrypt(v9, k)
                            decrypted9 = _uint32_to_bytes_le(v9)
                            self._parse_attr9(decrypted9, info)
            
            return info
            
        except Exception:
            return None
    
    def encode(self, info: MediaInfo, file_key: bytes) -> str:
        """
        Encode media info to fa string format.
        
        Args:
            info: MediaInfo object with media metadata
            file_key: File key (32 bytes)
            
        Returns:
            File attribute string (e.g., "8*COXwfdF5an8")
        """
        key_array = self._key_to_array(file_key)
        if not key_array:
            return ""
        
        k = _xxkey(key_array)
        
        # Encode attribute 8
        attr8_bytes = self._encode_attr8(info)
        v8 = _bytes_to_uint32_le(attr8_bytes)
        v8 = xxtea_encrypt(v8, k)
        encrypted8 = _uint32_to_bytes_le(v8)
        result = "8*" + self._encoder.encode(encrypted8)
        
        # If shortformat is 0, also encode attribute 9
        if info.shortformat == 0 and (info.container or info.videocodec or info.audiocodec):
            attr9_bytes = self._encode_attr9(info)
            v9 = _bytes_to_uint32_le(attr9_bytes)
            v9 = xxtea_encrypt(v9, k)
            encrypted9 = _uint32_to_bytes_le(v9)
            result += "/9*" + self._encoder.encode(encrypted9)
        
        return result
    
    def _key_to_array(self, file_key: bytes) -> Optional[List[int]]:
        """Convert file key bytes to 8-element uint32 array (Big-Endian like webclient)."""
        if len(file_key) < 32:
            # For 16-byte keys, duplicate to 32 bytes
            if len(file_key) >= 16:
                file_key = file_key[:16] + file_key[:16]
            else:
                return None
        
        # Use Big-Endian like webclient's base64_to_a32
        return list(struct.unpack('>8I', file_key[:32]))
    
    def _parse_attr8(self, data: bytes) -> MediaInfo:
        """Parse attribute 8 data into MediaInfo."""
        v = list(data[:8])
        
        # Width: bits from v[0] and v[1]
        width = (v[0] >> 1) + ((v[1] & 127) << 7)
        if v[0] & 1:
            width = (width << 3) + 16384
        
        # Height: bits from v[2] and v[3]
        height = v[2] + ((v[3] & 63) << 8)
        if v[1] & 128:
            height = (height << 1) + 16384
        
        # FPS: bits from v[3] and v[4]
        fps = (v[3] >> 7) + ((v[4] & 63) << 1)
        if v[3] & 64:
            fps = (fps << 3) + 128
        
        # Playtime: bits from v[4], v[5], v[6]
        playtime = (v[4] >> 7) + (v[5] << 1) + (v[6] << 9)
        if v[4] & 64:
            playtime = playtime * 60 + 131100
        
        # Shortformat: v[7]
        shortformat = v[7]
        
        return MediaInfo(
            width=width,
            height=height,
            fps=fps,
            playtime=playtime,
            shortformat=shortformat
        )
    
    def _parse_attr9(self, data: bytes, info: MediaInfo) -> None:
        """Parse attribute 9 data and update MediaInfo."""
        v = list(data[:8])
        
        info.container = v[0]
        info.videocodec = v[1] + ((v[2] & 15) << 8)
        info.audiocodec = (v[2] >> 4) + (v[3] << 4)
    
    def _encode_attr8(self, info: MediaInfo) -> bytes:
        """Encode MediaInfo to attribute 8 bytes."""
        width = info.width
        height = info.height
        fps = info.fps
        playtime = info.playtime
        shortformat = info.shortformat
        
        # Scale width: multiply by 2, compress if >= 32768
        width <<= 1
        if width >= 32768:
            width = ((width - 32768) >> 3) | 1
        if width >= 32768:
            width = 32767
        
        # Scale height: multiply by 2, compress if >= 32768  
        height <<= 1
        if height >= 32768:
            height = ((height - 32768) >> 3) | 1
        if height >= 32768:
            height = 32767
        
        # Scale playtime: multiply by 2, compress if >= 262144
        playtime <<= 1
        if playtime >= 262144:
            playtime = ((playtime - 262200) // 60) | 1
        if playtime >= 262144:
            playtime = 262143
        
        # Scale fps: multiply by 2, compress if >= 256
        fps <<= 1
        if fps >= 256:
            fps = ((fps - 256) >> 3) | 1
        if fps >= 256:
            fps = 255
        
        # Pack into bytes (little-endian)
        v = bytearray(8)
        v[7] = shortformat & 0xFF
        v[6] = (playtime >> 10) & 0xFF
        v[5] = (playtime >> 2) & 0xFF
        v[4] = ((playtime & 3) << 6) + (fps >> 2)
        v[3] = ((fps & 3) << 6) + ((height >> 9) & 63)
        v[2] = (height >> 1) & 0xFF
        v[1] = ((width >> 8) & 127) + ((height & 1) << 7)
        v[0] = width & 0xFF
        
        return bytes(v)
    
    def _encode_attr9(self, info: MediaInfo) -> bytes:
        """Encode codec info to attribute 9 bytes."""
        container = info.container
        vcodec = info.videocodec
        acodec = info.audiocodec
        
        v = bytearray(8)
        v[3] = (acodec >> 4) & 0xFF
        v[2] = ((vcodec >> 8) & 15) + ((acodec & 15) << 4)
        v[1] = vcodec & 0xFF
        v[0] = container & 0xFF
        
        return bytes(v)
    
    @staticmethod
    def has_media_attribute(fa: str) -> bool:
        """Check if fa string contains media attributes."""
        return fa is not None and ':8*' in fa


@dataclass
class MediaResult:
    """Result of media processing with thumbnail and preview."""
    thumbnail: Optional[bytes] = None
    preview: Optional[bytes] = None
    is_media: bool = False
    media_type: Optional[str] = None  # 'image' or 'video'


class MediaProcessor:
    """
    Processor for generating thumbnails and previews from media files.
    
    Also extracts media metadata using ffprobe (if available).
    
    Example:
        >>> processor = MediaProcessor()
        >>> result = processor.process("photo.jpg")
        >>> if result.is_media:
        ...     print(f"Thumbnail: {len(result.thumbnail)} bytes")
    """
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
    
    def __init__(
        self,
        auto_thumbnail: bool = True,
        auto_preview: bool = True,
        video_frame_time: float = 1.0
    ):
        """
        Initialize media processor.
        
        Args:
            auto_thumbnail: Auto-generate thumbnails
            auto_preview: Auto-generate previews
            video_frame_time: Frame extraction time for videos (seconds)
        """
        self.auto_thumbnail = auto_thumbnail
        self.auto_preview = auto_preview
        self.video_frame_time = video_frame_time
    
    def is_media(self, file_path) -> bool:
        """Check if file is a supported media file (image or video)."""
        from pathlib import Path
        ext = Path(file_path).suffix.lower()
        return ext in self.IMAGE_EXTENSIONS or ext in self.VIDEO_EXTENSIONS
    
    def is_image(self, file_path) -> bool:
        """Check if file is a supported image."""
        from pathlib import Path
        ext = Path(file_path).suffix.lower()
        return ext in self.IMAGE_EXTENSIONS
    
    def is_video(self, file_path) -> bool:
        """Check if file is a supported video."""
        from pathlib import Path
        ext = Path(file_path).suffix.lower()
        return ext in self.VIDEO_EXTENSIONS
    
    def process(self, file_path) -> MediaResult:
        """
        Process a media file to generate thumbnail and preview.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            MediaResult with thumbnail and preview bytes
        """
        from pathlib import Path
        path = Path(file_path)
        
        if not self.is_media(path):
            return MediaResult(is_media=False)
        
        result = MediaResult(is_media=True)
        
        if self.is_image(path):
            result.media_type = 'image'
            if self.auto_thumbnail:
                result.thumbnail = self.generate_thumbnail(path)
            if self.auto_preview:
                result.preview = self.generate_preview(path)
        elif self.is_video(path):
            result.media_type = 'video'
            if self.auto_thumbnail:
                result.thumbnail = self.generate_video_thumbnail(path)
            if self.auto_preview:
                result.preview = self.generate_video_preview(path)
        
        return result
    
    def generate_thumbnail(self, file_path) -> Optional[bytes]:
        """Generate thumbnail from image."""
        try:
            from .thumbnail import ThumbnailService
            service = ThumbnailService()
            return service.generate(file_path)
        except Exception:
            return None
    
    def generate_preview(self, file_path) -> Optional[bytes]:
        """Generate preview from image."""
        try:
            from .preview import PreviewService
            service = PreviewService()
            return service.generate(file_path)
        except Exception:
            return None
    
    def generate_video_thumbnail(self, file_path) -> Optional[bytes]:
        """Generate thumbnail from video frame."""
        try:
            from .thumbnail import ThumbnailService
            service = ThumbnailService()
            return service.generate_from_video(file_path, self.video_frame_time)
        except Exception:
            return None
    
    def generate_video_preview(self, file_path) -> Optional[bytes]:
        """Generate preview from video frame."""
        try:
            from .preview import PreviewService
            service = PreviewService()
            return service.generate_from_video(file_path, self.video_frame_time)
        except Exception:
            return None
    
    @staticmethod
    def is_available() -> bool:
        """Check if ffprobe is available."""
        import subprocess
        try:
            result = subprocess.run(
                ['ffprobe', '-version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @staticmethod
    def extract_metadata(file_path: str) -> Optional[MediaInfo]:
        """
        Extract media metadata from a file using ffprobe.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            MediaInfo or None if extraction failed
        """
        import subprocess
        import json
        
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode != 0:
                return None
            
            data = json.loads(result.stdout)
            
            info = MediaInfo()
            container = ''
            vcodec = ''
            acodec = ''
            
            # Get duration and container from format
            if 'format' in data:
                duration = float(data['format'].get('duration', 0))
                info.playtime = int(duration)
                container = data['format'].get('format_name', '').split(',')[0]
            
            # Get video/audio stream info
            for stream in data.get('streams', []):
                codec_type = stream.get('codec_type')
                
                if codec_type == 'video':
                    info.width = stream.get('width', 0)
                    info.height = stream.get('height', 0)
                    vcodec = stream.get('codec_name', '')
                    
                    # Handle rotation
                    rotation = 0
                    if 'tags' in stream:
                        rotation = int(stream['tags'].get('rotate', 0))
                    if 'side_data_list' in stream:
                        for side_data in stream['side_data_list']:
                            if 'rotation' in side_data:
                                rotation = abs(int(side_data['rotation']))
                    
                    # Swap width/height for 90/270 rotation
                    if rotation in (90, 270):
                        info.width, info.height = info.height, info.width
                    
                    # Parse fps
                    fps_str = stream.get('r_frame_rate', '0/1')
                    if '/' in fps_str:
                        num, den = fps_str.split('/')
                        if int(den) > 0:
                            info.fps = int(int(num) / int(den))
                
                elif codec_type == 'audio':
                    acodec = stream.get('codec_name', '')
                    if info.playtime == 0:
                        duration = float(stream.get('duration', 0))
                        info.playtime = int(duration)
            
            # Map to MEGA codec IDs using known shortformats
            info.shortformat = MediaProcessor._get_shortformat(container, vcodec, acodec)
            
            # If shortformat is 0 (custom), we'd need codec IDs
            # For now, set to 255 (unknown) if we can't determine shortformat
            if info.shortformat == 0:
                info.shortformat = 255
            
            return info if info.playtime > 0 else None
            
        except Exception:
            return None
    
    @staticmethod
    def _get_shortformat(container: str, vcodec: str, acodec: str) -> int:
        """
        Map container/codec combination to MEGA shortformat ID.
        
        Common shortformat values:
        1: mp42:avc1:mp4a-40-2 (MP4 with H.264 video and AAC audio)
        2: mp42:avc1:'' (MP4 with H.264 video, no audio)
        3: mp42:'':mp4a-40-2 (MP4 with AAC audio only)
        
        Returns 255 for unknown formats.
        """
        # Normalize codec names
        container = container.lower()
        vcodec = vcodec.lower()
        acodec = acodec.lower()
        
        # Map common ffprobe names to MEGA format
        is_mp4 = container in ('mp4', 'mov', 'm4a', 'm4v', 'quicktime')
        is_h264 = vcodec in ('h264', 'avc1', 'avc')
        is_aac = acodec in ('aac', 'mp4a')
        
        if is_mp4:
            if is_h264 and is_aac:
                return 1  # mp42:avc1:mp4a-40-2
            elif is_h264 and not acodec:
                return 2  # mp42:avc1:''
            elif not vcodec and is_aac:
                return 3  # mp42:'':mp4a-40-2
        
        # For other formats, return 255 (unknown)
        return 255
