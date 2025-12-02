"""
Unit tests for MediaAttribute encoding/decoding.

Based on MEGA webclient's MediaAttribute implementation.
"""
import pytest
from megapy.core.attributes.media import (
    MediaInfo,
    MediaAttributeService,
    xxtea_encrypt,
    xxtea_decrypt,
    _xxkey,
    _bytes_to_uint32_le,
    _uint32_to_bytes_le,
)


class TestXXTEA:
    """Tests for XXTEA encryption/decryption."""
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypt/decrypt are inverse operations."""
        data = [0x12345678, 0x9ABCDEF0]
        key = [0x11111111, 0x22222222, 0x33333333, 0x44444444]
        
        encrypted = xxtea_encrypt(data.copy(), key)
        decrypted = xxtea_decrypt(encrypted.copy(), key)
        
        assert decrypted == data
    
    def test_encrypt_changes_data(self):
        """Test that encryption actually changes the data."""
        data = [0x12345678, 0x9ABCDEF0]
        key = [0x11111111, 0x22222222, 0x33333333, 0x44444444]
        
        encrypted = xxtea_encrypt(data.copy(), key)
        
        assert encrypted != data
    
    def test_xxkey_extraction(self):
        """Test that xxkey extracts last 4 elements."""
        filekey = [1, 2, 3, 4, 5, 6, 7, 8]
        
        result = _xxkey(filekey)
        
        assert result == [5, 6, 7, 8]


class TestBytesConversion:
    """Tests for bytes/uint32 conversion."""
    
    def test_bytes_to_uint32_le(self):
        """Test little-endian bytes to uint32 conversion."""
        data = bytes([0x78, 0x56, 0x34, 0x12, 0xF0, 0xDE, 0xBC, 0x9A])
        
        result = _bytes_to_uint32_le(data)
        
        assert result == [0x12345678, 0x9ABCDEF0]
    
    def test_uint32_to_bytes_le(self):
        """Test uint32 to little-endian bytes conversion."""
        values = [0x12345678, 0x9ABCDEF0]
        
        result = _uint32_to_bytes_le(values)
        
        assert result == bytes([0x78, 0x56, 0x34, 0x12, 0xF0, 0xDE, 0xBC, 0x9A])
    
    def test_roundtrip(self):
        """Test bytes -> uint32 -> bytes roundtrip."""
        original = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        
        uint32s = _bytes_to_uint32_le(original)
        result = _uint32_to_bytes_le(uint32s)
        
        assert result == original


class TestMediaInfo:
    """Tests for MediaInfo dataclass."""
    
    def test_is_video(self):
        """Test is_video property."""
        video = MediaInfo(width=1920, height=1080, playtime=120)
        audio = MediaInfo(width=0, height=0, playtime=180)
        
        assert video.is_video is True
        assert audio.is_video is False
    
    def test_is_audio(self):
        """Test is_audio property."""
        video = MediaInfo(width=1920, height=1080, playtime=120)
        audio = MediaInfo(width=0, height=0, playtime=180)
        
        assert video.is_audio is False
        assert audio.is_audio is True
    
    def test_duration_formatted_minutes(self):
        """Test duration formatting for < 1 hour."""
        info = MediaInfo(playtime=185)  # 3:05
        
        assert info.duration_formatted == "3:05"
    
    def test_duration_formatted_hours(self):
        """Test duration formatting for >= 1 hour."""
        info = MediaInfo(playtime=3725)  # 1:02:05
        
        assert info.duration_formatted == "1:02:05"
    
    def test_resolution(self):
        """Test resolution string."""
        info = MediaInfo(width=1920, height=1080)
        
        assert info.resolution == "1920x1080"
    
    def test_resolution_empty_for_audio(self):
        """Test resolution is empty for audio-only."""
        info = MediaInfo(width=0, height=0, playtime=120)
        
        assert info.resolution == ""
    
    def test_is_valid(self):
        """Test is_valid property."""
        valid = MediaInfo(shortformat=1)
        invalid = MediaInfo(shortformat=255)
        
        assert valid.is_valid is True
        assert invalid.is_valid is False


class TestMediaAttributeService:
    """Tests for MediaAttributeService encoding/decoding."""
    
    def test_has_media_attribute(self):
        """Test detection of media attributes in fa string."""
        with_media = "123:0*abc/123:8*xyz"
        without_media = "123:0*abc/123:1*def"
        
        assert MediaAttributeService.has_media_attribute(with_media) is True
        assert MediaAttributeService.has_media_attribute(without_media) is False
        assert MediaAttributeService.has_media_attribute(None) is False
    
    def test_encode_decode_roundtrip(self):
        """Test that encode/decode are inverse operations."""
        service = MediaAttributeService()
        
        # Create a file key (32 bytes = 8 uint32)
        file_key = bytes([
            0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18,
            0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
            0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38,
        ])
        
        original = MediaInfo(
            width=1920,
            height=1080,
            fps=30,
            playtime=120,
            shortformat=1
        )
        
        # Encode
        encoded = service.encode(original, file_key)
        assert encoded.startswith("8*")
        
        # Decode (add fake user_id prefix)
        fa = f"123:{encoded}"
        decoded = service.decode(fa, file_key)
        
        assert decoded is not None
        assert decoded.width == original.width
        assert decoded.height == original.height
        assert decoded.fps == original.fps
        assert decoded.playtime == original.playtime
        assert decoded.shortformat == original.shortformat
    
    def test_decode_with_codec_info(self):
        """Test decode with attribute 9 (codec details)."""
        service = MediaAttributeService()
        
        file_key = bytes([
            0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18,
            0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
            0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38,
        ])
        
        original = MediaInfo(
            width=1280,
            height=720,
            fps=24,
            playtime=300,
            shortformat=0,  # Custom format, needs attr 9
            container=1,
            videocodec=2,
            audiocodec=3
        )
        
        # Encode
        encoded = service.encode(original, file_key)
        assert "8*" in encoded
        assert "9*" in encoded  # Should have attr 9
        
        # Decode
        fa = f"123:{encoded}"
        decoded = service.decode(fa, file_key)
        
        assert decoded is not None
        assert decoded.container == original.container
        assert decoded.videocodec == original.videocodec
        assert decoded.audiocodec == original.audiocodec
    
    def test_decode_invalid_fa(self):
        """Test decode with invalid fa string."""
        service = MediaAttributeService()
        file_key = bytes(32)
        
        assert service.decode(None, file_key) is None
        assert service.decode("", file_key) is None
        assert service.decode("123:0*abc", file_key) is None
    
    def test_decode_invalid_key(self):
        """Test decode with invalid key."""
        service = MediaAttributeService()
        
        assert service.decode("123:8*abc", bytes(8)) is None
        assert service.decode("123:8*abc", bytes(0)) is None


class TestMediaAttributeFromWebclient:
    """Test using example from MEGA webclient."""
    
    def test_webclient_example(self):
        """Test with the example from MediaAttribute.test() in webclient."""
        # From crypto.js MediaAttribute.test():
        # fa: '470:8*COXwfdF5an8'
        # k: [-989750631, -795573481, -2084370882, 1515041341, 
        #     -5120575, 233480270, -727919728, 1882664925]
        
        import struct
        
        # Convert signed int32 to bytes (little-endian)
        k_signed = [-989750631, -795573481, -2084370882, 1515041341, 
                    -5120575, 233480270, -727919728, 1882664925]
        
        # Convert to unsigned and then to bytes
        file_key = b''
        for v in k_signed:
            # Convert signed to unsigned 32-bit
            if v < 0:
                v = v + (1 << 32)
            file_key += struct.pack('<I', v)
        
        fa = "470:8*COXwfdF5an8"
        
        service = MediaAttributeService()
        info = service.decode(fa, file_key)
        
        # The decode should work without errors
        # We don't know the exact values but it shouldn't be None
        # and shortformat shouldn't be 255 (invalid)
        assert info is not None
        print(f"Decoded: width={info.width}, height={info.height}, "
              f"fps={info.fps}, playtime={info.playtime}, "
              f"shortformat={info.shortformat}")
