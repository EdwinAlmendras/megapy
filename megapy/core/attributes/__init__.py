"""
Attributes module for file attributes including thumbnails, previews, and media metadata.

This module provides:
- CustomAttributes: Model for custom attributes with minimized keys
- ThumbnailService: Auto-generation of 240x240 JPEG thumbnails (80% quality)
- PreviewService: Auto-generation of max 1024px JPEG previews (85% quality)
- MediaInfo: Video/audio metadata (resolution, duration, fps, codecs)
- MediaAttributeService: Encode/decode MEGA media attributes (:8* and :9*)
- MediaProcessor: Extract metadata from media files using ffprobe
"""
from .models import (
    CustomAttributes,
    FileAttributes,
    AttributeType
)
from .packer import AttributesPacker
from .thumbnail import ThumbnailService
from .preview import PreviewService
from .media import (
    MediaInfo,
    MediaAttributeService,
    MediaProcessor,
    MediaResult,
    xxtea_encrypt,
    xxtea_decrypt,
    _xxkey,
    _bytes_to_uint32_le,
    _uint32_to_bytes_le,
)

__all__ = [
    'CustomAttributes',
    'FileAttributes',
    'AttributeType',
    'AttributesPacker',
    'ThumbnailService',
    'PreviewService',
    'MediaInfo',
    'MediaAttributeService',
    'MediaProcessor',
    'MediaResult',
    'xxtea_encrypt',
    'xxtea_decrypt',
]
