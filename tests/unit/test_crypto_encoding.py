"""Tests for Base64 encoding utilities."""
import pytest
from megapy.core.crypto.utils.encoding import Base64Encoder


class TestBase64Encoder:
    """Test suite for Base64Encoder."""
    
    def test_encode_basic(self):
        """Test basic encoding."""
        encoder = Base64Encoder()
        data = b"Hello, World!"
        encoded = encoder.encode(data)
        
        assert isinstance(encoded, str)
        assert '+' not in encoded
        assert '/' not in encoded
        assert '=' not in encoded
    
    def test_decode_basic(self):
        """Test basic decoding."""
        encoder = Base64Encoder()
        original = b"Hello, World!"
        encoded = encoder.encode(original)
        decoded = encoder.decode(encoded)
        
        assert decoded == original
    
    def test_encode_decode_roundtrip(self):
        """Test encode/decode roundtrip with various data."""
        encoder = Base64Encoder()
        test_cases = [
            b"",
            b"a",
            b"ab",
            b"abc",
            b"abcd",
            b"\x00\x01\x02\x03",
            b"\xff" * 100,
            bytes(range(256)),
        ]
        
        for data in test_cases:
            encoded = encoder.encode(data)
            decoded = encoder.decode(encoded)
            assert decoded == data, f"Roundtrip failed for {data[:20]}..."
    
    def test_decode_with_padding(self):
        """Test decoding handles padding correctly."""
        encoder = Base64Encoder()
        # Standard base64 with padding
        data_with_padding = "SGVsbG8="
        decoded = encoder.decode(data_with_padding)
        assert decoded == b"Hello"
    
    def test_decode_without_padding(self):
        """Test decoding without padding."""
        encoder = Base64Encoder()
        data_without_padding = "SGVsbG8"
        decoded = encoder.decode(data_without_padding)
        assert decoded == b"Hello"
    
    def test_url_safe_characters(self):
        """Test URL-safe character replacement."""
        encoder = Base64Encoder()
        # Data that would produce + and / in standard base64
        data = b"\xfb\xff\xfe"
        encoded = encoder.encode(data)
        
        assert '-' in encoded or '_' in encoded or ('+' not in encoded and '/' not in encoded)
    
    def test_decode_url_safe_characters(self):
        """Test decoding URL-safe characters."""
        encoder = Base64Encoder()
        # URL-safe encoded string
        url_safe = "-_"
        standard = "+/"
        
        # Both should decode to same bytes
        decoded_url = encoder.decode(url_safe + "==")
        decoded_std = encoder.decode(standard + "==")
        assert decoded_url == decoded_std
    
    def test_encode_empty_bytes(self):
        """Test encoding empty bytes."""
        encoder = Base64Encoder()
        result = encoder.encode(b"")
        assert result == ""
    
    def test_decode_empty_string(self):
        """Test decoding empty string."""
        encoder = Base64Encoder()
        result = encoder.decode("")
        assert result == b""
    
    def test_binary_data(self):
        """Test encoding/decoding binary data."""
        encoder = Base64Encoder()
        binary_data = bytes(range(256))
        
        encoded = encoder.encode(binary_data)
        decoded = encoder.decode(encoded)
        
        assert decoded == binary_data
        assert len(decoded) == 256


class TestBase64EncoderEdgeCases:
    """Edge case tests for Base64Encoder."""
    
    def test_large_data(self):
        """Test encoding large data."""
        encoder = Base64Encoder()
        large_data = b"x" * 1_000_000
        
        encoded = encoder.encode(large_data)
        decoded = encoder.decode(encoded)
        
        assert decoded == large_data
    
    def test_null_bytes(self):
        """Test handling null bytes."""
        encoder = Base64Encoder()
        data_with_nulls = b"\x00\x00\x00test\x00\x00"
        
        encoded = encoder.encode(data_with_nulls)
        decoded = encoder.decode(encoded)
        
        assert decoded == data_with_nulls
    
    def test_invalid_base64_raises_error(self):
        """Test invalid base64 raises error."""
        import binascii
        encoder = Base64Encoder()
        
        # Single character is invalid base64 (not multiple of 4 after padding calc)
        with pytest.raises(binascii.Error):
            encoder.decode("A")
